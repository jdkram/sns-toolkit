# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Functional coverage for lost & found's browse/claim/dispose/label flows.
test_photo_uploads.py already covers the logging form's photo handling;
everything else here was untested (Chunk 10 of the quality pass —
docs/ARCHIVE/QUALITY_BASELINE_2026_09.md measured this at ~0% outside the photo-upload
paths)."""

import datetime

from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import get_site_config
from toolkit.labs.models import FoundItem
from .common import LabsTestsMixin


class LostAndFoundGateTests(LabsTestsMixin, TestCase):
    """Toggling SiteConfiguration.lost_and_found_enabled off 404s the log,
    the list, and the detail/claim/dispose/label flows alike."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.lost_and_found_enabled = False
        cfg.save()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_log_404s_when_disabled(self):
        response = self.client.get(reverse("labs-found-item-log"))
        self.assertEqual(response.status_code, 404)

    def test_list_404s_when_disabled(self):
        response = self.client.get(reverse("labs-found-items"))
        self.assertEqual(response.status_code, 404)

    def test_enabled_by_default(self):
        cfg = get_site_config()
        cfg.lost_and_found_enabled = True
        cfg.save()
        response = self.client.get(reverse("labs-found-items"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "labs/found_items.html")


class FoundItemLogFormTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_get_prefills_logged_by_with_current_user(self):
        response = self.client.get(reverse("labs-found-item-log"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].initial.get("logged_by"), "volunteer"
        )


class FoundItemListTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.unclaimed = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Blue umbrella",
            location_found="Café",
            logged_by="Test Volunteer",
        )
        self.claimed = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Red scarf",
            location_found="Cinema",
            logged_by="Test Volunteer",
            status=FoundItem.STATUS_CLAIMED,
            claimed_by="Alice",
            claimed_on=datetime.date.today(),
        )
        self.disposed = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Old umbrella",
            location_found="Bar",
            logged_by="Test Volunteer",
            status=FoundItem.STATUS_DISPOSED,
            disposed_on=datetime.date.today(),
            disposal_method=FoundItem.DISPOSAL_BINNED,
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_default_tab_shows_unclaimed_only(self):
        response = self.client.get(reverse("labs-found-items"))
        self.assertEqual(response.status_code, 200)
        items = list(response.context["items"])
        self.assertEqual(items, [self.unclaimed])
        self.assertEqual(response.context["tab"], "unclaimed")

    def test_claimed_tab_shows_claimed_only(self):
        response = self.client.get(
            reverse("labs-found-items"), {"tab": "claimed"}
        )
        self.assertEqual(list(response.context["items"]), [self.claimed])

    def test_disposed_tab_shows_disposed_only(self):
        response = self.client.get(
            reverse("labs-found-items"), {"tab": "disposed"}
        )
        self.assertEqual(list(response.context["items"]), [self.disposed])

    def test_invalid_tab_falls_back_to_unclaimed(self):
        response = self.client.get(
            reverse("labs-found-items"), {"tab": "not-a-real-tab"}
        )
        self.assertEqual(response.context["tab"], "unclaimed")
        self.assertEqual(list(response.context["items"]), [self.unclaimed])


class FoundItemDetailTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Blue umbrella",
            location_found="Café",
            logged_by="Test Volunteer",
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_detail_renders(self):
        response = self.client.get(
            reverse("labs-found-item", kwargs={"item_id": self.item.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blue umbrella")
        self.assertIn("claim_form", response.context)
        self.assertIn("dispose_form", response.context)


class FoundItemClaimTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Blue umbrella",
            location_found="Café",
            logged_by="Test Volunteer",
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_claim_marks_item_claimed(self):
        response = self.client.post(
            reverse("labs-found-item-claim", kwargs={"item_id": self.item.pk}),
            {"claimed_by": "Alice"},
        )
        self.assertRedirects(
            response,
            reverse("labs-found-item", kwargs={"item_id": self.item.pk}),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, FoundItem.STATUS_CLAIMED)
        self.assertEqual(self.item.claimed_by, "Alice")
        self.assertEqual(self.item.claimed_on, datetime.date.today())

    def test_claim_missing_claimed_by_does_not_change_status(self):
        response = self.client.post(
            reverse("labs-found-item-claim", kwargs={"item_id": self.item.pk}),
            {"claimed_by": ""},
        )
        self.assertRedirects(
            response,
            reverse("labs-found-item", kwargs={"item_id": self.item.pk}),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, FoundItem.STATUS_UNCLAIMED)

    def test_claiming_already_claimed_item_404s(self):
        self.item.status = FoundItem.STATUS_CLAIMED
        self.item.save()
        response = self.client.post(
            reverse("labs-found-item-claim", kwargs={"item_id": self.item.pk}),
            {"claimed_by": "Alice"},
        )
        self.assertEqual(response.status_code, 404)


class FoundItemDisposeTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Old umbrella",
            location_found="Bar",
            logged_by="Test Volunteer",
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_dispose_marks_item_disposed(self):
        response = self.client.post(
            reverse(
                "labs-found-item-dispose", kwargs={"item_id": self.item.pk}
            ),
            {"disposal_method": FoundItem.DISPOSAL_BINNED},
        )
        self.assertRedirects(response, reverse("labs-found-items"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, FoundItem.STATUS_DISPOSED)
        self.assertEqual(self.item.disposal_method, FoundItem.DISPOSAL_BINNED)
        self.assertEqual(self.item.disposed_on, datetime.date.today())

    def test_dispose_invalid_method_does_not_change_status(self):
        response = self.client.post(
            reverse(
                "labs-found-item-dispose", kwargs={"item_id": self.item.pk}
            ),
            {"disposal_method": "not-a-real-method"},
        )
        self.assertRedirects(response, reverse("labs-found-items"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, FoundItem.STATUS_UNCLAIMED)

    def test_disposing_already_disposed_item_404s(self):
        self.item.status = FoundItem.STATUS_DISPOSED
        self.item.save()
        response = self.client.post(
            reverse(
                "labs-found-item-dispose", kwargs={"item_id": self.item.pk}
            ),
            {"disposal_method": FoundItem.DISPOSAL_BINNED},
        )
        self.assertEqual(response.status_code, 404)


class FoundItemLabelTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Blue umbrella",
            location_found="Café",
            logged_by="Test Volunteer",
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_label_renders(self):
        response = self.client.get(
            reverse("labs-found-item-label", kwargs={"item_id": self.item.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.label_id)


class FoundItemModelTests(TestCase):
    def test_label_id_is_zero_padded(self):
        item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Test item",
            location_found="Bar",
            logged_by="Test Volunteer",
        )
        self.assertEqual(item.label_id, f"L-{item.pk:03d}")

    def test_status_display_uses_lost_report_labels(self):
        item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_LOST,
            description="Wallet",
            location_found="Unknown",
            logged_by="Reporter",
            status=FoundItem.STATUS_CLAIMED,
        )
        self.assertEqual(item.status_display(), "Reunited")

    def test_status_display_uses_found_report_labels(self):
        item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Umbrella",
            location_found="Bar",
            logged_by="Volunteer",
            status=FoundItem.STATUS_CLAIMED,
        )
        self.assertEqual(item.status_display(), item.get_status_display())

    def test_is_overdue_false_for_claimed_item(self):
        item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Umbrella",
            location_found="Bar",
            logged_by="Volunteer",
            found_on=datetime.date(2000, 1, 1),
            status=FoundItem.STATUS_CLAIMED,
        )
        self.assertFalse(item.is_overdue)

    def test_is_overdue_false_for_lost_report(self):
        item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_LOST,
            description="Wallet",
            location_found="Unknown",
            logged_by="Reporter",
            found_on=datetime.date(2000, 1, 1),
        )
        self.assertFalse(item.is_overdue)

    def test_is_overdue_true_for_old_unclaimed_found_item(self):
        item = FoundItem.objects.create(
            report_type=FoundItem.TYPE_FOUND,
            description="Umbrella",
            location_found="Bar",
            logged_by="Volunteer",
            found_on=datetime.date(2000, 1, 1),
        )
        self.assertTrue(item.is_overdue)
