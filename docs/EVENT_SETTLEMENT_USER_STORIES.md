# Closing the Event Financial Loop — Mini User-Stories Pass

**Status:** Complete, 2026-09-10. Input to the next step: a `docs/tasks/finance.md` task-file
entry (see `docs/EVENT_SETTLEMENT_SCOPING.md`'s Resume protocol). This file is workflow analysis,
not a schema proposal — the field/screen list at the end is what falls out of the workflow, kept
deliberately loose for whoever writes the actual spec.

**Read `docs/EVENT_SETTLEMENT_SCOPING.md` first.** Everything here builds on its Evidence and
Answers sections — the three settlement shapes, the flexible-line-items requirement, the
terms-entry checkbox decision, the "manual entry is the primary path" call. This file doesn't
re-argue any of that; it works through what those decisions mean for the people actually using
the screens.

---

## Persona A — the volunteer programmer, wrapping up their own event

This is the highest-friction case, because it's the one person in the whole loop who is doing
this *in addition to* the actual work of running a gig, tired, at the end of a long night, not as
their primary job. Everything else in this persona's story follows from that one fact.

### What they need, in order

1. **Nothing extra to remember.** Whatever they agreed at booking time — fee, split, minimum
   guarantee — should already be sitting in front of them, not something they have to recall or
   re-enter. This is the 9.54 structured cost-terms data; the settlement screen should read it,
   not ask for it again.
2. **A single, obvious way in**, reached from wherever they already are after a showing. The
   natural home is the Event Hub (`view_event_privatedetails.html`, URL `edit-event-details-view`)
   — the page that already lists each showing as a card and already hosts the completeness
   checklist and the `EventTermsRevision` change-history panel. A settlement prompt belongs there,
   next to the showing it's for, not in a separate "financial reporting" area of the site. If
   finding the form is its own task, a tired volunteer at 1am will skip it, exactly as roughly a
   third of the paper form's ticket-sales sections got left blank.
3. **A rough attendance number.** Optional precision — a headcount guess is fine, and should be
   accepted as fine.
4. **Ticket sales as free-form line items**, one blank row to start, "add another" to extend.
   No fixed columns, no forced categories. This is not a nice-to-have — Evidence A in the scoping
   doc shows every one of six real paper forms invented its own breakdown, and two left the
   section blank entirely. A digital form that insists on filling in "advance" and "door" as
   separate mandatory numbers will not match how anyone actually counts a cash box at closing
   time, and will get abandoned the same way the paper form sometimes was.
5. **Bar/café contribution — clearly optional, possibly not their job at all.** The paper form
   never asked for this from the programmer, because the programmer usually can't see till data.
   Forcing it here means forcing a blank field, or worse, a guess presented as a fact.
6. **Immediate, useful feedback**, not just data entry for someone else's benefit: does tonight's
   take, plus what's already on record, look like it crossed the minimum guarantee? This is the
   one piece of information that's actually useful to the programmer themselves, and giving it to
   them is the best incentive to fill the form in at all.
7. **Submit, and be done.** The record should be editable later (by them or by Finance), but
   submitting shouldn't feel like signing something binding — no forced reconciliation to the
   penny, no blocking validation on fields they genuinely don't have numbers for.

### What makes them not bother

- Being asked for a number they don't have (till data, exact reconciled cash) and being blocked
  from submitting without it.
- A fixed grid of price tiers that doesn't match how they actually sold tickets that night.
- Having to hunt for the form, or having to re-enter terms they already agreed weeks ago.
- Doing this on a phone, in a dark venue, at 1am, on a page that isn't built for that.
- Not knowing whether it's actually expected of them — ambient obligation without a clear "this
  takes two minutes and here's why it matters" framing.

---

## Persona B — Finance, trying to get an accurate monthly picture

This persona's job starts roughly where Persona A's ends, and on a much longer cycle: the
Evidence in the scoping doc points to something close to the org's existing monthly finance
rhythm, not a per-event deadline.

### What they need, in order

1. **A view scoped to a time window** (the month), listing every event/showing in it with a
   settlement status — recorded, partial, not recorded, or flagged not-applicable. The absence of
   a submission has to be visible as a gap, not silently invisible, or the loop doesn't actually
   close; it just moves the missing data one layer down.
2. **Comparable data across events.** A free-text line item that says "40 @ door" is fine for the
   programmer who wrote it, but Finance needs to be able to look across a month of these and make
   sense of them in aggregate — total attendance, total gig income, licence costs due. This is the
   direct tension with Persona A (below).
3. **The ability to correct, not just view.** Per the scoping doc's Evidence B, reconciliation
   against bank/till figures already happens as a manual, line-by-line process, with the
   bank-reconciled figure always winning over any estimate. Finance needs to be able to overwrite
   a programmer's door-count guess with a verified figure, weeks or months later, without losing
   the original — the same audit-trail pattern `EventTermsRevision` already establishes for cost
   terms.
4. **A place to record the distributor-payment outcome** — invoiced, paid, date — separate from
   the ticket/bar figures, per the scoping doc's Answers Q3 (the toolkit owns this too, not just
   the raw inputs).
