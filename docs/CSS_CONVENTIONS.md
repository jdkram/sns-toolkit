---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Sonnet 5"]
status: "#ai-input"
---

# CSS conventions

A checkable standard for this codebase's hand-written CSS, written after a full
systemic review of the 13 authored stylesheets (2026-09-10): `toolkit/static_common/css/{layout,login,messages,static_pages}.css`,
`toolkit/diary/static/diary/css/{archive,calendar_links,edit_form,edit_rota,event,form_event,programme}.css`,
`toolkit/inductions/static/inductions/css/session_detail.css`, and
`toolkit/labs/static/labs/css/floorplan.css`. Vendor CSS (Bootstrap, Font Awesome, jQuery UI,
FullCalendar, the `lib/` directories, anything under `static/` that isn't source) is out of
scope — that's collected/vendored output, not something we author.

Companion to [QUALITY_RUBRIC.md](QUALITY_RUBRIC.md) (Python) and the workspace's
`develop-html-css` skill (general HTML/CSS practice — semantics, layout method, responsive
units). This file is the project-specific layer: what's already true of *this* codebase's
CSS, where it drifted, and what to do about it going forward.

**How to use this:** when writing new CSS, follow the rules below. When touching an existing
file that violates one, fix it in the same file if it's cheap; otherwise leave a comment
rather than let a partial fix create a third inconsistent variant.

---

## The one finding that mattered most

`layout.css`'s `#sidebar` / `#site-nav` / `.nav-wrap` geometry used to be declared three
times — a base rule, a redeclaration inside a `1000px` media query, and a third "runtime
behaviour" block added later that silently won on several properties without anyone
deleting the earlier two. Reading any *one* of the three gave you the wrong answer for what
was actually rendering. That shape produced two real bugs (nav-clip, and a spurious
horizontal scrollbar in the nav on Windows/Firefox reported 2026-09-10) — not because either
fix was wrong, but because each one was a fourth layer stacked on the same broken shape
instead of a replacement for it. Consolidated into a single "Sidebar / nav geometry" section
2026-09-10 (see the comment in `layout.css` for the full trace, including one bit of
already-dead code the consolidation surfaced: `.nav-wrap`'s desktop `padding-top` had said
`42px` in three separate breakpoint rules for a long time, but a later unconditional rule
always won and 30px is what's actually been rendering — that's flagged in-file as a decision
to make explicitly, not something silently restored).

**The rule this implies:** if you need to override a selector's geometry at a later point in
the cascade (a "runtime behaviour" section, a bugfix patch, anything that isn't the file's
first pass), either fold the override back into the selector's one authoritative declaration,
or delete what it's overriding. Never leave both.

---

## Checkable rules

### C1 — One declaration site per selector per concern

A given selector's layout properties (position, width, padding, margin) should be set in one
place per breakpoint, not accumulated across a base rule, a "fix" block, and a later "runtime"
section. If you're about to add a third place that touches `#sidebar`, that's the smell from
the finding above — go edit the existing declaration instead.

### C2 — New colours and z-index values come from a token, not a fresh hex/number

`layout.css`'s `:root` now defines `--colour-brand` / `--colour-brand-bg` (the S+S site
palette) and a z-index scale (`--z-nav-toggle`, `--z-sidebar`, `--z-dropdown`,
`--z-skiplink`). Before this, "brand blue" existed as five different hex values across the
codebase (`#082080` the real one, `#0056b3` and `#007bff` from Bootstrap 4, `#0d6efd` the
*correct* Bootstrap 5.3 primary, `#00308F` in `messages.css`, `#000080` in `archive.css`), and
z-index had no scale at all — `#sidebar` and `.add-to-calendar__menu`
(`calendar_links.css`) both used a bare `500` with no relationship to each other, which is a
real collision risk on any page showing both (fixed 2026-09-10, now `var(--z-dropdown, 600)`).

