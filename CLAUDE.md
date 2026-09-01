# Claude Context — Cube Toolkit

## Orientation

This is the **Cube Toolkit** codebase — a Django app that manages events, members, and mailouts for the Cube Microplex cinema in Bristol. It also supports the Star and Shadow cinema via a separate settings layer.

Before doing anything else, read:
- [docs/ONBOARDING.md](docs/ONBOARDING.md) — project structure, apps, Django primer, how to run with Docker
- [docs/ARCHIVE/BRANCH_NOTES.md](docs/ARCHIVE/BRANCH_NOTES.md) — detailed audit of differences between the `master` and `s+s` branches

The current branch is **`master`** (Django 5.2 LTS, Wagtail 6.3, Python 3, no Celery).

---

## Repo layout: worktrees, not separate clones (as of 2026-07-28, revised 2026-09-01)

`~/code/sns-toolkit` is the single `.git` for every locally-relevant lineage of this codebase. Two sibling directories are **git worktrees** of this same repo, not separate clones (their `.git` is a file, not a directory):

| Directory | Branch | What it is |
|---|---|---|
| `~/code/sns-toolkit` | `sns_2026_overhaul` (usually) | The active rewrite. |
| `~/code/sns-production-mirror` | `production_snapshot_04_2026` | Rsync-based filesystem snapshot of the live server. Orphan history, five commits, no shared ancestry with the code lineages. `SECRET_KEY` in `devserver_settings.py` was scrubbed (`REDACTED_SECRET_KEY`) during import, so never touch that file's history without re-scrubbing first. |
| `~/code/sns-live-toolkit` | `cube_upstream_master` | Ben Motz's current upstream `cubetoolkit` `master`. Hash-identical to `BenMotz/cubetoolkit` on public GitHub, so it carries no exposure his own repo does not. |

### Remotes

| Remote | Points at | Public? | Notes |
|---|---|---|---|
| `origin` | `github.com/jdkram/sns-toolkit` | yes | Ours. |
| `homeserver` | freyja | no | Deploy target. |
| `upstream` | `github.com/BenMotz/cubetoolkit` | yes | Ben's published tree. Fetch freely. |
| `cube` | `toolkit@cubecinema.com:/home/toolkit/repo` | **no** | The Cube's own server. Read access granted by Marcus, May 2026. Slow: allow three minutes for a fetch. Fetches into `refs/remotes/cube/*` only. |

`cube` carries branches that exist nowhere else, currently `s+s-rebased` and `s+s-reunification`. Keep them as remote-tracking refs rather than local branches. They are Ben's unpublished, self-declared unreviewed work, so importing them is fine but publishing them is his call to make, not ours.

### The push guard

`.git/hooks/pre-push` (local only, not versioned) refuses any push to `origin` or `upstream` that would send commits reachable only from `refs/remotes/cube/*` or `production_snapshot_04_2026`.

It checks **content, not ref names**, because a name check is trivially defeated by `git push origin production_snapshot_04_2026:refs/heads/something-innocent`. Commits already reachable from `upstream/*` or `origin/*` are excluded as already public, which is why `cube/master` does not trip it. Pushes to `homeserver` are not checked.

It is a guard against accidents, not against intent: `--no-verify` bypasses it, and it lives only in this checkout. Re-create it after any fresh clone.

### Publishing rules

- **Never push `production_snapshot_04_2026` anywhere public.** It is a filesystem snapshot of a live server. This matters more once `jdkram/sns-toolkit` becomes a GitHub fork, because objects pushed into a fork network stay reachable from the network even after the branch is deleted.
- **Before importing a branch that is not already public somewhere, grep it for personal data you would be newly publishing.** Checked for `s+s-rebased` on 2026-09-01: same three settings files, same address, nothing new.
- Never run `git push origin --all`, `--mirror` or `-f` without checking which branches are included.

### The redaction procedure has been retired

A previous rule required cloning the `cube` remote to a disposable directory and running `git filter-repo` to strip `marcus@marcusv.org` before importing. That protected against an exposure Ben himself publishes: his `master` is public on GitHub, address included, at the same hash. The procedure cost real work and protected nothing, so it is gone, replaced by the lighter check above.

