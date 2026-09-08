from django import forms

from toolkit.diary.form_widgets import HtmlTextarea

import toolkit.diary.models


class DiaryIdeaForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.DiaryIdea
        fields = ("ideas",)


class MailoutForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.html_mailout_enabled = kwargs.pop("html_mailout_enabled")
        super().__init__(*args, **kwargs)
        if not self.html_mailout_enabled:
            del self.fields["send_html"]
            del self.fields["body_html"]

    send_html = forms.BooleanField(
        label="Send HTML mailout", initial=True, required=False
    )

    subject = forms.CharField(max_length=128, required=True, label_suffix="")

    body_text = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"wrap": "soft", "cols": 80}),
    )

    body_html = forms.CharField(
        required=False,
        widget=HtmlTextarea(
            enable_tables=True, enable_iframes=False, height="120ex"
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        send_html = cleaned_data.get("send_html")
        body_html = cleaned_data.get("body_html")
        if send_html and not body_html:
            raise forms.ValidationError(
                "HTML body is empty. "
                "If you do not want to send an HTML email unset the 'Send HTML Mailout' option"
            )


class SearchForm(forms.Form):
    search_term = forms.CharField(
        label="Search for", required=False, widget=forms.widgets.SearchInput()
    )
    start_date = forms.DateTimeField(label="Search from", required=False)
    end_date = forms.DateTimeField(label="Search to", required=False)
    search_in_descriptions = forms.BooleanField(
        label="Also search event descriptions", required=False
    )

    def clean(self):
        cleaned_data = super().clean()

        # Check that either a search term or a search start or end date is
        # supplied:
        if len(cleaned_data.get("search_term", "").strip()) == 0 and not (
            cleaned_data.get("start_date") or cleaned_data.get("end_date")
        ):
            raise forms.ValidationError(
                "Must give either a search term or a " "date range"
            )

        return cleaned_data
