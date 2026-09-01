# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^emails/$", views.email_log, name="audit-email-log"),
    re_path(r"^deletions/$", views.deletion_log, name="audit-deletion-log"),
]
