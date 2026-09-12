# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import logging

from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from toolkit.members.models import Member, Volunteer
from toolkit.toolkit_auth import password_emails
from toolkit.toolkit_auth.decorators import panopticon_required

from ..emails import send_welcome_email
from ..models import InductionSession, InductionSignup, InductionsSettings

logger = logging.getLogger(__name__)


def _create_volunteer_from_signup(signup: InductionSignup) -> Volunteer:
    """Create Member + User + Volunteer records from an InductionSignup."""
    name = signup.name or ""
    email = signup.email or ""

    member = Member(
        name=name,
        email=email,
        phone=signup.phone,
        address=signup.address,
        postcode=signup.postcode,
        gdpr_opt_in=timezone.now(),
    )
    member.save()

    if signup.desired_username:
        base = slugify(signup.desired_username)[:40] or "volunteer"
    else:
        parts = name.split()
        first = parts[0] if parts else "volunteer"
        last = parts[-1] if len(parts) > 1 else ""
        base = f"{first}{last}" or "volunteer"
    username = base
    n = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}-{n}"
        n += 1

    user = User(
        username=username,
        email=email,
        first_name=name.split()[0] if name else "",
        last_name=" ".join(name.split()[1:]) if name else "",
    )
    user.set_unusable_password()
    user.save()

    volunteer = Volunteer(
        user=user,
        member=member,
        display_name=signup.display_name,
        consent_policy_version=InductionsSettings.load().privacy_policy_version,
    )
    volunteer.save()

    return volunteer


def _find_existing_volunteer(signup: InductionSignup):
    """Return a matching Volunteer if one exists with the same email or name, else None."""
    if signup.email:
        user = (
            User.objects.filter(email__iexact=signup.email)
            .select_related("volunteer")
            .first()
        )
        if user and hasattr(user, "volunteer"):
            return user.volunteer
    if signup.name:
        member = (
            Member.objects.filter(name__iexact=signup.name)
            .select_related("volunteer")
            .first()
        )
        if member and hasattr(member, "volunteer"):
            return member.volunteer
    return None


def _send_password_reset_email(request, user):
    """Send a password-reset link to an existing volunteer account.

    Inductions-specific copy (refers to inductor confirmation) — the shared
    password_emails.send_password_set_email covers the members welcome/reset
    flow with different wording; this Email keeps its own subject/body and
    only reuses the token-building + venue lookup from password_emails.
    """
    reset_url = password_emails.build_password_reset_url(request, user)
    validity = password_emails.password_reset_validity()
    venue = password_emails.venue_name()
    name = user.first_name or user.username
    send_mail(
        subject=f"[{venue}] Log in to the toolkit",
        message=(
            f"Hi {name},\n\n"
            f"A volunteer inductor has confirmed your attendance at a recent induction.\n\n"
            f"Use the link below to log in to the {venue} volunteer toolkit (valid for {validity}):\n\n"
            f"{reset_url}\n\n"
            f"If you weren't expecting this email, please contact us."
        ),
        from_email=password_emails.from_email(),
        recipient_list=[user.email],
        fail_silently=False,
    )


