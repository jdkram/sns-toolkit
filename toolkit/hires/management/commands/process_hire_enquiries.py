# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.core.management.base import BaseCommand

from toolkit.audit.models import set_email_trigger
from toolkit.hires import services


class Command(BaseCommand):
    help = (
        "Daily hire-enquiry clock: pre-meeting digest, last call, honest "
        "auto-decline at the deadline, maybe-callout timeouts. A no-op while "
        "the feature flag is off."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        set_email_trigger("Scheduled job: process_hire_enquiries")
        result = services.run_clock(dry_run=opts["dry_run"])
        self.stdout.write(str(result))
