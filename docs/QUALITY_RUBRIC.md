---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Sonnet 5"]
status: "#ai-input"
---

# Quality rubric

A checkable standard for this codebase, synthesised during the September 2026 quality
pass (archived record: [ARCHIVE/QUALITY_PASS_2026_09.md](ARCHIVE/QUALITY_PASS_2026_09.md))
from three sources:

- The MiniMax M3 sweep (Chunk 5) — 68 files, deduplicated down to patterns that
  recurred in three or more files, plus one-off findings severe enough to name
  individually.
- The maintainability section of `docs/REVIEW_2026_OVERHAUL.md` (2026-06-12), whose
  security findings are already fixed but whose maintainability findings are not.
- A follow-up Kimi K2 Thinking sweep (same day, 2026-09-08) — 23 files, scoped
  narrowly to the security-relevant surface (redirect targets, file uploads,
  templates with raw `innerHTML`, unauthenticated entry points), run with a
  security-first/quality-secondary brief rather than MiniMax's general-quality one.
  Cost $0.28 across all 23 files via `openrouter/moonshotai/kimi-k2-thinking`. Raw
  reviews (gitignored) at `docs/QUALITY_PASS_RAW/chunk6_kimi_reviews/`, index at
  `docs/QUALITY_PASS_RAW/chunk6_kimi_index.md`.

  **A reliability gotcha worth recording alongside Chunk 5's `opencode`/stdin one:**
  2 of the 23 runs went agentic (used `bash`/`read`/`grep` to explore the wider repo
  instead of answering from the pasted file content) and silently ended with no
  final report after exhausting their tool-call budget — no error, just an empty or
  truncated output. Both were fixed by re-running with an explicit instruction to
  always conclude with a written report before ending the turn, even if that means
  cutting exploration short. Add that instruction pre-emptively on any future
  Kimi-thinking sweep rather than discovering the failure per-file.

  **Kimi's severity labels need a human triage pass, not automatic trust** — the
  same open-redirect finding was rated HIGH on one run and CRITICAL on an identical
  re-run, and the R14 authorization-check pattern (below) got five different
  severity ratings across five structurally identical instances in the same sweep.
  Treat its findings list as reliable, its priority ordering as not.
- **Quality Pass 2** (2026-09-08, see [QUALITY_PASS_2_2026_09.md](QUALITY_PASS_2_2026_09.md)) —
  a second MiniMax M3 sweep, 44 files, covering the pre-rewrite Cube-era code that
  Pass 1's chunk scoping never touched (`toolkit_auth/`, `members/forms.py` +
  `models.py`, `mailer/`, `diary/mailout_views.py` and several sibling `diary/`
  modules, `index/`, `util/`, management commands, templatetags). $0.67 total, zero
  empty outputs across all 44. Raw reviews at
  `docs/QUALITY_PASS_RAW/chunk_qp2_reviews/`, index at
  `docs/QUALITY_PASS_RAW/chunk_qp2_index.md`. Adds R15–R16 below and a second
  "Unfixed findings" section for this pass specifically.
- **Quality Pass 2, Tier 1 re-review** (2026-09-09) — the plan for Quality Pass 2
  originally scoped a Kimi K2 Thinking second opinion on Tier 1 (auth, permissions,
  mailer — the "money-adjacent" files), deferred at the time for budget. Decided
  2026-09-09 not to run Kimi at all going forward (cost/token premium not worth it
  for the quality delta), so instead re-read the
  MiniMax reviews already sitting in `chunk_qp2_reviews/` for those 12 Tier 1 files
  against what had actually been synthesised. Found 9 real findings (items 11–19
  below) that the first synthesis pass had missed — no new API spend, same source
  material, closer reading. Nothing rose to "fix immediately" severity like the
  GDPR email-scrub bug did; all left for triage.

  **One MiniMax finding turned out to be a false positive on verification** —
  worth recording as a specific caution alongside the general "triage before
  trusting" rule above, because this one *looked* airtight. It read
  `toolkit_auth/decorators.py:172`'s `logger.warning(f"login failed for:
  {credentials} from {ip}")` as logging a raw password on every failed login.
  Checked against Django's actual `contrib.auth.authenticate()` source
  (`_clean_credentials`, `django/contrib/auth/__init__.py`): Django itself
  redacts any credential key matching `/api|token|key|secret|password|signature/i`
  to `"********"` before firing the `user_login_failed` signal this code
  subscribes to — the `password` field is never live by the time this line sees
  it. A finding citing Django signal/framework behaviour as the mechanism is
  exactly the kind of claim to verify against the actual framework source before
  treating as confirmed, not just against this codebase's own call sites.

**How to use this:** check new and touched code against the rules below rather than
re-paying for external review per file. When a rule and the code disagree, fix the
code, not the rule — unless the disagreement reveals the rule was wrong, in which case
fix this file and say why in the commit. The "Unfixed findings" list at the foot is
historical; anything from it still open is tracked as a bug in
[tasks/known-issues.md](tasks/known-issues.md) (Bugs AV–AY), which is the list to update.

