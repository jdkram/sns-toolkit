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
| Chunks done | 0, 1, 2 |
| Next chunk | **3 (docs drift)** |
| Tests | 1,129 passing |
| Ruff | 0 findings |
| Black | clean at 79 |
| CI | `.github/workflows/ci.yml` + `.pre-commit-config.yaml` in place, not yet exercised by a real PR |

Commits so far, newest first:

```
(this commit)  docs(quality): record Chunk 2 results in the pass tracker
f46c977d  ci(quality): add pre-commit and GitHub Actions gates
b980935a  chore(quality): triage the 110 remaining ruff findings
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

### Chunk 3: Docs drift — NOT STARTED

Fix the 20 dead paths, starting with `ONBOARDING.md:280,282,298` and `SPEC.md:481` — what a new
human hits first. Add `operations` and `audit` to the onboarding app tour. Document the new
lint/coverage commands in `ONBOARDING.md`, replacing the prose tool settings now that
`pyproject.toml` owns them.

### Chunk 4: Baseline — NOT STARTED

Per-module coverage report in the container. Write `docs/QUALITY_BASELINE.md`: LOC and
complexity per app, coverage per module, ruff counts after Chunk 1, template size and inline-JS
totals. The before-picture, re-measured at Chunk 12.

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
