---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude"]
status: "#ai-written"
---

# Logging

What the toolkit writes to its logs, where to find them, and what you can and can't expect to see there. Covers the changes shipped 2026-07-14 (specs 9.154–9.159 — see [tasks/infrastructure.md](tasks/infrastructure.md)).

## Where logs live

All application logging goes to stderr, which Docker captures per container. There is no log file inside the container (the Docker settings files remove the file handler). To read logs:

```bash
docker compose logs toolkit          # web app
docker compose logs mailer           # mailout daemon
docker compose logs scheduler        # daily maintenance jobs
docker compose logs -f --tail 100 toolkit   # follow live
```

Every service is capped at 3 files × 10MB of JSON logs (set per service in the compose files), so a container holds roughly the most recent 30MB of output. Older lines are gone; anything that must survive belongs in the database (see "Gaps" below).

## Log format and levels

Lines look like:

```
[14/Jul/2026 19:46:09] INFO [toolkit.email:69] EMAIL SENT to=[someone@example.com] subject='Welcome' backend=django.core.mail.backends.console.EmailBackend
```

That is timestamp, level, logger name and line number, message.

- Everything under the `toolkit.*` logger hierarchy is emitted at DEBUG and above, in every environment.
- The root logger (framework noise, third-party libraries) is DEBUG in dev and WARNING in production, so a stray `logging.info(...)` call would vanish in production. Always log via a module logger (`logger = logging.getLogger(__name__)`); this exact mistake silently discarded showing-deletion logs until 2026-07-14 (Bug AQ).

## Email logging

Every email the toolkit attempts to send, from any code path (mailouts, password resets, digests, notifications), passes through a logging wrapper (`toolkit/util/email_backend.py`) and produces exactly one line under the `toolkit.email` logger:

| Line | Level | Meaning |
|---|---|---|
| `EMAIL SENT to=[...] subject=... backend=...` | INFO | The configured backend accepted the message |
| `EMAIL FAILED to=[...] subject=... error=...` | ERROR | The backend raised; the error text is included |
| `EMAIL NOT SENT to=[...] (backend reported 0 sent)` | ERROR | The backend declined without raising |

Two things to understand about these lines:

- **"Sent" means handed to the backend.** With the console backend (dev and, currently, production) nothing is actually delivered — the full message is printed to the container log just below the `EMAIL SENT` line. Only with a real SMTP backend does SENT mean "accepted by the mail server", and even then delivery to the inbox is not guaranteed.
- **Bodies are never in the log line.** Recipients, subject, and backend only. This is deliberate: bodies contain personal content and live password-set links. The console backend does print full bodies as its normal output, so treat log access as privileged.

The real backend is set by `TOOLKIT_WRAPPED_EMAIL_BACKEND` in the settings file; `EMAIL_BACKEND` always points at the wrapper.

### The email log page

Each send also writes a `SentEmailLog` database row, so the history survives log rotation. Panopticon users can browse it at `/audit/emails/` (nav: Meta → Email log): newest first, green/red status, expandable error text, filter by outcome, search by recipient, subject, or trigger. Mailouts appear as one summary row per batch ("mailout batch: N recipients"), not per recipient, since the mailout UI's own job record has the per-job detail. Rows are purged after `email_log_retain_days` (Site settings, default 90 days), and anonymising a volunteer scrubs their address from old rows.

Every row also records **what set the send off**: `trigger_source` (a short label, e.g. "Web request", "Scheduled job: send_volunteer_digest", "Mailout job #42") and, where a specific person's action caused it, `triggered_by` (the logged-in user). Web-request sends are tagged automatically by `EmailTriggerMiddleware`, which reads `request.user`; management commands and the mailout sender set their own label explicitly via `toolkit.audit.models.email_trigger()` / `set_email_trigger()`. Rows written before this was added (or by code paths nobody's tagged yet) show as "unknown" rather than guessing. The page itself also explains, in plain language, what the currently configured backend actually does with a message: console/file backends send nothing at all, and only SMTP hands mail to a real server, which is still no guarantee of inbox delivery (see the bounce-handling note below).

### What users see when email fails

Notification emails no longer fail silently or crash the page. If an email fails during a volunteer save, suspension, or last-gasp send, the operation still completes and the page shows a warning ("Saved, but the notification email failed to send..."), while the ERROR line above lands in the log. Bulk last-gasp sends continue past individual failures and report a failure count; failed recipients keep no cooldown, so they can be retried.

### Mailouts

The mailout pipeline logs its job lifecycle under `toolkit.mailer.*`, and each recipient send produces a `toolkit.email` line in the `mailer` container's log. The authoritative record of a mailout is the `MailoutJob` row itself (state, progress, send count), visible in the mailout UI — use that, not the logs, to answer "did the mailout run?".

### What we don't yet do: bounce handling

The toolkit currently has **no way to learn that an address is dead** after a send. A `SentEmailLog`/`Member.mailout_failed` row only turns up an error if the SMTP conversation itself rejects the message synchronously (e.g. "mailbox full" returned mid-transaction); `Member.mailout_failed` exists on the model but nothing sets it automatically today, it's admin-editable only. Most real-world bounces (dead/decommissioned mailbox, "user unknown") come back later as an asynchronous bounce message to the envelope sender, which the toolkit has no process for reading. In production, `TOOLKIT_WRAPPED_EMAIL_BACKEND` is still set to the console backend anyway, so nothing has actually left the building yet, but this becomes a real risk the day SMTP is switched on: repeatedly mailing a dead address is exactly the pattern that gets a sending domain rate-limited or blocklisted. See spec [9.160](tasks/infrastructure.md) for the proposed design.

## Scheduler

The `scheduler` container prints one line per job run:

```
[2026-07-14 03:00] [auto_dormancy] starting
[2026-07-14 03:00] [auto_dormancy] done
```

A failed job logs `FAILED (exit N)` and the loop carries on. The schedule itself is printed at container start. The scheduler also purges the file-based email archive (`/log/emails`, where configured) of files older than 60 days, and runs `purge_audit_logs` daily to enforce the email/deletion log retention settings.

## Deletions

Destructive actions are recorded twice: a WARNING log line with attribution ("deleted by username" — WARNING so it survives the production root-logger level), and a durable `DeletionLog` row shown at `/audit/deletions/` (linked from the email log page). Covered: bookings (showings) deleted through the edit UI, and any Event deletion — Event deletion is blocked at the model level, so if one ever appears here it means something bypassed the guard and warrants investigation. Routine archiving (tags, roles) and seed-data resets are deliberately not logged. Rows are purged after `deletion_log_retain_days` (Site settings, default 365 days).

## What is NOT in the logs

- **Email bodies** (see above), except as console-backend output.
- **Admin error emails.** The old `mail_admins` handler was dead config (no logger attached, empty `ADMINS`) and was removed; revisit once a real SMTP relay exists.

## Security note

Sent emails include password-set links that stay live for up to 7 days (`PASSWORD_RESET_TIMEOUT`) unless used. The log lines never contain them, but console-backend output and the file archive do. Anyone with `docker logs` or archive access effectively holds every unexpired reset link, so server access is the security boundary — do not widen access to logs or the archive (e.g. over HTTP) without stripping bodies. Fuller analysis in [tasks/infrastructure.md](tasks/infrastructure.md), spec 9.155.
