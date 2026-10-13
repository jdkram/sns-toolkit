# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.urls import path

from . import views

app_name = "hires"

urlpatterns = [
    path("quote/", views.quote, name="quote"),
    path("enquire/", views.enquire, name="enquire"),
    path("privacy/", views.privacy, name="privacy"),
    path("enquire/thanks/", views.thanks, name="thanks"),
    path("details/<str:token>/", views.details, name="details"),
    path("agree/<str:token>/", views.agree, name="agree"),
    path("manage/", views.queue, name="queue"),
    path("manage/settings/", views.settings_edit, name="settings"),
    path("manage/meetings/", views.meetings, name="meetings"),
    path("manage/types/", views.types, name="types"),
    path("manage/techs/", views.techs, name="techs"),
    path("manage/emails/", views.email_templates, name="emails"),
    path("manage/<int:pk>/", views.detail, name="detail"),
    path("manage/<int:pk>/act/", views.act, name="act"),
]
