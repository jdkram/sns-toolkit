import datetime

import django.db.models
from django import forms
from django.conf import settings
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Fieldset, Layout

from toolkit.diary.form_widgets import (
    JQueryDateTimePicker,
    MultiDatePickerWidget,
)

import toolkit.diary.models
from toolkit.diary.models import get_site_config
from collections import OrderedDict

from toolkit.diary.validators import validate_in_future


class ShowingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        # Vertical (stacked) layout — labels sit above their fields. The old
        # form-horizontal layout crammed labels into a narrow 2-column strip,
        # which wrapped awkwardly (and pushed the ⓘ tooltip onto its own line)
        # and indented the status checkboxes oddly on narrow viewports.
        # Spell out what "confirmed" actually does — it's the publish + open-rota
        # switch, not just a tick (see also the per-occurrence buttons on the hub).
        self.fields["confirmed"].label = "Confirmed (public + rota open)"
        # Status/visibility toggles live in their own group below the booking
        # details rather than high up amongst date/time — they're a final step,
        # and the hub's buttons are the main way to set them.
        self.helper.layout = Layout(
            Field("start"),
            Field("booked_by"),
            # Call times grouped on one row — they collapse to stacked below sm.
            Div(
                Div(Field("setup_time"), css_class="col-sm-4"),
                Div(Field("doors_time"), css_class="col-sm-4"),
                Div(Field("final_volunteer_time"), css_class="col-sm-4"),
                css_class="row",
            ),
            Fieldset(
                "Status & visibility",
                "confirmed",
                "cancelled",
                "hide_in_programme",
                "sold_out",
                "discounted",
            ),
        )

    class Meta:
        model = toolkit.diary.models.Showing
        fields = (
            "start",
            "booked_by",
            "confirmed",
            "hide_in_programme",
            "cancelled",
            "sold_out",
            "discounted",
            "setup_time",
            "doors_time",
            "final_volunteer_time",
        )

        widgets = {
            "start": JQueryDateTimePicker(),
            "setup_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "doors_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "final_volunteer_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
        }

    def clean_confirmed(self):
        confirmed = self.cleaned_data["confirmed"]
        if (
            confirmed
            and self.instance.event_id
            and not self.instance.event.terms_satisfied()
        ):

            raise forms.ValidationError(
                "Events require terms information "
                # TAGS_WITHOUT_TERMS is settings-only — no SiteConfiguration counterpart.
                f'(unless they are tagged with one of {"/".join(sorted(settings.TAGS_WITHOUT_TERMS))}). '
                "Please add more details."
            )
        return confirmed

    def clean(self):
        if self.instance.original_start_in_past():
            self.cleaned_data["start"] = self.instance.start
            noun = get_site_config().occurrence_noun
            raise forms.ValidationError(f"Cannot amend a historic {noun}")
        return super().clean()


ShowingFormSet = forms.modelformset_factory(
    toolkit.diary.models.Showing,
    extra=1,
    form=ShowingForm,
)


class ShowingRotaNotesForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.Showing
        fields = ("rota_notes",)


