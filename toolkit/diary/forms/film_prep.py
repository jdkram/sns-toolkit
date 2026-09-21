# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Forms for film readiness tracking (task 9.174)."""

from django import forms
from django.forms import inlineformset_factory

from toolkit.diary.models import FilmCopy, FilmPrep


class _ShowingChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, showing):
        label = showing.start.strftime("%a %d %b %Y, %H:%M")
        if showing.cancelled:
            label += " (cancelled)"
        return label


class FilmPrepForm(forms.ModelForm):
    """One film: its details, and which of the event's showings it plays at.

    Pass ``event`` for a new film; an existing film already knows its event.
    """

    showings = _ShowingChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        required=False,  # clean_showings gives the friendlier message
        label="Plays at",
        help_text=(
            "Tick every showing that plays this film. Same film all run: tick "
            "every date. Different film each night: add one film per date."
        ),
    )

    class Meta:
        model = FilmPrep
        fields = (
            "film_title",
            "bill_position",
            "showings",
            "subtitles",
            "backup_in_place",
            "backup_note",
            "trailers_plan",
            "booth_notes",
            "handover_note",
        )
        widgets = {
            "film_title": forms.TextInput(attrs={"class": "form-control"}),
            "bill_position": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "9"}
            ),
            "subtitles": forms.Select(attrs={"class": "form-select"}),
            "backup_in_place": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "backup_note": forms.TextInput(attrs={"class": "form-control"}),
            "trailers_plan": forms.Textarea(
                attrs={"class": "form-control", "rows": 2}
            ),
            "booth_notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 2}
            ),
            "handover_note": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
        }

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        event = event or self.instance.event
        self.fields["showings"].queryset = event.showings.order_by("start")

    def clean_showings(self):
        showings = self.cleaned_data["showings"]
        if not showings:
            raise forms.ValidationError(
                "Tick at least one showing, or the film will not appear "
                "on the dashboard."
            )
        return showings


class FilmCopyForm(forms.ModelForm):
    class Meta:
        model = FilmCopy
        fields = ("label", "format", "location_note")
        widgets = {
            "label": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "format": forms.Select(
                attrs={"class": "form-select form-select-sm"}
            ),
            "location_note": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
        }


# One blank row to start; a second copy (backup) is one save away.
FilmCopyFormSet = inlineformset_factory(
    FilmPrep,
    FilmCopy,
    form=FilmCopyForm,
    extra=1,
    can_delete=True,
)
