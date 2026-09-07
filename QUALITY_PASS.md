---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Opus 5"]
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
| Chunks done | 0, 1, 2, 3, 4 |
| Next chunk | **5 (MiniMax M3 broad sweep)** |
| Tests | 1,129 passing |
| Ruff | 0 findings |
| Black | clean at 79 |
| Coverage | 81.5% overall (21,788 statements) — see `docs/QUALITY_BASELINE.md` |
| CI | `.github/workflows/ci.yml` + `.pre-commit-config.yaml` in place, not yet exercised by a real PR |

Commits so far, newest first:

```
(this commit)  docs(quality): write the Chunk 4 coverage/complexity baseline
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

**A user hook rewrites the phrase "load-bearing" to "critical" on Write/Edit.** It fires on
those tools but not on `sed` or a heredoc via Bash. It exists to strip a tell of AI authorship,
which is fine for text the agent writes, but it will also silently rewrite *Jonny's* existing
prose in any file those tools touch. When making a surgical change to an existing doc, prefer
`sed`, and check `git diff` for edits you did not intend.

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

### Chunk 5: MiniMax M3 broad sweep (~40 files, ~$0.70) — NOT STARTED

Every non-test module in `labs/`, `inductions/`, `audit/`, `operations/`, plus
`diary/edit_views/`, `diary/forms.py`, `diary/models/`, `members/views/`, and the four worst
templates reviewed as templates.

Mechanics per the `hand-off-agents` skill: run **from the repo root** (`opencode run`
auto-rejects reads outside its working directory, and prints the rejection to stderr only —
stdout shows an empty response with no error). Use `--format json` and model
`openrouter/minimax/minimax-m3`. Cost and tokens are nested under `.part`, not top-level:

```bash
jq -r 'select(.type=="step_finish") | .part.cost'
```

Prompt aimed at Claude's specific weaknesses rather than "review this":

> Review `<path>` for what a Claude-authored review tends to miss: unnecessary verbosity,
> defensive error handling for scenarios that cannot happen, premature abstraction, and
> configuration knobs nothing sets. Then answer separately: what in this file would a competent
> Django developer with no AI assistance struggle to modify safely, and why? Cite line numbers.

Raw output to the session scratchpad, **not** into the repo. Log each run's actual cost in the
table at the foot of this file.

**Guard rail:** set a spend cap in the OpenRouter dashboard before starting. This is a
40-invocation loop, and unchecked agentic spending is a recurring complaint about the platform.

**Not doing:** the OpenCode Go subscription. The 2026-09-07 bake-off puts three file reviews at
$0.0487, so forty is ~$0.65. A $5–10/month subscription buys nothing this workload needs.

### Chunk 6: Synthesise a rubric — NOT STARTED

Deduplicate MiniMax's findings against the still-open items in `docs/REVIEW_2026_OVERHAUL.md`
(its three security findings are already fixed — verified 2026-09-07; its maintainability
findings are not). Turn recurring patterns into `docs/QUALITY_RUBRIC.md`: a written, checkable
standard for this codebase.

This is the step that makes the money worth spending. The rubric is what lets Chunks 8–11 run
without re-paying for external review per file, and it is the artefact that outlives the pass.

### Chunk 7: Feature scope — NOT STARTED, NEEDS JONNY

Nothing is deployed with live users, so there is no usage signal to audit. This is a values
question, not a data question.

`labs` is 4,281 lines, 60 URL patterns and 23 templates across eight mini-tools (collectives,
jobs, shopping, donations, loft, lost-and-found, exchange, floorplan). Each carries permanent
maintenance cost and adds to what a new volunteer navigates past to find the thing they came
for.

Produce a **decision document, not a deletion**: per tool, its size, test coverage,
dependencies, what removing it would cost and what keeping it commits to. Then work through it
with Jonny. No code removed without his call. Do this before Chunk 10 so coverage is not
invested in something he would rather cut.

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

### Chunk 10: Tests — NOT STARTED

Destructive paths first: `bulk_anonymise_volunteers`, `bulk_delete_never_onboarded`. Then
`toolkit_auth/` (the backend and decorators every app depends on, currently zero tests). Then
the `labs/shopping.py` and `volunteer_edit.py` gaps. Extend the `labs/tests/test_security.py`
pattern, which the June review correctly praised.

Then strengthen the 102 status-code-only tests — assert on state, not just HTTP 200. Natural
session boundary between the two halves.

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

Baseline to beat: **1,129 tests passing**. Tests run *only* inside the container — there is no
local venv and the C extensions exist only in the image.

Chunk 9 is the one part tests will not cover. It needs a browser pass over the rota editor,
event form, floorplan and induction session detail, confirming the interactive behaviour still
works.

## Spend log

| Date | Chunk | Model | Files | Cost |
|---|---|---|---|---|
| | | | | |
| | | **Total** | | **$0.00** |
