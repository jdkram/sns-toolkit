# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.shortcuts import get_object_or_404

from toolkit.toolkit_auth.decorators import panopticon_required
from toolkit.util.csv_export import csv_response

from ..models import InductionSession, InductionSignup


@panopticon_required
def manage_export_csv(request, slug):  # noqa: ARG001 -- view signature
    """Download a Simplelists-ready CSV of checked-in attendees."""
    session = get_object_or_404(InductionSession, slug=slug)
    checked_in = session.signups.filter(
        status=InductionSignup.STATUS_CHECKED_IN
    )
    rows = ([s.first_name, s.last_name, s.email] for s in checked_in)
    return csv_response(
        f"induction-{slug}-checked-in.csv", header=None, rows=rows
    )