@require_POST
@panopticon_required
def manage_check_in(request, slug, signup_id):
    """Legacy AJAX endpoint kept for backwards compatibility — creates account immediately."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)

    if signup.status == InductionSignup.STATUS_CHECKED_IN:
        return JsonResponse({"ok": False, "error": "Already checked in."})

    try:
        volunteer = _create_volunteer_from_signup(signup)
        send_welcome_email(request, signup, volunteer.user)
        signup.status = InductionSignup.STATUS_CHECKED_IN
        signup.volunteer = volunteer
        signup.checked_in_at = timezone.now()
        signup.checked_in_by = request.user
        signup.save()
        logger.info(
            f"{request.user} checked in {signup.name} (signup #{signup.pk}) "
            f"for session '{session.title}'"
        )
        return JsonResponse(
            {
                "ok": True,
                "volunteer_id": volunteer.pk,
                "checked_in_at": signup.checked_in_at.strftime("%H:%M"),
            }
        )
    except Exception as exc:
        logger.exception(f"Check-in failed for signup #{signup_id}")
        return JsonResponse({"ok": False, "error": str(exc)})


@require_POST
@panopticon_required
def manage_mark_attendance(request, slug, signup_id):
    """AJAX: toggle a signup's attendance status (CHECKED_IN <-> PENDING).

    Does NOT create a volunteer account. The 'Create accounts' step does that.
    """
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)

    if signup.volunteer_id:
        # Account already created — cannot unmark
        return JsonResponse(
            {
                "ok": False,
                "error": "Account already created — cannot unmark attendance.",
            }
        )

    if signup.status == InductionSignup.STATUS_CHECKED_IN:
        signup.status = InductionSignup.STATUS_PENDING
        signup.checked_in_at = None
        signup.checked_in_by = None
        signup.save()
        return JsonResponse({"ok": True, "status": "pending"})

    if signup.status == InductionSignup.STATUS_PENDING:
        signup.status = InductionSignup.STATUS_CHECKED_IN
        signup.checked_in_at = timezone.now()
        signup.checked_in_by = request.user
        signup.save()
        return JsonResponse({"ok": True, "status": "checked_in"})

    return JsonResponse(
        {
            "ok": False,
            "error": f"Cannot mark attendance for a {signup.get_status_display()} signup.",
        }
    )


@require_POST
@panopticon_required
def manage_create_accounts(request, slug):
    """Create volunteer accounts and send welcome emails for all CHECKED_IN signups.

    Only processes signups that are CHECKED_IN and do not yet have a volunteer FK.
    Before creating, checks for existing accounts with matching email or name and
    surfaces them as `duplicates` in the response for the inductor to resolve.
    Pass `force_signup_ids` (comma-separated) to bypass the duplicate check for
    specific signups.
    """
    session = get_object_or_404(InductionSession, slug=slug)
    pending_checkins = session.signups.filter(
        status=InductionSignup.STATUS_CHECKED_IN,
        volunteer__isnull=True,
    )
    forced_ids = set()
    for raw in request.POST.get("force_signup_ids", "").split(","):
        raw = raw.strip()
        if raw.isdigit():
            forced_ids.add(int(raw))

    created = []
    errors = []
    duplicates = []
    for signup in pending_checkins:
        if signup.pk not in forced_ids:
            existing = _find_existing_volunteer(signup)
            if existing:
                duplicates.append(
                    {
                        "signup_id": signup.pk,
                        "name": signup.name,
                        "match_type": (
                            "email"
                            if (
                                signup.email
                                and existing.user.email.lower()
                                == signup.email.lower()
                            )
                            else "name"
                        ),
                        "existing_volunteer_id": existing.pk,
                        "existing_username": existing.user.username,
                        "existing_email": existing.user.email,
                    }
                )
                continue
        try:
            volunteer = _create_volunteer_from_signup(signup)
            send_welcome_email(request, signup, volunteer.user)
            signup.volunteer = volunteer
            signup.save()
            created.append(
                {
                    "signup_id": signup.pk,
                    "name": signup.name,
                    "volunteer_id": volunteer.pk,
                    "username": volunteer.user.username,
                }
            )
            logger.info(
                f"{request.user} created account for {signup.name} (signup #{signup.pk}) "
                f"for session '{session.title}'"
            )
        except Exception as exc:
            logger.exception(
                f"Account creation failed for signup #{signup.pk}"
            )
            errors.append(
                {
                    "signup_id": signup.pk,
                    "name": signup.name,
                    "error": str(exc),
                }
            )

    return JsonResponse(
        {
            "ok": True,
            "created": created,
            "errors": errors,
            "duplicates": duplicates,
        }
    )


@require_POST
@panopticon_required
def manage_edit_signup(request, slug, signup_id):
    """AJAX: edit name and/or email for a signup (before account creation)."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)

    if signup.volunteer_id:
        return JsonResponse(
            {
                "ok": False,
                "error": "Account already created — edit the volunteer profile instead.",
            }
        )

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    desired_username = request.POST.get("desired_username", "").strip()

    if name:
        signup.name = name
    if email:
        signup.email = email
    signup.desired_username = desired_username
    signup.save()

    return JsonResponse(
        {
            "ok": True,
            "name": signup.name,
            "email": signup.email,
            "desired_username": signup.desired_username,
        }
    )


