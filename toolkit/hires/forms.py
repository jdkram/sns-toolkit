# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from django import forms
from django.utils import timezone

from toolkit.diary.models import Room

from . import defaults
from .models import (
    ApprovedTech,
    HireDate,
    HireEmailTemplate,
    HireEnquiry,
    HireSettings,
    HireType,
    ProgrammingMeeting,
    get_hire_settings,
)

N_DATE_ROWS = 2


def _combine(date, time):
    return timezone.make_aware(datetime.datetime.combine(date, time))


def default_event_times(get_in, get_out, cfg):
    """Provisional event start/end inside a building-access window.

    First contact only asks when the building is needed; the exact event
    times are asked later, once we have said yes in principle. Until then
    the event is assumed to sit inside the window with the default setup
    and pack-down allowances either side.
    """
    start = get_in + datetime.timedelta(minutes=cfg.default_setup_minutes)
    end = get_out - datetime.timedelta(minutes=cfg.default_teardown_minutes)
    if end <= start:
        return get_in, get_out
    return start, end


class HireEnquiryForm(forms.Form):
    """First contact: only what the meeting needs to say yes, no or maybe.

    Everything else (rooms, sound, who is coming, exact event times, the
    acknowledgements) is asked later, once there is something to talk
    about, so we don't ask for a lot of someone's time up front for an
    enquiry we may not be able to take on.
    """

    contact_name = forms.CharField(max_length=200, label="Your name")
    contact_organisation = forms.CharField(
        max_length=200, required=False, label="Organisation (if any)"
    )
    contact_email = forms.EmailField(label="Email")
    contact_phone = forms.CharField(
        max_length=40, required=False, label="Phone (optional)"
    )
    hire_type = forms.ModelChoiceField(
        queryset=HireType.objects.none(), label="What kind of hire?"
    )
    tier_requested = forms.ChoiceField(
        choices=HireEnquiry.TIER_CHOICES,
        label="Community or corporate?",
        initial="community",
    )
    title = forms.CharField(max_length=200, label="Name of your event")
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Tell us about it",
        help_text=(
            "Who it is for, what will happen, and anything you already know "
            "you will need. Include a link if there is one."
        ),
    )
    expected_attendance = forms.IntegerField(
        required=False,
        min_value=1,
        label="Roughly how many people? (optional)",
    )
    flexibility_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Are your dates flexible? (optional)",
        help_text="For example 'any Friday in March' or 'only that date'.",
    )
    late_night_ack = forms.BooleanField(required=False)
    # Honeypot: real people leave this blank.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cfg = get_hire_settings()
        self.cfg = cfg
        self.fields["hire_type"].queryset = HireType.objects.filter(
            active=True
        )
        self.late_requested = False
        self.fields["late_night_ack"].label = (
            cfg.late_night_ack_statement or defaults.LATE_NIGHT_ACK
        )
        for i in range(1, N_DATE_ROWS + 1):
            req = i == 1
            self.fields[f"date_{i}"] = forms.DateField(
                required=req,
                label="Date" if req else "Another date that could work",
                widget=forms.DateInput(attrs={"type": "date"}),
            )
            for key, label in (
                ("get_in", "Building opens"),
                ("get_out", "Everything out by"),
            ):
                self.fields[f"{key}_{i}"] = forms.TimeField(
                    required=req,
                    label=label,
                    widget=forms.TimeInput(attrs={"type": "time"}),
                )

    def date_rows(self):
        return [
            {
                "n": i,
                "fields": [
                    self[f"date_{i}"],
                    self[f"get_in_{i}"],
                    self[f"get_out_{i}"],
                ],
            }
            for i in range(1, N_DATE_ROWS + 1)
        ]

    def error_summary(self):
        """(anchor, label) per problem, one entry per date row."""
        rows = []
        seen_dates = set()
        date_prefixes = ("date_", "get_in_", "get_out_")
        for name, errs in self.errors.items():
            if name == "__all__" or not errs:
                continue
            if name.startswith(date_prefixes):
                n = name.rsplit("_", 1)[1]
                if n in seen_dates:
                    continue
                seen_dates.add(n)
                rows.append((f"date-row-{n}", f"Date {n}"))
            else:
                rows.append((f"field-{name}", self.fields[name].label))
        return rows

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError("Spam check failed.")
        hire_type = data.get("hire_type")
        min_hours = (
            hire_type.min_duration_hours
            if hire_type and hire_type.min_duration_hours
            else self.cfg.min_duration_hours
        )
        self.hire_dates = []
        now = timezone.now()
        for i in range(1, N_DATE_ROWS + 1):
            d = data.get(f"date_{i}")
            if not d:
                continue
            get_in, get_out = (
                data.get(f"get_in_{i}"),
                data.get(f"get_out_{i}"),
            )
            if not (get_in and get_out):
                self.add_error(
                    f"date_{i}", "Fill in both times for this date."
                )
                continue
            if get_in == get_out:
                self.add_error(
                    f"date_{i}",
                    "The building-open and everything-out times are the "
                    "same. Please give both.",
                )
                continue
            gi = _combine(d, get_in)
            go = _combine(d, get_out)
            while go <= gi:  # finishing after midnight
                go += datetime.timedelta(days=1)
            if gi < now:
                self.add_error(f"date_{i}", "That date is in the past.")
                continue
            hours = (go - gi).total_seconds() / 3600
            if hours < min_hours:
                self.add_error(
                    f"date_{i}",
                    f"We need the building for at least {min_hours} hours "
                    f"all told (yours is {hours:.1f}). Most hirers "
                    "underestimate setup and pack-down, and a keyholder has "
                    "to be there for all of it.",
                )
                continue
            start, end = default_event_times(gi, go, self.cfg)
            self.hire_dates.append(
                HireDate(get_in=gi, start=start, end=end, get_out=go)
            )
        self.late_requested = any(d.is_late_night() for d in self.hire_dates)
        if self.late_requested and not data.get("late_night_ack"):
            self.add_error(
                "late_night_ack",
                "Please tick this to confirm you've read the note about "
                "late finishes, or choose an earlier finish.",
            )
        if not self.hire_dates and not self.errors:
            raise forms.ValidationError("Please give at least one date.")
        return data


