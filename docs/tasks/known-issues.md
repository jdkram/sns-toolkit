# S&S Toolkit — Known Issues

Bugs and current system limitations.

**For work status:** [CURRENT_WORK.md](../../CURRENT_WORK.md)  
**For feature specs:** see the other files in [docs/tasks/](./)

---

## Browser verification checklist (2026-09-10) — done 2026-09-12

Two commits landed 2026-09-10 with zero browser verification (no Claude-in-Chrome connection
that session): `b072e4d0` (CSS systemic review — Bugs AZ, BA, BB, BC) and `eed5301f` (nav
parity — Bug BD). Worked through live on 2026-09-12 once a browser connection was available
(Docker dev server, logged in as both `programmer` and `admin`):

- **Bug BB** (`<strong>` weight): confirmed via computed styles — `<strong>` renders at
  `font-weight: 700` against the body's `500` on a public programme page. Genuinely bolder now.
- **`g` → `v` keyboard shortcut**: confirmed on `/programme/` — `g` shows nav-key badges
  (`Programme` = `p`, `Past events` = `v`, no collision), and `v` correctly navigates to "Find a
  past event". Bug BD's `data-nav-key` collision fix holds.
- **Toolkit navbar + Ctrl+K palette** (Bug BD): confirmed "Past events" on the navbar directly
  and "Maintenance schedule" in the Community dropdown; both also found via the palette
  (clicked the visible ⌘K button — plain `Ctrl+K` is intercepted by Chrome's own omnibox
  shortcut in this environment, so use the button or `Ctrl+/`).
- **Feature-flag gating** (Bug BD): toggled `building_map_enabled` off in Site Settings — "Building
  Map" disappeared from both the navbar dropdown and the palette immediately; re-enabled
  afterwards to restore the dev environment's normal state. Flash message on the settings save
  ("Site configuration updated") was clearly legible.
- **Console errors**: none on `/toolkit/` (`base_admin.html` + `fragment_navmenu.html`) across a
  fresh load.
- **Bug BA (mobile hamburger z-index)**: **not live-tested**. `resize_window` did not actually
  change the viewport in this session's browser environment (`window.innerWidth` stayed at
  2560 regardless of the requested size), so no real narrow-viewport click test was possible.
  Verified statically instead: `layout.css`'s z-index scale has `--z-nav-toggle: 600` above
  `--z-sidebar: 500`, which is the documented fix and is consistent with the button painting on
  top. Whoever next has a working mobile-width browser (or real device) should still do the
  actual tap-to-open/tap-to-close check before treating this as fully closed.
- **Bug AZ (Windows/Firefox scrollbar)**: still unverified — no such machine available in this
  session either. Unchanged from 2026-09-10.

Bug entries BB, BC, and BD's "not browser-verified" lines below are removed on the strength of
the checks above (BC's flash-message legibility was incidentally confirmed too, via the Site
Settings save). Bug BA keeps a narrowed caveat (z-index reasoning confirmed, live tap-test still
outstanding). Bug AZ is unchanged.

## Current bugs

**Bug BE** — Dashboard cards spill sideways on mobile, taking the navbar hamburger with them ✅ fixed 2026-09-21

**Symptom.** On a phone, the Open jobs card's "Urgent" / "Soon" / claimed-by columns sat
outside the card's right edge. The whole page scrolled horizontally, and the navbar's
hamburger button was off-screen until you scrolled sideways to reach it. The finance review
page (`/diary/edit/events/finance-review/`) showed the same spill from its card header's row
of badges and buttons.

**Root cause.** Two separate widenings, one shared consequence. On the dashboard,
`.shift-row td:first-child { white-space: nowrap }` was written for the date-led cards, but
applies to every card — including the three whose first column is free text (Open jobs,
Shopping, Maintenance), so a long job title could not wrap and forced the table wider than
its card. On the finance review page, the card header's inner `.d-flex` had no `flex-wrap`,
so five badges and buttons stayed on one line. The hamburger is a consequence, not a separate
bug: when anything overflows horizontally, a mobile browser widens the layout viewport to
fit, and `position: fixed` is sized against that viewport, so the `fixed-top` navbar grows
wider than the screen and its right-aligned toggle goes off the visible area.

**Fix.** Root causes: `nowrap` is now an opt-in `.shift-when` class on the date cells rather
than a positional `td:first-child` selector, and the finance review header's inner flex row
wraps. Guards against the class of bug, in `base_admin.html` so they cover every admin page:
`min-width: 0` on columns/cards/card bodies/headers so they can shrink below their content,
`overflow-wrap: anywhere` inside cards, flex rows inside cards wrapping by default under
576px (`.flex-nowrap` opts out), and `.card > .card-body { overflow-x: auto }` as a last
resort. Separately, the film readiness tables got an explicit `min-width` inside their
existing `.table-responsive` wrappers — the wrapper alone let the browser squeeze six columns
to one word per line rather than scrolling. Written up as rule C9 in
[../CSS_CONVENTIONS.md](../CSS_CONVENTIONS.md). Not browser-verified: pages confirmed to
render via the test client, but nobody has looked at them on a phone yet.

**Third time this has happened.** Bug W (2026-04-28, `.showing-meta` with `flex-wrap: nowrap`
on the rota) and Bug AO (still open, public pages at ≥1000px) are the same failure with
different causes, and Bug W's entry already identified the fixed-navbar consequence. That is
why this round's fixes are mostly guards in the shared base template rather than three more
one-page patches.

**Bug AZ** — `seed_dev_data` reruns can duplicate a showing (dev tooling only) — open, found 2026-09-21

**Symptom.** Re-running `seed_dev_data` on an already-seeded dev DB occasionally adds a
second `Showing` for an event on a date it already has, half an hour after the first
(`19:00` and `19:30`). Three event/date pairs on the current dev DB show it, one of them
from the new `programme_2026.toml` pool and three from the older `events.toml`/
`recurring.toml` pools, so the mechanism predates the 2026-09-21 seed rebuild. Intermittent:
two consecutive reruns during the review added nothing.

**Root cause.** `_seed_showing` calls `_find_free_slot` (`seed_dev_data.py`) to resolve room
contention *before* the `Showing.objects.get_or_create(event=..., start=...)` that is meant to
make the step idempotent. On a rerun, `_room_bookings` has been preloaded from the existing
`RoomBooking` rows, so the showing's own prior booking now counts as a conflict; the slot
shifts 30 minutes, and `get_or_create` keyed on the shifted datetime no longer matches the
existing row and creates a second one. Order-dependence in the driving querysets (several
have no explicit `order_by`) decides whether any given rerun trips it.

**Why it is not fixed here.** Dev-tooling only, no production code path, and the fix
(look up an existing showing for that event and date before consulting the room schedule,
rather than after) changes seeding behaviour enough to want its own verification pass with a
`--wipe` reseed. The 2026-09-21 seed rebuild widens exposure rather than causing it: four
weekday film pools plus 20 weeks of historical programme now contend for the same two rooms.

