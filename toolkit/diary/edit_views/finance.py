# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Views for event settlement records (task 9.171).

Entry points, matching the user-stories doc's split between the
programmer's fast entry form, the event-level payment outcome, and the
finance-facing review of both:

- ``showing_settlement_edit`` -- per-showing attendance/ticket-income/bar
  actuals, reached from the Event Hub's past-showings section.
- ``event_distributor_payment_edit`` -- the event-level invoiced/paid
  outcome, also reached from the Hub.
- ``bulk_mark_nothing_to_report`` -- mark several outstanding showings on a
  recurring series "nothing to report" in one go, for a backlog of elapsed
  showings that never need logging one-by-one.
- ``programmer_past_events`` -- a programmer's own past events with
  settlement status surfaced, the dashboard-card-linked destination.
- ``finance_settlement_review`` -- a date-ranged index of every event's
  settlement/distributor-payment status, for Finance's monthly rhythm.
  Links out to the two edit views above rather than duplicating them.
- ``event_prs_registration_edit`` -- optional PRS/PPL performer-registration
  record for one event, reached from the Hub alongside distributor payment.
- ``prs_report`` -- CSV export of the above across a date range, draft
  material for whoever submits the actual PRS/PPL return.
"""

import csv
import datetime
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

import toolkit.diary.forms as diary_forms
from toolkit.diary.models import (
    Event,
    PerformerRegistration,
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
                f"Finances saved for {showing.start:%d/%m/%Y %H:%M}.",
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
@require_http_methods(["POST"])
def bulk_mark_nothing_to_report(request):
    """Mark several outstanding showings "nothing to report" in one go
    (9.171 follow-up) -- the entry-form fix for a backlog of elapsed
    showings on a recurring regular (a weekly meetup, say) where nothing
    ever needs logging one-by-one. Deliberately not a fake zero-value line
    item (would pollute ticket-income totals and the PRS/PPL report) --
    see ShowingSettlement.nothing_to_report.

    Doesn't touch attendance -- a showing already partially recorded (e.g.
    just a headcount) keeps that headcount, only gains the flag. No
    confirmation step and no revision recorded, matching this codebase's
    existing pattern for reversible single-field toggles
    (no_financial_activity, Unconfirm) -- each showing stays individually
    correctable afterwards via its normal settlement form.
    """
    # Cast before querying: pk__in with a non-numeric string raises
    # ValueError from the field, i.e. a 500 rather than the "nothing
    # selected" path, on any hand-crafted or mangled POST.
    showing_ids = [
        int(raw)
        for raw in request.POST.getlist("showing_ids")
        if raw.isdigit()
    ]
    showings = list(
        Showing.objects.filter(pk__in=showing_ids).select_related("event")
    )
    if not showings:
        messages.warning(request, "No showings selected.")
        return HttpResponseRedirect(reverse("toolkit-index"))

    for showing in showings:
        settlement, _ = ShowingSettlement.objects.get_or_create(
            showing=showing
        )
        if not settlement.nothing_to_report:
            settlement.nothing_to_report = True
            settlement.updated_by = request.user
            settlement.save()

    messages.success(
        request,
        f"Marked {len(showings)} showing{'s' if len(showings) != 1 else ''} "
        "as nothing to report.",
    )
    event_id = showings[0].event_id
    return HttpResponseRedirect(
        reverse("edit-event-details-view", kwargs={"event_id": event_id})
        + "#showings-heading"
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
@require_http_methods(["GET", "POST"])
def event_prs_registration_edit(request, event_id):
    """Optional PRS/PPL performer-registration record for one event
    (9.171). Never a blocker -- see PerformerRegistration's docstring --
    so unlike showing_settlement_edit this has no "prior data" revision
    tracking: a low-stakes, freely-editable record, not one Persona B
    needs protected from being overwritten.
    """
    event = get_object_or_404(Event, pk=event_id)
    registration, _ = PerformerRegistration.objects.get_or_create(event=event)

    if request.method == "POST":
        form = diary_forms.PerformerRegistrationForm(
            request.POST, instance=registration
        )
        formset = diary_forms.PRSPerformerEntryFormSet(
            request.POST, instance=registration
        )
        if form.is_valid() and formset.is_valid():
            registration = form.save(commit=False)
            registration.updated_by = request.user
            registration.save()
            formset.instance = registration
            formset.save()
            messages.success(request, "PRS/PPL registration saved.")
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view", kwargs={"event_id": event_id}
                )
                + "#showings-heading"
            )
    else:
        form = diary_forms.PerformerRegistrationForm(instance=registration)
        formset = diary_forms.PRSPerformerEntryFormSet(instance=registration)

    return render(
        request,
        "edit_prs_registration.html",
        {"event": event, "form": form, "formset": formset},
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


def _date_range_from_request(request):
    now = timezone.now()
    default_from, default_to = _current_month_range(now.date())
    date_from = _parse_date(request.GET.get("date_from", "")) or default_from
    date_to = _parse_date(request.GET.get("date_to", "")) or default_to
    return now, date_from, date_to


def _events_with_elapsed_showings_in_range(
    date_from, date_to, now, extra_filters=None
):
    """Every event with at least one elapsed, non-cancelled showing whose
    *latest elapsed* showing falls in the range, paired with that event's
    sorted elapsed showings -- the shared query behind
    finance_settlement_review and prs_report (9.171), so the two never
    drift on what counts as "in range". `extra_filters` narrows further
    (e.g. prs_report's cost_type scoping) without duplicating the base
    query.

    Filters in Python on the max of each event's *elapsed* showings, not a
    DB-side Max("showings__start") -- a recurring event's overall latest
    showing is routinely a future date outside any reporting month, which
    would wrongly exclude the whole event from a range that its elapsed
    showings do fall in (found during 2026-09-14 manual testing).

    The DB still narrows to events with an elapsed, non-cancelled showing
    *inside* the range, which is a strict superset of the answer: an event
    whose latest elapsed showing falls in the range necessarily has an
    elapsed showing in the range. Without it the candidate set is every
    event the venue has ever run, which grows with total history rather
    than with the reporting window (on the dev DB, 92 events loaded with
    all their showings to return 10 for one month).
    """
    candidates = (
        Event.objects.filter(
            showings__start__lte=now,
            showings__start__date__gte=date_from,
            showings__start__date__lte=date_to,
            showings__cancelled=False,
            no_financial_activity=False,
            **(extra_filters or {}),
        )
        .prefetch_related("showings")
        .distinct()
    )

    result = []
    for event in candidates:
        elapsed = [
            s
            for s in event.showings.all()
            if s.start <= now and not s.cancelled
        ]
        if not elapsed:
            continue
        elapsed.sort(key=lambda s: s.start, reverse=True)
        latest_elapsed = elapsed[0].start
        if not (date_from <= latest_elapsed.date() <= date_to):
            continue
        result.append((event, elapsed))
    result.sort(key=lambda pair: pair[1][0].start, reverse=True)
    return result


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
    now, date_from, date_to = _date_range_from_request(request)

    rows = []
    for event, elapsed in _events_with_elapsed_showings_in_range(
        date_from, date_to, now
    ):
        registration = getattr(event, "performer_registration", None)
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
                "prs_relevant": event.prs_relevant(),
                "prs_recorded": bool(
                    registration and registration.has_any_data()
                ),
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


def _prs_report_rows_for_event(event, elapsed):
    attendance_total = 0
    ticket_income_total = Decimal("0")
    for showing in elapsed:
        settlement = getattr(showing, "settlement", None)
        if settlement is None:
            continue
        if settlement.attendance is not None:
            attendance_total += settlement.attendance
        ticket_income_total += settlement.ticket_income_total()

    registration = getattr(event, "performer_registration", None)
    performers = list(registration.performers.all()) if registration else []
    common = [
        event.name,
        timezone.localtime(elapsed[0].start).strftime("%d/%m/%Y %H:%M"),
        event.get_cost_type_display() if event.cost_type else "",
        "Yes" if event.outside_hire else "No",
        registration.filled_in_by if registration else "",
        (
            ""
            if registration is None or registration.vat_on_tickets is None
            else ("Yes" if registration.vat_on_tickets else "No")
        ),
    ]
    tail = [str(attendance_total), str(ticket_income_total)]

    if not performers:
        return [common + ["", "", ""] + tail]
    rows = []
    for performer in performers:
        rows.append(
            common
            + [
                performer.name,
                performer.get_registered_display(),
                (
                    ""
                    if performer.is_volunteer_or_amateur is None
                    else ("Yes" if performer.is_volunteer_or_amateur else "No")
                ),
            ]
            + tail
        )
    return rows


@write_required
@_settlement_enabled_or_404
@require_http_methods(["GET"])
def prs_report(request):
    """CSV export for whoever submits the PRS/PPL return (9.171): every
    PRS-relevant event (Event.prs_relevant()) in the date range, one row
    per performer -- or one blank-performer row for an event that hasn't
    had anything entered yet, so it stays visible as needing follow-up
    rather than silently vanishing from the export.

    Draft material for a human to check against bank/till figures, not an
    automated filing -- the scoping doc's evidence is explicit that
    reconciliation is always manual, line-by-line, with cash/bank-verified
    figures winning over any estimate every time.
    """
    now, date_from, date_to = _date_range_from_request(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="prs_report_{date_from}_{date_to}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        [
            "Event",
            "Last showing",
            "Cost type",
            "Outside hire",
            "Filled in by",
            "VAT on tickets",
            "Performer",
            "Registered",
            "Volunteer/amateur",
            "Attendance (elapsed showings in range)",
            "Ticket income (elapsed showings in range, £)",
        ]
    )
    events = _events_with_elapsed_showings_in_range(
        date_from,
        date_to,
        now,
        extra_filters={
            "cost_type__in": (
                Event.COST_TYPE_PERFORMER_FEE,
                Event.COST_TYPE_VENUE_HIRE,
            )
        },
    )
    for event, elapsed in events:
        for row in _prs_report_rows_for_event(event, elapsed):
            writer.writerow(row)

    return response
