---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Sonnet 5"]
status: "#ai-input"
---

# Navigation surfaces

This codebase has **three independently hand-written navigation surfaces**, not one. They
have drifted out of sync at least twice (documented below), and will keep doing so unless
whoever adds a nav item checks this file first. There is no shared data source they render
from — each is a separate template/array that has to be edited by hand.

| Surface | File | Audience |
|---|---|---|
| **Sidebar** | `toolkit/diary/templates/fragment_navmenu.html`, included by `#site-nav` in `base_public.html` | Anyone on a public page; the "logged in" section is for volunteers/staff browsing the public site |
| **Toolkit navbar** | The `<nav class="navbar...">` block in `toolkit/index/templates/base_admin.html` | Anyone using the internal toolkit (rota, diary, admin) |
| **Command palette** | The `window.TOOLKIT_COMMANDS` array, same file, just below the navbar | Same audience as the toolkit navbar — this is a Ctrl+K search over the same destinations |

## The design decision (2026-09-10)

**The sidebar is deliberately a smaller, curated subset. The toolkit navbar and command
palette are meant to be the complete set, and must mirror each other exactly.**

Rationale: the sidebar's job is public-page browsing, with a lean "quick access" section
underneath for a volunteer who's already looking at the public programme and wants to jump
to the toolkit — not a full admin console bolted onto every public page. The toolkit navbar
and command palette have no such excuse: they're both surfaces *for* toolkit users, on
toolkit pages, so a permission-gated item present in one and not the other is a bug, not a
design choice.

**The rule this implies:**
- Adding an item to the **toolkit navbar**? Add it to the **command palette** too, same
  permission/feature gate. And vice versa.
- Adding an item to the **sidebar**'s logged-in section? Decide deliberately whether it
  belongs in the toolkit navbar/palette too — most things a volunteer needs from the public
  page (Diary, Past events, Calendar, Rota, the Noticeboard items) should be mirrored there,
  since a toolkit user reaches the same destinations. Admin/reporting-only items (CSV
  exports, audit logs, bulk tools) are sidebar-*exempt* by design — don't add them there.
- Whichever direction: if a link is gated on a `site_config.*_enabled` flag anywhere, gate
  it the same way everywhere it appears — an ungated copy becomes a dead link (404, since
  the views themselves enforce `@_feature_enabled_or_404`) the moment the feature's toggled
  off, not a security hole, but a confusing loose end.

## What was actually found and fixed (2026-09-10)

Prompted by a reported mismatch ("Past events" visible on the sidebar, not on the toolkit
navbar). A full audit of all three surfaces turned up more than that one item:

**Missing from the toolkit navbar/palette (present in the sidebar):**
- **Past events** — sat right next to "Diary" behind the identical `feature_perms.diary_read`
  gate in the sidebar; the navbar's block for that gate only ever added "Diary". Added to
  both the navbar and the palette, `g → v` shortcut (was going to collide with `g → p`,
  already taken by "People" in the navbar — the sidebar itself had *also* doubled up `p` for
  both "Programme" and "Past events", silently making Past events unreachable by keyboard
  shortcut there too, since jQuery's `.attr()` on a multi-element match just returns the
  first DOM match. Fixed all three: sidebar, navbar, and palette now agree on `v`.
- **Maintenance schedule** — present in the sidebar's Noticeboard dropdown, absent from the
  navbar's Community dropdown and the palette entirely. Added to both.

**Feature flags checked at the view level (`@_feature_enabled_or_404`) but not gating the
link consistently everywhere it appeared** — the sidebar had every one of these right; the
navbar and/or command palette were missing them in various combinations:

| Flag | Sidebar | Navbar (before) | Palette (before) |
|---|---|---|---|
| `building_map_enabled` | ✅ | ❌ ungated | ❌ ungated |
| `shopping_list_enabled` | ✅ | ❌ ungated | ❌ ungated |
| `lost_and_found_enabled` | ✅ | ❌ ungated | ❌ ungated |
| `collectives_enabled` | ✅ | ❌ ungated | ❌ ungated |
| `donations_enabled` | ✅ (plus a public-nav-placement flag the toolkit surfaces don't need) | ❌ ungated | ❌ ungated |
| `jobs_board_enabled` | ✅ | ❌ ungated | ❌ ungated |

All six fixed in both the navbar and the palette, matching the sidebar's existing gate.

**Also found and fixed in passing:** the command palette had "Rota vacancies" listed twice —
once unconditionally, once correctly gated on `feature_perms.rota_vacancies` a few lines
later. The unconditional duplicate is removed.

**Deliberately not touched:** the long tail of toolkit-only items with no sidebar
equivalent — People and Meta dropdown contents (volunteer/member admin, reports, site
settings, audit log), "Do a shop", "Edit profile", "Queue" (programming queue). These are
correctly toolkit-only per the design decision above; the sidebar staying without them is
not drift, it's the point.

## Maintenance checklist

Before adding a nav item, ask:
1. Is this for toolkit users only, or does a public-page volunteer need it too?
2. If toolkit-only: add it to **both** the navbar and the palette, same gate, same target.
3. If it should also be reachable from the public page: add it to the sidebar too, using
   the *same* permission/feature check as the toolkit copies.
4. Pick a `data-nav-key`/palette shortcut letter that isn't already used **in that specific
   surface** — the sidebar and the navbar are separate keyboard-shortcut scopes
   (`keyboard-nav-public.js` targets `#site-nav`, `keyboard-nav-admin.js` targets
   `.navbar-nav`), so a key can safely repeat *across* surfaces (and should, for the same
   destination, as with "Past events" landing on `v` in both) but never *within* one.
5. If the destination is behind a `site_config.*_enabled` flag, gate the nav item on it
   everywhere the item appears — check the view's own `@_feature_enabled_or_404` decorator
   to find the exact flag name if unsure.