---

## Checkable rules

Each rule names what to grep for or look at, not just what to avoid in the abstract.

### R1 — No module-level `logger.setLevel(...)`

Found in 15+ files (`diary/edit_views/*.py`, `members/views/_common.py`, others).
Django's `LOGGING` dictConfig governs effective level from `settings_*.py`; a
per-module call at import time either does nothing or silently overrides deployment
config, and there's no way to tell which without reading the handler wiring.

**Check:** `grep -rn "logger.setLevel" toolkit --include=*.py` outside `settings_*.py`
should return nothing.

### R2 — Catch the specific exception, not `Exception`

Found in ~12 files. `request.user.volunteer` access wrapped in bare
`except Exception: pass` instead of `except Volunteer.DoesNotExist`; email sends
wrapped in `except Exception` instead of `SMTPException`. Masks `AttributeError` /
`KeyError` from real bugs as if they were expected failures.

**Check:** a bare `except Exception` (or `except:`) needs an inline comment naming
the specific *unpredictable* failure class that justifies the width (SMTP, a
subprocess, PDF rendering). "Defends against a rename typo" is not sufficient
justification — that's what the exception class list is for.

### R3 — Comments say why, not what

Found in 8+ files: `# Shared utility method:` headers, `# Overloaded Django ORM
method:` — restating what the next line already says via its name.

**Check:** a comment whose content is a substring-paraphrase of the function/class
name or line immediately below it should be deleted, not kept "for clarity."

### R4 — One source of truth for a vocabulary or field set touched from 3+ places

The single largest theme in the sweep, ~15 files. Cost fields duplicated across
`forms.py` (4 places); mark-type vocabulary in `misc.py` (3 places); permission-tier
additions across `site_config.py` and 4 other files with no cross-check;
`STATUS_*` constants in `operations/models.py` + `admin.py` + `maintenance.py` +
templates (4–5 sites each).

**Check:** if a single conceptual change (add an enum value, add a field) requires
editing 3+ files by hand, either derive the others from one constant, or add a
consistency test — `members/tests/test_site_config.py:342-415` already does this for
one such case; extend the pattern rather than admiring it in isolation. This is also
exactly the shape of the pre-existing "permission table drift" and "SiteConfiguration
triple-bookkeeping" findings from `REVIEW_2026_OVERHAUL.md` (2026-06-12,
`edit_site_configuration` and `SiteConfigurationForm.fields` vs the model vs
`field_groups`) — still open, not touched by this pass yet.

### R5 — A failed form/lookup on POST must show an error, not a silent success-looking redirect

Found in ~6 files: `tags_roles_rooms.py` (6 sites), `misc.py`, `donations.py`,
`lost_found.py`. An invalid form on a POST handler redirects with no
`messages.error(...)`, so the user sees what looks like a successful save.

**Check:** every `except <SpecificError>: pass` or invalid-form branch on a POST
handler either calls `messages.error(...)` (or equivalent) or has a comment
explaining why silence is correct there.

### R6 — Lazy `%s` logging, not f-strings, and check for PII first

Found in 3+ files (`diary_overview.py`, `templates.py`,
`volunteer_bulk_record.py:58-61` — the last one also puts a member's name into a log
line via `repr`).

**Check:** `logger.*(f"...")` should be `logger.*("...%s...", value)`. Separately,
before adding any interpolated value to a log line, check it isn't a member/volunteer
name, email, or address.

### R7 — `django.utils.html.escape` only in HTML context

Found in `diary_overview.py:493` (inside a `json.dumps` response) and
`rota.py:321` (on a `text/plain` response). Both mis-escape for their actual
consumer.

**Check:** a view returning `JsonResponse`/`json.dumps` or `text/plain` should never
call `escape()` — rely on `json.dumps`'s own encoding, or don't escape.

### R8 — Name the JSON contract between a view and its consuming template's JS

Found in 10+ places: `film.py` → `form_event.html`'s `data-film`; `floorplan.py` /
`loft.py` → `floorplan.html`'s JS; `RoomNote` GET/POST shape drift within
`floorplan.py` itself (lines ~74-84 vs ~141-148). Renaming a dict key on the Python
side breaks the JS silently — no Python test catches it.

**Check:** not fully fixable without a schema layer (out of scope for this pass), but
any view returning JSON consumed by inline template JS should have a comment naming
the consuming template, so a rename is `grep`-able on both sides before it ships.

### R9 — Business-rule numbers get a named constant

Found in 6+ files: the 3-link cap in `templates.py:209-211`,
`_MAX_BATCH_SHOWINGS = 52` in `forms.py`, the 28-day "due soon" window in
`operations/models.py:139`, the 72-hour reminder window in
`send_induction_reminders.py:30`, the rate limit `5` in `bulletins.py:137`
(inconsistent with the sibling `bulletin_default_expiry_days`, which *is*
admin-configurable, sitting right next to it).

**Check:** a bare numeric literal governing a window, cap, or threshold gets a named
module constant. If a sibling value of the same kind is already
`SiteConfiguration`-configurable, the new one should be too, or there's a one-line
comment saying why not.

