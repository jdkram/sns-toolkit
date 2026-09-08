---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Sonnet 5"]
status: "#ai-input"
---

# Labs feature scope — decision document

Chunk 7 of the [quality pass](../QUALITY_PASS.md). Not a proposal to delete anything — a
factual inventory to make the keep/cut conversation informed, one tool at a time. Nothing here
is deployed with live users yet, so there is no usage signal to lean on; this is a values
question about what Jonny wants to commit to maintaining, not a data question about what's
being used.

**How to read this:** each tool gets its size, its test coverage, what it depends on or is
depended on by, what deleting it would cost, and what keeping it commits to. No recommendation
column — that's the conversation this document is for, not something to pre-empt.

**Nothing here is gated by a feature flag.** All eight are always-on; there's no
`settings_starandshadow.py` switch to flip off one tool without touching code. Cutting one
means deleting views/templates/models/migrations and the one nav link in
`fragment_navmenu.html`, not toggling a flag.

---

## At a glance

| Tool | Python LOC | Template LOC | View coverage | Models | Nav entry |
|---|---:|---:|---:|---|---|
| Collectives | 149 | 645 (3 templates) | 99% | `Collective`, `CollectiveLink`, `CollectiveRole` | `labs-collectives` (+ public `labs-collectives-public`) |
| Jobs board | 123 | 228 (2 templates) | 100% | `Job` | `labs-jobs` |
| Shopping / procurement | 500 | 1,139 (6 templates) | 42% | `Supplier`, `ConsumableItem`, `SupplierRecord`, `NeedFlag`, `ProcurementPledge` | `labs-shopping` |
| Donations wishlist | 112 | 408 (2 templates) | 90% | `DonationItem` | `labs-donations` (+ public) |
| Building map (floorplan + loft + area photos) | 380 | 1,222 (1 template) | 34–37% | `RoomNote`, `LoftItem`, `LoftItemPhoto`, `AreaPhoto` | `labs-floorplan` |
| Lost & found | 117 | 622 (4 templates) | 50% (0% outside photo-upload paths) | `FoundItem` | `labs-found-item-log`, `labs-found-items` |
| Community exchange | 315 | 638 (3 templates) | 55% | `ExchangeItem` | `labs-exchange` |
| **Bulletins** *(not in scope)* | 272 | 128 (2 templates) | 86% | `Bulletin`, `BulletinRead` | `labs-bulletins` |

Bulletins is listed for completeness — it postdates the original 9.148-era Labs suite, has
strong test coverage already, and integrates with the dashboard (see below) in a way none of
the other seven do. It reads as a core feature that happens to live in the `labs` app, not a
mini-tool candidate for this review. Excluded from the totals and from the rest of this
document.

**Totals for the seven under review: 1,696 Python LOC, 4,902 template LOC, 51.6% average view
coverage.** ("Labs" as a whole is 6,471/5,030 LOC per `docs/QUALITY_BASELINE.md`; the ~230
Python / ~0 template line gap not in the table above is `models.py`, `forms.py`, `admin.py`,
`_common.py`, `urls.py` — shared infrastructure, not attributable to one tool.)

---

## Collectives

**What it is:** a directory of S+S's working groups (programming, tech, bar, etc.) — what each
does, how to join, a contact address, optional "example role" text. A logged-in view for
volunteers plus (per `docs/tasks/operations.md` 9.x) a planned public directory page.

**Size:** 149 Python LOC across one view module, three templates (`collectives.html`,
`collective_edit.html`, `collectives_print.html`) totalling 645 lines.

**Coverage:** 99% (`toolkit/labs/tests/test_collectives.py`, 270 lines) — the best-tested tool
in this review.

**Dependencies:** `toolkit.diary.models.get_site_config` (shared site config, read-only) and
the shared `_user_volunteer` helper. Nothing else in the codebase depends on it.

**Cost of removing:** low, mechanically — self-contained, well-tested, easy to excise cleanly.
The cost is organisational: this is the one tool with an explicit near-term roadmap item
(9.x public directory page, `docs/tasks/operations.md`) already scoped against it, so removing
it means also dropping or re-scoping that ticket.

**What keeping it commits to:** volunteer-facing directory content someone has to keep current
(collective descriptions, contact addresses) — a content-maintenance cost, not a code one. The
planned public page adds a second audience (the general public) whose expectations for
correctness are different from an internal tool.

---

## Jobs board

**What it is:** an ad-hoc maintenance/task board — post a job, claim it, mark it resolved.
Distinct from the rota (which is shift-based); this is one-off or occasional physical-space
work ("fix the projector bulb", "replace the till roll").

**Size:** 123 Python LOC, two templates (`jobs.html`, `job_form.html`) totalling 228 lines —
the smallest tool here by template size.