class HireDetailsForm(forms.Form):
    """Second stage: asked only after we have said yes in principle."""

    rooms_requested = forms.ModelMultipleChoiceField(
        queryset=Room.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Rooms you'd like",
        help_text="Tick any you'd like to use. We'll confirm what's possible.",
    )
    expected_attendance = forms.IntegerField(
        required=False, min_value=1, label="Expected attendance"
    )
    media_url = forms.URLField(
        required=False, label="A link to the act, film or organisation"
    )
    sound_tech = forms.ChoiceField(
        choices=HireEnquiry.SOUND_CHOICES,
        label="Will you need a sound tech?",
        help_text=(
            "Any music other than purely acoustic needs a sound tech who "
            "knows our system. Even a laptop playlist through our speakers "
            "counts. We keep a list of approved freelance techs."
        ),
        initial="unsure",
    )
    sound_tech_name = forms.CharField(
        max_length=200,
        required=False,
        label="Name of your own tech",
        help_text="Only if you chose 'bringing their own tech' above.",
    )
    offers_to_volunteers = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="What can you offer the volunteers who help?",
        help_text="For example food, a guest list, or a thank-you.",
    )

    def __init__(self, enquiry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enquiry = enquiry
        self.fields["rooms_requested"].queryset = Room.objects.all()
        self.hire_dates = [
            d for d in enquiry.dates() if d.accepted
        ] or enquiry.dates()[:1]
        for d in self.hire_dates:
            local_start = timezone.localtime(d.start)
            local_end = timezone.localtime(d.end)
            self.fields[f"start_{d.pk}"] = forms.TimeField(
                label="Event starts",
                initial=local_start.time().replace(second=0, microsecond=0),
                widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            )
            self.fields[f"end_{d.pk}"] = forms.TimeField(
                label="Event ends",
                initial=local_end.time().replace(second=0, microsecond=0),
                widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            )

    def time_rows(self):
        return [
            (d, self[f"start_{d.pk}"], self[f"end_{d.pk}"])
            for d in self.hire_dates
        ]

    def clean(self):
        data = super().clean()
        enquiry = self.enquiry
        sound = data.get("sound_tech")
        hire_type = enquiry.hire_type
        if hire_type and hire_type.needs_sound_tech and sound == "none":
            self.add_error(
                "sound_tech",
                "This kind of event needs a sound tech. Choose one of the "
                "other options.",
            )
        if sound == "own" and not data.get("sound_tech_name"):
            self.add_error("sound_tech_name", "Please name your tech.")
        self.new_times = {}
        for d in self.hire_dates:
            s, e = data.get(f"start_{d.pk}"), data.get(f"end_{d.pk}")
            if not (s and e):
                continue
            day = timezone.localtime(d.get_in).date()
            st = _combine(day, s)
            while st < d.get_in:
                st += datetime.timedelta(days=1)
            en = _combine(timezone.localtime(st).date(), e)
            while en <= st:
                en += datetime.timedelta(days=1)
            if st < d.get_in or en > d.get_out:
                self.add_error(
                    f"start_{d.pk}",
                    "The event has to sit inside the time you asked for the "
                    f"building ({timezone.localtime(d.get_in):%H:%M} to "
                    f"{timezone.localtime(d.get_out):%H:%M}). If you need "
                    "longer, please tell us and we'll adjust it.",
                )
                continue
            self.new_times[d.pk] = (st, en)
        return data


SETTINGS_GROUPS = [
    (
        "Opening and closing",
        "Is the form taking enquiries right now? (The whole-feature on/off "
        "switch is in Site settings.)",
        [
            "enquiries_open",
            "closed_message",
            "booking_window_start",
            "booking_window_end",
        ],
    ),
    (
        "Wording on the public form",
        "",
        [
            "how_we_work_text",
            "tier_guidance_text",
            "acknowledgement_statements",
            "privacy_notice_text",
            "privacy_contact",
        ],
    ),
    (
        "Who gets internal emails",
        "",
        ["notification_addresses"],
    ),
    (
        "Building time",
        "",
        [
            "min_duration_hours",
            "default_setup_minutes",
            "default_teardown_minutes",
        ],
    ),
    (
        "Late nights and door staff",
        "Late finishes are discouraged but possible. What hirers see is the "
        "wording and fees below. The security cost and licence limit are "
        "internal and never shown to hirers.",
        [
            "late_night_from",
            "late_night_fee_gbp",
            "door_staff_fee_gbp",
            "late_night_notice_text",
            "door_staff_notice_text",
            "late_night_ack_statement",
            "late_night_security_cost_gbp",
            "late_night_licences_per_year",
        ],
    ),
    (
        "The reply clock",
        "Every hirer is promised an answer. These control when the "
        "reminders go out and when an unanswered enquiry is honestly "
        "declined.",
        [
            "min_notice_days_before_meeting",
            "reply_grace_days",
            "digest_days_before_meeting",
            "warning_days",
            "callout_days",
            "fallback_reply_days",
        ],
    ),
    (
        "Money and privacy",
        "",
        [
            "volunteer_event_net_cost_gbp",
            "declined_purge_months",
            "hirer_purge_years",
        ],
    ),
]

SETTINGS_HELP = {
    "min_duration_hours": "Shortest total time in the building, from get-in to get-out, that we'll take a hire for. Hire types can override this.",
    "default_setup_minutes": "Until the hirer gives exact event times, the event is assumed to start this long after the building opens.",
    "default_teardown_minutes": "...and to end this long before everything must be out.",
    "late_night_from": "A hire whose get-out is after this time counts as a late night.",
    "late_night_notice_text": "Shown to hirers who ask for a late finish. Placeholders: {late_from}, {late_fee}.",
    "door_staff_notice_text": "Shown to hirers when door staff are required (late club nights). Placeholder: {door_fee}. Say why, and that it is an extra cost to them.",
    "late_night_ack_statement": "The tickbox a hirer must tick before asking for a late finish.",
    "late_night_fee_gbp": "Extra fee charged for late finishes (unless the hire type already covers them).",
    "late_night_security_cost_gbp": "What a late night costs us in security. Internal: subtracted from the income estimate so late nights do not look better than they are, and never quoted to a hirer.",
    "late_night_licences_per_year": "How many late-night licences you have a year. Shows the meeting how many late hires are already accepted this year (hires only; add your own late events). Blank hides it.",
    "min_notice_days_before_meeting": "An enquiry arriving fewer than this many days before a meeting goes to the next meeting instead.",
    "reply_grace_days": "Days after the meeting by which the hirer is promised an answer. If nobody has decided by then, they get the honest 'no capacity' email.",
    "digest_days_before_meeting": "How many days before each meeting the digest email goes to the notification list.",
    "warning_days": "How many days before an auto-decline the 'last call' email goes out.",
    "callout_days": "How long a 'Maybe' stays open looking for a volunteer coordinator before the hirer is told no.",
    "fallback_reply_days": "If no meeting is entered, hirers are promised an answer within this many days.",
    "declined_purge_months": "Personal details on declined or withdrawn enquiries are deleted this many months after closing. A daily job does this, and it is the figure shown to hirers on the form.",
    "hirer_purge_years": "Contact details of hirers who hired, and their Hirer record, are deleted this many years after the hire or last contact. The agreed terms and fee are kept as a financial record.",
    "booking_window_start": "Start of the dates we are actively booking. Optional.",
    "privacy_contact": "Where privacy questions go. Use a role address, not a person.",
}


class HireSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, text in SETTINGS_HELP.items():
            if name in self.fields:
                self.fields[name].help_text = text

    def grouped(self):
        return [
            (title, intro, [self[n] for n in names])
            for title, intro, names in SETTINGS_GROUPS
        ]

    class Meta:
        model = HireSettings
        exclude = ("id",)
        widgets = {
            "booking_window_start": forms.DateInput(attrs={"type": "date"}),
            "booking_window_end": forms.DateInput(attrs={"type": "date"}),
            "late_night_from": forms.TimeInput(attrs={"type": "time"}),
        }


class MeetingForm(forms.ModelForm):
    class Meta:
        model = ProgrammingMeeting
        fields = ["date", "kind", "notes"]
        labels = {"kind": "Type of meeting"}
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class HireTypeForm(forms.ModelForm):
    class Meta:
        model = HireType
        exclude = ()
        labels = {
            "community_fee_gbp": "Community fee (£)",
            "corporate_fee_gbp": "Corporate fee (£)",
            "vat_applies": "VAT is added on top",
            "min_duration_hours": "Minimum hours in the building",
            "needs_sound_tech": "Needs a sound tech (hirer can't say 'not needed')",
            "includes_late_night": "Price already covers late finishes",
            "provides_door_staff": "We guarantee door staff when it runs late",
            "unit": "Fee is charged",
            "public_description": "Description shown to hirers",
            "order": "Position in the list",
            "active": "Offer this on the form",
        }
        help_texts = {
            "unit": "Flat = one price per hire. Per hour or per 4-hour block = fee multiplied by the time in the building (get-in to get-out).",
            "min_duration_hours": "Blank = the site default in Hire settings.",
        }


class ApprovedTechForm(forms.ModelForm):
    class Meta:
        model = ApprovedTech
        exclude = ("consented_at",)
        labels = {
            "rate_text": "Rate (as they quote it)",
            "share_with_hirers": "OK to give their details to hirers",
            "notes": "Internal notes (never shown to hirers)",
            "active": "Still working with us",
        }
        help_texts = {
            "share_with_hirers": "Only tick once they have agreed. Their name, rate and contact details are then included in the 'Accepted' email.",
            "rate_text": "Free text, e.g. '£80 per gig'. Techs quote differently.",
        }


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = HireEmailTemplate
        fields = ["key", "subject", "body"]
        widgets = {"key": forms.HiddenInput}
