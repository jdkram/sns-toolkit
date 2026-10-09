---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude"]
status: "#ai-input"
---

# S&S Toolkit: Hires

Feature specs for outside hires: how an enquiry arrives, gets decided, gets answered, and how
the collective sees what hires are worth against the volunteer programme they fund.

**For work status:** [CURRENT_WORK.md](../../CURRENT_WORK.md)

---

### 9.175: Hire enquiries: an honest, resilient pipeline from enquiry to booking 🔴 XL

#### Resume protocol (read first)

**Build status (2026-10-09):** Phase A is built on `feature/9.175-hire-enquiries` behind the `hire_enquiries_enabled` site-settings flag; see CURRENT_WORK.md for the list of deviations and what is not built. The paragraph below is the pre-build scoping state, kept for context.

**State as of 2026-10-08 (late):** spec scoped across one long session with Jonny and one
external review. Not built, nothing committed yet (this file, the `docs/TASKS.md` index row and
the `CURRENT_WORK.md` row are uncommitted on `sns_2026_overhaul`). Every row in "Decisions taken"
was decided by Jonny explicitly; don't re-ask them.

**Next session, in order:**
1. Go through "Open questions" with Jonny. Question 2 (edit the draft privacy notice and the two
   decline emails together, in his voice, using the `prose`/`email` skills) is the one he
   flagged as next.
2. Questions 4 to 6 (PA charging, unapproved techs, who pays the tech) may need someone outside
   the session; record whatever he knows and leave the rest open.
3. Offer to commit (docs-only: `docs(hires): spec 9.175 hire enquiries`), no AI trailers.
4. The spec is "solidly scoped" once questions 1 and 2 are answered; 3 to 6 can be resolved
   during Phase A. Building starts with Phase A only.