Going forward: reach for `var(--colour-brand)` on public-facing pages that want the site
palette. Admin/rota pages that intentionally follow Bootstrap's own look should use
Bootstrap 5.3's actual values (`#0d6efd` primary, `#198754` success, `#dc3545` danger,
`#6c757d` secondary, `#adb5bd`/`#ced4da`/`#dee2e6`/`#e9ecef`/`#f8f9fa` for the grey scale,
`#212529`/`#495057` for text) — `floorplan.css` and `session_detail.css` already do this
correctly and are the reference to copy from. **Don't reach for `#0056b3` or `#007bff`** —
those are Bootstrap *4* colours, stale since the BS4→5.3 upgrade (`edit_rota.css`,
`calendar_links.css`, and `edit_form.css` still have them; migrate opportunistically when
touching those files rather than in one big repaint).

### C3 — Pick one naming scheme per file: BEM-ish, not snake_case or a mix

Three schemes currently coexist across the codebase: kebab-case (`.grid-item`,
`.article-page`), snake_case (`.event_image`, `.pre_title`, `.sold_out`), and BEM-ish
(`.grid-item--width2`, `.article-page__figure--l`). Worse, `.event-image` (hyphen) and
`.event_image` (underscore) both exist as *different* classes — a one-character typo away
from silently hitting the wrong rule. New CSS should use kebab-case with BEM modifiers
(`.block__element--modifier`) — `edit_rota.css` and `floorplan.css` already write new classes
this way; match them. Don't introduce new snake_case classes even in a file that already has
some.

### C4 — Don't give the same class name incompatible meanings across files

`.programme`, `.grid-item`, `.event_image`, and `.pre_title` mean completely different things
in `static_pages.css` (float-based masonry) versus `programme.css` (CSS Grid) versus
`event.css` (a near-duplicate of `static_pages.css`'s masonry — ~150 lines of copy-pasted
percentages and breakpoints). Nothing but "which template happens to load which stylesheet"
keeps these from colliding, and `event.css`'s own header comment already documents one
incident where an override silently stopped applying because of exactly this. If you're
adding a class that means something specific to one page type, scope it
(`.event-detail-grid-item`, not a bare `.grid-item`) rather than adding a fourth divergent
definition of an existing generic name. Extracting `event.css`'s and `static_pages.css`'s
shared masonry rules into one file both `@import` (or a shared partial, if a build step is
ever introduced) is the real fix, but is a bigger job than this pass covered — logged as a
future cleanup, not done here.

### C5 — No IE hacks, no duplicate normalize rules

`layout.css` carries `*zoom: 1`, `_font-family`, star-prefix hacks, and `*height: 13px` —
IE6/7 workarounds with no supported browser left to serve. It also pastes the same
normalize.css block in twice (`[hidden]{display:none}`, the `audio,canvas,video` rule, and
the `article,aside,...{display:block}` selector list each appear twice, with slightly
different selector lists each time — not touched in this pass since merging them safely
means computing the union of both lists rather than just deleting one, which is a follow-up
worth doing deliberately rather than as a drive-by). Don't add to either pile: no new
IE-only hacks, and if you're touching the normalize block, merge rather than append.

### C6 — `!important` is not a specificity strategy

`.action a` carries 3-4 `!important` declarations in both `layout.css` and
`static_pages.css`/`event.css`, with *different* colours in each, relying on file load order
to resolve which wins. This works today but every future override of `.action a` needs its
own `!important` to compete — there's no ceiling. If you need to override a selector that's
already fighting with `!important`, prefer raising the new rule's specificity (a more
specific selector, or scoping to a parent class) over adding another `!important` to the pile.

### C7 — Screen CSS never uses point units; check contrast against the *actual* rendered background

`messages.css` used `font-size: 16pt` (fixed 2026-09-10, now `1.333rem`) — points are a print
unit and have no defined relation to a user's browser font-size preference on screen. Use
`rem`/`em`/`px` instead.

