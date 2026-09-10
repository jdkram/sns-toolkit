# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-input"
"""Task 9.163: Event.created_by, and the audit trail assembled from
EventAuditLog + EventTermsRevision + DeletionLog on the Event Hub."""

import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.audit.models import DeletionLog, EventAuditLog
from toolkit.diary.edit_views.events import _build_event_audit_trail
from toolkit.diary.models import Event, Showing
from toolkit.diary.tests.common import DiaryTestsMixin


class CreatedByAndCreationLog(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_add_event_sets_created_by_and_logs_creation(self):
        future_date = (timezone.now() + datetime.timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        url = reverse("add-event")
        response = self.client.post(
            url,
            data={
                "dates": future_date,
                "start_time": "20:00",
                "duration": "01:30:00",
                "event_name": "Audit Trail Test Event",
                "event_template": "1",
                "booked_by": "Someone",
                "private": "",
                "outside_hire": "",
                "discounted": "",
                "entry_mode": "standing",
            },
        )
        event = Event.objects.get(name="Audit Trail Test Event")
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": event.pk}),
        )

        self.assertEqual(event.created_by, User.objects.get(username="admin"))

        logs = EventAuditLog.objects.filter(event=event)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].action, EventAuditLog.ACTION_CREATED)
        self.assertEqual(logs[0].actor, User.objects.get(username="admin"))

    def test_clone_event_sets_created_by_and_logs_creation(self):
        source = Event.objects.create(
            name="Source Event",
            copy="Some copy",
            duration=datetime.time(1, 30),
        )
        future_start = timezone.now() + datetime.timedelta(days=30)
        url = reverse("clone-event", kwargs={"event_id": source.pk})
        response = self.client.post(
            url,
            data={
                "event_name": "Cloned Event",
                "start": future_start.strftime("%Y-%m-%d %H:%M"),
                "booked_by": "Someone",
            },
        )
        self.assertEqual(response.status_code, 302)

        cloned = Event.objects.get(name="Cloned Event")
        self.assertEqual(cloned.created_by, User.objects.get(username="admin"))

        logs = EventAuditLog.objects.filter(event=cloned)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].action, EventAuditLog.ACTION_CREATED)
        self.assertIn(str(source.pk), logs[0].detail)


class ProgrammingStatusChangeLog(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.event = Event.objects.create(
            name="Queue Event",
            copy="c",
            programming_status="draft",
        )

    def test_status_change_is_logged_with_from_to_detail(self):
        url = reverse(
            "update-event-programming-status",
            kwargs={"event_id": self.event.pk},
        )
        self.client.post(url, data={"action": "propose"})

        logs = EventAuditLog.objects.filter(event=self.event)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].action, EventAuditLog.ACTION_STATUS_CHANGED)
        self.assertEqual(logs[0].detail, "propose: draft → proposed")
        self.assertEqual(logs[0].actor, User.objects.get(username="admin"))

    def test_save_notes_only_does_not_log_a_status_change(self):
        url = reverse(
            "update-event-programming-status",
            kwargs={"event_id": self.event.pk},
        )
        self.client.post(
            url, data={"action": "save_notes", "notes": "just a note"}
        )

        self.assertEqual(
            EventAuditLog.objects.filter(event=self.event).count(), 0
        )
        self.event.refresh_from_db()
        self.assertIn("just a note", self.event.programming_notes)


