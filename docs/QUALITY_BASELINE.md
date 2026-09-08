---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Opus 5", "Claude Sonnet 5"]
status: "#ai-input"
---

# Quality baseline — 2026-09-08 (before), re-measured 2026-09-08 (after)

The before-picture for the quality pass tracked in [QUALITY_PASS.md](../QUALITY_PASS.md), and
the after-picture from Chunk 12. Both are dated and should be read as snapshots, not as living
documents — the "before" table is as of commit `19e65fc3`, the "after" table as of `4691d28c`.

**What actually landed between the two measurements: Chunks 10 and 11, not 8–11.** Chunk 8
(deduplicate) and Chunk 9 (extract inline JS/CSS) were never started — the "next chunk: 12"
decision in QUALITY_PASS.md's status table skipped them. So this before/after measures the
effect of "give untested apps their own tests" (10) and "split god-sized files into packages"
(11) only. That matters for reading the complexity row below: package-splitting doesn't reduce
any individual function's cyclomatic complexity, so a flat "worst complexity" number that barely
moves is not a failed uplift — it's confirmation that the complexity-reducing work (8–9) is
still queued, exactly as predicted when Chunk 12 was scoped.

**How to reproduce these numbers**, in order:

```bash
docker compose exec -T toolkit /venv/bin/coverage run --source=toolkit manage.py test --settings=toolkit.test_settings
docker compose exec -T toolkit /venv/bin/coverage json -o /tmp/coverage.json
docker compose exec -T toolkit /venv/bin/ruff check --select C901 --config "lint.mccabe.max-complexity=1" toolkit
docker compose exec -T toolkit /venv/bin/ruff check toolkit
docker compose exec -T toolkit /venv/bin/black --check toolkit
```

The complexity command is a one-off CLI override, not a change to the committed
`pyproject.toml` — it drops the gate's threshold to 1 for a single run so ruff reports every
function's cyclomatic complexity as a "violation," rather than only the ones already over the
committed ratchet (101). `radon` would give the same numbers with a friendlier report format,
but isn't installed anywhere in this project and wasn't worth adding for a one-off measurement.

---

## Per-app summary — before (2026-09-08, `19e65fc3`)

LOC excludes migrations (auto-generated, not maintained by hand). Coverage is statement
coverage from the full test-suite run, not branch coverage.