Separately: when checking contrast, verify which template actually loads the stylesheet
before assuming a background colour. `messages.css`'s warning colour (`#FF7E00`) was flagged
twice against two different *wrong* backgrounds before anyone checked: first assumed to be on
white (my own initial review), then "corrected" to the public-page pink `--colour-brand-bg`
by a second-model review pass (`git grep messages.css` shows it only loads on
`base_admin.html`-derived templates, which have their own plain white page background — the
pink assumption was wrong too). The actual number (`#FF7E00` on white ≈ 2.55:1, below even
the 3:1 large-bold-text threshold that applies here) only came out right once someone grepped
the templates. Fixed to `#856404` (≈5.5:1), reusing the amber already established for warning
states in `edit_rota.css`/`form_event.css` rather than inventing a sixth ad hoc colour — see
`docs/tasks/known-issues.md` Bug BC for the full before/after numbers on all four states.
**The rule this implies:** "what background does this render on" is a template-inheritance
question, not something to infer from the stylesheet alone — grep for who `{% extends %}`s
what and loads the file before asserting a contrast ratio.

### C8 — Breakpoints are `px`, mobile-first, content-driven — that's fine, keep it that way

The workspace's general HTML/CSS skill recommends `em`-based breakpoints; this codebase
uses `px` consistently (360/475/600/1000/1260/1600/1900) and the values are already
content-driven (chosen where the layout actually breaks, not at device widths) rather than
arbitrary. That's an intentional, established deviation from the general skill default, not
an oversight — don't "fix" it to `em` in a drive-by; if it's ever revisited, do it as one
pass across every file at once, since the breakpoint values are shared critical constants
across `layout.css`, `programme.css`, `event.css`, and `static_pages.css`.

---

## Second-opinion pass (2026-09-10)

After the initial review above, MiniMax M3 (via OpenCode/OpenRouter, `$0.045` for the full
run) was asked to critically re-check it — both the risky sidebar/nav consolidation and the
12 files Claude hadn't touched. Its cascade re-derivation of the sidebar consolidation was
independently correct (it rebuilt the same before/after property tables from scratch and
reached the same conclusion). Of its other findings, three held up after verification and are
fixed (Bug BA, BB, BC in `docs/tasks/known-issues.md`); one (a `.black_overlay`/`#sidebar`
z-index "collision") turned out not to be a real rendering conflict once the actual DOM
geometry was checked — `.black_overlay`'s active state starts at `left: var(--sidebar-width)`
and never spatially overlaps the sidebar, so their z-index relationship never mattered, though
the value has been named (`--z-backdrop`) anyway for the documentation benefit. Worth
repeating for next time: a second model's findings are a lead to verify, not a fact to
relay — cross-check against the actual template inheritance, JS, and DOM before accepting or
logging any of them, in both directions (a model can both find something real *and* mis-frame
its severity, as with the "no way to close it" framing on Bug BA, or misjudge the actual
rendering context, as with Bug BC's background-colour mistake — made independently by both
Claude and MiniMax before anyone grepped the templates).

## What this doesn't cover

- **A build step.** There's no Sass/PostCSS pipeline, so "extract a shared partial" (C4)
  means either a plain CSS `@import` (with its own performance cost) or introducing tooling —
  a bigger decision than this pass makes unilaterally.
- **A full BEM rename** of the existing snake_case classes (C3). Renaming `.event_image`
  site-wide touches every template that references it; do it as its own deliberate pass with
  grep-verified template updates, not opportunistically.
- **Repainting the Bootstrap-4-blue files** (C2) to Bootstrap 5.3 colours. That's a visible
  UI change on pages (`edit_rota.html`, `form_event.html`) this session couldn't browser-test —
  migrate file-by-file when next touched, with an actual look at the rendered page.
- **The `event.css`/`static_pages.css` masonry duplication** (C4) — logged, not extracted.
