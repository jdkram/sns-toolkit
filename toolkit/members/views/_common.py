# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""
Shared helpers for the volunteer views subpackage.

volunteer_views.py was split per-feature in June 2026. Each submodule
imports what it actually uses directly from here (`logger`,
`_render_admin_email`, `_notify_vols_admin_status_change`) and from the
real source modules. No wildcard import: this file used to be a
`from ._common import *` re-export hub, which hid where every symbol came
from, and was un-starred in September 2026.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _render_admin_email(template, name, venue):
    """Substitute {name} and {venue} placeholders in an admin-configured email template.

    Used for last-gasp and suspension emails whose subject/body are editable
    in Site settings. Plain .replace (not str.format) so stray { } chars in
    admin text don't crash rendering.
    """
    return template.replace("{name}", name).replace("{venue}", venue)


def _notify_vols_admin_status_change(request, vol, now_active):
    # Volunteer status (active / dormant / retired) is edited on the volunteer's
    # own profile page. When that change moves a volunteer on or off the active
    # roster, email the volunteers admin so the mailing list can be kept in step.
    # No-op when no vols_admin_address is configured.
    vols_admin = settings.VENUE.get("vols_admin_address") or []

    # vols_admin_address must be a list of single addresses, not a
    # comma-joined string (send_mail iterates recipient_list character by
    # character if given a bare string) and not a list containing a
    # comma-joined element (this exact typo -- "a@x.com, b@y.com" as one
    # list entry -- broke volunteer-add on the s+s branch in production).
    if isinstance(vols_admin, str) or any("," in addr for addr in vols_admin):
        logger.error(
            "vols_admin_address is misconfigured (expected a list of single "
            "addresses, got %r); skipping volunteers-admin notification "
            "rather than sending to a garbled address.",
            vols_admin,
        )
        return

    if not vols_admin:
        return

    status_label = vol.get_status_display()
    if now_active:
        action_line = (
            f"to {status_label}.\n\n"
            f"Please add them back to the volunteers mailing list "
            f"at your earliest convenience."
        )
    else:
        action_line = (
            f"to {status_label}.\n\n"
            f"Please remove them from the volunteers mailing list "
            f"at your earliest convenience."
        )
    admin_body = (
        f"{request.user.last_name} has updated the status of volunteer\n\n"
        f"{vol.member.name} <{vol.member.email}>\n\n"
        f"{action_line}"
    )
    # An SMTP failure here must not 500 the volunteer save that triggered it.
    try:
        send_mail(
            f"[{settings.VENUE['longname']}] Change in volunteer status {vol.member.name}",
            admin_body,
            settings.VENUE["mailout_from_address"],
            vols_admin,
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            f"Failed to notify vols admin of status change for volunteer pk={vol.pk}"
        )
        messages.warning(
            request,
            "Saved, but the notification email to the volunteers admin failed "
            "to send. They may need to be told about this change manually.",
        )