5. **A way to flag and annotate exceptions** — the volunteer interested in reporting duties
   specifically mentioned "a private hire or a charity-split night" as things a human needs to
   annotate, not something a formula can infer.
6. **Something exportable or summarisable**, for PRS/PPL reporting and the existing monthly
   finance-explainer session — the destination this data is ultimately for.

### What makes them not bother, or lose trust in the data

- No visibility into what's missing — if unsubmitted settlements are invisible, Finance can't
  tell the difference between "nothing happened" and "nobody recorded it."
- Free text with genuinely no structure at all, at the point Finance needs to aggregate it — the
  flip side of Persona A's needs (see Conflicts, below).
- No way to correct a figure without destroying the original entry — this matters because the
  paper-book evidence shows corrections are normal (a struck-through duplicate row, a
  crossed-out mid-calculation total), not exceptional.

---

## Where Persona A and Persona B genuinely conflict

This is the real design tension in the feature, not a detail to smooth over:

| Tension | A wants | B wants | Resolution this implies |
|---|---|---|---|
| Ticket line items | Free text, zero friction, add-a-row | Comparable, aggregatable data | Keep line items free-text by default, but let each row optionally carry a category tag from a short picklist (advance / door / concession / guest list / other). Never require it. A tag Finance can fill in later is nearly as useful as one entered on the night. |
| Editability | Submit once, done | Correct months later, repeatedly | Settlement records stay editable indefinitely, with a revision history (following `EventTermsRevision`), not a "finalised, locked" state. A's submission is a first estimate, not a contract. |
| Fields owned | Only wants to enter what they can see (door, headcount) | Wants a complete picture including bar takings | Split ownership explicitly: bar contribution is a field the programmer *can* leave blank, filled in later by whoever does till reconciliation — don't make it block A's submission. |
| Precision | Wants to submit an honest guess and move on | Wants numbers that add up | Don't validate for exactness. A rough total that doesn't reconcile to the penny is still far better data than nothing, and matches the paper process's own error-tolerant reality (hand-corrected totals, struck-through rows). |

The general shape of the resolution: **the programmer's form and Finance's view are not the same
screen showing the same fields with different permissions** — they're a fast, forgiving entry
form feeding a slower, more demanding review process, with correction rights living on the review
side, not the entry side.

---

## Where a "clean" digital design would be worse than the paper process

Worth stating plainly, because the instinct when building a database-backed replacement for a
paper form is to tidy it up — and several of the tidiest-looking choices here would actively
break the thing that currently, if imperfectly, works:

- **Fixed price-tier columns.** Already ruled out in the scoping doc's Answers, but worth
  restating as the clearest example of the pattern: a schema that looks complete on a whiteboard
  doesn't match six for six real examples of how this is actually filled in.
- **Forcing exact bar/till attribution per overlapping event.** The paper process never solved
  this either — a single rough per-event figure, entered by whoever has till access, is an
  honest MVP, not a shortcut. Building anything more precise (real per-product markup, exact
  split by timestamp) is solving a problem nobody currently solves and nobody's asked for.
- **Hard validation that blocks submission on incomplete data.** The paper form tolerates blank
  sections; a digital form that throws an error on a blank ticket-sales section is stricter than
  the process it's replacing, in a system where two out of six real examples used exactly that
  blank state.
- **A locked, "finalised" settlement status once submitted.** Looks like good data-integrity
  practice; is actually wrong for this data, because bank/till figures overriding estimates
  *after the fact* is the normal, expected path per Evidence B, not an edge case.
- **A mandatory, structured PRS/PPL performer-registration sub-form**, mirroring the paper form's
  own registration-status fields. The scoping doc doesn't rule this in or out for MVP, and it's
  worth flagging rather than assuming: the evidence that PRS/PPL reporting has *already stalled*
  on paper suggests that making this a mandatory, structured field wouldn't fix the underlying
  compliance gap, just move it into a different, equally skippable place. If it's wanted at all,
  it belongs as an optional field, not a blocker in the settlement critical path — worth an
  explicit decision in the task-file spec rather than a default assumption either way.
