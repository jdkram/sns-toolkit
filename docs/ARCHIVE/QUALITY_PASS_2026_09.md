---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Opus 5", "Claude Sonnet 5"]
status: "#ai-input"
---

# Quality Pass Plan (September 2026, archived)

> **Status:** complete. All twelve chunks done on branch `chore/quality-pass-2026-09`
> (branched from `sns_2026_overhaul` at `ccbb3d6a`), browser-verified, and merged back.
> This file is the working log as it stood at the close of the pass, kept for the measured
> findings and the reasoning behind each decision; the commit history is the authoritative
> record of what changed. Its lasting outputs live elsewhere: `pyproject.toml`, the CI and
> pre-commit gates, [`docs/QUALITY_RUBRIC.md`](../QUALITY_RUBRIC.md), and the "Tooling and
> gates" section of `CLAUDE.md`. Open items it left behind are Bugs AV–AY in
> [`docs/tasks/known-issues.md`](../tasks/known-issues.md).
>
> Two notes in the state block below were overtaken before the merge: the manual browser
> check of `session_detail.html` was done on 2026-09-08 (see Chunk 9's follow-up section),
> and the CSV formula guard reached all three exports in Chunk 8. On 2026-09-08 that guard
> was also narrowed so `+44…` phone numbers export verbatim, after an independent review of
> the finished branch caught the regression.
> **Last updated:** 2026-09-08

### State at the end of the last session (2026-09-08)

| | |
|---|---|
| Branch | `chore/quality-pass-2026-09`, working tree clean |
| Chunks done | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 — all chunks complete |
| Next chunk | none — the plan's chunk list is exhausted |
| Tests | 1,359 passing (unchanged by Chunks 8 and 9 — both move code rather than add coverage; was 1,129 at session start — +7 security-fix regressions, +29 building-map, +34 shopping, +19 lost & found, +25 exchange, +21 feature-flag-gate, +18 edge-case-user, +33 destructive-path, +24 toolkit_auth, +18 volunteer_edit tests; the status-code-only strengthening pass and Chunk 11's package splits added no new tests) |
| Ruff | 0 findings |
| Black | clean at 79 |
| Coverage | 85.5% overall (23,631 statements), up from 81.5% baseline — see `docs/QUALITY_BASELINE.md` for the full before/after |
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

**2026-09-08: `Co-Authored-By`/`Claude-Session` trailers stripped from all 45 commits on this
branch**, at Jonny's explicit request. Same precedent as the `sns_2026_overhaul` rewrite documented
in `CLAUDE.md` ("Disclosure of AI involvement lives in the file-level `ai-contributors:` tags
instead"). Trees are byte-identical (checked via `git diff` against a backup tag); only the trailer
lines are gone. Old tip preserved as tag `backup/pre-trailer-strip/chore-quality-pass-2026-09`.
Branch was never pushed anywhere (checked `origin`/`homeserver` before rewriting), so this was a
safe local-only history edit — every hash below changed as a result. **Going forward: no more
`Co-Authored-By`/`Claude-Session` trailers on this branch's commits.**

Commits so far, newest first:

```
036f85bb  fix(quality): stop session_detail.js's modal crash cascading, restore onclick resilience
77178035  refactor(quality): extract edit_rota.html's inline JS/CSS, close Chunk 9 (4/4)
93aa7f9a  refactor(quality): extract form_event.html's inline JS/CSS (Chunk 9, 3/4)
40a8131a  refactor(quality): extract session_detail.html's inline JS/CSS (Chunk 9, 2/4)
a6af238d  refactor(quality): extract floorplan.html's inline JS/CSS (Chunk 9, 1/4)
d80d2fe2  refactor(quality): close Chunk 8, deduplicate cross-app helpers
6aa9a4a5  docs(quality): close Chunk 12, re-measured baseline confirms uplift
dedeed38  docs(quality): record Chunk 11 completion, all four sub-tasks
b80d8225  refactor(quality): split inductions/views.py into a package (Chunk 11)
cdaad9fa  refactor(quality): split diary/forms.py into a package (Chunk 11)
8c4ee34e  refactor(quality): remove old member_views.py path (Chunk 11 follow-up)
14282f8c  refactor(quality): fold member_views.py into members/views/ package (Chunk 11)
8fbc083a  docs(quality): record Chunk 11 part 1 completion
d7da82ef  refactor(quality): un-star members/views imports (Chunk 11, part 1)
3785d363  docs(quality): sync CURRENT_WORK.md with Chunk 6/7/10 completion
2911a5c9  test(quality): strengthen status-code-only assertions, close Chunk 10
13edee54  test(quality): close volunteer_edit.py's coverage gaps (Chunk 10)
8111cea5  test(quality): give toolkit_auth its own tests (Chunk 10)
4b96934c  fix(members): pluralise bulk-confirm phrases, strengthen weak test assertions
c407776a  test(quality): cover the destructive bulk volunteer-pool actions (Chunk 10)
6b9a8cb5  docs(quality): bring the resume log and CURRENT_WORK.md up to date for handoff
88242d42  test(labs): add "strange user" edge-case coverage, fix a real login-signal crash
7bd27a7a  feat(labs): make every labs mini-tool toggleable via SiteConfiguration
0dedc80b  test(quality): close the exchange.py coverage gap, all four labs targets done
31341f73  test(quality): close the lost_found.py coverage gap (Chunk 10, third target)
56a4d2fb  test(quality): close the shopping.py coverage gap (Chunk 10, second target)
75a5723e  feat(quality): record the Chunk 7 decision, close the building-map coverage gap
99ed0eb1  docs(quality): write the Chunk 7 labs feature-scope decision document
df6231f3  docs(quality): fold the session_detail.html XSS fix into Chunk 9's browser-check note
ea3024b8  fix(security): patch the 6 findings flagged by the Chunk 5/6 review sweeps
c497b556  docs(quality): update resume commit log with the R14 resolution commit
04d0f9ce  docs(quality): resolve R14 (shared-resource access stays open), set MiniMax as default model
33432d1a  docs(quality): fix placeholder commit hash in the resume log
da57229a  docs(quality): synthesise Chunk 6 rubric, run Kimi security sweep, flag 4 new XSS/CSVi findings
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

A maintainability pass already ran in June 2026 ([MAINTAINABILITY_PASS_2026_06.md](MAINTAINABILITY_PASS_2026_06.md),
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

Wrote [`docs/QUALITY_BASELINE.md`](QUALITY_BASELINE_2026_09.md): per-app Python/template LOC,
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

Wrote [`docs/QUALITY_RUBRIC.md`](../QUALITY_RUBRIC.md) from all 68 MiniMax Chunk 5 reviews,
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

[`docs/QUALITY_LABS_SCOPE.md`](QUALITY_LABS_SCOPE_2026_09.md) is the decision document: per tool
(seven mini-tools — bulletins excluded, see the doc's rationale), its size, test coverage,
dependencies, what removing it would cost and what keeping it commits to.

**Decided (Jonny): keep all seven.** This fork is deliberately "everything plus the kitchen
sink" — features get cherry-picked into `master` individually later, on their own merits,
rather than curated down now. That reframes the coverage gaps the doc found from a scoping
question into Chunk 10's priority order directly: worst-covered first, so nothing here reaches
a cherry-pick decision while still mostly unverified. Worst to best: the building map
(34-37%), Shopping (42%), Lost & Found (~0% outside photo upload), Exchange (55%) — see Chunk
10 below.

### Chunk 8: Deduplicate — DONE 2026-09-08

All five items done, one adjusted on inspection. 1239 tests still pass (same count as before —
no coverage lost or gained here, this chunk moves code rather than adding to it); `ruff` and
`black` both clean.

**`_user_volunteer` → `toolkit/util/volunteers.py`** as `user_volunteer`. It was a byte-for-byte
duplicate between `labs/views/_common.py` and `operations/views/maintenance.py`. `labs/_common.py`
re-exports it under its old private name so the six labs submodules that import
`_user_volunteer` from `._common` didn't need touching.

**`csv_response()` in `toolkit/util/csv_export.py`**, replacing the hand-rolled
`HttpResponse`/`csv.writer` pairs in `members/views/volunteer_export.py`,
`inductions/views/export.py` and `diary/edit_views/reports.py`. This closes the gap the Chunk 6
write-up flagged (line 41-43 above): only the inductions export guarded against formula
injection (a leading `=`/`+`/`-`/`@` executed as a formula by the spreadsheet app that opens the
file); the other two exported member-supplied free text — names, notes, full postal addresses —
with no guard at all. `csv_response()` applies the guard to every cell unconditionally, so all
three exports now have it.

**ICS generators unified** into `toolkit/util/ics.py`'s `build_vevent()`, called by both
`diary/calendar_links.py`'s `build_ics` (showings) and `inductions/views/public.py`'s
`calendar_ics` (induction sessions). Unifying surfaced a real latent bug in the inductions one,
not just duplication: it built `DTSTART;TZID=Europe/London` from `session.date.strftime()`
directly, unescaped. But `USE_TZ=True` is the project default (nothing overrides it), so
`session.date` is timezone-aware and `.strftime()` on an aware datetime prints whatever tzinfo
it currently carries — UTC, not Europe/London — so the emitted time was quietly wrong by an
hour for any session during BST, despite the label claiming otherwise. It also skipped the
RFC 5545 escaping the diary version had, so a session title with a comma or semicolon produced
a malformed `.ics` file. The shared `build_vevent()` always emits absolute UTC (`Z` form, no
TZID) and always escapes, so both bugs are gone by construction rather than needing per-call-site
fixes. No existing test asserted the old TZID string, so nothing needed updating for the fix.

**`tmdb.py`/`omdb.py`: deleted `tmdb.py` rather than giving it a common interface with `omdb.py`,
deviating from this chunk's original plan.** Checked first, since "unify two API clients" implied
there were two live branch points to unify: `tmdb.py` turned out to be fully dead code. Migration
`diary/0083_omdb_replace_tmdb` (itself now squashed away, visible only via the field
add/remove pair inside `0036_v2.py`) retired `SiteConfiguration.tmdb_api_key` when the app moved
to OMDb; `toolkit/diary/edit_views/film.py` only ever imports from `omdb.py`. `tmdb.py` had zero
importers anywhere in the app or its tests — a leftover from before the OMDb switch, not a live
alternative path callers branch on. Deleted outright (`grep`-verified no references first) rather
than built a common interface for a branch that doesn't exist. `docs/tasks/events-and-rota.md`'s
9.66 write-up still described TMDB as the live integration; added a correction note there rather
than rewriting the historical spec. `Film.tmdb_id`/`tmdb_certificate`/`tmdb_poster_path`/
`tmdb_fetched_at` remain on the model and stay permanently null under OMDb — a data-model
question, left alone.

**`shopping_buy*.html`: lighter dedup than planned, because the actual overlap was lighter than
assumed.** The three pages are largely independent (a supplier-picker card grid, a per-supplier
order table, an unsorted-items sorting table) — there was no block of literally repeated markup
across all three to `{% include %}` wholesale. What did repeat verbatim: the "title + back link"
header on the two table pages, and their table CSS skeleton (`width`/`border-collapse`/`th`
styling/hover, plus `.item-meta`). Extracted both into `labs/_buy_header.html` and
`labs/_buy_table_css.html`; `.buy-table`/`.sort-table` unified to one `.shop-table` class, with
each page keeping its own `td { vertical-align }` override since those genuinely differed
(`middle` vs `top`). The picker page (`shopping_buy.html`) has nothing in common with the other
two beyond ordinary page skeleton, so it's untouched — forcing an include there would have been
inventing duplication to satisfy the plan rather than removing real duplication.

### Chunk 9: Extract inline JS and CSS — DONE 2026-09-08

The largest single win, and the one no previous pass touched. **Likely two sessions on its
own** — one template per commit, stop cleanly between them.

1. ~~`labs/floorplan.html`~~ — **done 2026-09-08.** 721 lines, essentially zero server-side
   templating in the JS/CSS itself (three JSON blobs + a handful of URL/CSRF values at the
   top of the old inline `<script>`). Moved the `<style>` block verbatim to
   `labs/static/labs/css/floorplan.css` (linked via `{% block css %}`) and the `<script>` body
   to `labs/static/labs/js/floorplan.js`. The precedent named in the original plan
   (`diary/static/diary/js/edit_event.js`) turned out to be dead code itself — nothing
   includes it or its `mailout.js` sibling anywhere. Used the pattern that's actually live
   instead: `edit_rota.html`/`edit_rota.js`, where the external file exports a single factory
   function (`edit_rota(jQuery, ...args)`) and a two-line inline `<script>` block calls it with
   the template-rendered values as arguments. `floorplan.js` now exports `floorplan(notes,
   loftItems, areaPhotos, CSRF, ...urlTemplates, svgUrl)` the same way — the only Django
   template syntax left in `floorplan.html` is that one call. Verified: `node --check` on the
   new JS file, `toolkit.labs.tests` (320 tests, all still pass — `test_floorplan.py`'s
   XSS-safety assertions on `notes_json`/etc. cover the same rendered `<script>` block), and a
   throwaway Client-based smoke test (not committed) confirming the page still renders 200 with
   the new `<link>`/`<script src>` tags present and no leftover inline `<style>`. No live
   browser click-through — the Chrome extension wasn't connected this session — so still worth
   a manual check that room/zone editing, photo upload, and the SVG map click-to-scroll still
   work before this one's trusted for a screen nobody's watching closely.
2. ~~`inductions/.../session_detail.html`~~ — **done 2026-09-08.** 649 lines, and unlike
   `floorplan.html` this one had real server-side templating threaded through the JS: four
   `{% if user.is_superuser %}` branches inline in the script (one wrapping the whole edit-modal
   setup, one in the keydown handler, two inside a hand-built HTML string for a JS-inserted
   walk-in row), and two URLs built by hand-concatenating `{{ session.slug }}` into a JS string
   literal (`link-existing`, `remove-signup`) instead of using the `EDIT_URL_PATTERN`-style
   `{% url ... signup_id=0 %}` + `.replace('/0/', ...)` convention already used for the other
   four URLs on the page. Moved the `<style>` block to
   `inductions/static/inductions/css/session_detail.css` and the `<script>` to
   `inductions/static/inductions/js/session_detail.js`, exported as a `sessionDetail(opts)`
   factory taking an options object (CSRF, the six URL patterns, `isSuperuser`) — an options
   object rather than positional args because there were too many to keep straight positionally,
   following `mailout.js`'s precedent for that. The four `{% if %}` branches became a JS-side
   `if (opts.isSuperuser)`; the two hand-built URLs became `LINK_EXISTING_URL_PATTERN` /
   `REMOVE_SIGNUP_URL_PATTERN`, matching the existing convention (and no longer trusting a slug
   containing "/0/" to not collide, though that was already the existing pattern's assumption,
   not a new one). Checked whether `isSuperuser` gating is actually reachable both ways: the
   whole view is `@panopticon_required` (superusers only, `toolkit_auth/decorators.py`), so
   `isSuperuser` is always `true` in practice — the template's `{% if user.is_superuser %}`
   was already dead weight before this refactor, not something this chunk introduced. Two
   throwaway Client-based smoke tests (not committed) confirmed: the page renders 200 with the
   new static refs, `isSuperuser: true` present, and no leftover inline `<style>`; a non-panopticon
   user gets a 403 before any of this code runs. `node --check` clean; the existing 52
   `toolkit.inductions.tests` unchanged and passing. No live browser click-through this session
   either (extension not connected) — same caveat as `floorplan.html`: worth a manual pass over
   attendance checkboxes, walk-in registration, the edit modal, cap editing, and keyboard nav
   before trusting this fully.
3. ~~`form_event.html`~~ — **done 2026-09-08.** The biggest of the four (1,832 lines total by
   the time this ran — grown since the plan's 1,306 estimate), two separate inline `<script>`
   tags (one for the copy-summary counter, break-even calculator, field tips, cost-terms
   field-swap, poster generation and the crop/letterbox-bars tool; a second, self-contained, for
   OMDb film search/link), plus one `<style>` block. Moved the CSS to
   `diary/static/diary/css/form_event.css` verbatim and merged both scripts into one
   `diary/static/diary/js/form_event.js`, exported as a single `formEvent(opts)` factory — each
   original script kept its own internal IIFE wrapper, so the two blocks' variable scoping is
   unchanged (no risk of the crop-tool code and the film-search code colliding on a name).
   Four `{% if %}`-gated IIFEs (`structured_cost_terms_enabled`, `ticket_link_guidance_html`,
   `tag_descriptions_json`, `top_5_tag_pks_json`) became `if (opts.xxx)` guards; the two JSON
   blobs (`tag_descriptions_json`/`top_5_tag_pks_json`) needed the options-object property
   itself wrapped in `{% if %}...{% else %}null{% endif %}` rather than just the JS-side guard,
   because those two context keys are **absent entirely** on the "form re-rendered after a POST
   validation error" path (only the GET path computes them — confirmed by reading
   `edit_views/events.py`), and Django renders a missing variable as an empty string, which
   would otherwise break the options-object literal's syntax (`tagDescriptionsJson: ,`). Found
   one pre-existing latent bug while doing this and deliberately did **not** fix it, to keep
   this a pure extraction: `DEFAULT_TERMS_PLACEHOLDER = '{{ DEFAULT_TERMS_TEXT|escapejs }}'`
   references a template variable that is never in this view's context (no context processor or
   view sets `DEFAULT_TERMS_TEXT`), so it has always silently rendered as an empty string — the
   structured-cost-terms placeholder fallback has likely never actually shown the intended
   default text. Preserved verbatim, out of scope for a Chunk 9 extraction; worth a follow-up
   ticket. Verified: `node --check` on the new JS; the full `toolkit.diary.tests` suite passed
   516/516 both before and after; one existing test (`test_edit_event.py`'s
   `test_get_edit_event_form_no_media_no_legacy_copy`) asserted `assertContains(response,
   "word-counter")`, which was only ever true because that string appeared literally in the old
   inline `<style>`/`<script>` — updated it to assert on the new `diary/js/form_event.js`
   `<script src>` reference instead, same intent (confirms the word-counter feature's JS is
   wired up), now testing the actual current signal rather than an implementation-detail string
   match. Four throwaway Client-based smoke tests (not committed) additionally confirmed: the
   new static refs render with no leftover inline `<style>`/`<script>` content; the
   `structuredCostTermsEnabled` flag reflects both `true` and `false` correctly from
   `SiteConfiguration`; `tagDescriptionsJson` renders as JSON (not `null`) on the GET path; and
   both `tagDescriptionsJson: null` / `top5TagPks: null` render correctly on the POST
   validation-error path. No live browser click-through this session (extension not connected)
   — this template has the most genuinely interactive surface of the four, so a manual pass is
   worth prioritising: the break-even calculator, the crop tool and letterbox-bars colour
   picker/swatches, the OMDb film search-and-link flow, the poster generator, the cost-type
   field-swapping, and the tag-pill tooltips.
4. ~~`edit_rota.html`~~ — **done 2026-09-08.** The premise that "the factory function pattern
   already lives here, mostly a matter of confirming nothing needs to change" turned out to be
   half right: `edit_rota.js`'s `edit_rota(jQuery, ...)` call (rota-editing AJAX — signups,
   notes, clear-email prompts) was indeed already externalised and needed no changes. But a
   *second*, undocumented, ~1,030-line inline `<script>` sat directly after it in the same
   `{% block script %}` — the page's UI layer (filter panel, tag/role filters, the nav rail,
   badge preferences, keyboard shortcuts, the role sign-up picker) — that QUALITY_PASS.md's plan
   hadn't accounted for, plus the 894-line `<style>` block. Moved the CSS verbatim to
   `diary/static/diary/css/edit_rota.css`, and the second script to a new
   `diary/static/diary/js/edit_rota_ui.js`, exported as `editRotaUI(opts)` — a second, separate
   factory alongside the existing `edit_rota(...)` call rather than merging the two, since they
   were always independent concerns communicating only via a `rota:entry-changed` jQuery custom
   event, with no shared state.
   Six `{% if can_mark_events %}` / `{% if current_volunteer_pk %}` conditionals threaded through
   this script, one of them (`ROTA_MARKS`/`setShowingMark`/etc., ~60 lines) wrapping several
   `function` *declarations*. Wrapping declarations like that in a runtime `if` would have been
   a real bug under `"use strict"`, where a function declaration inside a block is block-scoped
   and invisible outside it — but a `typeof setShowingMark === "function"` check later in the
   same script, in the keyboard-shortcut handler, needs `setShowingMark` visible whether or not
   `can_mark_events` is true. Converted those three functions to `var name = function(...) {...}`
   expressions instead: `var` still hoists to the factory's outer scope even from inside an `if`
   block, so `typeof setShowingMark` correctly resolves to `"undefined"` when the mark feature is
   off, exactly matching the original behaviour where the whole block was never emitted by
   Django at all. The other five simpler conditionals (guarding single statements or a
   dynamically-built jQuery selector string) converted directly to `opts.canMarkEvents` /
   `opts.currentVolunteerPk` JS-side checks. Confirmed via `edit_views/rota.py` that
   `rota_marks_json` and `current_volunteer_pk` are always present in context regardless of
   `can_mark_events` (`"{}"` and `""` respectively when the viewing user has no linked
   `Volunteer`), so none of this needed the `{% if %}...{% else %}null{% endif %}`
   options-literal guard that `form_event.html` needed for its two absent-on-one-path JSON blobs.
   Verified: `node --check` on both new JS files; full `toolkit.diary.tests` (516/516) and the
   whole-project suite (1,359/1,359 — unchanged from Chunk 9's start, as expected for a pure
   extraction) both pass; three throwaway Client-based smoke tests (not committed) confirmed the
   new static refs render with no leftover inline `<style>`/`<script>` content, and that
   `canMarkEvents`/`currentVolunteerPk` correctly render `false`/`""` for a rota-permission user
   with no linked `Volunteer` and `true`/non-empty for one with a `Volunteer` record created in
   the test. No live browser click-through this session (extension not connected) — worth a
   manual pass over: the filter panel and tag/role filters, the month nav rail, badge visibility
   toggles (localStorage-backed), the keyboard shortcuts (`j`/`k` navigation, `s`/`1`/`2`/`0`
   marks, `r` role sign-up picker, `?` help modal), and the event-mark star/shadow toggle for a
   user with a linked `Volunteer`.

All four templates in this chunk are now done. **Chunk 9 status: DONE 2026-09-08.**

**Follow-up browser verification, 2026-09-08 (same day, Chrome extension became available):** did the
manual pass all four templates' write-ups above asked for. `floorplan.html`, `edit_rota.html` and
`form_event.html` all checked out clean — tab switching, room-note editing, the filter panel and
badge checkboxes, the break-even calculator, the cost-type field/placeholder swap, and the field-tip
tooltips all work exactly as before, no console errors.

`session_detail.html` surfaced a real bug, found and fixed here:

- **Genuine regression, fixed:** the original inline `<script>` declared `saveCap`/`adjustRoom` as
  bare top-level `function`s, which JS hoists to global scope unconditionally — so the template's
  inline `onclick="saveCap()"`/`onclick="adjustRoom(-1)"` handlers kept working even if something
  *later* in that same script threw. Wrapping everything in the `sessionDetail(opts)` factory lost
  that: the `window.saveCap = saveCap` exports only ran if execution reached that point, so an
  earlier throw meant the Save/±  buttons broke. Fixed by moving both `window.*` exports to the top
  of the factory, right after hoisting makes the functions available, before anything that could
  throw.
- **Pre-existing bug, confirmed not caused by this chunk, contained rather than fixed:**
  `new bootstrap.Modal(_editModalEl)` throws `TypeError: Cannot read properties of undefined
  (reading 'backdrop')` on every load of this page. Verified this is not a regression by swapping
  the pre-Chunk-9 template back in and reloading: identical crash, identical stack shape, at the
  same point in the same unchanged code. Root cause not investigated (out of scope for an
  extraction chunk) — likely a Bootstrap version/build mismatch specific to this dev environment.
  Consequence, though, *was* made worse by wrapping the surrounding code in one function: because
  `base_admin.html` legitimately renders `{% block script %}` twice (documented Django behaviour —
  the same block name used twice in one base template renders its content at both locations), this
  crash previously killed *everything textually after it* in whichever of the two script-block
  copies actually had a populated DOM (cap editor's Enter-key shortcut, room counter, `initialise
  counts`, keyboard nav, walk-in registration, "over the shoulder" mode, table sorting,
  remove-signup) — on every load, for every user, always, since `isSuperuser` is always `true` here
  (`@panopticon_required`gates the whole view). Wrapped the modal-init block in `try { ... } catch
  (err) { console.error(...) }` so this one broken, pre-existing feature (the inline edit modal)
  stops taking the rest of the page's interactivity down with it. Verified via a live walk-in
  registration (fetch round-trip, DOM row insertion, count increment) succeeding end-to-end
  post-fix. Confirmed via `node --check`, the existing 52 `toolkit.inductions.tests` (unchanged,
  still pass), and the live page. The modal itself remains broken and is not fixed here — worth its
  own ticket.
- The double-block-script-rendering (`base_admin.html`) is itself a separate, much bigger,
  out-of-scope architectural question — noted here only so a future pass doesn't mistake the
  "`sessionDetail` referenced twice at two line numbers" console noise for something Chunk 9 caused.

Also found while testing: the dev container's `runserver` process caches which apps have a
`static/` subdirectory *at process startup* (Django's `AppDirectoriesFinder`). Since `inductions`
had no `static/` directory at all before this chunk, the newly-added
`inductions/static/inductions/{css,js}/` files 404'd until the container was restarted — collect­
static and the files being present on disk were both irrelevant; only a process restart picks up a
brand-new app-level static directory. Not a code bug, but worth remembering for any future chunk
that gives a previously-static-free app its first static file: restart the dev container after.

### Chunk 10: Tests — DONE 2026-09-08

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

**Strengthening the status-code-only tests — done 2026-09-08. Chunk 10 complete.** Re-measured
rather than trusting the original "102" figure (written before this session's new test files
existed, and before checking what each one actually claims): a script-based sweep for tests whose
*only* assertion checks `status_code` found the true number of genuinely weak ones is much smaller
than 102 once permission/method-not-allowed/404 checks are excluded — those are not weak, `assert
this specific status code` **is** the complete and correct claim for "logged out gets redirected",
"non-superuser gets 403", "GET on a POST-only endpoint gets 405", "disabled feature 404s". Strength-
ening those would just be padding. The real gap was narrower and sharper: 31 tests across 3 apps
that checked `status_code == 200` (or an equivalent success path) and nothing else, for a view
whose whole point is to render specific content, save something, or reject invalid input — exactly
the failure mode the original finding named (`test_bulletins.py`'s empty-title POST asserting 200
with no check that no `Bulletin` was created).

Two were real validation gaps with the same shape: `test_bulletins.py::test_post_with_empty_title_returns_form`
and `test_donations.py::test_add_action_with_missing_name_returns_form` both posted invalid data and
only checked "still 200" — neither confirmed the form actually rejected it (`assertFormError`) or
that no record was created. Both now check both. The other 29 were "page loads" smoke tests (`GET`
a view, check `200`, nothing else) — a broken template, wrong template, or empty context would
still pass. All 29 gained `assertTemplateUsed` (the cheapest test that actually distinguishes "this
page" from "some page"), plus context/content checks were free wins existed (`test_edit_views.py`'s
`test_invalid_date_ignored_not_500` now confirms the invalid date was *ignored* rather than just
not crashing; `test_printedprogramme_views.py`'s edit-view-loads test now checks the formset is
actually empty). No new tests added, no dead code found this time — every one of the 31 targets was
a real, reachable, currently-passing-for-the-wrong-reasons test. 1,359 tests passing throughout
(unchanged count — this was a strengthening pass, not an additions pass).

**Chunk 10 is now fully done**: all four sub-items (`labs` coverage, destructive bulk actions,
`toolkit_auth`, `volunteer_edit.py`, status-code-only tests) complete. Next: Chunk 11
(un-star `members/views`, split the two remaining god-sized files).

### Chunk 11: Un-star members/views, split what's god-sized — DONE 2026-09-08

**Part 1 — done.** Replaced `from ._common import *` across all eight `members/views/` modules
with explicit per-module imports, then deleted the quarantine block from `pyproject.toml`.
Mechanical method, close to what this section originally proposed but via `F821` rather than
`F405`: for each module, temporarily swap the star import for a comment, run
`ruff check --select F821` over the whole package, and read off exactly which names ruff reports
undefined — that's the module's real dependency list, mechanically derived rather than
eyeballed. Mapped each name back to its true source (django.*, toolkit.diary.models,
toolkit.members.forms, toolkit.members.models, toolkit.toolkit_auth) using `_common.py`'s own
import block as the source-of-truth map; the three names that genuinely originate in
`_common.py` (`logger`, `_render_admin_email`, `_notify_vols_admin_status_change`) are now
imported explicitly (`from ._common import logger, ...`) instead of via wildcard.

`_common.py` itself shrank from 194 to ~80 lines — its `__all__` re-export list (58 entries) and
the docstring describing the old wildcard pattern are both gone, since nothing does
`from ._common import *` any more. `members/views/__init__.py`'s own explicit re-exports (for
`urls.py`) were untouched — different, legitimate pattern, not this quarantine.

Verification: ruff 0 findings package-wide, black clean at 79, 1359 tests passing (unchanged
from before the change — this was a pure import-plumbing refactor, no behaviour change).
Commit `d619a090`.

**Part 2 — done, three sub-tasks run in parallel as forks sharing one working tree.**

- `diary/forms.py` (1,661 lines, ~34 form classes) → `toolkit/diary/forms/` package: seven
  topic submodules (`events`, `showings`, `templates`, `tags_roles_rooms`,
  `printed_programme`, `misc`, `site_config`), naming aligned with `diary/edit_views/` where a
  topic overlaps. `__init__.py` explicitly re-exports every public class/formset so both
  `from toolkit.diary.forms import X` and `import toolkit.diary.forms as diary_forms` call
  sites kept working unchanged. Verified 1:1 symbol parity old↔new via an AST diff (nothing
  lost or invented) and full `__all__` coverage. Same F821-driven import-derivation method as
  Part 1 — no copied header, no `_common.py` hub. Commit `3c80f3ed`.
- `inductions/views.py` (grown to 1,047 lines since this chunk was scoped; the original
  845-line/33-function estimate was stale) → `toolkit/inductions/views/` package: six topic
  submodules (`public`, `sessions`, `signups`, `export`, `access_needs`,
  `manage_settings`). Handled with extra care since this file carries two recent security
  fixes (the CSV formula-injection guard in `manage_export_csv`, and the client-side
  `escapeHtml()` XSS fix in `session_detail.html`, which the split didn't touch since it's a
  template) — both explicitly re-verified intact post-split, not just assumed. Function-name-set
  diff old↔new was empty. Commit `c084aede`.
- `member_views.py` (566 lines, 13 functions) — investigated what "half-done split" meant
  rather than assuming: the file itself was already coherent (one topic, Member CRUD/search,
  comparable size to the `volunteer_*.py` siblings), so the actual gap was structural
  asymmetry — one flat Member module sitting next to a packaged set of Volunteer modules, not
  internal bloat needing further fragmentation. Resolved by folding it in as-is:
  `toolkit/members/views/member_views.py`, alongside its volunteer siblings. `urls.py`,
  `views/__init__.py`'s re-export list, `test_members.py`'s import/`@patch()` target, and
  `ONBOARDING.md` all updated to match. No further sub-splitting — forcing one would have been
  exactly the "design for hypothetical future requirements" this pass argues against elsewhere.
  Commits `51588940`, `652d386c`.

**A git-history wrinkle, worth knowing if anyone bisects this range:** the three forks shared
one working tree and container (no isolation was requested), so `3c80f3ed` accidentally rode
along with a rename-in-progress from the concurrent `inductions/views.py` fork
(`inductions/views.py → inductions/views_old.py`, zero content diff — git tracked it as a
clean rename). `c084aede` then deleted `views_old.py` while adding the real package. Net effect
across the two commits is correct and the working tree was never broken at any commit boundary
that landed, but `3c80f3ed`'s diff alone contains a file that isn't otherwise explained by its
own message. Confirmed harmless: no orphaned files, no duplicate content, working tree clean.

**Final verification, run after all four sub-tasks landed:** 1,359 tests passing (unchanged
throughout — every sub-task was pure import/module-structure refactoring, no behaviour change),
ruff 0 findings repo-wide, black clean at 79 (312 files unchanged).

`seed_dev_data.handle()` (complexity 101, ~1,090 lines before the first helper) is lowest
priority — dev-only. Keep pushing its data into the TOML fixtures rather than restructuring the
Python.

### Chunk 12: Confirm the uplift landed — DONE 2026-09-08

Re-ran the Chunk 4 measurements (coverage, ruff, black, per-app complexity) at commit
`4691d28c`, then a second MiniMax M3 pass ($0.1099, 5 files) over the modules Chunk 11 changed
most, prompted specifically to judge whether the package splits themselves helped or just
reshuffled the code. Full before/after table and the spot-check write-up are in
`docs/QUALITY_BASELINE.md` — not duplicated here. Headline numbers:

- **Coverage 81.5% → 85.5%**, driven by Chunk 10's new tests, not Chunk 11's splits (which added
  zero tests — pure import plumbing).
- **Worst per-app complexity essentially unchanged** — expected and correct, since moving code
  between files doesn't reduce any function's branch count. Confirms Chunks 8 and 9 (still not
  started) are where the actual complexity reduction has to happen, not a sign the uplift
  underperformed.
- **1,359 tests, ruff 0, black clean.**
- **The MiniMax spot-check's verdict on Chunk 11's own splits was mixed, not a clean pass**: the
  `_common.py` un-starring got a clean bill, but three new `__init__.py` re-export layers
  (`members/views/`, `diary/forms/`, and by implication `inductions/views/`) were independently
  flagged as adding indirection for a single consumer (`urls.py`) without a real public API —
  the same shape as the wildcard-hub pattern Chunk 11 set out to remove, just less traceable
  about it than before, not more. `inductions/views/export.py`'s split was flagged as premature
  for a ~30-line one-view file. Recorded as a candidate for a future pass, not acted on here.
- **One real, pre-existing bug surfaced and verified** (not introduced by this pass, not fixed
  here — out of scope for a re-measurement chunk): `member_views.py`'s
  `unsubscribe_member_right_now` and `opt_in` both call
  `panopticon_required(unsubscribe_member)(...)` on their access-denied branch instead of
  wrapping themselves — a panopticon-level staff member without a magic key gets routed into the
  wrong flow. Predates this branch entirely (`git log -S` traces it to `512618d2`, feature
  9.74). Worth a follow-up ticket. A second claimed bug from the same pass (a
  `reverse(..., query=...)` call) was checked directly and does not exist in the current code —
  a reminder that MiniMax findings need verification before being trusted, same as Chunk 5/6's
  findings did.

**Next real chunk is 8 or 9**, not a renumbered continuation — both were skipped rather than
descoped, and Chunk 12's own measurement confirms they're still where the complexity payoff is.

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
| 2026-09-08 | 12 | `openrouter/minimax/minimax-m3` | 5 | $0.1099 |
| | | **Total** | | **$1.6870** |
