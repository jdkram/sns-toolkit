# Closing the Event Financial Loop — Scoping Notes

**Status:** Scoping substantially complete as of 2026-09-10 (see "Answers" below). The mini
user-stories pass this file's Resume protocol calls for is now done — see
[docs/EVENT_SETTLEMENT_USER_STORIES.md](EVENT_SETTLEMENT_USER_STORIES.md). One piece of the design
below already exists in code, built as a side effect of 9.169 (`docs/tasks/events-and-rota.md`):
`Event.no_financial_activity`, the checkbox described under "Refinement, same day (2026-09-10)"
below. It currently only gates 9.169's programmer hard block and the cost-terms/terms-length
requirement (see `EventForm.clean()`) — it does **not** yet suppress any settlement-actuals
requirement, since that feature (per-Showing attendance/revenue/settlement recording) doesn't
exist yet. The rest of this scoping — the settlement schema itself — is still nothing designed or
built. Next step is a proper task-file entry (`docs/tasks/finance.md`) — see Resume protocol.

---

## Why this exists

Raised 2026-09-09: the toolkit tracks an event from idea through programming approval to a public,
staffed, ticketed listing — but the trail stops there. Nothing records what actually happened
afterwards: how many people came, how much money came in, what was actually paid out, whether a
distributor's minimum guarantee was triggered. Right now that information exists in three
disconnected places — a physical paper book (PRS/PPL reporting, ticket counts by price band, bar
takings), a manual reconciliation someone in the Finance Collective does by hand, and Jonny's
personal `sns-analysis` pipeline, which reconstructs an *approximate* picture after the fact from
TicketSource/EPOSnow exports and can never see cash door takings at all (documented in that
project's own `HANDOFF.md`).

The goal is to replace the paper book with something in the toolkit, close to real-time, visible
to more than one person — genuinely closing the loop rather than adding another reconstruction
layer. Full context and the reasoning behind that framing: see the conversation this file was
drafted from, and `~/.claude/projects/-home-jdkram-code-sns-toolkit/memory/project_event_financial_loop.md`.

## What's already true (established, not to re-derive)

- `Event` already has structured *planned* deal terms (task 9.54, shipped 2026-06-11):
  `cost_type`, `cost_distributor`, `cost_flat_fee_gbp`, `cost_fee_includes_vat`,
  `cost_percentage_split`, `cost_minimum_guarantee_gbp`, `cost_total_gbp`, `cost_rider_notes`,
  sound engineer fields. Gated behind `SiteConfiguration.structured_cost_terms_enabled`. An
  `EventTemplate` mirrors the same fields for pre-population (also 9.54).
- Change history on those fields already exists: `EventTermsRevision` (task 9.71), a signal-driven
  audit log, with a UI panel on `view_event_privatedetails.html`. Any new "settlement" work should
  probably follow this precedent rather than inventing a new audit pattern. Task 9.163
  (2026-09-10) added a second, adjacent precedent — `EventAuditLog` — for lifecycle events that
  aren't a field snapshot (created/status-changed/confirmed). A settlement feature will likely
  want to log against one or both of these rather than invent a third audit table.
- Nothing anywhere records *actuals*: no attendance field, no revenue field, no settlement record,
  on `Event`, `Showing`, or anywhere else in the diary app.
- This branch (`sns_2026_overhaul`) is not in production. Production is still on the pre-rewrite
  branch, so none of 9.54/9.71/9.163 exist for the Finance Collective today regardless of what
  this branch has built.
- The stage-tracker idea (visual "where is this event in its life" indicator) is agreed to live
  only on the Event Hub page — not baked into the public site or the design system generally. Not
  scoped further than that agreement.
- `docs/USER_STORIES_PASS.md`'s persona list and priority ranking (chunk 3) is confirmed settled
  and explicitly not to be reopened. None of its seven personas is "does the accounts" — this
  workstream needs its own task-file entry, not folding into that audit.
- **Existing formulae already in informal use org-wide** (not just one volunteer's private
  workaround — see Evidence below): ticket income from TicketSource = gross ÷ 1.2 (strips 20%
  VAT); bar/café contribution = EPOS net sales for that category × 50% (a flat margin assumption,
  not real per-product markup, but the same assumption the cinema's own annual financial analysis
  uses — reasonable for the toolkit to bake in as a first-pass default rather than waiting for
  real per-product margins that don't exist anywhere today).
- **Three distinct settlement shapes, not one**, matching three already-distinct `Event` states:
  - *Film screening*: TicketSource-heavy, licence cost is usually a known ~£87–100 standard rate
    (Park Circus/Filmbank terms) even when not itemised, single gross-take figure historically
    (no price-band breakdown recorded on paper for films).
  - *Volunteer gig* (`cost_type` other than hire): the majority (~67%, see Evidence) sell no
    tickets through TicketSource at all — cash/door only. Direct costs are whatever's itemised in
    the terms (artist fee, sound engineer, travel, accommodation, rider) — this already maps onto
    the 9.54 structured fields.
  - *External/outside hire* (`Event.outside_hire=True`): a fundamentally different model — the
    promoter keeps ticket income and runs their own box office; the venue only ever sees the hire
    fee and bar takings. These draw much larger crowds on average and need a far simpler
    settlement record (hire fee + bar only, no ticket breakdown).

## Evidence gathered 2026-09-10

Two sources, both anonymised per the Gotchas below — no volunteer is named in what follows even
though the original material (photos, emails) did name people.

### A. Six real filled PRS/PPL book pages + the film-screening ledger (photos)

The "paper book" is actually **two different recording systems**, not one:

1. **A per-gig PRS/PPL form.** Fields: who filled it in, the volunteer programmer or outside
   hirer's name, event date, title, event type (gig/club night/cabaret-comedy/other), any artists
   not already on record, an advance-vs-door ticket sales section, a VAT-on-tickets yes/no (for
   hirers), which performers are PRS/PPL-registered, and whether performers are volunteers/
   amateurs. Recorded **once per event** (a single date field; no multi-night example seen).
2. **A running ledger for film screenings**, in a completely different format: a plain table of
   `Date | Title | Attendance | Gross Take | Net Take`, one row per **showing**, with Net Take
   derived from Gross via a fixed, written-down formula (`Net = Gross × 100/120`, rounded to whole
   pounds, "no pennies"). Page totals summed by hand periodically.

Concrete findings that change how a digital replacement should be designed:

- **The gig form's ticket-sales section has no fixed schema, and never has.** Every one of six
  real filled examples invented its own breakdown: full/concession door pricing; online-vs-door
  with different unit prices and a combined total; three different door price tiers plus a free
  guest-list count with no total computed; a correction crossed out mid-calculation. **Two of the
  six left the whole ticket-sales section blank.** A fixed set of database columns (e.g.
  `advance_count`, `door_count`) would not match how this is actually filled in — it needs a
  flexible list of price-band line items (arbitrary "N tickets @ £X" rows, freely added), matching
  what Jonny's already concluded independently (see Answers, Q3).
- **No bar takings anywhere on the gig form.** Confirmed not tracked at the individual-event level
  on paper at all, for gigs.
- **Who fills it in varies**, and it is often *not* the programmer: several samples were filled in
  by a different volunteer "for" the named programmer/hirer, implying after-the-fact box-office
  reconciliation rather than same-night entry by the person running the event.
- **No structural link to a toolkit Event/Showing ID** — just free-text title + date, sometimes
  with the date field left blank entirely. Any legacy-data import would need fuzzy matching, not
  exact IDs, and should expect some records to be unmatchable.
- The film ledger itself has hand-corrected errors in the samples seen (a struck-through duplicate
  row, a corrected total) — the bar to clear for "closes the loop" is a genuinely messy,
  error-prone paper process today, not an idealised one.

### B. Correspondence and financial-analysis materials (email, `vol@jdkram.net`)

- **The PRS book is, in Jonny's own analysis, "the most reliable source" for gig door
  attendance/cash income** — more reliable than the TicketSource/EPOS-derived pipeline — precisely
  *because* most gigs never touch those digital systems at all: **67% of volunteer gigs (59 of 88,
  Jan 2024–Apr 2026) sold no tickets through TicketSource whatsoever.** This is the single
  strongest argument for digitising the book directly rather than continuing to invest in
  inferring gig economics from TicketSource/EPOS exports.
- **Reporting is not currently happening reliably by anyone.** Direct quote (anonymised): *"there
  are PRS reports, but I've yet to get my mitts on them. They're either not getting digitised from
  the book, or finance have them and don't circulate."* This contradicts the previous framing in
  this file ("someone in the Finance Collective does reconciliation by hand" implying a working,
  if manual, process) — the more accurate picture is that reporting has stalled, not that it's
  working slowly. No single confirmed person currently does this end-to-end.
- **Where reconciliation *has* happened, it's been a large manual batch, long after the fact**: one
  Finance Collective volunteer's project (mid-2026) added cost/bar-sales data to "the ticket sales
  data sent to PRS/PPL for all gigs last year" — i.e. a year-plus lag between event and
  reconciliation, done as a one-off catch-up exercise, not a running process.
- **Reconciling two independent estimates of the same event is not formulaic, it's manual
  line-by-line comparison, with cash/bank-reconciled figures always winning.** Jonny's own pipeline
  numbers were checked event-by-event against another volunteer's bank-reconciled figures for a
  string of gigs; door cash bypassing EPOS was "the biggest source of mismatch"; wherever a
  verified figure existed it was used over the pipeline's estimate, every time. **This is strong
  evidence that the toolkit's role should be structured *data entry* backed by whoever actually
  handled the cash/bank reconciliation, not a clever inference pipeline** — echoing the framing
  already agreed in Answers Q3 below.
- **A volunteer expressed direct interest in taking on some reporting duties**, describing an
  ideal cadence of roughly **monthly**, semi-automated (a pipeline handling what it can, a human
  checking/annotating fields it can't — e.g. flagging a private hire or a charity-split night) —
  useful evidence for both Q2 (cadence, still not firmly confirmed org-wide) and for who the
  "enters data" persona in a future user-stories pass might actually be: not necessarily the
  programmer, not necessarily existing Finance Collective members either.
- **The org already runs a monthly finance cadence for something adjacent**: a "monthly finance
  explainer" session (45 min, zoom or in-building) exists, separate from PRS/PPL reporting
  specifically but establishing monthly as an already-normal rhythm for finance communication at
  Star and Shadow.
- **Two data-driven infographics exist** (`sns-finances-infographic.html`,
  `sns-event-economics.html`, both March/May 2026) with hard aggregate numbers, useful context for
  the "nudge toward sustainability" framing in Q4:
  - Org-wide: ~£100k/year running costs; bar sales are the largest single net income stream (45%
    of costs covered); **volunteer event programming is a net cost overall** — it costs more than
    it brings in from ticket sales, which is *already* publicly stated org context, not new
    sensitive information this feature would be revealing for the first time.
  - Per-event (median, where measurable): a film screening nets roughly +£50 on ticket income +
    bar contribution minus licence cost. A volunteer gig has a median *deficit* of roughly −£204 on
    ticket income + bar contribution vs. direct costs (artist/sound/travel/accommodation/rider). Of
    the 23 gigs (out of 88) with enough data to compute this at all, 8 showed a surplus and 15 a
    deficit — **gigs losing money is the median outcome in the measurable sample, not an
    exceptional or anecdotal complaint.**
  - Neither volunteer time nor building overhead is allocated to individual events anywhere today
    — an explicit, already-agreed scoping boundary this feature should keep, not attempt to solve.
  - External hires draw much bigger crowds (median 181 attendees) than volunteer gigs (median 38)
    but the venue only ever sees the hire fee and bar takings from them — confirms the three-shape
    split above.

## Answers (2026-09-10)

Answered directly by Jonny, informed by the Evidence above. Superseds the original "Open
questions" list; kept in the same grouping for continuity.

### 1. What the paper book actually contains — answered, see Evidence A above.

### 2. Who does what, and when

- **Unconfirmed who, if anyone, currently does this reliably** — the Evidence above suggests
  reporting has actually stalled rather than being handled by one identifiable person. Not worth
  further digging; the toolkit design shouldn't assume a specific current owner exists.
- **Cadence unconfirmed precisely**, but a monthly rhythm is plausible: the org already runs a
  monthly finance session, and a volunteer independently proposed monthly as a workable reporting
  interval. Design for a monthly-ish batch cadence as the default assumption, not a stricter
  per-event deadline.
- **Reconciliation happens later, via different means, outside the toolkit** — e.g. film licence
  payments go directly to the distributor via their own web portal. The toolkit's job is to
  capture accurate *inputs* close to the event, not to become the payment system itself.
- **Data entry: ideally the programmer, on the night; box office entry would be excellent too.**
  The aspirational end-state is everything sold through TicketSource — including door sales and
  volunteer sign-in — but people are currently set in their ways (printed ticket lists marked by
  pen, till sales, manual tallying), and there's genuine merit to that low-tech approach's
  resilience (it doesn't depend on a device, a network connection, or the app being usable by
  every volunteer on a busy door). **Design for manual entry as the primary path, not as a
  fallback** — don't build on an assumption that TicketSource adoption for door sales will
  increase.

### 3. Scope of what the toolkit should own

- **Every event gets a settlement record by default**, including free/internal/volunteer
  screenings — those simply tick "not applicable" rather than being excluded from the model
  entirely. No conditional record-creation logic based on `cost_type`.
- **The toolkit owns both the inputs and the distributor payment itself** (was it invoiced, was it
  paid) — not just the numbers Finance later uses elsewhere. This is a wider scope than the
  original framing considered ("only the inputs... bookkeeping-proper begins elsewhere").
  Reconciliation with the distributor still happens externally (per Q2), but the toolkit should
  record the outcome of that, not just the raw inputs that fed into it.
- **Design method: derive the schema from what a programmer needs to do and what Finance needs to
  do, from a fresh user-stories pass — not from the paper form's fields directly.** The paper
  form's fields are a starting point for what data exists, not a template for the digital
  workflow.
- **Flexible price bands are a hard requirement**, confirmed independently by both Jonny's
  instruction and Evidence A: a fixed set of price-tier columns cannot represent how ticket sales
  are actually recorded today. The settlement model needs an arbitrary list of
  `{description, count, unit_price}` line items per showing, not fixed fields.
- **Refinement, same day (2026-09-10):** the "tick not applicable" above happens at settlement
  time, after the fact, once per event. For the large volume of genuinely non-financial rota items
  (Cleaning Club, maintenance jobs, internal meetings, work parties), that's still one avoidable
  step too many. Instead, flag this **upfront, at the terms-entry stage** — a checkbox alongside
  the cost terms (e.g. "This event has no financial activity to record") — and have that flag
  suppress/nullify the settlement reporting requirement on every `Showing` under that event, so
  the financial fields never appear for these at all. Goal: don't let the financial-loop feature
  add friction to getting low-stakes items onto the rota, especially maintenance work, where ease
  of entry matters more than anything else.
- Bar/café attribution when multiple events overlap in a day remains genuinely unsolved (carried
  over from the original framing) — likely still an acceptable MVP gap, covered by a single
  manually-entered contribution figure per event rather than real till attribution.

### 4. Visibility and governance

- **Jonny's call, for this prototype** — not escalated to the Finance Collective at this stage.
  Explicitly revisable: ship a default, gather feedback, adjust up or down.
- **Must be configurable via Site Settings** (`SiteConfiguration`), matching the pattern already
  used for other visibility/feature toggles in this codebase, so the actual venue running this can
  change the default without a code change.
- **This entire workstream must be feature-flagged** (a new `SiteConfiguration.*_enabled` field,
  following the `structured_cost_terms_enabled` precedent from 9.54) — ships dormant, doesn't
  affect anyone until a site turns it on, consistent with this codebase's general approach to
  speculative/high-impact features.

### 5. Relationship to `sns-analysis`

- **`sns-analysis` is an archived project.** The explicit goal is for this toolkit feature to
  **obviate it** — not to stay independent, not merely to "point it at" the new data. Once real
  settlement data exists in the toolkit, `sns-analysis`'s LLM-based cost extraction and
  till/TicketSource reconciliation should become unnecessary, since the toolkit will hold ground-
  truth data `sns-analysis` was only ever approximating.

## Non-questions (deliberately not asking)

- **Granularity default:** actuals live at `Showing` level (attendance, price-band line items, a
  bar contribution figure per night) rolling up to an `Event`-level settlement summary — confirmed
  by both the paper book's per-showing film ledger and the per-event gig form; gigs (recorded once
  per event on paper) likely need this collapsed to a single implicit showing in the common case
  of a one-off gig, but the model should be showing-level throughout for consistency with films
  and multi-night runs.
- **Stage-tracker placement:** already agreed — Event Hub only.
- **Three settlement shapes** (film / volunteer gig / external hire) — confirmed by Evidence B;
  the schema should accommodate all three without forcing external hires through the same
  ticket-price-band structure gigs and films need.

## Gotchas

- **Don't name specific volunteers in this file.** It lives in a public repo (see the "Publishing
  rules" in `CLAUDE.md`). Refer to roles ("Finance Collective", "a volunteer", "whoever does
  PRS/PPL reporting"), not individuals — this applies even to real quotes: paraphrase or genericise
  rather than reproduce identifying phrasing.
- The two infographics referenced in Evidence B contain real, specific financial figures about
  Star and Shadow's finances (£100k/year running costs breakdown, per-event medians). These are
  aggregate/organisational figures, not personal data, and are already shared with the wider
  membership (linked from a `finance@starandshadow.org.uk` email and a public quarterly
  spreadsheet) — safe to reference here, unlike anything naming an individual volunteer.

## Resume protocol

1. Read this file in full before doing anything else, then
   [docs/EVENT_SETTLEMENT_USER_STORIES.md](EVENT_SETTLEMENT_USER_STORIES.md).
2. Scoping and the user-stories pass are both complete — the next step is a proper task-file
   entry: a new `docs/tasks/finance.md` domain file, next available `9.X` number, sized per the
   existing convention (🟢 XS – 🔴 XL), derived from the user-stories pass above, not lifted
   directly from this file's raw evidence.
3. That task-file entry should specify: the showing-level settlement model with flexible
   price-band line items, the three-shape split (film/gig/hire), the feature flag + Site Settings
   visibility control, and how it hooks into the existing `EventTermsRevision`/`EventAuditLog`
   audit precedents.
4. This file is now linked from `CLAUDE.md`'s "Next planned workstream" section (done 2026-09-10,
   same session as this evidence pass) — keep that pointer current once the task-file entry exists.
