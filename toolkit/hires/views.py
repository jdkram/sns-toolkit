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
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from toolkit.toolkit_auth import password_emails
from toolkit.toolkit_auth.decorators import feature_required

from . import defaults, services
from .forms import (
    ApprovedTechForm,
    EmailTemplateForm,
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


def _rate_limited(key, limit=5, window=3600):
    k = f"hires_rl_{key}"
    n = cache.get(k, 0)
    if n >= limit:
        return True
    cache.set(k, n + 1, timeout=window)
    return False


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
    if not cfg.enquiries_open:
        return render(
            request, "hires/closed.html", {"message": cfg.closed_message}
        )
    if request.method == "POST":
        form = HireEnquiryForm(request.POST)
        ip = _client_ip(request) or "?"
        email = request.POST.get("contact_email", "").lower()
        if _rate_limited(f"ip_{ip}", 10) or (
            email and _rate_limited(f"em_{email}", 3)
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
                title=d["title"],
                description=d["description"],
                expected_attendance=d["expected_attendance"],
                media_url=d["media_url"],
                sound_tech=d["sound_tech"],
                sound_tech_name=d["sound_tech_name"],
                offers_to_volunteers=d["offers_to_volunteers"],
                date_flexible=d["date_flexible"],
                flexibility_notes=d["flexibility_notes"],
                acknowledgements=list(d["acknowledgements"]),
            )
            enquiry.save()  # need a pk for the M2M before assigning meeting
            enquiry.rooms_requested.set(d["rooms_requested"])
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
            "min_hours": cfg.min_duration_hours,
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
            "tier_guidance": cfg.tier_guidance_text,
            "privacy_notice": _template_text(cfg.privacy_notice_text),
            "retention_notice": (
                f"We'll keep your details for up to "
                f"{cfg.declined_purge_months} months after we've dealt with "
                f"your enquiry, or {cfg.hirer_purge_years} years after your "
                "last contact if you hire from us. We then delete them."
            ),
            "types": HireType.objects.filter(active=True),
        },
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
def agree(request, token):
    enquiry = get_object_or_404(
        E, agreement_token=token, status__in=[E.AWAITING_AGREEMENT, E.BOOKED]
    )
    if request.method == "POST" and enquiry.status == E.AWAITING_AGREEMENT:
        services.record_agreement(enquiry, ip=_client_ip(request))
        return redirect("hires:agree", token=token)
    return render(
        request,
        "hires/agree.html",
        {
            "enquiry": enquiry,
            "terms": services.terms_text(enquiry),
            "fee": services.fee_text(enquiry),
            "dates": services.describe_dates(enquiry, accepted_only=True),
            "guarantee": services.guarantee_text(enquiry),
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
        e.email_problem = bool(
            services.email_problems(services.messages_for(e, rows))
        )
    return render(
        request,
        "hires/queue.html",
        {
            "groups": groups,
            "closed": closed,
            "summary": season_summary(),
            "today": timezone.localdate(),
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
            "estimate": enquiry.estimate_gbp(),
            "charge": enquiry.charge_gbp(),
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
            "can_decide": enquiry.status
            in (E.ACKNOWLEDGED, E.TO_DISCUSS, E.MAYBE),
            "tech_unlisted": enquiry.sound_tech == "own"
            and enquiry.sound_tech_name,
            "event_terms_ok": bool(
                enquiry.event and enquiry.event.terms_satisfied()
            ),
        },
    )


@hires_gate
@feature_required("hire_enquiries")
@require_POST
def act(request, pk):
    enquiry = get_object_or_404(E, pk=pk)
    action = request.POST.get("action", "")
    note = request.POST.get("note", "").strip()
    try:
        if action == "accept":
            coord = None
            if request.POST.get("coordinator", "").isdigit():
                coord = User.objects.filter(
                    pk=int(request.POST["coordinator"])
                ).first()
            ids = [
                int(x) for x in request.POST.getlist("dates") if x.isdigit()
            ]
            fee = request.POST.get("fee") or None
            from decimal import Decimal, InvalidOperation

            try:
                fee = Decimal(fee) if fee else None
            except InvalidOperation:
                raise ValueError("The fee is not a number")
            door_raw = request.POST.get("door_fee") or None
            try:
                door_fee = Decimal(door_raw) if door_raw else None
            except InvalidOperation:
                raise ValueError("The door staff charge is not a number")
            services.accept(
                enquiry,
                request.user,
                coordinator=coord,
                accepted_date_ids=ids or None,
                tier_agreed=request.POST.get("tier_agreed", ""),
                fee=fee,
                door_fee=door_fee,
            )
            messages.success(
                request,
                "Accepted. A proposed event was created; add the terms "
                "there, then send the booking confirmation from here.",
            )
            return redirect("hires:detail", pk=pk)
        elif action == "maybe":
            services.mark_maybe(enquiry, request.user, note)
            messages.success(request, "Marked as maybe; callout sent.")
        elif action == "decline":
            services.decline(enquiry, request.user)
            messages.success(request, "Declined; the hirer has been told.")
        elif action == "outside":
            services.replied_outside_toolkit(enquiry, note)
            messages.success(
                request, "Noted. The clock moved on to the next meeting."
            )
        elif action == "resend":
            services.resend(enquiry, request.POST.get("key", ""))
            messages.success(
                request, "Email re-sent. See Messages sent below."
            )
        elif action == "withdraw":
            services.withdraw(enquiry)
            messages.info(request, "Marked as withdrawn.")
        elif action == "volunteer":
            services.volunteer_to_coordinate(enquiry, request.user)
            messages.success(request, "You're coordinating this one.")
        elif action == "send_confirmation":
            services.send_confirmation(enquiry)
            messages.success(request, "Terms and agreement link sent.")
        elif action == "assign_meeting":
            m = get_object_or_404(
                ProgrammingMeeting, pk=request.POST.get("meeting") or 0
            )
            services.assign_meeting(enquiry, m)
            enquiry.digest_sent_at = None
            enquiry.status = E.TO_DISCUSS
            enquiry.save()
            messages.success(request, "Moved; the deadline was recomputed.")
        elif action == "link_hirer":
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
            messages.success(request, "Linked to hirer record.")
        elif action == "save_notes":
            enquiry.internal_notes = request.POST.get("notes", "")
            enquiry.save(update_fields=["internal_notes"])
            messages.success(request, "Notes saved.")
        else:
            messages.error(request, "Unknown action.")
    except ValueError as exc:
        messages.error(request, str(exc))
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
        {"form": form, "groups": form.grouped()},
    )


@hires_gate
@feature_required("hire_settings")
def meetings(request):
    form = MeetingForm(request.POST or None)
    if request.method == "POST":
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
        },
    )


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
    keys = list(defaults.EMAIL_DEFAULTS) + list(defaults.INTERNAL_DEFAULTS)
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
            "keys": [(k, defaults.EMAIL_LABELS[k][0]) for k in keys],
            "key": key,
            "label": defaults.EMAIL_LABELS[key][0],
            "when": defaults.EMAIL_LABELS[key][1],
            "form": form,
            "customised": bool(row),
        },
    )
