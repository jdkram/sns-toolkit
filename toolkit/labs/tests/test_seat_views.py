# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 5.5"]; status: "#ai-written"
from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import get_site_config
from toolkit.labs.views.seat_views import SEAT_PHOTO_DIR, seat_photo_urls

from .common import LabsTestsMixin


class SeatViewsTests(LabsTestsMixin, TestCase):
    """Public seat views page (9.176): no login, gated on
    SiteConfiguration.seat_views_enabled."""

    def test_page_loads_without_login(self):
        response = self.client.get(reverse("labs-seat-views"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "labs/seat_views.html")

    def test_404s_when_disabled(self):
        cfg = get_site_config()
        cfg.seat_views_enabled = False
        cfg.save()
        response = self.client.get(reverse("labs-seat-views"))
        self.assertEqual(response.status_code, 404)

    def test_photo_map_matches_files_on_disk(self):
        photos = seat_photo_urls()
        on_disk = {p.stem for p in SEAT_PHOTO_DIR.glob("*.jpg")}
        self.assertEqual(set(photos), on_disk)
        self.assertIn("COMFY4", photos)
        self.assertTrue(photos["C5"].endswith(".jpg"))

    def test_photo_map_reaches_the_page(self):
        response = self.client.get(reverse("labs-seat-views"))
        self.assertContains(response, 'id="seat-views-photos"')
        self.assertContains(response, "labs/seat_views/A1")


class SeatViewsNavTests(LabsTestsMixin, TestCase):
    """The public sidebar link (under Programme) follows the same flag as
    the page."""

    def test_sidebar_link_shown_when_enabled(self):
        response = self.client.get(reverse("labs-seat-views"))
        self.assertContains(response, 'data-nav-key="s"')

    def test_sidebar_link_hidden_when_disabled(self):
        cfg = get_site_config()
        cfg.seat_views_enabled = False
        cfg.save()
        response = self.client.get(reverse("labs-donations"))
        self.assertNotContains(response, reverse("labs-seat-views"))
