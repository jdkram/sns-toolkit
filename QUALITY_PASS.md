---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Opus 5", "Claude Sonnet 5"]
status: "#ai-input"
---

# Quality Pass Plan

> **Status:** in progress on branch `chore/quality-pass-2026-09`, branched from
> `sns_2026_overhaul` at `ccbb3d6a`.
> **Last updated:** 2026-09-08
> **Resume by:** reading this file top-to-bottom, then checking
> `git log --oneline chore/quality-pass-2026-09` to see which chunks actually shipped.

### State at the end of the last session (2026-09-08)

| | |
|---|---|
| Branch | `chore/quality-pass-2026-09`, working tree clean |
| Chunks done | 0, 1, 2, 3, 4, 5, 6, 7 (keep all seven `labs` tools) |
| Next chunk | **10 in progress**: `labs` portion done (all four coverage targets at 100%, toggleability follow-up, edge-case follow-up), destructive paths (`bulk_anonymise_volunteers`/`bulk_delete_never_onboarded`) now done too; still to go: `toolkit_auth/backends.py` + permission decorators, `volunteer_edit.py`'s gaps, status-code-only tests — then 8, 9, 11, 12 |
| Tests | 1,317 passing (was 1,129 at session start — +7 security-fix regressions, +29 building-map, +34 shopping, +19 lost & found, +25 exchange, +21 feature-flag-gate, +18 edge-case-user, +33 destructive-path tests) |
| Ruff | 0 findings |
| Black | clean at 79 |
| Coverage | 81.5% overall (21,788 statements) — see `docs/QUALITY_BASELINE.md`, not yet re-run since the security fixes |
| CI | `.github/workflows/ci.yml` + `.pre-commit-config.yaml` in place, not yet exercised by a real PR |

**All six previously-unfixed security findings are now fixed** (out of band from the
Chunk 7-11 cadence, as flagged): the stored-XSS vector in
`toolkit/inductions/templates/inductions/manage/session_detail.html` (Chunk 5); the open
redirect via unvalidated `HTTP_REFERER` in `toolkit/labs/views/bulletins.py` (Chunk 6); the
three further XSS variants from the Kimi sweep (`diary/templates/form_showing.html`,
`members/templates/volunteer_bulk_record.html`,
`diary/templates/edit_event_template_detail.html` — rubric rule R13); and the CSV
formula-injection gap in `inductions/views.py` (`manage_export_csv`). All six carry regression
tests now (1,136 total, up from 1,129) except the session_detail.html fix, which is a pure
client-side JS sink with no Django-test-client coverage — see `docs/QUALITY_RUBRIC.md`'s
"Unfixed findings" section (now struck through) for the fix detail and test names per item.
**Still needs a manual browser check** of the session_detail.html induction signup flow, per
Chunk 9's existing note that JS-sink fixes aren't covered by the test suite. The
`csv_response()` unification in Chunk 8 should still add the same formula-injection guard to
`members/views/volunteer_export.py` and `diary/edit_views/reports.py` — not done here, out of
scope for an out-of-band security fix.

**All seven `labs` tools are now individually toggleable via `SiteConfiguration`,** not just
Exchange (`community_exchange_enabled` already existed — the Chunk 7 decision doc's claim that
"nothing here is feature-flagged" was wrong on that point, now corrected there). Added
`collectives_enabled`, `jobs_board_enabled`, `building_map_enabled`, `shopping_list_enabled`,
`lost_and_found_enabled`, `donations_enabled` (migration `0044`), each defaulting to `True` so
nothing changes for existing deployments. A shared `_feature_enabled_or_404(flag_name)`
decorator in `toolkit/labs/views/_common.py` — generalised from `exchange.py`'s original inline
`if not cfg.community_exchange_enabled: raise Http404` duplicated across 9 views, which now
uses the decorator too — gates every entry point per tool, and `fragment_navmenu.html` hides
the corresponding nav link when a flag is off. Fields grouped into
`SITE_CONFIG_FIELD_GROUPS` per the existing convention; `docs/tasks/` untouched since this is
infrastructure, not a new feature spec.

**A real test-isolation bug found and fixed while adding these:** `SiteConfiguration`'s
`get_site_config()` caches the config object for 300s, and `.save()` clears that cache — but
Django's `TestCase` wraps each test in a transaction it rolls back afterward, and the *cache*
is not part of that transaction. A test that flips a flag and saves populates the cache with
the flipped value *during* its own (later-rolled-back) transaction; that cached object survives
the rollback and leaks into whatever test runs next, since Python's `unittest` loads test
classes in alphabetical order by name, not file order. `toolkit/diary/tests/common.py` already
carries the fix (`cache.delete(SiteConfiguration._CACHE_KEY)` in `setUp`) — `toolkit/labs/tests/common.py`
never got it, so writing the first `labs` test that toggled a flag without also explicitly
resetting it immediately surfaced the gap (`CollectivesGateTests` broke every
`CollectivesPublicTests` test that ran after it alphabetically). Fixed by adding the same guard
to `LabsTestsMixin.setUp()`. Worth knowing before writing any future test that mutates
`SiteConfiguration` in any app that doesn't already have this guard in its test mixin.

**Resolved, no longer open:** the R14 decision (five views with no ownership check on shared
objects — `collectives.py`, `area_photos.py`, `loft.py`, `exchange.py`, `jobs.py`) was decided
by Jonny 2026-09-08: intentional, not a bug, for all five. Reasoning and the rule are in
`docs/QUALITY_RUBRIC.md`'s R14. No code changed as a result — the decision was "leave as is,"
not "add a check." Noted here only so a future pass doesn't re-flag it as new.

**Model choice for future sweeps:** default to MiniMax M3 for this project's opencode-based
review passes, not Kimi. Jonny's call after seeing both: MiniMax's per-file cost was lower and
its output more consistently reliable (no severity-rating volatility, no agentic-tool-budget
failures) than Kimi K2 Thinking's. Kimi found real things a general-quality pass wouldn't have
(see the Chunk 6 follow-up entry below), so a security-focused second opinion from a different
model is still worth considering occasionally — just not as the default.

Commits so far, newest first:

```
8bf26460  test(labs): add "strange user" edge-case coverage, fix a real login-signal crash
16f7527b  feat(labs): make every labs mini-tool toggleable via SiteConfiguration
7eca2501  test(quality): close the exchange.py coverage gap, all four labs targets done
cd068462  test(quality): close the lost_found.py coverage gap (Chunk 10, third target)
70fb63ae  test(quality): close the shopping.py coverage gap (Chunk 10, second target)
238dd150  feat(quality): record the Chunk 7 decision, close the building-map coverage gap
71c68490  docs(quality): write the Chunk 7 labs feature-scope decision document
393b08d6  docs(quality): fold the session_detail.html XSS fix into Chunk 9's browser-check note
239af162  fix(security): patch the 6 findings flagged by the Chunk 5/6 review sweeps
99946c72  docs(quality): update resume commit log with the R14 resolution commit
a835716d  docs(quality): resolve R14 (shared-resource access stays open), set MiniMax as default model
8810a7fd  docs(quality): fix placeholder commit hash in the resume log
4fe4c50a  docs(quality): synthesise Chunk 6 rubric, run Kimi security sweep, flag 4 new XSS/CSVi findings
08a87fb8  docs(quality): record the Chunk 5 MiniMax sweep and an XSS finding
bd202cd6  docs(quality): write the Chunk 4 coverage/complexity baseline
19e65fc3  docs(quality): fix dead paths and document the tooling (Chunk 3)
2ff7f79d  docs(quality): record Chunk 2 results in the pass tracker
f46c977d  ci(quality): add pre-commit and GitHub Actions gates
b980935a  chore(quality): triage the 110 remaining ruff findings
be24b41e  docs(quality): make the pass resumable by a fresh session
94786738  docs(quality): record Chunk 1 results in the pass tracker
716002bd  chore(quality): black reformat at the now-pinned 79 columns
c336f5df  chore(quality): remove 892 unused imports and variables
e5822a1b  chore(quality): add ruff/black config and the quality-pass tracker
ccbb3d6a  fix(digest): ... (last commit on sns_2026_overhaul, the branch point)
```

