# Archive

Historical reference documents. Content was accurate at time of writing but is no longer actively maintained.

| File | Contents |
|------|----------|
| [BRANCH_NOTES.md](BRANCH_NOTES.md) | Audit of differences between the `master` and `s+s` branches — written during the 2026 migration project |
| [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md) | Record of the 2026-03-31 staging DB migration from the `s+s` branch to `master` — one-off, done |
| [PIPELINE_IMPL.md](PIPELINE_IMPL.md) | Original implementation plan for the programming pipeline (9.2) — superseded by the shipped code |
| [MAINTAINABILITY_PASS_2026_06.md](MAINTAINABILITY_PASS_2026_06.md) | Plan and log of the June 2026 maintainability pass (attic deletion, god-module splits, migration squash). All chunks done 2026-06-28 |
| [QUALITY_PASS_2026_09.md](QUALITY_PASS_2026_09.md) | Plan, measured findings, and chunk-by-chunk log of the September 2026 quality pass (ruff/black/CI, external-model review, security fixes, dedup, inline-JS extraction). Complete 2026-09-08. Its lasting outputs are `pyproject.toml`, the CI/pre-commit gates, and [docs/QUALITY_RUBRIC.md](../QUALITY_RUBRIC.md) |
| [QUALITY_BASELINE_2026_09.md](QUALITY_BASELINE_2026_09.md) | Before/after measurements for that pass: per-app LOC, coverage, complexity |
| [QUALITY_LABS_SCOPE_2026_09.md](QUALITY_LABS_SCOPE_2026_09.md) | Decision record: all seven `labs` mini-tools kept, each behind its own Site Settings flag |
