# User Stories & Core Workflow Audit — Plan

**Status:** Not started. This file is the plan, written 2026-09-09, for a session where Jonny has
time to sit down and actually run it. A cold session (any agent, any day) should be able to pick
this up from this file alone — see "Resume protocol" below.

---

## State at last session (2026-09-09, second session)

- Chunks 1–3 are done, on paper, in the Findings section below. **Chunk 4 (the end-to-end
  browser walks) is the next thing and has not started.** Chunks 5–6 follow it.
- Chunk 3's priority list was put to Jonny and **confirmed as drafted**, so a resuming session
  should start walking workflow #1 rather than reopening the ranking. Jonny chose to stop
  before chunk 4 rather than start the browser walks in the same session; the agreed shape when
  it resumes is the **top three, walked in depth** rather than five walked lightly.
- Docker was up and healthy at the time of writing (`toolkit`, `mariadb`, `mailer`,
  `scheduler` all running), so chunk 4 is unblocked.
- Nothing from this session is committed.
- Git state is unchanged from the previous session: branch `sns_2026_overhaul` is 1 commit
  ahead of `origin` (`bfb7cd27`), not pushed, with the previous session's docs work still
  uncommitted. Check `git status`/`git log` before continuing, since this note goes stale as
  soon as anything else happens on the branch.
- Work from the previous session (context, not part of this workstream): docs consolidation
  (three dead docs archived, two content bugs fixed in `docs/tasks/`), a conciseness/AI-tell
  pass across the live docs (found them already largely clean, small edits only), and a deep
  editorial pass on `docs/SPEC.md` (restored a "Known limitations" section, split the
  film-programming how-to into its own doc, fixed a stale/duplicated `Room` model description
  and opened task 9.168 for the gap, reframed the £75k–£150k valuation, named the document's
  dual developer-handoff/AI-context-primer purpose as an open tension).

---

## Why this exists

Jonny wants to know which of the toolkit's workflows are the ones worth polishing hardest — the
"real smooth paths" — and to use that list to sanity-check the system's high-level architecture
against actual user needs, rather than continuing to build features breadth-first. The output of
this pass should be: a short list of the workflows that matter most, an honest read on how well
the current implementation serves them, and any architectural calls that fall out of that.

## Method (agreed 2026-09-09)

**Fast-and-opinionated first pass.** Build the persona list and candidate top workflows from
what's already documented (`SPEC.md` §2 permission model, §4 key workflows,
`docs/tasks/known-issues.md`, `CURRENT_WORK.md`'s shipped-fix history) plus Jonny's own judgement
in conversation — not a big evidence-mining exercise up front. Only reach for git-history or
issue-archaeology on the specific workflows where the fast pass leaves genuine doubt about
whether it's actually a hot path.

**Don't default to formal "As a user, I want X, so that Y" story templates for their own sake.**
The goal is a ranked list of workflows and a clear sense of what "good" looks like for each, not
a backlog artefact. A short paragraph per workflow, stating the stakes plainly, will usually beat
a rigid template.

---

## Chunks

### Chunk 1 — Draft persona list `[x]` done 2026-09-09

Starting point: `SPEC.md` §2 already lists public visitor / volunteer / programmer /
panopticon. Decide whether any of these need splitting — e.g. "prospective volunteer, not yet a
member" behaves very differently from "established volunteer" for induction-adjacent workflows,
and "the collective" as a governance stakeholder isn't the same as any individual role.

**Output:** a short persona list, one line each on what they're actually there to do.

### Chunk 2 — Candidate top workflows per persona `[x]` done 2026-09-09

For each persona, list 2–4 workflows where a *failure* has real stakes — not just things they can
technically do. Draw on:

- `SPEC.md` §4 (key workflows) as the existing candidate list.
- `docs/tasks/known-issues.md` for where real friction has already surfaced repeatedly.
- `CURRENT_WORK.md`'s history of shipped fixes, for signal on what's caused real pain before
  (e.g. the `vols_admin_address` production incident, Bug AV's induction-modal bug).

**Output:** per persona, a short ranked list (rank by stakes × frequency, not effort), one
sentence of justification each. The justification is the valuable part, not the number.

### Chunk 3 — Reconcile into one cross-persona priority list `[x]` done 2026-09-09, confirmed by Jonny

Not every persona's #1 workflow deserves equal investment. Merge into a single ordered list of,
say, the top 5–8 workflows across the whole system — the actual "smooth path" candidates.

### Chunk 4 — Walk each prioritised workflow end-to-end against the current build `[ ]` not started (next up)

For each of the top workflows: trace it through the actual running system (Docker dev instance,
in-browser), not just the spec or the code. Note every point of friction, inconsistency, or
missing affordance encountered along the way. This mirrors the existing CLAUDE.md rule to verify
rendered/interactive behaviour rather than reason from code alone — it applies doubly here, since
the whole point is lived experience, not architecture-on-paper.

### Chunk 5 — Architectural read-out `[ ]` not started

Step back and ask the high-level question: does the current architecture actually support these
workflows well, or does polish keep getting undermined by something structural (permission model,
data-model gaps, an inconsistently-applied UI pattern)? This is where an architectural decision
might actually get made, rather than just a list of small fixes.

### Chunk 6 — Feed findings back into the tracked docs `[ ]` not started

Turn findings into scoped entries in `docs/tasks/*.md` (design rationale, following existing
sizing-label conventions) and `CURRENT_WORK.md` (status/priority). Once done, retire this file to
`docs/ARCHIVE/` with a row in `docs/ARCHIVE/README.md`, following the
`MAINTAINABILITY_PASS_2026_06.md` / `QUALITY_PASS_2026_09.md` precedent.

---

## Resume protocol

A cold session picking this up should:

1. Read this file in full.
2. Check `git log` / `git status` against the "State at last session" note above and update that
   note before continuing, since it will be stale.
3. Start at the first chunk not marked done. Chunks 1–3 can happen in conversation, but their
   *output* must be written into the Findings section below before the session ends — not left
   sitting only in chat history.
4. Update the chunk status markers and the state-at-last-session block before ending the session.

---

## Findings

### Personas (chunk 1)

Seven, expanded from SPEC §2's four. The personas deliberately do not map onto the permission
tiers, because the two places the system is thinnest (people who have not joined yet, and people
who joined last month) sit either outside the login entirely or invisibly inside the "volunteer"
tier.

| Persona | Logged in? | What they are actually there to do |
|---|---|---|
| **Public visitor** | no | Find out what is on, decide whether to come, reach a ticket link. |
| **Prospective volunteer** | no | Work out what this place is, whether there is room in it for them, and how to get to an induction. |
| **New volunteer** (first ~3 months) | yes, barely | Get a working account, work out what the roles mean, take a first shift without having to ask a human. |
| **Established volunteer** | yes, weekly | Pick up shifts, check when they are on, find out who to ask about a given thing. |
| **Programmer** | yes, in bursts | Get an event from an idea to a correctly listed, staffed, ticketed showing. |
| **Coordinator** (Panopticon) | yes, in bursts | Keep the roster, the mailing lists and the member data straight; send mailouts; grant and review access. |
| **The collective** | not a login | See who holds power and why, and have an audit trail when something goes wrong. |

Three splits worth justifying:

- **Prospective volunteer, split from public visitor.** They come through the same front door
  and want a different thing. §8.12 makes the case in Jonny's own words: a public blurb per
  collective "would massively help prospective volunteers get a sense of how the cinema works",
  and might bring people in via the print room or Community Kitchen rather than the cinema.
- **New volunteer, split from established volunteer.** Same permission tier, opposite needs.
  Everything an established volunteer finds merely annoying (the rota wall of text in §8.6,
  free-text names in §8.1, no my-shifts view in §8.3) is disorienting rather than annoying in
  someone's first month, and their failure mode is silent. They do not file a bug, they just
  stop coming.
- **The collective, kept despite not being a login.** It is the only stakeholder who would ask
  for the access-transparency page, deletion logging (9.159) or GDPR erasure. Without naming it,
  those features have no persona to justify them and read as gold-plating.

Considered and rejected as separate personas: **keyholder** (a trust status held by established
volunteers rather than a distinct set of needs, though the "who do I even ask" friction in §8.12
is real, and lands below as E4) and **maintainer / successor** (a real and carefully served
audience, see CURRENT_WORK.md's "Picking this up", but a reader of the repo rather than a user of
the running system, so out of scope here).

### Candidate workflows (chunk 2)

Ranked within each persona by stakes × frequency, not by effort. The justification is the
valuable part; the ordering is a means to chunk 3.

**Public visitor**

| | Workflow | Why it matters |
|---|---|---|
| V1 | Find out what is on and get to a ticket link | The highest-volume path in the whole system and the only one with an external audience. Bug AO (site-wide horizontal overflow at ≥1000px, confirmed on `/programme/`) sits directly on it and is currently open. |
| V2 | Read one event's page and decide to come | Where the copy and the poster do the actual persuading. §8.16 means film events are the ones most likely to render imageless, because PVSL licensing keeps posters late, so the failure lands hardest exactly where it costs most. |
| V3 | Work out how to get involved or who to contact | Thin, and mostly a Wagtail page. Overlaps P1 below. |

**Prospective volunteer**

| | Workflow | Why it matters |
|---|---|---|
| P1 | Find an induction session and sign up for it | This branch has a real public flow (`inductions:session_list_public` → `signup` → `signup_thanks`, plus `access_needs_signup`), which is a step change over the live Google Form. It is the single conversion point for every future volunteer, and it is new code that has never been walked as a stranger would walk it. |
| P2 | Get a sense of the place before committing | The collectives public page exists but still overflows, blocked on Bug AO (task 9.152 partial). |

**New volunteer**

| | Workflow | Why it matters |
|---|---|---|
| N1 | Welcome email → set password → first login | One-shot, per person, with total failure as the failure mode: no account means no route in except emailing a coordinator. Bugs AJ, AK and AH were all on this path, all real, all shipped fixes, which is decent evidence it is fragile. |
| N2 | Find and take a first shift | The retention moment. Someone who cannot work out which slots are free, what "Duty Manager" entails, or whether their sign-up saved, quietly does not come back. Served today by the same rota view §8.6 calls a wall of text. |

**Established volunteer**

| | Workflow | Why it matters |
|---|---|---|
| E1 | See what needs filling and sign up | Highest-frequency logged-in action in the system by a wide margin. Every gram of friction here is paid weekly by everyone. |
| E2 | Check when they are next on | Not rough, absent. There is no my-schedule view at all (§8.3), so the answer to a question people ask constantly is "scroll the rota and look for your own name", against a free-text field that may hold a typo of it. |
| E3 | Drop a shift they can no longer do | No reserve or standby mechanism (§8.4), and no ownership check on clearing a slot (§8.3), so anyone can clear anyone. Handled today by messaging the list. Stakes are real (an unstaffed bar on the night) but the toolkit is currently not in this loop at all. |
| E4 | Find out who to ask about X | Partly served now by the collectives directory and the volunteer directory. Keyholder-finding is deliberately left as a human interaction (§8.12), which is a defensible call, not a gap. |

**Programmer**

| | Workflow | Why it matters |
|---|---|---|
| G1 | Idea → event → showings → terms → confirmed → public | The longest chain in the system and the highest stakes per action, since the output is public. Bug AR was a break in precisely this chain (approved events vanishing between `programming_status` and `Showing.confirmed`), fixed 2026-09-09 and worth re-walking to confirm the fix holds for a human, not just for the test. |
| G2 | Get the event staffed, including a keyholder | Depends entirely on E1 working for other people, plus an out-of-system keyholder conversation. |
| G3 | Propose an event into the queue for a Monday meeting | Newer path, less worn, and the one where a stranger's mental model is most likely to diverge from the code's state machine. |
| G4 | Return later to add the TicketSource link, then confirm | Small but critical: §4.5 makes confirmation depend on it, so it is the last gate before anything is public. |

**Coordinator**

| | Workflow | Why it matters |
|---|---|---|
| C1 | Add a new volunteer end to end, including the mailing list | Where the system and the human process meet, and the site of the known `vols_admin_address` production incident. Now has an automated route via `manage_create_accounts` on an induction session, which is a materially different workflow from the one SPEC §4.2 describes. |
| C2 | Retire or make dormant, including GDPR erasure on request | Legal stakes. The `Volunteer.anonymise()` email-scrub bug fixed on 2026-09-09 lived here, and it was the same comma-joined-field class as the `vols_admin_address` incident. |
| C3 | Send a mailout | Irreversible once sent, and reaches everyone. The mailer also carries the largest single cluster of verified-but-unfixed findings in the repo (Bug AY items 6 to 10). |
| C4 | Change site settings, grant or review access | Low frequency, wide blast radius. Bug AY item 4 (`_passes_level` failing open on an unrecognised permission string) is here. |

**The collective**

| | Workflow | Why it matters |
|---|---|---|
| K1 | See who holds Panopticon or Programmer access, and why | Already built (`/toolkit/access/`, with mandatory reasons and 365-day review). Probably the best-served item on this whole list. |
| K2 | Reconstruct what happened after something goes wrong | Deletion logging (9.159) is built here and still not in production, which is why it is CURRENT_WORK's named first deployable thing. |

### Cross-persona priority list (chunk 3)

Ordered by how much total harm bad execution does, across everyone, over a year. Drafted from the
docs, then put to Jonny on 2026-09-09 against three alternative orderings (public-facing first,
programmer chain first, induction signup first) and **confirmed as drafted**. Treat it as settled
input to chunk 4 rather than something to reopen.

| # | Workflow | Composed of | Why this rank |
|---|---|---|---|
| 1 | **A volunteer finds a shift and takes it** | E1, N2 | The system's actual purpose. Highest frequency, and the thing that determines whether the building opens. Friction here compounds across every volunteer every week, and for a new volunteer it decides whether there is a second shift at all. |
| 2 | **A volunteer knows when they are next on** | E2 | Ranked this high because it is a total absence rather than a rough edge, and because it is asked constantly. Cheap to serve badly, cheap to serve well, currently not served. |
| 3 | **A stranger finds an induction and signs up** | P1, V3, P2 | The only conversion point for new people, and brand-new code on this branch that no stranger has walked. Getting this right is how the volunteer base is replenished, which makes it upstream of everything else on the list. |
| 4 | **A visitor finds what is on and books** | V1, V2 | Highest volume, only external audience, and it has a confirmed open layout bug on it. Ranked below the volunteer paths only because a rough public page loses one booking, whereas a rough rota loses a volunteer. |
| 5 | **A programmer takes an event from idea to public listing** | G1, G4, G3 | Highest stakes per action and the longest chain, so the most places to break. Lower frequency than 1 to 4, which is the only reason it sits here. |
| 6 | **A coordinator adds a volunteer end to end** | C1 | The seam between software and human process, historically the site of the one real production incident, and materially changed by the inductions app. |
| 7 | **A coordinator sends a mailout** | C3 | Irreversible, wide blast radius, and the code underneath it has the most known unfixed findings. |
| 8 | **A volunteer drops out and the shift gets re-covered** | E3 | Lowest confidence on this list. The toolkit is currently not in this loop at all, and it is genuinely arguable that the mailing list is the right place for it to stay. Included so the question gets asked, not because the answer is obviously "build something". |

Deliberately below the line: K1 (already well served), E4 and the keyholder question (the friction
is partly the point, per §8.12), C2 and C4 (high stakes but low frequency, and both recently
audited), G2 (mostly a restatement of 1 from the other side).

### Incidental finding: the induction docs were stale ✅ fixed 2026-09-09

**Found:** SPEC §4.2, SPEC §6's Google Forms row, known-issues §8.2 and task 9.4 all described
volunteer induction as "entirely manual", a Google Form with copy-paste into the toolkit and "no
audit trail of who inducted whom". That is the live production process on the `s+s` branch. This
branch has an `inductions` app covering public session listing and sign-up, access-needs requests,
capacity caps, check-in, attendance marking, walk-in registration, CSV export and bulk account
creation from attendees. Four documents were describing a process this branch replaced, and task
9.4 was still sitting in the backlog as unbuilt.

**Fixed, same session:** SPEC gained a §1.7 and a rewritten §4.2 with a corrected diagram and a
behaviours table; §6's Google Forms row now says it is a production-only arrangement that this
branch supersedes rather than integrates with; known-issues §8.2 was rewritten to the
"✅ Largely addressed / Still open" shape §8.7 already uses; task 9.4 was marked delivered,
item by item against its original bullets.

**Real gap surfaced while doing it, still open:** `_create_volunteer_from_signup`
(`inductions/views/signups.py`) creates `Member` + `User` + `Volunteer` directly and never fires
the `vols_admin_address` "please add to the mailing list" notification that the manual
`/volunteers/add/` path sends via `members/views/_common.py`. Anyone inducted through the new flow
is invisible to whoever maintains Simplelists. It is worse than the manual path it replaces,
because bulk creation can drop an entire cohort in one action. Recorded in known-issues §8.2 as
open item 2; it wants a task number and a fix, and it is a live example of the kind of thing
chunk 4 exists to find. Note that it was found by reading code, not by walking the workflow, which
is mild evidence the chunk 4 walks should be done with the code open alongside.

---

## Gotchas

- **Naming collision:** `CURRENT_WORK.md` already uses "Phase 1/2/3/4" for a different,
  feature-porting workstream. Refer to this pass as "the user-stories/workflow-audit pass," never
  as "Phase 3" — that label is taken.
- `SPEC.md` §4's workflows are written from the system's perspective ("how the system supports
  X"), not ranked by lived importance. Don't treat that list's order as already-prioritised —
  that's exactly what chunks 1–3 exist to establish.
- Some `known-issues.md` entries were resolved on 2026-09-09 (see `CURRENT_WORK.md`'s "Last major
  change"). Check current status before citing one as live friction.
- Chunk 4 needs the Docker dev environment up (`docker compose up -d`) — see CLAUDE.md's Docker
  setup section for the edit/reload cycle.

---

## Verification

This pass is done when: every persona has at least one workflow audited end-to-end (chunk 4), the
cross-persona priority list is written down (not just discussed), and every finding has landed as
either a `docs/tasks/*.md` item or a `CURRENT_WORK.md` status row — not left only in this file or
in conversation.
