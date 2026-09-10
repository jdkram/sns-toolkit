# Closing the Event Financial Loop — Scoping Notes

**Status:** Pre-scoping. Nothing designed, nothing built. This file exists to hold open questions
until there's time to answer them properly — it is deliberately a list of things to ask Jonny,
not a spec. A cold session should read this and know exactly what's still unknown, rather than
guessing and building the wrong thing.

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
  probably follow this precedent rather than inventing a new audit pattern.
- Nothing anywhere records *actuals*: no attendance field, no revenue field, no settlement record,
  on `Event`, `Showing`, or anywhere else in the diary app.
- This branch (`sns_2026_overhaul`) is not in production. Production is still on the pre-rewrite
  branch, so none of 9.54/9.71 exist for the Finance Collective today regardless of what this
  branch has built.
- The Finance Collective's actual workload is, in practice, concentrated in one or two people
  doing most of the reconciliation. One of them is believed ("I think", per Jonny) to be the
  person who reports PRS/PPL figures onward — not confirmed, and deliberately not named here (see
  Gotchas).
- The stage-tracker idea (visual "where is this event in its life" indicator) is agreed to live
  only on the Event Hub page — not baked into the public site or the design system generally. Not
  scoped further than that agreement.
- `docs/USER_STORIES_PASS.md`'s persona list and priority ranking (chunk 3) is confirmed settled
  and explicitly not to be reopened. None of its seven personas is "does the accounts" — this
  workstream needs its own task-file entry, not folding into that audit.

## Open questions

Grouped by theme. Answering these is the actual next session's job before any schema or UI gets
designed. Resist the temptation to guess plausible answers and move on — several of these change
the shape of the data model, not just field names.

### 1. What the paper book actually contains

- Can I see (or have described precisely) a real filled page from the current PRS/PPL book?
  Everything below depends on what's actually recorded there rather than what seems plausible.
- Does it record only ticket counts per price band, or also bar takings, door cash, and anything
  else, per the earlier description ("tickets sold at each price, and money on the bar")?
- Is it recorded per showing/night, or once per event/booking (relevant for multi-night runs,
  touring shows across several dates)?
- Who physically writes in the book, and when — on the night (box office volunteer), or after
  (someone reconciling from till + TicketSource)?

### 2. Who does what, and when, in the new process

- Confirm who actually reports PRS/PPL onward, and to whom, and how often (per event, monthly
  batch, quarterly).
- Is settlement (recording actuals + resolving the deal, e.g. minimum-guarantee top-up) one
  action by one person, or a small workflow — e.g. box office volunteer logs the night's numbers,
  someone else later confirms the distributor payment?
- Does replacing the paper book mean the Finance Collective would enter data directly into the
  toolkit themselves, or would someone else (box office volunteers, programmers) enter raw numbers
  with Finance reviewing/exporting only? This changes who the form needs to be usable by.
- Is there a deadline or recurring reporting cadence (e.g. a quarterly PRS/PPL return, an annual
  accounts close) that would make this urgent to land by a particular date, or is it open-ended?

### 3. Scope of what the toolkit should own

- Does every event need a settlement record — including free/internal/volunteer screenings
  (`cost_type = internal`) — or only events where money actually changes hands with an external
  party (distributor, performer, hirer)?
- Should the toolkit record the *distributor payment itself* (was it invoiced, was it paid), or
  only the inputs (actual revenue, attendance) that Finance then uses to calculate that payment
  elsewhere (a separate accounts system/spreadsheet)? I.e. where does the toolkit's responsibility
  end and bookkeeping-proper begin?
- Bar/café takings attribution: `sns-analysis` flags this as genuinely unsolved when multiple
  events overlap in a day. Is a single manually-entered "bar contribution for this event" figure
  (as presumably already done by hand on paper) an acceptable MVP, or does this need to wait for
  real till attribution?

### 4. Visibility and governance

- Who actually gets to decide the visibility model — is this Jonny's call as a design decision,
  or does it need to go to the Finance Collective (or a wider meeting) given it touches how
  transparent the collective is about money and, implicitly, about individual programmers'
  events?
- Is per-event attendance/revenue data sensitive in a way that needs restricting to a Finance
  role, or would an aggregate-only view open to all volunteers (no names attached) already
  satisfy the "nudge toward a culture of sustainability" goal without needing a restricted tier
  at all?

### 5. Relationship to `sns-analysis`

- Once real settlement data exists in the toolkit, should `sns-analysis` be pointed at it (retiring
  the LLM-based cost-extraction step and some of the till/TicketSource reconciliation), or should
  the two stay independent indefinitely?
- Is there any appetite for reusing `sns-analysis`'s existing schema thinking (`fact_event_costs`,
  `dim_event_terms`) as a starting point for the toolkit's own settlement model, or should the
  toolkit design start fresh given it will be structured data entry rather than extraction?

## Non-questions (deliberately not asking)

- **Granularity default:** actuals will very likely need to live at `Showing` level (attendance,
  revenue by price band, bar contribution per night) rolling up to an `Event`-level settlement
  summary, since the paper book's stated purpose (PRS/PPL, price-band reporting) is inherently
  per-performance. Worth confirming once question 1 is answered, but not worth a dedicated
  question — it falls out of the paper book's actual structure.
- **Stage-tracker placement:** already agreed — Event Hub only.

## Gotchas

- **Don't name specific volunteers in this file.** It lives in a public repo (see the "Publishing
  rules" in `CLAUDE.md`). Refer to roles ("Finance Collective", "whoever does PRS/PPL reporting"),
  not individuals — even though Jonny named names in conversation while scoping this.

## Resume protocol

1. Read this file in full before doing anything else.
2. Do not propose a schema, model, or UI until the "Open questions" section above has actual
   answers from Jonny, not assumed ones — the whole point of this file is to avoid guessing.
3. Once answered, the natural next step is a proper task-file entry (new `docs/tasks/finance.md`
   domain file, next available `9.X` number, sized per the existing convention) rather than
   building directly from this file.
4. This file should be linked from `CLAUDE.md` once it has real content worth a cold session
   finding — currently linked nowhere; add that link in the same commit that adds any real
   answers, so it doesn't go stale and invisible like an unlinked plan would.
