import datetime
import calendar

from django import forms
from django.conf import settings

import toolkit.diary.models


class PrintedProgrammeSeasonFormMixin:
    """Shared season (start/end month) fields and validation.

    A custom pair of month/year choice fields is used for each of start and
    end month (if the normal Date select is used there's no trivial way to
    hide the choice of day of month - plus this allows the available range
    of years to be limited to Cube founding through next year). The derived
    start_month/end_month are computed and validated (no overlap with an
    existing season) in clean().
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["start_year"].initial = self.instance.start_month.year
            self.fields["start_form_month"].initial = (
                self.instance.start_month.month
            )
            self.fields["end_year"].initial = self.instance.end_month.year
            self.fields["end_form_month"].initial = (
                self.instance.end_month.month
            )

    def clean(self):
        cleaned_data = super().clean()

        try:
            start_month = datetime.date(
                int(cleaned_data["start_year"]),
                int(cleaned_data["start_form_month"]),
                1,
            )
            end_month = datetime.date(
                int(cleaned_data["end_year"]),
                int(cleaned_data["end_form_month"]),
                1,
            )
        except (KeyError, ValueError, TypeError):
            raise forms.ValidationError(
                "Invalid/missing value for start/end month and/or year"
            )

        if start_month > end_month:
            self.add_error(
                "end_form_month",
                "End month must not be before start month.",
            )
            return cleaned_data

        overlapping = (
            toolkit.diary.models.PrintedProgramme.objects.seasons_overlapping(
                start_month, end_month
            )
        )
        if self.instance.pk:
            overlapping = overlapping.exclude(pk=self.instance.pk)
        if overlapping.exists():
            self.add_error(
                None,
                "This date range overlaps with an existing printed "
                "programme entry.",
            )
            return cleaned_data

        self.instance.start_month = start_month
        self.instance.end_month = end_month

        return cleaned_data


def _season_month_year_field(initial):
    return forms.ChoiceField(
        choices=[
            (y, y)
            for y in range(
                settings.DAWN_OF_TIME, datetime.date.today().year + 2
            )
        ],
        initial=initial,
    )


def _season_month_field(initial):
    return forms.ChoiceField(
        label="Month",
        choices=(list(zip(range(13), calendar.month_name))[1:]),
        initial=initial,
    )


class NewPrintedProgrammeForm(
    PrintedProgrammeSeasonFormMixin, forms.ModelForm
):
    start_year = _season_month_year_field(datetime.date.today().year)
    start_form_month = _season_month_field(datetime.date.today().month)
    end_year = _season_month_year_field(datetime.date.today().year)
    end_form_month = _season_month_field(datetime.date.today().month)

    class Meta:
        model = toolkit.diary.models.PrintedProgramme
        fields = (
            "start_form_month",
            "start_year",
            "end_form_month",
            "end_year",
            "programme",
            "designer",
            "notes",
        )


class EditPrintedProgrammeSeasonForm(
    PrintedProgrammeSeasonFormMixin, forms.ModelForm
):
    start_year = _season_month_year_field(datetime.date.today().year)
    start_form_month = _season_month_field(datetime.date.today().month)
    end_year = _season_month_year_field(datetime.date.today().year)
    end_form_month = _season_month_field(datetime.date.today().month)

    class Meta:
        model = toolkit.diary.models.PrintedProgramme
        fields = (
            "start_form_month",
            "start_year",
            "end_form_month",
            "end_year",
            "programme",
            "designer",
            "notes",
        )
