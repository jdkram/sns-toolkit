---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Sonnet 5"]
status: "#ai-input"
---

# Quality rubric

A checkable standard for this codebase, synthesised in Chunk 6 of
[QUALITY_PASS.md](../QUALITY_PASS.md) from two sources:

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

**How to use this:** Chunks 8–11 (dedup, template extraction, tests, un-starring
`members/views/`) should check new and touched code against the rules below rather
than re-paying for external review per file. When a rule and the code disagree, fix
the code, not the rule — unless the disagreement reveals the rule was wrong, in which
case fix this file and say why in the commit.

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

---

## Unfixed findings, ranked

Findings severe enough to fix directly rather than fold into a rubric rule. None
touched by this chunk — Chunk 6 is synthesis only.

### Needs its own out-of-band fix (security), not the normal chunk cadence

1. **Stored XSS, `inductions/manage/session_detail.html`** — already documented in
   QUALITY_PASS.md's Chunk 5 section and flagged to Jonny directly (2026-09-08).
   Still open. Not repeated in full here; see that entry.
2. **Open redirect via `HTTP_REFERER`, `labs/views/bulletins.py:199,213`** — new,
   found by this synthesis. `request.META.get("HTTP_REFERER")` goes straight into
   `redirect()` with no `url_has_allowed_host_and_scheme` check. Same vulnerability
   class as `diary/edit_views.py:2609`, which `REVIEW_2026_OVERHAUL.md` flagged and
   which is already fixed — this second instance was missed by that review because
   it's in `labs`, not `diary`. Low severity in the same way the fixed one was
   (authenticated volunteers only), but it's the same one-line fix
   (`url_has_allowed_host_and_scheme`) and shouldn't wait for Chunk 8.
3. **Stored XSS, `diary/templates/form_showing.html:20`** — `_rooms_json()`
   (`diary/edit_views/showings.py:212`) uses plain `json.dumps()`, embedded via
   `{{ rooms_json|safe }}` inside a `&lt;script&gt;` block. Room names are
   programmer/panopticon-editable, and this is the exact anti-pattern
   `daterange.py`'s `safe_json()` helper already exists to prevent — this call site
   just doesn't use it. See rubric rule R13.
4. **Stored XSS, `members/templates/volunteer_bulk_record.html:198`** —
   `{{ selected_qual.name|escapejs }}` is embedded in an HTML string literal that's
   later assigned via `.innerHTML =` (line 138). `escapejs` doesn't escape
   `&lt;`/`&gt;`/`&amp;`, so a qualification name containing a script tag survives into
   the DOM. Same root cause as R13 — the wrong filter for the actual sink.
5. **JS-context XSS, `diary/templates/edit_event_template_detail.html:522`** —
   `onclick="return confirm('Delete template \'{{ event_template.name }}\'?')"` has
   no `|escapejs`. Django's default HTML-escaping isn't sufficient here: the browser
   HTML-decodes the attribute value before treating it as JS source, so an escaped
   `'` still breaks out of the string once decoded.
6. **CSV formula injection, `inductions/views.py:488`
   (`manage_export_csv`)** — volunteer-supplied `first_name`/`last_name` written raw
   via `csv.writer`, no guard against a leading `=`/`+`/`-`/`@` (Excel/Sheets
   formula-execution-on-open). The same hand-rolled CSV pattern exists in
   `members/views/volunteer_export.py` and `diary/edit_views/reports.py` — already
   tracked as duplication in this file's Measured Findings section — so check all
   three for the same gap when Chunk 8 unifies them into a shared `csv_response()`
   helper, not just this one.

Items 3-6 are new confirmed findings from the Kimi sweep (2026-09-08), same severity
class as items 1-2 — not fixed yet, need the same direct flag rather than waiting
for the normal chunk cadence.

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
    labs-undertested finding in `docs/QUALITY_BASELINE.md` to the specific gap.

---

## What this rubric does not cover

Chunk 9 (inline JS/CSS extraction) and Chunk 7 (feature-scope decision) are
structural, not code-quality questions this rubric can check — see their own
sections in QUALITY_PASS.md.
