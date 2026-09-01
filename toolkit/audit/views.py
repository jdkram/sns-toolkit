# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Panopticon-only audit pages: sent emails (9.156) and deletions (9.159).

Recipient addresses are PII, so both pages are superuser-gated.
"""
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from toolkit.toolkit_auth.decorators import panopticon_required

from .models import DeletionLog, SentEmailLog

PAGE_SIZE = 50

# Plain-language names for the backends TOOLKIT_WRAPPED_EMAIL_BACKEND can
# point at, shown on the email log page so a non-developer can tell whether
# mail is actually leaving the building.
BACKEND_DESCRIPTIONS = {
    "django.core.mail.backends.console.EmailBackend": (
        "Console backend: nothing is actually sent. Messages are only "
        "written to the server's log output. Safe for testing."
    ),
    "django.core.mail.backends.smtp.EmailBackend": (
        "SMTP backend: messages are handed to a real mail server "
        "(configured via the EMAIL_HOST settings) for delivery."
    ),
    "django.core.mail.backends.filebased.EmailBackend": (
        "File-based backend: messages are written to disk instead of "
        "being sent. Used for local development."
    ),
    "django.core.mail.backends.locmem.EmailBackend": (
        "In-memory backend: messages are kept in memory only, for "
        "automated tests. Nothing is sent."
    ),
}


@panopticon_required
def email_log(request):
    logs = SentEmailLog.objects.select_related("triggered_by")

    status = request.GET.get("status", "")
    if status == "success":
        logs = logs.filter(success=True)
    elif status == "failed":
        logs = logs.filter(success=False)

    search = request.GET.get("search", "").strip()
    if search:
        logs = logs.filter(
            Q(recipients__icontains=search)
            | Q(subject__icontains=search)
            | Q(trigger_source__icontains=search)
            | Q(triggered_by__username__icontains=search)
        )

    configured_backend = getattr(
        settings,
        "TOOLKIT_WRAPPED_EMAIL_BACKEND",
        "django.core.mail.backends.console.EmailBackend",
    )

    page = Paginator(logs, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "audit/email_log.html", {
        "page": page,
        "status": status,
        "search": search,
        "failure_count": SentEmailLog.objects.filter(success=False).count(),
        "configured_backend": configured_backend,
        "configured_backend_description": BACKEND_DESCRIPTIONS.get(
            configured_backend, f"Unrecognised backend ({configured_backend})."
        ),
    })


@panopticon_required
def deletion_log(request):
    logs = DeletionLog.objects.select_related("deleted_by")

    search = request.GET.get("search", "").strip()
    if search:
        logs = logs.filter(
            Q(description__icontains=search)
            | Q(model__icontains=search)
            | Q(deleted_by__username__icontains=search)
        )

    page = Paginator(logs, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "audit/deletion_log.html", {
        "page": page,
        "search": search,
    })
