# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.core.management.base import BaseCommand

from toolkit.hires import purge


class Command(BaseCommand):
    help = (
        "Delete hirers' personal data once the retention periods in Hire "
        "settings have passed. Runs even when the feature flag is off."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count what would be deleted without deleting anything.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        result = purge.purge_expired(dry_run=dry)
        prefix = "[dry-run] Would delete" if dry else "Deleted"
        self.stdout.write(
            f"{prefix}: personal data on {result['enquiries']} "
            f"enquiry(ies), {result['hirers']} hirer record(s)."
        )
