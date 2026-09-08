# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Direct tests for EmailOrUsernameBackend.authenticate -- the fallback
email-lookup path in particular, which had no dedicated coverage despite
being how the "log in with your email address" flow actually works."""

from django.contrib.auth.models import User
from django.test import TestCase

from toolkit.toolkit_auth.backends import EmailOrUsernameBackend


class TestEmailOrUsernameBackend(TestCase):
    def setUp(self):
        self.backend = EmailOrUsernameBackend()
        self.user = User.objects.create_user(
            "someusername", "person@example.com", "correct-password"
        )

    def test_authenticates_by_username(self):
        result = self.backend.authenticate(
            None, username="someusername", password="correct-password"
        )
        self.assertEqual(result, self.user)

    def test_authenticates_by_email_case_insensitively(self):
        result = self.backend.authenticate(
            None,
            username="PERSON@EXAMPLE.COM",
            password="correct-password",
        )
        self.assertEqual(result, self.user)

    def test_email_fallback_wrong_password_returns_none(self):
        result = self.backend.authenticate(
            None, username="person@example.com", password="wrong-password"
        )
        self.assertIsNone(result)

    def test_unknown_username_and_email_returns_none(self):
        result = self.backend.authenticate(
            None, username="nobody@example.com", password="whatever"
        )
        self.assertIsNone(result)

    def test_inactive_user_cannot_authenticate_via_email_fallback(self):
        self.user.is_active = False
        self.user.save()
        result = self.backend.authenticate(
            None, username="person@example.com", password="correct-password"
        )
        self.assertIsNone(result)

    def test_duplicate_email_returns_none(self):
        # Django's User.email has no uniqueness constraint, so two accounts
        # can share one -- the email fallback must not guess which is meant.
        User.objects.create_user(
            "otherusername", "person@example.com", "another-password"
        )
        result = self.backend.authenticate(
            None, username="person@example.com", password="correct-password"
        )
        self.assertIsNone(result)