### R10 — No wildcard imports hiding symbol origin

`members/views/*.py`'s `from ._common import *`. Already tracked as Chunk 11 in
QUALITY_PASS.md; MiniMax surfaced it independently in nearly every file in that
package, each time as the top "hard to modify safely" item. No new information —
strong independent confirmation this is worth doing, not a new rule to add elsewhere.

### R11 — Local imports need a stated reason

Found in 4+ files: `film.py:36,108` (`import urllib.error` — stdlib, always
importable, no reason to defer it), `collectives.py:17` (local re-import of
something already at module scope). Contrast with genuinely critical local
imports that already carry a comment (`diary/edit_views/_common.py:14`,
`labs/models.py:433`) — those are fine as-is.

**Check:** a local (function-body) import needs a one-line comment naming the
specific circular-import path it avoids. "Looks defensive" is not a reason; move it
to module scope if it can't name one.

### R12 — Never pass an attacker-influenced value straight into `redirect()`

Added 2026-09-08 after the second instance of this exact bug turned up independently
in two different apps: `diary/edit_views.py:2609` (`request.POST.get("next")`,
already fixed per `REVIEW_2026_OVERHAUL.md`) and `labs/views/bulletins.py:199,213`
(`request.META.get("HTTP_REFERER")`, still open — see "Unfixed findings" below). Both
are the same root cause — a redirect target read from user-controlled input with no
validation — found in two separate reviews months apart, which means it's a class,
not a one-off.

**Check:** `grep -rn "redirect(" toolkit --include=*.py` and check every call whose
argument traces back to `request.POST`, `request.GET`, or `request.META` (most
commonly `HTTP_REFERER` or a `next` param). Each one needs
`django.utils.http.url_has_allowed_host_and_scheme` (or a hardcoded/reversed URL) —
no exceptions, because the fix is one line and the alternative is an open redirect
usable for phishing off this domain's trust.

### R13 — Match the escape filter to the actual sink, not the source

Added 2026-09-08 from the Kimi K2 Thinking security sweep (below), which found three
genuinely different escaping bugs — and, tellingly, also got one escaping
recommendation backwards itself, which is exactly why this needs to be a rule and not
just "be careful": `django.utils.html.escape`/`|escape` is for HTML-attribute or
element context; `|escapejs` is for a JS *string literal* embedded directly in
`&lt;script&gt;`, not for a value later assigned via `.innerHTML =` (that still needs
HTML-escaping, because the browser parses the resulting string as markup, not as a
literal); `mark_safe(json.dumps(...))` is only safe if the JSON itself has been
escaped against `&lt;`/`&gt;`/`&amp;` before the `mark_safe` call (see `daterange.py`'s
`safe_json()` for the correct pattern — `_rooms_json()` in
`diary/edit_views/showings.py` skips it and is a real finding, see "Unfixed findings"
below).

**Check:** for every `|safe`, `|escapejs`, `mark_safe(...)`, or `.innerHTML =`, name
the actual sink out loud before picking the filter — HTML attribute, script-body
string literal, or DOM property assignment are three different contexts with three
different rules, and picking the wrong one because "it's near a `&lt;script&gt;` tag"
is how R13's own source findings happened.

### R14 — Shared-object modify/delete views are intentionally open to any volunteer; write down when they're not

Added 2026-09-08 from the Kimi sweep, which found the same shape independently in
five files: `labs/views/collectives.py` (`collective_edit`), `area_photos.py`
(upload/delete), `loft.py` (item/photo delete), `exchange.py`
(`mark_on_loan`/`mark_returned`), `jobs.py` (`job_resolve`) — `@login_required` alone,
with no check that the acting user has any relationship to the specific object being
changed. Kimi's own severity ratings on this identical shape swung from "clean, fine
for this trust model" to "critical, do not deploy" depending on which file it
happened to be looking at, which is what forced this to be an explicit written
decision rather than something a future pass re-litigates per file.