- **Building the primary entry path around TicketSource data.** Auto-pulling TicketSource figures
  looks like it removes double-entry work, and might be worth adding later as a pre-fill for the
  minority of events that do use it — but per the scoping doc's Q2 decision, the majority of gigs
  never touch TicketSource at all. A design that treats it as the backbone rather than an
  optional shortcut would misrepresent how most events actually sell tickets.

---

## Persona C — booking a non-financial rota item (maintenance, cleaning, a work party)

This persona should, by design, barely notice this feature exists. The scoping doc's Answers
already settled the mechanism — a checkbox at terms-entry, ticked upfront, suppressing the
settlement requirement for every showing under that event rather than a per-showing
"not applicable" tick after the fact. One thing worth sanity-checking against that design intent,
now resolved by checking the actual code, and one still worth flagging:

**Resolved: the checkbox lands on a screen this persona already visits, because there is only
one screen.** "Terms-entry" turns out not to be a dedicated page — the cost-terms fields
(`cost_type`, `cost_distributor`, `cost_flat_fee_gbp`, …) are just three fields among many
(copy, media, tags, film linking, budget lines) on the single general-purpose event-edit form
(`EditEventView`, `form_event.html`, URL `edit-event-details`) that every event, financial or
not, already has to pass through to be created or edited at all. So the checkbox doesn't add a
new screen for this persona — it adds one field to a form they were already going to submit.
The remaining design question is just *placement on that already-long form*: it needs to sit
somewhere a maintenance-job organiser will actually see it (near the top, or near whatever
field they're already filling in for a non-financial event) rather than buried after the
budget-line fields a cleaning-club entry will never touch.

**The genuinely ambiguous case: a bake sale during a work party.** An event that's overwhelmingly
non-financial in purpose but has some small, real financial activity attached. Two failure modes
to design against:

- If the checkbox is ticked in advance (work parties usually are non-financial) and the bake sale
  wasn't anticipated, that £40 simply vanishes from the record with no prompt to reconsider —
  the more disruptive failure, because it's silent.
- If organisers are expected to correctly predict "will anything financial happen" at
  terms-entry time, they'll sometimes guess wrong in both directions, and re-litigating that
  guess needs to be trivial, not a one-way gate.

The implication: **the checkbox should be freely reversible on the same terms-entry screen** (not
locked once saved), and its label should set expectations honestly — something like "no
financial activity *expected*" rather than a flat assertion — so a wrong guess is a two-second fix
rather than a dead end. Given the friction-reduction goal explicitly outweighs settlement
completeness for this persona, the right default when in doubt is to let false negatives (a small
bake sale goes unrecorded) pass silently rather than adding any extra prompt or confirmation step
that a maintenance-job organiser would have to click through every time.

---

## What falls out of this — not a schema, just the consequence

Framed as what the workflow above implies exists, for whoever writes the actual
`docs/tasks/finance.md` spec to take or leave:

**Screens implied:**
- The existing event-edit form (`EditEventView` / `form_event.html`) gains the "no financial
  activity expected" checkbox, placed near the top rather than after the budget-line fields.
- A per-showing settlement entry point on the Event Hub (`view_event_privatedetails.html`),
  alongside the existing showing cards — not a new standalone destination.
- An event-level settlement summary, rolling up its showings, living on that same Hub page
  alongside the existing cost terms and `EventTermsRevision` change-history panel.
- A Finance-facing, date-ranged review screen: status per event/showing (recorded / partial /
  not recorded / not applicable), drill-down and correction, distributor-payment tracking.

**Fields implied, at `Showing` level:**
- Attendance (optional, approximate)
- Ticket sales as repeatable line items: free-text description, optional category tag, count,
  unit price
- Bar/café contribution (optional, separately attributable to whoever entered it)
- Free-text notes, for exceptions Finance needs to flag (private hire, charity split)

**Fields implied, at `Event` level:**
- The "no financial activity expected" flag, freely reversible
- Distributor payment outcome: invoiced (with date), paid (with date), amount
- A derived settlement-completeness status (not stored — computed from its showings)
- Revision history on corrections, following the `EventTermsRevision`/`EventAuditLog` precedent
  rather than a new audit pattern

**Deliberately left open, for the task-file spec to decide rather than this pass:**
- Whether PRS/PPL performer-registration status is in scope for MVP at all (flagged above as a
  genuine open question, not a default lean either way).
- The exact shape of the category-tag picklist for ticket line items.
- Whether the "settlement recorded" status surfaces anywhere on the public or volunteer-facing
  side, or stays entirely internal/Finance-facing.
