import datetime

from django import forms
from django.db import models
from django.forms import inlineformset_factory
from django.conf import settings
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Field, Layout

from toolkit.diary.form_widgets import (
    HtmlTextarea,
    JQueryDateTimePicker,
    MultiDatePickerWidget,
    TagPillSelect,
)

import toolkit.diary.models
from toolkit.diary.models import get_site_config
from toolkit.members.models import Volunteer

from toolkit.diary.validators import validate_in_future

_COST_FIELDS = (
    "no_financial_activity",
    "cost_type",
    "cost_distributor",
    "cost_flat_fee_gbp",
    "cost_fee_includes_vat",
    "cost_percentage_split",
    "cost_minimum_guarantee_gbp",
    "cost_total_gbp",
    "cost_rider_notes",
    "cost_sound_engineer_name",
    "cost_sound_engineer_fee_gbp",
    "cost_sound_engineer_paid_by",
)


def _card_open(section_id: str, title: str, start_open: bool = True) -> str:
    expanded = "true" if start_open else "false"
    show_class = " show" if start_open else ""
    arrow_style = "transform:rotate(90deg)" if start_open else ""
    return (
        f'<div class="card mb-3">'
        f'<div class="card-header p-2" id="{section_id}-hdr" '
        f'style="cursor:pointer;user-select:none;" '
        f'data-bs-toggle="collapse" data-bs-target="#{section_id}-body" '
        f'aria-expanded="{expanded}" aria-controls="{section_id}-body">'
        f'<span class="section-arrow" style="{arrow_style}">&#9658;</span>'
        f"<strong>{title}</strong>"
        f"</div>"
        f'<div id="{section_id}-body" class="collapse{show_class}">'
        f'<div class="card-body pt-2 pb-1">'
    )


_CARD_CLOSE = "</div></div></div>"


class _VolunteerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.member.name