| App | Python LOC | Template LOC | Test coverage | Worst complexity |
|---|---:|---:|---:|---|
| `diary` | 21,330 | 11,865 | 91.0% | 19 (`edit_diary_list`, `edit_views/diary_overview.py`) |
| `members` | 9,558 | 4,887 | 88.0% | 20 (`edit_volunteer`, `views/volunteer_edit.py`) |
| `labs` | 6,471 | 5,030 | 76.8% | 9 (`donation_manage`, `views/donations.py`) |
| `util` | 4,654 | 0 | 17.5% | 101 (`handle`, `seed_dev_data.py` — dev-only, see note) |
| `inductions` | 3,554 | 2,666 | 73.3% | 10 (`handle`, `send_consent_renewal_reminders.py`) |
| `index` | 1,381 | 1,360 | 93.2% | 19 (`get_context_data`, `index/views.py`) |
| `mailer` | 1,286 | 80 | 94.8% | 11 (`send_mailout_to`, `mailer/sender.py`) |
| `audit` | 769 | 177 | 97.0% | 4 (`handle`, `purge_audit_logs.py`) |
| `operations` | 764 | 176 | 91.3% | 4 (`status`, `operations/models.py`) |
| `toolkit_auth` | 620 | 170 | 61.6%\* | 5 (`feature_required`, `decorators.py`) |
| `content` | 202 | 231 | 91.8%\* | — (no function over complexity 1 that isn't trivial) |
| **App subtotal** | **50,589** | **26,642**\*\* | | |
| **Repo total** | **51,738** | **27,772** | **81.5%** (21,788 statements) | worst overall: 101 |

\*\* The 1,149-line gap between the app subtotal and the repo total is `toolkit/*.py` files
that sit outside any app — `settings_common.py`, `settings_starandshadow.py`, `urls.py`,
`urls_flat.py`, `test_common.py`, the `docker_settings_*`/`devserver_settings.py` variants.
The template-LOC gap (1,130 lines) is `templates/` and `star_and_shadow_templates/` — the
shared base templates and S+S overrides that live outside any single app's `templates/` dir.

\* **`toolkit_auth` and `content` have zero dedicated test files** (`find toolkit/toolkit_auth
-iname '*test*'` and the same for `content` both return nothing) — the coverage numbers above
are entirely incidental, earned by other apps' tests calling through `feature_required` /
`panopticon_required` / the auth backend on their way to testing something else, or Wagtail
migrations executing `content/models.py` at test-DB setup. `toolkit_auth/backends.py`
(the actual `authenticate()` override) sits at only 50% specifically because nothing exercises
its failure paths — a bug in the email-or-username lookup logic could ship without any test
noticing, since no test asserts on that logic directly. This is the gap Chunk 10 names first.

Ruff: **0 findings**. Black: **clean** at line-length 79. Both confirmed together with the
coverage run above, same commit.

## Per-app summary — after (2026-09-08, `4691d28c`, Chunks 10–11 landed)

| App | Python LOC | Template LOC | Test coverage | Worst complexity |
|---|---:|---:|---:|---|
| `diary` | 21,555 | 11,877 | 91.1% | 19 (`edit_diary_list`, unchanged) |
| `members` | 10,507 | 4,889 | 94.0% | 20 (`edit_volunteer`, unchanged) |
| `labs` | 8,654 | 5,030 | 92.6% | 9 (`donation_manage`, unchanged) |
| `util` | 4,654 | 0 | 17.6% | 101 (`handle`, `seed_dev_data.py`, unchanged — dev-only) |
| `inductions` | 3,708 | 2,675 | 74.2% | 10 (`handle`, unchanged) |
| `index` | 1,381 | 1,360 | 93.2% | 19 (`get_context_data`, unchanged) |
| `mailer` | 1,286 | 80 | 94.8% | 11 (`send_mailout_to`, unchanged) |
| `audit` | 769 | 177 | 97.0% | 4 (`email_log`, `models.py` — was `handle`, still 4) |
| `operations` | 771 | 176 | 91.4% | 4 (`stale_commitment` — was `status`, still 4) |
| `toolkit_auth` | 885 | 170 | 80.7% | 5 (`_create_or_update_user` — was `feature_required`, still 5) |
| `content` | 202 | 231 | 91.8% | — (unchanged) |
| **Repo total** | **55,521** | **27,795** | **85.5%** (23,631 statements) | worst overall: 101 |

**Coverage: 81.5% → 85.5% (+4 points).** Driven almost entirely by Chunk 10's new tests, not by
the Chunk 11 splits (which are pure import-plumbing and added zero new tests). The two biggest
movers are exactly the two apps Chunk 10 targeted: `toolkit_auth` 61.6% → 80.7% (it went from
zero dedicated test files to its own suite) and `members`/`labs` climbing on the back of the
shopping/exchange/lost-and-found/edge-case/destructive-path test batches. `inductions` moved
least (73.3% → 74.2%) because Chunk 10 didn't scope tests there — it's still the largest
remaining coverage gap among user-facing apps.

**Worst complexity: essentially unchanged, as expected.** Every app's worst-function number is
either identical or names a different function at the same complexity — moving code between
files doesn't change any function's branch count. This is the confirmation Chunk 12 was scoped
to get: the Chunk 10–11 uplift improved test coverage and file-level navigability, but the
actual complexity reduction work (Chunk 8's deduplication, Chunk 9's inline-JS/CSS extraction,
both still not started) has not happened yet. Read the flat complexity row as "on track,
nothing to fix here" rather than "the uplift didn't work."

**LOC grew by +3,783 Python / +23 template lines, and that's expected, not scope creep.** The
three biggest jumps line up exactly with Chunk 10's test additions: `labs` +2,183 lines (the
shopping/exchange/lost-and-found/donations test batches), `members` +949 (volunteer_edit +
destructive-path + edge-case-user tests), `toolkit_auth` +265 (its first dedicated test file).
`diary` (+225) and `inductions` (+154) are almost entirely the `__init__.py` re-export
boilerplate from their Chunk 11 package splits, not new logic.

Ruff: **0 findings**. Black: **clean** at line-length 79. Tests: **1,359 passing** (was 1,136 at
the baseline measurement, 1,129 at session start — see QUALITY_PASS.md's spend/session log for
the per-test-batch breakdown).

---

## Chunk 12 spot-check: did the split help, or just make the code Claude-shaped differently?

A second MiniMax M3 pass, 5 files, $0.1099 total, over the modules Chunk 11 changed the most:
`members/views/_common.py`, `members/views/__init__.py`, `members/views/member_views.py`,
`diary/forms/events.py`, `inductions/views/export.py`. Prompted specifically to judge the
split's own quality, not just do a generic review. Full output in
`docs/QUALITY_PASS_RAW/chunk12_reviews/` (gitignored).

**The verdict on the splits themselves is mixed, and worth taking seriously rather than filing
under "known trade-off":**

- **`members/views/__init__.py` and `diary/forms/__init__.py`-style re-export layers got called
  out independently, on both files, as indirection with a single consumer (`urls.py`) that adds
  a "triple-edit hazard" (submodule, `__init__.py`, `urls.py` all need touching to add a view)
  without adding a real public API. This is the same shape as the `_common.py` wildcard-hub
  anti-pattern Chunk 11 explicitly set out to remove, just with the wildcard swapped for an
  explicit list — an improvement in traceability, not in indirection.