def rota_form_factory(showing):
    # Dynamically generate a form to edit the rota for the given showing

    # Members for RotaForm class:
    members = OrderedDict()

    # All permanent roles (one-shot roles are handled separately in the view)
    roles = toolkit.diary.models.Role.objects.filter(
        is_one_shot=False
    ).order_by("name")

    # list of role IDs, to get stored in form and used to build rota from
    # submitted form data (as submitted data won't include IDs where rota
    # count is 0)
    _role_ids = []

    # Get all rota entries for showing, annotated with the maximum value of
    # "rank" for the role
    rota_entries = toolkit.diary.models.Role.objects.filter(
        rotaentry__showing_id=showing.pk
    ).annotate(max_rank=django.db.models.Max("rotaentry__rank"))

    # Build dict mapping role ID to max_rank
    rota_entry_count_by_role = dict(
        (role.pk, role.max_rank) for role in rota_entries
    )

    for role in roles:
        _role_ids.append(role.pk)
        # All roles get an IntegerField spinner.
        # Standard roles are prefixed "role_"; non-standard "other_" so the
        # template can render them in two visual groups with the same spinner UI.
        prefix = "role_" if role.standard else "other_"
        members[f"{prefix}{role.pk}"] = forms.IntegerField(
            min_value=0,
            max_value=get_site_config().max_count_per_role,
            required=False,  # Missing field treated as 0 — you don't need to explicitly zero every role
            label=role.name,
            initial=rota_entry_count_by_role.get(role.pk, 0),
            widget=forms.NumberInput(attrs={"class": "rota_count"}),
        )

    def get_rota(self):
        # Build a dict mapping role_id: number from submitted cleaned data.
        # None (missing/blank field) counts as 0.
        result = dict.fromkeys(self._role_ids, 0)
        for field, value in self.cleaned_data.items():
            if value is None:
                continue
            if field.startswith("role_"):
                result[int(field[5:])] = value
            elif field.startswith("other_"):
                result[int(field[6:])] = value
        return result

    members["_role_ids"] = _role_ids
    members["get_rota"] = get_rota

    return type("RotaForm", (forms.Form,), members)


class CloneShowingForm(forms.Form):
    # For cloning a showing, so only need very minimal extra details

    clone_start = forms.DateTimeField(
        required=True,
        validators=[validate_in_future],
        widget=JQueryDateTimePicker(),
    )
    booked_by = forms.CharField(min_length=1, max_length=128, required=True)


_MAX_BATCH_SHOWINGS = 52


class BatchAddShowingsForm(forms.Form):
    """Add multiple showings to an existing event on several dates at once.

    The programmer selects one or more dates via a flatpickr multi-date picker.
    All showings share the same start time, room, booked_by, and confirmed flag.
    """

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._event = event
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-3"
        self.helper.field_class = "col-sm-9"

    dates = forms.CharField(
        widget=MultiDatePickerWidget(),
        label="Dates",
        help_text="Click to select one or more dates (max {}).".format(
            _MAX_BATCH_SHOWINGS
        ),
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Start time",
        help_text="The time each showing starts. Applies to all selected dates.",
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
    confirmed = forms.BooleanField(
        required=False,
        label="Create as confirmed",
        help_text="Only tick if the event has terms set. Confirmed showings appear in the programme immediately.",
    )

    def clean_dates(self):
        raw = self.cleaned_data.get("dates", "").strip()
        if not raw:
            raise forms.ValidationError("Select at least one date.")
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
        if not parsed:
            raise forms.ValidationError("Select at least one date.")
        if len(parsed) > _MAX_BATCH_SHOWINGS:
            raise forms.ValidationError(
                "Maximum {} dates per batch.".format(_MAX_BATCH_SHOWINGS)
            )
        return sorted(set(parsed))

    def clean(self):
        cleaned = super().clean()
        dates = cleaned.get("dates")
        start_time = cleaned.get("start_time")
        if dates and start_time:
            now = datetime.datetime.now()
            past = [
                d
                for d in dates
                if datetime.datetime.combine(d, start_time) < now
            ]
            if past:
                date_strs = ", ".join(d.strftime("%-d %b %Y") for d in past)
                raise forms.ValidationError(
                    f"The following dates are in the past: {date_strs}."
                )
        if cleaned.get("confirmed") and self._event is not None:
            if not self._event.terms_satisfied():
                self.add_error(
                    "confirmed",
                    "Add terms to the event before creating confirmed showings.",
                )
        return cleaned


class QuickCreateOpenSessionForm(forms.Form):
    """Minimal form for a keyholder to announce the building is open."""

    date = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"}
        ),
        help_text="Which day? Defaults to today.",
    )
    opens_at = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control"}
        ),
        initial=datetime.time(14, 0),
        help_text="When will you open up?",
    )
    closes_at = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control"}
        ),
        initial=datetime.time(18, 0),
        help_text="When will you be locking up? Volunteers need to be out by this time.",
    )
    note = forms.CharField(
        max_length=256,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Print room is free all day",
            }
        ),
        help_text="Optional — anything useful for people dropping in.",
    )
