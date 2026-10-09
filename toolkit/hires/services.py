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


def guarantee_text(enquiry):  # noqa: ARG001 (per-enquiry wording later)
    return _format(
        defaults.GUARANTEE_BLOCK,
        best_effort="bar, door, projection and any other volunteer help",
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


def send_to_hirer(enquiry, key, source, **extra):
    vars = {
        "name": enquiry.contact_name,
        "title": enquiry.title,
        "dates": describe_dates(enquiry),
        "guarantee": guarantee_text(enquiry),
        "meeting_date": (
            f"{enquiry.meeting.date:%-d %B %Y}" if enquiry.meeting else "TBC"
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
        "techs": "",
        "terms": "",
        "fee": "",
        "agreement_url": "",
        "timing": "",
        "window_note": "",
    }
    vars.update(extra)
    subject, body = render_email(key, **vars)
    body += (
        "\n\n--\nHow we use your information: "
        + abs_url(reverse("hires:privacy"))
        + "\n"
    )
    _send([enquiry.contact_email], subject, body, source)


def notify_internal(key, source, **vars):
    cfg = get_hire_settings()
    to = cfg.notification_address_list()
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


# --- Meeting-aware reply clock -------------------------------------------


def next_meeting_for(submitted_at, cfg=None):
    cfg = cfg or get_hire_settings()
    earliest = timezone.localtime(submitted_at).date() + datetime.timedelta(
        days=cfg.min_notice_days_before_meeting
    )
    return (
        ProgrammingMeeting.objects.filter(date__gte=earliest, cancelled=False)
        .order_by("date")
        .first()
    )


def assign_meeting(enquiry, meeting=None, cfg=None):
    """Assign (or reassign) a meeting and derive the deadline from it.

    The deadline is always derived from the meeting, never stored on its own,
    so moving a meeting cannot leave a stale promise. Clears the last-call
    marker because the new deadline is a new promise.
    """
    cfg = cfg or get_hire_settings()
    meeting = meeting or next_meeting_for(enquiry.submitted_at, cfg)
    enquiry.meeting = meeting
    if meeting:
        enquiry.reply_deadline = meeting.date + datetime.timedelta(
            days=cfg.reply_grace_days
        )
    else:
        enquiry.reply_deadline = timezone.localtime(
            enquiry.submitted_at
        ).date() + datetime.timedelta(days=cfg.fallback_reply_days)
    enquiry.warning_sent_at = None
    enquiry.digest_sent_at = None
    return enquiry


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
    send_to_hirer(
        enquiry,
        "acknowledgement",
        HIRER_EMAIL_SOURCES["acknowledgement"],
        timing=timing,
        window_note=window_note,
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
):
    """Accept: create a proposed Event linked back, email the hirer."""
    from toolkit.diary.models import (
        Event,
        RoomBooking,
        Showing,
    )

    if enquiry.status not in (E.TO_DISCUSS, E.ACKNOWLEDGED, E.MAYBE):
        raise ValueError(f"Cannot accept an enquiry that is {enquiry.status}")
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
            fee = enquiry.estimate_gbp()
        enquiry.agreed_fee_gbp = fee
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
    send_to_hirer(
        enquiry,
        "accepted",
        HIRER_EMAIL_SOURCES["accepted"],
        coordinator_line=_coordinator_line(enquiry),
        techs=_approved_tech_text(),
    )
    return event


def _coordinator_line(enquiry):
    user = enquiry.coordinator
    if not user:
        return ""
    return f"{user.get_full_name() or user.username} will be your contact."


def mark_maybe(enquiry, user, what_we_need, cfg=None):  # noqa: ARG001
    cfg = cfg or get_hire_settings()
    if not what_we_need.strip():
        raise ValueError("Say what support is needed")
    enquiry.callout_what_we_need = what_we_need.strip()
    enquiry.callout_deadline = timezone.localdate() + datetime.timedelta(
        days=cfg.callout_days
    )
    enquiry.callout_warning_sent_at = None
    _set_status(enquiry, E.MAYBE)
    enquiry.save()
    send_to_hirer(enquiry, "maybe", HIRER_EMAIL_SOURCES["maybe"])
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


def decline(enquiry, user):  # noqa: ARG001
    _set_status(enquiry, E.DECLINED)
    enquiry.save()
    send_to_hirer(enquiry, "declined", HIRER_EMAIL_SOURCES["declined"])


def withdraw(enquiry):
    _set_status(enquiry, E.WITHDRAWN)
    enquiry.save()


def replied_outside_toolkit(enquiry, note):
    """Postpone (not stop) the clock: move to the next meeting."""
    if not note.strip():
        raise ValueError("Add a one-line note of what was said")
    enquiry.replied_outside_toolkit_at = timezone.now()
    enquiry.internal_notes = (
        f"{enquiry.internal_notes}\n[{timezone.localdate()}] Replied "
        f"outside the toolkit: {note.strip()}"
    ).strip()
    after = (
        enquiry.meeting.date + datetime.timedelta(days=1)
        if enquiry.meeting
        else timezone.localdate()
    )
    nxt = (
        ProgrammingMeeting.objects.filter(date__gte=after, cancelled=False)
        .order_by("date")
        .first()
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
    return f"£{fee:.2f} (excluding VAT where it applies)"


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


def record_agreement(enquiry, ip=None):
    enquiry.terms_agreed_at = timezone.now()
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
        "paused": False,
    }
    if not hires_enabled():
        out["paused"] = True
        return out

    live = E.objects.filter(status__in=E.CLOCK_STATES)

    # Enquiries stranded with no meeting get one if one now exists.
    for enq in live.filter(meeting__isnull=True):
        nxt = next_meeting_for(enq.submitted_at, cfg)
        if nxt and not dry_run:
            assign_meeting(enq, nxt, cfg)
            enq.save()

    # Pre-meeting digest, one per meeting.
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
            out["digests"] += 1

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
            f"£{e.estimate_gbp():.0f}; auto-declines "
            f"{by:%-d %b}"
            if by
            else f"- {e.title} ({e.contact_organisation or e.contact_name})"
        )
    return "\n".join(lines)


def meeting_cancelled(meeting):
    """Move a cancelled meeting's enquiries on; tell hirers if it slips."""
    meeting.cancelled = True
    meeting.save()
    for enq in meeting.enquiries.filter(status__in=E.CLOCK_STATES):
        old = enq.reply_deadline
        assign_meeting(enq, next_meeting_for(enq.submitted_at))
        enq.digest_sent_at = None
        enq.save()
        if old and enq.reply_deadline and enq.reply_deadline > old:
            try:
                send_to_hirer(
                    enq, "meeting_moved", HIRER_EMAIL_SOURCES["meeting_moved"]
                )
            except Exception:
                logger.exception("Meeting-moved email failed %s", enq.pk)


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
            techs=_approved_tech_text(),
        )
    else:
        send_to_hirer(enquiry, key, source)
