# S&S Toolkit — Finance

Feature specs for event financial settlement: attendance, ticket/bar income, distributor
payment outcomes, and the Finance-facing review that closes the loop the paper PRS/PPL book
and `sns-analysis` currently cover informally.

**For work status:** [CURRENT_WORK.md](../../CURRENT_WORK.md)

**Design trail for 9.171:** [docs/EVENT_SETTLEMENT_SCOPING.md](../EVENT_SETTLEMENT_SCOPING.md)
(evidence + decisions) → [docs/EVENT_SETTLEMENT_USER_STORIES.md](../EVENT_SETTLEMENT_USER_STORIES.md)
(workflow analysis, the two personas' conflicting needs, what falls out of it). Read both before
touching 9.171 — this entry is the spec that falls out of them, not a restatement of their
reasoning.

---

### 9.171 — Event settlement records: attendance, ticket/bar income, distributor payment 🟠 L — MVP shipped 2026-09-12

**Shipped this pass:** the data model (`ShowingSettlement`, `SettlementLineItem`, the three
`Event.distributor_*` fields), the `event_settlement_enabled` feature flag, the per-showing
settlement entry form and the event-level distributor-payment form (both reached from the Event
Hub), the derived `settlement_status()`/`distributor_payment_status()` helpers, and — per a direct
follow-up ask — three UI pieces the spec below only implied: the Event Hub's past-showings section
now gets more visual prominence (auto-expanded, red-bordered rows) whenever something's
outstanding; a "Your past events" page (`programmer-past-events`) lists a programmer's own past
events with settlement/distributor-payment status; and a dashboard card surfaces the same,
auto-shown to any volunteer set as `Event.programmer` on at least one event, no opt-in needed. 76
new tests (model logic, feature-flag 404s, the Hub's prominence behaviour, the dashboard card),
full suite green (1,460 tests), ruff/black clean. **Not browser-verified** — no Claude-in-Chrome
connection this session either; the settlement form's one bit of JS (the "add another row" button
for line items) has only been exercised via the Django test client, which confirms the page
renders and posts correctly but not that the button itself works as a human would click it.

**Deliberately not built this pass** (see the spec below for what each was for): the Finance-facing
date-ranged monthly review screen; revision history on corrections (currently just
`updated_by`/`updated_at`, not the full `EventTermsRevision`/`EventAuditLog`-style audit trail the
user-stories doc asked for); a decision on PRS/PPL performer-registration status. All three remain
open — see "Deliberately open" below, unchanged from the original spec.

**The Finance-facing monthly review screen — shipped 2026-09-12.** `finance_settlement_review`
(`edit_views/finance.py`) built exactly to the resume protocol below: date-ranged (defaults to the
current calendar month), one card per event with an elapsed showing in the range, each showing its
`settlement_status()`/`distributor_payment_status()` plus a per-showing drill-down table linking to
`showing_settlement_edit`, and a link to `event_distributor_payment_edit` for the event-level
outcome. `no_financial_activity` events excluded at the query level. Same `write_required` +
`event_settlement_enabled` gate as everything else in the feature (the "Open decision" below was
resolved by taking the documented default). Reachable via a new standing dashboard link — not a
data-bearing card, since the review page itself does the querying — shown to any Programmer+ once
the flag's on; extracting `_finance_settlement_review_url_for()` in `toolkit/index/views.py` kept
`ToolkitIndexView.get_context_data` under the complexity gate, the same move the original
settlement widget needed. 12 new tests, full suite green (diary 597, index 94), ruff/black clean.
Not browser-verified (test-client only, same caveat as the rest of 9.171).

**Revision history on corrections — shipped 2026-09-12.** Distributor-payment fields
(`distributor_invoiced_date`/`distributor_paid_date`/`distributor_paid_amount_gbp`) now reuse
`EventTermsRevision` directly (extended `_AUDITED_FIELDS`, new snapshot columns, a `changed_fields`
CSV column driving a `summary()` method so the display says which fields actually changed).
`ShowingSettlement` corrections get a new `SettlementRevision` model instead — captured explicitly
in the view rather than via a signal, since the ticket-sales line items are a formset that saves
after the parent row, so a pre_save signal on the settlement alone can't see them changing. No
revision on a settlement's first-ever save, only once something already recorded gets
overwritten — matching Persona B's "correct without destroying the original" ask. Both surface on
the Event Hub's existing Panopticon-only audit trail panel, and the settlement form gets its own
"Change history" section matching the Terms field's. 14 new tests, full suite green (1,472),
ruff/black clean. Not browser-verified (test-client only, same caveat as the rest of 9.171). Full
detail in `docs/SPEC.md`'s ShowingSettlement/SettlementLineItem section.

Still open: the PRS/PPL scope decision.

---

### Resume protocol: the Finance-facing monthly review screen

**Self-contained — a fresh session should be able to start straight from this section without
re-reading the scoping/user-stories docs first**, though they're linked above if the "why" behind
a choice below needs re-deriving. This is the last unbuilt piece of 9.171 that doesn't need a
browser to build and verify (test-client only, same as everything else in this task so far) —
everything else queued in `CURRENT_WORK.md` is blocked on a Claude-in-Chrome connection this
session didn't have either.

**What it is, in one line:** a date-ranged index of every event/showing in the window with its
settlement/distributor-payment status, linking out to the *existing* correction forms — not a new
data-entry surface, since `showing_settlement_edit` and `event_distributor_payment_edit`
(`toolkit/diary/edit_views/finance.py`) already are where corrections happen. This screen's whole
job is helping Finance find the right ones, on their own monthly rhythm, without hunting through
the calendar. Persona B's "correct without destroying the original" need is why last session built
`SettlementRevision`/`EventTermsRevision` first — that's already there for this screen to display.

**Nearest existing pattern to copy, almost line for line:**
- `programmer_past_events` (`edit_views/finance.py`) already does "list events with elapsed
  showings, compute `settlement_status()`/`distributor_payment_status()` per event, render a
  table" — this screen is the same shape, minus the `Event.programmer` scoping, plus a date range.
- `past_events_search` (`edit_views/events.py`) already does the date-range query-param pattern
  (`date_from`/`date_to` GET params, `datetime.date.fromisoformat` parsing, defaults) against
  `Max("showings__start")` — copy this for the range filter rather than reinventing it. Default the
  range to "this calendar month" (Finance's existing rhythm, per the scoping doc's Evidence B) when
  no params are given, unlike `past_events_search` which defaults to no filter at all.

**Concrete plan:**
1. New view, e.g. `finance_settlement_review` in `edit_views/finance.py`, `@write_required`,
   `@_settlement_enabled_or_404`, `@require_http_methods(["GET"])` — same decorator stack as
   `programmer_past_events`, no new permission tier (this codebase has no "Finance" role; see "Open
   decision" below).
2. Query: `Event.objects.annotate(latest_showing_start=Max("showings__start")).filter(...)`
   scoped to the date range, `no_financial_activity=False`, excluding events with zero elapsed
   non-cancelled showings — reuse the elapsed-showing filtering already written in
   `programmer_past_events` rather than re-deriving it.
3. Per-event row: `event`, `latest_showing`, `event.settlement_status()`,
   `event.distributor_payment_status()`, and — new for this screen, since Persona B needs
   drill-down, not just a status badge — a list of the event's *showings* each with its own
   `Showing.settlement_status()` and a direct link to `showing_settlement_edit`, plus one link to
   `event_distributor_payment_edit`. No new forms: this page links out to forms already built.
4. Template: a new `finance_settlement_review.html`, table-per-month or table-per-event (event
   grouping likely reads better given showings nest under one distributor-payment outcome) —
   follow `programmer_past_events.html`'s existing table markup as the starting point rather than
   designing fresh.
5. URL: add to `toolkit/diary/urls.py` alongside the other three settlement URLs; name it something
   like `finance-settlement-review`.
6. Link to it from somewhere reachable — the natural spot is the Event Hub's existing settlement
   UI area, or a Site-Settings-configurable dashboard card following the `programmer_past_events`
   card's exact pattern (`toolkit/index/views.py`) if Finance should have a standing dashboard
   entry the way programmers already do. Pick one when building; both are cheap, and the "no per-
   user opt-in, auto-shown" precedent from the existing card is the default to match unless there's
   a reason not to.

**Open decision, deliberately not pre-resolved:** who can see this page. Existing settlement views
are `write_required` (Programmer+), and this codebase has no separate "Finance" permission tier
(non-hierarchical by design — see `docs/SPEC.md` §2). Simplest default: same `write_required` gate
as everything else in this feature, i.e. any Programmer+ can reach it, same as the entry forms
they'd be correcting. Revisit only if Jonny specifically wants to restrict it further.

**Test plan:** mirror `ProgrammerPastEventsViewTests`/`EventHubSettlementDisplayTests` in
`test_event_settlement.py` — feature-flag 404, date-range filtering (in/out of range), status
display per event, drill-down links present, `no_financial_activity` events excluded.

**Not in scope for this pass** (per the original spec's "Deliberately open" list, still
unresolved): PRS/PPL performer-registration status, aggregate CSV export, correction-rights
enforcement beyond the existing permission gate (nothing here should block a Programmer from using
these forms — only from *not knowing* a correction is needed, which is what this screen fixes).

**Effort:** the smallest genuinely-new-UI piece left in 9.171 — one view, one template, one URL,
reusing every status/permission/query building block already built. Rough guess 4-8h given how
much of steps 1-4 above is "copy an existing view and change the scoping", well under the original
spec's "biggest unknown in the range" framing (which was written before `programmer_past_events`
existed as a template to copy).

**Source:** `docs/EVENT_SETTLEMENT_SCOPING.md` + `docs/EVENT_SETTLEMENT_USER_STORIES.md`, both
complete 2026-09-10. Six photographed PRS/PPL paper-book pages, a film-screening ledger, and a
`vol@jdkram.net` email trail established the evidence base; the user-stories pass turned that
into two personas whose needs genuinely conflict (see below) and a list of what falls out of
resolving that conflict.

**Problem.** Event cost *terms* are captured (9.54's `cost_type`/`cost_total_gbp`/etc., and
9.149's itemised budget estimate-vs-actual once built) but *actuals* — what a showing actually
took on the door, at the bar, and whether the distributor was ever paid — are never recorded in
the toolkit at all. Today this lives on paper (a PRS/PPL book in two incompatible formats, no
fixed price-band schema in practice) or is approximated after the fact by the archived
`sns-analysis` project, which infers figures from TicketSource and till exports rather than
holding ground truth. 67% of volunteer gigs never touch TicketSource, so that inference gap is
structural, not an edge case. PRS/PPL reporting has, per the evidence, actually stalled — there
is no current owner making it happen.

**Goal.** Give every event a settlement record by default, own both the raw inputs (attendance,
line-item income) and the outcome (distributor invoiced/paid), and make `sns-analysis`
unnecessary once this exists — not run alongside it.

#### The core design tension (from the user-stories pass)

Two personas want incompatible things from the same data, and the spec only works if it stops
trying to make one screen serve both:

| | Persona A — the volunteer, wrapping up their own event, at 1am | Persona B — Finance, monthly review, weeks later |
|---|---|---|
| Ticket line items | Free text, zero friction, "add another" row | Comparable, aggregatable across a month |
| Editability | Submit once, move on | Correct repeatedly, indefinitely |
| Precision | An honest rough guess | Numbers that eventually add up |
| Fields owned | Only what they can see (door take, headcount) | The complete picture, including bar |

**Resolution:** a fast, forgiving entry form (A) feeds a slower, more demanding review process
(B). Correction rights live on the review side, not the entry side. Line items are free-text by
default but can optionally carry a category tag from a short picklist (advance / door /
concession / guest list / other) — never required, useful whenever present. See the
user-stories doc's "Where Persona A and Persona B genuinely conflict" section for the full
reasoning; don't re-derive it, cite it.

#### What NOT to build (the paper process is more forgiving than it looks)

Each of these looks like an obvious data-integrity improvement over a paper form and would
actually break the thing the paper form gets right. Full reasoning in the user-stories doc's
"Where a 'clean' digital design would be worse than the paper process" section:

- Fixed price-tier columns — no such schema exists in practice across six real examples.
- Hard validation blocking submission on incomplete data — two of six real paper forms left
  ticket-sales sections blank, and that's tolerated today.
- A locked "finalised" settlement status — bank/till figures overriding an estimate *after the
  fact* is the normal path, not an exception.
- Building the primary entry path around TicketSource — most gigs never touch it; treat any
  TicketSource pre-fill as an optional shortcut for the minority that do, not the backbone.

#### Data model

**`Showing`-level** (settlement is per-showing; an `Event`-level summary rolls these up — the
paper book's own per-showing film ledger and the per-event gig form both confirm this
granularity, per the scoping doc's "Non-questions" section):

- `attendance` — nullable integer, optional, approximate.
- Ticket sales as a repeatable line-item model (new `SettlementLineItem` or similar, FK to
  `Showing`): free-text description, optional category tag (advance / door / concession / guest
  list / other — short `choices`, never `blank=False`), count, unit price. One blank row to
  start in the UI, "add another" to extend — no fixed columns.
- `bar_contribution_gbp` — nullable, optional, separately attributable (i.e. don't force whoever
  fills in the ticket side to also supply this; it's commonly a different person with till
  access).
- `settlement_notes` — free text, for exceptions Finance needs to flag (a private hire, a
  charity split) — per Persona B's "a way to flag and annotate exceptions" requirement.

**`Event`-level:**

- `no_financial_activity` — **already exists**, built 2026-09-10 as part of 9.169. Do not add a
  second flag; wire this task's settlement requirement to key off it. When ticked, no showing
  under the event needs a settlement record and none of this UI should nag about one. Per the
  user-stories doc's Persona C section, keep it freely reversible on the same terms-entry screen
  (already the case — it's a normal `Event` field on the general-purpose edit form, not a
  one-way gate) — label it "no financial activity **expected**", not a flat assertion, so a wrong
  guess (a bake sale during an otherwise non-financial work party) is a two-second fix rather
  than a silently vanished £40.
- Distributor payment outcome: `distributor_invoiced_date`, `distributor_paid_date`,
  `distributor_paid_amount_gbp` — separate from the ticket/bar figures, per the scoping doc's
  Answers Q3 (the toolkit owns the outcome, not just the raw inputs).
- A derived settlement-completeness status (recorded / partial / not recorded / not
  applicable) — **computed from its showings and `no_financial_activity`, not stored** — same
  pattern as the existing Event Hub completeness checklist (9.169's `has_programmer`,
  `has_copy`, etc., in `events.py`'s `completeness` dict).
- Revision history on corrections — follow the `EventTermsRevision`/`EventAuditLog` precedent
  (9.163) rather than inventing a third audit pattern. Every overwrite of a line item or
  attendance figure should be attributable and reversible in the audit trail, matching Persona
  B's "correct without destroying the original" requirement.

#### Screens

- **Event-edit form** (`EditEventView` / `form_event.html`): the `no_financial_activity`
  checkbox already exists here (9.169) — no new screen needed for Persona C.
- **Per-showing settlement entry**, on the Event Hub (`view_event_privatedetails.html`),
  alongside the existing showing cards — not a new standalone destination. This is Persona A's
  "single, obvious way in", reached from wherever they already are after a showing. It should
  read 9.54's structured cost terms (fee, split, minimum guarantee) rather than ask for them
  again, and give immediate feedback: does tonight's take look like it crossed the minimum
  guarantee.
- **Event-level settlement summary**, rolling up its showings, on that same Hub page alongside
  the existing cost-terms display and the `EventTermsRevision` panel.
- **Finance-facing review screen**, new: date-ranged (the month, matching Finance's existing
  rhythm — see scoping doc Evidence B), listing every event/showing in the window with its
  settlement status, drill-down and correction, distributor-payment tracking. This is where
  correction rights live, per the core tension above — not on Persona A's entry form.

#### Deliberately open, not decided by this entry

- **Whether PRS/PPL performer-registration status is in scope for MVP.** The user-stories doc
  flags this explicitly as unresolved rather than defaulting either way: PRS/PPL reporting has
  already stalled on paper, so a mandatory structured field here might just move the same gap
  into a different, equally skippable place. If built at all, it should be optional, not a
  blocker in the settlement critical path. Decide at implementation time, not in this spec.
- The exact shape of the category-tag picklist for ticket line items (a starting list is given
  above — advance / door / concession / guest list / other — treat it as a draft, not final).
- Whether "settlement recorded" status surfaces anywhere on the public or volunteer-facing side,
  or stays entirely internal/Finance-facing. Default assumption: internal-only, since nothing in
  either evidence pass asked for a public-facing view.

#### Visibility and rollout

- **Feature-flagged**, following the `structured_cost_terms_enabled` precedent from 9.54 —
  ships dormant, a `SiteConfiguration.*_enabled` field turns it on per-site.
- **Visibility configurable via Site Settings**, not hardcoded — matches the pattern used for
  every other visibility toggle in this codebase. Per the scoping doc's Answers, this is Jonny's
  own call for this prototype: Site-Settings-configurable and feature-flagged, explicitly
  revisable (ship a default, gather feedback, adjust).

**Related:** 9.54 (structured cost terms, read not re-entered by the settlement form), 9.149
(itemised budget estimate vs. actual — a different, complementary shape of financial data, not
a replacement), 9.163/9.169 (audit-trail and completeness-checklist precedents this task
reuses), 9.169 specifically for `no_financial_activity` (already built, wired here rather than
duplicated).

**Size estimate:** 🟠 L — new `SettlementLineItem`-style model + migration, Event/Showing field
additions + migration, two new UI surfaces (Hub entry point, Finance review screen) plus one
existing-screen no-op (the checkbox is already there), an audit-trail extension, a feature flag.
Roughly 40–70h; the Finance-facing review screen is the single biggest unknown inside that
range, since it's genuinely new UI rather than an addition to an existing page.
