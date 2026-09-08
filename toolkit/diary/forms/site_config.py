from django import forms

from toolkit.diary.form_widgets import (
    AgeRatingChoicesWidget,
    HtmlTextarea,
)
from toolkit.diary.models import EventTag, SiteConfiguration


class SiteConfigurationForm(forms.ModelForm):
    stats_training_tag_slugs = forms.MultipleChoiceField(
        choices=[],  # populated in __init__ from EventTag queryset
        required=False,
        label="Exclude these event tags from shift counts",
        help_text=(
            "Events tagged with any of these are not counted as confirmed shifts on the "
            "volunteer stats page. Use this to keep induction sessions and training events "
            "separate from the programming eligibility total."
        ),
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "list-unstyled ps-0 mt-1"}
        ),
    )

    class Meta:
        model = SiteConfiguration
        # Auto-derive the form field set from the model `_meta` so adding a
        # SiteConfiguration field never requires also listing it here. The
        # grouping/ordering for the Panopticon edit page lives in
        # `SITE_CONFIG_FIELD_GROUPS` (see site_config.py), not in this Meta.
        exclude = ("id",)
        widgets = {
            "programme_accent_colour": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "form-control form-control-sm",
                    "style": "width:60px;height:32px;padding:2px;",
                }
            ),
            "breakeven_guidance_note": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "films_start_on_time_banner_text": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "rota_clear_email_prompt_text": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "images_start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "banner_text": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "collectives_intro": HtmlTextarea(),
            "donations_intro": HtmlTextarea(),
            "ticket_link_guidance_html": HtmlTextarea(),
            "bulletin_guidance": forms.Textarea(
                attrs={"rows": 6, "class": "form-control"}
            ),
            "eventlink_extra_allowed_domains": forms.Textarea(
                attrs={"rows": 4, "class": "form-control font-monospace"}
            ),
            "age_rating_choices": AgeRatingChoicesWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tag_choices = [
            (tag.slug, tag.name) for tag in EventTag.objects.order_by("name")
        ]
        self.fields["stats_training_tag_slugs"].choices = tag_choices
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(
                widget, (AgeRatingChoicesWidget, forms.CheckboxSelectMultiple)
            ):
                pass  # these widgets manage their own markup; don't inject form-control
            else:
                existing = widget.attrs.get("class", "")
                if "form-control" not in existing:
                    widget.attrs["class"] = (
                        existing + " form-control"
                    ).strip()

    def clean_omdb_api_key(self):
        key = self.cleaned_data.get("omdb_api_key", "").strip()
        if not key:
            return key
        if self.instance.pk and key == self.instance.omdb_api_key:
            # Unchanged — don't re-test OMDb on every unrelated settings save.
            return key

        import urllib.error

        from toolkit.diary.omdb import (
            OmdbAuthError,
            OmdbRateLimitError,
            verify_api_key,
        )

        try:
            verify_api_key(key)
        except OmdbAuthError:
            raise forms.ValidationError(
                "OMDb rejected this API key. Check it's correct and active at "
                "https://www.omdbapi.com/apikey.aspx, then try again."
            )
        except OmdbRateLimitError:
            raise forms.ValidationError(
                "Could not verify this key — OMDb says its daily request limit "
                "has already been reached (shared across everyone using this "
                "key). This doesn't necessarily mean the key itself is wrong. "
                "The limit resets at midnight UTC; try saving again after that, "
                "or leave the existing key in place for now."
            )
        except (urllib.error.URLError, ValueError):
            raise forms.ValidationError(
                "Could not reach OMDb to verify this key. Check the server's "
                "network connection and try again."
            )
        return key
