# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from toolkit.toolkit_auth import password_emails
from toolkit.toolkit_auth.decorators import panopticon_required

from ..emails import notify_policy_change, send_test_notification_email
from ..forms import InductionsSettingsForm
from ..models import InductionsSettings

logger = logging.getLogger(__name__)


def _test_template_vars(request, cfg: InductionsSettings) -> dict:
    """Sample variable values used when sending template preview emails and rendering tooltips."""
    validity = password_emails.password_reset_validity()
    sample_date = timezone.now().replace(
        hour=18, minute=30, second=0, microsecond=0
    ) + timezone.timedelta(days=7)
    venue = password_emails.venue_name()
    requester_name = request.user.get_full_name() or request.user.username
    return {
        "name": requester_name,
        "username": request.user.username,
        "venue": venue,
        "session_title": "Test Induction Session",
        "session_date": sample_date.strftime("%A %-d %B %Y at %H:%M"),
        "session_location": "Cinema",
        "calendar_url": request.build_absolute_uri(
            "/inductions/test-session/calendar.ics"
        ),
        "password_url": request.build_absolute_uri(
            "/accounts/reset/Mg/abc-123-def456/"
        ),
        "password_reset_url": request.build_absolute_uri(
            reverse("password_reset")
        ),
        "validity": validity,
        "welcome_pack_url": cfg.welcome_pack_url
        or "(no welcome pack URL configured)",
    }


@panopticon_required
def manage_settings(request):
    cfg = InductionsSettings.load()
    if request.method == "POST":
        form = InductionsSettingsForm(request.POST, instance=cfg)
        if form.is_valid():
            form.save()
            messages.success(request, "Inductions settings saved.")
            return redirect("inductions:manage_settings")
    else:
        form = InductionsSettingsForm(instance=cfg)

    return render(
        request,
        "inductions/manage/settings.html",
        {
            "form": form,
            "sample_vars": _test_template_vars(request, cfg),
            "test_email_url": reverse("inductions:manage_send_test_email"),
            "mark_policy_updated_url": reverse(
                "inductions:manage_mark_policy_updated"
            ),
            "policy_version": cfg.privacy_policy_version,
            "policy_updated_at": cfg.privacy_policy_updated_at,
            "user_email": request.user.email or "",
        },
    )


@require_POST
@panopticon_required
def manage_mark_policy_updated(request):  # noqa: ARG001 -- view signature
    """Bump the privacy policy version and immediately notify affected volunteers.

    Non-destructive and fully reversible in effect (worst case: one extra
    email round), so this only needs a JS confirm() dialog rather than the
    typed-confirmation-phrase pattern used for anonymisation.
    """
    # notify_policy_change() queries live from the DB for volunteers behind
    # *the already-bumped* version, so the bump has to be committed before
    # it runs -- it can't simply be reordered to "notify, then bump". But
    # bumping outside a transaction meant a failed send (e.g. the mail
    # server being down) left the version permanently bumped with nobody
    # notified, and a retry then bumped it *again* -- inflating the version
    # number by one for every failed attempt with no corresponding policy
    # change. Wrapping both in one transaction means a failure rolls the
    # bump back too, so a retry starts from the same version instead of
    # skipping ahead.
    try:
        with transaction.atomic():
            cfg = InductionsSettings.load()
            cfg.privacy_policy_version += 1
            cfg.privacy_policy_updated_at = timezone.now()
            cfg.save()
            sent, skipped = notify_policy_change()
    except Exception as exc:
        logger.exception("Failed to send policy-change notifications")
        return JsonResponse({"ok": False, "error": str(exc)})

    return JsonResponse({"ok": True, "notified": sent, "skipped": skipped})


@require_POST
@panopticon_required
def manage_send_test_email(request):
    template_type = request.POST.get("template_type", "notification")

    if template_type == "notification":
        cfg = InductionsSettings.load()
        recipient = cfg.organiser_notification_email
        if not recipient:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "No organiser notification email is configured.",
                }
            )
        try:
            send_test_notification_email(recipient)
        except Exception as exc:
            logger.exception("Failed to send test notification email")
            return JsonResponse({"ok": False, "error": str(exc)})
        return JsonResponse({"ok": True, "recipient": recipient})

    # Template preview: render the named template with sample data and send to
    # the requesting user's own email address so they can see what variables resolve to.
    recipient = request.user.email
    if not recipient:
        return JsonResponse(
            {"ok": False, "error": "Your account has no email address set."}
        )

    cfg = InductionsSettings.load()
    sample_vars = _test_template_vars(request, cfg)
    from_email = (
        settings.VENUE.get("mailout_from_address")
        or settings.DEFAULT_FROM_EMAIL
    )

    template_map = {
        "confirmation": (
            cfg.get_confirmation_subject(),
            cfg.get_confirmation_body(),
        ),
        "reminder": (cfg.get_reminder_subject(), cfg.get_reminder_body()),
        "welcome": (cfg.get_welcome_subject(), cfg.get_welcome_body()),
        "access_needs_ack": (
            cfg.get_access_needs_ack_subject(),
            cfg.get_access_needs_ack_body(),
        ),
    }
    if template_type not in template_map:
        return JsonResponse(
            {"ok": False, "error": f"Unknown template type: {template_type}"}
        )

    raw_subject, raw_body = template_map[template_type]
    try:
        subject = raw_subject.format(**sample_vars)
        body = raw_body.format(**sample_vars)
    except KeyError as exc:
        # A malformed template referencing an unknown placeholder used to be
        # swallowed here and the raw, unformatted template sent as if the
        # test had succeeded -- an operator testing a broken template got no
        # signal anything was wrong. Surface it instead.
        return JsonResponse(
            {
                "ok": False,
                "error": f"Template has an unknown placeholder: {exc}",
            }
        )

    preview_note = (
        f"--- PREVIEW (sent to {recipient} with sample data) ---\n\n"
    )

    try:
        send_mail(
            subject=f"[Preview] {subject}",
            message=preview_note + body,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception as exc:
        logger.exception("Failed to send template preview email")
        return JsonResponse({"ok": False, "error": str(exc)})

    return JsonResponse({"ok": True, "recipient": recipient})