**Decided 2026-09-08 (Jonny):** intentional, not a bug, for all five. Explicit
reasoning: "for shared resources like the spaces, it's important that one person
can't block others [from] replacing the image" — for a shared physical resource
(a room's photo, a loft item, a collective's listing), the realistic failure mode
isn't malicious editing by another volunteer, it's one person's absence or oversight
blocking everyone else from a routine update. Locking these down would trade a rare,
low-cost risk (a volunteer edits something they maybe shouldn't) for a common,
annoying one (nobody can fix a stale photo because the one person who "owns" it isn't
around). Consistent with S+S's deliberately non-hierarchical volunteer model — see
this repo's own culture notes.

**Check:** before adding a *new* modify/delete view on a shared resource, this
default now applies — open to any logged-in volunteer, no ownership check needed —
**unless** the object represents something where a wrong edit is costly or hard to
reverse (financial records, permission grants, another volunteer's personal data).
In that narrower case, write down in a one-line comment why this one departs from the
default. Don't add an ownership check "just in case" on a shared resource; that's the
thing this decision rules out.

### R15 — An external side-effect and its own completion-state write are one unit; don't let them diverge

Added 2026-09-08 from Quality Pass 2's MiniMax sweep, which found the same shape
independently in three files: `mailer/sender.py:184,224` (a cancelled send loop
`break`s but still falls through to `do_complete(sent=sent)` — an admin who cancels
a 10,000-recipient send after 200 sees the job marked "Complete", not "Cancelled");
`util/email_backend.py` (~82-104, the success-path audit write is outside the
exception handler that protects the failure path, so a successful send followed by
a failed audit-log write leaves no record it went out — an operator restoring from
the audit trail could legitimately re-send already-delivered mail); and
`util/management/commands/send_volunteer_digest.py` (~215-220, `msg.send()`
succeeds but the following `volunteer.save(update_fields=["last_digest_sent_at"])`
raising means next week's run re-sends the identical digest).

**Check:** grep for `\.send(` or another external-effect call followed, in the same
function, by a separate persistence call (`.save()`, an audit-log write, a
state-transition method like `do_complete`/`do_fail`). Trace what state the system
is left in if the persistence call raises, or if a `break`/early-return skips the
state transition the effect actually implies — "sent but not recorded" and "not
sent but recorded as sent" are both real bugs, not edge cases to wave away.

### R16 — A falsy-but-legitimate value (`0`, `""`, explicit `False`) is not "not provided"

Added 2026-09-08 from Quality Pass 2's MiniMax sweep, found in 3+ files:
`diary/poster.py:206-207` (`cfg.thumbnail_crop_width or 600` — `0` is a valid crop
width, indistinguishable here from "unset"), `util/templatetags/thumbnail_l.py:83,88`
(`bar_colour or ""`, a size tuple defaulted the same way), `mailer/models.py:55-56`
(a blank `body_html` string doubles as the tri-state "don't send HTML" flag, with no
way to tell "unset" from "explicitly cleared"). `diary/daterange.py:92`'s
`if user_days_ahead:` dropping `?days=0` from a query string is the same shape but
**unverified** — check whether `user_days_ahead` is the string `"0"` (truthy) or an
already-cast `int(0)` (falsy) before treating it as a fourth instance.

**Check:** grep for `\bor\s+\d`, `\bor\s+""`, or a bare `if value:` immediately after
a `request.GET.get(...)`/model-field read, wherever `0`, `""`, or `False` is a real
value distinct from "the caller didn't set this" — not everywhere `or`/truthy-checks
appear, only where the falsy value is meaningful.

---

## Explicitly not rubric material

MiniMax raised these and then, in several cases, self-corrected once it checked
context. Don't let a future pass re-flag them:

- **Long `help_text` and admin-facing prose.** Deliberate per
  `REVIEW_2026_OVERHAUL.md` — this project writes for non-expert Panopticon admins,
  not for line-count. Leave it.
- **Defensive `try/except JSONDecodeError` / malformed-input handling on endpoints
  reachable outside the trusted JS client.** Legitimate — curl, admin tooling, and
  future clients can hit these. Not AI-paranoia.
- **`re_path` vs `path()`, missing `app_name` namespaces.** Real but cosmetic;
  worth a mechanical pass sometime, not a rubric rule.
- **Single-caller helper functions.** MiniMax mostly concluded these were fine once
  it checked call-site count — several exist specifically to keep side-effecting
  logic (get_or_create, formset construction) legible. Don't chase "N=1 caller ⇒
  inline it" as a blanket rule.
- **Stylistic inconsistency with no behavioural consequence** (`@require_POST` vs
  `@require_http_methods(["POST"])`, `OrderedDict` vs `dict`). Ruff/black catch more
  of this more cheaply than prose guidance would.
- **A genuinely clean file is a real negative, not under-searching.** 10+ files
  (`audit/urls.py`, `inductions/admin.py`, `labs/admin.py`, `operations/admin.py`,
  `operations/models.py`, `operations/urls.py`, `send_consent_renewal_reminders.py`)
  came back with nothing to flag. The sweep wasn't finding-inflated.
- **(Quality Pass 2) Defensive branches guarding against a third-party API's
  undocumented, unversioned behaviour.** `diary/omdb.py`'s guards against an
  invalid-key response arriving with HTTP 200, or a normally-always-present `Type`
  field being absent, look like paranoia about states that "can't happen" — but
  OMDb is a service this project doesn't control and can't pin a contract against.
  Unlike defending against this codebase's own impossible states, insurance against
  an external API silently changing shape is legitimate. Leave it.
- **(Quality Pass 2) Code-smell findings in dev-only seed/fixture tooling**
  (`seed_dev_data.py`, `seed_data/fetch_trailers.py` — magic numbers, string-matched
  roles, fragile TOML writes). Real, but this is Docker-dev-only tooling with a
  single maintainer and zero production blast radius. Fix opportunistically if the
  file is next touched for another reason; don't spend Tier-1-grade review time here.
- **(Quality Pass 2) Docstring/comment examples that are wrong but purely
  descriptive** (`poster.py`'s stated character-count threshold not matching the
  code, `days_to_human.py` and `showing_date_format.py`'s wrong worked examples).
  Zero behavioural risk — these mislead a reader, not the program. Batch into one
  low-effort docs-fix pass rather than treating each as a separate finding.
- **(Quality Pass 2) `QuerySet.update()` bypassing `save()`/signals.** Found in
  `diary/signals.py` (an `Event.objects.filter(...).update(...)` caller never
  triggers the audit-trail signal) and `auto_dormancy.py` (bulk `.update()` skips
  any future "you've gone dormant" notification hook). Real and worth knowing, but
  only two instances and the existing R5 (silent failure on POST) already covers
  the same underlying "don't let a write silently skip its consequences" territory
  closely enough that a third full rule isn't earning its keep yet — note it here so
  a third instance prompts promoting it, rather than re-discovering the first two.

---

## Unfixed findings, ranked (historical, as of 2026-09-08)

Findings severe enough to fix directly rather than fold into a rubric rule. Status
at the close of the pass: the seven security items are fixed; item 12 now has its
regression test (`test_misconfigured_vols_admin_address_skips_email_not_save`);
item 13 was done by the dedup work; item 14 was decided, not a bug; item 15 was a
misreading (the suppressed argument is `request`, and the noqa is correct). Items 7
to 11 remain open as Bug AY in `tasks/known-issues.md`.

### Security findings — fixed 2026-09-08, out of band from the normal chunk cadence

All six below are now fixed, with regression tests, on `chore/quality-pass-2026-09`
(1,136 tests passing, up from 1,129; ruff/black clean). Kept here for the record —
struck through rather than deleted so a future pass doesn't re-flag the same shape
as new.

1. ~~**Stored XSS, `inductions/manage/session_detail.html`**~~ — **fixed.** Added
   an `escapeHtml()` JS helper and applied it to every server-response field
   (`item.username`, `d.name`, `d.existing_email`, `d.existing_username`,
   `e.name`/`e.error`, `data.desired_username`, `data.name`, `data.email`,
   `data.preview_username`, `data.signed_up_at`) reaching `.innerHTML` in this
   file. No automated test — this is a pure client-side JS sink with no Django
   test client coverage; needs a manual browser check per Chunk 9's existing
   "tests will not cover this" note.
2. ~~**Open redirect via `HTTP_REFERER`, `labs/views/bulletins.py:199,213`**~~ —
   **fixed.** Added `_redirect_to_referer()`, using
   `url_has_allowed_host_and_scheme` the same way `diary/edit_views/site_config.py`
   already does, falling back to `toolkit-index` for an off-site or missing
   referer. Regression tests in `labs/tests/test_bulletins.py`
   (`test_read_all_ignores_off_site_referer`,
   `test_bulletin_read_ignores_off_site_referer`,
   `test_read_all_honours_same_site_referer`).
3. ~~**Stored XSS, `diary/templates/form_showing.html:20`**~~ — **fixed.**
   `_rooms_json()` now calls `daterange.safe_json()` instead of raw
   `json.dumps()`. Regression test:
   `diary/tests/test_edit_showing.py::EditShowingRoomBookingTests::test_rooms_json_is_script_safe`.
4. ~~**Stored XSS, `members/templates/volunteer_bulk_record.html:198`**~~ —
   **fixed.** Removed the `|escapejs`-into-`innerHTML` anti-pattern; the
   qualification name is now rendered once, HTML-escaped, into a
   `<strong id="award-qual-name">` element, and the confirm-modal JS reads it
   back via `textContent` and the existing client-side `esc()` helper.
   Regression test:
   `members/tests/test_volunteers.py::TestBulkRecordTraining::test_qualification_name_is_html_escaped_not_js_escaped`.
5. ~~**JS-context XSS, `diary/templates/edit_event_template_detail.html:522`**~~ —
   **fixed.** Added the missing `|escapejs` to `event_template.name` in the
   `onclick="confirm(...)"` attribute. Regression test:
   `diary/tests/test_edit_misc.py::TemplateDeleteConfirmEscapingTests::test_template_name_with_quote_is_js_escaped`.
6. ~~**CSV formula injection, `inductions/views.py:488` (`manage_export_csv`)**~~
   — **fixed** for this call site: added `_csv_formula_guard()`, prefixing a
   leading `=`/`+`/`-`/`@` with a tab. Regression test:
   `inductions/tests/test_security.py::ExportCsvFormulaInjection`. The other two
   hand-rolled CSV exports (`members/views/volunteer_export.py`,
   `diary/edit_views/reports.py`) still need the same guard — left for Chunk 8's
   `csv_response()` unification as originally scoped, not fixed here.
7. ~~**Stored XSS, `labs/views/floorplan.py`'s `floorplan()` view**~~ — **fixed.**
   Found 2026-09-08 while writing Chunk 10 coverage for the building map, not by
   either review sweep. Same root cause as R13/item 3: `notes_json`,
   `area_photos_json`, and `loft_items_json` were built with raw `json.dumps()`
   and rendered via `{{ ...|safe }}` into `floorplan.html`'s inline `<script>`
   block. `RoomNote.body` and `LoftItem.name`/`.description` are free text any
   logged-in volunteer can set. Switched all three to `daterange.safe_json()`.
   Regression tests: `labs/tests/test_floorplan.py::FloorplanPageTests::test_notes_json_is_script_safe`
   and `::test_loft_items_json_is_script_safe`.

### Real bugs, worth a fix when the relevant file is next touched (Chunk 8 or 11, not urgent enough to interrupt)

7. **`EventTag.delete()` (`diary/models/misc.py:166`) and `Role.delete()`
   (`diary/models/rota.py:134-143`) don't return Django's documented `(count, dict)`
   shape** from `Model.delete()` — they return `False` and `(0, {})` respectively.
   Generic code trusting the Django contract (anything that does
   `count, _ = obj.delete()`) will misbehave silently.
8. **`inductions/views.py:866-872`** — a `KeyError` from a malformed admin email
   template is caught, and the *raw, unformatted* template (literal `{placeholder}`
   still in it) is silently returned as if the test-send succeeded. An operator
   testing a broken template gets no signal that it's broken.
9. **`inductions/views.py:787-807` (`manage_mark_policy_updated`)** — the
   policy-version bump commits before `notify_policy_change()` runs. If the send
   fails, every volunteer is permanently marked "behind" and gets re-emailed on every
   retry, even after the first send actually went out.
10. **`toolkit/diary/models/site_config.py:867-874` (`_passes_level`)** — an
    unrecognised `PERMISSION_LEVEL_CHOICES` string (e.g. stale seed data predating a
    new tier) silently falls through to `user.is_superuser`. Privilege-escalation
    shaped, not just dead code — worth a fail-closed default instead.
11. **`labs/views/floorplan.py` / `labs/views/loft.py`: URLs built by
    string-replacing a sentinel (`/0/`, `/ROOM_ID/`) into a `reverse()`d path**,
    matched on both the Python side and inline JS in `floorplan.html` /
    `session_detail.html`. A URL converter change (e.g. `<int:room_id>` →
    `<uuid:room_id>`) breaks this with no error anywhere. Related to R8 (unnamed
    JSON contract) but specifically about URL construction, not payload shape.
12. **`members/views/_common.py:86-93`** — the one genuinely critical defensive
    check found in the whole sweep. It guards against the real, documented
    April-2026 `vols_admin_address` comma-join incident (see the memory
    `project_vols_admin_footgun_incident`), but has **no test**, only a prose
    comment. A future "simplification" pass (Chunk 8 or 11) could silently
    reintroduce a real production incident. Add a regression test before anything
    else touches this function.
13. **`_user_volunteer` duplicated verbatim** in `operations/views/maintenance.py:15`
    and `labs/views/_common.py:55` — already tracked in QUALITY_PASS.md's
    "Duplication no linter will catch" and Chunk 8's scope. MiniMax found the same
    pair independently; no new file, just confirmation it's worth doing.
14. ~~A pattern, not a single bug — missing ownership/role checks on shared-object
    modify/delete views~~ — **resolved, not a bug.** Decided 2026-09-08: intentional
    for all five files (`collectives.py`, `area_photos.py`, `loft.py`, `exchange.py`,
    `jobs.py`). See rubric rule R14 for the full reasoning. Left in this list, struck
    through, so a future pass doesn't re-discover and re-flag it as new.
15. **`area_photos.py:45`'s `# noqa: ARG001` is factually wrong** — the suppressed
    argument (`area_id`) is used in the function body one line below the decorator.
    Harmless (the noqa just does nothing), but a suppressed lint that never needed
    suppressing is worth a two-second fix whenever that file is next opened.

### Test-coverage gaps named precisely (feeds Chunk 10, not new scope)

10. **`labs/views/loft.py` and `labs/views/area_photos.py` have zero test
    coverage**, confirmed by grep — four JSON endpoints (create/update/
    photo-upload/photo-delete) entirely unverified. Sharpens the general
    labs-undertested finding in `docs/ARCHIVE/QUALITY_BASELINE_2026_09.md` to the specific gap.

---

## Unfixed findings, ranked (Quality Pass 2, 2026-09-08)

From the 44-file MiniMax M3 sweep over the pre-rewrite Cube-era code (see the
"Quality Pass 2" entry above). Same convention as the Pass 1 list: fixed items are
struck through and kept for the record so a future pass doesn't re-flag the same
shape as new.

### Fixed 2026-09-08, out of band (same incident class as an existing fixed bug)

1. ~~**`Volunteer.anonymise()`'s GDPR email-scrub wiped the whole audit row, not
   just the matching address** (`members/models.py`, `anonymise()`)~~ — **fixed.**
   `SentEmailLog.recipients` is comma-joined and a single row can name several
   addresses (a direct email cc'ing more than one person; mailout batches are
   summarised separately and don't hit this path). The original code matched rows
   with `recipients__icontains=original_email` and then `.update()`d the *entire*
   field to a placeholder — anonymising one volunteer destroyed every other
   recipient's address on any row they happened to share. Same root cause as the
   documented `vols_admin_address` comma-join incident (see
   `feedback_vols_admin_footgun_incident`, R14's neighbour in spirit): a
   comma-joined field treated as if substring-matching it were safe. Fixed by
   iterating matching rows and replacing only the one address that equals
   `original_email` (case-insensitive, exact match on the split/stripped
   address), leaving every other recipient on the row untouched. Regression test:
   `members/tests/test_volunteers.py::TestAnonymiseVolunteer::test_anonymise_scrubs_only_own_address_from_shared_log_row`.

### Needs operational verification before treating as urgent

2. **`mailer/mailerd.py:53-57` (`poll_for_pending`) claims no more than one
   `mailerd` process ever runs, but nothing enforces it** — no
   `select_for_update()` or atomic claim on the pending-job row. Two instances
   running concurrently (a manual debug run during a deploy, a supervisor
   misconfiguration) would both pick up the same job and both send the full
   recipient list — a mass duplicate-send, not a cosmetic bug. **Before treating
   as urgent:** confirm the deployment topology genuinely guarantees single-
   instance (check `containerconfig/tk_run.sh` and the process supervisor config
   for anything that could start a second `mailerd`). If that guarantee holds
   operationally, this drops to defence-in-depth — worth an atomic claim next
   time the file is touched, not an interrupt-everything fix.
3. **`diary/templatetags/repeat.py`'s `{% capture %}`/`{% retrieve %}` tags store
   per-render state on the compiled template Node instance** (`CaptureNode.render`,
   lines 9/11; `CaptureRetrieverNode`, line 47) rather than on the per-request
   `Context`. Django compiles a template's Node tree once and reuses the same
   instances across every render, so under a threaded WSGI worker two concurrent
   requests hitting the same compiled template could interleave — one user's
   captured content leaking into another's response. **Before treating as a live
   bug:** (a) grep templates for `{% capture` / `{% retrieve` — if nothing calls
   these tags, there's no bug to fix, just dead code to consider removing; (b)
   check whether gunicorn actually runs multi-threaded (`GUNICORN_RELOAD=1` in
   `docker-compose.yml` doesn't establish this either way).

### Real bugs, worth a fix when the relevant file is next touched

4. **`toolkit_auth/decorators.py:24,39` — `write_required`/`read_required`
   redirect an authenticated-but-unauthorised user back to the login page**, which
   they can already reach. Logging back in doesn't grant the missing permission,
   so the user loops: login → still lacking the permission → redirected to login
   again. The `_strict` sibling decorators correctly `raise PermissionDenied`
   (403) instead. Confirmed by reading both decorator pairs side by side.
5. **`members/models.py`'s `Member.save()`/`_generate_membership_number()`
   has a two-save collision-avoidance loop with no unique constraint backing
   it** (~lines 155-189) — a new `Member` briefly exists with `number="?"`, then
   the loop counts existing rows to pick a free number. Concurrent creates can
   race past the count check and produce duplicate membership numbers. Needs a
   quick check of the actual DB schema/migration to confirm `number` really has
   no `unique=True`/unique index before scheduling a fix.
6. **`toolkit_auth/management/commands/configure_toolkit_users.py:74` — the
   `read` permission is created with the `write` permission's name**
   (copy-paste from the block two lines above). Because `Permission`'s real
   uniqueness is `(content_type, codename)`, not `name`, `get_or_create` never
   self-heals this — every environment ever seeded from this command shows the
   wrong label in Django admin permanently. Cosmetic but permanent; one-line fix
   whenever this file is next opened.
7. **`toolkit_auth/password_emails.py` (~46-51) — the reset email always rounds
   the timeout down to whole days, in both directions.**
   `PASSWORD_RESET_TIMEOUT // 86400` floors a 12-hour timeout to "0 days"
   (displayed as "1 day" by a subsequent `max(1, ...)`) and a 25-hour timeout
   also floors to "1 day" — both wrong, and both in the direction of overstating
   how long the link stays valid. Minor, but worth fixing alongside any other
   change to that email.
8. **`util/management/commands/purge_stale_volunteers.py` (~125-131) — no
   `transaction.atomic()` around a destructive, irreversible bulk-anonymisation
   loop.** A mid-loop failure leaves some volunteers anonymised and others not,
   with only a partial-success count reported. Wrap it before this command's next
   scheduled run is relied on for a real purge.
9. **`diary/validators.py` (`_get_extra_allowed_domains`, ~26-34) — built-in
   allowed domains are lowercased, admin-entered ones via `SiteConfiguration`
   aren't.** An admin who types `MyCloud.org` gets silently rejected by the
   validator meant to accept it. Confirmed by comparing the two code paths.
10. **`members/forms.py` (`GroupTrainingForm.clean()`, ~347-353) doesn't return
    `cleaned_data`.** Calls `super().clean()`, discards the result instead of
    `return self.cleaned_data`. Tolerated by modern Django's `if cleaned_data is
    not None` guards, but wrong by convention and will break the moment anything
    reads this form's `clean()` return value directly.
11. **`mailer/models.py:74` (`do_sending`'s `progress_pct` calc) can report
    101%.** `int((100.0 * sent) / total) + 1 if total else 100` adds an
    unconditional `+1`, so the final batch (`sent == total`) evaluates to 101.
    Normally masked by `do_complete` overwriting it with a hardcoded 100, but any
    job that dies before `do_complete` runs (worker crash, unhandled exception —
    see finding 13) leaves 101% on screen. One-line fix: drop the `+1`, or cap
    with `min(100, ...)`.
12. **`mailer/sender.py` (~113, ~204) interpolates `recipient.mailout_key`
    into the unsubscribe/edit URL with no None/empty check.** A member with a
    missing or blank key (legacy data, a creation-time race) gets a link like
    `?k=None` or `?k=`, which the receiving view will reject — that recipient
    silently loses their unsubscribe/edit path on every mailout. GDPR-adjacent:
    fix by refusing to mail recipients without a key, or guarding the
    interpolation.
13. **`mailer/mailerd.py`'s `run()` main loop has no exception handling around
    `run_job(job)`.** Any exception during a send — SMTP timeout, DNS failure, a
    programming error in the recipient queryset — propagates out of the loop and
    kills the whole daemon. `clean_up()` only recovers the stuck job on the
    *next* process restart, so a single transient SMTP hiccup can take the whole
    mailer offline until someone notices and restarts it. Wrap the `run_job`
    call in a `try/except` that logs and continues.
14. **`mailer/views.py`'s `jobs_list` and `jobs_table` disagree on default job
    visibility.** `jobs_list` defaults `show_completed=False` but
    `show_failed=True` — failed jobs are visible by default, completed ones
    aren't. `jobs_table` (used for the polling refresh) treats an absent query
    param as `False` for *both* flags. A user polling the table sees a
    different job set than the one they loaded the page with, with no state
    change on their part.
15. **`diary/mailout_views.py:134` — the POST-invalid branch of `mailout` drops
    context the GET branch provides.** The GET path renders via
    `_render_mailout_form`, which includes `days_ahead`/`copy_days_ahead` in the
    context; the POST-invalid branch calls `render(request, "form_mailout.html",
    {"form": form})` directly, omitting both. If the template reads either
    value (display, or a hidden field round-tripping it into the next POST), a
    failed-validation resubmit renders with that data missing. Fix by routing
    the invalid branch through `_render_mailout_form` too.
16. **`members/forms.py`'s `VolunteerForm.clean_collectives` (~210-219) re-adds
    deactivated invite-only collectives.** It preserves a volunteer's existing
    invite-only collective memberships by iterating
    `self.instance.collectives.filter(invite_only=True)` with no `active=True`
    filter, while the *new*-selection path two lines earlier (line ~197) does
    filter on `active=True`. A collective deactivated after a volunteer joined
    it gets silently re-attached to them on every subsequent profile save.
17. **`members/forms.py`'s `TrainingRecordForm.__init__` (~306-309) narrows
    `training_type`'s choices to whatever `general_training_enabled` currently
    allows.** A volunteer with an existing record of the now-disabled type
    can't have that record edited through this form — the field's choices no
    longer include their current value, so re-saving would either reject the
    form or silently clobber the type. Same shape as the already-documented
    `VolunteerForm.status` choice-filter issue in the same file.
18. **`members/models.py`'s `Volunteer.save()` portrait cleanup calls
    `os.unlink(self.__original_portrait)` directly (~365-375) instead of
    `default_storage.delete(name)`.** Works today because storage is local
    filesystem; breaks silently (or raises an uncaught error `except OSError`
    won't match) the moment storage moves to S3/GCS. Low urgency while storage
    stays local, but the fix is a one-line swap to the storage API whenever this
    method is next touched.
19. **`members/models.py`'s `Volunteer.save()` toggles `user.is_active` in a
    separate write from the volunteer save itself (~378-400), not inside
    `transaction.atomic()`.** A crash between the two writes can leave a
    suspended volunteer's login still active, or vice versa.

### Needs caller verification (do not act on without checking first)

- **`members/forms.py`'s `NewMemberForm` exposes `is_member` as an editable
  field** — a real privilege-escalation shape *only if* an unauthenticated
  signup flow instantiates this form. Check `members/views/` for who actually
  uses `NewMemberForm` before treating this as live.
- **`diary/public_views.py`'s `view_event`** falls through to "the first event
  with `legacy_id=None`" when both `event_id` and `legacy_id` are falsy — a real
  bug only if the URLconf can ever route here without supplying one of the two.
  Check the URLconf before scheduling a fix.

---

## What this rubric does not cover

Chunk 9 (inline JS/CSS extraction) and Chunk 7 (feature-scope decision) are
structural, not code-quality questions this rubric can check — see their own
sections in QUALITY_PASS.md.