- **`inductions/views/export.py` split was flagged as premature** for a ~30-line, one-view file:
  "defensible only because it's the only download-shaped view in the package... tag as
  'justify by next view', not a permanent layout."
- **`members/views/member_views.py`'s relocation was judged cosmetic, not de-bloating**: nothing
  was extracted, nothing recoupled, the file is byte-for-byte the same content in a new
  location. Reasonable per QUALITY_PASS.md's own reasoning (no internal split was warranted),
  but confirms the fold-in didn't reduce complexity — only fixed the structural asymmetry it set
  out to fix.
- **`members/views/_common.py`'s post-un-starring state got a clean bill**: "no dead code beyond
  [one already-noted item]", the two remaining shared helpers "are both genuinely shared... the
  indirection earns its keep." This is the one file where the review confirms the split
  unambiguously helped.

**One real, verified, pre-existing bug surfaced, not introduced by this pass**: in
`toolkit/members/views/member_views.py`, both `unsubscribe_member_right_now` (line 366) and
`opt_in` (line 393) fall back to `panopticon_required(unsubscribe_member)(request, member_id)`
on the access-denied branch — wrapping and calling the *wrong* function (`unsubscribe_member`
instead of themselves). A panopticon-level staff member hitting either of those two views
without a valid magic key gets routed into the unsubscribe flow instead of theirs. Verified by
reading the code directly (not just trusting the model): confirmed present, and confirmed via
`git log -S` to predate this branch entirely — introduced in `512618d2` (feature 9.74,
2026-ish, restricting member PII to Panopticon), untouched by Chunk 11's relocation. Not fixed
here — out of Chunk 12's scope — but worth a follow-up ticket. (A second claimed bug, a
`reverse("search-members", query=...)` call, was checked and does not exist in the current
code — the model's claim there does not survive verification; not included above.)

**Read together with the metrics above**, this spot-check's real finding is that Chunk 11
delivered real value (per-file navigability, one clean removal of the wildcard-hub pattern) at
a real cost (three new `__init__.py` re-export layers, two of which are flagged as
under-justified) — not a wash, but not a pure win either. If a further pass ever revisits
`members/views/`, the two candidates the review agrees on are: drop the `__init__.py` re-export
layer in favour of `urls.py` importing submodules directly, and reconsider
`volunteer_pool_admin.py`'s split-by-size-not-cohesion grouping.

---

## Template debt

Not re-measured — reused from QUALITY_PASS.md's "Measured findings" section (2026-09-07),
which is the authoritative source. Reproduced here so the before/after in Chunk 12 doesn't
require cross-referencing two files:

| Template | Total | Inline `<script>` | Inline `<style>` | Actual markup |
|---|---:|---:|---:|---:|
| `diary/templates/edit_rota.html` | 2,161 | 1,039 | 894 | ~230 |
| `diary/templates/form_event.html` | 1,832 | 1,306 | 42 | ~480 |
| `labs/templates/labs/floorplan.html` | 1,222 | 721 | — | ~500 |
| `inductions/.../session_detail.html` | 957 | 649 | — | ~300 |

**7,535 lines of inline JavaScript** total, across these four templates alone, live where no
linter, test, or browser cache can reach them. See QUALITY_PASS.md Chunk 9 for the extraction
plan.

---

## Reading this table

- **`util`'s 17.5% coverage is not representative of hand-maintained code quality.** The app is
  dominated by `seed_dev_data.py` (919 statements, 0% covered, complexity 101) and two other
  dev-only management commands (`fetch_trailers.py`, `send_volunteer_digest.py`) that are
  never run under test because they're operator tools, not application logic. Excluding
  `seed_dev_data.py`, `fetch_trailers.py`, `check_media_dirs.py`, and `send_volunteer_digest.py`
  (all dev/ops tooling with no test-suite path to them), the remaining `util` coverage would be
  much closer to the rest of the codebase — this is a measurement artefact of what the app
  contains, not a hidden testing gap.
- **`labs` (76.8%) and `inductions` (73.3%) are the two real gaps** among user-facing apps.
  QUALITY_PASS.md's findings already name the specific untested surface:
  `bulk_anonymise_volunteers` / `bulk_delete_never_onboarded` in `members` (88% overall hides
  these), and `labs/views/shopping.py` (3 of 13 endpoints tested), `loft.py`, `area_photos.py`
  (no tests at all). Chunk 10 is scoped from this, not from the aggregate percentage.
- **102 tests assert only a status code**, per QUALITY_PASS.md's measurement — not visible in
  the coverage percentage at all, since a line executed by a weak test still counts as
  "covered." A high number here does not mean the corresponding behaviour is verified; treat
  coverage as a map of what runs, not of what's checked.
- **Complexity is a ratchet, not a target** (see `pyproject.toml`'s comment on
  `max-complexity`). The honest ceiling is 12; every function above that number is a Chunk 9/11
  candidate, not a bug to fix independently of that work.