## Why this pass exists

The concern that prompted it: the branch is ~49k lines of Python and ~30k lines of templates
across ~2,180 commits, most of it AI-assisted, and nobody has measured whether the quality
holds or whether a human could maintain it unaided.

A maintainability pass already ran in June 2026 ([MAINTAINABILITY_PASS.md](MAINTAINABILITY_PASS.md),
11 chunks, all merged). It was Claude reviewing Claude, and its own refactor is the best
argument for doing this differently. Splitting `edit_views.py` and `volunteer_views.py` into
packages, it reached for two shortcuts:

- `diary/edit_views/` got a **copy-pasted 60-line import header** in every module. Seven of
  twelve still have byte-identical first-60-lines. `reports.py` is 163 lines, 60 of them
  imports it does not use.
- `members/views/` got a **`_common.py` re-export hub**, pulled in by all eight modules via
  `from ._common import *`. 542 symbol references with no traceable origin — you cannot tell
  what `Volunteer` or `timezone` is in those files without opening another one.

Both went unnoticed for two and a half months, because this repo has no linter. No model would
reliably have caught them by reading. `ruff` catches both in seconds.

So this pass has three layers, and the order matters:

| Layer | Does | Cost |
|---|---|---|
| **Deterministic** — ruff, black, coverage, CI | Mechanical correctness. Runs on every commit, forever, cannot regress. | Free |
| **MiniMax M3 via OpenCode** | Judgement in Claude's blind spot: verbosity, defensive branches for impossible states, premature abstraction, config knobs nothing sets. | ~$0.70 |
| **Claude Opus** | Sequencing, architecture, turning findings into a written rubric, executing the uplift. | Session time |

Deterministic first, so the paid review is not spent reading dead import headers and reporting
on noise.

---

## Working across sessions

This is roughly eight sessions of work, deliberately broken so no single session has to hold
it all.

**Every session starts:**

1. Read this file top to bottom.
2. `git log --oneline chore/quality-pass-2026-09` — what shipped, versus what this file claims.
3. `git status` — pick up anything uncommitted.
4. Run the verification block at the foot of this file. Confirm green *before* touching
   anything.
5. Do the next `NOT STARTED` chunk. Update its status in the same commit as the work.

**Rules that make this safe to interrupt:**

- One chunk per commit, minimum. Never leave a chunk half-done across a session boundary. If a
  chunk will not fit in the remaining budget, stop *before* starting it.
- Every commit leaves the branch green.
- The findings below are **measured, not estimated**. Read them rather than spending budget
  re-deriving them. Re-measure only at Chunk 4 (baseline) and Chunk 12 (confirmation).
- If a chunk's scope turns out to be wrong once opened, write what you learned into this file
  before stopping. That note is worth more than partial code.

**Session sizing** (a hint, not a promise):

| Session | Chunks |
|---|---|
| 1 | 0–3 — config, mechanical fixes, CI, docs drift |
| 2 | 4–5 — coverage baseline, then the MiniMax sweep |
| 3 | 6 — rubric synthesis |
| 4 | 7 — feature-scope conversation (needs Jonny) |
| 5–7 | 8–11 — the uplift; Chunk 9 may want two sessions alone |
| 8 | 12 — re-measure and confirm |

---

## Gotchas for whoever picks this up

Each of these cost real time to discover. None is guessable from the code.

**Tests run only inside the container.** There is no local venv, and `mysqlclient` plus several
C extensions exist only in the image. Every verification command is
`docker compose exec -T toolkit /venv/bin/...`. The `-T` matters in a non-interactive shell.

**Never `.only()` on models with a custom `__init__`.** `EventTag`, `Event`, `Showing`,
`RotaEntry`, `Role`, `Member` and `Volunteer` cache field values in `__init__`. Deferring one
makes accessing it call `refresh_from_db`, which constructs a new instance, which calls
`__init__` again. Infinite recursion, one DB round-trip per frame. Use `.values()` and read the
results as dicts. This is in CLAUDE.md too, and it is easy to reintroduce during a refactor.

**Django template comments must be single-line.** A `{# ... #}` spanning multiple lines is not
stripped reliably and leaks into the rendered HTML. Relevant to Chunk 9, which touches four
large templates.

**`ruff --fix` is not universally safe.** Two categories of correct code look like dead code to
it: re-export shims (`members/views/__init__.py`, guarded in `pyproject.toml`) and side-effect
imports (`audit/apps.py:11`, which registers signal handlers). Check before running `--fix`
across new territory, not after.

**A user hook rewrites the phrase "critical" to "critical" on Write/Edit.** It fires on
those tools but not on `sed` or a heredoc via Bash. It exists to strip a tell of AI authorship,
which is fine for text the agent writes, but it will also silently rewrite *Jonny's* existing
prose in any file those tools touch. When making a surgical change to an existing doc, prefer
`sed`, and check `git diff` for edits you did not intend.

**`SiteConfiguration`'s cache outlives a rolled-back test transaction.** `get_site_config()`
caches for 300s; `.save()` clears that cache — but the cache isn't part of Django `TestCase`'s
per-test transaction, so a test that flips a flag and saves populates the cache *during* its
own transaction, and that cached value survives the rollback into whatever test runs next
(`unittest` loads test classes alphabetically by name, not file order, so "next" can be a
world away in the file). `toolkit/diary/tests/common.py` already guards against this
(`cache.delete(SiteConfiguration._CACHE_KEY)` in `setUp`); any other app's test mixin that
lets a test mutate `SiteConfiguration` needs the same guard, or a flag-toggling test will
silently break unrelated tests elsewhere in the same run. Found the hard way adding the labs
feature-flags (2026-09-08) — `LabsTestsMixin` didn't have it either, until then.

**`opencode run` silently rejects reads outside its working directory** (Chunk 5). It prints
the rejection to stderr only; stdout and the JSON output show an empty response with no error.
Always run it with the repo as the working directory.

---

## Measured findings (2026-09-07)

### Tooling: nothing was enforced

