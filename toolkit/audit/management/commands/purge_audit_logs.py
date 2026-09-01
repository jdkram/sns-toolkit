# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""
Purge old audit rows per the SiteConfiguration retention settings.

Run daily from the scheduler container (see containerconfig/tk_run.sh).
email_log_retain_days / deletion_log_retain_days of 0 mean "keep forever".
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.audit.models import DeletionLog, SentEmailLog
from toolkit.diary.models import get_site_config

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete SentEmailLog / DeletionLog rows older than the configured retention"

    def handle(self, *args, **options):
        config = get_site_config()
        now = timezone.now()

        for model, field_name, days in [
            (SentEmailLog, "sent_at", config.email_log_retain_days),
            (DeletionLog, "deleted_at", config.deletion_log_retain_days),
        ]:
            if not days:
                self.stdout.write(
                    f"{model.__name__}: retention disabled (0 days), keeping everything"
                )
                continue
            cutoff = now - timedelta(days=days)
            deleted, _ = model.objects.filter(
                **{f"{field_name}__lt": cutoff}
            ).delete()
            msg = f"{model.__name__}: purged {deleted} row(s) older than {days} days"
            self.stdout.write(msg)
            if deleted:
                logger.info(msg)