class ShowingConfirmUnconfirmLog(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.event = Event.objects.create(
            name="Confirmable Event",
            copy="c",
            cost_type=Event.COST_TYPE_INTERNAL,
        )
        self.showing = Showing.objects.create(
            event=self.event,
            start=timezone.now() + datetime.timedelta(days=7),
        )

    def test_confirm_is_logged(self):
        url = reverse(
            "update-showing-status", kwargs={"showing_id": self.showing.pk}
        )
        self.client.post(url, data={"action": "confirm"})

        logs = EventAuditLog.objects.filter(event=self.event)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].action, EventAuditLog.ACTION_CONFIRMED)

    def test_unconfirm_is_logged(self):
        self.showing.confirmed = True
        self.showing.save()

        url = reverse(
            "update-showing-status", kwargs={"showing_id": self.showing.pk}
        )
        self.client.post(url, data={"action": "unconfirm"})

        logs = EventAuditLog.objects.filter(event=self.event)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].action, EventAuditLog.ACTION_UNCONFIRMED)

    def test_confirm_all_showings_writes_one_aggregate_row(self):
        Showing.objects.create(
            event=self.event,
            start=timezone.now() + datetime.timedelta(days=8),
        )
        url = reverse(
            "confirm-all-showings", kwargs={"event_id": self.event.pk}
        )
        self.client.post(url)

        logs = EventAuditLog.objects.filter(
            event=self.event, action=EventAuditLog.ACTION_CONFIRMED
        )
        self.assertEqual(logs.count(), 1)
        self.assertIn("2 showings confirmed", logs[0].detail)

    def test_confirm_all_showings_logs_nothing_when_none_to_confirm(self):
        self.showing.confirmed = True
        self.showing.save()

        url = reverse(
            "confirm-all-showings", kwargs={"event_id": self.event.pk}
        )
        self.client.post(url)

        self.assertEqual(
            EventAuditLog.objects.filter(event=self.event).count(), 0
        )


class AuditPanelVisibility(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.event = Event.objects.create(name="Panel Visibility Event")

    def test_superuser_sees_the_panel(self):
        self.client.login(username="admin", password="T3stPassword!")
        url = reverse(
            "edit-event-details-view", kwargs={"event_id": self.event.pk}
        )
        response = self.client.get(url)
        self.assertContains(response, "Audit trail")
        self.assertIsNotNone(response.context["audit_trail"])

    def test_non_superuser_does_not_see_the_panel(self):
        from toolkit.test_common import _create_toolkit_permissions

        write_perm, _read_perm = _create_toolkit_permissions()
        programmer = User.objects.create_user(
            "a_programmer", "programmer@test.example", "T3stPassword!3"
        )
        programmer.user_permissions.add(write_perm)

        self.client.login(username="a_programmer", password="T3stPassword!3")
        url = reverse(
            "edit-event-details-view", kwargs={"event_id": self.event.pk}
        )
        response = self.client.get(url)
        self.assertNotContains(response, "Audit trail")
        self.assertIsNone(response.context["audit_trail"])


class BuildEventAuditTrail(DiaryTestsMixin, TestCase):
    """Direct tests of the merge/sort logic, independent of the view."""

    def setUp(self):
        super().setUp()
        self.event = Event.objects.create(name="Merge Test Event")
        self.user = User.objects.get(username="admin")

    def test_merges_and_sorts_all_three_sources_newest_first(self):
        EventAuditLog.objects.create(
            event=self.event,
            action=EventAuditLog.ACTION_CREATED,
            actor=self.user,
        )
        self.event.terms = "Some terms text that is reasonably long."
        self.event.save()  # triggers an EventTermsRevision via signal
        DeletionLog.objects.create(
            model="Showing",
            object_pk="999",
            description=f"Booking for 'x' (event id {self.event.pk}) on 1/1/26",
            deleted_by=self.user,
            via=DeletionLog.VIA_EDIT_UI,
        )

        rows = _build_event_audit_trail(self.event)
        self.assertEqual(len(rows), 3)
        # Newest first:
        timestamps = [r["timestamp"] for r in rows]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_deletion_log_only_matches_this_events_showings(self):
        other_event = Event.objects.create(name="Other Event")
        DeletionLog.objects.create(
            model="Showing",
            object_pk="1",
            description=f"Booking for 'x' (event id {other_event.pk}) on 1/1/26",
            deleted_by=self.user,
            via=DeletionLog.VIA_EDIT_UI,
        )

        rows = _build_event_audit_trail(self.event)
        self.assertEqual(rows, [])
