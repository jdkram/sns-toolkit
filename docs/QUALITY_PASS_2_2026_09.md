---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Sonnet 5"]
status: "#ai-input"
---

# Quality Pass 2: the pre-rewrite Cube code (planned, not yet run)

**Status:** scoped 2026-09-08, not started. Written up after CI (added by the first quality
pass) failed on its very first real run — not on new code, but on `mailout_views.py`, a file
dating to Ben Motz's original Cube Microplex codebase that no review pass had ever opened. See
"Why this exists" below.

## Why this exists

[`docs/ARCHIVE/QUALITY_PASS_2026_09.md`](ARCHIVE/QUALITY_PASS_2026_09.md) put ruff/black/CI
under the whole repo and ran two AI review sweeps (MiniMax M3, then Kimi K2 Thinking) — but
those sweeps were **scoped to the apps and modules this rewrite actually reworked or extended**:
`labs/`, `inductions/`, `audit/`, `operations/`, `diary/edit_views/`, `diary/forms.py`,
`diary/models/`, `members/views/`, plus 23 hand-picked files chosen by risk pattern (redirects,
file uploads, raw `innerHTML`, unauthenticated endpoints) for the security sweep. That was a
reasonable way to spend a fixed budget, but it means large parts of the pre-2026 Cube codebase —
code this project inherited rather than wrote — never got a judgement-level look, only the
mechanical ruff/black pass.

The gap surfaced concretely on 2026-09-08: `toolkit/diary/mailout_views.py`'s test suite
(`test_mailout_view.py`) turned out to rely on a brittle, environment-sensitive
`assertContains(html=True)` comparison against a ~50-line literal HTML blob — the kind of thing
a general-quality review flags immediately (MiniMax's Chunk 5 prompt explicitly asks about
"defensive branches for impossible states" and similar smells; a fragile test assertion is
adjacent to that class of finding). `mailout_views.py` traces back to
`Factor out mailout views into a separate file` — pre-rewrite, Ben-era code — and sits outside
every chunk's scope list. Fixed in isolation (`fix(tests): stop the mailout HTML test asserting
a whole-page HTML blob`), but it's a single data point, not a guarantee the rest of this surface
is clean.

## Scope: 45 files, ~9,600 lines

Everything in `toolkit/` **not** covered by the first pass's chunks (Chunk 5's eight
dirs/files, Chunk 6's 23 hand-picked files, or newly-created-by-the-pass modules like
`util/csv_export.py`/`ics.py`/`volunteers.py`), excluding `migrations/`, `apps.py` boilerplate,
test files, and empty `__init__.py`s. Grouped by rough risk tier:

**Tier 1 — auth, permissions, money-adjacent (review first):**
- `toolkit/toolkit_auth/backends.py`, `decorators.py`, `forms.py`, `password_emails.py`
- `toolkit/toolkit_auth/management/commands/configure_toolkit_users.py`
- `toolkit/members/forms.py`, `toolkit/members/models.py`
- `toolkit/mailer/sender.py`, `mailerd.py`, `models.py`, `views.py`, `forms.py`
- `toolkit/diary/mailout_views.py` (partially covered by today's fix — the view logic itself,
  not just its test, hasn't had a review pass)

**Tier 2 — user-facing views and data handling:**
- `toolkit/diary/public_views.py`, `calendar_links.py`, `clash.py`, `feeds.py`,
  `form_widgets.py`, `omdb.py`, `poster.py`, `signals.py`, `validators.py`, `edit_prefs.py`
- `toolkit/diary/daterange.py`
- `toolkit/index/models.py`, `views.py`
- `toolkit/util/image.py`, `email_backend.py`, `context_processors.py`

**Tier 3 — management commands and templatetags (lower traffic, still unreviewed):**
- `toolkit/util/management/commands/seed_dev_data.py` (513 lines — already excluded from the
  complexity gate outright; worth a look on its own terms even if it stays excluded)
- `auto_dormancy.py`, `check_media_dirs.py`, `purge_stale_volunteers.py`,
  `send_volunteer_digest.py`, `seed_data/fetch_trailers.py`
- `toolkit/diary/templatetags/*.py` (7 files), `toolkit/util/templatetags/*.py` (2 files)

Deliberately excluded, same reasoning as the first pass: `settings_*.py` /
`docker_settings_*.py` / `urls*.py` (declarative config, low judgement-review value) and
`devserver_settings.py`.

## Method (reuse what Chunk 5/6 already learned)

Per the archived pass's own conclusion: **default to MiniMax M3** (`openrouter/minimax/minimax-m3` via
`opencode run`), not Kimi K2 Thinking, for the general-quality sweep — cheaper and better noise
discipline. Reuse Chunk 6's Kimi sweep only for a second, security-focused opinion on Tier 1
(auth/mailer) specifically, the same way it was used as a second opinion on redirects/uploads
last time.

Known gotchas from the archived pass, to avoid re-discovering:
- `opencode run` reads stdin — a `while read` loop over a file list will have its own input
  silently consumed by `opencode`. Load paths into a `mapfile` array first, iterate that, and
  redirect `opencode`'s stdin from `/dev/null`.
- Some runs go agentic (use `bash`/`read`/`grep` beyond the pasted file) and silently end with
  no report after exhausting their tool budget. Add an explicit "you must conclude with a
  written report before ending the turn" instruction to the prompt up front.
- `opencode run` silently rejects reads outside its working directory.
- The `:free` MiniMax variant errors on every attempt on this OpenRouter account (likely a
  zero-data-retention account setting) — use the paid model directly.

## Cost estimate

The archived pass's Chunk 5 (68 files, MiniMax M3) cost **$1.30** total. This scope is smaller
(45 files, ~9,600 lines vs. Chunk 5's larger set) — expect **$0.80–$1.10** for the MiniMax pass
across all three tiers, plus a small Kimi top-up (Chunk 6 cost $0.28 for 23 files) if Tier 1
gets the second security-focused opinion — call it **$1.00–$1.40** all in. Negligible in the
context of the $1.69 the whole first pass cost.

## What to do with findings

Same as the first pass: write findings into `docs/QUALITY_RUBRIC.md` (extending the existing
rubric, not starting a new one) rather than fixing inline as they arrive, then triage — real
bugs and security findings fixed with regression tests, verbosity/style findings assessed
against the rubric's existing "not rubric material" precedents before acting. Anything found
in Tier 1 (auth/money-adjacent) should be treated as higher priority than an equivalent finding
elsewhere, given what's at stake if it's wrong.
