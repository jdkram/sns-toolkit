# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Retention: delete hirers' personal data when the notice says we will.

Rules (docs/tasks/hires.md, "Data protection"):
- Declined, withdrawn or timed-out enquiries lose their personal fields
  ``declined_purge_months`` after closing. The shape (type, dates, outcome)
  stays for statistics.
- Booked or completed hires lose contact details ``hirer_purge_years`` after
  the hire. The frozen agreed terms, the fee and the linked event are
  financial records (kept six years) and stay.
- ``Hirer`` records go ``hirer_purge_years`` after the last activity, unless
  an enquiry of theirs is still open.
- Open enquiries are never touched.

Deliberately NOT gated by the hire_enquiries_enabled flag: a retention
promise must not lapse because someone switched the feature off.
"""

import logging

from django.db import transaction
from django.utils import timezone

from toolkit.audit.models import DeletionLog, log_deletion

from .models import HireEnquiry, Hirer, get_hire_settings

logger = logging.getLogger(__name__)
E = HireEnquiry

DELETED = "[deleted]"


def anonymise_enquiry(enquiry, now=None):
    """Blank every personal or free-text field on one enquiry."""
    keep_title = enquiry.keeps_financial_record
    enquiry.contact_name = DELETED
    enquiry.contact_organisation = ""
    enquiry.contact_email = ""
    enquiry.contact_phone = ""
    enquiry.description = DELETED
    enquiry.flexibility_notes = ""
    enquiry.offers_to_volunteers = ""
    enquiry.media_url = ""
    enquiry.sound_tech_name = ""
    enquiry.internal_notes = ""
    enquiry.custom_answers = []
    enquiry.callout_what_we_need = ""
    enquiry.agreement_token = ""
    enquiry.terms_agreed_ip = None
    enquiry.hirer = None
    if not keep_title:
        enquiry.title = "Deleted enquiry"
        enquiry.terms_agreed_snapshot = ""
    enquiry.personal_data_purged_at = now or timezone.now()
    enquiry.save()


def _hirer_last_activity(hirer):
    last = timezone.localtime(hirer.last_activity_at).date()
    for e in hirer.enquiries.all():
        ref = e.retention_reference_date()
        if ref is None:
            return None  # an open enquiry: leave the hirer alone
        last = max(last, ref)
    return last


def purge_expired(today=None, dry_run=False, cfg=None):
    cfg = cfg or get_hire_settings()
    today = today or timezone.localdate()
    now = timezone.now()
    out = {"enquiries": 0, "hirers": 0}

    candidates = (
        E.objects.filter(personal_data_purged_at__isnull=True)
        .filter(status__in=E.CLOSED_NEGATIVE + (E.BOOKED, E.COMPLETED))
        .prefetch_related("hire_dates")
    )
    for enquiry in candidates:
        due = enquiry.purge_due_on(cfg)
        if due is None or due > today:
            continue
        out["enquiries"] += 1
        if dry_run:
            continue
        with transaction.atomic():
            # Describe it before wiping, with no personal data in the text.
            description = (
                f"Hire enquiry #{enquiry.pk} personal data anonymised "
                f"({enquiry.get_status_display()}, retention date {due})"
            )
            anonymise_enquiry(enquiry, now)
            log_deletion(
                "HireEnquiry",
                enquiry.pk,
                description,
                via=DeletionLog.VIA_MANAGEMENT_COMMAND,
            )

    cutoff_days = int(cfg.hirer_purge_years * 365.25)
    for hirer in Hirer.objects.prefetch_related("enquiries__hire_dates"):
        last = _hirer_last_activity(hirer)
        if last is None or (today - last).days < cutoff_days:
            continue
        out["hirers"] += 1
        if dry_run:
            continue
        with transaction.atomic():
            pk = hirer.pk
            hirer.delete()
            log_deletion(
                "Hirer",
                pk,
                f"Hirer #{pk} deleted after {cfg.hirer_purge_years} years "
                "without activity",
                via=DeletionLog.VIA_MANAGEMENT_COMMAND,
            )
    return out