**Grounding already done (don't redo):** the live form's seven fields and the FAQ prices
(summarised in "Problem" and seeded into `HireType`); `Event.terms_satisfied()` /
`has_financial_terms()`; the programming queue view (`edit_views/site_config.py`); the
inductions custom-questions JSON; 9.164 and 9.173 overlap checked; no existing meeting, sound
tech or hire-enquiry models.

**Source:** Conversation 2026-10-08. Scoped over four rounds of questions; every decision
below was taken explicitly by Jonny unless it is listed under "Assumptions made while
writing" or "Open questions".

#### Problem

The public Hire & Enquire form (a Wagtail `EmailFormPage`, `toolkit/content/models.py`) takes
seven free-text fields and emails them to info@. Nothing structured is kept. The page promises
"we'll get back to you as soon as possible".

The intended process is: enquiry arrives, it is discussed at a programming or programming
development meeting (at least monthly), the meeting decides yes / no / maybe and who will
coordinate, the hirer hears back promptly, terms are agreed, the event goes on the rota.

What actually happens: the programme is full of the collective's own events, enquiries rarely
get an answer, and hirers who persist end up at an open Monday meeting, baffled. Leaving the
form open while not answering it is the worst of both worlds. It is dishonest to hirers and
damages the venue's reputation.

There is also a slower, structural problem. Hires keep the lights on and pay for the volunteer
programme, but the link between the two is invisible and the feedback loop is months long, so
it is hard for the collective to strike a balance between "fun stuff we want to do" and "hires
that let us do it".

#### Principles

1. **Silence is never the outcome.** Every enquiry gets an acknowledgement, and a decision or an
   honest "we don't have capacity" by a date the hirer was told in advance.
2. **Resilient to low volunteer capacity.** The honest outcome happens even if nobody acts. The
   system warns first, then sends.
3. **Explicit about what is guaranteed.** The space and a keyholder are guaranteed. Bar, door and
   other volunteer roles are best-effort, because nobody is paid to be there. Hirers are told this
   before they enquire, when they enquire, and when they are accepted.
4. **Make the money legible.** Show what a hire is worth in volunteer events it funds, at the
   moment the meeting is deciding.
5. **Plan ahead.** Booking windows and recurring holds push conversations towards whole seasons.

#### Decisions taken (2026-10-08)

| Area | Decision |
|---|---|
| Intake | A toolkit `HireEnquiry` record **replaces** the Wagtail form. |
| Form editability | **Hybrid.** Core fields fixed in code (labels and help text editable). Extra questions use the inductions custom-questions editor (9.4), extracted to a shared component. No form builder. |
| Queue | `HireEnquiry` is its **own model**, shown as a section of the **programming queue page** in the same visual style. "Yes" creates a proposed `Event` linked back to the enquiry. |
| Timeout | **Warn, then auto-send.** |
| Timeout clock | **Meeting-aware.** Deadline counts from the first programming meeting after submission. |
| Maybe | **Callout with its own deadline.** If nobody steps forward, the hirer gets an editable "we couldn't find support" email. |
| Capacity | **Both:** booking windows as standard, plus a master open/closed switch. |
| Availability | **Both audiences, different detail.** Internal: full detail. Public: room × day-part, free / busy / held. |
| Standard slots | **Recurring hold rules**, with per-date release. |
| Busyness signal (internal) | Room occupancy, volunteer load, pairing opportunity. (No weekly cap.) |
| Income denominator | **Admin-set figures.** |
| Income surfaces | On each enquiry, and a season summary on the queue page. (No dashboard card, no public line.) |
| Ethos | All four: acknowledgement checklist; support needs and offers; explicit "guaranteed vs best-effort" in confirmation; post-event goodwill note. |
| Hirer memory | A separate **`Hirer`** record, so history and goodwill notes persist across enquiries. |
| Permissions | **Runtime `perm_*` fields** on `SiteConfiguration` (9.49 pattern), defaulting to the programmer tier. |
| Notifications | A **list of addresses** (the programming list now, e.g. a private hires group later). Pre-meeting digest, plus maybe-callouts sent immediately. |
| "Terms agreed" | The event's existing terms, as the code already defines them, plus a recorded fee. |
| Hirer agrees terms | **In v1.** One-click agreement link in the confirmation email; booked only once the hirer agrees. |
| Minimum duration | **3 hours by default**, counted on the whole access window including get-in and get-out, which the form makes hirers think about explicitly. |
| Community vs corporate | **The meeting decides.** The hirer is guided to apply as one or the other on the form. |
| Day-parts | **Morning / afternoon / evening**, plus **late night** as a separately priced extra (security cost, extra strain on volunteers). |
| Privacy notice | An **editable `SiteConfiguration` field**, drafted below. |
| Decline tone | **Very honest.** Default wording owns up to how we are acting as an organisation. |
| Sound tech | **Asked on the form.** Any music other than purely acoustic needs one; "not sure" is treated as yes for music. Hirers are pointed at an admin-kept list of approved techs who know the gear. |

#### Why no form builder

A self-editing form brings schema migration, conditional logic and validation into admin
territory, and every feature downstream (availability, income, the timeout) depends on
structured core fields that an admin could quietly delete. The hybrid keeps those fields in
code and gives admins the part they actually change: wording, and a handful of extra questions.
9.173 reached the same conclusion for the programming proposal form on 2026-09-17. The
inductions editor (`InductionSession.custom_questions`, JSON list of
`{label, type: text|checkbox|select, required, options}`) already exists, so the maintenance
cost is one shared JS component used in two places.

#### Data model

All new models live in a new `hires` app (keeps `diary` from growing further and gives
retention jobs a clear home). Field names are indicative.

- **`Hirer`**: `name`, `organisation` (blank), `email` (indexed, not unique: people share
  inboxes), `phone`, `created_at`, `last_activity_at`. A new enquiry is **never linked
  automatically**. A matching email (or name) is shown as a suggested match on the queue card,
  and a person confirms it or creates a new `Hirer`. Two people sharing an organisational inbox
  must not have their histories merged by accident, and a wrong link is much harder to undo than
  a missing one. Merging duplicates is a separate manual action. Holds personal data, so it has a retention
  rule (below).
- **`HireType`**: admin-editable price list, seeded from the public FAQ. `name` (e.g.
  "Cinema"), `community_fee_gbp`, `corporate_fee_gbp`, `unit` (flat / per hour / per 4-hour
  block), `vat_applies`, `min_duration_hours` (blank = the site default of 3),
  `default_rooms` (M2M `Room`), `order`, `active`, `public_description`. Drives the form's type
  dropdown and the income estimate.
- **`HireEnquiry`**:
  - Link: `hirer` FK.
  - Core fields (fixed in code): `hire_type` FK, `tier_requested` (community / corporate,
    chosen by the hirer with guidance), `tier_agreed` (set by the meeting; blank until then),
    `title`, `description`, `preferred_dates` (structured: one or more candidate dates, each
    with **get-in**, **event start**, **event end** and **get-out** times, so availability and
    the minimum duration can be checked against the whole time the building is in use),
    `date_flexible`, `sound_tech` (bringing an approved tech / would like an approved tech /
    bringing their own tech / not needed / not sure), `sound_tech_name` (blank),
    (bool), `flexibility_notes`, `rooms_requested` (M2M `Room`), `expected_attendance`,
    `media_url`.
  - Ethos: `support_roles_requested` (M2M rota `Role`, limited to roles flagged as offerable to
    hirers), `offers_to_volunteers` (text, e.g. food, guest list), `acknowledgements` (JSON:
    which statements were ticked, with their wording at the time).
  - Extras: `custom_answers` (JSON, answers to the admin-defined questions, stored with the
    question label at the time so later edits to the question don't rewrite history).
  - Workflow: `status` (below), `status_changed_at`, `coordinator` (FK user, the volunteer
    programmer), `discuss_at_meeting` FK `ProgrammingMeeting`, `reply_deadline`,
    `warning_sent_at`, `callout_deadline`, `replied_outside_toolkit_at`, `internal_notes`.
  - Terms agreement: `agreement_token` (signed, single-purpose), `confirmation_sent_at`,
    `terms_agreed_at`, `terms_agreed_snapshot` (the exact terms text and fee the hirer agreed
    to, frozen at that moment), `terms_agreed_ip`. A later edit to the event's terms never
    changes the snapshot.
  - Outcome: `event` (OneToOne `Event`, set on "yes"), `estimated_income_gbp` (snapshot at
    decision time; the live estimate is computed).
- **`ProgrammingMeeting`**: `date`, `kind` (programming / programming development / open Monday),
  `notes`. Admins enter a season's meetings in one go. No meeting model exists today.
- **`SlotHold`** (recurring rule): `label` (e.g. "Thursday and Friday screenings"), `rooms`
  (M2M), `weekdays`, `start_time`, `end_time`, `valid_from`, `valid_until` (blank = ongoing),
  `public_label` (what hirers see, e.g. "Held for our film programme").
- **`SlotHoldRelease`**: `hold` FK, `date`, `reason`. Releases one date of a hold ("no film
  that Thursday, offer it out").
- **`HirerNote`** (goodwill): `hirer` FK, `enquiry` FK (nullable), `author`, `created_at`,
  `text`. Internal only. (A sentiment field was considered and dropped after review: it invites
  scoring people, and the text says more.)
- **`ApprovedTech`**: the list of freelance sound techs who know the building's gear. `name`,
  `email`, `phone`, `rate_text` (free text, e.g. "£X per gig", since techs quote differently),
  `specialisms` (e.g. live bands, DJ, cinema sound), `notes` (internal), `active`,
  `share_with_hirers` + `consented_at` (a tech's details only go to hirers once they have agreed
  to it). Admin-edited under `perm_hire_settings`. It holds techs' personal data, so it lives in
  the database, never in docs or seed data with real details (the repo is public).
- **`HireType`** also gains `needs_sound_tech` (gigs, club nights: yes; talks, workshops,
  screenings: no) and `includes_pa` (see open question 4).
- **Rota `Role`**: one new boolean, `offerable_to_hirers`, so the form only lists roles the
  collective is willing to call out for.
- **`SiteConfiguration`**: see "Settings" below.

`Event` is untouched apart from the reverse link from `HireEnquiry.event`; `outside_hire` and
`hire_name` (9.30) are filled in when the event is created.

#### Status machine

```
submitted ──(auto, immediately)──> acknowledged
acknowledged ──(assigned to a meeting)──> to_discuss
to_discuss ──> accepted ──(terms satisfied, confirmation sent)──> awaiting_agreement
                         ──(hirer clicks "I agree")──> booked ──> completed
              (terms edited after agreement: booked ──> awaiting_agreement, re-sent)
           ──> maybe ──(coordinator found)──> accepted
                     ──(decided against)──> declined                       [email]
                     ──(callout deadline passes)──> declined_no_support   [auto email]
           ──> declined                                                    [email]
acknowledged / to_discuss ──(reply deadline passes)──> declined_capacity   [auto email]
any open state ──> withdrawn (hirer withdrew)
```

Any status change made by a person counts as a reply and stops the reply clock.

"Replied outside the toolkit" (for info@ conversations the toolkit cannot see) **postpones the
clock, it does not stop it**: it records `replied_outside_toolkit_at` and moves the enquiry to
the next meeting, recomputing the deadline from there. Otherwise one click would park an enquiry
forever, which is the silence this feature exists to end. The button asks for a one-line note of
what was said. If the hirer has already agreed by email, the person records the decision
instead (accept, decline), which is a real status change.

**When meetings change.** The deadline is always derived from the enquiry's assigned meeting,
never stored independently of it:
- Moving an enquiry to a different meeting recomputes its deadline (and clears
  `warning_sent_at`).
- Cancelling or deleting a `ProgrammingMeeting` moves its enquiries to the next meeting and
  recomputes. If the new deadline is later than the one the hirer was given, the hirer gets a
  short editable "we've had to move our meeting, you'll hear by X" email, so the date we
  promised is never silently broken.

**When the feature is switched off.** Turning `hire_enquiries_enabled` off while enquiries are
open pauses every clock: nothing auto-sends while the feature is off. Open enquiries stay visible
to admins. Switching it back on recomputes deadlines from the next meeting. The settings page
warns, with a count, before the flag is turned off with enquiries open.

#### Behaviour

**Public form.** A Wagtail page type, `HireEnquiryPage`, renders the toolkit form inside the
CMS. This keeps the existing URL (`/hire-and-enquire/enquire/`) and the CMS navigation, and lets
editors keep editing the intro and thank-you text in Wagtail as they do now. The form shows:
- The intro, then a short plain-language panel on how S+S works (editable): entirely volunteer
  run, the space and a keyholder are guaranteed, everything else depends on volunteers choosing
  to help, events that match our ethos get more support.
- The public availability view (below) next to the date picker.
- **Community or corporate.** The hirer picks one, guided by editable help text
  (`hire_tier_guidance_text`, e.g. "community: grassroots, DIY, unfunded or charitable;
  corporate: businesses, funded organisations, events run for profit"). The meeting confirms or
  changes it (`tier_agreed`), and the income estimate uses the agreed tier once set, the
  requested one until then.
- **Time in the building, not just the event.** Each candidate date asks for get-in, event start,
  event end and get-out separately. Get-in and get-out are pre-filled at
  `hire_default_setup_minutes` / `hire_default_teardown_minutes` either side (default 60 each),
  with the line: "Most hirers underestimate setup and pack-down. The building has to be open, and
  a keyholder present, for all of it." The **whole access window** must be at least the hire
  type's minimum (default `hire_min_duration_hours` = 3); a shorter window is rejected with that
  explanation, not silently extended.
- **Sound tech.** "Will you need a sound tech?" with the options above and the rule in the help
  text: "Any music performance other than purely acoustic needs a sound tech who knows our
  system. We keep a list of approved freelance techs and their rates." Where the hire type has
  `needs_sound_tech`, "not needed" is not offered, and "not sure" is treated as "would like an
  approved tech". Choosing "bringing their own tech" asks for the name; the queue card flags it
  if that name is not on the approved list, so the meeting can decide (see open question 5).
- **Late night.** Any access window running past `hire_late_night_from` (default 23:00) is
  flagged on the form as late night: an extra fee (`hire_late_night_fee_gbp`), and the reason
  given plainly ("late finishes mean paying for security and ask more of our volunteers").
  Gigs and club nights already price their late hours on the FAQ; the late-night fee applies on
  top of a hire type only where that type's own pricing doesn't already include it
  (`HireType.includes_late_night`).
- Core fields, support roles requested, offers to volunteers, admin extra questions, then the
  acknowledgement checklist (editable statements, all required, e.g. "I understand bar and door
  staff are not guaranteed", "Volunteers working my event will be offered food and drink").
- A link to the hire privacy notice (`hire_privacy_notice_text`, editable; first draft below).
- Honeypot and rate limit for spam. (Auto-emails go to whatever address is typed in, so a
  rate limit per address and per IP matters more than it would for a form that only emails us.)

**Booking windows and the master switch.**
- `hire_booking_window_start` / `_end`: the date range the collective is actively booking.
  Dates inside the window behave normally. Dates beyond it are accepted but marked "considered
  at season planning", and the acknowledgement email says so. This is the forward-planning lever.
- Optional "full" ranges inside the window (admin-entered), which warn the hirer on the form
  before they submit.
- `hire_enquiries_open` master switch with an editable closed message. When off, the page shows
  the message and no form. This is the honest answer when the collective is overwhelmed.

**Acknowledgement.** Sent immediately. Says when it will be discussed and the date they will
hear back by (from the meeting-aware deadline), repeats what is guaranteed and what is
best-effort, and links the FAQ.

**Reply clock (meeting-aware).**
- On submission, the enquiry is assigned to the first `ProgrammingMeeting` on or after
  `submitted + hire_min_notice_days_before_meeting` (so an enquiry the night before a meeting
  goes to the next one). `reply_deadline = meeting.date + hire_reply_grace_days`.
- **Notifications go to a list of addresses, not to people.** `hire_notification_addresses` is
  an ordered list of email addresses (decided 2026-10-08): in practice the programming mailing
  list, which forwards on, plus any others later (e.g. a private hires group). Validated one
  address per entry, so a comma-joined string in a single entry is rejected; this is the
  `vols_admin_address` incident class, and the same guard applies.
- **Pre-meeting digest (the warning).** `hire_digest_days_before_meeting` before each
  `ProgrammingMeeting`, one email to the notification addresses lists every enquiry assigned to
  that meeting: hirer, type, dates, fit, income estimate, the date it will auto-decline, and a
  link to each. Since meetings are roughly monthly, this is roughly a monthly email, and it
  doubles as the hires part of the meeting agenda. Sent even when the list is empty? No: an empty
  digest is skipped.
- **Last call (only when needed).** `hire_warning_days` before a deadline, if any enquiries for
  that meeting are still undecided, one short email lists just those. This covers the real risk
  of a monthly rhythm: the meeting says yes, nobody enters it, and the clock declines a hire the
  collective wanted. In a month where decisions are entered promptly it never sends.
- **No meetings entered.** If there is no future `ProgrammingMeeting`, enquiries fall back to
  `hire_fallback_reply_days` (assumption 1) and a monthly digest goes out on the first of the
  month instead, with a line asking someone to enter meeting dates.
- **Auto-send:** at the deadline, if no reply has been recorded, status becomes
  `declined_capacity` and the capacity email goes out.
- Runs daily on the existing `scheduler` container (`tk_run.sh`). All sends go through
  `toolkit/mailer/` inside `email_trigger`, so each shows in `SentEmailLog` with a
  `trigger_source` such as "Hire enquiry: auto capacity decline".

**Maybe and callout.** Marking "maybe" requires a short "what we need" note. It emails the hirer
("we'd like to, we're looking for a volunteer to coordinate it, you'll hear by X"), sends a
callout to the same `hire_notification_addresses` **immediately** (decided 2026-10-08; not batched
into the digest, because a callout that waits up to a month is no use), and sets
`callout_deadline`. The callout says what support is needed, the dates, what the hirer offers
volunteers, and a link to step forward. A volunteer who
steps forward becomes `coordinator` and the enquiry moves to `accepted`. If the deadline passes
with nobody, `declined_no_support` and its email go out, preceded by a last-call email to the
same addresses `hire_warning_days` beforehand.

**Multiple preferred dates.** An enquiry can list several candidate dates. The queue card shows
the fit indicator and clash check **per date**, so the meeting can see at a glance which of them
work. Accepting means picking one (or, for a genuine run, several), and only those become
showings on the new `Event`. The income estimate uses the number of dates actually accepted;
before that it shows the estimate for one date.

**Queue section.** On the programming queue page, a "Hire enquiries" section in the same style as
the event queue, grouped by meeting. Each card shows: hirer and organisation (with a badge
and a link to past history and goodwill notes if they are a repeat hirer), hire type, dates
requested and flexibility, rooms, the **income estimate**, a **fit indicator** for the requested
dates (free / clash / pairing opportunity / heavy week), support roles requested and what the
hirer offers, the reply deadline as a countdown, and the decision buttons (accept / maybe /
decline / replied outside toolkit). Accepting asks for a coordinator and creates a proposed
`Event` with `outside_hire=True`, `hire_name` set, room bookings created from the requested
slot, and rota slots for the requested support roles, then hands over to the existing queue and
Event Hub.

**What "booked" means (decided 2026-10-08).** S+S already records terms on each event and treats
them as contractually binding, so "terms agreed" reuses the code's existing definition rather
than inventing a new one. An accepted enquiry becomes `booked` when its linked `Event`:
- passes `Event.terms_satisfied()` (`diary/models/event.py`: terms not required by tag, or
  free-text terms over `programme_event_terms_min_words`, or a non-TBC cost type), **and**
- has `cost_type = venue_hire`, so the hire fee is recorded as structured data, not only in
  prose.

The toolkit detects this; nobody has to remember to change a status. The Event Hub then offers
"send booking confirmation" to the coordinator rather than sending it by itself, because terms
are often typed in stages and the first save that passes the check is not necessarily the
finished version. Edits to terms after booking are already captured by the terms revision
history; the Hub shows "terms changed since confirmation was sent" with a button to re-send.

**Sound tech in the emails.** The approved-tech list is **not** on the public form (it is
techs' personal data). The "accepted" email includes the active, consented techs with their
rates and contact details, so the hirer can book one directly, as the FAQ already says they do.
S+S is not a party to that arrangement. The booked confirmation lists the sound tech under
"your responsibility" if one is needed and none is named yet, and the Event Hub shows "sound
tech: not yet confirmed" until the coordinator records who it is.

**Terms agreement (v1, decided 2026-10-08).** The confirmation email carries a one-click
"I agree to these terms" link (a signed URL; no hirer login). It opens a page showing the terms,
fee, dates and access times, the guaranteed / best-effort lists, and the acknowledgements they
ticked, with one button. Clicking it records `terms_agreed_at` and freezes the snapshot, and the
enquiry becomes `booked`. The coordinator and the event's Hub see "awaiting hirer agreement"
until then. If the terms are edited after agreement, the Hub requires re-sending, and the
enquiry goes back to `awaiting_agreement` until the hirer agrees to the new version. The old
snapshot is kept. No automatic chasing in v1: the Hub shows how long it has been waiting.

**Confirmation (booked).** The confirmation **quotes the event's terms verbatim**, so the hirer
has a written copy of what S+S treats as binding (nothing sends them one today). It also lists
explicitly what is **guaranteed** (the space, the times, a keyholder) and what is
**best-effort** (each requested support role, plainly marked), and repeats the acknowledgements
they ticked. The rota callout for the event shows the support roles and what the hirer has
offered volunteers, so people can see what they are signing up to.

**Internal availability view.** A room × day calendar for a chosen range, layering:
- **Occupancy:** existing `RoomBooking`s, plus recurring holds (minus releases).
- **Volunteer load:** events per ISO week and how full their rotas are. Noisy until rotas are
  published, so it is shown as a secondary signal and labelled with how many rotas are still
  empty.
- **Pairing opportunity:** a day where another event is already booked in a *different* room,
  at overlapping or adjacent times, is marked as a good fit, because one keyholder can cover
  both. This turns "busy" into "good to add", as the collective already does informally.

**Public availability view.** Per bookable room, per day, split into **morning / afternoon /
evening**, plus a **late night** column marked "by arrangement, extra fee" (boundaries in
settings). Each cell is one of: free, booked, held for our
programme (with the hold's `public_label`), outside the booking window ("considered at season
planning"). No event names or details. A short note that "free" means "worth asking", not
"available".

**Income.**
- Each enquiry's estimate comes from its `HireType` fee for the agreed (or else requested)
  tier × units, plus the late-night fee where it applies **minus**
  `hire_late_night_security_cost_gbp`, so a late finish shows what it actually nets rather
  than flattering the figure. The queue card also flags late-night requests in words: "late
  night: security needed, heavier on volunteers". It is shown as
  "about £300 ≈ 2 volunteer events", with the denominator from
  `hire_volunteer_event_net_cost_gbp`.
- Season summary at the top of the queue section: confirmed hire income, income under
  discussion, the total in volunteer-event equivalents, and beside it how many volunteer
  events are programmed for the same period.
- The denominator is labelled with its source and when it was last set ("admin estimate, set
  2026-10-08") so nobody mistakes it for an actual figure.

**Goodwill notes.** After a booked event's date, the coordinator is prompted (Event Hub, and the
existing past-events surfaces) to leave a short note on the hirer. Notes are visible to holders
of the hire permission only, appear on the hirer's history, and are flagged on future
enquiries from the same hirer. Help text under the input: "Write this as if the hirer might
read it." **They might.** Notes about an identifiable person are personal data and disclosable
under a subject access request. Factual and fair ("volunteers weren't offered food, despite
agreeing to") is fine; anything else is a liability. **Don't name volunteers in notes** ("the bar
volunteer said they were rude" rather than naming them): a volunteer's account is their personal
data as well as the hirer's, and it would otherwise have to be redacted by hand before any
disclosure. The help text says both of these things.

#### Settings (`SiteConfiguration`)

- `hire_enquiries_enabled` (ships off; while off, the Wagtail form keeps working unchanged).
- `hire_enquiries_open`, `hire_closed_message`.
- `hire_booking_window_start`, `hire_booking_window_end`.
- `hire_min_notice_days_before_meeting`, `hire_reply_grace_days`,
  `hire_digest_days_before_meeting`, `hire_warning_days`, `hire_callout_days`,
  `hire_fallback_reply_days`.
- `hire_notification_addresses` (list, one validated address per entry): pre-meeting digest,
  last call, maybe-callouts, meeting-moved notices.
- `hire_daypart_boundaries` (morning / afternoon / evening, e.g. 09:00 / 12:00 / 17:00) and
  `hire_late_night_from` (e.g. 23:00).
- `hire_min_duration_hours` (default 3), `hire_default_setup_minutes`,
  `hire_default_teardown_minutes` (default 60 each).
- `hire_late_night_fee_gbp`, `hire_late_night_security_cost_gbp`.
- `hire_tier_guidance_text`.
- `hire_privacy_notice_text` (rich text; linked from the form and every hirer email).
- `hire_volunteer_event_net_cost_gbp` (+ who set it and when).
- `hire_how_we_work_text`, `hire_acknowledgement_statements` (ordered list).
- Email templates, each a subject + body with placeholders (`{name}`, `{venue}`, `{title}`,
  `{dates}`, `{meeting_date}`, `{reply_by}`, `{guaranteed}`, `{best_effort}`, `{coordinator}`,
  `{terms}`),
  same pattern as `last_gasp_email_*`: acknowledgement, accepted, maybe, declined, capacity
  timeout, no-support timeout, booked confirmation (with agreement link), meeting moved. Plus the
  internal digest, last-call and callout emails. Defaults for the decline emails are drafted
  below.
- Retention: `hire_declined_purge_months` (default 6), `hire_hirer_purge_years` (default 3).
- Permissions: `perm_hire_enquiries` (view and act on enquiries, write goodwill notes) and
  `perm_hire_settings` (holds, prices, meetings, emails, windows). Both default to programmer
  tier.

#### Data protection

- Declined and withdrawn enquiries: personal fields purged `hire_declined_purge_months` after
  closing. The enquiry's shape (type, dates, outcome) is kept for statistics.
- `Hirer`: purged `hire_hirer_purge_years` after `last_activity_at`, including goodwill notes.
  Reuses the daily-purge pattern from inductions.
- The hire privacy notice is `hire_privacy_notice_text`, editable by admins. First draft in
  "Draft default texts" below.
- **The digest and callouts go to a mailing list**, so a hirer's name, organisation and event
  details reach everyone on that list. The notice says so. Digests carry no phone numbers or
  email addresses; those stay in the toolkit behind the hire permission.
- **Agreed terms outlive the hirer purge.** The frozen terms snapshot and the event's fee are a
  financial record, kept for six years (the usual HMRC period) with the event, even after the
  `Hirer`'s contact details and goodwill notes are purged. The snapshot keeps the organisation
  name, not personal contact details.

#### Phasing

Each phase is shippable alone behind `hire_enquiries_enabled`. Phase A on its own fixes the
dishonesty.

| Phase | Contents | Size |
|---|---|---|
| **A. Honest loop** | `hires` app; `Hirer`, `HireType`, `HireEnquiry`, `ProgrammingMeeting`; `HireEnquiryPage` + form (core fields, ethos fields, acknowledgements); shared custom-questions component extracted from inductions; status machine; queue section; meeting-aware clock, digest, last call and auto-send; maybe/callout; all emails; terms agreement link and snapshot; access-window durations, minimum and late-night flag; tier guidance; sound-tech question and `ApprovedTech` list; privacy notice field; master switch and booking windows; perms; tests | 🟠 L, ~76h |
| **B. Availability** | `SlotHold`, `SlotHoldRelease`; internal room × day view with occupancy, volunteer load, pairing; public room × day-part view on the form; fit indicator on queue cards | 🟠 L, ~40h |
| **C. Income** | Estimate on cards; season summary; denominator setting with provenance | 🔵 S, ~10h |
| **D. Memory** | `HirerNote`; post-event prompt; repeat-hirer badge and history; hirer merge; retention jobs | 🔵 S, ~14h |

**Total:** 🔴 XL, roughly 140h. A is the critical path; B, C and D are independent of each other
once A has landed.

#### Deployment dependency

Production still runs the old `s+s` branch. None of this reaches hirers until the overhaul is
deployed there, and the timeout needs the `scheduler` container running wherever it is
deployed (9.157). Worth raising alongside the "low-hanging fruit" ports once staging exists.

#### Out of scope (v1)

Hirer login or self-service portal; invoicing, deposits and payment (the agreement link
records agreement to the terms, it is not a contract generator); calendar feeds
or sync; importing the existing info@ backlog; an admin form builder; a dashboard card or public
income line (both explicitly declined 2026-10-08); a weekly event cap (declined 2026-10-08).

#### Assumptions made while writing (check these)

1. **No meeting entered → fallback clock.** If no `ProgrammingMeeting` exists after the
   submission date, the deadline falls back to `submitted + hire_fallback_reply_days` and the
   warning email also nags admins to enter meeting dates. Without this, forgetting to enter
   meetings would silently stop every clock, which is the exact failure the feature exists to
   prevent.
2. **Only people with the hire permission can act**, but anyone logged in can see the queue
   section read-only, matching the existing programming queue.
3. **"Yes" creates a *proposed* Event, not an active one**, so hires go through the same
   confirmation step as everything else (9.162).
4. **Prices are VAT-exclusive** and the estimate shows the pre-VAT figure, because VAT isn't
   income the collective keeps.
5. **The public view never shows event names**, even for public events, to keep it simple and
   avoid leaking private bookings.

#### Open questions

Resolved 2026-10-08: warning and callout recipients; what "terms agreed" means; hirer agreement
(in v1); minimum duration; community vs corporate; day-parts; privacy notice (editable field,
draft below); decline tone (very honest, drafts below).

1. **Timer defaults** (the clock, not booking length). Proposed: digest 5 days before the
   meeting, grace 7 days after it, last call 2 days before the deadline, callout 14 days,
   fallback 35 days. All editable; these are just what ships.
2. **Review the draft texts below**: the privacy notice and the two decline emails. They are
   first drafts written for you to edit, not finished copy.
3. **Late-night figures.** The fee and the security cost are settings, but someone needs to
   supply real numbers before launch.
4. **PA for talks and non-music events.** Nobody is sure how a PA (mics and speakers for a talk
   or panel) is currently charged. Options: included in the hire type (`includes_pa` true for
   workshops and conferences), a flat add-on fee, or "ask us". Needs checking with whoever
   handles hire invoices before Phase A ships; the field is there either way.
5. **Hirer's own tech who isn't on the approved list.** Allowed if they come in for a handover
   with someone who knows the gear, never, or the meeting's call each time? The spec currently
   just flags it on the card.
6. **Who pays the tech** is assumed to be the hirer, directly (from the FAQ's "hire freelance
   sound tech separately"). Confirm that's still how it works.

#### Draft default texts

These ship as the defaults for the editable settings. Placeholders in `{braces}`. Both decline
emails close with a short, optional invitation to volunteer (requested 2026-10-08): it is the
other honest route to getting an event on, but it is offered last and lightly, so a declined
hirer doesn't read it as being palmed off. The "ten events" figure should match
`active_volunteer_min_shifts` from 9.173 if that ships; worth turning into a placeholder then. No real
addresses: `{privacy_contact}` and `{venue}` come from venue settings.

**Capacity timeout (`declined_capacity`).**

> Subject: Your enquiry to {venue}: we haven't managed to get back to you
>
> Hi {name},
>
> Thank you for getting in touch about {title}. We owe you a straight answer, so here it is: we
> haven't been able to take your enquiry on, and we're sorry it has taken until now to tell you.
>
> {venue} is run entirely by volunteers. Nobody is paid to answer enquiries or to staff events,
> and at the moment most of our volunteers' time is going on our own programme. Your enquiry was
> due to be discussed at our meeting on {meeting_date}, and nobody was able to take it on. That
> says more about our capacity than about your event.
>
> We'd rather tell you this honestly than leave you waiting. If your plans are flexible, you're
> welcome to enquire again for a later season, or to come along to one of our open meetings,
> where the people who decide these things are in the room.
>
> There is one other route, if it ever appeals. Anyone can volunteer here, and once you've
> helped out at ten of other people's events you can programme your own, with {venue} taking on
> the financial risk (and keeping any profit). It's a slower path and it isn't for everyone, but
> it's how most of what happens here gets put on.
>
> Thanks again for thinking of us.
>
> {venue}

**No support found (`declined_no_support`).**

> Subject: Your enquiry to {venue}: we couldn't find the support
>
> Hi {name},
>
> When we last wrote, we said we'd like to host {title} and were looking for a volunteer to
> coordinate it. We've asked around and nobody has been able to take it on, so we have to say
> no this time. We're sorry to have kept you waiting for that answer.
>
> Because we're entirely volunteer run, an event only happens here when someone chooses to give
> their time to it. That isn't a judgement on your event, and it might be different another
> season. If you'd like to try again, the best route is to come to one of our open meetings and
> meet the people who might get involved.
>
> There is one other route, if it ever appeals. Anyone can volunteer here, and once you've
> helped out at ten of other people's events you can programme your own, with {venue} taking on
> the financial risk (and keeping any profit). It's a slower path and it isn't for everyone, but
> it's how most of what happens here gets put on.
>
> {venue}

**Hire privacy notice (`hire_privacy_notice_text`).**

> **How we use your information when you enquire about hiring {venue}**
>
> **Who we are.** {venue} is a volunteer-run cinema and venue. We are responsible for the
> information you give us when you enquire about a hire. Questions about it go to
> {privacy_contact}.
>
> **What we collect.** Your name, organisation, email address and phone number; the details of
> the event you propose (dates, times, rooms, description, links); your answers to our
> questions; and, if your hire goes ahead, the terms you agree to and when you agreed them.
>
> **Why, and on what basis.** We use it to consider your enquiry, reply to you, and, if we go
> ahead, arrange and run your event. This is processing you have asked us to do before entering
> into an agreement with you. If you hire from us, we keep a short record of how it went
> (for example, that an event ran smoothly) so we can look after returning hirers well; we do
> this because we have a legitimate interest in running bookings well. We write those notes on
> the basis that you may ask to see them.
>
> **Who sees it.** Volunteers who handle hire enquiries can see everything. A summary of your
> enquiry (your name, organisation and event details, but not your email or phone number) is
> sent to our programming mailing list, whose members are volunteers who help decide what we
> host. If your event goes ahead, volunteers signing up to help will see its details and
> anything you've offered them. We do not sell your information or share it with anyone else,
> except where the law requires it.
>
> **How long we keep it.** If your enquiry doesn't go ahead, we delete your personal details
> {declined_purge_months} months after it closes. If you hire from us, we keep your contact
> details and booking history for {hirer_purge_years} years after your last contact with us.
> The terms of any hire you agreed, and its fee, are financial records and are kept for six
> years.
>
> **Your rights.** You can ask to see the information we hold about you, ask us to correct it,
> or ask us to delete it (we may need to keep financial records). You can also complain to the
> Information Commissioner's Office (ico.org.uk) if you're unhappy with how we've handled it.

#### Review log

- **2026-10-08, external review** (DeepSeek V4 Pro via OpenCode, about 1p, with no access to
  this conversation). Accepted and folded in above: per-date fit for multiple preferred dates;
  "replied outside the toolkit" postpones rather than stops the clock; deadlines recompute when a
  meeting moves or is cancelled; manual decline from maybe; clocks pause when the flag is off;
  suggested rather than automatic `Hirer` matching; don't name volunteers in goodwill notes;
  dropped the sentiment field. Raised as open question 8: honesty of the auto-decline wording.
  Rejected because they reverse decisions taken explicitly on 2026-10-08: replacing recurring
  holds with static text, removing the income-figure provenance, and collapsing goodwill notes
  into one text field.

**Related:** 9.4 (inductions custom questions, to be extracted and shared), 9.30 (`hire_name`),
9.73 (outside-hire badge on rota), 9.113/9.162 (programming queue), 9.49 (runtime perms),
9.157 (scheduler), 9.164 (internal decision emails, same mailer plumbing), 9.171 (settlement
actuals, a possible later source for the income denominator), 9.173 (proposal checklist; same
"no form builder" reasoning).