@require_POST
@panopticon_required
def manage_no_show(request, slug, signup_id):  # noqa: ARG001 -- view signature
    """AJAX endpoint: toggle no-show (pending → no_show, or no_show → pending)."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)
    if signup.status == InductionSignup.STATUS_CHECKED_IN:
        return JsonResponse(
            {
                "ok": False,
                "error": "Already checked in — cannot mark as no-show.",
            }
        )
    if signup.status == InductionSignup.STATUS_NO_SHOW:
        signup.status = InductionSignup.STATUS_PENDING
        signup.save()
        return JsonResponse({"ok": True, "new_status": "pending"})
    signup.status = InductionSignup.STATUS_NO_SHOW
    signup.save()
    return JsonResponse({"ok": True, "new_status": "no_show"})


@require_POST
@panopticon_required
def manage_add_walkin(request, slug):
    """AJAX: register a walk-in attendee directly from the session manage page."""
    session = get_object_or_404(InductionSession, slug=slug)
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    address = request.POST.get("address", "").strip()
    postcode = request.POST.get("postcode", "").strip()

    if not first_name:
        return JsonResponse({"ok": False, "error": "First name is required."})
    if not email:
        return JsonResponse(
            {
                "ok": False,
                "error": "Email address is required — it's needed to create a volunteer account.",
            }
        )

    name = f"{first_name} {last_name}".strip()
    signup = InductionSignup.objects.create(
        session=session,
        name=name,
        email=email,
        phone=phone,
        address=address,
        postcode=postcode,
        status=InductionSignup.STATUS_PENDING,
    )
    return JsonResponse(
        {
            "ok": True,
            "signup_id": signup.pk,
            "name": signup.name,
            "email": signup.email,
            "preview_username": signup.preview_username,
            "signed_up_at": signup.signed_up_at.strftime("%-d %b %H:%M"),
        }
    )


@require_POST
@panopticon_required
def manage_remove_signup(request, slug, signup_id):
    """AJAX: remove a pending signup (only; checked-in and no-show cannot be removed)."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)
    if signup.status != InductionSignup.STATUS_PENDING:
        return JsonResponse(
            {"ok": False, "error": "Only pending sign-ups can be removed."}
        )
    signup.delete()
    logger.info(
        f"{request.user} removed signup #{signup_id} ({signup.name}) from session '{session.title}'"
    )
    return JsonResponse({"ok": True})


@require_POST
@panopticon_required
def manage_link_existing(request, slug, signup_id):
    """AJAX: link a signup to an existing volunteer account and send a login email."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)
    existing_volunteer_id = request.POST.get("existing_volunteer_id")
    try:
        volunteer = Volunteer.objects.select_related("user").get(
            pk=existing_volunteer_id
        )
    except (Volunteer.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Volunteer not found."})

    signup.volunteer = volunteer
    signup.status = InductionSignup.STATUS_CHECKED_IN
    signup.save()

    if volunteer.user and volunteer.user.email:
        try:
            _send_password_reset_email(request, volunteer.user)
        except Exception:
            logger.exception(
                f"Password reset email failed for volunteer #{volunteer.pk}"
            )
            return JsonResponse(
                {
                    "ok": True,
                    "warning": "Linked, but the login email could not be sent.",
                }
            )

    logger.info(
        f"{request.user} linked signup #{signup.pk} ({signup.name}) to existing volunteer #{volunteer.pk}"
    )
    return JsonResponse({"ok": True})
