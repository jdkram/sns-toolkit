# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Default wording for hire enquiries. All of it is editable at runtime.

The decline texts and privacy notice are the first drafts from
docs/tasks/hires.md, still awaiting Jonny's edit. Placeholders use {braces}.
"""

CLOSED_MESSAGE = (
    "We're not taking new hire enquiries at the moment. We're entirely "
    "volunteer run, and right now we don't have the people to give "
    "enquiries the attention they deserve. Please try again later."
)

HOW_WE_WORK = (
    "We are entirely volunteer run. The space and a keyholder are "
    "guaranteed for your hire. Everything else (bar, projection, stage "
    "help) depends on volunteers choosing to help, and events that fit our "
    "ethos tend to get more support."
)

TIER_GUIDANCE = (
    "Community: grassroots, DIY, unfunded or charitable events. "
    "Corporate: businesses, funded organisations, and events run for profit."
)

ACKNOWLEDGEMENTS = "\n".join(
    [
        "I understand that bar staff are not guaranteed, because everyone "
        "working here is a volunteer.",
        "I understand that the space and a keyholder are guaranteed, and "
        "everything else is best-effort.",
        "Volunteers working my event will be offered food and drink.",
    ]
)

LATE_NIGHT_NOTICE = (
    "Late finishes (after {late_from}) are the exception here, not the "
    "rule. We only have a limited number of late nights each year, they "
    "cost us extra, and they ask a lot of our volunteers, who all need to "
    "get home safely afterwards. Please consider finishing earlier if you "
    "can. If you do need a late finish, there is an extra charge of "
    "{late_fee}, and we can't promise your date will be available."
)

DOOR_STAFF_NOTICE = (
    "Late club nights need door staff. We arrange them, and the cost is "
    "an additional charge to you: {door_fee}."
)

LATE_NIGHT_ACK = (
    "I understand late finishes are limited, cost extra, and may not be "
    "available for my date."
)

PRIVACY_NOTICE = """\
How we use your information when you enquire about hiring {venue}

Who we are. {venue} is a volunteer-run cinema and venue. We are responsible \
for the information you give us when you enquire about a hire. Questions \
about it go to {privacy_contact}.

What we collect. Your name, organisation, email address and phone number; \
the details of the event you propose (dates, times, rooms, description, \
links); your answers to our questions; and, if your hire goes ahead, the \
terms you agree to and when you agreed them.

Why, and on what basis. We use it to consider your enquiry, reply to you, \
and, if we go ahead, arrange and run your event. This is processing you \
have asked us to do before entering into an agreement with you.

Who sees it. Volunteers who handle hire enquiries can see everything. A \
summary of your enquiry (your name, organisation and event details, but not \
your email or phone number) is sent to our programming mailing list, whose \
members are volunteers who help decide what we host. If your event goes \
ahead, volunteers signing up to help will see its details and anything \
you've offered them. We do not sell your information or share it with \
anyone else, except where the law requires it.

How long we keep it. If your enquiry doesn't go ahead, we delete your \
personal details {declined_purge_months} months after it closes. If you \
hire from us, we keep your contact details and booking history for \
{hirer_purge_years} years after your last contact with us. The terms of any \
hire you agreed, and its fee, are financial records and are kept for six \
years.

