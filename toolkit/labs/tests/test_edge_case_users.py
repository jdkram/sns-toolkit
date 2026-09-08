# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Labs behaviour under three "strange user" shapes that are easy to miss
when every fixture in the rest of the suite is a tidy, freshly-created
volunteer with an ordinary ASCII name:

- a logged-in user with no linked Volunteer profile at all (any superuser
  or Panopticon/Programmer-tier account, or a User created without ever
  going through volunteer induction);
- unicode, emoji, and very long text in the free-text fields labs views
  accept from any logged-in volunteer;
- a GDPR-anonymised Volunteer (Volunteer.anonymise()) whose row survives
  with de-identified data, still referenced by FKs on historical records
  (ExchangeItem.owner_volunteer, NeedFlag.flagged_by,
  ProcurementPledge.pledged_by) that were never designed to be deleted.

None of these are expected to be bugs going in — the point is to pin down
that they aren't, with a test that fails loudly if a future change makes
one of them start crashing or misbehaving.
"""

import django.contrib.auth.models as auth_models
from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import get_site_config
from toolkit.labs.models import (
    ConsumableItem,
    ExchangeItem,
    Job,
    NeedFlag,
    ProcurementPledge,
)
from toolkit.members.models import Member, Volunteer
from .common import LabsTestsMixin

# ── A: users with no linked Volunteer profile ───────────────────────────────


class NoVolunteerProfileTests(LabsTestsMixin, TestCase):
    """`self.user_admin` is a real, permitted, logged-in user — Programmer
    tier, `toolkit.write` — with no Volunteer row at all. Every labs view
    that reaches for `request.user.volunteer` needs to cope with that."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()
        self.client.login(username="admin", password="T3stPassword!")

    def test_shopping_flag_succeeds_with_no_flagged_by(self):
        item = ConsumableItem.objects.create(
            name="Hand soap", category=ConsumableItem.CATEGORY_CLEANING
        )
        response = self.client.post(
            reverse("labs-shopping-flag", kwargs={"item_id": item.pk})
        )
        self.assertRedirects(response, reverse("labs-shopping"))
        flag = NeedFlag.objects.get(item=item)
        self.assertIsNone(flag.flagged_by)
        # Rendering the item page afterwards must not crash on a None FK.
        detail = self.client.get(
            reverse("labs-shopping-item", kwargs={"item_id": item.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "someone")

    def test_shopping_pledge_and_resolve_succeed_with_no_volunteer(self):
        item = ConsumableItem.objects.create(
            name="Hand soap", category=ConsumableItem.CATEGORY_CLEANING
        )
        flag = NeedFlag.objects.create(item=item)
        self.client.post(
            reverse("labs-shopping-pledge", kwargs={"flag_id": flag.pk})
        )
        pledge = ProcurementPledge.objects.get(need_flag=flag)
        self.assertIsNone(pledge.pledged_by)

        response = self.client.post(
            reverse("labs-shopping-resolve", kwargs={"flag_id": flag.pk})
        )
        self.assertRedirects(response, reverse("labs-shopping"))
        flag.refresh_from_db()
        self.assertIsNone(flag.resolved_by)

        list_page = self.client.get(reverse("labs-shopping"))
        self.assertEqual(list_page.status_code, 200)

    def test_exchange_add_as_owner_volunteer_leaves_owner_unset(self):
        """exchange_add only auto-assigns owner_volunteer when the poster
        has a Volunteer profile; a Programmer/Panopticon account posting on
        someone else's behalf must not silently claim ownership of nothing,
        nor crash trying to."""
        response = self.client.post(
            reverse("labs-exchange-add"),
            {
                "listing_type": ExchangeItem.TYPE_GIVE,
                "name": "Spare monitor",
                "description": "",
                "category": ExchangeItem.CATEGORY_AV,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "location_notes": "",
                "status": ExchangeItem.STATUS_AVAILABLE,
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = ExchangeItem.objects.get(name="Spare monitor")
        self.assertIsNone(item.owner_volunteer)

    def test_exchange_item_view_by_non_owner_no_volunteer_shows_no_edit(self):
        item = ExchangeItem.objects.create(
            name="Old kettle",
            listing_type=ExchangeItem.TYPE_GIVE,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.vol,
        )
        response = self.client.get(
            reverse("labs-exchange-item", kwargs={"item_id": item.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_edit"])
        self.assertFalse(response.context["can_see_contact"])

    def test_collective_join_without_volunteer_profile_errors_cleanly(self):
        response = self.client.post(
            reverse(
                "labs-collective-join", kwargs={"slug": self.col_open.slug}
            ),
            follow=True,
        )
        self.assertContains(response, "volunteer profile")


# ── B: unicode, emoji, and very long text ───────────────────────────────────


class UnusualTextTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_shopping_item_name_with_emoji_and_unicode_round_trips(self):
        name = "Tofu 豆腐 🥢 (не забудь)"
        response = self.client.post(
            reverse("labs-shopping-add"),
            {"name": name, "category": ConsumableItem.CATEGORY_KITCHEN},
        )
        self.assertEqual(response.status_code, 302)
        item = ConsumableItem.objects.get(name=name)
        list_page = self.client.get(reverse("labs-shopping"))
        self.assertContains(list_page, name)
        detail = self.client.get(
            reverse("labs-shopping-item", kwargs={"item_id": item.pk})
        )
        self.assertContains(detail, name)

    def test_shopping_item_add_truncates_long_name_without_crashing(self):
        long_name = "Emergency biscuits " + ("🍪" * 200)
        response = self.client.post(
            reverse("labs-shopping-add"),
            {
                "name": long_name,
                "category": ConsumableItem.CATEGORY_SNACKS,
            },
        )
        self.assertEqual(response.status_code, 302)
        item = ConsumableItem.objects.get(name=long_name[:100])
        self.assertLessEqual(len(item.name), 100)

    def test_shopping_flag_notes_with_unicode_and_over_length_truncates(self):
        item = ConsumableItem.objects.create(
            name="Bin bags", category=ConsumableItem.CATEGORY_CLEANING
        )
        notes = "🧻" * 350
        self.client.post(
            reverse("labs-shopping-flag", kwargs={"item_id": item.pk}),
            {"notes": notes},
        )
        flag = NeedFlag.objects.get(item=item)
        self.assertLessEqual(len(flag.notes), 300)
        # Truncation lands on a whole emoji, not a broken UTF-16 surrogate
        # half — round-tripping through the DB and back must not raise.
        flag.refresh_from_db()

    def test_exchange_item_with_unicode_name_and_description_renders(self):
        response = self.client.post(
            reverse("labs-exchange-add"),
            {
                "listing_type": ExchangeItem.TYPE_GIVE,
                "name": "Café table ☕️ — “vintage”",
                "description": "Wobbly leg, très chic. 桌子.",
                "category": ExchangeItem.CATEGORY_FURNITURE,
                "condition": ExchangeItem.CONDITION_FAIR,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "location_notes": "",
                "status": ExchangeItem.STATUS_AVAILABLE,
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = ExchangeItem.objects.get(name__startswith="Café table")
        response = self.client.get(
            reverse("labs-exchange-item", kwargs={"item_id": item.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "桌子")

    def test_job_title_with_unicode_renders_in_list(self):
        Job.objects.create(
            title="Fix the projector 🎥 (número dos)",
            urgency=Job.URGENCY_HIGH,
            posted_by=self.user_admin,
        )
        response = self.client.get(reverse("labs-jobs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "🎥")

    def test_volunteer_with_unicode_name_shown_as_flagger(self):
        mem = Member.objects.create(
            name="Ƈhriƨtopher Ñoño-Müller",
            email="unicode-vol@test.example",
            number="200",
        )
        user = auth_models.User.objects.create_user(
            "unicode_vol", "unicode-vol@test.example", "T3stPassword!9"
        )
        vol = Volunteer.objects.create(member=mem, user=user)
        item = ConsumableItem.objects.create(
            name="Hand soap", category=ConsumableItem.CATEGORY_CLEANING
        )
        NeedFlag.objects.create(item=item, flagged_by=vol)

        response = self.client.get(
            reverse("labs-shopping-item", kwargs={"item_id": item.pk})
        )
        self.assertContains(response, "Ƈhriƨtopher Ñoño-Müller")


# ── C: GDPR-anonymised volunteers ───────────────────────────────────────────


class AnonymisedVolunteerTests(LabsTestsMixin, TestCase):
    """Volunteer.anonymise() scrubs the Member/Volunteer/User rows and
    disables the login, but does not delete the Volunteer row itself, so
    every FK pointing at it from labs (ExchangeItem.owner_volunteer,
    NeedFlag.flagged_by, ProcurementPledge.pledged_by, the collectives
    m2m) keeps pointing at a now-anonymous but still-real row."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()
        self.mem = Member.objects.create(
            name="Soon Anonymous", email="soon-anon@test.example", number="201"
        )
        self.user = auth_models.User.objects.create_user(
            "soon_anon", "soon-anon@test.example", "T3stPassword!8"
        )
        self.anon_vol = Volunteer.objects.create(
            member=self.mem, user=self.user
        )

    def test_exchange_item_owned_by_anonymised_volunteer_still_renders(self):
        item = ExchangeItem.objects.create(
            name="Old kettle",
            listing_type=ExchangeItem.TYPE_GIVE,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.anon_vol,
        )
        self.anon_vol.anonymise()

        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(
            reverse("labs-exchange-item", kwargs={"item_id": item.pk})
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.owner_volunteer_id, self.anon_vol.pk)
        self.assertContains(response, "Anonymised volunteer")

    def test_anonymised_volunteer_cannot_edit_their_old_listing(self):
        """Their account is disabled (is_active=False) as part of
        anonymisation, so they can no longer log in at all — can_edit
        being unreachable this way, not via a special-case check, is the
        actual guarantee this test pins down."""
        ExchangeItem.objects.create(
            name="Old kettle",
            listing_type=ExchangeItem.TYPE_GIVE,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.anon_vol,
        )
        self.anon_vol.anonymise()
        self.assertFalse(
            self.client.login(username="soon_anon", password="T3stPassword!8")
        )

    def test_shopping_flag_by_anonymised_volunteer_still_renders(self):
        item = ConsumableItem.objects.create(
            name="Bin bags", category=ConsumableItem.CATEGORY_CLEANING
        )
        flag = NeedFlag.objects.create(item=item, flagged_by=self.anon_vol)
        ProcurementPledge.objects.create(
            need_flag=flag, pledged_by=self.anon_vol
        )
        self.anon_vol.anonymise()

        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(
            reverse("labs-shopping-item", kwargs={"item_id": item.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "labs/shopping_item.html")
        list_page = self.client.get(reverse("labs-shopping"))
        self.assertEqual(list_page.status_code, 200)
        self.assertTemplateUsed(list_page, "labs/shopping.html")

    def test_anonymise_clears_collective_memberships(self):
        self.anon_vol.collectives.add(self.col_open)
        self.anon_vol.anonymise()
        self.assertEqual(self.anon_vol.collectives.count(), 0)

    def test_anonymised_volunteer_excluded_from_exchange_owner_picker(self):
        self.anon_vol.anonymise()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange-add"))
        self.assertNotIn(
            self.anon_vol,
            list(response.context["form"].fields["owner_volunteer"].queryset),
        )
