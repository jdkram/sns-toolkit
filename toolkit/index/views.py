import datetime
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db import connection, OperationalError
from django.db.models import (
    Count,
    ExpressionWrapper,
    F,
    IntegerField,
    Min,
    Q,
)
from django.http import (
    HttpResponse,
    HttpResponseServerError,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from toolkit.diary.models import (
    Event,
    RotaEntry,
    Showing,
    VolunteerEventMark,
    get_site_config,
)
from toolkit.diary.models.film_prep import (
    LOOKAHEAD_DAYS,
    READY,
    film_row,
    returns_outstanding,
    showings_without_film,
    upcoming_film_preps,
    user_can_update_film_prep,
)
from toolkit.index.models import IndexLink
from toolkit.members.models import PanopticonGrant, Volunteer
from toolkit.toolkit_auth.decorators import panopticon_required

# Curated catalogue of pinnable dashboard links.
# perm: Django permission codename required, or None for any logged-in user.
# toolkit.read = volunteer-level; toolkit.write = programmer+.
_LINK_CATALOGUE = [
    {
        "key": "diary",
        "label": "Diary",
        "url_name": "default-edit",
        "perm": "toolkit.write",
    },
    {
        "key": "rota",
        "label": "Rota",
        "url_name": "rota-edit",
        "perm": "toolkit.read",
    },
    {
        "key": "calendar",
        "label": "Calendar",
        "url_name": "diary-edit-calendar",
        "perm": "toolkit.write",
    },
    {
        "key": "bulletins",
        "label": "Bulletins",
        "url_name": "labs-bulletins",
        "perm": "toolkit.read",
    },
    {
        "key": "collectives",
        "label": "Collectives",
        "url_name": "labs-collectives",
        "perm": "toolkit.read",
    },
    {
        "key": "directory",
        "label": "Volunteer directory",
        "url_name": "view-volunteer-list",
        "perm": "toolkit.read",
    },
    {
        "key": "jobs",
        "label": "Jobs board",
        "url_name": "labs-jobs",
        "perm": "toolkit.read",
    },
    {
        "key": "exchange",
        "label": "Community exchange",
        "url_name": "labs-exchange",
        "perm": "toolkit.read",
    },
    {
        "key": "floorplan",
        "label": "Building map",
        "url_name": "labs-floorplan",
        "perm": "toolkit.read",
    },
    {
        "key": "shopping",
        "label": "Shopping list",
        "url_name": "labs-shopping",
        "perm": "toolkit.read",
    },
    {
        "key": "lost-found",
        "label": "Lost & found",
        "url_name": "labs-found-items",
        "perm": "toolkit.read",
    },
    {
        "key": "stats",
        "label": "Your history",
        "url_name": "volunteer-stats",
        "perm": "toolkit.read",
    },
    {
        "key": "tags",
        "label": "Tags",
        "url_name": "edit_event_tags",
        "perm": "toolkit.write",
    },
    {
        "key": "templates",
        "label": "Event templates",
        "url_name": "edit_event_templates",
        "perm": "toolkit.write",
    },
    {
        "key": "rooms",
        "label": "Rooms",
        "url_name": "edit_rooms",
        "perm": "toolkit.write",
    },
    {
        "key": "roles",
        "label": "Roles",
        "url_name": "edit_roles",
        "perm": "toolkit.write",
    },
    {
        "key": "site-settings",
        "label": "Site settings",
        "url_name": "edit-site-configuration",
        "perm": "toolkit.write",
    },
    {
        "key": "access-levels",
        "label": "Access levels",
        "url_name": "toolkit-access",
        "perm": "toolkit.read",
    },
    {
        "key": "qual-report",
        "label": "Qualification report",
        "url_name": "view-qualification-report",
        "perm": "toolkit.read",
    },
]

_MAX_FAVOURITE_LINKS = 8


def _available_links(user):
    """Return catalogue entries accessible to `user`, with `url` resolved."""
    result = []
    for item in _LINK_CATALOGUE:
        if item["perm"] and not user.has_perm(item["perm"]):
            continue
        result.append({**item, "url": reverse(item["url_name"])})
    return result


def _outstanding_settlements_for(volunteer, now):
    """Rows for the dashboard's "Your past events" settlement widget (9.171):
    this volunteer's events with an elapsed showing still needing settlement,
    most recent first, capped at 8 -- or [] if the feature's off. Split out
    of get_context_data purely to keep that method under the complexity gate
    (docs/QUALITY_RUBRIC.md); folding the event_settlement_enabled check in
    here too (rather than as a second condition at the call site) keeps that
    method's own branch count down to the one "if volunteer" it already had.
    """
    if volunteer is None or not get_site_config().event_settlement_enabled:
        return []
    programmed_events = (
        Event.objects.filter(programmer=volunteer)
        .prefetch_related("showings")
        .distinct()
    )
    rows = []
    for event in programmed_events:
        status = event.settlement_status()
        if status not in ("not_recorded", "partial"):
            continue
        elapsed = [
            s
            for s in event.showings.all()
            if s.start <= now and not s.cancelled
        ]
        rows.append(
            {
                "event": event,
                "latest_showing": max(elapsed, key=lambda s: s.start),
                "status": status,
            }
        )
    rows.sort(key=lambda r: r["latest_showing"].start, reverse=True)
    return rows[:8]


def _film_prep_cards_for(user, volunteer, now):
    """Context for the film-readiness dashboard cards (9.174), or {}.

    "Your films": the films on events this volunteer is the programmer of,
    any status, plus a prompt row for each upcoming date of theirs that has
    no film recorded yet (a Family Film Club date, say). "Films needing a
    test": untested films in the look-ahead window across the venue, and
    "Drives to send back" (hired hard drives whose screenings are over),
    both for anyone who may update film prep (Programmer+ or a
    projectionist). Someone who is both a programmer and a projectionist
    sees their own films in the first card only, so nothing appears twice.
    """
    if not get_site_config().film_prep_enabled:
        return {}
    cards = {"film_overview_url": reverse("film-readiness-overview")}
    if volunteer is not None:
        mine = [
            film_row(p, now)
            for p in upcoming_film_preps(now).filter(
                event__programmer=volunteer
            )
        ]
        mine += [
            {
                "kind": "missing",
                "start": s.start,
                "event": s.event,
                "showing": s,
            }
            for s in showings_without_film(now, LOOKAHEAD_DAYS).filter(
                event__programmer=volunteer
            )
        ]
        if mine:
            cards["film_prep_mine"] = sorted(mine, key=lambda r: r["start"])[
                :8
            ]
    if user_can_update_film_prep(user):
        others = upcoming_film_preps(now, days=LOOKAHEAD_DAYS)
        if volunteer is not None:
            others = others.exclude(event__programmer=volunteer)
        rows = [film_row(p, now) for p in others]
        rows = [r for r in rows if r["readiness"] != READY]
        if rows:
            cards["film_tests"] = sorted(rows, key=lambda r: r["start"])[:8]
        returns = returns_outstanding(now)
        if returns:
            cards["film_returns"] = returns[:8]
    return cards


def _finance_settlement_review_url_for(user):
    """The dashboard's standing link to the Finance settlement review
    (9.171), or None -- gated on toolkit.write (this codebase has no
    separate Finance permission tier) and the feature flag. Split out
    alongside _outstanding_settlements_for to keep get_context_data's
    branch count down (docs/QUALITY_RUBRIC.md).
    """
    if (
        not user.has_perm("toolkit.write")
        or not get_site_config().event_settlement_enabled
    ):
        return None
    return reverse("finance-settlement-review")


class ToolkitIndexView(ListView):
    model = IndexLink
    template_name = "toolkit_index.html"

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()

        try:
            volunteer = user.volunteer
        except Exception:
            volunteer = None

        if volunteer:
            context["has_volunteer"] = True
            context["dash_hidden_cards"] = (
                volunteer.dashboard_hidden_cards or []
            )
            context["dash_card_order"] = volunteer.dashboard_card_order or []
            saved_keys = volunteer.favourite_link_keys or []
            available = {link["key"]: link for link in _available_links(user)}
            favourite_links = [
                available[k] for k in saved_keys if k in available
            ]
            if favourite_links:
                context["favourite_links"] = favourite_links
            context["manage_favourites_url"] = reverse(
                "manage-favourite-links"
            )

            # Welcome-back card: a logged-in Dormant volunteer is, by definition,
            # a returner. Offer a one-click route back to Active and nudge them
            # toward re-induction. Dismissable for the session (the card links
            # back here with ?dismiss_welcome=1).
            if self.request.GET.get("dismiss_welcome"):
                self.request.session["welcome_back_dismissed"] = True
            if (
                volunteer.status == Volunteer.STATUS_DORMANT
                and not self.request.session.get("welcome_back_dismissed")
            ):
                context["welcome_back"] = True
                context["next_induction"] = (
                    Showing.objects.filter(
                        confirmed=True,
                        start__gte=now,
                        event__tags__name__in=[
                            "induction",
                            "training-for-volunteers",
                        ],
                    )
                    .select_related("event")
                    .order_by("start")
                    .distinct()
                    .first()
                )

            context["consent_overdue"] = volunteer.consent_overdue
            if context["consent_overdue"]:
                from toolkit.inductions.models import InductionsSettings

                context["privacy_policy_url"] = (
                    InductionsSettings.load().privacy_policy_url
                )

            context["upcoming_shifts"] = list(
                RotaEntry.objects.filter(
                    volunteer=volunteer,
                    showing__start__gte=now,
                    showing__confirmed=True,
                )
                .select_related("showing__event", "role")
                .order_by("showing__start")[:5]
            )
            context["starred_events"] = list(
                VolunteerEventMark.objects.filter(
                    volunteer=volunteer,
                    mark_type=VolunteerEventMark.MARK_STAR,
                )
                .annotate(
                    next_showing=Min(
                        "event__showings__start",
                        filter=Q(event__showings__start__gte=now),
                    )
                )
                .filter(next_showing__isnull=False)
                .select_related("event")
                .order_by("next_showing")[:5]
            )

        if user.has_perm("toolkit.write"):
            lookback_start = (
                max(user.last_login, now - timedelta(days=30))
                if user.last_login
                else now - timedelta(days=30)
            )
            new_showings = list(
                Showing.objects.filter(
                    created_at__gte=lookback_start,
                    start__gte=now,
                    event__private=False,
                )
                .select_related("event")
                .order_by("created_at")[:8]
            )
            if new_showings:
                context["new_showings"] = new_showings

            unconfirmed_showings = list(
                Showing.objects.filter(
                    confirmed=False,
                    start__gte=now,
                    start__lte=now + timedelta(days=42),
                )
                .select_related("event")
                .order_by("start")[:8]
            )
            if unconfirmed_showings:
                context["unconfirmed_showings"] = unconfirmed_showings

        # Rota gaps — all logged-in users (9.91)
        cfg = get_site_config()
        if cfg.rota_gap_min_missing or cfg.rota_gap_min_pct:
            qs = (
                Showing.objects.filter(
                    start__gte=now,
                    start__lte=now + timedelta(days=21),
                    confirmed=True,
                )
                .annotate(
                    total_required=Count(
                        "rotaentry", filter=Q(rotaentry__required=True)
                    ),
                    filled=Count(
                        "rotaentry",
                        filter=Q(rotaentry__required=True)
                        & (
                            Q(rotaentry__volunteer__isnull=False)
                            | Q(rotaentry__name__gt="")
                        ),
                    ),
                )
                .annotate(
                    missing=ExpressionWrapper(
                        F("total_required") - F("filled"),
                        output_field=IntegerField(),
                    )
                )
                .select_related("event")
                .order_by("start")
            )
            gap_filter = Q()
            if cfg.rota_gap_min_missing:
                gap_filter |= Q(missing__gte=cfg.rota_gap_min_missing)
            if cfg.rota_gap_min_pct:
                gap_filter |= Q(
                    total_required__gt=0,
                    missing__gte=ExpressionWrapper(
                        F("total_required") * cfg.rota_gap_min_pct / 100,
                        output_field=IntegerField(),
                    ),
                )
            showings_with_gaps = list(qs.filter(gap_filter)[:8])
            if showings_with_gaps:
                context["showings_with_gaps"] = showings_with_gaps

        # Upcoming inductions & training — all logged-in users (9.93)
        upcoming_training = list(
            Showing.objects.filter(
                confirmed=True,
                start__gte=now,
                start__lte=now + timedelta(days=42),
                event__tags__name__in=["induction", "training-for-volunteers"],
            )
            .select_related("event")
            .order_by("start")
            .distinct()[:8]
        )
        if upcoming_training:
            context["upcoming_training"] = upcoming_training

        # Recent bulletins card (9.95). Only shows bulletins the current user
        # hasn't dismissed — "Got it" removes them from the dashboard entirely.
        from toolkit.labs.views import _unread_bulletins_for

        unread = list(_unread_bulletins_for(user)[:5])
        if unread:
            context["recent_bulletins"] = unread

        # Shopping list widget (9.88): items with open need flags.
        from toolkit.labs.models import NeedFlag

        shopping_needs = list(
            NeedFlag.objects.filter(resolved_at__isnull=True)
            .select_related("item", "flagged_by__member")
            .prefetch_related("pledge__pledged_by__member")
            .order_by("-flagged_at")[:8]
        )
        if shopping_needs:
            context["shopping_needs"] = shopping_needs

        # Open jobs widget (9.148): unresolved jobs from the ad-hoc jobs board.
        from toolkit.labs.models import Job
        from toolkit.labs.views import _urgency_order

        open_jobs = list(
            Job.objects.filter(resolved=False)
            .annotate(urgency_order=_urgency_order())
            .select_related("claimed_by")
            .order_by("urgency_order", "posted_at")[:8]
        )
        if open_jobs:
            context["open_jobs"] = open_jobs

        # Upcoming maintenance widget (9.80): next few recurring tasks by next_due.
        from toolkit.operations.models import MaintenanceTask

        active_tasks = (
            MaintenanceTask.objects.filter(active=True)
            .select_related("committed_to__member")
            .prefetch_related("records")
        )
        upcoming_maintenance = sorted(
            active_tasks, key=lambda t: (t.next_due is None, t.next_due)
        )[:5]
        if upcoming_maintenance:
            context["upcoming_maintenance"] = upcoming_maintenance
            context["MAINT_STATUS_OVERDUE"] = MaintenanceTask.STATUS_OVERDUE
            context["MAINT_STATUS_DUE_SOON"] = MaintenanceTask.STATUS_DUE_SOON

        # Settlement outstanding widget (9.171): automatically appears for
        # any volunteer set as Event.programmer on at least one event --
        # no opt-in needed, matching how new_showings/unconfirmed_showings
        # above are automatic for anyone with toolkit.write. Feature-flagged
        # off by default (the flag check lives inside the helper, so this
        # method only gains the one "if volunteer" branch it already had).
        outstanding_settlements = _outstanding_settlements_for(volunteer, now)
        if outstanding_settlements:
            context["outstanding_settlements"] = outstanding_settlements

        # Film readiness cards (9.174): flag check and de-duplication live
        # in the helper, keeping this method's branch count flat.
        context.update(_film_prep_cards_for(user, volunteer, now))

        # Finance's monthly settlement review (9.171): a standing link, not
        # a data-bearing card -- the review page itself does the querying,
        # so this costs nothing beyond a permission check and a flag read.
        # Unconditional assignment (rather than an "if" here) to keep this
        # method's branch count under the complexity gate.
        context["finance_settlement_review_url"] = (
            _finance_settlement_review_url_for(user)
        )

        return context


def health(request):  # noqa: ARG001 -- view signature
    try:
        connection.ensure_connection()
    except OperationalError:
        return HttpResponseServerError("db unavailable")
    return HttpResponse("ok")


@login_required
def toolkit_access(request):
    """Access transparency page: who holds elevated permissions and why.

    All logged-in volunteers can see this page.  It explains the three access
    tiers in plain language and lists current Panopticon and Programmer users.
    """
    panopticon_users = (
        User.objects.filter(is_superuser=True, is_active=True)
        .select_related("panopticon_grant")
        .order_by("panopticon_grant__granted_at", "username")
    )
    programmer_group = Group.objects.filter(name="Programmers").first()
    programmer_users = (
        (
            programmer_group.user_set.filter(is_active=True)
            .select_related("programmer_grant")
            .order_by("username")
        )
        if programmer_group
        else User.objects.none()
    )

    return render(
        request,
        "toolkit_access.html",
        {
            "panopticon_users": panopticon_users,
            "programmer_users": programmer_users,
        },
    )


@login_required
@require_POST
def dashboard_prefs(request):
    """AJAX endpoint: save dashboard card visibility and order for this volunteer."""
    try:
        volunteer = request.user.volunteer
    except Exception:
        return JsonResponse({"error": "no volunteer"}, status=403)
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"error": "bad request"}, status=400)
    if "hidden_cards" in data:
        volunteer.dashboard_hidden_cards = [
            str(k) for k in data["hidden_cards"]
        ]
    if "card_order" in data:
        volunteer.dashboard_card_order = [str(k) for k in data["card_order"]]
    volunteer.save(
        update_fields=["dashboard_hidden_cards", "dashboard_card_order"]
    )
    return JsonResponse({"ok": True})