Your rights. You can ask to see the information we hold about you, ask us \
to correct it, or ask us to delete it (we may need to keep financial \
records). You can also complain to the Information Commissioner's Office \
(ico.org.uk) if you're unhappy with how we've handled it.
"""

_VOLUNTEER_ROUTE = (
    "There is one other route, if it ever appeals. Anyone can volunteer "
    "here, and once you've helped out at ten of other people's events you "
    "can programme your own, with {venue} taking on the financial risk (and "
    "keeping any profit). It's a slower path and it isn't for everyone, but "
    "it's how most of what happens here gets put on."
)

GUARANTEE_BLOCK = (
    "What is guaranteed: the space, your agreed times, and a keyholder.\n"
    "{extras}"
    "What is best-effort: {best_effort}. Nobody is paid to be here, so "
    "these depend on volunteers choosing to help."
)

# key -> (subject, body)
EMAIL_DEFAULTS = {
    "acknowledgement": (
        "Your enquiry to {venue}: we've got it",
        "Hi {name},\n\n"
        "Thank you for enquiring about {title}. This is an automatic "
        "acknowledgement so you know it has arrived.\n\n"
        "{timing}\n\n"
        "{guarantee}\n\n"
        "{window_note}"
        "{venue}\n",
    ),
    "accepted": (
        "Your enquiry to {venue}: good news about {title}",
        "Hi {name},\n\n"
        "We'd like to host {title}. {coordinator_line}\n\n"
        "Next we need to agree terms. You'll get a confirmation email with "
        "the terms and a button to agree to them.\n\n"
        "{techs}"
        "{venue}\n",
    ),
    "maybe": (
        "Your enquiry to {venue}: we'd like to, but need a volunteer",
        "Hi {name},\n\n"
        "We'd like to host {title}, but at the moment nobody has volunteered "
        "to coordinate it. We're asking around, and you'll hear from us by "
        "{callout_deadline}, one way or the other.\n\n"
        "{venue}\n",
    ),
    "declined": (
        "Your enquiry to {venue}",
        "Hi {name},\n\n"
        "Thank you for getting in touch about {title}. Having talked it "
        "over, we're not able to take it on this time.\n\n"
        + _VOLUNTEER_ROUTE
        + "\n\nThanks again for thinking of us.\n\n{venue}\n",
    ),
    "declined_capacity": (
        "Your enquiry to {venue}: we haven't managed to get back to you",
        "Hi {name},\n\n"
        "Thank you for getting in touch about {title}. We owe you a "
        "straight answer, so here it is: we haven't been able to take your "
        "enquiry on, and we're sorry it has taken until now to tell you.\n\n"
        "{venue} is run entirely by volunteers. Nobody is paid to answer "
        "enquiries or to staff events, and at the moment most of our "
        "volunteers' time is going on our own programme. Your enquiry was "
        "due to be discussed at our meeting on {meeting_date}, and nobody "
        "was able to take it on. That says more about our capacity than "
        "about your event.\n\n"
        "We'd rather tell you this honestly than leave you waiting. If your "
        "plans are flexible, you're welcome to enquire again for a later "
        "season, or to come along to one of our open meetings, where the "
        "people who decide these things are in the room.\n\n"
        + _VOLUNTEER_ROUTE
        + "\n\nThanks again for thinking of us.\n\n{venue}\n",
    ),
    "declined_no_support": (
        "Your enquiry to {venue}: we couldn't find the support",
        "Hi {name},\n\n"
        "When we last wrote, we said we'd like to host {title} and were "
        "looking for a volunteer to coordinate it. We've asked around and "
        "nobody has been able to take it on, so we have to say no this "
        "time. We're sorry to have kept you waiting for that answer.\n\n"
        "Because we're entirely volunteer run, an event only happens here "
        "when someone chooses to give their time to it. That isn't a "
        "judgement on your event, and it might be different another "
        "season. If you'd like to try again, the best route is to come to "
        "one of our open meetings and meet the people who might get "
        "involved.\n\n" + _VOLUNTEER_ROUTE + "\n\n{venue}\n",
    ),
    "meeting_moved": (
        "Your enquiry to {venue}: our meeting has moved",
        "Hi {name},\n\n"
        "We've had to move the meeting where {title} will be discussed. "
        "You'll now hear from us by {reply_by}. Sorry for the delay.\n\n"
        "{venue}\n",
    ),
    "booking_confirmation": (
        "{venue}: please confirm the terms for {title}",
        "Hi {name},\n\n"
        "Here are the terms for {title}.\n\n"
        "Dates and access:\n{dates}\n\n"
        "Fee: {fee}\n\n"
        "Terms:\n{terms}\n\n"
        "{guarantee}\n\n"
        "To agree to these terms, open this link and press the button:\n"
        "{agreement_url}\n\n"
        "Nothing is booked until you do.\n\n"
        "{venue}\n",
    ),
    "booked": (
        "{venue}: {title} is booked",
        "Hi {name},\n\n"
        "Thank you for agreeing the terms. {title} is booked.\n\n"
        "Dates and access:\n{dates}\n\n"
        "{guarantee}\n\n"
        "{venue}\n",
    ),
}

INTERNAL_DEFAULTS = {
    "digest": (
        "Hire enquiries for the {meeting_date} meeting ({count})",
        "Hire enquiries to discuss at the meeting on {meeting_date}:\n\n"
        "{lines}\n\n"
        "Decide them here: {queue_url}\n"
        "Any not decided by their auto-decline date get an honest "
        "'we didn't have capacity' email.\n",
    ),
    "last_call": (
        "Last call: undecided hire enquiries",
        "These hire enquiries will be auto-declined soon unless someone "
        "decides them:\n\n{lines}\n\nDecide them here: {queue_url}\n",
    ),
    "callout": (
        "Volunteer wanted to coordinate a hire: {title}",
        "We said 'maybe' to a hire and need someone to coordinate it.\n\n"
        "{title} ({organisation})\n{dates}\n\n"
        "What we need: {what_we_need}\n"
        "What the hirer offers volunteers: {offers}\n\n"
        "Step forward by {callout_deadline}: {enquiry_url}\n",
    ),
    "no_meetings": (
        "Hire enquiries need a meeting date",
        "There are hire enquiries waiting but no programming meeting dates "
        "entered, so they're running on the fallback clock. Please add "
        "the next meeting dates: {meetings_url}\n\n{lines}\n",
    ),
}


# key -> (friendly name, when it is sent)
EMAIL_LABELS = {
    "acknowledgement": (
        "Enquiry received",
        "To the hirer, straight after they submit the form.",
    ),
    "accepted": (
        "Accepted",
        "To the hirer when you press Accept. Lists approved sound techs. The terms themselves follow in the booking confirmation.",
    ),
    "maybe": (
        "Maybe: looking for a coordinator",
        "To the hirer when you mark an enquiry Maybe.",
    ),
    "declined": ("Declined", "To the hirer when you press Decline."),
    "declined_capacity": (
        "Auto-decline: no capacity",
        "To the hirer automatically if nobody has decided by the reply date.",
    ),
    "declined_no_support": (
        "Auto-decline: nobody stepped forward",
        "To the hirer automatically if a Maybe callout runs out of time.",
    ),
    "meeting_moved": (
        "Meeting moved",
        "To the hirer if their meeting is cancelled and the reply date slips.",
    ),
    "booking_confirmation": (
        "Booking confirmation (terms to agree)",
        "To the hirer when you press Send booking confirmation. Contains the agreement link.",
    ),
    "booked": ("Booked", "To the hirer after they agree to the terms."),
    "digest": (
        "Pre-meeting digest (internal)",
        "To the notification list a few days before each programming meeting.",
    ),
    "last_call": (
        "Last call (internal)",
        "To the notification list shortly before enquiries would be auto-declined.",
    ),
    "callout": (
        "Maybe callout (internal)",
        "To the notification list when you mark an enquiry Maybe: a request for a volunteer coordinator.",
    ),
    "no_meetings": (
        "No meeting dates (internal)",
        "Monthly nag to the notification list when enquiries are waiting but no meetings are entered.",
    ),
}