No CI, no `pyproject.toml`, `tox.ini`, `Makefile` or pre-commit config. Every tool setting
lived in prose in `docs/ONBOARDING.md`. `black` was pinned in `requirements/dev.txt` and run by
hand at `--line-length 79` — a number recorded nowhere machine-readable, so a bare `black` run
used the default 88 and reformatted the repo. No linter, no type checker, no coverage tooling.
The one git hook (`.git/hooks/pre-push`) is a privacy guard, not a quality gate.

Neither width was actually clean when measured: `black -l 79 --check` wanted to reformat 135
files, `-l 88` wanted 171. 79 is both closer and the documented intent, so that is what
`pyproject.toml` now pins.

### Ruff, under the project's own config

| Rule | Count | Notes |
|---|---|---|
| `F401` unused import | **885** | auto-fixable |
| `ARG001/002/005` unused argument | 71 | needs judgement |
| `C901` complex structure | 19 | worst is `seed_dev_data.handle` at **101** |
| `F841` unused variable | 9 | auto-fixable |
| `E741` ambiguous name | 5 | |
| `E402`, `F811`, `W292` | 9 | |
| **Total** | **998** | 890 auto-fixable |

Unused imports cluster exactly where June's split ran: `diary/edit_views/_common.py` (56),
`film.py` (51), `reports.py` (48), `misc.py` (48), `showings.py` (43), `labs/views/_common.py` (42).

**`E501` is deliberately disabled.** Not laziness — measured. After a clean `black -l 79` pass,
1,375 lines still exceed 79, because black cannot split long string literals or comments
(`help_text`, log messages, seed data). A permanently red rule is worse than no rule.

**Two traps found while configuring, both now guarded in `pyproject.toml`:**

- `members/views/__init__.py` is a re-export shim with **no `__all__`** (its two sibling
  packages both declare one). Ruff flags all 34 re-exports as `F401`; a naive `ruff --fix`
  would delete them and break the URLconf. `per-file-ignores` covers `__init__.py` everywhere.
- The `from ._common import *` pattern in `members/views/` is **quarantined, not blessed** —
  ignored so the CI gate can go up now, scheduled for Chunk 11. Delete that ignore when it lands.

### Template debt: the largest single item, untouched by any previous pass

**7,535 lines of JavaScript live inline inside Django templates**, where no linter, test, or
browser cache can reach them.

| Template | Total | Inline `<script>` | Inline `<style>` | Actual markup |
|---|---|---|---|---|
| `diary/templates/edit_rota.html` | 2,161 | 1,039 | 894 | ~230 |
| `diary/templates/form_event.html` | 1,832 | 1,306 | 42 | ~480 |
| `labs/templates/labs/floorplan.html` | 1,222 | 721 | — | ~500 |
| `inductions/.../session_detail.html` | 957 | 649 | — | ~300 |

Upstream's `edit_rota.html` was 126 lines; `form_event.html` was 67. There is already a
precedent for doing this properly — `toolkit/diary/static/diary/js/edit_event.js` and
`toolkit/static_common/js/*.js` — so extraction follows an existing pattern.

### Test coverage: 1,129 tests, unevenly placed, unmeasurable

- **`toolkit/toolkit_auth/` has zero tests.** It holds the email-or-username auth backend and
  the `feature_required` / `write_required` / `read_required` decorators every app depends on.
  `toolkit/content/` (Wagtail models) also has none.
- The destructive bulk operations are untested: `bulk_anonymise_volunteers` and
  `bulk_delete_never_onboarded` in `members/views/volunteer_pool_admin.py`.
- `labs/views/shopping.py` (523 lines) has 3 of 13 endpoints tested; `loft.py` and
  `area_photos.py` have none.
- **102 tests assert nothing but a status code.** `labs/tests/test_bulletins.py:105` posts an
  empty title and asserts 200 — a view that silently created a titleless record would pass.
  `members/tests/test_members.py:331` patches the model the view queries, then asserts against
  the mock's own call log.
- No `coverage` package was installed anywhere, so none of this was measurable. Chunk 0 fixes
  that; Chunk 4 measures it.

### Duplication no linter will catch

- `_user_volunteer(user)` exists verbatim in `labs/views/_common.py:55` and
  `operations/views/maintenance.py:15`. Three app-local `_common.py` modules and no shared
  `toolkit/util` home means cross-app helpers get copied instead of promoted.
- Hand-rolled CSV export built from scratch in three places: `members/views/volunteer_export.py:155`,
  `inductions/views.py:493`, `diary/edit_views/reports.py:92`.
- Two independent iCalendar generators: `diary/calendar_links.py`, `inductions/views.py:106`.
- `diary/tmdb.py` and `diary/omdb.py` implement matching signatures with no shared protocol, so
  callers branch on which is configured.
- Single-vs-bulk view pairs duplicated in `volunteer_pool_admin.py`; three near-identical
  `shopping_buy*.html` templates with no `{% include %}`.

### Docs drift

20 doc-referenced paths do not exist. The ones that matter: `docs/ONBOARDING.md:298` and
`docs/SPEC.md:481` send a newcomer to `toolkit/members/volunteer_views.py`, which June's split
deleted. `ONBOARDING.md:280,282` link `diary/models.py` and `diary/edit_views.py`, both now
packages. The `operations` and `audit` apps appear zero times in the onboarding app tour.
`members/member_views.py` was left behind by the split — a half-finished refactor, and the
reason the docs are wrong.

---

## Chunks

### Chunk 0: Set up the pass — DONE 2026-09-07

- [x] Branch `chore/quality-pass-2026-09` off `sns_2026_overhaul` at `ccbb3d6a`
- [x] This file, seeded with the measured findings above
- [x] `pyproject.toml` — black and ruff config, pinning line-length 79
- [x] `ruff==0.16.6` + `coverage>=7.6,<8` added to `requirements/dev.txt`
- [x] Same plus `black` added to `requirements/docker.txt`, `docker.lock` recompiled
- [x] `docker compose up --build -d`; verified `ruff` 0.16.6, `black` 26.3.1, `coverage` 7.16.0 in the image, and that container-side ruff picks up `pyproject.toml` (998 findings, matching the host)

### Chunk 1: Mechanical fixes — DONE 2026-09-07

`ruff check --fix` for `F401`/`F841` only, then `black` as a **separate** commit — both
mechanical, but each a large enough diff that mixing them makes review impossible. Full
suite green after each.

- [x] `ruff --select F401,F841 --fix` — 892 fixed, 823 deletions across 48 files
      (`c336f5df`). `__init__.py` untouched; the per-file-ignore held.
- [x] `black` at the pinned 79 — 142 files (`716002bd`). Net +3,688 lines, because
      79 columns splits more call signatures than the previous mixed state did.
- Result: ruff findings **998 → 110**, none auto-fixable. Those need judgement and
  are Chunk 2's first job: 71 `ARG`, 19 `C901`, 8 `F841`, 5 `E741`, 4 `E402`, 3 `F401`.

### Chunk 2: The gates — DONE 2026-09-08

**Ruff findings, resolved not just silenced.** The pre-triage table below was worked
line-by-line, not blanket-ignored:

- `ARG001` on signal handlers and the three `@receiver`-decorated functions in
  `toolkit_auth/decorators.py` — per-file-ignores added for `*/signals.py` and that one file.
- `ARG002` on `handle(self, *args, **options)` — per-file-ignore for
  `*/management/commands/*.py`.