**Coverage:** 100% (`toolkit/labs/tests/test_jobs.py`, 197 lines).

**Dependencies:** none beyond the shared `lab_forms` module. `docs/tasks/operations.md` names
two *proposed* couplings that don't exist yet: a dashboard card (mirroring the existing
`shopping_needs`/`recent_bulletins` pattern in `index/views.py`) and a room-linkage to the
building map (`_FLOORPLAN_ROOMS` extracted to a shared module so both `jobs.py` and
`floorplan.py` can reference the same room list). Today, cutting Jobs affects nothing else.

**Cost of removing:** lowest of the seven — fully tested, fully isolated, no live cross-tool
wiring yet. If cut, the two proposed integration tickets in `docs/tasks/operations.md`
(dashboard card, map linkage) go with it.

**What keeping it commits to:** the two proposed integrations are real design investment
already written down — picking Jobs up again later means either building those (dashboard
visibility was explicitly framed as "the actual fix" for a named cultural problem: volunteers
who only do shifts not knowing what background work exists) or leaving it as a lower-visibility
standalone board.

---

## Shopping / procurement

**What it is:** the largest and least-tested tool. A shared consumables list with suppliers,
"need flagged" / "pledged to buy" / "bought" states, a per-supplier buying workflow, and
enrichment against supplier records. Genuinely the most operationally complex of the seven —
real multi-step workflow, not a CRUD list.

**Size:** 500 Python LOC (the largest single view module in `labs`), six templates
(`shopping.html`, `shopping_buy.html`, `shopping_buy_supplier.html`,
`shopping_buy_unsorted.html`, `shopping_item.html`, `shopping_item_add.html`) totalling 1,139
lines — the largest template footprint after the building map.

**Coverage: 42%**, the second-worst of the seven. `docs/QUALITY_BASELINE.md` names this
explicitly: "3 of 13 endpoints tested." `toolkit/labs/tests/test_shopping.py` is 339 lines but
covers only a slice of `shopping.py`'s 500.

**Dependencies:** `_user_volunteer` (shared helper) only. Five models
(`Supplier`, `ConsumableItem`, `SupplierRecord`, `NeedFlag`, `ProcurementPledge`) — the most of
any tool here, reflecting the workflow's real complexity (an item can have multiple supplier
records, multiple pledges over its life).

**Cost of removing:** highest of the seven, on two axes at once — most code, and the code
that's least verified, so removing it safely means reviewing behaviour a test suite mostly
doesn't already describe. Five models' worth of migrations to consider too.

**What keeping it commits to:** closing the 58%-untested gap before this is trustworthy for
real procurement decisions (someone pledging to buy something, someone else assuming it's
covered). This is the standout Chunk 10 candidate among the seven if kept — the size and the
coverage gap point the same direction.

---

## Building map (floorplan + loft + area photos)

**What it is:** an interactive SVG floorplan of the building, with per-room notes and photos,
plus a "loft" sub-area with its own itemised inventory (with photos). Three view modules
(`floorplan.py`, `loft.py`, `area_photos.py`) that only make sense together — `floorplan.py`
imports directly from `loft.py`, and there is no separate nav entry for the loft; it's reached
through the map.

