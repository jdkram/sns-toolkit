# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Public enquiry form, terms agreement, and the management screens.

Every view starts with ``hires_gate``: while the ``hire_enquiries_enabled``
flag on SiteConfiguration is off, the whole feature 404s.
"""

import logging
from functools import wraps

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.cache import cache
from django.forms import modelformset_factory
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from toolkit.toolkit_auth import password_emails
from toolkit.toolkit_auth.decorators import feature_required

from . import defaults, services
from .forms import (
    ApprovedTechForm,
    EmailTemplateForm,
    HireDetailsForm,
    HireEnquiryForm,
    HireSettingsForm,
    HireTypeForm,
    MeetingForm,
)
from .models import (
    ApprovedTech,
    HireEmailTemplate,
    HireEnquiry,
    HireType,
    Hirer,
    ProgrammingMeeting,
    get_hire_settings,
    hires_enabled,
)

logger = logging.getLogger(__name__)
E = HireEnquiry


def hires_gate(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not hires_enabled():
            raise Http404("Hire enquiries are not enabled")
        return view(request, *args, **kwargs)

    return wrapper


def _client_ip(request):
    return request.META.get("REMOTE_ADDR") or None


def _over_limit(key, limit):
    return cache.get(f"hires_rl_{key}", 0) >= limit


def _record_hit(key, window=3600):
    k = f"hires_rl_{key}"
    cache.set(k, cache.get(k, 0) + 1, timeout=window)


def _template_text(text):
    cfg = get_hire_settings()
    try:
        return text.format(
            venue=password_emails.venue_name(),
            privacy_contact=cfg.privacy_contact or "the venue",
            declined_purge_months=cfg.declined_purge_months,
            hirer_purge_years=cfg.hirer_purge_years,
        )
    except (KeyError, IndexError, ValueError):
        return text


# --- Public ----------------------------------------------------------------


@hires_gate
def enquire(request):
    cfg = get_hire_settings()
    blockers, _ = services.readiness(cfg)
    if blockers:
        logger.warning("Hire form closed, not ready: %s", "; ".join(blockers))
    if not cfg.enquiries_open or blockers:
        return render(
            request, "hires/closed.html", {"message": cfg.closed_message}
        )
    full, reopens = services.full_until(cfg)
    if full:
        until = f"{reopens:%-d %B}" if reopens else "we have more dates"
        return render(
            request,
            "hires/closed.html",
            {
                "heading": "We're full for now",
                "message": services._format(
                    cfg.full_message or defaults.FULL_MESSAGE,
                    full_until=until,
                ),
            },
        )
    if request.method == "POST":
        form = HireEnquiryForm(request.POST)
        ip = _client_ip(request) or "?"
        email = request.POST.get("contact_email", "").lower()
        # Only successful submissions count: someone fixing mistakes on the
        # form (the 3-hour minimum, say) must not be locked out for it.
        if _over_limit(f"ip_{ip}", 10) or (
            email and _over_limit(f"em_{email}", 3)
        ):
            messages.error(
                request,
                "You've sent several enquiries recently. Please wait a "
                "while before trying again.",
            )
        elif form.is_valid():
            d = form.cleaned_data
            enquiry = E(
                contact_name=d["contact_name"],
                contact_organisation=d["contact_organisation"],
                contact_email=d["contact_email"],
                contact_phone=d["contact_phone"],
                hire_type=d["hire_type"],
                tier_requested=d["tier_requested"],
                community_case=(
                    d["community_case"].strip()
                    if d["tier_requested"] == "community"
                    else ""
                ),
                community_evidence=(
                    d["community_evidence"].strip()
                    if d["tier_requested"] == "community"
                    else ""
                ),
                title=d["title"],
                description=d["description"],
                expected_attendance=d["expected_attendance"],
                flexibility_notes=d["flexibility_notes"],
                date_flexible=bool(d["flexibility_notes"].strip()),
            )
            enquiry.save()
            _record_hit(f"ip_{ip}")
            _record_hit(f"em_{email}")
            services.submit_enquiry(enquiry, form.hire_dates)
            request.session["hires_last_reply_by"] = (
                f"{enquiry.reply_deadline:%-d %B %Y}"
            )
            request.session["hires_last_ref"] = f"HIRE-{enquiry.pk}"
            request.session["hires_last_title"] = enquiry.title
            return redirect("hires:thanks")
    else:
        form = HireEnquiryForm()
    form.fields["tier_requested"].help_text = cfg.tier_guidance_text
    return render(
        request,
        "hires/enquire.html",
        {
            "form": form,
            "min_hours": cfg.site_min_hours(),
            "late_notice": services.late_notice_text(cfg),
            "door_notice": services.door_notice_text(cfg),
            "late_from": f"{cfg.late_night_from:%H:%M}",
            "door_types": {
                str(t.pk): t.provides_door_staff
                for t in HireType.objects.filter(active=True)
            },
            "door_now": bool(
                form.late_requested
                and HireType.objects.filter(
                    pk=form.data.get("hire_type") or 0,
                    provides_door_staff=True,
                ).exists()
            ),
            "how_we_work": cfg.how_we_work_text,
            "community_rate_text": cfg.community_rate_text,
            "tier_guidance": cfg.tier_guidance_text,
            "privacy_notice": _template_text(cfg.privacy_notice_text),
            "retention_notice": (
                f"We'll keep your details for up to "
                f"{cfg.declined_purge_months} months after we've dealt with "
                f"your enquiry, or {cfg.hirer_purge_years} years after your "
                "last contact if you hire from us. We then delete them."
            ),
            "types": HireType.objects.filter(active=True),
            "price_rows": services.price_rows(),
            "info_url": (cfg.info_page_url or "").strip(),
        },
    )


@hires_gate
def quote(request):
    """Indicative fee for the form's live estimate (same maths as the real
    quote, via services.indicative_fee_text). Stores nothing."""
    import datetime

    from .models import HireDate

    g = request.GET
    hire_type = HireType.objects.filter(
        pk=g.get("hire_type") or 0, active=True
    ).first()
    tier = (
        g.get("tier")
        if g.get("tier") in dict(E.TIER_CHOICES)
        else E.TIER_COMMUNITY
    )
    dates = []
    try:
        day = datetime.date.fromisoformat(g.get("date", ""))
        t_in = datetime.time.fromisoformat(g.get("get_in", ""))
        t_out = datetime.time.fromisoformat(g.get("get_out", ""))
    except ValueError:
        return JsonResponse({"text": ""})
    gi = timezone.make_aware(datetime.datetime.combine(day, t_in))
    go = timezone.make_aware(datetime.datetime.combine(day, t_out))
    while go <= gi:
        go += datetime.timedelta(days=1)
    dates.append(HireDate(get_in=gi, start=gi, end=go, get_out=go))
    return JsonResponse(
        {"text": services.indicative_fee_text(hire_type, tier, dates)}
    )


@hires_gate
def privacy(request):
    cfg = get_hire_settings()
    return render(
        request,
        "hires/privacy.html",
        {"notice": _template_text(cfg.privacy_notice_text)},
    )


@hires_gate
def thanks(request):
    return render(
        request,
        "hires/thanks.html",
        {
            "reply_by": request.session.get("hires_last_reply_by", ""),
            "ref": request.session.get("hires_last_ref", ""),
            "title": request.session.get("hires_last_title", ""),
        },
    )


@hires_gate
def details(request, token):
    enquiry = get_object_or_404(
        E,
        details_token=token,
        status__in=[E.ACCEPTED, E.AWAITING_AGREEMENT, E.BOOKED],
    )
    if enquiry.is_purged:
        raise Http404
    form = HireDetailsForm(
        enquiry,
        request.POST or None,
        initial={
            "rooms_requested": list(enquiry.rooms_requested.all()),
            "expected_attendance": enquiry.expected_attendance,
            "media_url": enquiry.media_url,
            "sound_tech": enquiry.sound_tech,
            "sound_tech_name": enquiry.sound_tech_name,
            "offers_to_volunteers": enquiry.offers_to_volunteers,
        },
    )
    # Once terms are out the details are what was quoted: changes go through
    # the coordinator, who re-sends the confirmation.
    locked = enquiry.status in (E.AWAITING_AGREEMENT, E.BOOKED)
    if request.method == "POST" and not locked and form.is_valid():
        services.complete_details(enquiry, form.cleaned_data, form.new_times)
        return render(request, "hires/details_thanks.html", {"e": enquiry})
    return render(
        request,
        "hires/details.html",
        {
            "e": enquiry,
            "form": form,
            "locked": locked,
            "already_sent": bool(enquiry.details_completed_at),
        },
    )


@hires_gate
def agree(request, token):
    enquiry = get_object_or_404(
        E, agreement_token=token, status__in=[E.AWAITING_AGREEMENT, E.BOOKED]
    )
    cfg = get_hire_settings()
    statements = cfg.acknowledgement_list()
    error = ""
    if request.method == "POST" and enquiry.status == E.AWAITING_AGREEMENT:
        ticked = request.POST.getlist("ack")
        if all(s in ticked for s in statements):
            services.record_agreement(
                enquiry, ip=_client_ip(request), acknowledged=statements
            )
            return redirect("hires:agree", token=token)
        error = "Please tick every box before agreeing."
    return render(
        request,
        "hires/agree.html",
        {
            "enquiry": enquiry,
            "terms": services.terms_text(enquiry),
            "fee": services.fee_text(enquiry),
            "dates": services.describe_dates(enquiry, accepted_only=True),
            "guarantee": services.guarantee_text(enquiry),
            "statements": statements,
            "error": error,
        },
    )


# --- Management -----------------------------------------------------------

GROUPS = [
    ("Needs a decision", (E.ACKNOWLEDGED, E.TO_DISCUSS)),
    ("Maybe: looking for a coordinator", (E.MAYBE,)),
    ("Accepted: agreeing terms", (E.ACCEPTED, E.AWAITING_AGREEMENT)),
    ("Booked", (E.BOOKED,)),
]


def season_summary():
    cfg = get_hire_settings()
    booked = E.objects.filter(status__in=[E.BOOKED, E.COMPLETED])
    open_ = E.objects.filter(
        status__in=[
            E.ACKNOWLEDGED,
            E.TO_DISCUSS,
            E.MAYBE,
            E.ACCEPTED,
            E.AWAITING_AGREEMENT,
        ]
    )
    confirmed = sum((e.agreed_fee_gbp or e.estimate_gbp()) for e in booked)
    discussing = sum(e.estimate_gbp() for e in open_)
    per = cfg.volunteer_event_net_cost_gbp or 1
    return {
        "confirmed": confirmed,
        "discussing": discussing,
        "confirmed_events": round(float(confirmed / per), 1),
        "discussing_events": round(float(discussing / per), 1),
        "per_event": per,
    }


@hires_gate
@feature_required("hire_enquiries")
def queue(request):
    enquiries = (
        E.objects.select_related("hire_type", "meeting", "event")
        .prefetch_related("hire_dates")
        .all()
    )
    groups = []
    for label, statuses in GROUPS:
        rows = [e for e in enquiries if e.status in statuses]
        rows.sort(key=lambda e: e.reply_deadline or e.submitted_at.date())
        groups.append((label, rows))
    closed = [
        e for e in enquiries if e.status in E.CLOSED_NEGATIVE + (E.COMPLETED,)
    ][:30]
    rows = services.hire_email_rows(
        since=timezone.now() - timezone.timedelta(days=120)
    )
    for e in enquiries:
        e.no_keyholder = e.status in (
            E.ACCEPTED,
            E.AWAITING_AGREEMENT,
            E.BOOKED,
        ) and bool(services.unfilled_keyholder_slots(e))
        e.email_problem = bool(
            services.email_problems(services.messages_for(e, rows))
        )
    deciding = [
        e
        for _, rows in groups
        for e in rows
        if e.status in (E.ACKNOWLEDGED, E.TO_DISCUSS, E.MAYBE)
    ]
    around = services.whats_on(deciding)
    for e in deciding:
        e.whats_on = around.get(e.pk, [])
    return render(
        request,
        "hires/queue.html",
        {
            "groups": groups,
            "closed": closed,
            "summary": season_summary(),
            "today": timezone.localdate(),
            "blockers": services.readiness()[0],
            "no_meetings": not ProgrammingMeeting.objects.filter(
                date__gte=timezone.localdate(), cancelled=False
            ).exists(),
        },
    )


@hires_gate
@feature_required("hire_enquiries")
def detail(request, pk):
    enquiry = get_object_or_404(
        E.objects.select_related("hire_type", "meeting", "event", "hirer"),
        pk=pk,
    )
    suggested = Hirer.objects.filter(email__iexact=enquiry.contact_email)
    sent = services.messages_for(enquiry, services.hire_email_rows())
    problems = services.email_problems(sent)
    return render(
        request,
        "hires/detail.html",
        {
            "e": enquiry,
            "sent": [
                (r, services.label_for_source(r.trigger_source)) for r in sent
            ],
            "email_problems": [
                (
                    r,
                    services.label_for_source(r.trigger_source),
                    services._KEY_FOR_SOURCE.get(r.trigger_source),
                )
                for r in problems
            ],
            "dates": enquiry.dates(),
            "whats_on": services.whats_on([enquiry]).get(enquiry.pk, []),
            "estimate": enquiry.estimate_gbp(),
            "charge": enquiry.charge_gbp(),
            "full_charge": enquiry.charge_gbp(tier=E.TIER_CORPORATE),
            "subsidy": enquiry.subsidy_gbp(),
            "late_dates": enquiry.late_dates(),
            "licence": services.late_licence_usage(enquiry),
            "door_required": enquiry.door_staff_required(),
            "door_default": get_hire_settings().door_staff_fee_gbp,
            "suggested_hirers": suggested if not enquiry.hirer else [],
            "past": E.objects.filter(
                contact_email__iexact=enquiry.contact_email
            ).exclude(pk=enquiry.pk),
            "meetings": ProgrammingMeeting.objects.filter(
                date__gte=timezone.localdate(), cancelled=False
            ),
            "staff": [
                (
                    u.pk,
                    (
                        f"{u.get_full_name()} ({u.username})"
                        if u.get_full_name()
                        else u.username
                    ),
                )
                for u in User.objects.filter(is_active=True).order_by(
                    "first_name", "username"
                )
            ],
            "purge_on": enquiry.purge_due_on(),
            "details_link": services.details_url(enquiry),
            "can_decide": enquiry.status
            in (E.ACKNOWLEDGED, E.TO_DISCUSS, E.MAYBE),
            "drafts": services.draft_decision_emails(enquiry, request.user),
            "meeting_full": enquiry.meeting
            and not services.has_space(enquiry.meeting, exclude=enquiry.pk),
            "keyholder_gap": services.unfilled_keyholder_slots(enquiry),
            "tech_unlisted": enquiry.sound_tech == "own"
            and enquiry.sound_tech_name,
            "event_terms_ok": bool(
                enquiry.event and enquiry.event.terms_satisfied()
            ),
        },
    )


def _email_choice(request):
    """How the hirer hears about a decision, from the draft on the page."""
    if request.POST.get("email_mode") == "self":
        return services.SELF
    subject = request.POST.get("email_subject", "").strip()
    body = request.POST.get("email_body", "").strip()
    if subject and body:
        return (subject, body.replace("\r\n", "\n") + "\n")
    return None


def _money(raw, what):
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(raw) if raw else None
    except InvalidOperation:
        raise ValueError(f"The {what} is not a number")


# Each action takes (request, enquiry) and returns the message to show; a
# ValueError becomes an error message instead.


def _note(request):
    return request.POST.get("note", "").strip()


def _act_accept(request, enquiry):
    coord = None
    if request.POST.get("coordinator", "").isdigit():
        coord = User.objects.filter(
            pk=int(request.POST["coordinator"])
        ).first()
    ids = [int(x) for x in request.POST.getlist("dates") if x.isdigit()]
    email = _email_choice(request)
    services.accept(
        enquiry,
        request.user,
        coordinator=coord,
        accepted_date_ids=ids or None,
        tier_agreed=request.POST.get("tier_agreed", ""),
        fee=_money(request.POST.get("fee"), "fee"),
        door_fee=_money(request.POST.get("door_fee"), "door staff charge"),
        email=email,
    )
    return (
        "Accepted. A proposed event was created; add the terms there, then "
        "send the booking confirmation from here."
        + (
            " The hirer was not emailed: send them the details link below."
            if email == services.SELF
            else ""
        )
    )


def _act_maybe(request, enquiry):
    email = _email_choice(request)
    services.mark_maybe(enquiry, request.user, _note(request), email=email)
    return "Marked as maybe; callout sent." + (
        " The hirer was not emailed." if email == services.SELF else ""
    )


def _act_decline(request, enquiry):
    email = _email_choice(request)
    services.decline(enquiry, request.user, email=email)
    if email == services.SELF:
        return "Declined. The hirer was not emailed: remember to tell them."
    return "Declined; the hirer has been told."


def _act_champion(request, enquiry):
    services.champion(enquiry, request.user)
    return (
        "It's yours. It has left the meeting queue and nothing automatic "
        "will go to the hirer."
    )


def _act_release(request, enquiry):
    services.release(enquiry, request.user)
    return "Handed back to the meeting queue."


def _act_outside(request, enquiry):
    services.replied_outside_toolkit(enquiry, _note(request))
    return "Noted. The clock moved on to the next meeting."


def _act_details_received(request, enquiry):
    services.mark_details_received(enquiry, _note(request))
    return "Marked as received."


def _act_resend(request, enquiry):
    services.resend(enquiry, request.POST.get("key", ""))
    return "Email re-sent. See Messages sent below."


def _act_withdraw(_request, enquiry):
    services.withdraw(enquiry)
    return "Marked as withdrawn."


def _act_volunteer(request, enquiry):
    services.volunteer_to_coordinate(enquiry, request.user)
    return "You're coordinating this one."


def _act_send_confirmation(_request, enquiry):
    services.send_confirmation(enquiry)
    return "Terms and agreement link sent."


def _act_assign_meeting(request, enquiry):
    m = get_object_or_404(
        ProgrammingMeeting, pk=request.POST.get("meeting") or 0
    )
    if enquiry.status not in E.CLOCK_STATES:
        raise ValueError(
            "Only enquiries still waiting for a decision can be moved to "
            "another meeting"
        )
    full = not services.has_space(m, exclude=enquiry.pk)
    services.assign_meeting(enquiry, m)
    enquiry.status = E.TO_DISCUSS
    enquiry.save()
    messages.success(request, "Moved; the deadline was recomputed.")
    if full and not enquiry.coordinator_id:
        slots = m.slots()
        messages.warning(
            request,
            f"That meeting is now over its {slots} hire "
            f"slot{'' if slots == 1 else 's'}. Move something else on, or "
            "raise its slots on the Meetings page.",
        )
    return None


def _act_link_hirer(request, enquiry):
    hirer = Hirer.objects.filter(
        pk=request.POST.get("hirer") or 0
    ).first() or Hirer.objects.create(
        name=enquiry.contact_name,
        organisation=enquiry.contact_organisation,
        email=enquiry.contact_email,
        phone=enquiry.contact_phone,
    )
    enquiry.hirer = hirer
    enquiry.save(update_fields=["hirer"])
    return "Linked to hirer record."


def _act_save_notes(request, enquiry):
    enquiry.internal_notes = request.POST.get("notes", "")
    enquiry.save(update_fields=["internal_notes"])
    return "Notes saved."


_ACTIONS = {
    "accept": _act_accept,
    "maybe": _act_maybe,
    "decline": _act_decline,
    "champion": _act_champion,
    "release": _act_release,
    "outside": _act_outside,
    "details_received": _act_details_received,
    "resend": _act_resend,
    "withdraw": _act_withdraw,
    "volunteer": _act_volunteer,
    "send_confirmation": _act_send_confirmation,
    "assign_meeting": _act_assign_meeting,
    "link_hirer": _act_link_hirer,
    "save_notes": _act_save_notes,
}


@hires_gate
@feature_required("hire_enquiries")
@require_POST
def act(request, pk):
    enquiry = get_object_or_404(E, pk=pk)
    handler = _ACTIONS.get(request.POST.get("action", ""))
    if handler is None:
        messages.error(request, "Unknown action.")
    else:
        try:
            done = handler(request, enquiry)
            if done:
                messages.success(request, done)
        except ValueError as exc:
            messages.error(request, str(exc))
    if request.POST.get("next") == "meetings":
        return redirect("hires:meetings")
    return redirect("hires:detail", pk=pk)


# --- Settings screens -----------------------------------------------------


@hires_gate
@feature_required("hire_settings")
def settings_edit(request):
    cfg = get_hire_settings()
    form = HireSettingsForm(request.POST or None, instance=cfg)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Hire settings saved.")
        return redirect("hires:settings")
    return render(
        request,
        "hires/settings.html",
        {
            "form": form,
            "groups": form.grouped(),
            "readiness": services.readiness(cfg),
        },
    )


@hires_gate
@feature_required("hire_settings")
def meetings(request):
    form = MeetingForm(request.POST or None)
    if request.method == "POST":
        if request.POST.get("slots_for"):
            m = get_object_or_404(
                ProgrammingMeeting, pk=request.POST["slots_for"]
            )
            raw = request.POST.get("hire_slots", "").strip()
            m.hire_slots = int(raw) if raw.isdigit() else None
            m.save(update_fields=["hire_slots"])
            messages.success(request, f"Hire slots for {m} saved.")
            return redirect("hires:meetings")
        if request.POST.get("cancel"):
            m = get_object_or_404(
                ProgrammingMeeting, pk=request.POST["cancel"]
            )
            services.meeting_cancelled(m)
            messages.success(request, "Meeting cancelled; enquiries moved on.")
            return redirect("hires:meetings")
        if form.is_valid():
            form.save()
            messages.success(request, "Meeting added.")
            return redirect("hires:meetings")
    return render(
        request,
        "hires/meetings.html",
        {
            "form": form,
            "meetings": ProgrammingMeeting.objects.filter(
                date__gte=timezone.localdate() - timezone.timedelta(days=60)
            ),
            "agendas": _agendas(),
            "upcoming": ProgrammingMeeting.objects.filter(
                date__gte=timezone.localdate(), cancelled=False
            ),
        },
    )


def _agendas():
    """Each upcoming meeting's hire enquiries, soonest hire date first."""
    today = timezone.localdate()
    grace = timezone.timedelta(days=get_hire_settings().reply_grace_days)
    out = []
    for m in ProgrammingMeeting.objects.filter(
        date__gte=today, cancelled=False
    ):
        rows = []
        for e in m.agenda().select_related("hire_type"):
            first = e.dates()[:1]
            start = first[0].start if first else None
            day = timezone.localtime(start).date() if start else None
            rows.append(
                {
                    "e": e,
                    "start": start,
                    "too_late": day and day <= m.date,
                    "answer_after": day and m.date < day <= m.date + grace,
                }
            )
        rows.sort(key=lambda r: (r["start"] is None, r["start"]))
        out.append({"m": m, "rows": rows, "over": len(rows) > m.slots()})
    return out