@login_required
def manage_favourite_links(request):
    """Let a volunteer choose which nav links appear in their dashboard panel."""
    try:
        volunteer = request.user.volunteer
    except Exception:
        return redirect("toolkit-index")

    available = _available_links(request.user)
    available_keys = {link["key"] for link in available}

    if request.method == "POST":
        selected = [
            k for k in request.POST.getlist("links") if k in available_keys
        ]
        volunteer.favourite_link_keys = selected[:_MAX_FAVOURITE_LINKS]
        volunteer.save(update_fields=["favourite_link_keys"])
        messages.success(request, "Favourite links saved.")
        return redirect("toolkit-index")

    saved_keys = set(volunteer.favourite_link_keys or [])
    for link in available:
        link["selected"] = link["key"] in saved_keys

    return render(
        request,
        "manage_favourite_links.html",
        {
            "available_links": available,
            "max_links": _MAX_FAVOURITE_LINKS,
        },
    )


@panopticon_required
@require_POST
def mark_panopticon_reviewed(request, grant_id):
    """Mark a PanopticonGrant as reviewed today."""
    grant = get_object_or_404(PanopticonGrant, pk=grant_id)
    grant.last_reviewed_at = datetime.date.today()
    grant.reviewed_by = request.user
    grant.save()
    messages.success(
        request, f"Marked {grant.user.username}'s access as reviewed."
    )
    return HttpResponseRedirect(reverse("toolkit-access"))
