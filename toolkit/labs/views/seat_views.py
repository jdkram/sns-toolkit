# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 5.5"]; status: "#ai-written"
"""Public seat views page (9.176).

A seating plan of the cinema: pick a seat, see a photo of the screen from
it. The seat layout lives in ``seat_views.js``; this view only tells it
which seats have a photo. A seat has a photo when a file named after its
seat ID (``C5.jpg``, ``COMFY4.jpg``) sits in ``static/labs/seat_views/``,
so adding a photo needs no code change.
"""

from pathlib import Path

from django.shortcuts import render
from django.templatetags.static import static

from ._common import _feature_enabled_or_404

SEAT_PHOTO_DIR = (
    Path(__file__).resolve().parent.parent / "static" / "labs" / "seat_views"
)


def seat_photo_urls():
    """Map each photographed seat ID to its static URL.

    URLs go through ``static()`` one file at a time because production uses
    manifest storage, which hashes each filename; a directory prefix would
    not resolve.
    """
    return {
        path.stem: static(f"labs/seat_views/{path.name}")
        for path in sorted(SEAT_PHOTO_DIR.glob("*.jpg"))
    }


@_feature_enabled_or_404("seat_views_enabled")
def seat_views(request):
    return render(
        request,
        "labs/seat_views.html",
        {"seat_photos": seat_photo_urls()},
    )
