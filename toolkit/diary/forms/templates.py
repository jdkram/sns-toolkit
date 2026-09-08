from django import forms
from django.forms import inlineformset_factory

from toolkit.diary.form_widgets import TagPillSelect

import toolkit.diary.models


class EventTemplateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This form is rendered by hand (not via crispy) so it doesn't pick
        # up Bootstrap classes automatically - add them here, matching the
        # pattern in SiteConfigurationForm.
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, TagPillSelect):
                pass  # manages its own markup
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                existing = widget.attrs.get("class", "")
                if "form-select" not in existing:
                    widget.attrs["class"] = (existing + " form-select").strip()
            else:
                existing = widget.attrs.get("class", "")
                if "form-control" not in existing:
                    widget.attrs["class"] = (
                        existing + " form-control"
                    ).strip()

    class Meta:
        model = toolkit.diary.models.EventTemplate
        # roles is handled by a separate inline formset (EventTemplateRoleFormSet)
        fields = (
            "name",
            "tags",
            "pricing",
            "film_information",
            "copy_summary",
            "copy",
            "cost_type",
            "cost_distributor",
            "cost_flat_fee_gbp",
            "cost_fee_includes_vat",
            "cost_percentage_split",
            "cost_minimum_guarantee_gbp",
            "cost_total_gbp",
            "terms",
            "rota_notes",
            "private",
            "outside_hire",
        )
        widgets = {
            "tags": TagPillSelect(),
            "copy": forms.Textarea(attrs={"wrap": "soft", "rows": 10}),
            "copy_summary": forms.Textarea(attrs={"wrap": "soft", "rows": 4}),
            "terms": forms.Textarea(attrs={"wrap": "soft", "rows": 6}),
            "rota_notes": forms.Textarea(attrs={"wrap": "soft", "rows": 4}),
            "pricing": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. '\u00a30 Full / \u00a30 Concession'"
                    ),
                }
            ),
            "film_information": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Dir: [director], 1990, USA, 120 mins, Cert: 15",
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
        }


class EventTemplateRoleForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.EventTemplateRole
        fields = ("role", "count")
        widgets = {
            "role": forms.Select(attrs={"class": "form-select"}),
            "count": forms.NumberInput(
                attrs={
                    "min": 1,
                    "max": 20,
                    "style": "width:5em",
                    "class": "form-control",
                }
            ),
        }


# Inline formset: one EventTemplateRole row per role slot on the template.
# extra=1 always appends one blank row for adding a new role.
EventTemplateRoleFormSet = inlineformset_factory(
    toolkit.diary.models.EventTemplate,
    toolkit.diary.models.EventTemplateRole,
    form=EventTemplateRoleForm,
    extra=1,
    can_delete=True,
)


class EventTemplateRoomForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.EventTemplateRoom
        fields = ("room", "start_delta_minutes", "end_delta_minutes")
        widgets = {
            "room": forms.Select(attrs={"class": "form-select"}),
            "start_delta_minutes": forms.NumberInput(
                attrs={"style": "width:6em", "class": "form-control"}
            ),
            "end_delta_minutes": forms.NumberInput(
                attrs={"style": "width:6em", "class": "form-control"}
            ),
        }


EventTemplateRoomFormSet = inlineformset_factory(
    toolkit.diary.models.EventTemplate,
    toolkit.diary.models.EventTemplateRoom,
    form=EventTemplateRoomForm,
    extra=1,
    can_delete=True,
)


class EventTemplateLinkForm(forms.ModelForm):
    """Single resource link attached to an event template."""

    class Meta:
        model = toolkit.diary.models.EventTemplateLink
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


EventTemplateLinkFormSet = inlineformset_factory(
    toolkit.diary.models.EventTemplate,
    toolkit.diary.models.EventTemplateLink,
    form=EventTemplateLinkForm,
    extra=3,
    max_num=3,
    validate_max=True,
    can_delete=True,
)