- The ~46 remaining `ARG` findings were read individually. All but 6 turned out to be
  framework-mandated signatures (Django views called positionally from urlconf, admin
  permission hooks, widget `render()`/`value_from_datadict()`, template tag registration,
  `Model.delete(*args, **kwargs)`, a `signal.signal()` handler, `BaseEmailBackend` mocks) —
  each got an inline `# noqa` naming the API that requires it, not a blanket ignore, so a
  genuinely dead argument on non-framework code still trips the gate. The 6 real exceptions:
  `labs/forms.py`'s `ExchangeItemForm.__init__(user=...)` is accepted-but-unused pending real
  filtering logic (noted, not fixed — out of scope here); `auto_dormancy.py`'s
  `lambda v: None` intentionally matches a sibling callback's shape; three `seed_dev_data.py`
  private-helper arguments (`volunteer_objects`, `anchor`, `vol_list`) are dead and deferred to
  Chunk 11's rewrite rather than hand-patched now.
- `C901`: `max-complexity` raised from 12 to 101 (the measured worst), with a comment
  explaining it's a ratchet, not a target, to be brought back down as Chunks 9 and 11 land.
- `E741` ambiguous `l`: all 5 renamed (`label_text`, `line`, `lang`, `lightness`).
- `E402`: `diary/edit_views/events.py` and `film.py` had a `._common` import stranded after a
  `logger = ...` line — moved up, no deliberate layering involved. The
  `docker_settings_starandshadow.py` and `seed_dev_data.py` noqa comments were sitting on the
  wrong physical line for a multi-line import (ruff anchors `noqa` to the line the name itself
  is on, not the closing paren) — moved. `members/tests/test_volunteers.py` had a stray
  mid-file import, moved to the top.
- `F401` in `audit/apps.py` and `seed_dev_data.py`: kept, noqa'd, comment explains why
  (side-effect import; availability probes).
