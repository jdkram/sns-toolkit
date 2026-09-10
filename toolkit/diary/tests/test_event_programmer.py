"""Tests for 9.169: Event.programmer, the rota auto-populate hook, the
Event Hub completeness nag, and the SiteConfiguration-gated hard block."""

import datetime
import zoneinfo

import django.contrib.auth.models as auth_models
from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import (
    Event,
    Role,
    RotaEntry,
    Showing,
    get_site_config,
)
from toolkit.diary.tests.common import DiaryTestsMixin, NowPatchMixin
from toolkit.members.models import Member, Volunteer

UKTZ = zoneinfo.ZoneInfo("Europe/London")


class EventHasFinancialTermsTests(TestCase):
    def test_false_by_default(self):
        event = Event(name="Bare event")
        event.save()
        self.assertFalse(event.has_financial_terms())

    def test_true_when_cost_type_set(self):
        event = Event(
            name="Priced event", cost_type=Event.COST_TYPE_FILM_LICENSE
        )
        event.save()
        self.assertTrue(event.has_financial_terms())

    def test_false_when_cost_type_tbc(self):
        event = Event(name="TBC event", cost_type=Event.COST_TYPE_TBC)
        event.save()
        self.assertFalse(event.has_financial_terms())

    def test_false_when_no_financial_activity_ticked_despite_cost_type(self):
        # The checkbox is an explicit override -- wins even over a cost type
        # that was set (e.g. left over from an earlier edit).
        event = Event(
            name="Cleaning Club",
            cost_type=Event.COST_TYPE_FILM_LICENSE,
            no_financial_activity=True,
        )
        event.save()
        self.assertFalse(event.has_financial_terms())


