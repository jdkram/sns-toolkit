# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Coverage for community exchange's state-transition actions
(mark_on_loan/mark_returned/mark_all_gone/mark_missing) — the gap
docs/QUALITY_LABS_SCOPE.md identified as where a shared-item-lifecycle bug
would actually live. Chunk 10 of the quality pass, fourth and final labs
target."""

import django.contrib.auth.models as auth_models
from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import get_site_config
from toolkit.labs.models import ExchangeItem
from toolkit.members.models import Member, Volunteer
from .common import LabsTestsMixin


class ExchangeEnabledMixin(LabsTestsMixin):
    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()


class ExchangeItemDetailContactTests(ExchangeEnabledMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = ExchangeItem.objects.create(
            name="Old kettle",
            listing_type=ExchangeItem.TYPE_GIVE,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.vol,
            added_by=self.user_vol,
        )

    def test_lister_can_see_contact(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.get(
            reverse("labs-exchange-item", kwargs={"item_id": self.item.pk})
        )
        self.assertTrue(response.context["can_see_contact"])

    def test_other_volunteer_cannot_see_contact(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(
            reverse("labs-exchange-item", kwargs={"item_id": self.item.pk})
        )
        self.assertFalse(response.context["can_see_contact"])

    def test_disabled_feature_404s(self):
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(
            reverse("labs-exchange-item", kwargs={"item_id": self.item.pk})
        )
        self.assertEqual(response.status_code, 404)


class ExchangeEditGateAndAutoOwnerTests(ExchangeEnabledMixin, TestCase):
    def test_edit_disabled_feature_404s(self):
        item = ExchangeItem.objects.create(
            name="Old kettle", listing_type=ExchangeItem.TYPE_GIVE
        )
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(
            reverse("labs-exchange-edit", kwargs={"item_id": item.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_withdraw_disabled_feature_404s(self):
        item = ExchangeItem.objects.create(
            name="Old kettle", listing_type=ExchangeItem.TYPE_GIVE
        )
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.post(
            reverse("labs-exchange-withdraw", kwargs={"item_id": item.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_add_auto_assigns_owner_volunteer_when_unset(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(
            reverse("labs-exchange-add"),
            {
                "listing_type": ExchangeItem.TYPE_GIVE,
                "name": "Spare chair",
                "description": "",
                "category": ExchangeItem.CATEGORY_FURNITURE,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "location_notes": "",
                "status": ExchangeItem.STATUS_AVAILABLE,
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = ExchangeItem.objects.get(name="Spare chair")
        self.assertEqual(item.owner_volunteer, self.vol)


class ExchangeMarkOnLoanTests(ExchangeEnabledMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = ExchangeItem.objects.create(
            name="DeWalt drill",
            listing_type=ExchangeItem.TYPE_LEND,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.vol,
            added_by=self.user_vol,
        )
        self.client.login(username="admin", password="T3stPassword!")

    def _url(self):
        return reverse(
            "labs-exchange-mark-on-loan", kwargs={"item_id": self.item.pk}
        )

    def test_marks_item_on_loan(self):
        response = self.client.post(
            self._url(),
            {
                "borrowed_by_name": "Alice",
                "borrowed_by_contact": "07000000000",
            },
        )
        self.assertRedirects(
            response,
            reverse("labs-exchange-item", kwargs={"item_id": self.item.pk}),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_ON_LOAN)
        self.assertEqual(self.item.borrowed_by_name, "Alice")
        self.assertEqual(self.item.borrowed_by_contact, "07000000000")
        self.assertEqual(self.item.borrowed_by, self.user_admin)

    def test_give_item_rejected(self):
        give_item = ExchangeItem.objects.create(
            name="Old kettle", listing_type=ExchangeItem.TYPE_GIVE
        )
        response = self.client.post(
            reverse(
                "labs-exchange-mark-on-loan",
                kwargs={"item_id": give_item.pk},
            ),
            {"borrowed_by_name": "Alice", "borrowed_by_contact": "x"},
        )
        self.assertEqual(response.status_code, 403)

    def test_already_on_loan_shows_warning_and_does_not_change(self):
        self.item.status = ExchangeItem.STATUS_ON_LOAN
        self.item.borrowed_by_name = "Bob"
        self.item.save()
        self.client.post(
            self._url(),
            {"borrowed_by_name": "Alice", "borrowed_by_contact": "x"},
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.borrowed_by_name, "Bob")

    def test_missing_name_errors(self):
        self.client.post(self._url(), {"borrowed_by_contact": "07000000000"})
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_AVAILABLE)

    def test_missing_contact_errors(self):
        self.client.post(self._url(), {"borrowed_by_name": "Alice"})
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_AVAILABLE)

    def test_any_logged_in_volunteer_can_mark_on_loan(self):
        """R14: intentionally open to any logged-in volunteer, not just the
        owner — a shared-resource default, not an oversight."""
        self.client.logout()
        self.client.login(username="volunteer", password="T3stPassword!3")
        self.client.post(
            self._url(),
            {"borrowed_by_name": "Alice", "borrowed_by_contact": "x"},
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_ON_LOAN)

    def test_disabled_feature_404s(self):
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 404)


class ExchangeMarkReturnedTests(ExchangeEnabledMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = ExchangeItem.objects.create(
            name="DeWalt drill",
            listing_type=ExchangeItem.TYPE_LEND,
            status=ExchangeItem.STATUS_ON_LOAN,
            borrowed_by=self.user_vol,
            borrowed_by_name="Alice",
            borrowed_by_contact="07000000000",
        )
        self.client.login(username="admin", password="T3stPassword!")

    def _url(self):
        return reverse(
            "labs-exchange-mark-returned", kwargs={"item_id": self.item.pk}
        )

    def test_marks_returned_and_clears_borrower(self):
        response = self.client.post(self._url())
        self.assertRedirects(
            response,
            reverse("labs-exchange-item", kwargs={"item_id": self.item.pk}),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_AVAILABLE)
        self.assertIsNone(self.item.borrowed_by)
        self.assertEqual(self.item.borrowed_by_name, "")
        self.assertEqual(self.item.borrowed_by_contact, "")

    def test_missing_item_can_also_be_returned(self):
        self.item.status = ExchangeItem.STATUS_MISSING
        self.item.save()
        self.client.post(self._url())
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_AVAILABLE)

    def test_available_item_shows_warning_and_is_unchanged(self):
        self.item.status = ExchangeItem.STATUS_AVAILABLE
        self.item.borrowed_by_name = ""
        self.item.save()
        self.client.post(self._url())
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_AVAILABLE)

    def test_give_item_rejected(self):
        give_item = ExchangeItem.objects.create(
            name="Old kettle", listing_type=ExchangeItem.TYPE_GIVE
        )
        response = self.client.post(
            reverse(
                "labs-exchange-mark-returned",
                kwargs={"item_id": give_item.pk},
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_disabled_feature_404s(self):
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 404)


class ExchangeMarkAllGoneTests(ExchangeEnabledMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = ExchangeItem.objects.create(
            name="Homegrown tomatoes",
            listing_type=ExchangeItem.TYPE_SHARE,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.vol,
        )

    def _url(self, item=None):
        return reverse(
            "labs-exchange-mark-all-gone",
            kwargs={"item_id": (item or self.item).pk},
        )

    def test_owner_marks_all_gone(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(self._url())
        self.assertRedirects(response, reverse("labs-exchange"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_ALL_GONE)

    def test_superuser_marks_all_gone(self):
        self.user_admin.is_superuser = True
        self.user_admin.save()
        self.client.login(username="admin", password="T3stPassword!")
        self.client.post(self._url())
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_ALL_GONE)

    def test_non_owner_forbidden(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_AVAILABLE)

    def test_lend_item_rejected(self):
        lend_item = ExchangeItem.objects.create(
            name="Drill",
            listing_type=ExchangeItem.TYPE_LEND,
            owner_volunteer=self.vol,
        )
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(self._url(lend_item))
        self.assertEqual(response.status_code, 403)

    def test_disabled_feature_404s(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 404)


class ExchangeMarkMissingTests(ExchangeEnabledMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = ExchangeItem.objects.create(
            name="DeWalt drill",
            listing_type=ExchangeItem.TYPE_LEND,
            status=ExchangeItem.STATUS_ON_LOAN,
            owner_volunteer=self.vol,
        )

    def _url(self):
        return reverse(
            "labs-exchange-mark-missing", kwargs={"item_id": self.item.pk}
        )

    def test_owner_marks_missing(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(self._url())
        self.assertRedirects(
            response,
            reverse("labs-exchange-item", kwargs={"item_id": self.item.pk}),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_MISSING)

    def test_non_owner_forbidden(self):
        mem2 = Member.objects.create(
            name="Other Vol", email="other2@test.example", number="101"
        )
        user2 = auth_models.User.objects.create_user(
            "other_vol2", "other2@test.example", "T3stPassword!5"
        )
        Volunteer.objects.create(member=mem2, user=user2)
        self.client.login(username="other_vol2", password="T3stPassword!5")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_ON_LOAN)

    def test_superuser_can_mark_missing(self):
        self.user_admin.is_superuser = True
        self.user_admin.save()
        self.client.login(username="admin", password="T3stPassword!")
        self.client.post(self._url())
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExchangeItem.STATUS_MISSING)

    def test_disabled_feature_404s(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 404)
