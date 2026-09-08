# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Tests for the LoggingEmailBackend wrapper (9.154)."""

from django.core import mail
from django.core.mail import send_mail
from django.core.mail.backends.base import BaseEmailBackend
from django.test import TestCase, override_settings


class FailingBackend(BaseEmailBackend):
    """Raises on every send. Referenced by dotted path in override_settings."""

    def send_messages(
        self, email_messages  # noqa: ARG002 -- BaseEmailBackend API
    ):
        raise ConnectionRefusedError("SMTP server said no")


class ZeroSendBackend(BaseEmailBackend):
    """Reports nothing sent without raising, as smtp does for refused recipients."""

    def send_messages(
        self, email_messages  # noqa: ARG002 -- BaseEmailBackend API
    ):
        return 0


WRAPPER = "toolkit.util.email_backend.LoggingEmailBackend"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


# TestCase (not SimpleTestCase): each send also writes a SentEmailLog row
# (toolkit.audit), which needs the test database.
@override_settings(EMAIL_BACKEND=WRAPPER)
class LoggingEmailBackendTests(TestCase):
    @override_settings(TOOLKIT_WRAPPED_EMAIL_BACKEND=LOCMEM)
    def test_success_delegates_to_inner_backend_and_logs(self):
        with self.assertLogs("toolkit.email", "INFO") as logs:
            sent = send_mail(
                "Test subject", "body", "from@example.com", ["to@example.com"]
            )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test subject")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("EMAIL SENT", logs.output[0])
        self.assertIn("to@example.com", logs.output[0])
        self.assertIn("Test subject", logs.output[0])
        self.assertIn(LOCMEM, logs.output[0])

    @override_settings(TOOLKIT_WRAPPED_EMAIL_BACKEND=LOCMEM)
    def test_one_log_line_per_message(self):
        messages = [
            mail.EmailMessage(
                "Subject one", "body", "from@example.com", ["a@example.com"]
            ),
            mail.EmailMessage(
                "Subject two", "body", "from@example.com", ["b@example.com"]
            ),
        ]
        with self.assertLogs("toolkit.email", "INFO") as logs:
            sent = mail.get_connection().send_messages(messages)
        self.assertEqual(sent, 2)
        self.assertEqual(len(logs.output), 2)
        self.assertIn("a@example.com", logs.output[0])
        self.assertIn("b@example.com", logs.output[1])

    @override_settings(
        TOOLKIT_WRAPPED_EMAIL_BACKEND="toolkit.util.tests.FailingBackend"
    )
    def test_failure_logs_error_and_reraises(self):
        with self.assertLogs("toolkit.email", "ERROR") as logs:
            with self.assertRaises(ConnectionRefusedError):
                send_mail(
                    "Doomed", "body", "from@example.com", ["to@example.com"]
                )
        self.assertIn("EMAIL FAILED", logs.output[0])
        self.assertIn("to@example.com", logs.output[0])
        self.assertIn("SMTP server said no", logs.output[0])

    @override_settings(
        TOOLKIT_WRAPPED_EMAIL_BACKEND="toolkit.util.tests.FailingBackend"
    )
    def test_failure_with_fail_silently_logs_error_and_swallows(self):
        with self.assertLogs("toolkit.email", "ERROR") as logs:
            sent = send_mail(
                "Doomed",
                "body",
                "from@example.com",
                ["to@example.com"],
                fail_silently=True,
            )
        self.assertEqual(sent, 0)
        self.assertIn("EMAIL FAILED", logs.output[0])

    @override_settings(
        TOOLKIT_WRAPPED_EMAIL_BACKEND="toolkit.util.tests.ZeroSendBackend"
    )
    def test_zero_sent_without_exception_logs_error(self):
        with self.assertLogs("toolkit.email", "ERROR") as logs:
            sent = send_mail(
                "Refused", "body", "from@example.com", ["to@example.com"]
            )
        self.assertEqual(sent, 0)
        self.assertIn("EMAIL NOT SENT", logs.output[0])


class CsvFormulaGuardTests(TestCase):
    """csv_formula_guard must neutralise formula-shaped cells without
    mangling phone numbers and negative figures, which also start with
    `+`/`-` and are exported verbatim by the volunteer export."""

    def test_formula_leaders_are_prefixed(self):
        from toolkit.util.csv_export import csv_formula_guard

        for cell in ("=1+1", "@SUM(A1)", "+cmd|' /C calc'!A0", "-2+3*x"):
            self.assertEqual(csv_formula_guard(cell), "\t" + cell, cell)

    def test_phone_numbers_and_plain_figures_pass_through(self):
        from toolkit.util.csv_export import csv_formula_guard

        for cell in ("+44 7700 900123", "+44(0)191-123-4567", "-12.5", "-"):
            self.assertEqual(csv_formula_guard(cell), cell, cell)

    def test_non_strings_and_ordinary_text_pass_through(self):
        from toolkit.util.csv_export import csv_formula_guard

        for cell in (None, 42, "Volunteer One", "", "a=b"):
            self.assertEqual(csv_formula_guard(cell), cell)