def _formset_view(request, model, form, template, title, intro="", extra=1):
    FS = modelformset_factory(model, form=form, extra=extra, can_delete=True)
    formset = FS(request.POST or None, queryset=model.objects.all())
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, f"{title} saved.")
        return redirect(request.path)
    return render(
        request, template, {"formset": formset, "title": title, "intro": intro}
    )


@hires_gate
@feature_required("hire_settings")
def types(request):
    return _formset_view(
        request,
        HireType,
        HireTypeForm,
        "hires/formset.html",
        "Hire types",
        "The price list. These appear in the 'What kind of hire?' dropdown "
        "and drive the income estimate. Use the empty form at the bottom to "
        "add one; tick Delete on a form to remove it.",
    )


@hires_gate
@feature_required("hire_settings")
def techs(request):
    return _formset_view(
        request,
        ApprovedTech,
        ApprovedTechForm,
        "hires/formset.html",
        "Approved sound techs",
        "Freelance techs who know our gear. They contain personal data: "
        "only tick 'OK to give their details to hirers' once they have "
        "agreed. None added yet means hirers are simply told they need a "
        "tech.",
    )


@hires_gate
@feature_required("hire_settings")
def email_templates(request):
    keys = [k for _s, _b, ks in defaults.EMAIL_STAGES for k in ks]
    key = request.GET.get("key") or request.POST.get("key") or keys[0]
    if key not in keys:
        raise Http404
    row = HireEmailTemplate.objects.filter(key=key).first()
    subject, body = (
        defaults.EMAIL_DEFAULTS.get(key) or defaults.INTERNAL_DEFAULTS[key]
    )
    if request.method == "POST":
        if request.POST.get("reset"):
            HireEmailTemplate.objects.filter(key=key).delete()
            messages.success(request, "Reset to the default wording.")
            return redirect(f"{request.path}?key={key}")
        form = EmailTemplateForm(request.POST, instance=row)
        if form.is_valid():
            form.save()
            messages.success(request, "Email wording saved.")
            return redirect(f"{request.path}?key={key}")
    else:
        form = EmailTemplateForm(
            instance=row,
            initial={"key": key, "subject": subject, "body": body},
        )
    return render(
        request,
        "hires/email_templates.html",
        {
            "stages": [
                (
                    stage,
                    blurb,
                    [
                        (
                            k,
                            defaults.EMAIL_LABELS[k][0].removesuffix(
                                " (internal)"
                            ),
                            k in defaults.INTERNAL_DEFAULTS,
                        )
                        for k in stage_keys
                    ],
                )
                for stage, blurb, stage_keys in defaults.EMAIL_STAGES
            ],
            "internal": key in defaults.INTERNAL_DEFAULTS,
            "key": key,
            "label": defaults.EMAIL_LABELS[key][0].removesuffix(" (internal)"),
            "when": defaults.EMAIL_LABELS[key][1],
            "form": form,
            "customised": bool(row),
        },
    )
