# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from toolkit.toolkit_auth.decorators import panopticon_required

from ..models import InductionSession, InductionSignup


def _csv_formula_guard(value):
    """Prefix a leading `=`/`+`/`-`/`@` with a tab so spreadsheet apps treat
    the cell as text rather than executing it as a formula on open."""
    if value and value[0] in ("=", "+", "-", "@"):
        return "\t" + value
    return value


@panopticon_required
def manage_export_csv(request, slug):  # noqa: ARG001 -- view signature
    """Download a Simplelists-ready CSV of checked-in attendees."""
    session = get_object_or_404(InductionSession, slug=slug)
    checked_in = session.signups.filter(
        status=InductionSignup.STATUS_CHECKED_IN
    )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="induction-{slug}-checked-in.csv"'
    )
    writer = csv.writer(response)
    for s in checked_in:
        writer.writerow(
            [
                _csv_formula_guard(s.first_name),
                _csv_formula_guard(s.last_name),
                s.email,
            ]
        )
    return response