A correction to the earlier note in passing: `s+s+nosix` was described as "already correctly redacted" on public GitHub. It is not. Local `master`, `s+s`, `s+s+nosix` and `retheme-2023` are the redacted lineage; the copies on GitHub carry the real address and always have. Decision taken 2026-09-01: adopt the GitHub lineage locally, so the two agree and there is one canonical history per branch. Not yet executed; the four branches still hold the redacted hashes.

### Known and unfixed

- The same personal email appears as the git **author identity** on roughly 150 historical commits already public on GitHub. Fixing it means rewriting hashes on published branches, which is a separate and bigger decision.
- `toolkit/devserver_settings.py` has a hardcoded `SECRET_KEY`, already public on `master`, `sns_2026_overhaul`, `s+s` and `s+s+nosix`. Dev-only, but worth removing the hardcoded fallback at some point.
- On `sns_2026_overhaul` the address survives at tip in `CLAUDE.md` and `CURRENT_WORK.md`, quoted as part of the `vols_admin_address` incident write-up. Documentation of a real bug rather than live config, but it is still someone's address in a public repo.

### History of this layout

The original standalone directories (`sns-production-mirror-old`, `sns-live-toolkit-old`) were reviewed and deleted 2026-07-28. A restic snapshot of `~/code` was taken beforehand. Two further stray clones of `BenMotz/cubetoolkit` were found in `~/code/0archive` on 2026-09-01; the eight commits unique to them (your own 2026-02-17 dev-setup and seed-data work) are preserved as tag `archive/claudified-2026-02-17`.

---

## Django template comments — single line only

**Never write multi-line `{# ... #}` comments in Django templates.** Django's template engine does not strip them reliably when they span multiple lines, and the raw comment text leaks into the rendered HTML.

- ✅ `{# Short single-line comment #}` — safe
- ❌ `{# Multi-line\n   comment #}` — leaks into HTML output

If a comment needs more than one line, use multiple single-line `{# ... #}` tags, or put the explanation in a Python/view-layer code comment instead.

---

## Never use `.only()` on models with a custom `__init__`

Several models in this codebase cache field values in `__init__` for validation:

| Model | Cached fields |
|---|---|
| `EventTag` | `read_only`, `name`, `slug` |
| `Event` | (similar pattern) |
| `Showing` | (similar pattern) |
| `RotaEntry` | (similar pattern) |
| `Role` | (similar pattern) |
| `Member` | (similar pattern) |
| `Volunteer` | (similar pattern) |

Using `.only("pk", "some_field")` on any of these defers the cached fields. Accessing a deferred field inside `__init__` calls `refresh_from_db`, which constructs a new instance, which calls `__init__` again -- infinite recursion, one DB round-trip per frame. The page hangs until the stack overflows.

**Rule:** use `.values("pk", "some_field")` (returns dicts) instead. Access results as `t["pk"]`, not `t.pk`.

---

## Standing rule: keep docs/ in sync with the code

**After every code change, update the relevant docs.**

**Status tracking — one file only:**
- Bug fixes / features completed → mark ✅ + date in **[CURRENT_WORK.md](CURRENT_WORK.md)** (inline in the table, or add a row to the Done section). Do **not** also update TASKS.md.
- New features proposed → add to the appropriate domain file in [docs/tasks/](docs/tasks/) (see [docs/TASKS.md](docs/TASKS.md) for the index) using the next available `9.X` number and a sizing label (🟢 XS / 🔵 S / 🟡 M / 🟠 L / 🔴 XL / ⛔ XXL), and add a row to CURRENT_WORK.md.

**Spec — update when the system changes:**
- Data model changes → update [docs/SPEC.md](docs/SPEC.md) section 8 (data model) and ER diagram
- New external system dependencies → update [docs/SPEC.md](docs/SPEC.md) section 6 (external integrations)
- Workflow changes → update [docs/SPEC.md](docs/SPEC.md) section 4 (key workflows)
- Permission changes → update [docs/SPEC.md](docs/SPEC.md) section 2 (permission model)

Do not commit code changes without also committing the corresponding docs update in the same commit (or immediately following it).

---

## Git workflow: bundle and commit on your signal

