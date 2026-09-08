# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-input"
"""Shared iCalendar (RFC 5545) VCALENDAR/VEVENT builder.

Unifies toolkit/diary/calendar_links.py's build_ics with
toolkit/inductions/views/public.py's calendar_ics (September 2026), which
had diverged in two ways worth noting rather than silently fixing:

- diary's version escaped SUMMARY/DESCRIPTION/LOCATION per RFC 5545;
  inductions' didn't, so a session title containing a comma or semicolon
  produced a malformed .ics file.
- diary's version expresses times in absolute UTC ("Z" form); inductions'
  used DTSTART;TZID=Europe/London with a naive-looking wall-clock string
  taken straight from session.date.strftime(). With USE_TZ=True (the
  project default, unchanged by any settings file), session.date is a
  timezone-aware datetime whose strftime() prints whatever tzinfo it
  currently carries — UTC, not Europe/London — so the emitted time was
  quietly wrong by an hour for any session during BST, despite the label
  claiming otherwise.

Both call sites now go through the UTC form below, which sidesteps the
TZID bug rather than requiring each call site to convert correctly.
"""

import datetime as _dt


def _utc():
    return _dt.timezone.utc


def _utc_compact(dt):
    """Format a datetime as basic UTC iCalendar form: YYYYMMDDTHHMMSSZ.

    Naive datetimes are treated as already being UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_utc())
    return dt.astimezone(tz=_utc()).strftime("%Y%m%dT%H%M%SZ")


def ics_escape(text):
    """Escape per RFC 5545: backslash, semicolon, comma, newline."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def build_vevent(
    *,
    uid,
    dtstart,
    dtend,
    summary,
    location="",
    dtstamp=None,
    description=None,
    url=None,
    prodid="-//Toolkit//EN",
):
    """Build a single-event VCALENDAR payload (CRLF-terminated, unfolded).

    No external dependency — one VEVENT is trivial, and long lines are not
    folded (clients tolerate this and our content rarely exceeds 75 octets
    in practice).
    """
    if dtstamp is None:
        dtstamp = _dt.datetime.now(tz=_utc())

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{ics_escape(prodid)}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_utc_compact(dtstamp)}",
        f"DTSTART:{_utc_compact(dtstart)}",
        f"DTEND:{_utc_compact(dtend)}",
        f"SUMMARY:{ics_escape(summary)}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{ics_escape(description)}")
    lines.append(f"LOCATION:{ics_escape(location)}")
    if url:
        lines.append(f"URL:{url}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"
