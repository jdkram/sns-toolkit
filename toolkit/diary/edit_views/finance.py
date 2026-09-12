# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Views for event settlement records (task 9.171).

Entry points, matching the user-stories doc's split between the
programmer's fast entry form, the event-level payment outcome, and the
finance-facing review of both:

- ``showing_settlement_edit`` -- per-showing attendance/ticket-income/bar
  actuals, reached from the Event Hub's past-showings section.
- ``event_distributor_payment_edit`` -- the event-level invoiced/paid
  outcome, also reached from the Hub.
- ``programmer_past_events`` -- a programmer's own past events with
  settlement status surfaced, the dashboard-card-linked destination.
- ``finance_settlement_review`` -- a date-ranged index of every event's
  settlement/distributor-payment status, for Finance's monthly rhythm.
  Links out to the two edit views above rather than duplicating them.
"""

import datetime
from functools import wraps

from django.contrib import messages
from django.db.models import Max
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

import toolkit.diary.forms as diary_forms
from toolkit.diary.models import (
    Event,
    SettlementRevision,
    Showing,
    ShowingSettlement,
    get_site_config,
)
from toolkit.toolkit_auth.decorators import write_required
from toolkit.util.volunteers import user_volunteer


def _settlement_enabled_or_404(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not get_site_config().event_settlement_enabled:
            raise Http404
        return func(request, *args, **kwargs)

    return wrapper


def _settlement_line_items_snapshot(settlement):
    return list(
        settlement.line_items.values(
            "description", "category", "count", "unit_price_gbp"
        ).order_by("order", "pk")
    )


@write_required
@_settlement_enabled_or_404
@require_http_methods(["GET", "POST"])
def showing_settlement_edit(request, showing_id):
    showing = get_object_or_404(Showing, pk=showing_id)
    settlement, _ = ShowingSettlement.objects.get_or_create(showing=showing)

    # Captured before the form touches the instance -- a ModelForm mutates
    # its bound instance's attributes during is_valid(), not just save(), so
    # this has to happen first or "prior" and "new" would be the same thing.
    # Only used to decide whether this save is a *correction* (something
    # already there, worth keeping a revision of) vs a first-ever entry.
    prior_had_data = settlement.has_any_data()
    prior_attendance = settlement.attendance
    prior_bar_contribution_gbp = settlement.bar_contribution_gbp
    prior_notes = settlement.notes
    prior_line_items = _settlement_line_items_snapshot(settlement)

    if request.method == "POST":
        form = diary_forms.ShowingSettlementForm(
            request.POST, instance=settlement
        )
        formset = diary_forms.SettlementLineItemFormSet(
            request.POST, instance=settlement
        )
        if form.is_valid() and formset.is_valid():
            settlement = form.save(commit=False)
            settlement.updated_by = request.user
            settlement.save()
            formset.instance = settlement
            formset.save()

            if prior_had_data and (
                settlement.attendance != prior_attendance
                or settlement.bar_contribution_gbp
                != prior_bar_contribution_gbp
                or settlement.notes != prior_notes
                or _settlement_line_items_snapshot(settlement)
                != prior_line_items
            ):
                SettlementRevision.objects.create(
                    settlement=settlement,
                    saved_by=request.user,
                    attendance=prior_attendance,
                    bar_contribution_gbp=prior_bar_contribution_gbp,
                    notes=prior_notes,
                    line_items_snapshot=[
                        {
                            **item,
                            "unit_price_gbp": (
                                str(item["unit_price_gbp"])
                                if item["unit_price_gbp"] is not None
                                else None
                            ),
                        }
                        for item in prior_line_items
                    ],
                )

            messages.success(
                request,
                f"Settlement saved for {showing.start:%d/%m/%Y %H:%M}.",
            )
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view",
                    kwargs={"event_id": showing.event_id},
                )
                + "#showings-heading"
            )
    else:
        form = diary_forms.ShowingSettlementForm(instance=settlement)
        formset = diary_forms.SettlementLineItemFormSet(instance=settlement)

    return render(
        request,
        "edit_showing_settlement.html",
        {
            "showing": showing,
            "event": showing.event,
            "form": form,
            "formset": formset,
            "ticket_income_total": settlement.ticket_income_total(),
        },
    )


@write_required
@_settlement_enabled_or_404
@require_http_methods(["GET", "POST"])
def event_distributor_payment_edit(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    if request.method == "POST":
        form = diary_forms.DistributorPaymentForm(request.POST, instance=event)
        if form.is_valid():
            event._saved_by = request.user
            form.save()
            messages.success(request, "Distributor payment outcome saved.")
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view", kwargs={"event_id": event_id}
                )
                + "#showings-heading"
            )
    else:
        form = diary_forms.DistributorPaymentForm(instance=event)

    return render(
        request,
        "edit_distributor_payment.html",
        {"event": event, "form": form},
    )


@write_required
@_settlement_enabled_or_404
@require_http_methods(["GET"])
def programmer_past_events(request):
    """A programmer's own past events, with settlement status surfaced.

    The dashboard card's linked destination (see toolkit/index/views.py) and
    the direct answer to "programmers can quickly see all their past events,
    showing whether there are outstanding requirements". Scoped to the
    current volunteer's own Event.programmer rows only -- past_events_search
    (9.149) already covers the general "find any past event" case.
    """
    volunteer = user_volunteer(request.user)
    now = timezone.now()
    rows = []
    if volunteer is not None:
        events = (
            Event.objects.filter(programmer=volunteer)
            .prefetch_related("showings")
            .distinct()
        )
        for event in events:
            elapsed = [
                s
                for s in event.showings.all()
                if s.start <= now and not s.cancelled
            ]
            if not elapsed:
                continue
            rows.append(
                {
                    "event": event,
                    "latest_showing": max(elapsed, key=lambda s: s.start),
                    "settlement_status": event.settlement_status(),
                    "distributor_payment_status": event.distributor_payment_status(),
                }
            )
        rows.sort(key=lambda r: r["latest_showing"].start, reverse=True)

    return render(
        request,
        "programmer_past_events.html",
        {"rows": rows, "has_volunteer": volunteer is not None},
    )


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _current_month_range(today):
    start = today.replace(day=1)
    if today.month == 12:
        end = today.replace(year=today.year + 1, month=1, day=1)
    else:
        end = today.replace(month=today.month + 1, day=1)
    end = end - datetime.timedelta(days=1)
    return start, end


@write_required
@_settlement_enabled_or_404
@require_http_methods(["GET"])
def finance_settlement_review(request):
    """Date-ranged index of every event/showing's settlement and
    distributor-payment status, for Finance's monthly review rhythm (9.171).

    Not a data-entry surface -- ``showing_settlement_edit`` and
    ``event_distributor_payment_edit`` already are where corrections
    happen. This view's whole job is helping Finance find the right ones
    without hunting through the calendar. Defaults to the current calendar
    month, matching Finance's existing paper-book rhythm, unlike
    past_events_search (9.149) which defaults to no filter at all.
    """
    now = timezone.now()
    default_from, default_to = _current_month_range(now.date())

    date_from = _parse_date(request.GET.get("date_from", "")) or default_from
    date_to = _parse_date(request.GET.get("date_to", "")) or default_to

    events = (
        Event.objects.annotate(latest_showing_start=Max("showings__start"))
        .filter(
            latest_showing_start__date__gte=date_from,
            latest_showing_start__date__lte=date_to,
            latest_showing_start__lte=now,
            no_financial_activity=False,
        )
        .prefetch_related("showings")
        .distinct()
        .order_by("-latest_showing_start")
    )

    rows = []
    for event in events:
        elapsed = [
            s
            for s in event.showings.all()
            if s.start <= now and not s.cancelled
        ]
        if not elapsed:
            continue
        elapsed.sort(key=lambda s: s.start, reverse=True)
        rows.append(
            {
                "event": event,
                "latest_showing": elapsed[0],
                "settlement_status": event.settlement_status(),
                "distributor_payment_status": event.distributor_payment_status(),
                "showings": [
                    {"showing": s, "status": s.settlement_status()}
                    for s in elapsed
                ],
            }
        )

    return render(
        request,
        "finance_settlement_review.html",
        {
            "rows": rows,
            "date_from": date_from,
            "date_to": date_to,
        },
    )
