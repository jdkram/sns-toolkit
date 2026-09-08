# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from toolkit.toolkit_auth.decorators import panopticon_required

from ..forms import InductionSessionForm
from ..models import InductionSession, InductionSignup


@panopticon_required
def manage_session_list(request):
    sessions = InductionSession.objects.prefetch_related("signups").order_by(
        "-date"
    )
    return render(
        request,
        "inductions/manage/session_list.html",
        {
            "sessions": sessions,
        },
    )


@panopticon_required
def manage_session_new(request):
    if request.method == "POST":
        form = InductionSessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.created_by = request.user
            session.save()
            messages.success(request, f"Session '{session.title}' created.")
            return redirect(
                "inductions:manage_session_detail", slug=session.slug
            )
    else:
        form = InductionSessionForm()

    return render(
        request,
        "inductions/manage/session_form.html",
        {
            "form": form,
            "title": "New induction session",
            "custom_questions_json": "[]",
        },
    )


@panopticon_required
def manage_session_edit(request, slug):
    session = get_object_or_404(InductionSession, slug=slug)
    import json

    if request.method == "POST":
        form = InductionSessionForm(request.POST, instance=session)
        raw_questions = request.POST.get("custom_questions_raw", "[]")
        try:
            questions = json.loads(raw_questions)
        except (ValueError, TypeError):
            questions = session.custom_questions

        if form.is_valid():
            s = form.save(commit=False)
            s.custom_questions = questions
            s.save()
            messages.success(request, "Session updated.")
            return redirect("inductions:manage_session_detail", slug=s.slug)
    else:
        form = InductionSessionForm(instance=session)

    return render(
        request,
        "inductions/manage/session_form.html",
        {
            "form": form,
            "session": session,
            "title": f"Edit — {session.title}",
            "custom_questions_json": json.dumps(session.custom_questions),
        },
    )


@panopticon_required
def manage_session_detail(request, slug):
    session = get_object_or_404(InductionSession, slug=slug)
    signups = list(
        session.signups.select_related(
            "volunteer__member", "volunteer__user", "checked_in_by"
        )
    )
    signup_url = request.build_absolute_uri(
        reverse("inductions:signup", kwargs={"slug": slug})
    )
    accounts_created = sum(1 for s in signups if s.volunteer_id)

    cap = session.effective_capacity()
    over_cap_count = max(0, len(signups) - cap) if cap is not None else 0
    if over_cap_count:
        over_cap_ids = {s.pk for s in signups[-over_cap_count:]}
        for s in signups:
            s.is_over_cap = s.pk in over_cap_ids
    else:
        for s in signups:
            s.is_over_cap = False

    return render(
        request,
        "inductions/manage/session_detail.html",
        {
            "session": session,
            "signups": signups,
            "signup_url": signup_url,
            "accounts_created": accounts_created,
            "over_cap_count": over_cap_count,
        },
    )


@require_POST
@panopticon_required
def manage_session_set_cap(request, slug):
    """AJAX: set this session's max_signups directly, for the +/- cap control on the detail page."""
    session = get_object_or_404(InductionSession, slug=slug)
    raw = request.POST.get("max_signups", "").strip()
    if raw == "":
        session.max_signups = None
    else:
        try:
            value = int(raw)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid value."})
        if value < 0:
            return JsonResponse(
                {"ok": False, "error": "Cap cannot be negative."}
            )
        session.max_signups = value
    session.save()
    return JsonResponse({"ok": True, "max_signups": session.max_signups})


@require_POST
@panopticon_required
def manage_session_close(request, slug):
    session = get_object_or_404(InductionSession, slug=slug)
    session.status = InductionSession.STATUS_CLOSED
    session.save()
    messages.success(
        request, f"'{session.title}' is now closed to new sign-ups."
    )
    return redirect("inductions:manage_session_detail", slug=slug)


@require_POST
@panopticon_required
def manage_session_purge(request, slug):
    session = get_object_or_404(InductionSession, slug=slug)
    count = _purge_session(session)
    messages.success(request, f"Purged {count} pending/no-show record(s).")
    return redirect("inductions:manage_session_detail", slug=slug)


def _purge_session(session: InductionSession) -> int:
    """Null PII on pending/no-show signups. Returns count of records purged."""
    to_purge = session.signups.filter(
        status__in=[
            InductionSignup.STATUS_PENDING,
            InductionSignup.STATUS_NO_SHOW,
        ]
    )
    count = to_purge.count()
    to_purge.update(name="", email="", custom_responses={})
    session.status = InductionSession.STATUS_PURGED
    session.save()
    return count