**I will accumulate changes and commit when you ask me to.**

This gives you full control over batching related changes together and deciding the right moment to commit. When you suggest we should commit (e.g., "let's commit all this"), I will:

1. Display the files that will be staged
2. Show the proposed commit message(s)
3. Run `git commit` with your approval

If you want to adjust the commit message or split into multiple commits, just let me know.

---

## Versioning: bump VERSION on significant releases

The project uses CalVer (`YYYY.MM.N`). The canonical version is in [`VERSION`](VERSION) at the repo root.

**When to bump:** when a meaningful chunk of work is done and you'd want to know "what version was running when X happened". This is not every commit — it's at natural milestones: a feature shipped, a phase completed, a significant bug fixed.

**How to bump (I will prompt you at the right moment):**

1. Update `VERSION` — e.g. `2026.05.6`
2. Commit it: `git add VERSION && git commit -m "chore(release): 2026.05.6"`
3. Tag the commit: `git tag v2026.05.6`
4. Push the tag: `git push origin v2026.05.6` (and `git push homeserver` for the homeserver)
5. **Create a GitHub Release:** go to GitHub → Releases → Draft new release → choose the tag → paste release notes → Publish.

**Release notes source:** Use the completed items from [CURRENT_WORK.md](CURRENT_WORK.md) — the ✅ rows since the last release. Summarise in plain English for a non-developer audience. Format: one bullet per shipped feature or notable fix.

Full workflow documented in [docs/ONBOARDING.md — Releases and Versioning](docs/ONBOARDING.md).

---

## Live site investigation plan

An investigation plan covering compatibility with production data and three staging bug fixes is at:
`~/notes/Community/sns/sns-investigation-plan.md`

Also relevant: `~/notes/Community/sns/servers.md` for SSH aliases, server paths, and rsync/DB dump commands.

---

## Hosting/infrastructure decision pending (2026-08)

XtreamLab (who host the live site) have proposed a revised hosting and support
arrangement that would add a proper staging environment and standby mirror —
decision expected at a S+S meeting on 2026-08-04. Contract terms and costs are
sensitive and are **not** recorded in this repo; see
`~/notes/Community/sns/meeting-prep-2026-08-04.md` for the current state.

Once staging access exists, expect a "low-hanging fruit" phase of small,
high-impact ports from this branch into production — the deletion-logging fix
(9.159, already shipped here — see [CURRENT_WORK.md](CURRENT_WORK.md)) is the
current first candidate, since it needs no further dev work, only deployment.

---

## Current task: Port S+S-specific features from the `s+s` branch

The `s+s` branch was the Star and Shadow production branch but ran Django 2.2 (EOL). We have started fresh from `master` (which is far more modern) and ported the S+S-specific functionality across. Initial Docker setup and basic seed data are complete; focus is now on porting remaining features.

The `s+s` branch is available locally for reference (`git checkout s+s`, or inspect files with `git show s+s:path/to/file`). See [docs/ARCHIVE/BRANCH_NOTES.md](docs/ARCHIVE/BRANCH_NOTES.md) for full details on branch differences.

**For current task status, what's done, and what's next, see [CURRENT_WORK.md](CURRENT_WORK.md).** That is the single source of truth — do not track status anywhere else.

---

## Docker setup on `master`

**How master's Docker works** (different from what was built on `s+s`):

- Multi-stage Dockerfile: `base` → `build` (compiles wheels) → `run` (lean final image)
- Non-root user (`toolkit:toolkit`)
- Runs via gunicorn with `--reload` (hot-reload enabled via `GUNICORN_RELOAD=1` in docker-compose.yml)
- Entrypoint: `containerconfig/tk_run.sh` — accepts `gunicorn` or `mailerd` as argument
- Settings file: `DJANGO_SETTINGS_MODULE=toolkit.docker_settings_starandshadow` (env var; no symlink needed)
- Static files: collected at container start by `tk_run.sh` (not baked into image)
- Source code: bind-mounted from host at runtime — container always sees your local files
- Requirements split into `requirements/base.txt`, `requirements/dev.txt`, `requirements/docker.txt`

**Edit/reload cycle — tell the user which command to run after making changes:**

