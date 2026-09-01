# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Tests for the audit app: SentEmailLog (9.156) and DeletionLog (9.159)."""
import datetime
from unittest.mock import patch

from django.core.mail import send_mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from toolkit.audit.models import (
    DeletionLog,
    SentEmailLog,
    record_email,
    summarise_email_batch,
)
from toolkit.audit.signals import suppress_event_deletion_log
from toolkit.diary.models import Event, Showing
from toolkit.diary.tests.common import DiaryTestsMixin
from toolkit.members.tests.common import MembersTestsMixin

WRAPPER = "toolkit.util.email_backend.LoggingEmailBackend"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@override_settings(EMAIL_BACKEND=WRAPPER)
class SentEmailLogTests(TestCase):
    @override_settings(TOOLKIT_WRAPPED_EMAIL_BACKEND=LOCMEM)
    def test_successful_send_creates_row(self):
        send_mail("Audit row", "body", "from@example.com", ["to@example.com"])
        log = SentEmailLog.objects.get()
        self.assertEqual(log.recipients, "to@example.com")
        self.assertEqual(log.subject, "Audit row")
        self.assertTrue(log.success)
        self.assertEqual(log.error, "")
        self.assertEqual(log.backend, LOCMEM)

    @override_settings(
        TOOLKIT_WRAPPED_EMAIL_BACKEND="toolkit.util.tests.FailingBackend"
    )
    def test_failed_send_creates_row_with_error(self):
        with self.assertLogs("toolkit.email", "ERROR"):
            send_mail(
                "Doomed", "body", "from@example.com", ["to@example.com"],
                fail_silently=True,
            )
        log = SentEmailLog.objects.get()
        self.assertFalse(log.success)
        self.assertIn("SMTP server said no", log.error)

    @override_settings(TOOLKIT_WRAPPED_EMAIL_BACKEND=LOCMEM)
    def test_batch_sends_summarised_as_one_row(self):
        with summarise_email_batch("[mailout] Big news"):
            for n in range(3):
                send_mail(
                    "Big news", "body", "from@example.com", [f"m{n}@example.com"]
                )
        log = SentEmailLog.objects.get()
        self.assertEqual(log.recipients, "(mailout batch: 3 recipients)")
        self.assertEqual(log.subject, "[mailout] Big news")
        self.assertTrue(log.success)

    @override_settings(TOOLKIT_WRAPPED_EMAIL_BACKEND=LOCMEM)
    def test_sends_after_batch_get_their_own_rows(self):
        with summarise_email_batch("[mailout] Batch"):
            send_mail("Batch", "body", "from@example.com", ["a@example.com"])
        send_mail("Report", "body", "from@example.com", ["b@example.com"])
        self.assertEqual(SentEmailLog.objects.count(), 2)
        self.assertTrue(
            SentEmailLog.objects.filter(subject="Report").exists()
        )

    def test_record_email_never_raises(self):
        with patch.object(
            SentEmailLog.objects, "create", side_effect=RuntimeError("db gone")
        ):
            with self.assertLogs("toolkit.audit.models", "ERROR"):
                record_email("x@example.com", "s", success=True)


class AuditViewTests(MembersTestsMixin, TestCase):
    def test_pages_require_panopticon(self):
        for url_name in ("audit-email-log", "audit-deletion-log"):
            url = reverse(url_name)
            # Anonymous: redirected to login
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            # Non-superuser: forbidden
            self.client.login(username="read_only", password="T3stPassword!1")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.client.logout()

    def test_email_log_page_lists_and_filters(self):
        self.client.login(username="admin", password="T3stPassword!")
        SentEmailLog.objects.create(
            recipients="good@example.com", subject="Fine", success=True,
            backend="x",
        )
        SentEmailLog.objects.create(
            recipients="bad@example.com", subject="Broken", success=False,
            error="boom", backend="x",
        )

        response = self.client.get(reverse("audit-email-log"))
        self.assertContains(response, "good@example.com")
        self.assertContains(response, "bad@example.com")

        response = self.client.get(reverse("audit-email-log"), {"status": "failed"})
        self.assertNotContains(response, "good@example.com")
        self.assertContains(response, "bad@example.com")
        self.assertContains(response, "boom")

        response = self.client.get(reverse("audit-email-log"), {"search": "Fine"})
        self.assertContains(response, "good@example.com")
        self.assertNotContains(response, "bad@example.com")

    def test_deletion_log_page(self):
        self.client.login(username="admin", password="T3stPassword!")
        DeletionLog.objects.create(
            model="Showing", object_pk="42",
            description="Booking for 'Test Film' on 01/01/2030 19:00",
            via=DeletionLog.VIA_EDIT_UI,
        )
        response = self.client.get(reverse("audit-deletion-log"))
        self.assertContains(response, "Test Film")

        response = self.client.get(
            reverse("audit-deletion-log"), {"search": "no-such-thing"}
        )
        self.assertNotContains(response, "Test Film")


class DeleteShowingAuditTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    @patch("django.utils.timezone.now")
    def test_delete_showing_writes_deletion_log(self, now_patch):
        now_patch.return_value = self._fake_now
        showing = Showing.objects.get(id=7)
        event_name = showing.event.name

        with self.assertLogs("toolkit.diary.edit_views.showings", "WARNING") as logs:
            self.client.post(
                reverse("delete-showing", kwargs={"showing_id": 7})
            )

        self.assertFalse(Showing.objects.filter(id=7).exists())
        log = DeletionLog.objects.get()
        self.assertEqual(log.model, "Showing")
        self.assertEqual(log.object_pk, "7")
        self.assertIn(event_name, log.description)
        self.assertEqual(log.deleted_by.username, "admin")
        self.assertEqual(log.via, DeletionLog.VIA_EDIT_UI)
        # And the WARNING line carries attribution:
        self.assertIn("admin", logs.output[0])

    @patch("django.utils.timezone.now")
    def test_delete_showing_in_past_writes_nothing(self, now_patch):
        now_patch.return_value = self._fake_now
        self.client.post(reverse("delete-showing", kwargs={"showing_id": 1}))
        self.assertTrue(Showing.objects.filter(id=1).exists())
        self.assertFalse(DeletionLog.objects.exists())


class EventDeletionTrapTests(DiaryTestsMixin, TestCase):
    def test_queryset_event_delete_logs(self):
        event_pk = self.e2.pk
        with self.assertLogs("toolkit.audit.signals", "WARNING"):
            Event.objects.filter(pk=event_pk).delete()
        log = DeletionLog.objects.get(model="Event")
        self.assertEqual(log.object_pk, str(event_pk))
        self.assertEqual(log.via, DeletionLog.VIA_SIGNAL)

    def test_suppressed_during_seeding(self):
        with suppress_event_deletion_log():
            Event.objects.filter(pk=self.e2.pk).delete()
        self.assertFalse(DeletionLog.objects.filter(model="Event").exists())


class PurgeAuditLogsTests(TestCase):
    def _age(self, obj, field, days):
        type(obj).objects.filter(pk=obj.pk).update(
            **{field: timezone.now() - datetime.timedelta(days=days)}
        )

    def test_purges_per_retention_settings(self):
        old_email = SentEmailLog.objects.create(
            recipients="a@example.com", subject="old", success=True, backend="x"
        )
        new_email = SentEmailLog.objects.create(
            recipients="b@example.com", subject="new", success=True, backend="x"
        )
        old_deletion = DeletionLog.objects.create(
            model="Showing", object_pk="1", description="old",
            via=DeletionLog.VIA_EDIT_UI,
        )
        self._age(old_email, "sent_at", 100)  # > default 90
        self._age(old_deletion, "deleted_at", 400)  # > default 365

        call_command("purge_audit_logs")

        self.assertFalse(SentEmailLog.objects.filter(pk=old_email.pk).exists())
        self.assertTrue(SentEmailLog.objects.filter(pk=new_email.pk).exists())
        self.assertFalse(DeletionLog.objects.filter(pk=old_deletion.pk).exists())

    def test_zero_disables_purge(self):
        from toolkit.diary.models import get_site_config

        config = get_site_config()
        config.email_log_retain_days = 0
        config.save()

        old_email = SentEmailLog.objects.create(
            recipients="a@example.com", subject="old", success=True, backend="x"
        )
        self._age(old_email, "sent_at", 1000)
        call_command("purge_audit_logs")
        self.assertTrue(SentEmailLog.objects.filter(pk=old_email.pk).exists())


class AnonymiseScrubTests(MembersTestsMixin, TestCase):
    def test_anonymise_scrubs_email_log_recipients(self):
        # vol_1's member email is volon@cube.test (see MembersTestsMixin)
        SentEmailLog.objects.create(
            recipients="volon@cube.test", subject="Hello", success=True,
            backend="x",
        )
        SentEmailLog.objects.create(
            recipients="other@example.com", subject="Hello", success=True,
            backend="x",
        )
        vol_pk = self.vol_1.pk

        self.vol_1.anonymise()

        self.assertEqual(
            SentEmailLog.objects.filter(
                recipients=f"(anonymised volunteer {vol_pk})"
            ).count(),
            1,
        )
        self.assertTrue(
            SentEmailLog.objects.filter(
                recipients="other@example.com"
            ).exists()
        )
