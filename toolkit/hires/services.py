# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Hire enquiry workflow: emails, the meeting-aware reply clock, decisions.

Everything that changes ``HireEnquiry.status`` goes through here so the
rules in docs/tasks/hires.md (silence is never the outcome; a person's
status change counts as a reply) live in one place.
"""

import datetime
import logging
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from toolkit.audit.models import email_trigger
from toolkit.toolkit_auth import password_emails

from . import defaults
from .models import (
    ApprovedTech,
    HireEmailTemplate,
    HireEnquiry,
    ProgrammingMeeting,
    get_hire_settings,
    hires_enabled,
)

logger = logging.getLogger(__name__)

E = HireEnquiry


# key -> the trigger_source recorded in SentEmailLog for each hirer email.
HIRER_EMAIL_SOURCES = {
    "acknowledgement": "Hire enquiry: acknowledgement",
    "accepted": "Hire enquiry: accepted",
    "maybe": "Hire enquiry: maybe",
    "declined": "Hire enquiry: declined",
    "declined_capacity": "Hire enquiry: auto capacity decline",
    "declined_no_support": "Hire enquiry: auto no-support decline",
    "meeting_moved": "Hire enquiry: meeting moved",
    "booking_confirmation": "Hire enquiry: booking confirmation",
    "booked": "Hire enquiry: booked",
}
_KEY_FOR_SOURCE = {v: k for k, v in HIRER_EMAIL_SOURCES.items()}


def _venue():
    return password_emails.venue_name()


def _format(template, **kwargs):
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        # A bad admin edit must not stop the honest email going out.
        return template


def site_base_url():
    # Management commands have no request, so use the venue's siteurl
    # (same convention as the password emails).
    return (settings.VENUE.get("siteurl") or "").rstrip("/")


def abs_url(path):
    return f"{site_base_url()}{path}"


def render_email(key, **vars):
    """Subject, body for a hirer or internal email (override, else default)."""
    row = HireEmailTemplate.objects.filter(key=key).first()
    if row:
        subject, body = row.subject, row.body
    else:
        subject, body = (
            defaults.EMAIL_DEFAULTS.get(key) or defaults.INTERNAL_DEFAULTS[key]
        )
    vars.setdefault("venue", _venue())
    return _format(subject, **vars), _format(body, **vars)


def _fmt_dt(dt):
    return timezone.localtime(dt).strftime("%a %-d %b %Y, %H:%M")


def describe_dates(enquiry, accepted_only=False):
    rows = enquiry.dates()
    if accepted_only:
        rows = [d for d in rows if d.accepted] or rows
    return "\n".join(
        f"- {_fmt_dt(d.start)} to {timezone.localtime(d.end):%H:%M} "
        f"(building open {_fmt_dt(d.get_in)} to "
        f"{timezone.localtime(d.get_out):%H:%M})"
        for d in rows
    )


def money(amount):
    return f"£{amount:.2f}".replace(".00", "")


def late_notice_text(cfg=None):
    """The hirer-facing nudge about late finishes (admin-editable)."""
    cfg = cfg or get_hire_settings()
    fee = cfg.late_night_fee_gbp
    return _format(
        cfg.late_night_notice_text or defaults.LATE_NIGHT_NOTICE,
        late_from=f"{cfg.late_night_from:%H:%M}",
        late_fee=money(fee) if fee else "an additional fee we'll confirm",
    )


def door_notice_text(cfg=None, door_fee=None):
    """Expectation-setting about door staff and their cost (editable)."""
    cfg = cfg or get_hire_settings()
    fee = door_fee if door_fee is not None else cfg.door_staff_fee_gbp
    return _format(
        cfg.door_staff_notice_text or defaults.DOOR_STAFF_NOTICE,
        door_fee=(
            money(fee)
            if fee is not None
            else "an additional charge we'll confirm"
        ),
    )


def guarantee_text(enquiry):
    """Plain statement of what is promised, what costs extra, what is not."""
    extras = ""
    best_effort = "bar staff, projection and any other volunteer help"
    if enquiry.door_staff_required():
        extras = (
            "Door staff: "
            + door_notice_text(door_fee=enquiry.door_staff_fee_gbp)
            + "\n"
        )
    else:
        best_effort = (
            "bar staff, door staff, projection and any other volunteer help"
        )
    return _format(
        defaults.GUARANTEE_BLOCK, extras=extras, best_effort=best_effort
    )


def _send(to, subject, body, source):
    with email_trigger(source):
        send_mail(
            subject=subject,
            message=body,
            from_email=password_emails.from_email(),
            recipient_list=list(to),
            fail_silently=False,
        )


def _info_line():
    cfg = get_hire_settings()
    url = (cfg.info_page_url or "").strip()
    if not url:
        return ""
    if url.startswith("/"):
        url = abs_url(url)
    return f"More about hiring here, including how it all works: {url}\n\n"


def render_hirer_email(enquiry, key, **extra):
    """Subject and body of a hirer email, filled in for this enquiry."""
    vars = {
        "name": enquiry.contact_name,
        "title": enquiry.title,
        "dates": describe_dates(enquiry),
        "guarantee": guarantee_text(enquiry),
        "meeting_date": (
            f"{enquiry.meeting.date:%-d %B %Y}" if enquiry.meeting else "TBC"
        ),
        "meeting_line": (
            "Your enquiry was due to be discussed at our meeting on "
            f"{enquiry.meeting.date:%-d %B %Y}, and nobody was able to take "
            "it on."
            if enquiry.meeting
            else "Nobody was able to take it on."
        ),
        "reply_by": (
            f"{enquiry.reply_deadline:%-d %B %Y}"
            if enquiry.reply_deadline
            else "soon"
        ),
        "callout_deadline": (
            f"{enquiry.callout_deadline:%-d %B %Y}"
            if enquiry.callout_deadline
            else "soon"
        ),
        "coordinator_line": "",
        "details_url": "",
        "techs": "",
        "terms": "",
        "fee": "",
        "agreement_url": "",
        "timing": "",
        "window_note": "",
        "indicative_fee": "",
        "rate_note": "",
        "info_line": _info_line(),
    }
    vars.update(extra)
    return render_email(key, **vars)


def send_to_hirer(enquiry, key, source, override=None, **extra):
    """Email the hirer. `override` is a (subject, body) a person edited."""
    if override:
        subject, body = override
    else:
        subject, body = render_hirer_email(enquiry, key, **extra)
    body += (
        "\n\n--\nHow we use your information: "
        + abs_url(reverse("hires:privacy"))
        + "\n"
    )
    _send([enquiry.contact_email], subject, body, source)


def notify_internal(key, source, extra_to=(), **vars):
    cfg = get_hire_settings()
    to = cfg.notification_address_list()
    to += [a for a in extra_to if a and a not in to]
    if not to:
        logger.warning("Hire notification %s: no addresses configured", key)
        return False
    vars.setdefault("queue_url", abs_url(reverse("hires:queue")))
    try:
        subject, body = render_email(key, **vars)
        _send(to, subject, body, source)
    except Exception:
        # An SMTP or template failure on an internal email must not stop
        # the daily job before it reaches the honest auto-decline step.
        logger.exception("Hire internal notification %s failed", key)
        return False
    return True


# --- Indicative fee ---------------------------------------------------------

UNIT_LABELS = {"flat": "per hire", "hour": "per hour", "block4": "per 4 hours"}


def price_rows(hire_types=None):
    """Public price list: one row per active type (fees of 0 = on request)."""
    from .models import HireType

    rows = []
    for t in hire_types or HireType.objects.filter(active=True):
        unit = UNIT_LABELS.get(t.unit, "")

        def fee(amount, unit=unit):
            return f"{money(amount)} {unit}" if amount else "on request"

        rows.append(
            {
                "name": t.name,
                "description": t.public_description,
                "community": fee(t.community_fee_gbp),
                "corporate": fee(t.corporate_fee_gbp),
                "vat": t.vat_applies,
            }
        )
    return rows


def indicative_fee_text(hire_type, tier, hire_dates, cfg=None):
    """A plain-English guide to the fee, before anyone has decided anything.

    Worked out by the same function as the real quote. Says plainly that it
    is a guide, never mentions our internal costs, and for the community
    rate (which the meeting grants) also gives the full-rate figure, so
    nobody is surprised if it isn't granted.
    """
    from .models import HireEnquiry, quote_gbp

    if not hire_type:
        return ""
    cfg = cfg or get_hire_settings()
    amount = quote_gbp(hire_type, tier, hire_dates) if hire_dates else None
    if amount is None or amount <= 0:
        return "We'll confirm the fee when we reply."
    vat = " plus VAT" if hire_type.vat_applies else ""
    if tier == HireEnquiry.TIER_COMMUNITY:
        text = f"About {money(amount)}{vat} at the community rate, if the volunteers agree it"
        full = quote_gbp(hire_type, HireEnquiry.TIER_CORPORATE, hire_dates)
        if full > amount:
            text += f"; at the full rate it would be about {money(full)}{vat}"
    else:
        text = f"About {money(amount)}{vat} at the full rate"
    late = any(d.is_late_night() for d in hire_dates)
    if late and not hire_type.includes_late_night and cfg.late_night_fee_gbp:
        text += (
            f", including a {money(cfg.late_night_fee_gbp)} late-night charge"
        )
    text += "."
    if late and hire_type.provides_door_staff:
        text += " Door staff for a late club night are charged on top."
    return text + (
        " This is a guide: the fee is confirmed in writing before anything "
        "is booked."
    )


# --- What else is on (meeting support) ----------------------------------------

WINDOW_DAYS = 7


CLASH = "clash"  # red: same time, same space
CHECK = "check"  # yellow: might clash; a person should look


def _overlaps(a_from, a_to, b_from, b_to):
    return a_from < b_to and a_to > b_from


def _cleanup_end(frm, to, cfg):
    """When a late use's clearing-up is assumed to end, or None if not late.

    Clean-up after a late night is often forgotten when booking the next
    morning, so a late finish is treated as holding its space until
    `cfg.cleanup_until` the following day.
    """
    f, t = timezone.localtime(frm), timezone.localtime(to)
    crosses_midnight = t.date() > f.date()
    if not crosses_midnight and t.time() <= cfg.late_night_from:
        return None
    day = t.date() if crosses_midnight else t.date() + datetime.timedelta(1)
    end = timezone.make_aware(
        datetime.datetime.combine(day, cfg.cleanup_until)
    )
    return end if end > to else None


def _classify(it, hd, hire_rooms, cfg):
    """(tier, reason) for one other use of the building against a hire date.

    Red only when certain: overlapping times in a room both are using. Most
    first enquiries have no rooms yet, so their overlaps can only be amber.
    """
    rooms = it["room_ids"]
    known = bool(rooms) and bool(hire_rooms)
    shared = known and bool(rooms & hire_rooms)
    if _overlaps(it["from"], it["to"], hd.get_in, hd.get_out):
        if shared:
            return CLASH, "Same time, same space"
        if known:
            return CHECK, "Same time, different space"
        return CHECK, "Same time; rooms not known yet"
    if known and not shared:
        return "", ""
    if it["cleanup_to"] and _overlaps(
        it["to"], it["cleanup_to"], hd.get_in, hd.get_out
    ):
        return CHECK, "Late finish before: may still be clearing up"
    own_cleanup = _cleanup_end(hd.get_in, hd.get_out, cfg)
    if own_cleanup and _overlaps(
        hd.get_out, own_cleanup, it["from"], it["to"]
    ):
        return CHECK, "This hire finishes late: its clean-up may run into this"
    for gap in (hd.get_in - it["to"], it["from"] - hd.get_out):
        mins = gap.total_seconds() / 60
        if 0 <= mins < cfg.changeover_minutes:
            return CHECK, f"Tight changeover ({mins:.0f} min)"
    return "", ""


def whats_on(enquiries, window=WINDOW_DAYS):
    """For each enquiry date: everything else in the building within +-7 days.

    Returns {enquiry.pk: [per-date dict]}. A handful of queries however
    many enquiries are shown, so the queue can show it on every card.
    Includes other hires still being decided (they are not on the diary
    yet), and tiers each thing against the hire date: a clash (same time,
    same space), something to check (same time elsewhere or rooms unknown,
    a tight changeover, or late-night clean-up spilling into the next day),
    or fine.
    """
    from toolkit.diary.models import Showing

    from .models import HireDate

    cfg = get_hire_settings()
    enquiries = list(enquiries)
    targets = []
    for e in enquiries:
        ds = e.dates()
        use = [d for d in ds if d.accepted] or ds
        targets.append((e, use))
    starts = [
        timezone.localtime(d.start).date() for _, use in targets for d in use
    ]
    if not starts:
        return {}
    lo = timezone.make_aware(
        datetime.datetime.combine(
            min(starts) - datetime.timedelta(days=window), datetime.time.min
        )
    )
    hi = timezone.make_aware(
        datetime.datetime.combine(
            max(starts) + datetime.timedelta(days=window + 1),
            datetime.time.min,
        )
    )
    showings = list(
        Showing.objects.filter(start__gte=lo, start__lt=hi, cancelled=False)
        .exclude(event__programming_status="rejected")
        .select_related("event", "event__hire_enquiry")
        .prefetch_related("room_bookings__room")
    )
    pending = list(
        HireDate.objects.filter(
            start__gte=lo,
            start__lt=hi,
            enquiry__status__in=(E.ACKNOWLEDGED, E.TO_DISCUSS, E.MAYBE),
            enquiry__event__isnull=True,
        )
        .select_related("enquiry")
        .prefetch_related("enquiry__rooms_requested")
    )

    items = []
    for sh in showings:
        bookings = list(sh.room_bookings.all())
        start, end = sh.start, sh.end_time
        for rb in bookings:
            start = min(start, rb.start)
            if rb.end:
                end = max(end, rb.end)
        ev = sh.event
        hire = getattr(ev, "hire_enquiry", None)
        status = ev.get_programming_status_display()
        items.append(
            {
                "kind": "hire" if ev.outside_hire else "event",
                "title": ev.name,
                "start": sh.start,
                "from": start,
                "to": end,
                "rooms": ", ".join(
                    dict.fromkeys(rb.room.name for rb in bookings)
                ),
                "room_ids": {rb.room_id for rb in bookings},
                "status": "" if ev.programming_status == "active" else status,
                "event_id": ev.pk,
                "enquiry_pk": hire.pk if hire else None,
                "confirmed": sh.confirmed,
            }
        )
    for hd in pending:
        rooms = list(hd.enquiry.rooms_requested.all())
        items.append(
            {
                "kind": "enquiry",
                "title": hd.enquiry.title,
                "start": hd.start,
                "from": hd.get_in,
                "to": hd.get_out,
                "rooms": ", ".join(r.name for r in rooms),
                "room_ids": {r.pk for r in rooms},
                "status": "Hire enquiry, undecided",
                "event_id": None,
                "enquiry_pk": hd.enquiry_id,
                "confirmed": False,
            }
        )
    for it in items:
        it["day"] = timezone.localtime(it["start"]).date()
        it["cleanup_to"] = _cleanup_end(it["from"], it["to"], cfg)
    items.sort(key=lambda it: it["start"])

    out = {}
    for e, use in targets:
        hire_rooms = {r.pk for r in e.rooms_requested.all()}
        out[e.pk] = [
            _date_summary(e, d, items, hire_rooms, cfg, window) for d in use
        ]
    return out


def _date_summary(e, d, items, hire_rooms, cfg, window):
    day = timezone.localtime(d.start).date()
    days = {}
    counts = {CLASH: 0, CHECK: 0, "same_day": 0}
    for it in items:
        if it["event_id"] and it["event_id"] == e.event_id:
            continue
        if it["enquiry_pk"] == e.pk:
            continue
        delta = (it["day"] - day).days
        if abs(delta) > window:
            continue
        row = dict(it)
        row["tier"], row["reason"] = _classify(it, d, hire_rooms, cfg)
        if row["tier"]:
            counts[row["tier"]] += 1
        if delta == 0:
            counts["same_day"] += 1
        days.setdefault(it["day"], []).append(row)
    days.setdefault(day, [])
    return {
        "hire_date": d,
        "day": day,
        "days": [
            {
                "date": k,
                "target": k == day,
                "offset": (k - day).days,
                "items": v,
            }
            for k, v in sorted(days.items())
        ],
        "same_day": counts["same_day"],
        "clashes": counts[CLASH],
        "checks": counts[CHECK],
        "week": sum(len(v) for v in days.values()),
    }


# --- Readiness ---------------------------------------------------------------


def readiness(cfg=None):
    """What must be true before the form can honestly take enquiries.

    Returns (blockers, warnings), each a list of plain sentences. Blockers
    close the public form: with nobody to warn, or nothing to choose, the
    promise of an answer can't be kept.
    """
    from .models import HireType

    cfg = cfg or get_hire_settings()
    blockers, warnings = [], []
    if not cfg.notification_address_list():
        blockers.append(
            "No valid notification address is set, so nobody would be "
            "warned before an enquiry is auto-declined. Add one in Hire "
            "settings."
        )
    if not HireType.objects.filter(active=True).exists():
        blockers.append(
            "There are no active hire types, so hirers would have nothing "
            "to choose. Add them under Hire types."
        )
    if not ProgrammingMeeting.objects.filter(
        date__gte=timezone.localdate(), cancelled=False
    ).exists():
        warnings.append(
            "No future programming meeting is entered, so enquiries run on "
            "the fallback clock."
        )
    if not _keyholder_role():
        warnings.append(
            "No rota role is marked keyholder-only, so accepted hires get "
            "no keyholder slot even though hirers are promised one."
        )
    if not cfg.privacy_contact.strip():
        warnings.append(
            "No privacy contact is set, so the privacy notice tells hirers "
            "to write to 'the venue'."
        )
    return blockers, warnings


# --- Meeting-aware reply clock -------------------------------------------


def has_space(meeting, exclude=None):
    """Whether a meeting has a hire slot free (ignoring enquiry `exclude`)."""
    used = meeting.agenda().exclude(pk=exclude).count()
    return used < meeting.slots()


def next_meeting_for(submitted_at, cfg=None, exclude=None, after=None):
    """The first meeting with a free hire slot, far enough ahead to prepare.

    Full meetings are skipped, so the date a hirer is given is the real one.
    `exclude` is the enquiry being placed, so it doesn't count against
    itself; `after` forces a meeting later than that date.
    """
    cfg = cfg or get_hire_settings()
    earliest = timezone.localtime(submitted_at).date() + datetime.timedelta(
        days=cfg.min_notice_days_before_meeting
    )
    # Re-homing an old enquiry must never pick a meeting that has happened.
    earliest = max(earliest, timezone.localdate())
    if after:
        earliest = max(earliest, after + datetime.timedelta(days=1))
    for meeting in ProgrammingMeeting.objects.filter(
        date__gte=earliest, cancelled=False
    ).order_by("date"):
        if has_space(meeting, exclude):
            return meeting
    return None


def full_until(cfg=None):
    """(closed, reopens_on) for the public form.

    Closed when meetings are entered but none within the horizon has a free
    slot. `reopens_on` is when the first meeting with space comes within
    the horizon, or None if no meeting with space is entered at all. With
    no meetings entered, the form stays open on the fallback clock.
    """
    cfg = cfg or get_hire_settings()
    if not cfg.full_horizon_weeks:
        return False, None
    today = timezone.localdate()
    horizon = datetime.timedelta(weeks=cfg.full_horizon_weeks)
    future = ProgrammingMeeting.objects.filter(
        date__gte=today, cancelled=False
    ).order_by("date")
    if not future.exists():
        return False, None
    for meeting in future:
        if has_space(meeting):
            if meeting.date <= today + horizon:
                return False, None
            return True, meeting.date - horizon
    return True, None


def assign_meeting(enquiry, meeting=None, cfg=None):
    """Assign (or reassign) a meeting and derive the deadline from it.

    The deadline is always derived from the meeting, never stored on its own,
    so moving a meeting cannot leave a stale promise. Clears the last-call
    marker because the new deadline is a new promise.
    """
    cfg = cfg or get_hire_settings()
    meeting = meeting or next_meeting_for(
        enquiry.submitted_at, cfg, exclude=enquiry.pk
    )
    enquiry.meeting = meeting
    if meeting:
        enquiry.reply_deadline = meeting.date + datetime.timedelta(
            days=cfg.reply_grace_days
        )
    else:
        base = max(
            timezone.localtime(enquiry.submitted_at).date(),
            timezone.localdate(),
        )
        enquiry.reply_deadline = base + datetime.timedelta(
            days=cfg.fallback_reply_days
        )
    enquiry.warning_sent_at = None
    enquiry.digest_sent_at = None
    return enquiry


def _require_state(enquiry, allowed, what):
    """Refuse a decision on an enquiry that has moved on (stale tab, etc.)."""
    if enquiry.status not in allowed:
        raise ValueError(
            f"Can't {what}: this enquiry is now "
            f"'{enquiry.get_status_display()}'. Reload the page to see "
            "what has happened."
        )


_DECIDABLE = (E.ACKNOWLEDGED, E.TO_DISCUSS)


def _set_status(enquiry, status):
    enquiry.status = status
    enquiry.status_changed_at = timezone.now()


# --- Intake ---------------------------------------------------------------


def submit_enquiry(enquiry, hire_dates):
    """Persist a new enquiry with its dates, assign a meeting, acknowledge."""
    cfg = get_hire_settings()
    with transaction.atomic():
        enquiry.status = E.SUBMITTED
        enquiry.submitted_at = timezone.now()
        if cfg.booking_window_end and any(
            timezone.localtime(d.start).date() > cfg.booking_window_end
            for d in hire_dates
        ):
            enquiry.beyond_booking_window = True
        assign_meeting(enquiry, cfg=cfg)
        _set_status(enquiry, E.ACKNOWLEDGED)
        enquiry.save()
        for d in hire_dates:
            d.enquiry = enquiry
            d.save()
    try:
        send_acknowledgement(enquiry)
    except Exception:
        # The enquiry is safely stored; a failed ack must not lose it.
        logger.exception("Hire acknowledgement failed for %s", enquiry.pk)
    return enquiry


def send_acknowledgement(enquiry):
    if enquiry.meeting:
        timing = (
            f"It will be discussed at our meeting on "
            f"{enquiry.meeting.date:%-d %B %Y}, and you will hear from us "
            f"by {enquiry.reply_deadline:%-d %B %Y}."
        )
    else:
        timing = (
            f"You will hear from us by {enquiry.reply_deadline:%-d %B %Y}."
        )
    window_note = ""
    if enquiry.beyond_booking_window:
        window_note = (
            "Your dates are further ahead than we are currently booking, so "
            "they will be considered at season planning.\n\n"
        )
    fee_line = ""
    if enquiry.hire_type:
        text = indicative_fee_text(
            enquiry.hire_type, enquiry.tier, enquiry.dates()[:1]
        )
        if text:
            fee_line = f"The fee: {text}\n\n"
    rate_note = ""
    if enquiry.tier_requested == E.TIER_COMMUNITY:
        rate_note = (
            "You asked for the community rate. The volunteers will read "
            "what you told us when they discuss your enquiry, and if we "
            "can't offer it we'll say so before anything is booked.\n\n"
        )
    send_to_hirer(
        enquiry,
        "acknowledgement",
        HIRER_EMAIL_SOURCES["acknowledgement"],
        timing=timing,
        window_note=window_note,
        indicative_fee=fee_line,
        rate_note=rate_note,
    )


# --- Decisions ------------------------------------------------------------


def _approved_tech_text():
    techs = ApprovedTech.objects.filter(active=True, share_with_hirers=True)
    if not techs:
        return ""
    lines = [
        f"- {t.name}"
        + (f", {t.rate_text}" if t.rate_text else "")
        + (f", {t.email}" if t.email else "")
        + (f", {t.phone}" if t.phone else "")
        for t in techs
    ]
    return (
        "If you need a sound tech, these freelancers know our gear. You "
        "book and pay them directly:\n" + "\n".join(lines) + "\n\n"
    )


def accept(
    enquiry,
    user,
    coordinator=None,
    accepted_date_ids=None,
    tier_agreed="",
    fee=None,
    door_fee=None,
    email=None,
):
    """Accept: create a proposed Event linked back, email the hirer.

    `email` is how the hirer hears: None for the standard wording, a
    (subject, body) a person has edited, or SELF if they'll write it.
    """
    from toolkit.diary.models import (
        Event,
        RoomBooking,
        Showing,
    )

    if enquiry.status not in (E.TO_DISCUSS, E.ACKNOWLEDGED, E.MAYBE):
        raise ValueError(f"Cannot accept an enquiry that is {enquiry.status}")
    if enquiry.event_id:
        raise ValueError("This enquiry already has an event")
    with transaction.atomic():
        dates = enquiry.dates()
        chosen = [
            d
            for d in dates
            if accepted_date_ids is None or d.pk in accepted_date_ids
        ] or dates[:1]
        for d in dates:
            d.accepted = d in chosen
            d.save(update_fields=["accepted"])
        if tier_agreed:
            enquiry.tier_agreed = tier_agreed
        enquiry.coordinator = coordinator or user
        if fee is None:
            # What the hirer is charged, never the internal net estimate.
            fee = enquiry.charge_gbp()
        enquiry.agreed_fee_gbp = fee
        _ensure_details_token(enquiry)
        if enquiry.door_staff_required():
            enquiry.door_staff_fee_gbp = (
                door_fee
                if door_fee is not None
                else get_hire_settings().door_staff_fee_gbp
            )
        else:
            enquiry.door_staff_fee_gbp = None
        enquiry.estimated_income_gbp = enquiry.estimate_gbp()

        event = Event.objects.create(
            name=enquiry.title,
            outside_hire=True,
            hire_name=enquiry.contact_organisation or enquiry.contact_name,
            programming_status="proposed",
            cost_type=Event.COST_TYPE_VENUE_HIRE,
            cost_flat_fee_gbp=fee,
            programming_notes=(
                f"From hire enquiry #{enquiry.pk}. {enquiry.description}"
            )[:4000],
        )
        rooms = list(enquiry.rooms_requested.all())
        for d in chosen:
            showing = Showing.objects.create(
                event=event,
                start=d.start,
                booked_by=(user.get_full_name() or user.username)[:64],
                confirmed=False,
            )
            for room in rooms:
                RoomBooking.objects.create(
                    showing=showing, room=room, start=d.get_in, end=d.get_out
                )
        enquiry.event = event
        _set_status(enquiry, E.ACCEPTED)
        enquiry.save()
        ensure_rota_for_hire(enquiry)
    _tell_hirer(enquiry, "accepted", user, email, **_accepted_vars(enquiry))
    return event


def _ensure_details_token(enquiry):
    if not enquiry.details_token:
        enquiry.details_token = secrets.token_urlsafe(32)
        enquiry.details_requested_at = timezone.now()


def _accepted_vars(enquiry, coordinator=None):
    return dict(
        coordinator_line=_coordinator_line(enquiry, coordinator),
        details_url=details_url(enquiry),
        techs=_approved_tech_text(),
    )


# A person will write to the hirer themselves; the system sends nothing.
SELF = "self"

_DECISION_NAMES = {
    "accepted": "Accepted",
    "maybe": "Marked maybe",
    "declined": "Declined",
}


def _tell_hirer(enquiry, key, user, email, **extra):
    if email == SELF:
        who = (user.get_full_name() or user.username) if user else "someone"
        enquiry.internal_notes = (
            f"{enquiry.internal_notes}\n[{timezone.localdate()}] "
            f"{_DECISION_NAMES[key]}. Not emailed by the system: {who} is "
            "getting in touch with the hirer."
        ).strip()
        enquiry.save(update_fields=["internal_notes"])
        return
    override = email if isinstance(email, tuple) else None
    send_to_hirer(
        enquiry, key, HIRER_EMAIL_SOURCES[key], override=override, **extra
    )


def draft_decision_emails(enquiry, user):
    """Editable drafts of the accept, maybe and decline emails.

    Filled in as they would be sent, so the person deciding reads the
    actual words before anything goes. Creates the details link early (it
    only works once the enquiry is accepted) so the draft can include it.
    """
    if enquiry.status not in _DECIDABLE + (E.MAYBE,):
        return {}
    if not enquiry.details_token:
        _ensure_details_token(enquiry)
        enquiry.save(update_fields=["details_token", "details_requested_at"])
    cfg = get_hire_settings()
    callout_by = timezone.localdate() + datetime.timedelta(
        days=cfg.callout_days
    )
    return {
        "accepted": render_hirer_email(
            enquiry,
            "accepted",
            **_accepted_vars(enquiry, enquiry.coordinator or user),
        ),
        "maybe": render_hirer_email(
            enquiry, "maybe", callout_deadline=f"{callout_by:%-d %B %Y}"
        ),
        "declined": render_hirer_email(enquiry, "declined"),
    }


# --- Rota: make the promises to hirers visible to volunteers ---------------

RULES_NOTE = (
    "Outside hire. The keyholder is guaranteed to the hirer; every other "
    "role is best-effort."
)
OFFER_PREFIX = "Hirer offers volunteers: "


def _keyholder_role():
    from toolkit.diary.models import Role

    return Role.objects.filter(keyholder_only=True).order_by("id").first()


def ensure_rota_for_hire(enquiry):
    """Give each showing a keyholder slot and a rota note about the hire.

    "A keyholder is guaranteed" is a promise to the hirer, so the slot must
    exist for a volunteer to sign up to. Returns False if the venue has no
    keyholder role configured (the queue then warns).
    """
    from toolkit.diary.models import RotaEntry

    if not enquiry.event:
        return False
    role = _keyholder_role()
    for showing in enquiry.event.showings.all():
        if (
            role
            and not RotaEntry.objects.filter(
                showing=showing, role=role
            ).exists()
        ):
            RotaEntry.objects.create(showing=showing, role=role, rank=1)
        lines = [
            ln
            for ln in showing.rota_notes.splitlines()
            if ln.strip() and not ln.startswith(OFFER_PREFIX)
        ]
        if RULES_NOTE not in lines:
            lines.insert(0, RULES_NOTE)
        if enquiry.offers_to_volunteers.strip():
            lines.append(
                OFFER_PREFIX + " ".join(enquiry.offers_to_volunteers.split())
            )
        showing.rota_notes = "\n".join(lines)[:4096]
        showing.save(update_fields=["rota_notes"])
    return role is not None


def unfilled_keyholder_slots(enquiry):
    """Keyholder slots with nobody signed up, or None if there is no event."""
    from toolkit.diary.models import RotaEntry

    if not enquiry.event:
        return None
    role = _keyholder_role()
    if not role:
        return None
    return RotaEntry.objects.filter(
        showing__event=enquiry.event,
        role=role,
        volunteer__isnull=True,
        name="",
    ).count()


def details_url(enquiry):
    if not enquiry.details_token:
        return ""
    return abs_url(
        reverse("hires:details", kwargs={"token": enquiry.details_token})
    )


def complete_details(enquiry, cleaned, new_times):
    """Apply the second-stage answers to the enquiry, its dates and event."""
    from toolkit.diary.models import RoomBooking

    with transaction.atomic():
        enquiry.rooms_requested.set(cleaned["rooms_requested"])
        enquiry.expected_attendance = cleaned["expected_attendance"]
        enquiry.media_url = cleaned["media_url"]
        enquiry.sound_tech = cleaned["sound_tech"]
        enquiry.sound_tech_name = cleaned["sound_tech_name"]
        enquiry.offers_to_volunteers = cleaned["offers_to_volunteers"]
        enquiry.details_completed_at = timezone.now()
        enquiry.save()
        rooms = list(enquiry.rooms_requested.all())
        for d in enquiry.dates():
            if d.pk in new_times:
                d.start, d.end = new_times[d.pk]
                d.save(update_fields=["start", "end"])
        if enquiry.event:
            showings = list(enquiry.event.showings.order_by("start"))
            chosen = [d for d in enquiry.dates() if d.accepted]
            for showing, d in zip(showings, chosen):
                showing.start = d.start
                showing.save()
                showing.room_bookings.all().delete()
                for room in rooms:
                    RoomBooking.objects.create(
                        showing=showing,
                        room=room,
                        start=d.get_in,
                        end=d.get_out,
                    )
        ensure_rota_for_hire(enquiry)
    notify_internal(
        "details_received",
        "Hire enquiry: details received",
        title=enquiry.title,
        name=enquiry.contact_organisation or enquiry.contact_name,
        enquiry_url=abs_url(
            reverse("hires:detail", kwargs={"pk": enquiry.pk})
        ),
    )


def mark_details_received(enquiry, note):
    """The hirer gave the details another way (e.g. by email)."""
    if not note.strip():
        raise ValueError("Add a one-line note of how you got them")
    enquiry.details_completed_at = timezone.now()
    enquiry.internal_notes = (
        f"{enquiry.internal_notes}\n[{timezone.localdate()}] Details taken "
        f"outside the form: {note.strip()}"
    ).strip()
    enquiry.save()


def _coordinator_line(enquiry, user=None):
    user = user or enquiry.coordinator
    if not user:
        return ""
    return f"{user.get_full_name() or user.username} will be your contact."


def mark_maybe(enquiry, user, what_we_need, cfg=None, email=None):
    cfg = cfg or get_hire_settings()
    _require_state(enquiry, _DECIDABLE, "mark this as maybe")
    if not what_we_need.strip():
        raise ValueError("Say what support is needed")
    enquiry.callout_what_we_need = what_we_need.strip()
    enquiry.callout_deadline = timezone.localdate() + datetime.timedelta(
        days=cfg.callout_days
    )
    enquiry.callout_warning_sent_at = None
    _set_status(enquiry, E.MAYBE)
    enquiry.save()
    _tell_hirer(
        enquiry,
        "maybe",
        user,
        email,
        callout_deadline=f"{enquiry.callout_deadline:%-d %B %Y}",
    )
    notify_internal(
        "callout",
        "Hire enquiry: maybe callout",
        title=enquiry.title,
        organisation=enquiry.contact_organisation or enquiry.contact_name,
        dates=describe_dates(enquiry),
        what_we_need=enquiry.callout_what_we_need,
        offers=enquiry.offers_to_volunteers or "nothing specified",
        callout_deadline=f"{enquiry.callout_deadline:%-d %B %Y}",
        enquiry_url=abs_url(
            reverse("hires:detail", kwargs={"pk": enquiry.pk})
        ),
    )


def decline(enquiry, user, email=None):
    _require_state(enquiry, _DECIDABLE + (E.MAYBE,), "decline")
    _set_status(enquiry, E.DECLINED)
    enquiry.save()
    _tell_hirer(enquiry, "declined", user, email)


# --- Champions: a programmer takes an enquiry on by hand -------------------


def champion(enquiry, user):
    """A programmer takes this on: it leaves the meeting queue.

    Nothing automatic goes to the hirer while it is championed. If the
    reply date passes, the champion is nudged instead (see run_clock).
    """
    _require_state(enquiry, E.CLOCK_STATES, "take this on")
    if enquiry.coordinator_id and enquiry.coordinator_id != user.pk:
        raise ValueError(
            f"{enquiry.coordinator.get_full_name() or enquiry.coordinator}"
            " has already taken this on"
        )
    enquiry.coordinator = user
    enquiry.champion_nudged_at = None
    enquiry.internal_notes = (
        f"{enquiry.internal_notes}\n[{timezone.localdate()}] Taken on by "
        f"{user.get_full_name() or user.username}."
    ).strip()
    enquiry.save()


def release(enquiry, user):
    """Hand a championed enquiry back to the meeting queue."""
    _require_state(enquiry, E.CLOCK_STATES, "hand this back")
    enquiry.coordinator = None
    enquiry.internal_notes = (
        f"{enquiry.internal_notes}\n[{timezone.localdate()}] Handed back "
        f"to the meeting by {user.get_full_name() or user.username}."
    ).strip()
    promised = enquiry.reply_deadline
    meeting = enquiry.meeting
    keep = (
        meeting
        and not meeting.cancelled
        and meeting.date >= timezone.localdate()
        and has_space(meeting, exclude=enquiry.pk)
    )
    if not keep:
        assign_meeting(enquiry)
    enquiry.save()
    _tell_if_slipped(enquiry, promised)


def withdraw(enquiry):
    _require_state(enquiry, E.OPEN_STATES, "mark this as withdrawn")
    _set_status(enquiry, E.WITHDRAWN)
    enquiry.save()


def replied_outside_toolkit(enquiry, note):
    """Postpone (not stop) the clock: move to the next meeting."""
    _require_state(enquiry, E.CLOCK_STATES, "postpone the clock")
    if not note.strip():
        raise ValueError("Add a one-line note of what was said")
    enquiry.replied_outside_toolkit_at = timezone.now()
    enquiry.internal_notes = (
        f"{enquiry.internal_notes}\n[{timezone.localdate()}] Replied "
        f"outside the toolkit: {note.strip()}"
    ).strip()
    nxt = next_meeting_for(
        enquiry.submitted_at,
        exclude=enquiry.pk,
        after=enquiry.meeting.date if enquiry.meeting else None,
    )
    if nxt:
        assign_meeting(enquiry, nxt)
    else:
        # No later meeting entered: postpone on the fallback clock rather
        # than re-selecting the current meeting (which would not move it).
        cfg = get_hire_settings()
        enquiry.meeting = None
        enquiry.reply_deadline = timezone.localdate() + datetime.timedelta(
            days=cfg.fallback_reply_days
        )
        enquiry.warning_sent_at = None
        enquiry.digest_sent_at = None
    enquiry.save()


def volunteer_to_coordinate(enquiry, user):
    if enquiry.status != E.MAYBE:
        raise ValueError("This enquiry is not looking for a coordinator")
    return accept(enquiry, user, coordinator=user)


# --- Terms agreement ------------------------------------------------------


def send_confirmation(enquiry):
    """Email the terms with a one-click agreement link (v1: no login)."""
    if not enquiry.event:
        raise ValueError("No event to confirm")
    event = enquiry.event
    if enquiry.status not in (E.ACCEPTED, E.AWAITING_AGREEMENT):
        raise ValueError(
            "Confirmations can only be sent for accepted hires that are not "
            "yet booked"
        )
    if not enquiry.details_completed_at:
        raise ValueError(
            "The hirer hasn't sent the further details yet. Wait for them, "
            "or use 'Details received another way'."
        )
    if not event.terms_satisfied():
        raise ValueError("The event's terms are not yet satisfied")
    if event.cost_type != event.COST_TYPE_VENUE_HIRE:
        raise ValueError("The event's cost type must be 'Venue hire'")
    previous = (
        enquiry.status,
        enquiry.status_changed_at,
        enquiry.agreement_token,
        enquiry.confirmation_sent_at,
        enquiry.terms_agreed_at,
    )
    enquiry.agreement_token = secrets.token_urlsafe(32)
    enquiry.confirmation_sent_at = timezone.now()
    enquiry.terms_agreed_at = None
    _set_status(enquiry, E.AWAITING_AGREEMENT)
    enquiry.save()
    try:
        send_to_hirer(
            enquiry,
            "booking_confirmation",
            HIRER_EMAIL_SOURCES["booking_confirmation"],
            terms=terms_text(enquiry),
            fee=fee_text(enquiry),
            agreement_url=abs_url(
                reverse(
                    "hires:agree", kwargs={"token": enquiry.agreement_token}
                )
            ),
        )
    except Exception as exc:
        (
            enquiry.status,
            enquiry.status_changed_at,
            enquiry.agreement_token,
            enquiry.confirmation_sent_at,
            enquiry.terms_agreed_at,
        ) = previous
        enquiry.save()
        logger.exception("Booking confirmation failed for %s", enquiry.pk)
        raise ValueError(
            "The confirmation email could not be sent. Nothing has changed; "
            "please try again."
        ) from exc


def terms_text(enquiry):
    event = enquiry.event
    return (
        event.terms or ""
    ).strip() or "No further terms beyond the fee, dates and access times shown."


def fee_text(enquiry):
    fee = enquiry.agreed_fee_gbp
    if fee is None:
        return "to be confirmed"
    text = f"£{fee:.2f} (excluding VAT where it applies)"
    if enquiry.tier == E.TIER_COMMUNITY:
        text += (
            "\nRate: community rate, a reduced rate the volunteers have "
            "agreed to offer."
        )
    elif enquiry.tier_requested == E.TIER_COMMUNITY:
        text += (
            "\nRate: full rate. We weren't able to offer the community "
            "rate for this hire."
        )
    else:
        text += "\nRate: full rate."
    if enquiry.door_staff_required():
        door = enquiry.door_staff_fee_gbp
        text += "\nPlus door staff, charged to you in addition: " + (
            f"£{door:.2f}" if door is not None else "amount to be confirmed"
        )
    return text


def agreement_snapshot(enquiry):
    return (
        f"Hire: {enquiry.title} for "
        f"{enquiry.contact_organisation or 'an individual hirer'}\n"
        f"Fee: {fee_text(enquiry)}\n"
        f"Dates:\n{describe_dates(enquiry, accepted_only=True)}\n\n"
        f"Terms:\n{terms_text(enquiry)}\n\n"
        "Acknowledged:\n"
        + "\n".join(f"- {a}" for a in enquiry.acknowledgements)
    )


def record_agreement(enquiry, ip=None, acknowledged=None):
    if enquiry.status != E.AWAITING_AGREEMENT:
        raise ValueError("This enquiry is not awaiting agreement")
    enquiry.terms_agreed_at = timezone.now()
    if acknowledged is not None:
        enquiry.acknowledgements = list(acknowledged)
    enquiry.terms_agreed_snapshot = agreement_snapshot(enquiry)
    enquiry.terms_agreed_ip = ip or None
    _set_status(enquiry, E.BOOKED)
    enquiry.save()
    ev = enquiry.event
    if ev and ev.programming_status != "active":
        ev.programming_status = "active"
        ev.save()
    try:
        send_to_hirer(enquiry, "booked", HIRER_EMAIL_SOURCES["booked"])
    except Exception:
        logger.exception("Booked email failed for %s", enquiry.pk)


# --- The clock (run daily by the scheduler) -------------------------------


def _send_digests(live, today, cfg, dry_run):
    """Pre-meeting digest, one per meeting. Returns how many were sent."""
    sent = 0
    digest_from = today + datetime.timedelta(
        days=cfg.digest_days_before_meeting
    )
    for meeting in ProgrammingMeeting.objects.filter(
        cancelled=False, date__gte=today, date__lte=digest_from
    ):
        pending = list(
            live.filter(meeting=meeting, digest_sent_at__isnull=True)
        )
        if not pending or dry_run:
            continue
        if notify_internal(
            "digest",
            "Hire enquiry: pre-meeting digest",
            meeting_date=f"{meeting.date:%-d %B %Y}",
            count=len(pending),
            lines=_digest_lines(pending),
        ):
            now = timezone.now()
            E.objects.filter(pk__in=[e.pk for e in pending]).update(
                digest_sent_at=now
            )
            sent += 1
    return sent


def _nudge_champions(claimed, today, dry_run):
    """Taken on and past the reply date: remind the champion and the list.

    Once only, and never anything to the hirer: a person is handling it.
    """
    nudged = 0
    for enq in claimed.filter(
        reply_deadline__lte=today, champion_nudged_at__isnull=True
    ):
        if dry_run:
            nudged += 1
            continue
        champ = enq.coordinator
        if notify_internal(
            "champion_nudge",
            "Hire enquiry: champion nudge",
            extra_to=[champ.email],
            title=enq.title,
            champion=champ.get_full_name() or champ.username,
            reply_by=f"{enq.reply_deadline:%-d %B %Y}",
            enquiry_url=abs_url(
                reverse("hires:detail", kwargs={"pk": enq.pk})
            ),
        ):
            enq.champion_nudged_at = timezone.now()
            enq.save(update_fields=["champion_nudged_at"])
            nudged += 1
    return nudged


def run_clock(today=None, cfg=None, dry_run=False):
    """Daily pass: digest, last call, auto-decline, callout timeouts.

    Returns a dict of counts. Does nothing at all while the feature flag is
    off (clocks are paused, not cancelled).
    """
    cfg = cfg or get_hire_settings()
    today = today or timezone.localdate()
    out = {
        "digests": 0,
        "last_calls": 0,
        "auto_declined": 0,
        "callout_warnings": 0,
        "callout_declined": 0,
        "champion_nudges": 0,
        "paused": False,
    }
    if not hires_enabled():
        out["paused"] = True
        return out

    # Championed enquiries are a person's job, not the clock's: they are
    # left out of every automatic step below and only get a nudge.
    claimed = E.objects.filter(
        status__in=E.CLOCK_STATES, coordinator__isnull=False
    )
    live = E.objects.filter(
        status__in=E.CLOCK_STATES, coordinator__isnull=True
    )

    # Enquiries stranded with no meeting get one if one now exists.
    for enq in live.filter(meeting__isnull=True):
        nxt = next_meeting_for(enq.submitted_at, cfg)
        if nxt and not dry_run:
            old = enq.reply_deadline
            assign_meeting(enq, nxt, cfg)
            enq.save()
            _tell_if_slipped(enq, old)

    out["digests"] = _send_digests(live, today, cfg, dry_run)

    # No meetings at all: nag, once a month, on the first.
    if today.day == 1 and not dry_run:
        orphans = list(live.filter(meeting__isnull=True))
        if (
            orphans
            and not ProgrammingMeeting.objects.filter(
                date__gte=today, cancelled=False
            ).exists()
        ):
            notify_internal(
                "no_meetings",
                "Hire enquiry: no meeting dates",
                lines=_digest_lines(orphans),
                meetings_url=abs_url(reverse("hires:meetings")),
            )

    # Last call.
    warn_by = today + datetime.timedelta(days=cfg.warning_days)
    stale = list(
        live.filter(
            reply_deadline__lte=warn_by,
            reply_deadline__gt=today,
            warning_sent_at__isnull=True,
        )
    )
    if stale and not dry_run:
        if notify_internal(
            "last_call",
            "Hire enquiry: last call",
            lines=_digest_lines(stale),
        ):
            E.objects.filter(pk__in=[e.pk for e in stale]).update(
                warning_sent_at=timezone.now()
            )
            out["last_calls"] = len(stale)

    out["champion_nudges"] = _nudge_champions(claimed, today, dry_run)

    # Auto-decline at the deadline.
    for enq in live.filter(reply_deadline__lte=today):
        if dry_run:
            out["auto_declined"] += 1
            continue
        _set_status(enq, E.DECLINED_CAPACITY)
        enq.save()
        try:
            send_to_hirer(
                enq,
                "declined_capacity",
                HIRER_EMAIL_SOURCES["declined_capacity"],
            )
        except Exception:
            logger.exception("Capacity decline email failed %s", enq.pk)
        out["auto_declined"] += 1

    # Maybe callouts: last call then timeout.
    maybes = E.objects.filter(status=E.MAYBE)
    for enq in maybes:
        if not enq.callout_deadline or dry_run:
            continue
        if enq.callout_deadline <= today:
            _set_status(enq, E.DECLINED_NO_SUPPORT)
            enq.save()
            try:
                send_to_hirer(
                    enq,
                    "declined_no_support",
                    HIRER_EMAIL_SOURCES["declined_no_support"],
                )
            except Exception:
                logger.exception("No-support email failed %s", enq.pk)
            out["callout_declined"] += 1
        elif (
            enq.callout_deadline <= warn_by and not enq.callout_warning_sent_at
        ):
            if notify_internal(
                "last_call",
                "Hire enquiry: callout last call",
                lines=_digest_lines([enq]),
            ):
                enq.callout_warning_sent_at = timezone.now()
                enq.save(update_fields=["callout_warning_sent_at"])
                out["callout_warnings"] += 1
    return out


def _digest_lines(enquiries):
    lines = []
    for e in enquiries:
        first = e.dates()[:1]
        when = _fmt_dt(first[0].start) if first else "no date"
        by = (
            e.callout_deadline
            if e.status == E.MAYBE
            else e.reply_deadline or e.callout_deadline
        )
        lines.append(
            f"- {e.title} ({e.contact_organisation or e.contact_name}), "
            f"{e.hire_type or 'unspecified'}, {when}, about "
            f"£{e.estimate_gbp():.0f}"
            + (
                f" (asks for the community rate: subsidy about "
                f"£{e.subsidy_gbp():.0f})"
                if e.tier == E.TIER_COMMUNITY
                else ""
            )
            + f"; auto-declines {by:%-d %b}"
            if by
            else f"- {e.title} ({e.contact_organisation or e.contact_name})"
        )
    return "\n".join(lines)


def _tell_if_slipped(enquiry, promised):
    """Email the hirer when their reply date moved later than we told them."""
    if (
        promised
        and enquiry.reply_deadline
        and enquiry.reply_deadline > promised
    ):
        try:
            send_to_hirer(
                enquiry, "meeting_moved", HIRER_EMAIL_SOURCES["meeting_moved"]
            )
        except Exception:
            logger.exception("Meeting-moved email failed %s", enquiry.pk)


def meeting_cancelled(meeting):
    """Move a cancelled meeting's enquiries on; tell hirers if it slips."""
    meeting.cancelled = True
    meeting.save()
    for enq in meeting.enquiries.filter(status__in=E.CLOCK_STATES):
        old = enq.reply_deadline
        assign_meeting(enq, next_meeting_for(enq.submitted_at))
        enq.digest_sent_at = None
        enq.save()
        _tell_if_slipped(enq, old)


