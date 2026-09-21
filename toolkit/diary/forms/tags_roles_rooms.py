import datetime

from django import forms
from django.forms import inlineformset_factory

import toolkit.diary.models


class RoleForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.Role
        fields = (
            "name",
            "standard",
            "description",
            "stats_label",
            "beginner_friendly",
            "wheelchair_accessible",
            "keyholder_only",
            "is_projectionist",
            "required_qualification",
            "qualification_gate",
        )


class RoomForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.Room
        fields = ("name", "colour", "is_primary", "show_column", "map_slug")
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "colour": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "form-control form-control-sm",
                    "style": "max-width: 80px; padding: 2px 4px;",
                }
            ),
            "map_slug": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "e.g. room-cinema",
                }
            ),
        }


class RoomBookingForm(forms.ModelForm):
    """A single room booking slot for a Showing (room + time window + notes).

    start_time / end_time are time-only fields; the showing's local date is
    combined with them on save.  date_offset shifts the date relative to the
    Showing's date (0 = same day, -1 = day before, +1 = day after).
    """

    date_offset = forms.TypedChoiceField(
        choices=[(0, "Same day"), (-1, "Day before"), (1, "Day after")],
        coerce=int,
        initial=0,
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
        label="Day",
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control form-control-sm"},
            format="%H:%M",
        ),
        label="Start",
    )
    end_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control form-control-sm"},
            format="%H:%M",
        ),
        label="End",
    )

    class Meta:
        model = toolkit.diary.models.RoomBooking
        fields = ("room", "date_offset", "notes")
        widgets = {
            "notes": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Tech setup only, not public",
                    "class": "form-control form-control-sm",
                }
            ),
        }
        labels = {"notes": "Notes (optional)"}

    def __init__(self, *args, showing_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.showing_date = showing_date
        # Pre-populate time and offset fields from existing instance
        if self.instance and self.instance.pk and self.instance.start:
            import django.utils.timezone as dj_tz

            self.initial["start_time"] = dj_tz.localtime(
                self.instance.start
            ).strftime("%H:%M")
            if self.instance.end:
                self.initial["end_time"] = dj_tz.localtime(
                    self.instance.end
                ).strftime("%H:%M")
            self.initial["date_offset"] = self.instance.date_offset

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.showing_date and self.cleaned_data.get("start_time"):
            import django.utils.timezone as dj_tz

            tz = dj_tz.get_current_timezone()
            offset = self.cleaned_data.get("date_offset") or 0
            actual_date = self.showing_date + datetime.timedelta(days=offset)
            instance.start = dj_tz.make_aware(
                datetime.datetime.combine(
                    actual_date, self.cleaned_data["start_time"]
                ),
                tz,
            )
            end_t = self.cleaned_data.get("end_time")
            instance.end = (
                dj_tz.make_aware(
                    datetime.datetime.combine(actual_date, end_t), tz
                )
                if end_t
                else None
            )
        if commit:
            instance.save()
            self.save_m2m()
        return instance


RoomBookingInlineFormSet = inlineformset_factory(
    toolkit.diary.models.Showing,
    toolkit.diary.models.RoomBooking,
    form=RoomBookingForm,
    extra=0,
    can_delete=True,
    min_num=0,
)