class EventForm(forms.ModelForm):
    programmer = _VolunteerChoiceField(
        queryset=Volunteer.objects.filter(
            status=Volunteer.STATUS_ACTIVE
        ).select_related("member"),
        required=False,
        help_text=(
            "Who owns this event -- who to contact about it. "
            "Only one person; use the Role system on the rota to share "
            "credit informally if more than one volunteer is involved."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If the current programmer has since gone dormant/retired, keep them
        # selectable so re-saving the form doesn't silently unset them.
        current_programmer_id = getattr(self.instance, "programmer_id", None)
        if current_programmer_id:
            self.fields["programmer"].queryset = Volunteer.objects.filter(
                models.Q(status=Volunteer.STATUS_ACTIVE)
                | models.Q(pk=current_programmer_id)
            ).select_related("member")
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"
        # Build age restriction choices from site config so venues can use
        # their own rating scheme (BBFC, FSK, etc.) without a code change.
        cfg = get_site_config()
        # Remove structured cost fields when the feature flag is off so they
        # don't appear in the form and can't be submitted.
        if not cfg.structured_cost_terms_enabled:
            for f in _COST_FIELDS:
                self.fields.pop(f, None)
        choices = [("", "Not stated")] + [
            (e["value"], e["label"])
            for e in cfg.age_rating_choices
            if e.get("value")
        ]
        self.fields["age_restriction"].widget = forms.Select(choices=choices)
        self.fields["age_restriction"].widget.attrs.setdefault(
            "class", "form-select"
        )

        if cfg.structured_cost_terms_enabled:
            cost_and_terms = [
                HTML(_card_open("costs", "Cost &amp; terms")),
                "no_financial_activity",
                "cost_type",
                "cost_distributor",
                "cost_flat_fee_gbp",
                "cost_fee_includes_vat",
                "cost_percentage_split",
                "cost_minimum_guarantee_gbp",
                "cost_total_gbp",
                "terms",
                "cost_rider_notes",
                "cost_sound_engineer_name",
                "cost_sound_engineer_fee_gbp",
                "cost_sound_engineer_paid_by",
                HTML(_CARD_CLOSE),
            ]
        else:
            cost_and_terms = [
                HTML(_card_open("terms", "Terms")),
                "terms",
                HTML(_CARD_CLOSE),
            ]
        self.helper.layout = Layout(
            HTML(_card_open("basics", "Basics")),
            "name",
            "tags",
            HTML(_CARD_CLOSE),
            HTML(_card_open("public", "Public listing")),
            "pricing",
            "ticket_link",
            "trailer_url",
            "film_information",
            "age_restriction",
            "pre_title",
            "post_title",
            HTML(_CARD_CLOSE),
            HTML(_card_open("programming", "Programming")),
            "programmer",
            "approval_type",
            "approved_at_meeting_date",
            "meeting_name",
            "meeting_minutes_url",
            "programming_status",
            "programming_notes",
            "duration",
            HTML(_CARD_CLOSE),
            HTML(_card_open("access", "Visibility &amp; access")),
            "outside_hire",
            "hire_name",
            "private",
            HTML(_CARD_CLOSE),
            HTML(_card_open("description", "Description")),
            "copy",
            "copy_summary",
            HTML(_CARD_CLOSE),
            *cost_and_terms,
        )
        for field in self.fields.values():
            field.help_text = ""

    class Meta:
        model = toolkit.diary.models.Event
        # Ensure soft wrapping is set for textareas:
        widgets = {
            # Use the custom WYSIWYG text editor widget:
            "copy": HtmlTextarea(attrs={"wrap": "soft"}),
            "copy_summary": forms.Textarea(attrs={"wrap": "soft"}),
            "terms": forms.Textarea(
                attrs={
                    "wrap": "soft",
                    "placeholder": f"e.g {settings.DEFAULT_TERMS_TEXT}",
                }
            ),
            "cost_flat_fee_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_percentage_split": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "max": "100",
                    "style": "width:7em",
                }
            ),
            "cost_minimum_guarantee_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_total_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_rider_notes": forms.Textarea(
                attrs={"wrap": "soft", "rows": 3}
            ),
            "cost_sound_engineer_fee_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_sound_engineer_paid_by": forms.Select(
                attrs={"style": "width:auto"}
            ),
            "programming_notes": forms.Textarea(
                attrs={
                    "wrap": "soft",
                    "rows": 5,
                    "placeholder": "e.g. Looking for a Friday in May; tech rider: DCP, 5.1 audio, projector set up by noon",
                }
            ),
            "approved_at_meeting_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "pricing": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. '\u00a30 Full / \u00a30 Concession' "
                        "or '\u00a30 advance, \u00a30 on the door'"
                    ),
                }
            ),
            "film_information": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Dir: [director], 1990, USA, 120 mins, "
                    "Cert: 15",
                }
            ),
            "pre_title": forms.TextInput(
                attrs={
                    "placeholder": (
                        (
                            f"Text displayed before / above the event"
                            f"name, e.g. '{settings.VENUE['name']} presents'"
                        )
                    ),
                }
            ),
            "post_title": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Text displayed after / below the event name,"
                        " e.g. 'with support from A Band'"
                    ),
                }
            ),
            "tags": TagPillSelect(),
            "trailer_url": forms.URLInput(
                attrs={
                    "placeholder": "e.g. https://www.youtube.com/watch?v=…",
                }
            ),
        }
        order = ("tags",)
        fields = (
            "name",
            "tags",
            "pricing",
            "ticket_link",
            "trailer_url",
            "film_information",
            "age_restriction",
            "pre_title",
            "post_title",
            "approval_type",
            "approved_at_meeting_date",
            "meeting_name",
            "meeting_minutes_url",
            "programming_status",
            "programming_notes",
            "programmer",
            "duration",
            "outside_hire",
            "hire_name",
            "private",
            "copy",
            "copy_summary",
            "no_financial_activity",
            "cost_type",
            "cost_distributor",
            "cost_flat_fee_gbp",
            "cost_fee_includes_vat",
            "cost_percentage_split",
            "cost_minimum_guarantee_gbp",
            "cost_total_gbp",
            "terms",
            "cost_rider_notes",
            "cost_sound_engineer_name",
            "cost_sound_engineer_fee_gbp",
            "cost_sound_engineer_paid_by",
        )

    def clean_terms(self):
        terms = self.cleaned_data.get("terms", "")
        if "[" in terms and "]" in terms:
            raise forms.ValidationError(
                "The terms look like they still contain unfilled placeholders (e.g. [Distributor]). "
                "Please fill in all the bracketed sections before saving."
            )
        return terms

    def clean_film_information(self):
        film_info = self.cleaned_data.get("film_information", "")
        if "[" in film_info and "]" in film_info:
            raise forms.ValidationError(
                "The screening details look like they still contain unfilled placeholders (e.g. [Director]). "
                "Please fill in all the bracketed sections before saving."
            )
        return film_info

    def clean_copy_summary(self):
        copy_summary = self.cleaned_data.get("copy_summary", "")
        max_chars = get_site_config().programme_copy_summary_max_chars
        if len(copy_summary) > max_chars:
            raise forms.ValidationError(
                f"Copy summary must be {max_chars} "
                f"characters or fewer (currently {len(copy_summary)} characters)"
            )
        return copy_summary

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("approval_type")
            == toolkit.diary.models.Event.APPROVAL_MEETING
        ):
            if not cleaned_data.get("approved_at_meeting_date"):
                self.add_error(
                    "approved_at_meeting_date",
                    "Please enter the date of the meeting at which this was approved.",
                )
            else:
                # Meeting approved with a date set → treat as active.
                cleaned_data["programming_status"] = "active"
        if self.instance.all_showings_confirmed():
            terms = cleaned_data.get("terms", "")
            terms_word_count = len(terms.split())

            terms_not_required = cleaned_data.get(
                "tags"
            ).contains_tag_to_not_need_terms()

            cost_type = cleaned_data.get("cost_type")
            cost_type_set = bool(
                cost_type
                and cost_type != toolkit.diary.models.Event.COST_TYPE_TBC
            )
            # Decided upfront, at terms-entry time (not after the fact at
            # settlement time), so low-stakes rota items never pay a
            # financial-admin tax for existing. Recuses from stating cost
            # terms and from the 9.169 programmer hard block; distinct from
            # terms_not_required (tags), which only waives the free-text
            # Terms field.
            no_financial_activity = bool(
                cleaned_data.get("no_financial_activity")
            )

            cfg = get_site_config()
            min_words = cfg.programme_event_terms_min_words

            if (
                cfg.structured_cost_terms_enabled
                and cfg.structured_cost_required
                and not cost_type_set
                and not terms_not_required
                and not no_financial_activity
            ):
                self.add_error(
                    "cost_type",
                    f"Cost type must be set (to something other than TBC) before "
                    f"'{self.instance.name}' can be confirmed, or tick "
                    f"'No financial activity' above.",
                )

            if (
                terms_word_count < min_words
                and not terms_not_required
                and not cost_type_set
                and not no_financial_activity
            ):
                msg = (
                    f"Event terms for confirmed event '{self.instance.name}' "
                    f"are missing or too short. Please enter at least "
                    f"{min_words} words, or set the cost type above."
                )
                self.add_error("terms", msg)

            if (
                cfg.structured_cost_terms_enabled
                and cfg.programmer_required_for_financial_events
                and cost_type_set
                and not no_financial_activity
                and not cleaned_data.get("programmer")
            ):
                self.add_error(
                    "programmer",
                    f"A programmer must be set before '{self.instance.name}' "
                    f"can be confirmed, since it has financial terms attached "
                    f"-- there has to be someone on the line for that.",
                )
        return cleaned_data


class MediaItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"

        guidance_url = get_site_config().alt_text_guidance_url or None
        if guidance_url:
            from django.utils.safestring import mark_safe

            base = self.fields["alt_text"].help_text
            self.fields["alt_text"].help_text = mark_safe(
                f'{base} <a href="{guidance_url}" target="_blank" rel="noopener">Guide ↗</a>'
            )

    class Meta:
        model = toolkit.diary.models.MediaItem
        widgets = {
            "media_file": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/gif,image/png"}
            ),
            "alt_text": forms.Textarea(
                attrs={
                    "rows": 3,
                    "style": "resize: vertical;",
                    "class": "form-control",
                }
            ),
            "bar_colour": forms.HiddenInput(),
            "crop_x": forms.HiddenInput(),
            "crop_y": forms.HiddenInput(),
            "crop_w": forms.HiddenInput(),
            "crop_h": forms.HiddenInput(),
        }
        exclude = ("mimetype", "caption")

    def clean_media_file(self):
        media_file = self.cleaned_data.get("media_file", None)
        if media_file:
            size_MB = media_file.size / 1048576.0
            max_MB = get_site_config().programme_media_max_size_mb
            if size_MB > max_MB:
                raise forms.ValidationError(
                    f"Media file must be {max_MB} MB or less "
                    f"(uploaded file is {size_MB:.2f} MB)"
                )
        return media_file