# --- Message history and retry ---------------------------------------------


def _addresses(row):
    return [a.strip().lower() for a in row.recipients.split(",")]


def hire_email_rows(since=None):
    """Hire-triggered SentEmailLog rows, newest first (one query)."""
    from toolkit.audit.models import SentEmailLog

    rows = SentEmailLog.objects.filter(
        trigger_source__startswith="Hire enquiry:"
    )
    if since:
        rows = rows.filter(sent_at__gte=since)
    return list(rows.order_by("-sent_at"))


def messages_for(enquiry, rows):
    """Rows sent to this enquiry's hirer since it was submitted.

    Matches the exact address (the log stores recipients comma-joined, so a
    plain substring match would confuse ba@x.org with a@x.org). Two
    enquiries from one shared inbox will each see the other's later mail;
    the panel says so rather than guessing.
    """
    addr = enquiry.contact_email.lower()
    start = enquiry.submitted_at - datetime.timedelta(minutes=1)
    return [r for r in rows if r.sent_at >= start and addr in _addresses(r)]


def email_problems(messages):
    """Failed hirer emails not since followed by a success of the same kind.

    Returns the newest failed row for each affected kind of email.
    """
    latest_ok = {}
    for r in messages:  # newest first
        if r.success and r.trigger_source not in latest_ok:
            latest_ok[r.trigger_source] = r.sent_at
    seen, problems = set(), []
    for r in messages:
        if r.success or r.trigger_source in seen:
            continue
        seen.add(r.trigger_source)
        ok_at = latest_ok.get(r.trigger_source)
        if ok_at is None or ok_at < r.sent_at:
            problems.append(r)
    return problems