| Change type | Command needed |
|---|---|
| Python files (views, models, forms, management commands) | None — `runserver` auto-reloads |
| Templates (`.html` files) | None — `runserver` picks them up immediately |
| CSS or JS (static files) | None — `runserver` serves static files directly from source |
| New Python dependency (requirements files) | `docker compose up --build -d` |
| Dockerfile or `tk_run.sh` | `docker compose up --build -d` |

After telling the user what you changed, always state which of the above applies. For almost all day-to-day changes the answer is "just refresh your browser."

**To build and run (first time, or after Dockerfile/dependency changes):**
```bash
docker compose up --build -d
```

**To create initial users and seed sample data after first boot:**
```bash
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
```

`configure_toolkit_users --password` creates all demo accounts non-interactively. Accounts created:

| Username | Tier | Password |
| --- | --- | --- |
| `admin` | Panopticon (superuser) | `password` |
| `programmer`, `programmer2` | Programmer | `password` |
| `volunteer` … `volunteer5` | Volunteer (rota only) | `password` |

To reset passwords on already-existing accounts, add `--force-password`:
```bash
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password --force-password
```

Omit `--password` for production — it will prompt interactively for each new account and skip any that already exist.

**To run tests — ALWAYS inside the container, never locally.**

> ⚠️ **Do not attempt to run tests outside the container.** The project dependencies (including the `fixtures` test library, `mysqlclient`, and several C extensions) are only installed inside the Docker image. There is no local venv, and `tox` is not installed on the host. Every attempt to run tests locally will fail. Do not try to create a venv, install deps, or invoke `tox` or `python manage.py` directly on the host. The one and only way to run tests is:

```bash
docker compose exec toolkit /venv/bin/python3 manage.py test --settings=toolkit.test_settings
```

To run a specific test module or class:
```bash
docker compose exec toolkit /venv/bin/python3 manage.py test toolkit.diary.tests.test_edit_views --settings=toolkit.test_settings
```

---

## Key file locations

| Purpose | File |
|---|---|
| S+S venue config (feature flags, VENUE dict) | [toolkit/settings_starandshadow.py](toolkit/settings_starandshadow.py) |
| S+S Docker dev settings | [toolkit/docker_settings_starandshadow.py](toolkit/docker_settings_starandshadow.py) |
| S+S Docker prod settings | [toolkit/docker_settings_prod_starandshadow.py](toolkit/docker_settings_prod_starandshadow.py) |
| Shared base settings | [toolkit/settings_common.py](toolkit/settings_common.py) |
| Container entrypoint | [containerconfig/tk_run.sh](containerconfig/tk_run.sh) |
| Dev docker compose | [docker-compose.yml](docker-compose.yml) |
| S+S-specific templates | [star_and_shadow_templates/](star_and_shadow_templates/) |
| Current work / status / roadmap | [CURRENT_WORK.md](CURRENT_WORK.md) |
| System specification | [docs/SPEC.md](docs/SPEC.md) |
| Logging: what's logged where, email log lines | [docs/LOGGING.md](docs/LOGGING.md) |
| Feature specs & design rationale | [docs/TASKS.md](docs/TASKS.md) (index) → [docs/tasks/](docs/tasks/) (domain files) |
| Current version string | [VERSION](VERSION) |

---

## Code Search

Use `semble search` to find code by describing what it does or naming a symbol/identifier, instead of grep:

​```bash
semble search "authentication flow" ./my-project
semble search "save_pretrained" ./my-project
semble search "save model to disk" ./my-project --top-k 10
​```

Use `semble find-related` to discover code similar to a known location (pass `file_path` and `line` from a prior search result):

​```bash
semble find-related src/auth.py 42 ./my-project
​```

`path` defaults to the current directory when omitted; git URLs are accepted.

If `semble` is not on `$PATH`, use `uvx --from "semble[mcp]" semble` in its place.

### Workflow

1. Start with `semble search` to find relevant chunks.
2. Inspect full files only when the returned chunk is not enough context.
3. Optionally use `semble find-related` with a promising result's `file_path` and `line` to discover related implementations.
4. Use grep only when you need exhaustive literal matches or quick confirmation of an exact string.

