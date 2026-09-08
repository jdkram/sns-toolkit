# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Direct unit tests for the permission decorators every app in this repo
depends on (write_required, read_required, write_required_strict,
panopticon_required, feature_required, ip_or_permission_required).

These call the decorated function directly via RequestFactory rather than
going through a real URL/view, so a bug here would previously only ever be
caught incidentally by whichever app's tests happened to exercise it."""

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from toolkit.test_common import create_toolkit_test_users
from toolkit.toolkit_auth.decorators import (
    feature_required,
    ip_or_permission_required,
    panopticon_required,
    read_required,
    write_required,
    write_required_strict,
)


def _dummy_view(request, *args, **kwargs):
    return "ok"


class DecoratorTestsBase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.users = create_toolkit_test_users()

    def _request(self, user):
        req = self.factory.get("/some-view/")
        req.user = user
        return req


class TestWriteRequired(DecoratorTestsBase):
    def test_anonymous_redirects_to_login(self):
        view = write_required(_dummy_view)
        resp = view(self._request(AnonymousUser()))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_authenticated_without_write_perm_redirects(self):
        view = write_required(_dummy_view)
        resp = view(self._request(self.users.read_only))
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_with_write_perm_passes_through(self):
        view = write_required(_dummy_view)
        request = self._request(self.users.admin)
        result = view(request)
        self.assertEqual(result, "ok")
        self.assertEqual(request.view_access_level, "Programmer+")


class TestReadRequired(DecoratorTestsBase):
    def test_anonymous_redirects_to_login(self):
        view = read_required(_dummy_view)
        resp = view(self._request(AnonymousUser()))
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_without_read_perm_redirects(self):
        view = read_required(_dummy_view)
        resp = view(self._request(self.users.no_perm))
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_with_read_perm_passes_through(self):
        view = read_required(_dummy_view)
        request = self._request(self.users.read_only)
        result = view(request)
        self.assertEqual(result, "ok")
        self.assertEqual(request.view_access_level, "All volunteers")


class TestWriteRequiredStrict(DecoratorTestsBase):
    def test_anonymous_redirects_to_login(self):
        view = write_required_strict(_dummy_view)
        resp = view(self._request(AnonymousUser()))
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_without_write_perm_raises_403(self):
        view = write_required_strict(_dummy_view)
        with self.assertRaises(PermissionDenied):
            view(self._request(self.users.read_only))

    def test_authenticated_with_write_perm_passes_through(self):
        view = write_required_strict(_dummy_view)
        request = self._request(self.users.admin)
        result = view(request)
        self.assertEqual(result, "ok")
        self.assertEqual(request.view_access_level, "Programmer+")


class TestPanopticonRequired(DecoratorTestsBase):
    def test_anonymous_redirects_to_login(self):
        view = panopticon_required(_dummy_view)
        resp = view(self._request(AnonymousUser()))
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_non_superuser_raises_403(self):
        view = panopticon_required(_dummy_view)
        # admin here carries toolkit.write/read but is_admin_superuser
        # defaults True in create_toolkit_test_users -- use read_only,
        # which is neither superuser nor write-permissioned.
        with self.assertRaises(PermissionDenied):
            view(self._request(self.users.read_only))

    def test_authenticated_superuser_passes_through(self):
        view = panopticon_required(_dummy_view)
        request = self._request(self.users.admin)
        result = view(request)
        self.assertEqual(result, "ok")
        self.assertEqual(request.view_access_level, "Panopticon only")


class TestFeatureRequired(DecoratorTestsBase):
    """No SiteConfiguration.perm_<name> field exists for this made-up
    feature name, so the decorator falls back to its documented default
    (PERM_PROGRAMMER, i.e. toolkit.write) -- exercising that fallback path
    directly rather than relying on a real feature's current default."""

    def test_anonymous_redirects_to_login(self):
        view = feature_required("nonexistent_feature")(_dummy_view)
        resp = view(self._request(AnonymousUser()))
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_without_required_perm_raises_403(self):
        view = feature_required("nonexistent_feature")(_dummy_view)
        with self.assertRaises(PermissionDenied):
            view(self._request(self.users.read_only))

    def test_authenticated_with_required_perm_passes_through(self):
        view = feature_required("nonexistent_feature")(_dummy_view)
        request = self._request(self.users.admin)
        result = view(request)
        self.assertEqual(result, "ok")
        self.assertEqual(request.view_access_level, "Programmer+")


class TestIpOrPermissionRequired(DecoratorTestsBase):
    def test_matching_ip_bypasses_permission_check(self):
        view = ip_or_permission_required(["10.0.0.1"], "toolkit.write")(
            _dummy_view
        )
        request = self._request(AnonymousUser())
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        result = view(request)
        self.assertEqual(result, "ok")

    def test_non_matching_ip_falls_back_to_permission_check(self):
        view = ip_or_permission_required(["10.0.0.1"], "toolkit.write")(
            _dummy_view
        )
        request = self._request(self.users.admin)
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        result = view(request)
        self.assertEqual(result, "ok")

    def test_non_matching_ip_and_no_permission_redirects_to_login(self):
        # Django's own permission_required (no raise_exception=True) redirects
        # rather than raising, even for an authenticated user.
        view = ip_or_permission_required(["10.0.0.1"], "toolkit.write")(
            _dummy_view
        )
        request = self._request(self.users.no_perm)
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        resp = view(request)
        self.assertEqual(resp.status_code, 302)