def label_for_source(source):
    key = _KEY_FOR_SOURCE.get(source)
    if key:
        return defaults.EMAIL_LABELS[key][0]
    return source.removeprefix("Hire enquiry: ")


def resend(enquiry, key):
    """Re-send one kind of hirer email that failed earlier."""
    source = HIRER_EMAIL_SOURCES.get(key)
    if not source:
        raise ValueError("Unknown email")
    if key == "booking_confirmation":
        raise ValueError(
            "Use 'Send booking confirmation' to re-send the terms."
        )
    if key == "acknowledgement":
        send_acknowledgement(enquiry)
    elif key == "accepted":
        send_to_hirer(
            enquiry,
            key,
            source,
            coordinator_line=_coordinator_line(enquiry),
            details_url=details_url(enquiry),
            techs=_approved_tech_text(),
        )
    else:
        send_to_hirer(enquiry, key, source)


# --- Late-night licences (internal only, never shown to hirers) -------------


def late_licence_usage(enquiry, cfg=None):
    """How many late-night hires are already accepted in the same year.

    None when no yearly limit is configured or this enquiry has no late
    date. Counts hires only: the venue's own late events are not known to
    this feature, so the figure is a floor, and the meeting must add them.
    """
    cfg = cfg or get_hire_settings()
    limit = cfg.late_night_licences_per_year
    late = enquiry.late_dates()
    if not limit or not late:
        return None
    year = timezone.localtime(late[0].start).year
    used = 0
    for other in E.objects.filter(
        status__in=(E.ACCEPTED, E.AWAITING_AGREEMENT, E.BOOKED, E.COMPLETED)
    ).exclude(pk=enquiry.pk):
        if any(
            timezone.localtime(d.start).year == year
            for d in other.late_dates()
            if d.accepted
        ):
            used += 1
    return {"year": year, "used": used, "limit": limit}