- `F841` unused locals: `diary_overview.py`'s `local_now` and `rota.py`'s
  `yesterday_local_date` were confirmed dead (grepped for any later use) and deleted. Three
  test-file locals (`test_shopping.py`, `test_maintenance.py`, `seed_dev_data.py`'s `job`) were
  create()-for-side-effect only — dropped the assignment, kept the call. One,
  `test_edit_misc.py`'s `initial_pricing`, was genuinely unused scaffolding — deleted.
  **One was a real bug**, exactly the class QUALITY_PASS.md called out in advance:
  `test_programming_queue.py`'s `test_invalid_action_returns_error` computed a `response` and
  never asserted on it. Added `assertRedirects` against the actual redirect target (the Event
  Hub, not the queue — the view's "unknown action" branch returns before the `next` param is
  read, which the test now pins down instead of leaving implicit).

Ruff: 110 → 0. Black: clean. Tests: 1,129 passing (one assertion added, none broken).

**The gates themselves:** `.pre-commit-config.yaml` (ruff + black on staged files) and
`.github/workflows/ci.yml` (ruff, `black --check`, full Django test suite via SQLite, no DB
service container needed) are in place. Not yet exercised by a real push/PR — that happens
naturally once this branch's work goes up.

*After this chunk, June's regression could not have happened. Everything later is optional in a
way this is not.*

### Chunk 3: Docs drift — DONE 2026-09-08

Re-measured before fixing anything: of the 20 counted in the original finding, only ~9 were
real drift (a doc-referenced path a newcomer would actually hit and find broken). The rest live
in `docs/tasks/*.md`, which is explicitly a feature-spec / not-yet-built index (see each file's
own header), so a reference to a module that doesn't exist yet is often the point, not a bug.

**Fixed — real drift, all in `ONBOARDING.md` and `SPEC.md`:**

- `ONBOARDING.md`: `diary/models.py` → `diary/models/`, `diary/edit_views.py` →
  `diary/edit_views/`, `members/volunteer_views.py` → `members/views/` (all three became
  packages in June's split; `members/member_views.py` is untouched because it's still real —
  checked it's imported live from `members/urls.py` and covered by
  `members/tests/test_members.py`, so it is not the dead weight it looked like from the name
  alone. It's a from-day-one Member-views module, distinct from the Volunteer-views package,
  that the June split simply never touched).
- `ONBOARDING.md`'s Go-Live checklist claimed a `settings_cube.py` that has never existed —
  Cube runs on `settings_common.py` directly (it holds the Cube `VENUE` dict and is the
  default); only Star and Shadow gets a venue-specific override file. Corrected the sentence
  rather than inventing the file.
- `SPEC.md §"Account auto-creation"`: five references to `members/volunteer_views.py` (deleted
  in June) → `members/views/volunteer_edit.py` (verified via grep — all four named functions,
  `edit_volunteer`, `_send_password_set_email`, `send_volunteer_password_reset`,
  `set_volunteer_password`, live in that one module). Dropped a stale `lines ~329–346` pin while
  there — line numbers rot faster than filenames and this one already had.
- Added `operations` and `audit` to `ONBOARDING.md`'s project-structure tree, app tour, and URL
  map — both are real, shipped apps (`MaintenanceTask`/`MaintenanceRecord` and
  `SentEmailLog`/`DeletionLog` respectively) that appeared zero times before this.
- Replaced `ONBOARDING.md`'s "Code formatting" section (black-only, hand-typed `--line-length
  79`) with "Linting, formatting, and coverage": ruff, black and coverage commands as they
  actually run now that `pyproject.toml` owns the settings, plus a paragraph on the pre-commit
  hook and CI workflow. Ran the new coverage commands for real in the container before writing
  them down — `coverage run --source=toolkit manage.py test ...` then `coverage report -m` both
  work as documented (82% overall, see Chunk 4).
- Mechanical, low-risk: bulk-replaced the backticked token `` `edit_views.py` `` →
  `` `edit_views/` `` across `docs/tasks/*.md` (8 occurrences, 4 files) — safe in every context
  because the package still holds that code, just split by file, so the swap can't misdirect
  regardless of whether the surrounding sentence describes a past bug or a future one. Also
  fixed one `diary/models.py` → `diary/models/event.py` reference in a not-yet-built spec
  (incidentally: `EventTermsRevision`, the model that spec proposes, already exists in that
  file — a CURRENT_WORK.md status question, out of scope here, flagging for whoever owns that
  tracker).

**Left alone, and why (so the next session doesn't re-churn this):**

- `docs/tasks/operations.md`, `volunteers.md`, `public-site.md`: references to
  `room_data.py`, `export_volunteer_shifts_enhanced_report.py` (a different repo,
  `~/code/sns-analysis`, correctly not part of this one), `content/views.py`, and
  `mailing_lists.html` are all paths a proposed feature would create — genuinely prospective,
  not broken.
- `docs/tasks/known-issues.md:432` documents Chosen's removal in the past tense ("✅ resolved
  ... deleted") — correct as written, nothing to fix.
- A handful of abbreviated mid-doc mentions (`edit_views/diary_overview.py`,
  `edit_views/rota.py`, `manage/settings.html` missing their app-directory prefix) resolve fine
  once you supply the obvious parent directory; not worth a mechanical pass that would touch
  dozens of lines for a purely cosmetic gain.
- `docs/REVIEW_2026_OVERHAUL.md` is gitignored (`.gitignore:64`) — a personal working document,
  not part of the published docs set, so out of scope regardless of what it references.

Verification: full test suite (1,129 passing), ruff (0), black (clean) all re-run after the doc
changes — doc-only, so unsurprising, but checked rather than assumed.

### Chunk 4: Baseline — DONE 2026-09-08

Wrote [`docs/QUALITY_BASELINE.md`](docs/QUALITY_BASELINE.md): per-app Python/template LOC,
statement coverage, and worst cyclomatic complexity, plus ruff/black status and the reused
(not re-measured) template-debt table from this file's Measured Findings section.

**How complexity was measured without adding a dependency:** `radon` isn't installed anywhere
in the project. Ran `ruff check --select C901 --config "lint.mccabe.max-complexity=1" toolkit`
as a one-off CLI override — this doesn't touch the committed `pyproject.toml` ratchet, it just
makes ruff report every function's complexity as a "violation" for that single invocation, which
is enough to extract a worst-per-app table.

**One real finding surfaced by doing this properly rather than trusting the aggregate percentage:**
`toolkit_auth` (61.6%) and `content` (91.8%) both have **zero dedicated test files** — confirmed
with `find ... -iname '*test*'` — despite non-trivial coverage numbers. Those numbers are
incidental: earned by other apps' tests calling through `feature_required` /
`panopticon_required` on their way to testing something else, not by anything that tests
`toolkit_auth` itself. `backends.py`'s `authenticate()` override sits at only 50% specifically
because nothing exercises its failure paths. This confirms and sharpens the "zero tests" finding
already in this file's Measured Findings section — it isn't that the code never runs under test,
it's that nothing asserts on *its own* behaviour. Recorded in `QUALITY_BASELINE.md` so Chunk 10
starts from this, not from re-discovering it.

Also worth knowing for later: `util`'s 17.5% coverage is a measurement artefact, not a hidden
gap — it's dominated by `seed_dev_data.py` (0% covered, complexity 101, dev-only) and three
other operator-tool management commands nothing in the test suite ever calls. Don't read that
percentage as "the utilities are untested"; most of the app's real coverage is fine.

### Chunk 5: MiniMax M3 broad sweep — DONE 2026-09-08

Scope came out to **68 files**, not the ~40 estimated when this chunk was scoped — the
apps/dirs named (`labs/`, `inductions/`, `audit/`, `operations/`, `diary/edit_views/`,
`diary/forms.py`, `diary/models/`, `members/views/`) plus four templates simply contain more
non-test modules than the earlier estimate assumed. Excluded from the 68: `apps.py` files (5,
all 7-11 lines of pure framework boilerplate with no logic to find verbosity or premature
abstraction in) and `toolkit/audit/tests.py` (a genuine test file despite the name, out of
scope per "non-test module").

**Mechanics, as actually run:**

- Ran from the repo root, one `opencode run --model openrouter/minimax/minimax-m3 --format json`
  invocation per file, via a driver script (not committed — lived in the session scratchpad).
- **A real gotcha, not in this file before now:** `opencode run` reads stdin. A first attempt
  looped with `while IFS= read -r path; do ... opencode run ...; done < "$FILES"` — `opencode`
  consumed the *loop's own* remaining input from the shared file descriptor, so the loop
  silently ended after the first file with no error. Fixed by loading paths into a bash array
  with `mapfile` first and iterating that instead (and redirecting `opencode`'s own stdin from
  `/dev/null` as a second line of defence). Cost one throwaway run of `labs/admin.py`
  ($0.0109) — recorded in the spend log below, harmless, and the fix is generic enough to be
  worth remembering for any future scripted-loop-over-opencode work, not just this pass.
- The `:free` MiniMax variant errored (`UnknownError`) on every attempt — plausibly because
  Jonny's OpenRouter account is configured for zero-data-retention providers only, and the
  free tier commonly trades retention for cost. Not investigated further; the paid model worked
  immediately and the cost difference was immaterial ($1.30 total across all 68 files).
- Total: **$1.2999**, avg $0.0191/file — under half the 2026-09-07 bake-off's $0.0487 average
  and well under the ~$0.65-for-40-files original estimate (68 files at the actual scope would
  have been ~$3.31 at the bake-off rate; came in at well under half that). Zero errors, zero
  empty outputs, across all 68.
- Raw output (one `.md` per file, extracted from the `--format json` event stream, plus an
  index with per-file cost) lives at `docs/QUALITY_PASS_RAW/chunk5_reviews/` —
  **gitignored, not committed**, but persisted on disk (not the session scratchpad, which is
  session-scoped and would not have survived to a Chunk 6 session). See
  `docs/QUALITY_PASS_RAW/chunk5_index.md` for the full path→cost table.

**A finding surfaced immediately rather than held for Chunk 6's synthesis:**
`toolkit/inductions/templates/inductions/manage/session_detail.html` renders several
signup-derived fields (`name`, `username`, `existing_email`, `existing_username`) into the DOM
via raw string-concatenated `.innerHTML` (lines ~433, 438, 480-490, 508) with no escaping.
Traced the data path: those fields originate from `InductionSignup.name`/`.email`, populated
from `SignupForm` (`toolkit/inductions/forms.py:13-14,95`) — plain `CharField`s with no
HTML-stripping, submitted via `toolkit/inductions/views.py:signup()`, a **public, unauthenticated
view** (anyone who can reach an open induction session's signup page). A signup submitted with
`name = <script>...</script>` (or an `onerror` payload) would execute in the browser of whoever
next opens the session's manage page to review signups/duplicates — a Panopticon or
Programmer-tier user, per the app's permission model. **Confirmed real, not fixed.** Flagged to
Jonny directly in the session that found it (2026-09-08); not urgent enough to rush a fix
immediately before a machine shutdown (this branch has no live users yet — see
`QUALITY_PASS.md`'s Chunk 7 note on `labs`, same "nothing deployed" status applies here), but
should not wait for the natural Chunk 6→8-11 cadence either. Whoever picks up the branch next
should treat this as its own small fix (escape on render, or switch to `textContent`/DOM
construction instead of string-built `innerHTML`), not batch it in with Chunk 9's inline-JS
extraction just because it's in the same file.

**One finding checked and downgraded:** the same sweep flagged `edit_rota.html:1145`
(`var myVolPk = "{{ current_volunteer_pk }}";`, no `|escapejs`) as an XSS surface. Traced it:
`current_volunteer_pk` is `str(volunteer.pk)` (`diary/edit_views/rota.py:160`) — always a
plain integer string, never attacker-controlled free text. Worth adding `|escapejs` anyway as
cheap defence-in-depth if that view is touched for another reason, but not a real vulnerability
and not worth an out-of-band fix the way the induction one is.

**Not doing:** the OpenCode Go subscription. Confirmed unnecessary — the 68-file run at $1.30
total is nowhere near where a flat monthly fee would pay for itself.

### Chunk 6: Synthesise a rubric — DONE 2026-09-08

Wrote [`docs/QUALITY_RUBRIC.md`](docs/QUALITY_RUBRIC.md) from all 68 MiniMax Chunk 5 reviews,
deduplicated against `docs/REVIEW_2026_OVERHAUL.md`'s still-open maintainability findings
(permission-table drift, `SiteConfiguration` triple-bookkeeping).

**11 checkable rules** (R1–R11), each with a grep-able check, not vague guidance: no
module-level `logger.setLevel`, catch specific exceptions not `Exception`, comments say why not
what, one source of truth for a vocabulary touched from 3+ places (the single largest recurring
theme, ~15 files), error messages instead of silent redirects on a failed POST, lazy `%s`
logging (and a PII check), `escape()` only in HTML context, name the JSON contract between a
view and its consuming template's JS, named constants for business-rule numbers, no wildcard
imports (confirms Chunk 11's scope, no new information), local imports need a stated reason. A
"not rubric material" section records what MiniMax raised and then correctly self-corrected on
(verbose admin-facing help text, defensive JSON parsing on endpoints reachable outside the
trusted client, single-caller helpers, cosmetic urls.py inconsistencies) so a future pass doesn't
re-litigate it.

**A second unfixed finding, same severity class as Chunk 5's XSS, needs the same out-of-band
treatment:** `labs/views/bulletins.py:199,213` feeds `request.META.get("HTTP_REFERER")` straight
into `redirect()` with no `url_has_allowed_host_and_scheme` check — the same open-redirect
vulnerability class as `diary/edit_views.py:2609`, which `REVIEW_2026_OVERHAUL.md` flagged and
which is already fixed. This second instance was missed by that review because it's in `labs`,
not `diary`. Low severity (authenticated volunteers only, same as the fixed one), but it's the
same one-line fix and doesn't need to wait for Chunk 8. Flagged to Jonny directly
(2026-09-08, same session as this chunk). Two independent instances of the same root cause,
found in separate reviews months apart, is a class rather than a one-off — added as rubric
rule R12: no `redirect()` call may take a value traced back to `request.POST`, `request.GET` or
`request.META` without `url_has_allowed_host_and_scheme`.

Also recorded in the rubric, ranked but not fixed here (synthesis only): two `Model.delete()`
contract violations (`EventTag`, `Role` — don't return Django's `(count, dict)` shape), a
silently-returned-unformatted email template on a `KeyError` in `inductions/views.py:866-872`, a
policy-version bump that commits before its notification email sends
(`inductions/views.py:787-807`), a privilege-escalation-shaped fallback in `site_config.py`'s
`_passes_level` (unrecognised permission string falls through to `is_superuser`), sentinel-string
URL construction in `floorplan.py`/`loft.py` with no test coverage on the JS side, and the one
genuinely critical defensive check the whole sweep found
(`members/views/_common.py:86-93`, guarding the real April-2026 `vols_admin_address` incident)
having no regression test. All feed Chunks 8, 10 or 11's existing scope rather than opening new
work.

This is the step that makes the money worth spending. The rubric is what lets Chunks 8–11 run
without re-paying for external review per file, and it is the artefact that outlives the pass.

### Chunk 6 follow-up: Kimi K2 Thinking security sweep — DONE 2026-09-08

A second sweep, run the same session, out of curiosity about how a different model/provider
compares to MiniMax and to get a security-focused (not just general-quality) second opinion on
the surface most likely to hide real vulnerabilities. **Not part of the original chunk plan** —
recorded here rather than renumbering everything.

**Scope:** 23 files, hand-picked (not a blind full-repo sweep) from four categories: views
calling `redirect()` with request-derived input (the R12 class), views handling
`request.FILES` uploads, templates using raw `innerHTML`, and unauthenticated/token-based entry
points. Model: `openrouter/moonshotai/kimi-k2-thinking` via `opencode run`. Cost: **$0.2772**
across all 23 (plus two retries at negligible extra cost — see the gotcha below), each ~$0.005–
$0.04 depending on file size.

**A new gotcha, same family as Chunk 5's:** 2 of 23 runs (`labs/views/lost_found.py`,
`members/views/volunteer_edit.py`) went agentic — used `bash`/`read`/`grep` to explore beyond
the pasted file content — and silently ended with no final report after exhausting their
tool-call budget. No error, just empty/truncated JSON output. Fixed both by re-running with an
explicit "you must conclude with a written report before ending the turn" instruction. Recorded
in `docs/QUALITY_RUBRIC.md` so a future Kimi-thinking sweep adds that instruction pre-emptively
rather than discovering the failure per-file.

**Findings:** four new confirmed vulnerabilities (three XSS variants sharing one root cause —
an escape filter mismatched to its actual sink, now rubric rule R13 — and one CSV
formula-injection gap), one systemic pattern needing Jonny's judgement rather than a blind fix
(missing ownership checks on shared-object modify/delete views, five files, rubric rule R14),
and one already-known finding re-confirmed with no new information. Full detail, all ranked, in
`docs/QUALITY_RUBRIC.md`'s "Unfixed findings" section (items 3–6 and 14) — not repeated here.

**Comparing Kimi to MiniMax, since that was the other half of the point of running this:**
Kimi followed the requested report format (exploit scenario + severity + fix, and an explicit
"clean" verdict where warranted) more consistently than an unstructured review would, and its
noise discipline matched MiniMax's — genuinely clean files were reported as clean, not padded
with nitpicks. Its weak point is severity calibration: identical findings got different ratings
on different runs (one open-redirect finding rated HIGH once and CRITICAL on an identical
re-run), and the R14 pattern got five different severity judgements across five structurally
identical instances in the same sweep — so its findings list is reliable, its priority
*ordering* is not, and needs a human pass before being acted on. It also produced one confident
but wrong remediation suggestion (recommending `|escapejs` in a spot where `|escape` was
already correct) — a reminder that "state the exploit scenario" doesn't guarantee the fix
suggested alongside it is right. Cross-file tracing was opportunistic (only on the 2 files that
went agentic) rather than the systematic file-to-file cross-referencing MiniMax did on nearly
every review — MiniMax's general-quality prompt structure inherently forces that; Kimi's
narrower security brief didn't ask for it explicitly, and mostly didn't do it unprompted.

### Chunk 7: Feature scope — DONE 2026-09-08

[`docs/QUALITY_LABS_SCOPE.md`](docs/QUALITY_LABS_SCOPE.md) is the decision document: per tool
(seven mini-tools — bulletins excluded, see the doc's rationale), its size, test coverage,
dependencies, what removing it would cost and what keeping it commits to.

**Decided (Jonny): keep all seven.** This fork is deliberately "everything plus the kitchen
sink" — features get cherry-picked into `master` individually later, on their own merits,
rather than curated down now. That reframes the coverage gaps the doc found from a scoping
question into Chunk 10's priority order directly: worst-covered first, so nothing here reaches
a cherry-pick decision while still mostly unverified. Worst to best: the building map
(34-37%), Shopping (42%), Lost & Found (~0% outside photo upload), Exchange (55%) — see Chunk
10 below.

### Chunk 8: Deduplicate — NOT STARTED

Promote `_user_volunteer` to `toolkit/util`. Shared `csv_response()` helper for the three
hand-rolled exports. Unify the two ICS generators. Give `tmdb.py` / `omdb.py` a common interface
so callers stop branching. Add `{% include %}` to the three `shopping_buy*.html` variants.

### Chunk 9: Extract inline JS and CSS — NOT STARTED

The largest single win, and the one no previous pass touched. Follow the existing
`diary/static/diary/js/edit_event.js` precedent. **Likely two sessions on its own** — one
template per commit, stop cleanly between them.

1. `labs/floorplan.html` — 721 lines, zero server-side templating. Pure lift-and-shift.
2. `inductions/.../session_detail.html` — 649 lines.
3. `form_event.html` — 1,306 lines across four blocks.
4. `edit_rota.html` — last. Its 894-line `<style>` block and template-interpolated JS need the
   most care.

Tests will not cover this. See the browser verification note below.

### Chunk 10: Tests — IN PROGRESS, started 2026-09-08

Reordered 2026-09-08 per the Chunk 7 outcome: since every `labs` tool is being kept, close its
coverage gaps first, worst-covered to best, before the other named gaps below.

1. ~~**Building map**~~ — **done.** New `toolkit/labs/tests/test_floorplan.py` (29 tests)
   takes `floorplan.py`/`loft.py`/`area_photos.py` from 34-37% to **100%** each. Also found and
   fixed a live stored-XSS bug while writing it (not previously flagged): `floorplan()` was
   embedding `notes_json`/`area_photos_json`/`loft_items_json` via raw `json.dumps()` + `|safe`,
   same root cause as rubric rule R13 (room notes and loft item names/descriptions are
   free-text, volunteer-editable). Switched to `daterange.safe_json()`, same fix as the earlier
   `_rooms_json()` finding. Regression tests: `test_notes_json_is_script_safe`,
   `test_loft_items_json_is_script_safe`.
2. ~~**Shopping**~~ — **done.** New `toolkit/labs/tests/test_shopping_buy.py` (34 tests) plus
   two additions to the existing `test_shopping.py` cover the previously-untested two-thirds:
   `shopping_item_add`, `shopping_supplier_add`/`_delete`, the whole buyer workflow
   (`shopping_buy`, `shopping_buy_supplier`, `shopping_buy_unsorted`, `shopping_item_enrich`,
   `shopping_buy_add`, `shopping_out_of_stock`), and the `shopping_pledge` re-pledge branch —
   which turned out to only fire when the existing pledge is already *fulfilled* (an
   unfulfilled one of any status short-circuits with "someone already pledged" first), not what
   the name suggested going in. `shopping.py`: 42% → **100%**.
3. ~~**Lost & found**~~ — **done.** New `toolkit/labs/tests/test_lost_found.py` (19 tests)
   covers the browse tabs, detail view, claim/dispose flows (including the "already
   claimed/disposed → 404" and "invalid form data → no-op" branches), the label page, and the
   `FoundItem` model's `label_id`/`status_display`/`is_overdue` logic. `lost_found.py`: 50% →
   **100%**.
4. ~~**Exchange**~~ — **done.** New `toolkit/labs/tests/test_exchange_actions.py` (25 tests)
   covers the four state-transition actions the doc flagged
   (`mark_on_loan`/`mark_returned`/`mark_all_gone`/`mark_missing`), each one's feature-flag
   gate, the `exchange_item`/`exchange_edit`/`exchange_withdraw` gates, and the
   `exchange_add` owner-volunteer auto-assignment branch. `exchange.py`: 55% → **100%**.

**All four `labs` coverage targets are done.** Whole-package result:
`floorplan.py`/`loft.py`/`area_photos.py`/`shopping.py`/`lost_found.py`/`exchange.py` all at
100%; `labs/views/` overall 97% (only `bulletins.py` 86%, `collectives.py` 99%, `donations.py`
90% remain short of full, none of them Chunk 7 targets). 1,245 tests passing (was 1,129 at
session start).

**Follow-up (same day): "strange user" edge cases**, at Jonny's request after the feature-flag
work above. Three categories, one new file each:

- `toolkit/labs/tests/test_edge_case_users.py` — logged-in users with no linked `Volunteer`
  profile (any Panopticon/Programmer account), unicode/emoji/very-long free text in labs'
  user-supplied fields, and GDPR-anonymised volunteers (`Volunteer.anonymise()` scrubs the
  Member/Volunteer/User rows and disables login, but the row itself survives, still referenced
  by `ExchangeItem.owner_volunteer`, `NeedFlag.flagged_by`, `ProcurementPledge.pledged_by`).
  18 tests, all confirming existing behaviour rather than finding gaps in labs itself — except
  one, below.
- `toolkit/toolkit_auth/tests/test_login_signals.py` — **a real bug, found by the no-volunteer
  test's `self.client.login()` calls.** `user_login_failed_callback`
  (`toolkit_auth/decorators.py`) did `request.META.get("REMOTE_ADDR")` unconditionally, but
  Django's `user_login_failed` signal fires with `request=None` whenever `authenticate()` is
  called without a request — which includes Django's own test `Client.login()`, any management
  command that authenticates directly, and some third-party auth backends. Every failed login
  through one of those paths crashed with `AttributeError: 'NoneType' object has no attribute
  'META'` instead of just logging a warning. Fixed with a `request is not None` guard, falling
  back to `"unknown"` for the IP. 2 regression tests. This is also `toolkit_auth`'s first test
  file — Chunk 10's "currently zero tests" note below no longer applies to `decorators.py`'s
  signal handlers specifically, though the rest of the app (the auth backend itself,
  `feature_required`, etc.) is still untested.

1,284 tests passing (was 1,245 before this follow-up).

**Destructive paths — done 2026-09-08.** New `toolkit/members/tests/test_pool_bulk_actions.py`
(33 tests) covers `bulk_anonymise_volunteers` and `bulk_delete_never_onboarded` end to end: both
steps of each two-step select→confirm flow, the typed-phrase mismatch guard, the delete/anonymise
split in the delete flow (clean candidates hard-deleted, ones with rota or last-gasp history
falling back to anonymise), the portrait-file cleanup branch, and the non-superuser/GET-redirect
guards on both. Picked up a few cheap adjacent gaps in the same file while there:
`admin_restore_volunteer`'s no-op-with-warning branch (calling it on an Active volunteer),
`last_gasp_email`'s and `bulk_last_gasp_email`'s disabled-flag branches, and
`auto_dormancy_apply`'s "no thresholds configured" branch. `volunteer_pool_admin.py`: 54% → **99%**
(one line, 727, is dead code — the `action` variable is always normalised to `"compose"` or
`"send"` before that fallback `return` could ever run, so left uncovered rather than contorting a
test to hit unreachable code).

**A $0.027 MiniMax M3 spot-review of that new test file caught a real one-line bug it introduced
coverage for, not just test-quality nits**: `bulk_anonymise_volunteers` and
`bulk_delete_never_onboarded` both build their typed-confirmation phrase as
`f"... {n} volunteers"` unconditionally, so a single-volunteer selection asks the Panopticon to
type "anonymise 1 volunteers" — and the new tests, having been written by reading the view, had
baked the wrong string in as the expected value rather than catching it. Fixed both f-strings to
pluralise correctly, updated the four tests that asserted the literal phrase. Also fixed, same
review: `test_send_step_sends_and_logs`/`test_send_step_skips_volunteers_in_cooldown` only checked
`LastGaspEmailLog` row counts (a broken `send_mail` with the log-create surviving would still
pass) — now assert on `mail.outbox` too; the portrait-delete test only checked the `Volunteer` row
was gone, never that the file itself was removed — rewritten with a real uploaded file in a
temporary `MEDIA_ROOT` and an `os.path.exists()` check before/after; both "wrong confirmation
phrase" tests only checked the happy path didn't fire, never the error message itself — added
`assertContains(resp, "did not match")`. Tried a free-tier model first (`nemotron-3-ultra:free` via
OpenRouter) for this same review — it read both files (20k input tokens) then stopped after 96
output tokens with no written report, tool-call budget or free-tier throttling presumably cutting
it short before any text generation. `minimax-m3:free` errored outright with a server
`UnknownError`, unchanged from the Chunk 5 gotcha even after lifting the account's zero-data-
retention filter — so ZDR was never the actual blocker on that one. Conclusion: free OpenRouter
models aren't reliable enough for this workflow yet; keep using paid MiniMax M3 as the default,
per the existing model-choice note above — a two-file spot-review like this one costs about 3
cents and reliably returns a written report.

1,317 tests passing (was 1,284).

**`toolkit_auth/backends.py` and the permission decorators — done 2026-09-08.** Both already had
incidental coverage from every other app's tests exercising them on the way to something else
(79% and 98% respectively at session start), which is exactly the gap Chunk 4 flagged: high
numbers, nothing asserting on the module's *own* contract. New `test_backends.py` (6 tests) hits
`EmailOrUsernameBackend.authenticate`'s username path, the case-insensitive email fallback, wrong
password, unknown user, an inactive user (blocked via `user_can_authenticate`), and the
duplicate-email `MultipleObjectsReturned` case — Django's `User.email` has no uniqueness
constraint, so two accounts can share one, and the fallback correctly refuses to guess rather than
picking one. New `test_decorators.py` (18 tests) exercises `write_required`, `read_required`,
`write_required_strict`, `panopticon_required`, `feature_required` and
`ip_or_permission_required` directly via `RequestFactory`, each across anonymous/no-perm/has-perm,
checking both the gate itself and the `request.view_access_level` badge value it sets on success.
One assumption checked and corrected while writing these: `ip_or_permission_required`'s non-IP
fallback wraps Django's own `permission_required`, which without `raise_exception=True` **redirects
to login rather than raising `PermissionDenied`**, even for an authenticated user with no
permission — the first draft assumed a 403 and the test failed, confirming the real behaviour
before pinning it. `backends.py`: 79% → 100%; `decorators.py`: 98% → 100%. 1,341 tests passing (was
1,317).

**`volunteer_edit.py`'s gaps — done 2026-09-08.** New `test_volunteer_edit_extra.py` (18 tests)
covers the username-collision-on-create loop, the non-superuser save-target redirect (a plain
volunteer editing their own profile lands on `view-volunteer-list`, not the Panopticon summary),
the suspension-lifted message and the suspension-email preview block (suspend via the dedicated
`toggle_volunteer_suspension` view, then confirm `edit_volunteer`'s GET renders the pending
preview), and the five standalone endpoints that had no coverage at all:
`set_volunteer_password`, `send_volunteer_password_reset`,
`add_volunteer_qualification`/`remove_volunteer_qualification`, and
`save_volunteer_permissions` (including the Panopticon-grant-needs-a-reason validation branch).
`volunteer_edit.py`: 63% → **97%**. The remaining 3% is two genuinely unreachable branches, left
uncovered rather than contorted around: `Volunteer.user` is a non-nullable `OneToOneField`, so the
"volunteer has no linked user" defensive checks in `set_volunteer_password` and
`save_volunteer_permissions` can never fire; and `edit_volunteer`'s own "just got suspended"
message/redirect branch is dead too — `VolunteerForm` explicitly excludes `STATUS_SUSPENDED` from
its choices (suspension is "handled outside this form...via a dedicated toggle action", per the
form's own comment), so that transition can only ever happen through
`toggle_volunteer_suspension`, which carries its own equivalent messaging. 1,359 tests passing
(was 1,341).

Then the last item originally scoped for this chunk: strengthening the 102 status-code-only tests
to assert on state rather than just HTTP 200.

### Chunk 11: Un-star members/views, split what's god-sized — NOT STARTED

Replace `from ._common import *` across the eight `members/views/` modules with explicit
per-module imports, then delete the quarantine block from `pyproject.toml`. Ruff cannot autofix
this, but its `F405` output names every symbol per module, so the import lists can be generated
mechanically and verified by re-running ruff.

Then `diary/forms.py` (1,656 lines, 34 form classes) and `inductions/views.py` (845 lines, 33
functions) — the two that never got the package treatment. Finish the `member_views.py` split
June left half-done.

**Apply the lesson:** split by moving imports, then let ruff prove what each module actually
needs. Do not copy a shared header, and do not reach for a star-import hub. Those are precisely
the two shortcuts that produced this chunk.

`seed_dev_data.handle()` (complexity 101, ~1,090 lines before the first helper) is lowest
priority — dev-only. Keep pushing its data into the TOML fixtures rather than restructuring the
Python.

### Chunk 12: Confirm the uplift landed — NOT STARTED

Re-run the Chunk 4 measurements. Then a small second MiniMax pass (~5 files, ~$0.10) over the
most heavily changed modules, checking the uplift helped rather than just making the code
Claude-shaped in a new way. Update `docs/QUALITY_BASELINE.md` with before/after.

---

## Verification

Every chunk gates on this, and every session starts by running it to confirm a green start:

```bash
docker compose exec toolkit /venv/bin/python3 manage.py test --settings=toolkit.test_settings
docker compose exec toolkit /venv/bin/ruff check toolkit
docker compose exec toolkit /venv/bin/black --line-length 79 --check toolkit
```

Baseline to beat: **1,136 tests passing**. Tests run *only* inside the container — there is no
local venv and the C extensions exist only in the image.

Chunk 9 is the one part tests will not cover. It needs a browser pass over the rota editor,
event form, floorplan and induction session detail, confirming the interactive behaviour still
works. **Fold in a check of the 2026-09-08 session_detail.html XSS fix while there**: the
account-creation flow (create accounts, duplicate-match, force-create, edit-signup, walk-in add)
all now runs untrusted response fields through a client-side `escapeHtml()` before `.innerHTML`
— confirm signup names/usernames still render correctly (no double-escaping, no literal `&amp;`
where a plain `&` should show) and that the flow still works end-to-end, since this is a
client-side JS sink with no Django-test-client coverage.

## Spend log

| Date | Chunk | Model | Files | Cost |
|---|---|---|---|---|
| 2026-09-08 | 5 | `openrouter/minimax/minimax-m3` | 68 (+1 throwaway re-run, see Chunk 5 gotcha) | $1.2999 |
| 2026-09-08 | 6 follow-up | `openrouter/moonshotai/kimi-k2-thinking` | 23 (+2 retries, see gotcha) | $0.2772 |
| | | **Total** | | **$1.5771** |
