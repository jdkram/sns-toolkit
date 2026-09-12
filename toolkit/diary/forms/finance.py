# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Forms for event settlement records (task 9.171)."""

from django import forms
from django.forms import inlineformset_factory

from toolkit.diary.models import (
    Event,
    PerformerRegistration,
    PRSPerformerEntry,
    SettlementLineItem,
    ShowingSettlement,
)


class ShowingSettlementForm(forms.ModelForm):
    class Meta:
        model = ShowingSettlement
        fields = ("attendance", "bar_contribution_gbp", "notes")
        widgets = {
            "attendance": forms.NumberInput(
                attrs={"class": "form-control", "min": "0"}
            ),
            "bar_contribution_gbp": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 2}
            ),
        }


class SettlementLineItemForm(forms.ModelForm):
    class Meta:
        model = SettlementLineItem
        fields = (
            "description",
            "category",
            "count",
            "unit_price_gbp",
            "order",
        )
        widgets = {
            "description": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "e.g. 40 advance online",
                }
            ),
            "category": forms.Select(
                attrs={"class": "form-select form-select-sm"}
            ),
            "count": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "min": "1",
                    "style": "width:5em",
                }
            ),
            "unit_price_gbp": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "step": "0.01",
                    "min": "0",
                    "style": "width:7em",
                }
            ),
            "order": forms.HiddenInput(),
        }


# Free-text, unbounded line items -- no max_num. extra=1 gives one blank
# row to start, "add another" (JS, cloning the empty form) extends it.
SettlementLineItemFormSet = inlineformset_factory(
    ShowingSettlement,
    SettlementLineItem,
    form=SettlementLineItemForm,
    extra=1,
    can_delete=True,
)


class DistributorPaymentForm(forms.ModelForm):
    """Event-level distributor-payment outcome -- separate from the
    per-showing actuals above, since one deal usually covers every showing
    under the event (scoping doc Answers Q3)."""

    class Meta:
        model = Event
        fields = (
            "distributor_invoiced_date",
            "distributor_paid_date",
            "distributor_paid_amount_gbp",
        )
        widgets = {
            "distributor_invoiced_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "distributor_paid_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "distributor_paid_amount_gbp": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
        }


class PerformerRegistrationForm(forms.ModelForm):
    """Event-level PRS/PPL record -- entirely optional (task 9.171); see
    PerformerRegistration's docstring for why this is never required."""

    class Meta:
        model = PerformerRegistration
        fields = ("filled_in_by", "vat_on_tickets", "notes")
        widgets = {
            "filled_in_by": forms.TextInput(attrs={"class": "form-control"}),
            "vat_on_tickets": forms.NullBooleanSelect(
                attrs={"class": "form-select"}
            ),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 2}
            ),
        }


class PRSPerformerEntryForm(forms.ModelForm):
    class Meta:
        model = PRSPerformerEntry
        fields = ("name", "registered", "is_volunteer_or_amateur", "order")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "Performer/artist name",
                }
            ),
            "registered": forms.Select(
                attrs={"class": "form-select form-select-sm"}
            ),
            "is_volunteer_or_amateur": forms.NullBooleanSelect(
                attrs={"class": "form-select form-select-sm"}
            ),
            "order": forms.HiddenInput(),
        }


# Free-text, unbounded performer rows, same shape as SettlementLineItemFormSet
# -- no max_num, extra=1 gives one blank row to start.
PRSPerformerEntryFormSet = inlineformset_factory(
    PerformerRegistration,
    PRSPerformerEntry,
    form=PRSPerformerEntryForm,
    extra=1,
    can_delete=True,
)
