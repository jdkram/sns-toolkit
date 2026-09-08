# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.7"]; status: "#ai-written"
"""
Per-showing "Add to calendar" link generation.

Three flavours per showing:
  - .ics file (text/calendar) — universal, works with Apple Calendar,
    Outlook desktop, anything that handles the MIME type.
  - Google Calendar prepopulated template URL.
  - Outlook.com prepopulated template URL.

These are one-shot adds, not subscriptions: if the showing moves, the
calendar entry won't update. See docs/TASKS.md 9.10.4a.
"""

from urllib.parse import urlencode

from django.conf import settings

from toolkit.util.ics import build_vevent


def _utc_compact(dt):
    """Format a tz-aware datetime as basic UTC iCalendar form: YYYYMMDDTHHMMSSZ."""
    return dt.astimezone(tz=_utc()).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso(dt):
    """Format a tz-aware datetime as extended UTC ISO 8601, no fractional seconds."""
    return dt.astimezone(tz=_utc()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc():
    import datetime as _dt

    return _dt.timezone.utc


def _venue_location():
    venue = getattr(settings, "VENUE", {}) or {}
    return (
        venue.get("cinemaname")
        or venue.get("longname")
        or venue.get("name")
        or ""
    )


def _summary(showing):
    parts = [showing.event.name]
    room = showing.primary_room
    # MULTIROOM_ENABLED is settings-only — no SiteConfiguration counterpart.
    if getattr(settings, "MULTIROOM_ENABLED", False) and room:
        parts.append(f"({room.name})")
    return " ".join(p for p in parts if p)


def _description(showing, public_url=None):
    bits = [
        "⚠ This entry uses the event's public start time, not your shift time. "
        "Please check the rota notes and update this calendar entry to match your actual shift."
    ]
    summary = (showing.event.copy_summary or "").strip()
    if summary:
        bits.append(summary)
    if public_url:
        bits.append(public_url)
    return "\n\n".join(bits)


def _public_url(request, showing):
    """Absolute URL to the public event page for this showing."""
    if request is None:
        return ""
    from django.urls import reverse

    return request.build_absolute_uri(
        reverse("single-showing-view", kwargs={"showing_id": showing.pk})
    )


def build_ics(showing, request=None, dtstamp=None):
    """Single-event iCalendar payload (RFC 5545) for one showing."""
    venue = getattr(settings, "VENUE", {}) or {}
    host = (
        request.get_host()
        if request is not None
        else (
            venue.get("url", "toolkit.local")
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )
    )
    public_url = _public_url(request, showing)

    return build_vevent(
        uid=f"showing-{showing.pk}@{host}",
        dtstart=showing.start,
        dtend=showing.end_time,
        summary=_summary(showing),
        location=_venue_location(),
        dtstamp=dtstamp,
        description=_description(showing, public_url),
        url=public_url or None,
        prodid=f"-//{venue.get('longname', 'Toolkit')}//Toolkit//EN",
    )


def google_calendar_url(showing, request=None):
    public_url = _public_url(request, showing)
    params = {
        "action": "TEMPLATE",
        "text": _summary(showing),
        "dates": f"{_utc_compact(showing.start)}/{_utc_compact(showing.end_time)}",
        "details": _description(showing, public_url),
        "location": _venue_location(),
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(
        {k: v for k, v in params.items() if v}
    )


def outlook_calendar_url(showing, request=None):
    public_url = _public_url(request, showing)
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": _summary(showing),
        "startdt": _utc_iso(showing.start),
        "enddt": _utc_iso(showing.end_time),
        "body": _description(showing, public_url),
        "location": _venue_location(),
    }
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(
        {k: v for k, v in params.items() if v}
    )