**Bug AR** — Approved queue events vanish from the diary — nothing bridges "approved" to "confirmed" ✅ fixed 2026-09-09

**Symptom.** A programmer proposes an event, it goes through the Monday-meeting programming queue, gets marked active (`make_active` action) — and then it disappears. It's on the internal calendar somewhere, but not on the diary a programmer actually checks day to day, and there's no message telling them why or what to do next.

**Root cause.** `programming_status` (draft/proposed/active/rejected — the queue's state machine) and `Showing.confirmed` (whether a booking is public-facing — a separate state machine gated by `Event.terms_satisfied()`) are independent. `update_event_programming_status`'s `make_active` branch only flipped `programming_status`, then redirected back to the programming queue (`next` posted by the queue template) — a page that only lists draft/proposed/rejected events, so the just-approved event had already vanished from it, with only a flash message and no link to what remained. The Event Hub (`view_event_privatedetails.html`) already had a "terms outstanding" / "N unconfirmed" completeness-bar indicator; the gap was purely that the programmer was never sent there.

**Fix (task 9.162's scope only, not 9.163/9.164):** `update_event_programming_status` now checks, for `make_active`/`approve_at_meeting`, whether the event still has an unconfirmed future showing or unsatisfied terms after the status change. If so, it overrides `next` and redirects to the Event Hub with a warning message instead of back to the queue, reusing the existing completeness-bar UI rather than building anything new. When nothing is outstanding (showing already confirmed, terms satisfied), it still honours `next` and returns to the queue as before. `toolkit/diary/edit_views/site_config.py`, regression tests in `toolkit/diary/tests/test_programming_queue.py`. The notification-email piece (9.164, blocked on 9.163's `created_by` field) is intentionally still out of scope.

**Bug E** — Homepage list view layout broken by volunteer event info ✅ investigated 2026-09-09, not reproducible

Re-checked against current code: `view_showing_index.html`'s list-view `is_volunteer`/`hide_in_programme`/`private` conditionals are exhaustive and mutually exclusive (every iteration hits exactly one branch, no dangling unclosed tags), and `programme.css`'s `.list`/`.day`/`.sameday` rules render a coherent hanging-indent layout. Live-browser check as a logged-in volunteer (which is the only path that can render internal/private showings in this view) showed a clean list with no visible misalignment. The original report's own wording was hedged ("likely pushing... etc.") — reads as a report against an earlier version of this page, since fixed by unrelated CSS work, rather than a bug in current code. Re-open with a screenshot if it recurs.

**Bug F** — Grid view volunteer banners aesthetics ✅ investigated 2026-09-09, not reproducible — superseded by a different design

The "banner" element this bug describes doesn't exist in the current codebase — no `.banner` class anywhere in `programme.css` or `view_showing_index.html`. Internal/private events in the grid are now styled as a whole-card tint + border (`.showing.showing-internal`, `programme.css:476-487`, explicitly commented "Volunteer-only (internal) event cards"), not a separate banner strip that could fail to fill its cell. This bug's premise no longer applies.

**Bug B** — Wagtail `translation_key` column overflow ✅ fixed 2026-02 (this file just hadn't been updated to match)

On MariaDB, `wagtailcore_page.translation_key` was `varchar(32)` but Wagtail 6 generates 36-character UUIDs. Creating CMS pages throws `DataError`. Fixed via migration `0013_widen_page_translation_key.py`, widened to `varchar(36)` with an `INFORMATION_SCHEMA` guard so it's a safe no-op on fresh installs.

**Bug K** — Rota `&amp;` display glitch ✅ fixed 2026-03-02

**Root cause:** jeditable's `loaddata` option is NOT a value-transform callback. It provides extra POST parameters for a `loadurl` AJAX request. We don't use `loadurl`, so any function assigned to `loaddata` is silently ignored. The correct option is `data`: when set to a function, jeditable calls it with `$(element).html()` (raw innerHTML, Django-escaped) and uses the return value to populate the editor.

**Fix in `edit_rota.js`:** use `data: function(value) { ... }` with a regex decode of Django's 6 escape sequences (order matters — `&amp;` first):
```js
data: function(value) {
    return value
        .replace(/&amp;/g,  '&')
        .replace(/&lt;/g,   '<')
        .replace(/&gt;/g,   '>')
        .replace(/&quot;/g, '"')
        .replace(/&#x27;/g, "'")
        .replace(/&#39;/g,  "'");
}
```

**Server response must stay unescaped plain text** (`return HttpResponse(showing.rota_notes, ...)`). After save jeditable calls `$(self).html(result)`; the browser's innerHTML getter re-encodes `&` → `&amp;`, so the next `data` call sees `&amp;` and decodes correctly. If you add `escape()` to the response, jeditable's `.html()` double-encodes it (`&amp;` → `&amp;amp;`) and a spiral begins.

**Bug M** — Calendar edit view: simultaneous events in the same timeslot overwrite each other ✅ fixed 2026-04-04 (this file just hadn't been updated to match)

On days with 6+ events scheduled at the same time, FullCalendar rendered later events on top of earlier ones rather than tiling them side-by-side, because events with no explicit `end` had zero duration and FullCalendar's overlap detection never triggered. Fixed by `Showing.end_time` (`toolkit/diary/models/showing.py:264-273`): returns `start + Event.duration` when set, or a default 2-hour fallback when not, so every event now has a real end time for FullCalendar to tile against. Separately, the calendar was later migrated from FullCalendar 3 to FullCalendar 6 entirely (`feat(calendar): migrate from FC3 to FC6 with resource timeline views`).

**Bug L** — Wheelchair-inaccessible role strikethrough too subtle 🟢 XS

**Bug L** — Wheelchair-inaccessible role strikethrough too subtle ✅ N/A — model changed

The strikethrough indicator this bug described no longer exists. Wheelchair accessibility is now an affirmative ♿ badge on roles confirmed accessible, not a strikethrough on inaccessible ones — the ambiguity this bug reported can't recur under the new model.

**Bug O** — Volunteer rota: event-name links redirect to login ✅ fixed 2026-03-03 (this file just hadn't been updated to match)

`edit_rota.html` now gates the showing-title link on `perms.toolkit.write`/`is_superuser`: programmers/superusers go to the Event Hub, volunteers go to the public showing view instead of bouncing off a permission check.

**Bug P** — Event Tags page: pre-Bootstrap styling and confusing UX ✅ fixed 2026-03-03 (this file just hadn't been updated to match)

Ported to a Bootstrap 4 card layout; the drag handle is now hidden on non-promoted tags (was previously shown but inert), and footer help text explains the "in menu" vs. drag-order distinction.

**Bug Q** — Roles page: pre-Bootstrap styling ✅ fixed 2026-03-03 (this file just hadn't been updated to match)

Ported to a Bootstrap 4 card + table layout, with a read-only badge and a highlighted new-row state.

---

**Bug R** — Mobile: public-site sidebar always visible, not gated by hamburger ✅ fixed 2026-03-03 (this file just hadn't been updated to match)

Fixed as designed: the sidebar starts off-screen (`left: -240px; z-index: 200`) at all widths, with a desktop-only `@media (min-width: 1000px)` block making it always-visible there; `site-common.js` toggles a `.sidebar-open` class to bring it on-screen on mobile. (The rules originally landed in `site_custom.css`; that file was later folded into `layout.css` during an unrelated CSS consolidation — same fix, current location.)

---

**Bug S** — Login page: nav bar overlaps form on mobile; style inconsistent with admin ✅ fixed 2026-03-03 (this file just hadn't been updated to match)

Went with Option B: `star_and_shadow_templates/base_login.html` is a minimal logo-only base template with no navigation at all. Login, logout, and all four password-reset templates now extend it instead of `base_public.html`, so the overlap and the style-inconsistency issue are both moot.

---

**Bug T** — Admin toolkit: mobile navbar overflow and layout issues ✅ fixed 2026-03-03 (this file just hadn't been updated to match)

All three sub-issues fixed in `base_admin.html`: brand image capped at `max-width: 120px`, body padding reduced to `3.5rem 0.5rem` on ≤576px, and the rota controls' date inputs shrink to `6em` on ≤640px.

---

**Bug U** — Rota: excessive left indentation wastes horizontal space on mobile ✅ fixed 2026-03-03 (this file just hadn't been updated to match)

`edit_rota.html`'s `@media (max-width: 640px)` block removes `ul.rota`'s left padding and reduces `.showing_rota_notes`/`.event-links` margin to `0.5em`.

---

**Bug V** — Tags/Roles admin: content overflows horizontally on narrow screens ✅ fixed 2026-03-03 (this file just hadn't been updated to match)

**V1** (Tags page): `overflow-x: auto` added to `.card-body` in `edit_event_tags.html`. **V2** (Roles page): the roles table in `form_edit_roles.html` wrapped in `<div style="overflow-x: auto;">`.

**Bug AV** — Induction session detail: the Panopticon "edit signup" modal never initialises ✅ fixed 2026-09-09

**Root cause, finally found (two compounding bugs):** `session_detail.html`'s `{% block script %}` was nested *inside* its own `{% block body %}` override (`{% block body %}...{% block script %}...{% endblock %}{% endblock %}`), while every ancestor template (`base_admin.html`, `templates/base.html`) treats `script` and `body` as separate sibling blocks. Because Django resolves a block by name wherever that name's tag physically appears anywhere in the inheritance chain, this produced two real bugs at once: (1) the whole resolved script block — jquery, bootstrap, the command palette, `session_detail.js`, and the inline `sessionDetail(...)` call — rendered **twice**, verified via `render_to_string(...).count("session_detail.js") == 2`; and (2) far more importantly, `{% block script %}`'s *real* position is dictated by `templates/base.html`, which places it in `<head>` — so the entire script, including the inline call that queries `#edit-modal` and the walk-in-registration form, executed **before `<body>` (and those elements) existed in the DOM at all**. `document.getElementById('edit-modal')` returned a valid element (IDs still resolve pre-body-parse in some cases) but in a DOM state `bootstrap.Modal`'s constructor couldn't handle cleanly, hence `_config` being undefined inside `_initializeBackDrop`. The original bug write-up's guess (`{% block script %}` "appears twice in `base_admin.html`") was close in spirit but wrong in the specific file — `base_admin.html` and `base.html` each define it exactly once; the duplicate came from `session_detail.html` itself.

**Fix:** `toolkit/inductions/templates/inductions/manage/session_detail.html` — closed `{% block body %}` before opening the (now sibling, not nested) `{% block script %}`; wrapped the `sessionDetail({...})` call in `document.addEventListener('DOMContentLoaded', ...)`, matching the pattern already used by `programming_queue.html` and several other admin templates. Verified live: modal opens correctly pre-filled with signup data, walk-in registration form expands, zero console errors. Regression test: `toolkit/inductions/tests/test_flows.py::Capacity::test_manage_detail_script_block_not_duplicated`.

**Bug AW** — `unsubscribe_member_right_now` and `opt_in` route access-denied users into the wrong view ✅ fixed 2026-09-09 (was actually dead code, fixed anyway for clarity)

Both views in `members/views/member_views.py` called `panopticon_required(unsubscribe_member)(...)` on their access-denied branch instead of wrapping themselves — a real-looking bug, but tracing the actual code paths shows it was unreachable: `_check_access_permitted_for_member_key` returns `True` (skipping the `panopticon_required(...)` branch entirely) whenever `request.user.has_perm("toolkit.write")` is `True`, and Django's `PermissionsMixin.has_perm` unconditionally returns `True` for any active superuser *before* consulting the permission itself. Since `panopticon_required` demands `is_superuser`, the only user who could ever reach the mis-wrapped `func(request, ...)` call already satisfied `has_perm` at the top of the function and never got there. So this specific miswiring never changed behaviour for any real user — the observable symptom in the original write-up doesn't occur. Fixed anyway (`unsubscribe_member_right_now`/`opt_in` now wrap themselves, not `unsubscribe_member`) since it's a one-line, zero-risk clarity fix that removes a footgun for future readers, and would matter the moment `panopticon_required` ever changes to a non-superuser-bypassing check. Predates the 2026 rewrite (`git log -S` traces it to feature 9.74).

**Bug AX** — Structured-cost-terms placeholder has never shown its default text ✅ fixed 2026-09-09

`diary/js/form_event.js` read `DEFAULT_TERMS_PLACEHOLDER` from a template variable (`DEFAULT_TERMS_TEXT`) that no view or context processor ever set — confirmed by checking `settings_common.py` (where `DEFAULT_TERMS_TEXT` genuinely exists, but as a Django *setting*, not template context) and `diary/context_processors.py` (no reference to it at all). Fixed by adding `"DEFAULT_TERMS_TEXT": settings.DEFAULT_TERMS_TEXT` to both context dicts `EditEventView` builds for `form_event.html` (`toolkit/diary/edit_views/events.py`, GET and POST-validation-error paths), matching the pattern every sibling context value already follows. Regression test: `toolkit/diary/tests/test_edit_event.py::EditEventView::test_default_terms_placeholder_is_populated`.

**Bug AZ** — Left-hand nav shows a spurious horizontal scrollbar on platforms with non-overlay scrollbars 🟡 fixed in code 2026-09-10, unverified on real Windows/Firefox

**Symptom (as reported):** on a Windows PC in Firefox, the left-hand sidebar nav showed a scrollbar problem. Not reproducible here — this workstation only has overlay scrollbars (Linux/Mac), which is exactly why this class of bug hides in dev.

**Root cause (reasoned from the CSS, not confirmed live):** `#sidebar` (`layout.css`) is a fixed, scrolling box — `overflow-y: auto; height: 100vh`. Its children `#site-nav` and `.nav-wrap` were both given an explicit `width: var(--sidebar-width)`, i.e. exactly as wide as the *parent's own* box. Per the CSS overflow spec, `overflow-y: auto` with `overflow-x` left at its default `visible` forces `overflow-x` to compute to `auto` too — one axis can't scroll while the other stays visible. So the moment the nav's content is tall enough to need a vertical scrollbar, that scrollbar (on a platform where it takes up real layout space, i.e. not macOS/Linux overlay scrollbars) narrows the sidebar's content box. The children are still hard-set to the sidebar's *full* width, now wider than the shrunk content box, so they overflow horizontally too — a second, horizontal scrollbar appears inside the nav. Windows' default (and Firefox's) non-overlay scrollbar is the common case where this becomes visible; a long enough nav (e.g. more links for a Panopticon/programmer login) is what triggers the vertical scrollbar in the first place, which is presumably why it wasn't spotted in casual dev testing with a shorter nav.

**Fix:** `layout.css` — `#site-nav` and `.nav-wrap` now use `width: 100%` (tracks whatever space is actually available in the parent's content box) instead of a hardcoded copy of `--sidebar-width`. Added `overflow-x: hidden` on `#sidebar` itself as a defensive backstop — nav content should never need to scroll sideways, so clipping is the safe failure mode, not a second scrollbar. **Not verified against a real Windows/Firefox instance** — no such machine available here, and headless Chromium's overlay scrollbars can't reproduce the platform behaviour this bug depends on. Re-open/confirm-closed with a screenshot from that platform when available.

**Follow-up, 2026-09-10:** a full CSS systemic review (see [docs/CSS_CONVENTIONS.md](../CSS_CONVENTIONS.md)) traced *why* this kept happening — `#sidebar`/`#site-nav`/`.nav-wrap` geometry was declared three separate times in `layout.css` (a base rule, a `1000px`-query redeclaration, and a later "runtime behaviour" block that silently won on several properties without the earlier two being removed). Consolidated into one authoritative "Sidebar / nav geometry" section, computed styles unchanged except one discovered dead-code case: `.nav-wrap`'s desktop `padding-top` said `42px` in three breakpoint rules, but a later unconditional rule always won and 30px is what's actually been rendering — kept as-is (flagged in-file) rather than silently "restoring" 42px. Same live-verification caveat applies: not browser-tested.

**Bug BA** — Mobile hamburger button becomes unclickable once the sidebar drawer is open ✅ fixed 2026-09-10

**Symptom:** on mobile (<1000px), tapping the hamburger opens the sidebar drawer. To close it again by tapping the same button — the obvious, expected gesture — nothing visibly happens for a mouse/touch user with no other affordance in view.

**Root cause:** `#mobile-menu-btn` (`layout.css`) and `#sidebar` share the same (root) stacking context — neither's ancestors (`.grid`, `.navigation-wrap`, `.mobile-wrap`) isolate one from the other with their own `z-index`. At mobile widths `.grid` has no `margin-left` offset (that's desktop-only), so `.navigation-wrap`/`#mobile-menu-btn` sit at the same top-left screen position the opened `#sidebar` slides into. `#mobile-menu-btn`'s z-index (`var(--z-nav-toggle)` = 100) was lower than `#sidebar`'s (`var(--z-sidebar)` = 500), so the sidebar painted on top of the button and intercepted the tap. A swipe gesture on `.black_overlay` (`site-common.js`) offered an alternate close path, and the button stayed keyboard-focusable throughout (z-index doesn't affect tab order), so this wasn't a total dead-end — but for a mouse/touch user without knowledge of the swipe gesture, tapping the visible-looking-clickable spot did nothing. Found via an independent CSS review (MiniMax M3 via OpenRouter, 2026-09-10), cross-checked against the actual DOM structure (`base_public.html`) and `site-common.js` before accepting it — the model's own framing ("no way to close it") overstated the case since the swipe fallback exists, but the core defect (the button visually and functionally covered for click/tap) was confirmed real.

**Fix:** `layout.css` — reordered the z-index scale so `--z-nav-toggle` (600) sits above `--z-sidebar` (500), not below it. The hamburger button now stays on top and clickable/tappable regardless of drawer state. **Partially verified 2026-09-12**: the z-index ordering itself was confirmed live in the running dev CSS (600 > 500, matching this fix), but a real narrow-viewport tap-to-open/tap-to-close test still hasn't happened — that session's browser tooling couldn't actually resize the viewport (`window.innerWidth` stayed fixed regardless of the requested size). Still needs a genuine mobile-width or real-device check.

**Bug BB** — `<strong>`/`<b>` render with zero visual weight difference from body text ✅ fixed 2026-09-10

**Root cause:** `layout.css` set `b, strong { font-weight: 500; }` and, separately, `body { font-weight: 500; }` — identical numeric weight. Any editorial emphasis (event descriptions, article copy) rendered indistinguishable from surrounding text. Found by the same MiniMax review pass; confirmed by grep (both declarations verified at their cited lines) before accepting.

**Fix:** `layout.css` — `b, strong` now set to `font-weight: 700`. The site's primary body font (`Roboto Mono`, loaded via the Google Fonts link in `base_public.html`) only has weights up to 500 fetched, so 700 will render via the browser's default synthetic-bold algorithm rather than a true bold face — a real visual distinction either way, and strictly better than the prior complete invisibility. `Source Code Pro` (used for `.copy p`/`#site-nav`) does have a genuine 700 weight already loaded, so that context gets a true bold. **Browser-verified 2026-09-12**: computed styles on a live `/programme/` page confirmed `<strong>` at `font-weight: 700` against the body's `500`.

**Bug BC** — `messages.css` warning colour fails contrast; unrelated units bug found alongside it ✅ fixed 2026-09-10

**Important correction to how this was first reported:** the same MiniMax review flagged all three of success/error/warning as failing contrast, on the assumption `messages.css` renders on the site's pink `--colour-brand-bg` (`#e3cae3`) — it doesn't. `messages.css` only loads on `base_admin.html`-derived (internal/admin) templates (confirmed via grep across every template that references it), never on `base_public.html` pages, and `base_admin.html` has a plain white page background (confirmed by its own in-file comment). Recomputed against the real background: only the warning colour genuinely fails (`#FF7E00` on white ≈ 2.55:1, below even the 3:1 large-bold-text threshold that applies to this 16pt bold text) — success (≈5.14:1), error (≈4.00:1, meets the applicable 3:1 threshold), and info (≈11.5:1) all already pass. Lesson for next time: check which template actually loads a stylesheet before asserting what background it renders against — this applies to both the reviewing model and to Claude's own initial acceptance of the flagged finding without that check.

**Also found alongside it:** `font-size: 16pt` — points are a print unit with no defined relation to a user's browser font-size preference on screen; every other stylesheet in this codebase uses `em`/`rem`.

**Fix:** `messages.css` — `font-size: 16pt` → `1.333rem` (equivalent rendered size at default browser settings, but a relative unit). `li.warning`'s colour changed from `#FF7E00` to `#856404` (≈5.49:1 on white), reusing the amber already established site-wide for warning states (`edit_rota.css`, `form_event.css`) rather than inventing a sixth ad hoc colour. Success/error/info left unchanged since they already pass. **Incidentally browser-verified 2026-09-12**: a Site Settings save triggered a live success flash message, clearly legible on `base_admin.html`'s white background — the warning/error/info variants weren't individually triggered that session, but the shared template/CSS path is confirmed working.

**Bug BD** — Sidebar, toolkit navbar, and command palette had drifted apart — several items present in one and missing from the others ✅ fixed 2026-09-10

**Symptom (as reported):** "Past events" showed in the public sidebar but not in the toolkit's top navbar.

**Root cause:** there are three independently hand-written navigation surfaces — `fragment_navmenu.html` (sidebar), the `<nav>` block in `base_admin.html` (toolkit navbar), and `window.TOOLKIT_COMMANDS` in the same file (the Ctrl+K command palette) — with no shared data source. Design decision established while investigating (see [docs/NAVIGATION.md](../NAVIGATION.md)): the sidebar is deliberately a leaner subset for public-page browsing; the navbar and palette are meant to be the complete toolkit set and must mirror each other exactly. Auditing all three against that rule found:

1. **"Past events"** missing from the navbar and palette despite sitting behind the identical `feature_perms.diary_read` gate as "Diary" in the sidebar — a plain omission when it was added to one template and not the others.
2. **"Maintenance schedule"** missing from the navbar's Community dropdown and the palette, present in the sidebar's Noticeboard dropdown.
3. **Six `site_config.*_enabled` feature flags** (`building_map_enabled`, `shopping_list_enabled`, `lost_and_found_enabled`, `collectives_enabled`, `donations_enabled`, `jobs_board_enabled`) gated correctly in the sidebar but left ungated in the navbar and/or palette — not a security hole (the views themselves enforce `@_feature_enabled_or_404`) but a link that 404s the moment a site admin disables the feature, since the nav item itself doesn't know to disappear.
4. **A `data-nav-key` bug found along the way:** the sidebar used `"p"` for both "Programme" and "Past events". `keyboard-nav-public.js` selects by `data-nav-key`, and jQuery's `.attr()` on a multi-element match returns only the first DOM match — so the `g → p` shortcut could only ever reach "Programme"; "Past events" was silently unreachable by keyboard. Also found: the command palette listed "Rota vacancies" twice, once unconditionally and once correctly gated on `feature_perms.rota_vacancies`.

**Fix:** added the missing items and feature-flag gates to whichever surface(s) lacked them (`toolkit/index/templates/base_admin.html`, both the navbar and the palette); changed "Past events"'s key to `v` in all three surfaces (sidebar, navbar, palette) to resolve the collision and keep the shortcut consistent across surfaces; removed the duplicate "Rota vacancies" palette entry. `docs/NAVIGATION.md` records the design decision and a maintenance checklist so this doesn't silently drift a third time; all three files now carry a one-line pointer comment to it. **Browser-verified 2026-09-12**: `g` → `v` correctly jumps to "Find a past event" with no collision against "Programme" (`p`); "Past events" and "Maintenance schedule" both confirmed present on the toolkit navbar and in the Ctrl+K palette; toggling `building_map_enabled` off in Site Settings removed "Building Map" from both the navbar dropdown and the palette simultaneously, confirming the feature-flag-gating fix.

**Bug AY** — Findings from the September 2026 review sweeps ✅ 13 of 14 fixed 2026-09-10, 1 investigated and closed as not-a-live-bug

Was a list of 14 small catalogued findings, kept together so they weren't lost. All addressed in one pass, each with a regression test and `ruff`/`black`/full-suite verification (1,274 tests, all green) — but **not browser-tested**, consistent with everything else logged that day.

1. ✅ `EventTag.delete()`/`Role.delete()` now return `(0, {})` (Django's documented shape) instead of a bare `False` on the read-only-refusal path.
2. ✅ The induction template-preview test-send now reports an error (naming the bad placeholder) instead of silently falling back to the raw unformatted template and claiming success.
3. ✅ `manage_mark_policy_updated`'s version bump and `notify_policy_change()` call are now one `transaction.atomic()` block — `notify_policy_change()` genuinely needs the bump already committed to query who's outstanding, so the two calls couldn't simply be reordered; wrapping them means a failed send rolls the bump back too, so a retry starts from the same version instead of inflating it further on every failure.
4. ✅ `_passes_level` now explicitly checks all three `PERMISSION_LEVEL_CHOICES` values and fails closed (denies everyone, logs a warning) for anything else, instead of falling through to `user.is_superuser`.
5. ✅ `floorplan.js` and `session_detail.js` now assert their URL-sentinel templates actually contain the expected sentinel before relying on it, throwing a clear error naming which template broke instead of silently building a dead URL that 404s far from the actual cause.
6. ✅ `MailoutJob.do_sending()`'s progress percentage is now clamped to 100 — the `+1` nudge (so 0 sent shows 1%, not a stalled-looking 0%) was pushing the final batch to 101%, normally masked by `do_complete()` but visible if a job died first.
7. ✅ `send_mailout_to()` now self-heals a blank `mailout_key` (regenerates and persists one) before building unsubscribe/edit links, rather than silently sending a link that can't work.
8. ✅ `mailerd`'s per-job loop now catches anything `run_job()` doesn't handle itself (extracted to `_run_job_safely()`), marks just that job failed, and keeps the daemon running — an unhandled exception used to kill the whole daemon, not just the one job.
9. **Investigated, not a live bug.** `jobs_list`/`jobs_table` do have different hardcoded defaults, but the checkboxes that drive `jobs_table`'s polling live in the *parent* template (`jobs-list.html`), outside the `<table>` that gets swapped on each poll, so `hx-include='input[type="checkbox"]'` faithfully round-trips whatever the checkboxes are actually set to on every request. The two defaults only diverge if `jobs_table` is hit standalone with no query params at all (direct/API access) — never in the real polling flow. Left as-is rather than "fixed" in a way that would have broken the working uncheck-to-hide toggle (HTML checkboxes send nothing when unchecked, so "explicitly off" and "no default" are indistinguishable at the HTTP layer).
10. ✅ `mailout`'s POST-invalid branch now re-parses `days_ahead`/`copy_days_ahead` from `request.POST` (falling back to site-config defaults), matching the GET branch, so a failed-validation resubmit no longer resets both number inputs to blank.
11. ✅ `VolunteerForm.clean_collectives` now filters on `active=True` when re-adding a volunteer's existing invite-only collectives, matching the visible field's own queryset — a since-deactivated invite-only collective no longer gets silently re-added forever.
12. ✅ `TrainingRecordForm` now only narrows `training_type` choices when the instance's own current value isn't the disabled one — a volunteer's existing record of a since-disabled training type stays editable instead of failing validation outright.
13. ✅ `Volunteer.save()`'s portrait cleanup now goes through `self.portrait.storage.delete(name)` instead of `os.unlink(path)`, using `.name` (the storage-relative key) rather than `.file.name` (which only happens to be a real filesystem path on local storage) — works on any storage backend, not just local. (While fixing this, found and left alone a separate, narrower quirk: `__original_portrait` isn't refreshed after a delete within the same in-memory instance, so a second `.save()` on that same Python object without reloading won't detect a further portrait change. Harmless under the normal one-instance-per-request lifecycle every view here actually uses; not touched since it's out of scope for this fix and reloading the instance already sidesteps it.)
14. ✅ `Volunteer.save()`'s `User.is_active` toggle is now inside the same `transaction.atomic()` block as the volunteer save itself — a crash between the two writes used to be able to leave a suspended volunteer still able to log in (or, on reinstatement, the reverse); now both commit or neither does.

Structural, not a bug, left alone: the `members/views/`, `diary/forms/` and `inductions/views/` packages each re-export every name through `__init__.py` for a single consumer (`urls.py`). An independent review flagged this as indirection without a public API. Reasonable to collapse to direct submodule imports in `urls.py` at some point; not urgent.

---


## 8. Current limitations and known gaps

These are real limitations in the current system that a rewrite should address.

### 8.1 Rota is disconnected from volunteers
`RotaEntry.name` is free text. Volunteers are not linked to their rota slots.
Consequences:
- Can't email everyone signed up for a showing
- Can't see a volunteer's rota history
- Typos in names go undetected
- No way to confirm a volunteer is still active

**Solution spec — volunteer FK on RotaEntry** 🟡 M (~12–16h)

Add `RotaEntry.volunteer = ForeignKey(Volunteer, null=True, blank=True, on_delete=models.SET_NULL)`. Nullable so: (a) existing entries without a match keep `volunteer=None`, (b) external hires (task 9.22) stay as `volunteer=None` permanently.

Implementation steps, in order:

1. **Migration**: add the nullable FK column.
2. **Port name coercion from s+s** (`edit_views/` `edit_rota_entry` view): when a non-superuser submits a non-empty rota slot, ignore the typed text and set `rota_entry.volunteer = request.user.volunteer`. Superusers retain free-text mode. This must land *before* the backfill migration, otherwise the backfill data is polluted with arbitrary strings.
3. **Backfill migration**: case-insensitive name match over existing `RotaEntry.name` values → `Volunteer.member.name`. Skip and log: entries with ambiguous matches (two volunteers share a name); entries with no match (typos, anonymised volunteers). This is best-effort.
4. **GDPR anonymisation update** (`volunteer_views.py:592`): primary path becomes `RotaEntry.objects.filter(volunteer=v).update(volunteer=None, name="")`. Keep the existing text-match sweep as fallback for legacy entries where the FK was never set.
5. **Pronouns tooltip update** (`edit_views.py:1380`): currently builds a name→pronouns dict and does a text lookup. Post-FK, entries with `volunteer` set go direct to `entry.volunteer.member.personal_pronouns`. Dict fallback remains for legacy entries.
6. **Display**: `edit_rota.html` and `view_rota.html` currently render `entry.name`. Post-FK, prefer `entry.volunteer.member.name` when FK is set.

**Design questions to answer before starting:**

1. **Name field retention**: keep `RotaEntry.name` as a separate field (used for external hires and legacy display), or derive it from the FK when set? Keeping it is simpler but creates two sources of truth. The safest path: keep the field, write it on sign-up from `volunteer.member.name`, and accept that it drifts if the member later changes their name.
2. **Superuser auto-link**: if a superuser types a name matching a volunteer, should the system attempt to link the FK? Convenient but adds a lookup on every save.
3. **Existing coercion gap**: master currently accepts any text from any user (coercion was never ported from s+s). Porting coercion should be a separate PR *before* the FK migration, so the backfill starts from a clean baseline.

**Unblocks**: 9.25 (tap-to-sign-up), 8.10 (volunteer workload view), "my schedule" view, reliable email to showing sign-ups, reliable GDPR erasure.

### 8.2 Volunteer induction is entirely manual ✅ Largely addressed (2026-09-09 audit; built earlier)

**Built:** the `inductions` app. Capacity-limited sessions, a public sign-up form
with GDPR consent and configurable custom questions, `.ics` calendar links,
check-in and walk-in registration on the day, no-show marking, timed purge of
pending and no-show sign-ups, a separate access-needs request form routing to
1:1 sessions, CSV export, and bulk `Member` + `User` + `Volunteer` creation from
the attendees, with a duplicate check on email and name. Gated behind
`InductionsSettings.inductions_enabled`, default off. Full description in
[SPEC.md §4.2](../SPEC.md).

The audit-trail complaint in the original wording no longer holds:
`InductionSignup.checked_in_by`, `InductionSession.created_by` and the per-volunteer
log line at account creation together answer "who inducted whom".

**Still open:**

1. **Not deployed.** Production runs the `s+s` branch, which has no `inductions`
   app, so the Google Form and copy-paste process described above is still what
   actually happens at Star and Shadow. Everything here is untested against real
   users.
2. **No mailing-list notification on the induction path.** `_create_volunteer_from_signup`
   (`inductions/views/signups.py`) creates the records directly and never calls the
   `vols_admin_address` notification that `/volunteers/add/` fires via
   `members/views/_common.py`. Someone inducted this way never generates a "please
   add to the mailing list" email, so they are invisible to whoever maintains
   Simplelists. Worse than the manual path it replaces, because bulk creation can
   drop a whole cohort silently. Compounds 8.5 below.
3. **Off by default**, which is correct as a shipping default but means the flow
   is easy to forget exists.

### 8.3 Volunteer self-service is partial
Volunteers can log in, view the rota, and sign up for slots via an
interactive click-to-edit interface at `/diary/edit/rota/`. This is gated by
the `diary.change_rotaentry` Django model permission.

**Name coercion (S&S branch only, not yet on master):** when a volunteer
clicks a slot and submits any non-empty text, the server ignores what was
typed and instead saves `request.user.volunteer.member.name` — i.e. the
logged-in user's own name. This prevents volunteers from writing each other's
names into slots. Submitting an empty value clears the slot. Any volunteer
with the permission can clear any slot, including one filled by someone else
— there is no ownership check on deletion. Superusers (Panopticon) bypass the
coercion and can write any text freely.

This coercion logic exists on the `s+s` branch but has not yet been ported
to `master`, where the rota edit view currently accepts and saves whatever
text is submitted verbatim.

Editing a volunteer's own profile (`/volunteers/N/edit/`) requires
`toolkit.write` (Panopticon level) — there is no self-editing exception in
the current code.

There is no "my schedule" view — a volunteer cannot see a filtered list of
only the showings they are signed up for.

### 8.4 No reserve/standby slots
If someone drops out of a rota role, there's no mechanism for reserves. This
is handled informally (e.g. messaging the volunteers list).

### 8.5 Email list is managed externally
The link between "volunteers in the Toolkit" and "members of the Simplelists
mailing list" is entirely manual. There is no synchronisation.

A compounding problem: the volunteer list and the mailing list are two
separate systems with no shared identifier, but in practice one person's
presence on a training-specific mailing list (e.g. the bar volunteers list)
is often managed as a side-effect of their induction. When someone attends a
bar induction, they are added to the bar mailing list by the person running
the session — but this is a manual step that depends on whoever ran the
session remembering to do it. There is no record in the toolkit of which
lists someone is on.

Consequences:
- A volunteer who is bar-trained may not be on the bar mailing list if
  their induction was not followed up correctly
- If someone leaves and re-joins, they may not be re-added to specialist
  lists during their return induction, unless whoever runs it explicitly
  checks
- Someone may want to stop receiving emails from a list (e.g. bar) while
  remaining active in that role — but there is no clean way to distinguish
  "unsubscribed from list" from "no longer qualified"
- Over time, mailing lists accumulate former volunteers who have never been
  removed — making them less useful and noisier

### 8.6 Rota view is a wall of text
The rota view shows all events in a date range with all their role slots and
rota notes. There's no filtering, grouping, or visual hierarchy. Large rota
notes dominate the view.

### 8.7 No programming pipeline / approval process ✅ Partially addressed (2026-06-05)

**MVP delivered:** `Event.programming_status` (draft/proposed/active/rejected) + `Event.programming_notes` + programming queue view at `/diary/edit/programming-queue/`. Programmers can propose events for Monday meetings; queue shows pending items; quick approve/return/skip actions for Programmer+. See task 9.113 for full spec.

**Still open:** no Finance Collective threshold flag, no etiquette guide link, no TMDB integration. See §9.2 for the full pipeline roadmap.

~~Events go straight from "created" to "confirmed" without any formal approval step. Proposed events are reviewed in Monday meetings (often added on to meetings that are primarily about other things), but there's no standard process for them hitting the system first.~~

### 8.8 Training records are too rigid to model real role requirements
The current training record system tries to fit all role qualifications into a
single model: a logged event with a trainer name, a date, and a role. Records
expire after 12 months and must be re-logged. This overhead means records are
not maintained, and as a result the system is not used as a gate on role
sign-up at all.

The deeper problem is that the real qualification requirements (see rule 13)
are fundamentally different in kind, and a single model cannot represent them:

- **Induction-granted certificates** (food hygiene level 1) are delivered
  in-house as part of the monthly café induction. The gate is the induction
  itself — a boolean, like bar. The level 1 certificate is an outcome of
  attending, not something obtained separately.
- **External certificates** (food hygiene level 2) need a record of the
  certificate itself — issuing body, expiry date — not an internal training
  log. Expiry genuinely matters here and should be surfaced.
- **Internal tiered training** (projectionist levels) needs a progression
  model, not a flat list of records. Level 2 implies level 1; re-logging
  after 12 months makes no sense for a skill that doesn't expire.
- **Informal shadow-based progression** (sound/tech) should not be
  formalised at all. A lightweight "this volunteer is comfortable with this
  role" flag, set by the volunteer or a coordinator, is sufficient.
- **Induction gates** (bar) are binary — you have had the induction or you
  haven't. A single boolean per volunteer is the right model, not a
  timestamped log.
- **Nomination processes** (keyholder) are social and governance decisions,
  not training events. The system should record the outcome (this person is a
  keyholder) without trying to model the process that led there.

A rewrite should model these as distinct types rather than forcing them
through a single `TrainingRecord` schema. Hard gates (bar induction, food
hygiene cert) can block sign-up. Soft signals (sound/tech comfort flag) can
inform but not block. Keyholder status is a property of the volunteer record,
not a training record at all.

It's worth noting a real world pain point caused by this: Community Kitchen log their food hygiene level 2 certificates, which were agreed by policy to need refreshing every 2 years. Jonny wrote a spreadsheet for logging these, but this was never widely adopted in a way that would have been much easier if a culture of recording training was baked in from the start, and the toolkit had a frictionless ready-baked solution, as opposed to the (rather snazzy, if I do say so myself) google sheet that highlights when people are close to needing refreshers.

### 8.9 Training records expire silently
There's no notification or dashboard view highlighting volunteers whose
training has lapsed or is about to lapse. (This is a secondary issue given
8.8 — solve the friction problem first.) See 8.8 example at the end of Community Kitchen certs.

### 8.10 No view of volunteer workload
There's no way to see how many hours or shifts any given volunteer has
committed to, or to spot volunteers who are over-stretched or disengaged. Or invite dormant volunteers to re-induct (or want to be removed from the system, helping with good GDPR compatible processes?).

### 8.11 Room booking model is too simple for multi-room events
A `Showing` has a single optional `room` field. This works for a simple
screening in one room, but many events at S&S require multiple rooms at
different times within the same event — for example:

- Venue access from 4pm for general setup
- Cinema booth from 6pm for tech and AV prep
- Cinema itself from 7pm to 9pm for the event proper

The current system has no way to express this. The workarounds in use are:

1. **Create multiple events** — programmers book each room as a separate diary
   entry, cluttering the programme with fake events and disconnecting the rota
   from the real event.
2. **Create multiple showings of the same event** — slightly better, but the
   programme then shows the same event listed multiple times at different
   times, which is confusing publicly and internally.
3. **Do nothing** — the room bookings are informal or forgotten, leading to
   undetected clashes when two events assume they have access to the same
   space at the same time.

There is also no clash detection: the system does not warn when two confirmed
showings overlap in the same room.

### 8.12 Collectives are not modelled in the toolkit

The Star and Shadow operates through a network of informal working groups and
collectives — Bar Collective, Programming Collective, Technical Collective,
and various others — which self-assemble around a shared interest and operate
with significant autonomy. These are not captured anywhere in the toolkit.

**Current state:**

- Groups communicate primarily through mailing lists managed in
  [Simplelists](https://simplelists.com/). Creating or administering a list
  requires knowing someone who has Simplelists admin access — a small and
  informally defined group. There is no self-service route.
- There is no central directory of which collectives exist, what they do, or
  who is in them. This is sometimes intentional: groups may prefer not to
  be publicly findable.
- There is one collective listed in the info pages via Wagtail, accessible from the public site: Community Kitchen. A solution could have a "public copy" blurb about the collectives which would massively help prospective volunteers get a sense of how the cinema works, and if they'd like to join. Collectives that people might not assume operate out of a cinema - Community Kitchen, print room, library - might all benefit from being more visible, and we might get new folks approaching us for inductions because they're interested in those aspects.
- A volunteer wanting to contact, say, the Tech Collective has no
  in-system way of discovering who is in it or how to reach them. They must
  ask around in person or via the general mailing list.

**A specific pain point — new programmers and keyholders:**

A newly onboarded programmer must arrange keyholding cover for their event.
Keyholders are an informal group of long-standing trusted volunteers; there is
no list in the toolkit, and no automated way to request one. In practice:

- The programmer must know (or be pointed to) individual keyholders by name
- They make contact directly, often via personal messages or the general list
- Keyholders agree or decline based on personal availability and their
  relationship with the programmer

This friction might not be entirely accidental. Having to personally approach
keyholders — and earn their willingness to vouch for a showing — is a
lightweight form of community vetting. Any feature that automates this away
entirely should be considered carefully. The right response may be to make the
*list* of keyholders visible in the toolkit (so new programmers know who to
approach) while leaving the actual agreement as a human interaction.

**What the toolkit could usefully do:**

- Expose a read-only directory of active collectives and their public contact
  points (e.g. mailing list address), where the collective has opted in to
  being listed
- Allow a Role to be flagged as `keyholder_capable`, making it easy to surface
  that list without building a full collectives model
- Note: full collective membership management (join requests, mailing list
  sync, governance) would be a large feature (🔴 XL or ⛔ XXL) and is not
  recommended as an early priority

### 8.15 Frontend library debt — legacy and EOL dependencies

Several vendored and CDN-referenced frontend libraries are outdated, some
critically so. Audited February 2026.

#### 🔴 Critical — CVEs / confirmed EOL

| Library | Version in use | Issue |
| --- | --- | --- |
| CKEditor | 4.7.3 | ✅ resolved. Replaced with Quill 2.0.3 (vendored). `HtmlTextarea` widget re-pointed to `js/lib/quill/quill.js` + `css/lib/quill.snow.css`; `htmltextarea.html` rewritten. Old `static_common/js/lib/ckeditor/` directory deleted. |
| jQuery (public site) | 2.1.3 via Google CDN | ✅ resolved. Replaced CDN reference with locally vendored `jquery.min.js` (3.5.1) in both `templates/base_public.html` and `star_and_shadow_templates/base_public.html`. No external dependency, no EOL version. |
| Google Fonts (all templates) | HTTP URL | ✅ resolved. Fixed `http://` → `https://` in `base_admin.html` (live request) and removed dead IE8 conditional comment blocks containing `http://` from all three base templates. |

#### 🟠 High — Abandoned or no longer receiving security patches

| Library | Version in use | Issue |
| --- | --- | --- |
| jQuery UI | 1.11.0 (2014) | ✅ Resolved. Updated to 1.13.3 (current LTS, drop-in). Long-term: replace datepicker with native `<input type="date">`. |
| Bootstrap | 4.6.2 | No longer maintained. BS5 breaks `data-toggle` → `data-bs-toggle`, `mr-auto` → `ms-auto`, `sr-only` → `visually-hidden`. Migration is entangled with django-crispy-forms (see below). Effort: 🟠 L. |
| Chosen | 1.1.0 | ✅ resolved. `ChosenSelectMultiple` now extends plain `SelectMultiple` with no custom Media or template. `volunteer_training_report.html` updated to use native `.change()` instead of `.chosen()`. All Chosen static files and `chosenselectmultiple.html` template deleted. |

#### 🟡 Medium — Outdated pins or frozen libraries

| Library | Version in use | Issue |
| --- | --- | --- |
| FullCalendar | 3.5.1 (2017) | Superseded by v6 (no jQuery, TypeScript, ESM). Improving the calendar edit view would warrant this upgrade; it is a large migration. Effort: 🔴 XL. |
| Moment.js | bundled in FC | Frozen (maintenance-only). Automatically resolved if FullCalendar is upgraded to v6. |
| html2text | 3.200.3 (2015) | ✅ resolved. Unpinned in `requirements/base.txt`; pip will now resolve the current release. |
| django-crispy-forms | <1.13 | EOL; v2.x separates template packs. Migrate to `crispy-forms>=2.0` + `crispy-bootstrap5`. Entangled with Bootstrap 5 upgrade above. |
| mysqlclient | 2.1.0 | ✅ resolved. Updated constraint to `>=2.2.0,<3` in `requirements/docker.txt`. |

#### 🟢 Low — Dead code to delete

- `respond.min.js` — IE8 media-query polyfill. IE8 is <0.01% of users. ✅ Removed
  (file deleted; script tag removed from both public base templates).
- IE8 conditional comments — `<!--[if lte IE 8]>` blocks in `base_public.html`
  and `base_admin.html` load six redundant Google Fonts requests that no browser
  will ever make. ✅ Removed (no longer present in templates).
- `wysihtml5.css` — WYSIHTML5 has been unmaintained since ~2014; verify it is not
  referenced anywhere and delete it. ✅ Deleted 2026-03-03 (confirmed unreferenced).

#### Recommended order of attack

1. ✅ HTTP → HTTPS on admin Google Fonts
2. ✅ jQuery 2.1.3 → 3.7+ on public site (local vendor)
3. ✅ Unpin `html2text` and `mysqlclient`
4. ✅ CKEditor 4 → Quill 2 (security-critical)
5. ✅ jQuery UI 1.11 → 1.13
6. ✅ Delete Respond.js and IE8 conditional comment blocks
7. ✅ Delete `wysihtml5.css`
8. ✅ Chosen → native `<select multiple>`
9. Bootstrap 4 → 5 + `crispy-forms` 2.x (batch together) — Effort: 🟠 L
10. FullCalendar 3 → 6 (large; do when calendar editing needs attention) — Effort: 🔴 XL

### 8.16 No default image when creating an event

When a programmer creates a new event without uploading a poster, the event has no image and appears imageless on the public programme grid. This is more noticeable at S&S than at the Cube because the PVSL licence means film posters often can't be published until shortly before the event.

**Partial solution already in the codebase:** `seed_dev_data` includes `_make_poster_image` — a bold typographic poster generator that takes the event name and a tag-derived colour, renders it at 800×450 with a gradient background, and stretches each line of text to fill the full frame width. It produces something that looks intentional rather than broken.

This could be wired up as an on-demand tool for programmers: a button on the event edit page ("Generate placeholder image") that calls a view invoking the same logic and attaches the result as a `MediaItem`. The bundled `DejaVuSans-Bold.ttf` in `seed_data/fonts/` is available to the server at runtime.

**Not yet implemented.** See 9.57 for the proposed feature spec.

---

---

