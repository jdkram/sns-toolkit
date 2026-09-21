# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Views for film readiness tracking (task 9.174).

The unit is one film, linked to the showings it plays at (see
models/film_prep.py): a run of one film, a different film per date, or a
double or triple bill.

- ``film_prep_add`` / ``film_prep_edit`` / ``film_prep_delete`` -- the full
  page for one film: which showings it plays at, checklist answers, handover
  note and copies. Reached from the Event Hub panel. Programmer+.
- ``film_readiness_overview`` -- read-only list of every upcoming film, all
  states, plus dates with no film recorded and drives to send back. Any
  logged-in volunteer may view it, so people considering programming can see
  the process before they start.
- ``film_milestone_claim`` / ``film_milestone_complete`` -- small POST
  endpoints so "I'll test this" and "Mark tested" are one click from the
  Hub or a dashboard card. ``film_milestone_unclaim`` and
  ``film_milestone_undo`` are their reverses, each audit-logged. Open to Programmer+ and to projectionist
  volunteers. Both redirect to ``next`` when it is a local URL.
"""

import datetime
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

import toolkit.diary.forms as diary_forms
from toolkit.audit.models import EventAuditLog, log_event_action
from toolkit.diary.models import (
    Event,
    FilmMilestone,
    FilmPrep,
    get_site_config,
)
from toolkit.diary.models.film_prep import (
    FORMAT_CHOICES,
    FORMAT_MILESTONES,
    LOOKAHEAD_DAYS,
    MILESTONE_LABELS,
    RESULT_OK,
    RESULT_PROBLEM,
    RETURN_CONFIRMED,
    RETURN_KEEP_DAYS,
    RETURNED,
    URGENT_DAYS,
    film_row,
    returns_outstanding,
    showings_without_film,
    upcoming_film_preps,
    user_can_update_film_prep,
)
from toolkit.toolkit_auth.decorators import write_required


def _film_prep_enabled_or_404(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not get_site_config().film_prep_enabled:
            raise Http404
        return func(request, *args, **kwargs)

    return wrapper


def film_update_required(func):
    """Programmer+, or a projectionist volunteer: the two-click endpoints
    (claim, complete) are the one part of film prep a rota-only volunteer
    may use. Same login redirect as write_required for everyone else."""

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        from django.contrib.auth.views import redirect_to_login

        if not user_can_update_film_prep(request.user):
            return redirect_to_login(request.get_full_path())
        request.view_access_level = "Programmer+ or projectionist"
        return func(request, *args, **kwargs)

    return wrapper


def _hub_url(event):
    return reverse("edit-event-details-view", kwargs={"event_id": event.pk})


def _redirect_back(request, event):
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}
    ):
        # A rota-only projectionist cannot open the Event Hub (Programmer+),
        # so send them back to the dashboard they came from.
        if request.user.has_perm("toolkit.write"):
            target = _hub_url(event) + "#film-readiness"
        else:
            target = reverse("default-edit")
    return HttpResponseRedirect(target)


def _default_showings(event, request):
    """Which showings to tick for a new film: the one named in ``?showing=``,
    else every showing that has no film yet, else (a brand-new film event)
    all of them. That makes "one film for the whole run" a single click and
    "a different film each date" a per-date button."""
    wanted = request.GET.get("showing", "")
    showings = event.showings.all()
    if wanted.isdigit():
        return showings.filter(pk=int(wanted))
    without = showings.filter(film_preps__isnull=True)
    return without if without.exists() else showings


def _film_prep_form_view(request, event, prep):
    """Shared by add and edit: the film form plus its copies formset."""
    is_new = prep.pk is None
    if request.method == "POST":
        form = diary_forms.FilmPrepForm(
            request.POST, instance=prep, event=event
        )
        formset = diary_forms.FilmCopyFormSet(request.POST, instance=prep)
        if form.is_valid() and formset.is_valid():
            prep = form.save(commit=False)
            prep.updated_by = request.user
            prep.save()
            form.save_m2m()
            formset.instance = prep
            formset.save()
            messages.success(request, f"Saved {prep.display_title}.")
            return HttpResponseRedirect(_hub_url(event) + "#film-readiness")
    else:
        form = diary_forms.FilmPrepForm(
            instance=prep,
            event=event,
            initial=(
                {"showings": _default_showings(event, request)}
                if is_new
                else None
            ),
        )
        formset = diary_forms.FilmCopyFormSet(instance=prep)

    return render(
        request,
        "edit_film_prep.html",
        {
            "event": event,
            "prep": None if is_new else prep,
            "form": form,
            "formset": formset,
            "guide_url": get_site_config().film_sourcing_guide_url,
        },
    )


@write_required
@_film_prep_enabled_or_404
@require_http_methods(["GET", "POST"])
def film_prep_add(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    return _film_prep_form_view(request, event, FilmPrep(event=event))


@write_required
@_film_prep_enabled_or_404
@require_http_methods(["GET", "POST"])
def film_prep_edit(request, prep_id):
    prep = get_object_or_404(
        FilmPrep.objects.select_related("event"), pk=prep_id
    )
    return _film_prep_form_view(request, prep.event, prep)


@write_required
@_film_prep_enabled_or_404
@require_POST
def film_prep_delete(request, prep_id):
    """Remove a film record, with its copies and progress. Needs the
    confirmation box ticked, since nothing here can be undone."""
    prep = get_object_or_404(
        FilmPrep.objects.select_related("event"), pk=prep_id
    )
    if not request.POST.get("confirm"):
        messages.error(request, "Tick the box to confirm the removal.")
        return HttpResponseRedirect(
            reverse("edit-film-prep", kwargs={"prep_id": prep.pk})
        )
    title = prep.display_title
    event = prep.event
    prep.delete()
    messages.success(request, f"Removed {title} from film readiness.")
    return HttpResponseRedirect(_hub_url(event) + "#film-readiness")


@film_update_required
@_film_prep_enabled_or_404
@require_POST
def film_milestone_claim(request, milestone_id):
    milestone = get_object_or_404(
        FilmMilestone.objects.select_related("copy__film_prep__event"),
        pk=milestone_id,
    )
    prep = milestone.copy.film_prep
    planned_for = None
    raw = request.POST.get("planned_for", "").strip()
    if raw:
        try:
            planned_for = datetime.date.fromisoformat(raw)
        except ValueError:
            messages.error(request, "That date was not understood.")
            return _redirect_back(request, prep.event)
    milestone.claim(request.user, planned_for=planned_for)
    log_event_action(
        prep.event,
        EventAuditLog.ACTION_FILM_CLAIMED,
        actor=request.user,
        detail=f"{prep.display_title}, {milestone.copy.label}: {milestone.label}",
    )
    messages.success(request, f"You have claimed: {milestone.label}.")
    return _redirect_back(request, prep.event)


@film_update_required
@_film_prep_enabled_or_404
@require_POST
def film_milestone_complete(request, milestone_id):
    milestone = get_object_or_404(
        FilmMilestone.objects.select_related("copy__film_prep__event"),
        pk=milestone_id,
    )
    prep = milestone.copy.film_prep
    result = request.POST.get("result", "")
    if result not in ("", RESULT_OK, RESULT_PROBLEM):
        result = ""
    notes = request.POST.get("notes", "").strip()[:256]
    milestone.complete(request.user, result=result, notes=notes)
    detail = f"{prep.display_title}, {milestone.copy.label}: {milestone.label}"
    if result == RESULT_PROBLEM:
        detail += " (problem)"
    log_event_action(
        prep.event,
        EventAuditLog.ACTION_FILM_STEP_DONE,
        actor=request.user,
        detail=detail,
    )
    messages.success(request, f"Recorded: {milestone.label}.")
    return _redirect_back(request, prep.event)


@film_update_required
@_film_prep_enabled_or_404
@require_POST
def film_milestone_unclaim(request, milestone_id):
    """Back out of "I'll do this". Anyone who can update film prep may hand a
    step back, not just the person who claimed it: people fall ill and
    someone else has to be able to clear the claim. The audit entry records
    who had claimed it and for when, so a claim dropped the day before a
    screening is visible afterwards."""
    milestone = get_object_or_404(
        FilmMilestone.objects.select_related("copy__film_prep__event"),
        pk=milestone_id,
    )
    prep = milestone.copy.film_prep
    if not milestone.claimed_by_id:
        messages.info(request, f"Nobody had claimed: {milestone.label}.")
        return _redirect_back(request, prep.event)
    detail = (
        f"{prep.display_title}, {milestone.copy.label}: {milestone.label}"
        f" (had been claimed by {milestone.claimed_by_name}"
    )
    if milestone.planned_for:
        detail += f" for {milestone.planned_for:%a %-d %b}"
    detail += ")"
    milestone.unclaim()
    log_event_action(
        prep.event,
        EventAuditLog.ACTION_FILM_UNCLAIMED,
        actor=request.user,
        detail=detail,
    )
    messages.success(request, f"Handed back: {milestone.label}.")
    return _redirect_back(request, prep.event)


@film_update_required
@_film_prep_enabled_or_404
@require_POST
def film_milestone_undo(request, milestone_id):
    """Mark a completed step as not done after all. What was recorded (who,
    when, result, notes) goes into the audit entry before it is cleared."""
    milestone = get_object_or_404(
        FilmMilestone.objects.select_related("copy__film_prep__event"),
        pk=milestone_id,
    )
    prep = milestone.copy.film_prep
    if not milestone.done_at:
        messages.info(request, f"Not marked done: {milestone.label}.")
        return _redirect_back(request, prep.event)
    if milestone.key == RETURNED and milestone.copy.milestones.filter(
        key=RETURN_CONFIRMED, done_at__isnull=False
    ):
        messages.error(request, "Undo the distributor's confirmation first.")
        return _redirect_back(request, prep.event)
    detail = (
        f"{prep.display_title}, {milestone.copy.label}: {milestone.label}"
        f" (had been done by {milestone.done_by_name or 'unknown'}"
        f" on {milestone.done_at:%-d %b}"
    )
    if milestone.result == RESULT_PROBLEM:
        detail += ", problem"
    if milestone.notes:
        detail += f", note: {milestone.notes}"
    detail += ")"
    milestone.undo()
    log_event_action(
        prep.event,
        EventAuditLog.ACTION_FILM_STEP_UNDONE,
        actor=request.user,
        detail=detail,
    )
    messages.success(request, f"Marked not done: {milestone.label}.")
    return _redirect_back(request, prep.event)


@login_required
@_film_prep_enabled_or_404
@require_http_methods(["GET"])
def film_readiness_overview(request):
    """Every upcoming film, ready or not, soonest first."""
    now = timezone.now()
    rows = sorted(
        (film_row(p, now) for p in upcoming_film_preps(now)),
        key=lambda r: (r["start"], r["prep"].bill_position),
    )
    counts = {}
    for row in rows:
        counts[row["readiness"]] = counts.get(row["readiness"], 0) + 1
    process = [
        (label, [MILESTONE_LABELS[k] for k in FORMAT_MILESTONES[fmt]])
        for fmt, label in FORMAT_CHOICES
    ]
    return render(
        request,
        "film_readiness_overview.html",
        {
            "rows": rows,
            "unfilled": list(showings_without_film(now, LOOKAHEAD_DAYS)),
            "returns": returns_outstanding(now, include_closed=True),
            "process": process,
            "counts": counts,
            "lookahead_days": LOOKAHEAD_DAYS,
            "urgent_days": URGENT_DAYS,
            "return_keep_days": RETURN_KEEP_DAYS,
            "can_update": user_can_update_film_prep(request.user),
            "can_open_hub": request.user.has_perm("toolkit.write"),
            "guide_url": get_site_config().film_sourcing_guide_url,
        },
    )