class EventLinkForm(forms.ModelForm):
    """Single event resource link (label + URL). Used inside EventLinkFormSet."""

    class Meta:
        model = toolkit.diary.models.EventLink
        fields = ("label", "url")
        widgets = {
            "label": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Event folder, Crew chat…",
                    "class": "form-control form-control-sm",
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "placeholder": "https://…",
                    "class": "form-control form-control-sm",
                }
            ),
        }
        labels = {
            "label": "Link name",
            "url": "URL",
        }


# Inline formset: up to 3 EventLink rows per Event.
# extra=3 so Django pads to max_num=3 with blank rows; validate_max=True so
# attempts to submit >3 links are rejected rather than silently truncated.
EventLinkFormSet = inlineformset_factory(
    toolkit.diary.models.Event,
    toolkit.diary.models.EventLink,
    form=EventLinkForm,
    extra=3,
    max_num=3,
    validate_max=True,
    can_delete=True,
)


class EventBudgetLineForm(forms.ModelForm):
    """A single budget row (category/item, estimate, actual).

    category/item/direction/order/estimate_source are hidden: they're set
    programmatically by sync_budget_lines_for_event() and by the
    budget-grid's "override" JS, not free-text-editable -- letting a
    programmer silently rename a category would defeat the point of the
    fixed, collectively-agreed category templates. estimate_gbp is shown
    read-only (via the template) for derived rows until "override" unlocks
    it; item is unhidden for ad-hoc rows added via "Add item".
    """

    class Meta:
        model = toolkit.diary.models.EventBudgetLine
        fields = (
            "direction",
            "category",
            "item",
            "estimate_gbp",
            "estimate_source",
            "actual_gbp",
            "notes",
            "order",
        )
        widgets = {
            "direction": forms.HiddenInput(),
            "category": forms.HiddenInput(),
            "item": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm budget-item-input",
                    "placeholder": "Item (optional)",
                }
            ),
            "estimate_source": forms.HiddenInput(),
            "order": forms.HiddenInput(),
            "estimate_gbp": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "class": "form-control form-control-sm budget-estimate-input",
                }
            ),
            "actual_gbp": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "class": "form-control form-control-sm budget-actual-input",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 2,
                    "wrap": "soft",
                }
            ),
        }


EventBudgetLineInlineFormSet = inlineformset_factory(
    toolkit.diary.models.Event,
    toolkit.diary.models.EventBudgetLine,
    form=EventBudgetLineForm,
    extra=0,
    can_delete=True,
)


def _target_month_choices():
    """Generate (YYYY-MM, "Month YYYY") choices for the next 18 months."""
    today = datetime.date.today()
    choices = [("", "— no target month —")]
    for i in range(18):
        month = today.month - 1 + i
        year = today.year + month // 12
        month = month % 12 + 1
        d = datetime.date(year, month, 1)
        choices.append((d.strftime("%Y-%m"), d.strftime("%B %Y")))
    return choices


_MAX_BATCH_SHOWINGS = 52


class NewEventForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"
        self.helper.layout = Layout(
            Field(
                "entry_mode"
            ),  # renders as hidden input; card UI is in the template
            HTML(
                '<div class="new-event-zone new-event-zone--required">'
                '<h3 class="new-event-zone__title">Book it now</h3>'
                '<p class="new-event-zone__hint text-muted">'
                "A placeholder with these four fields is enough to hold a space on the calendar. "
                "Everything else can be filled in from the Event Hub after creating."
                "</p>"
            ),
            Field("event_name"),
            Field("event_template"),
            HTML(
                '<div class="form-group row" id="template-preview-row" style="display:none">'
                '<div class="col-sm-2"></div>'
                '<div class="col-sm-10"><div id="template-preview"></div></div>'
                "</div>"
            ),
            Field("dates"),
            HTML('<div id="target-month-row">'),
            Field("target_month"),
            HTML("</div>"),
            Field("start_time"),
            HTML("</div>"),
            HTML(
                '<div class="new-event-zone new-event-zone--optional">'
                '<h3 class="new-event-zone__title">'
                'Details <small class="text-muted fw-normal">&mdash; amend any time from the Event Hub</small>'
                "</h3>"
            ),
            Field("duration"),
            Field("booked_by"),
            Field("private"),
            Field("outside_hire"),
            Field("discounted"),
            HTML("</div>"),
        )

    ENTRY_MODE_QUEUE = "queue"
    ENTRY_MODE_STANDING = "standing"
    ENTRY_MODE_TENTATIVE = "tentative"
    ENTRY_MODE_CHOICES = [
        ("queue", "Needs meeting approval"),
        ("standing", "Regular / standing event"),
        ("tentative", "Tentative placeholder"),
    ]
    entry_mode = forms.ChoiceField(
        choices=ENTRY_MODE_CHOICES,
        initial="queue",
        widget=forms.HiddenInput,
        label="",
    )

    event_name = forms.CharField(min_length=1, max_length=256, required=True)
    event_template = forms.ModelChoiceField(
        queryset=toolkit.diary.models.EventTemplate.objects.all(),
        required=True,
    )
    dates = forms.CharField(
        widget=MultiDatePickerWidget(),
        label="Date(s)",
        required=False,
        help_text="Optional — leave blank if the date is still TBC. Dates can be added later from the Event Hub.",
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Start time",
        required=False,
        initial=datetime.time(20, 0),
    )
    duration = forms.TimeField(required=True, initial=datetime.time(hour=1))
    booked_by = forms.CharField(min_length=1, max_length=64, required=True)
    target_month = forms.ChoiceField(
        choices=_target_month_choices,
        label="Target month",
        required=False,
        help_text="Which month are you roughly targeting? Shown in the diary to help plan the programme.",
    )
    private = forms.BooleanField(required=False)
    outside_hire = forms.BooleanField(required=False)
    # confirmed = forms.BooleanField(required=False)
    discounted = forms.BooleanField(required=False)

    def clean_target_month(self):
        # ChoiceField gives us YYYY-MM; normalise to the 1st of that month.
        raw = (self.cleaned_data.get("target_month") or "").strip()
        if not raw:
            return None
        if len(raw) == 7:
            raw = raw + "-01"
        try:
            return datetime.date.fromisoformat(raw)
        except ValueError:
            raise forms.ValidationError("Select a valid month.")

    def clean_dates(self):
        raw = self.cleaned_data.get("dates", "").strip()
        if not raw:
            return []
        parsed = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                parsed.append(datetime.date.fromisoformat(part))
            except ValueError:
                raise forms.ValidationError(
                    "Unrecognised date: {!r}. Expected YYYY-MM-DD.".format(
                        part
                    )
                )
        if len(parsed) > _MAX_BATCH_SHOWINGS:
            raise forms.ValidationError(
                "Maximum {} dates.".format(_MAX_BATCH_SHOWINGS)
            )
        return sorted(set(parsed))

    def clean(self):
        cleaned = super().clean()
        dates = cleaned.get("dates")
        start_time = cleaned.get("start_time")
        if dates and not start_time:
            self.add_error(
                "start_time", "Select a start time for the date(s) you chose."
            )
        if dates and start_time:
            now = timezone.now()
            past = [
                d
                for d in dates
                if timezone.make_aware(
                    datetime.datetime.combine(d, start_time)
                )
                <= now
            ]
            if past:
                date_strs = ", ".join(d.strftime("%-d %b %Y") for d in past)
                raise forms.ValidationError(
                    "The following dates are in the past: {}.".format(
                        date_strs
                    )
                )
        return cleaned


class CloneEventForm(forms.Form):
    """Minimal details needed to clone an existing event as a new event.

    The new event inherits all text/config fields (copy, terms, rota, etc.)
    from the source.  The programmer only needs to confirm the name, first
    showing date, and who booked it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-3"
        self.helper.field_class = "col-sm-9"

    event_name = forms.CharField(
        min_length=1,
        max_length=256,
        required=True,
        label="New event name",
        help_text="Pre-filled from source — edit to give the new event a different title.",
    )
    start = forms.DateTimeField(
        required=True,
        validators=[validate_in_future],
        widget=JQueryDateTimePicker(),
        label="First showing date/time",
        help_text="Pre-filled to one week after the source's latest showing.",
    )
    room = forms.ModelChoiceField(
        queryset=toolkit.diary.models.Room.objects.all(),
        required=False,
        label="Room",
        empty_label="— no room —",
    )
    booked_by = forms.CharField(
        min_length=1,
        max_length=128,
        required=True,
        label="Booked by",
    )
