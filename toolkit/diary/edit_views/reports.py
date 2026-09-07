import datetime
import logging
import csv


from django.http import (
    HttpResponse,
    Http404,
)
from django.shortcuts import render
from django.db.models import Q
from toolkit.toolkit_auth.decorators import (
    feature_required,
)

from toolkit.diary.models import (
    Showing,
)

# Shared utility method:
from toolkit.diary.daterange import get_date_range

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@feature_required("diary_reports")
def view_terms_report_csv(
    request, year: int, month: int, day: int
) -> HttpResponse:
    query_days_ahead = request.GET.get("daysahead", None)
    start_date, days_ahead = get_date_range(year, month, day, query_days_ahead)
    if start_date is None:
        raise Http404(days_ahead)

    end_date = start_date + datetime.timedelta(days=int(days_ahead))

    showings = (
        Showing.objects.not_cancelled()
        .confirmed()
        .start_in_range(start_date, end_date)
        .order_by("start")
        .select_related()
    )

    response = HttpResponse(
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="terms-{start_date.date().isoformat()}.csv"'
        },
    )
    writer = csv.writer(response)
    writer.writerow(["date", "time", "title", "terms"])
    for showing in showings:
        writer.writerow(
            [
                showing.start.date().isoformat(),
                showing.start.time().isoformat(timespec="minutes"),
                showing.event.name,
                showing.event.terms,
            ]
        )

    return response


@feature_required("diary_reports")
def view_event_field(request, field, year=None, month=None, day=None):
    # Method shared across various (slightly primitive) views into event data;
    # the copy, terms and rota reports.
    #
    # This method gets the list of events for the given date range (using the
    # same shared logic for parsing the parameters as the public list / edit
    # list) and then uses the appropriate template to render the results.

    assert field in ("copy", "terms", "rota", "copy_summary")

    query_days_ahead = request.GET.get("daysahead", None)
    start_date, days_ahead = get_date_range(year, month, day, query_days_ahead)
    if start_date is None:
        raise Http404(days_ahead)
    end_date = start_date + datetime.timedelta(days=days_ahead)
    # The rota view should include cancelled showings so volunteers can see what's off.
    # Copy/terms/copy_summary reports only care about active, non-private events.
    showings_qs = Showing.objects.confirmed().start_in_range(
        start_date, end_date
    )
    if field != "rota":
        showings_qs = showings_qs.not_cancelled().filter(event__private=False)
    showings = (
        showings_qs.order_by("start")
        #              following prefetch is for the rota view
        .prefetch_related(
            "rotaentry_set__role__required_qualification",
            "rotaentry_set__volunteer__member",
        ).select_related()
    )

    search = request.GET.get("search")
    if search:
        logger.info(f"Search term: {search}")
        # Note slightly sneaky use of **; this effectively results in a method
        # call like: showings.filter(event__copy__icontains=search)
        showings = showings.filter(
            Q(**{f"event__{field}__icontains": search})
            | Q(event__name__icontains=search)
        )

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "days_ahead": days_ahead,
        "showings": showings,
        "event_field": field,
        "search": search,
    }

    return render(request, f"view_{field}.html", context)
