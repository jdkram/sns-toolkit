# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import logging

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from toolkit.util.ics import build_vevent

from ..emails import (
    send_access_needs_ack,
    send_new_signup_notification,
    send_organiser_notification,
    send_session_full_notification,
    send_signup_confirmation,
)
from ..forms import AccessNeedsForm, SignupForm
from ..models import (
    InductionRequest,
    InductionSession,
    InductionSignup,
    get_inductions_settings,
)

logger = logging.getLogger(__name__)


def _check_enabled():
    if not get_inductions_settings().inductions_enabled:
        raise Http404


def signup(request, slug):
    _check_enabled()
    session = get_object_or_404(
        InductionSession, slug=slug, status=InductionSession.STATUS_OPEN
    )

    if session.is_full:
        return render(
            request, "inductions/signup_full.html", {"session": session}
        )

    if request.method == "POST":
        form = SignupForm(request.POST, session=session)
        if form.is_valid():
            new_signup = InductionSignup.objects.create(
                session=session,
                name=form.get_name(),
                email=form.cleaned_data["email"],
                phone=form.cleaned_data.get("phone", ""),
                address=form.cleaned_data.get("address", ""),
                postcode=form.cleaned_data.get("postcode", ""),
                custom_responses=form.get_custom_responses(),
            )
            try:
                send_signup_confirmation(request, new_signup)
            except Exception:
                logger.exception("Failed to send signup confirmation email")
            try:
                send_new_signup_notification(session, new_signup)
            except Exception:
                logger.exception(
                    "Failed to send new-signup organiser notification"
                )
            if session.is_full:
                try:
                    send_session_full_notification(session)
                except Exception:
                    logger.exception(
                        "Failed to send session-full organiser notification"
                    )
            return redirect("inductions:signup_thanks", slug=slug)
    else:
        form = SignupForm(session=session)

    return render(
        request,
        "inductions/signup.html",
        {
            "form": form,
            "session": session,
        },
    )


def signup_thanks(request, slug):
    _check_enabled()
    session = get_object_or_404(InductionSession, slug=slug)
    return render(
        request, "inductions/signup_thanks.html", {"session": session}
    )


def calendar_ics(request, slug):
    _check_enabled()
    session = get_object_or_404(InductionSession, slug=slug)
    venue = settings.VENUE.get("longname", settings.VENUE.get("name", ""))
    # Assume 2-hour induction if no end time.
    end_dt = session.date + timezone.timedelta(hours=2)

    content = build_vevent(
        uid=f"induction-{session.slug}@{request.get_host()}",
        dtstart=session.date,
        dtend=end_dt,
        summary=f"{session.title} — {venue} Induction",
        location=session.location or venue,
        prodid="-//Cube Toolkit//Inductions//EN",
    )
    return HttpResponse(content, content_type="text/calendar; charset=utf-8")


def access_needs_signup(request):
    _check_enabled()
    cfg = get_inductions_settings()
    if not cfg.access_needs_enabled:
        raise Http404
    if request.method == "POST":
        form = AccessNeedsForm(request.POST)
        if form.is_valid():
            req = InductionRequest.objects.create(
                name=form.cleaned_data["name"],
                email=form.cleaned_data["email"],
                access_needs=form.cleaned_data["access_needs"],
                rough_availability=form.cleaned_data.get(
                    "rough_availability", ""
                ),
            )
            try:
                send_access_needs_ack(request, req)
            except Exception:
                logger.exception("Failed to send access needs ack email")
            try:
                send_organiser_notification(req)
            except Exception:
                logger.exception("Failed to send organiser notification email")
            return redirect("inductions:access_needs_thanks")
    else:
        form = AccessNeedsForm()

    return render(
        request,
        "inductions/access_needs_signup.html",
        {
            "form": form,
            "intro_text": cfg.access_needs_intro_text,
        },
    )


def access_needs_thanks(request):
    _check_enabled()
    cfg = get_inductions_settings()
    if not cfg.access_needs_enabled:
        raise Http404
    return render(
        request,
        "inductions/access_needs_thanks.html",
        {
            "organiser_email": cfg.organiser_notification_email,
        },
    )


def session_list_public(request):
    """Public listing of all currently-open induction sessions."""
    _check_enabled()
    sessions = (
        InductionSession.objects.filter(status=InductionSession.STATUS_OPEN)
        .exclude(session_type=InductionSession.TYPE_ONE_TO_ONE)
        .order_by("date")
    )
    return render(
        request,
        "inductions/session_list_public.html",
        {
            "sessions": sessions,
            "cfg": get_inductions_settings(),
        },
    )
