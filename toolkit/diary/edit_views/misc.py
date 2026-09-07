import json
import logging


from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.contrib import messages
from django.contrib.auth.decorators import (
    permission_required,
)
from toolkit.toolkit_auth.decorators import (
    write_required,
)
from django.views.decorators.http import require_POST

from toolkit.diary.models import (
    Event,
    VolunteerEventMark,
)

# Shared utility method:

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_messages(request):
    message_list = [
        {"message": m.message, "tags": m.tags, "level": m.level}
        for m in messages.get_messages(request)
    ]

    return HttpResponse(
        json.dumps(message_list), content_type="application/json"
    )


@require_POST
@permission_required("diary.change_rotaentry")
def toggle_event_mark(request):
    """Set or clear the ★/☽ mark for the current user on an event. Returns JSON.

    Accepts mark_type: "star", "shadow", or "" (clear).
    One mark per (volunteer, event) — setting a new type replaces any existing one.
    """
    mark_type = request.POST.get("mark_type", "")
    event_id = request.POST.get("event_id")

    if mark_type not in (
        "",
        VolunteerEventMark.MARK_STAR,
        VolunteerEventMark.MARK_SHADOW,
    ):
        return JsonResponse({"error": "Invalid mark type"}, status=400)

    try:
        event = Event.objects.get(pk=event_id)
    except (Event.DoesNotExist, ValueError):
        return JsonResponse({"error": "Event not found"}, status=404)

    try:
        volunteer = request.user.volunteer
    except Exception:
        return JsonResponse(
            {"error": "No volunteer record for this user"}, status=403
        )

    if not mark_type:
        VolunteerEventMark.objects.filter(
            volunteer=volunteer, event=event
        ).delete()
    else:
        VolunteerEventMark.objects.update_or_create(
            volunteer=volunteer,
            event=event,
            defaults={"mark_type": mark_type},
        )

    return JsonResponse({"mark_type": mark_type})


@write_required
def view_force_error(request):
    raise AssertionError("Forced exception")