class ProgrammerContactRotaSyncTests(NowPatchMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.programmer_role = Role(
            name="Programmer contact", programmer_contact=True
        )
        self.programmer_role.save()
        self.other_role = Role(name="Ordinary shift")
        self.other_role.save()

        user = auth_models.User.objects.create_user("prog1", "", "testpass")
        member = Member(
            name="Prog One",
            email="prog1@example.test",
            address="",
            posttown="",
            postcode="",
            country="",
            phone="",
            website="",
        )
        member.save()
        self.volunteer = Volunteer(member=member, user=user)
        self.volunteer.save()

        self.event = Event(name="Test event")
        self.event.save()

        self.future_showing = Showing(
            start=self._fake_now + datetime.timedelta(days=7),
            event=self.event,
            booked_by="Someone",
        )
        self.future_showing.save()

        self.past_showing = Showing(
            start=self._fake_now - datetime.timedelta(days=7),
            event=self.event,
            booked_by="Someone",
        )
        self.past_showing.save(force=True)

    def test_new_programmer_contact_entry_auto_populated_from_event(self):
        self.event.programmer = self.volunteer
        self.event.save()

        entry = RotaEntry(
            role=self.programmer_role, showing=self.future_showing
        )
        entry.save()

        self.assertEqual(entry.volunteer, self.volunteer)
        self.assertEqual(entry.name, "Prog One")

    def test_new_entry_for_ordinary_role_not_touched(self):
        self.event.programmer = self.volunteer
        self.event.save()

        entry = RotaEntry(role=self.other_role, showing=self.future_showing)
        entry.save()

        self.assertIsNone(entry.volunteer)
        self.assertEqual(entry.name, "")

    def test_new_programmer_contact_entry_left_blank_when_no_programmer(self):
        entry = RotaEntry(
            role=self.programmer_role, showing=self.future_showing
        )
        entry.save()

        self.assertIsNone(entry.volunteer)
        self.assertEqual(entry.name, "")

    def test_existing_signup_not_overwritten_on_resave(self):
        other_user = auth_models.User.objects.create_user(
            "prog2", "", "testpass"
        )
        other_member = Member(
            name="Prog Two",
            email="prog2@example.test",
            address="",
            posttown="",
            postcode="",
            country="",
            phone="",
            website="",
        )
        other_member.save()
        other_volunteer = Volunteer(member=other_member, user=other_user)
        other_volunteer.save()

        self.event.programmer = self.volunteer
        self.event.save()

        entry = RotaEntry(
            role=self.programmer_role,
            showing=self.future_showing,
            volunteer=other_volunteer,
            name="Prog Two",
        )
        entry.save()
        # Re-save an already-signed-up entry: must not be clobbered back to
        # the event's programmer.
        entry.save()

        self.assertEqual(entry.volunteer, other_volunteer)
        self.assertEqual(entry.name, "Prog Two")

    def test_sync_updates_future_showings_only(self):
        future_entry = RotaEntry(
            role=self.programmer_role, showing=self.future_showing
        )
        future_entry.save()
        past_entry = RotaEntry(
            role=self.programmer_role, showing=self.past_showing
        )
        past_entry.save()

        self.event.programmer = self.volunteer
        self.event.save()
        self.event.sync_programmer_contact_rota()

        future_entry.refresh_from_db()
        past_entry.refresh_from_db()
        self.assertEqual(future_entry.volunteer, self.volunteer)
        self.assertEqual(future_entry.name, "Prog One")
        self.assertIsNone(past_entry.volunteer)
        self.assertEqual(past_entry.name, "")

    def test_sync_clears_future_entries_when_programmer_unset(self):
        entry = RotaEntry(
            role=self.programmer_role, showing=self.future_showing
        )
        entry.volunteer = self.volunteer
        entry.name = "Prog One"
        entry.save()

        self.event.programmer = None
        self.event.save()
        self.event.sync_programmer_contact_rota()

        entry.refresh_from_db()
        self.assertIsNone(entry.volunteer)
        self.assertEqual(entry.name, "")


class EventHubProgrammerChecklistTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_no_programmer_badge_shown_when_unset(self):
        response = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(response, "No programmer set")

    def test_no_programmer_badge_hidden_once_set(self):
        self.e4.programmer = Volunteer.objects.first()
        self.e4.save()
        response = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertNotContains(response, "No programmer set")


class EventProgrammerHardBlockTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def _post_event(self, event_id, overrides=None):
        url = reverse("edit-event-details", kwargs={"event_id": event_id})
        event = Event.objects.get(pk=event_id)
        data = {
            "name": event.name,
            "duration": "01:00:00",
            "terms": event.terms or "",
            "copy": event.copy or "",
            "copy_summary": event.copy_summary or "",
            "pricing": event.pricing or "",
            "pre_title": event.pre_title or "",
            "post_title": event.post_title or "",
            "film_information": event.film_information or "",
            "programming_status": event.programming_status or "idea",
            "approval_type": event.approval_type or "",
        }
        if overrides:
            data.update(overrides)
        return self.client.post(url, data, follow=True)

    def test_no_block_when_flag_off(self):
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.programmer_required_for_financial_events = False
        cfg.save()
        resp = self._post_event(
            self.e5.pk,
            {"cost_type": Event.COST_TYPE_FILM_LICENSE},
        )
        self.assertRedirects(
            resp,
            reverse(
                "edit-event-details-view", kwargs={"event_id": self.e5.pk}
            ),
        )

    def test_no_block_when_no_financial_terms(self):
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.programmer_required_for_financial_events = True
        cfg.save()
        resp = self._post_event(
            self.e5.pk,
            {"cost_type": Event.COST_TYPE_TBC},
        )
        form = resp.context.get("event_form") if resp.context else None
        if form:
            self.assertNotIn("programmer", form.errors)

    def test_blocked_when_financial_terms_and_no_programmer(self):
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.programmer_required_for_financial_events = True
        cfg.save()
        resp = self._post_event(
            self.e5.pk,
            {"cost_type": Event.COST_TYPE_FILM_LICENSE},
        )
        form = resp.context.get("event_form") if resp.context else None
        self.assertIsNotNone(form)
        self.assertIn("programmer", form.errors)

    def test_no_block_when_no_financial_activity_ticked(self):
        # Cost type set but the event is explicitly flagged as having no
        # financial activity -- the checkbox should win over the cost type.
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.programmer_required_for_financial_events = True
        cfg.save()
        resp = self._post_event(
            self.e5.pk,
            {
                "cost_type": Event.COST_TYPE_FILM_LICENSE,
                "no_financial_activity": "on",
            },
        )
        self.assertRedirects(
            resp,
            reverse(
                "edit-event-details-view", kwargs={"event_id": self.e5.pk}
            ),
        )

    def test_no_financial_activity_waives_cost_type_required(self):
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.structured_cost_required = True
        cfg.save()
        resp = self._post_event(
            self.e5.pk,
            {
                "cost_type": Event.COST_TYPE_TBC,
                "no_financial_activity": "on",
            },
        )
        # No cost_type error, no terms-too-short error -- both waived by the
        # checkbox, so the save goes through and redirects.
        self.assertRedirects(
            resp,
            reverse(
                "edit-event-details-view", kwargs={"event_id": self.e5.pk}
            ),
        )

    def test_not_blocked_when_programmer_set(self):
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.programmer_required_for_financial_events = True
        cfg.save()
        volunteer = Volunteer.objects.first()
        resp = self._post_event(
            self.e5.pk,
            {
                "cost_type": Event.COST_TYPE_FILM_LICENSE,
                "programmer": volunteer.pk,
            },
        )
        # Successful save redirects -- confirms no "programmer" error blocked it.
        self.assertRedirects(
            resp,
            reverse(
                "edit-event-details-view", kwargs={"event_id": self.e5.pk}
            ),
        )
