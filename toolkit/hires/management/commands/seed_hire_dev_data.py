# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Dev-only: hire types with PLACEHOLDER fees, upcoming meetings, flag on.

Fees here are invented so the estimate has something to multiply. Replace
them with the real FAQ prices in Hire settings > Hire types before use.
"""

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.diary.models import get_site_config
from toolkit.hires.models import (
    HireSettings,
    HireType,
    ProgrammingMeeting,
)

# name, community, corporate, unit, needs_sound_tech, provides_door_staff
TYPES = [
    ("Cinema screening", 120, 250, "flat", False, False),
    ("Gig or club night", 150, 300, "flat", True, True),
    ("Talk, workshop or meeting", 15, 30, "hour", False, False),
    ("Something else (tell us about it)", 100, 200, "flat", False, False),
]


class Command(BaseCommand):
    help = "Seed placeholder hire types and meetings; switch the flag on."

    def handle(self, *args, **opts):
        for i, (name, com, corp, unit, tech, door) in enumerate(TYPES):
            HireType.objects.get_or_create(
                name=name,
                defaults=dict(
                    community_fee_gbp=Decimal(com),
                    corporate_fee_gbp=Decimal(corp),
                    unit=unit,
                    needs_sound_tech=tech,
                    provides_door_staff=door,
                    order=i,
                ),
            )
        today = timezone.localdate()
        for weeks in (2, 6, 10):
            ProgrammingMeeting.objects.get_or_create(
                date=today + datetime.timedelta(weeks=weeks)
            )
        cfg = HireSettings.load()
        if not cfg.notification_addresses:
            cfg.notification_addresses = "programming@example.org"
            cfg.save()
        site = get_site_config()
        site.hire_enquiries_enabled = True
        site.save()
        self.stdout.write("Seeded hire dev data; hire_enquiries_enabled on.")
