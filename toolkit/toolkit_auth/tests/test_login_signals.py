# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""user_login_failed_callback must not crash when Django's authenticate()
is called without a request (request=None) -- this happens for anything
that calls authenticate() directly rather than going through a request-
bound login view, including Django's own test Client.login(). Found by
a labs edge-case test that logged a bad password in during setUp."""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.test import TestCase


class UserLoginFailedSignalTests(TestCase):
    def setUp(self):
        User.objects.create_user("someone", password="correct-password")

    def test_authenticate_with_no_request_does_not_crash_on_bad_password(
        self,
    ):
        result = authenticate(username="someone", password="wrong-password")
        self.assertIsNone(result)

    def test_client_login_with_bad_password_does_not_crash(self):
        self.assertFalse(
            self.client.login(username="someone", password="wrong-password")
        )
