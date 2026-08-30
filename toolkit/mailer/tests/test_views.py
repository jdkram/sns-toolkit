from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import fixtures
from django.test import TestCase
from django.urls import reverse
import django.utils.timezone

from toolkit.mailer.models import MailoutJob

from ...diary.tests.common import FAKE_NOW, ToolkitUsersFixture


class TestPermissions(TestCase, fixtures.TestWithFixtures):
    def setUp(self) -> None:
        self.useFixture(ToolkitUsersFixture())

    def _assert_need_login(self, views_to_test):
        for view_name, kwargs in views_to_test.items():
            url = reverse(view_name, kwargs=kwargs)
            expected_redirect = reverse("login", query={"next": url})
            # Test GET:
            with self.subTest(f"GET {view_name} {url}"):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertRedirects(response, expected_redirect)
            # Test POST:
            with self.subTest(f"POST {view_name} {url}"):
                response = self.client.post(url)
                self.assertEqual(response.status_code, 302)
                self.assertRedirects(response, expected_redirect)

    def test_need_login(self):
        views = {
            "mailer:job-delete": {"job_id": 1},
            "mailer:jobs-list": {},
            "mailer:jobs-table": {},
            "mailer:test-mailout-create": {},
        }
        self._assert_need_login(views)

    def test_need_write(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        views = {
            "mailer:job-delete": {"job_id": 1},
            "mailer:test-mailout-create": {},
        }
        self._assert_need_login(views)


class TestCancelJobView(TestCase, fixtures.TestWithFixtures):
    def setUp(self) -> None:
        self.useFixture(ToolkitUsersFixture())
        self.client.login(username="admin", password="T3stPassword!")

    def test_cancel(self) -> None:
        job = MailoutJob(
            send_at=django.utils.timezone.now() + timedelta(days=1),
            send_html=True,
            subject="subject",
            body_text="Body",
            body_html="<p>Body</p>",
        )
        job.save()
        self.assertEqual(MailoutJob.objects.count(), 1)
        self.assertEqual(job.state, MailoutJob.SendState.PENDING)

        url = reverse("mailer:job-delete", kwargs={"job_id": job.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("mailer:jobs-list"))

        job.refresh_from_db()
        self.assertEqual(job.state, MailoutJob.SendState.CANCELLED)

    def test_cancel_non_existent(self) -> None:
        url = reverse("mailer:job-delete", kwargs={"job_id": 100})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_get_not_permitted(self) -> None:
        url = reverse("mailer:job-delete", kwargs={"job_id": 100})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)


class TestListJobView(TestCase, fixtures.TestWithFixtures):
    def setUp(self) -> None:
        self.useFixture(ToolkitUsersFixture())
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse("mailer:jobs-list")

    def test_no_jobs(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs-list.html")
        self.assertTemplateUsed(response, "jobs-list-table.html")

    def _job(self) -> MailoutJob:
        return MailoutJob(
            send_at=django.utils.timezone.now() + timedelta(days=1),
            send_html=True,
            subject="subject",
            body_text="Body",
            body_html="<p>Body</p>",
        )

    def _create_jobs(self, extra_pending=0) -> list[MailoutJob]:
        jobs = [self._job() for _ in range(6 + extra_pending)]
        # 0 - pending
        # 1 - sending
        jobs[1].do_sending(sent=0, total=100)
        # 2 - cancelling

        jobs[2].do_sending(sent=0, total=100)
        jobs[2].do_cancel()
        # 3 - sent
        jobs[3].do_sending(sent=0, total=100)
        jobs[3].do_complete(sent=0x100)

        # 4 - failed
        jobs[4].do_fail(status="borked")

        # 5 - cancelled
        jobs[5].do_cancel()

        for job in jobs:
            job.save()

        return jobs

    def test_all_jobs(self) -> None:
        self._create_jobs()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs-list.html")
        self.assertTemplateUsed(response, "jobs-list-table.html")

        for job in MailoutJob.objects.all():
            self.assertContains(response, f"<td>{job.pk}</td>", html=True)

        self.assertContains(response, f"<td>FAILED: borked</td>", html=True)

    def test_table_fragment_no_jobs(self) -> None:
        url = reverse("mailer:jobs-table")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs-list-table.html")

    def test_table_fragment_all_jobs(self) -> None:
        self._create_jobs()

        url = reverse("mailer:jobs-table")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs-list-table.html")

        for job in MailoutJob.objects.all():
            self.assertContains(response, f"<td>{job.pk}</td>", html=True)

        self.assertContains(response, f"<td>FAILED: borked</td>", html=True)
        self.assertNotContains(response, 'hx-trigger="every 1s"')

    def test_table_fragment_polling_enabled(self) -> None:
        self._create_jobs()

        url = reverse("mailer:jobs-table", query={"poll-for-updates": "on"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs-list-table.html")

        self.assertContains(response, 'hx-trigger="every 1s"')

    def test_no_pagination_nav_single_page(self) -> None:
        self._create_jobs()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # Six jobs fit on a single page: no pagination controls.
        self.assertNotContains(response, "Page 1 of")

    def test_pagination_first_page(self) -> None:
        jobs = self._create_jobs(extra_pending=9)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 1 of 2")
        # Newest 10 (highest pks) shown, oldest 5 not.
        for job in jobs[10:]:
            self.assertContains(response, f"<td>{job.pk}</td>", html=True)
        for job in jobs[:5]:
            self.assertNotContains(response, f"<td>{job.pk}</td>", html=True)
        self.assertContains(response, "?page=2")

    def test_pagination_second_page(self) -> None:
        jobs = self._create_jobs(extra_pending=9)

        url = reverse("mailer:jobs-list", query={"page": "2"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")
        # Oldest 5 (lowest pks) shown on the second page.
        for job in jobs[:5]:
            self.assertContains(response, f"<td>{job.pk}</td>", html=True)
        for job in jobs[10:]:
            self.assertNotContains(response, f"<td>{job.pk}</td>", html=True)

    def test_pagination_out_of_range_page(self) -> None:
        self._create_jobs(extra_pending=9)
        # An out-of-range page falls back to the last page, not a 404.
        url = reverse("mailer:jobs-list", query={"page": "999"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")

    def test_pagination_invalid_page(self) -> None:
        jobs = self._create_jobs(extra_pending=9)
        # A non-numeric page falls back to the first page, not a 404.
        url = reverse("mailer:jobs-list", query={"page": "not-a-number"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 1 of 2")

    def test_table_fragment_pagination(self) -> None:
        jobs = self._create_jobs(extra_pending=9)

        url = reverse("mailer:jobs-table", query={"page": "2"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs-list-table.html")
        self.assertContains(response, "Page 2 of 2")
        for job in jobs[:5]:
            self.assertContains(response, f"<td>{job.pk}</td>", html=True)


class TestMailoutCreateView(TestCase, fixtures.TestWithFixtures):
    def setUp(self) -> None:
        self.useFixture(ToolkitUsersFixture())
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse("mailer:test-mailout-create")

        self.time_patch = patch("django.utils.timezone.now")
        self.time_mock = self.time_patch.start()
        self.time_mock.return_value = FAKE_NOW
        self.addCleanup(self.time_patch.stop)

    def _data(self, **overrides) -> dict:
        data = {
            "subject": "Test subject",
            "body_text": "Test body",
            "recipient_filter": "someone@example.com",
            "send_at": "01/06/2025 22:11",
        }
        data.update(overrides)
        return data

    def test_get(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "test-mailout.html")

    def test_create_scheduled(self) -> None:
        self.assertEqual(0, MailoutJob.objects.count())
        data = self._data()
        response = self.client.post(self.url, data=data)

        self.assertRedirects(response, reverse("mailer:jobs-list"))

        self.assertEqual(1, MailoutJob.objects.count())
        job = MailoutJob.objects.get()
        self.assertEqual(job.subject, data["subject"])
        self.assertEqual(job.body_text, data["body_text"])
        self.assertEqual(job.recipient_filter, data["recipient_filter"])
        # Test jobs are always forced to plain-text only:
        self.assertEqual(job.send_html, False)
        self.assertEqual(job.body_html, "")
        self.assertEqual(
            job.send_at,
            datetime(2025, 6, 1, 21, 11, tzinfo=timezone.utc),
        )

    def test_create_send_now(self) -> None:
        url = reverse("mailer:test-mailout-create", query={"send_at": "now"})
        self.assertEqual(0, MailoutJob.objects.count())
        # The posted send_at is in the past, but is overridden because of
        # the "send_at=now" query param:
        data = self._data(send_at="01/06/1901 12:00")
        response = self.client.post(url, data=data)

        self.assertRedirects(response, reverse("mailer:jobs-list"))

        self.assertEqual(1, MailoutJob.objects.count())
        job = MailoutJob.objects.get()
        self.assertEqual(job.subject, data["subject"])
        self.assertEqual(job.recipient_filter, data["recipient_filter"])
        self.assertEqual(job.send_at, FAKE_NOW + timedelta(seconds=2))

    def test_date_in_past(self) -> None:
        data = self._data(
            send_at=(FAKE_NOW - timedelta(seconds=1)).strftime(
                "%d/%m/%Y %H:%M"
            )
        )
        response = self.client.post(self.url, data=data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "test-mailout.html")
        self.assertFormError(
            response.context["form"], "send_at", "Must be in the future"
        )
        self.assertEqual(0, MailoutJob.objects.count())

    def test_missing_recipient(self) -> None:
        data = self._data(recipient_filter="")
        response = self.client.post(self.url, data=data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "test-mailout.html")
        self.assertFormError(
            response.context["form"],
            "recipient_filter",
            "A recipient email address is required",
        )
        self.assertEqual(0, MailoutJob.objects.count())

    def test_invalid_recipient_email(self) -> None:
        data = self._data(recipient_filter="not-an-email-address")
        response = self.client.post(self.url, data=data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "test-mailout.html")
        self.assertFormError(
            response.context["form"],
            "recipient_filter",
            "Please enter a valid email address",
        )
        self.assertEqual(0, MailoutJob.objects.count())
