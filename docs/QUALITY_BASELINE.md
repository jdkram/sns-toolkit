---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Opus 5"]
status: "#ai-input"
---

# Quality baseline — 2026-09-08

The before-picture for the quality pass tracked in [QUALITY_PASS.md](../QUALITY_PASS.md).
Re-measured at Chunk 12 once the uplift (Chunks 8–11) has landed, so every number here is
dated and should be read as "as of commit `19e65fc3`", not as a living document.

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

## Per-app summary

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