**Size:** 380 Python LOC across the three modules, but **one template of 1,222 lines** —
`floorplan.html` is the single largest template in the entire `labs` app, and per
`docs/QUALITY_BASELINE.md`, 721 of those lines are inline `<script>` (already flagged
separately as Chunk 9's #1 extraction target, independent of this decision).

**Coverage: the worst of the seven, on every module** — `floorplan.py` 37%, `loft.py` 34%,
`area_photos.py` 36%. `docs/QUALITY_BASELINE.md` names `loft.py`/`area_photos.py` as having "no
tests at all" beyond the shared `test_security.py` auth-boundary checks; there is no
`test_floorplan.py` or `test_loft.py` in `toolkit/labs/tests/` at all.

**Dependencies:** this is the most *architecturally* significant of the seven regardless of
size, because `_FLOORPLAN_ROOMS` (the canonical room list backing `RoomNote` and `AreaPhoto`)
is a real internal API other features are designed against — `docs/tasks/operations.md` 9.x
proposes extracting it to a shared `room_data.py` specifically so the Jobs board can key jobs
by room and link both directions between the map and the jobs list. That ticket doesn't exist
yet, but it's written down as planned, not speculative.

**Cost of removing:** high on the "least verified, most interactive" axis — 721 lines of
untested inline JS driving an SVG-click interaction model that a Django test client cannot
exercise at all (this needs the Chunk 9 browser-verification pass regardless of what's decided
here). Removing it also means dropping the planned jobs↔map integration before it's built.

**What keeping it commits to:** the largest inline-JS extraction in the whole codebase (Chunk
9), and — if the room-linkage ticket goes ahead — becoming a dependency other tools are built
against, which raises the cost of ever changing `_FLOORPLAN_ROOMS`'s shape later.

---

## Lost & found

**What it is:** log a found item, browse the log, claim or dispose of items, print a label.

**Size:** 117 Python LOC, four templates (`found_items.html`, `found_item.html`,
`found_item_log.html`, `found_item_label.html`) totalling 622 lines — the templates are larger
than the view logic suggests, mostly the label-printing layout.

**Coverage: 50% overall, but effectively 0% outside photo upload.** The only dedicated tests
are in `toolkit/labs/tests/test_photo_uploads.py` (`FoundItemPhotoTests`,
`PhotoUploadAnonTests`) — they test that logging a found item with/without a photo works and
that anonymous users are blocked, but the claim/dispose/browse/label flows have no dedicated
test file at all (no `test_lost_found.py` or `test_found_items.py`).

**Dependencies:** none beyond shared helpers. Nothing else references `FoundItem`.

**Cost of removing:** low — self-contained, moderate size, no roadmap investment found in
`docs/tasks/`.

**What keeping it commits to:** the coverage gap is a normal, not-urgent Chunk 10 item (there's
no complexity or workflow-risk signal like Shopping's), but it is a real gap — the claim and
dispose actions currently ship with zero regression coverage.

---

## Community exchange

**What it is:** a give-away/lend board for physical items — post an item, mark it on loan,
mark it returned, mark it gone, withdraw a listing.

**Size:** 315 Python LOC, three templates (`exchange.html`, `exchange_form.html`,
`exchange_item.html`) totalling 638 lines.

**Coverage:** 55% (`toolkit/labs/tests/test_exchange.py`, 277 lines, plus
`ExchangePhotoAddTests`/`ExchangePhotoEditTests` in `test_photo_uploads.py`). Missing coverage
per the earlier coverage run clusters around the on-loan/returned/all-gone/missing state
transitions (lines 193–315 in `exchange.py`).

**Dependencies:** `toolkit.diary.models.get_site_config` (shared config, read-only). This is
also one of the five files named in rubric rule R14 — its modify actions
(`mark_on_loan`/`mark_returned`) are intentionally open to any logged-in volunteer, a decision
Jonny already made 2026-09-08 and that stands regardless of what's decided here.

**Cost of removing:** low-to-moderate — more state machine than Jobs or Lost & Found (five
distinct item states to reason about), but self-contained.

**What keeping it commits to:** finishing coverage of the state-transition logic, which is
where a shared-item-lifecycle bug would actually live (an item marked returned twice, or gone
after being on loan) — the kind of bug a status-code-only test wouldn't catch even if it
existed.

---

## Donations wishlist

**What it is:** the smallest and most passive tool — a public-facing wishlist of things S+S
needs donated, with an internal management view.

**Size:** 112 Python LOC, two templates (`donations.html`, `donations_manage.html`) totalling
408 lines.

**Coverage:** 90% (`toolkit/labs/tests/test_donations.py`, 126 lines) — second-best after
Collectives.

**Dependencies:** `get_site_config` (shared, read-only), same pattern as Collectives and
Exchange. Nothing depends on it.

**Cost of removing:** lowest of the seven alongside Jobs — small, well-tested, no roadmap
investment, no cross-tool coupling.

**What keeping it commits to:** almost nothing further — this is close to "done" as a tool;
the only real cost is the same content-maintenance one as Collectives (someone keeps the
wishlist current).

---

## Cross-cutting patterns, for the conversation itself

- **Coverage splits cleanly into two groups.** Collectives (99%), Donations (90%), Jobs (100%)
  are all well-tested. Shopping (42%), the building map (34–37%), Lost & Found (50% but ~0%
  outside photo upload), and Exchange (55%) are not. This split does not track tool size in
  either direction — Jobs is small and well-tested, Shopping is large and poorly tested, but
  Collectives is mid-sized and well-tested while the building map is mid-sized and the worst
  covered of all seven.
- **Only two tools have anything written down about their future** (Collectives' public page,
  Jobs' dashboard card and map linkage, and the map's own room-data extraction ticket that
  Jobs depends on). The other four — Shopping, Lost & Found, Exchange, Donations — have no
  forward-looking tickets in `docs/tasks/` at all. That's a fact about documentation, not
  necessarily about intent; worth naming in the conversation rather than assuming it either
  way.
- **The building map is architecturally critical for Jobs' proposed future**, even though
  today the two modules don't share any code. If the map is cut, the room-linkage half of the
  9.148-adjacent jobs ticket in `docs/tasks/operations.md` goes with it.
- **Nothing here can be soft-disabled.** Any "cut" decision is a real deletion (views,
  templates, models, migrations, the nav link), not a flag flip — worth knowing before treating
  this as a low-stakes experiment.
