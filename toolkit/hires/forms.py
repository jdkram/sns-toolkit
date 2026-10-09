# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from django import forms
from django.utils import timezone

from toolkit.diary.models import Room

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

N_DATE_ROWS = 3


def _combine(date, time):
    return timezone.make_aware(datetime.datetime.combine(date, time))


class HireEnquiryForm(forms.Form):
    """Public enquiry form. Core fields fixed in code (spec: hybrid)."""

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
    )
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
        max_length=200, required=False, label="Name of your own tech"
    )
    offers_to_volunteers = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="What can you offer the volunteers who help?",
        help_text="For example food, a guest list, or a thank-you.",
    )
    date_flexible = forms.BooleanField(
        required=False, label="My dates are flexible"
    )
    flexibility_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Anything we should know about flexibility?",
    )
    acknowledgements = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        label="Please confirm you understand",
        error_messages={
            "required": "Please tick every box so we know you've read them."
        },
    )
    # Honeypot: real people leave this blank.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cfg = get_hire_settings()
        self.cfg = cfg
        self.fields["hire_type"].queryset = HireType.objects.filter(
            active=True
        )
        self.fields["rooms_requested"].queryset = Room.objects.all()
        self.statements = cfg.acknowledgement_list()
        self.fields["acknowledgements"].choices = [
            (s, s) for s in self.statements
        ]
        for i in range(1, N_DATE_ROWS + 1):
            req = i == 1
            self.fields[f"date_{i}"] = forms.DateField(
                required=req,
                label=f"Date {i}",
                widget=forms.DateInput(attrs={"type": "date"}),
            )
            for key, label in (
                ("get_in", "Get-in: we open the building at"),
                ("start", "Event starts"),
                ("end", "Event ends"),
                ("get_out", "Everything packed up and out by"),
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
                    self[f"start_{i}"],
                    self[f"end_{i}"],
                    self[f"get_out_{i}"],
                ],
            }
            for i in range(1, N_DATE_ROWS + 1)
        ]

    def error_summary(self):
        """(anchor, label) per problem, one entry per date row."""
        rows = []
        seen_dates = set()
        date_prefixes = ("date_", "get_in_", "start_", "end_", "get_out_")
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

    def clean_acknowledgements(self):
        ticked = self.cleaned_data.get("acknowledgements", [])
        missing = [s for s in self.statements if s not in ticked]
        if missing:
            raise forms.ValidationError(
                "Please tick every box so we know you've read them."
            )
        return ticked

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError("Spam check failed.")
        hire_type = data.get("hire_type")
        sound = data.get("sound_tech")
        if hire_type and hire_type.needs_sound_tech and sound == "none":
            self.add_error(
                "sound_tech",
                "This kind of event needs a sound tech. Choose one of the "
                "other options.",
            )
        if sound == "own" and not data.get("sound_tech_name"):
            self.add_error("sound_tech_name", "Please name your tech.")
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
            times = [
                data.get(f"{k}_{i}")
                for k in ("get_in", "start", "end", "get_out")
            ]
            if not all(times):
                self.add_error(
                    f"date_{i}", "Fill in all four times for this date."
                )
                continue
            get_in, start, end, get_out = times
            day = d
            gi = _combine(day, get_in)
            st = _combine(day, start)
            if st < gi:
                st += datetime.timedelta(days=1)
            en = _combine(day, end)
            while en <= st:
                en += datetime.timedelta(days=1)
            go = _combine(day, get_out)
            while go < en:
                go += datetime.timedelta(days=1)
            if st < now:
                self.add_error(f"date_{i}", "That date is in the past.")
                continue
            hours = (go - gi).total_seconds() / 3600
            if hours < min_hours:
                self.add_error(
                    f"date_{i}",
                    f"The whole time in the building, from get-in to "
                    f"get-out, must be at least {min_hours} hours (yours is "
                    f"{hours:.1f}). Most hirers underestimate setup and "
                    "pack-down, and the building has to be open, with a "
                    "keyholder present, for all of it.",
                )
                continue
            self.hire_dates.append(
                HireDate(get_in=gi, start=st, end=en, get_out=go)
            )
        if not self.hire_dates and not self.errors:
            raise forms.ValidationError("Please give at least one date.")
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
        "Building time and late nights",
        "",
        [
            "min_duration_hours",
            "default_setup_minutes",
            "default_teardown_minutes",
            "late_night_from",
            "late_night_fee_gbp",
            "late_night_security_cost_gbp",
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
    "default_setup_minutes": "Not used by the form yet (reserved for pre-filling get-in).",
    "default_teardown_minutes": "Not used by the form yet (reserved for pre-filling get-out).",
    "late_night_from": "A hire finishing after this time counts as late night.",
    "late_night_fee_gbp": "Extra fee charged for late finishes (unless the hire type already covers them).",
    "late_night_security_cost_gbp": "What a late night costs us in security. Subtracted from the income estimate so late nights don't look better than they are.",
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
