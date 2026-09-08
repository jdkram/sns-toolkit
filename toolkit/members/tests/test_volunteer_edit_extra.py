# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Coverage for volunteer_edit.py branches test_volunteers.py doesn't reach:
username collision on create, the non-superuser save-target redirect, the
suspension-lifted message and suspension-email preview, and the standalone
password/qualification/permissions endpoints (set_volunteer_password,
send_volunteer_password_reset, add/remove_volunteer_qualification,
save_volunteer_permissions)."""

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from toolkit.members.models import (
    Member,
    Qualification,
    Volunteer,
    VolunteerQualification,
)

from .common import MembersTestsMixin


class TestUsernameCollision(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def test_second_volunteer_with_same_slugified_name_gets_suffixed_username(
        self,
    ):
        # vol_1 (member "Volunteer One") already has user "vol1" -- but the
        # slug of a *new* volunteer's name is what's checked for collision,
        # so pick a name that slugifies to something already taken.
        from django.contrib.auth.models import User

        User.objects.create_user("clashname", "existing@test.example", "pw")
        response = self.client.post(
            reverse("add-volunteer"),
            data={
                "mem-name": "clashname",
                "mem-email": "newperson@test.example",
                "vol-status": "active",
            },
            follow=True,
        )
        self.assertContains(response, "Created volunteer")
        new_member = Member.objects.get(name="clashname")
        self.assertEqual(new_member.volunteer.user.username, "clashname-1")


class TestSuspensionLiftedViaEditForm(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def test_reinstate_via_edit_form_shows_lifted_message(self):
        self.vol_1.status = Volunteer.STATUS_SUSPENDED
        self.vol_1.save()
        response = self.client.post(
            reverse("edit-volunteer", kwargs={"volunteer_id": self.vol_1.id}),
            data={
                "mem-name": self.vol_1.member.name,
                "mem-email": self.vol_1.member.email,
                "vol-status": "active",
            },
            follow=True,
        )
        self.assertContains(response, "suspension has been lifted")
        self.vol_1.refresh_from_db()
        self.assertEqual(self.vol_1.status, Volunteer.STATUS_ACTIVE)


class TestNonSuperuserSaveRedirect(MembersTestsMixin, TestCase):
    def test_self_edit_by_non_superuser_redirects_to_volunteer_list(self):
        self.client.force_login(self.vol_1.user)
        response = self.client.post(
            reverse("edit-volunteer", kwargs={"volunteer_id": self.vol_1.id}),
            data={
                "mem-name": self.vol_1.member.name,
                "mem-email": self.vol_1.member.email,
                "vol-status": "active",
            },
        )
        self.assertRedirects(
            response,
            reverse("view-volunteer-list"),
            fetch_redirect_response=False,
        )


class TestSuspensionEmailPreview(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )
        config = self._get_site_config()
        config.suspension_email_subject = "Suspended, {name}"
        config.suspension_email_body = "Sorry {name}, at {venue}."
        config.save()

    def _get_site_config(self):
        from toolkit.diary.models import get_site_config

        return get_site_config()

    def test_preview_shown_after_suspend_toggle(self):
        self.client.post(
            reverse(
                "toggle-volunteer-suspension",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {"action": "suspend"},
        )
        response = self.client.get(
            reverse("edit-volunteer", kwargs={"volunteer_id": self.vol_1.id})
        )
        self.assertIsNotNone(response.context["suspension_email_preview"])
        self.assertIn(
            "Suspended",
            response.context["suspension_email_preview"]["subject"],
        )

    def test_no_preview_when_not_pending(self):
        response = self.client.get(
            reverse("edit-volunteer", kwargs={"volunteer_id": self.vol_1.id})
        )
        self.assertIsNone(response.context["suspension_email_preview"])


class SetPasswordTestsBase(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )


class TestSetVolunteerPassword(SetPasswordTestsBase):
    def test_non_superuser_forbidden(self):
        self.client.logout()
        self.client.force_login(self.vol_1.user)
        response = self.client.post(
            reverse(
                "set-volunteer-password",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {"new_password1": "n3wP4ssword!", "new_password2": "n3wP4ssword!"},
        )
        self.assertNotEqual(response.status_code, 200)

    # Volunteer.user is a non-nullable OneToOneField, so the "no linked
    # user" branch in this view is unreachable in practice -- not tested.

    def test_valid_password_is_set(self):
        response = self.client.post(
            reverse(
                "set-volunteer-password",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {"new_password1": "n3wP4ssword!", "new_password2": "n3wP4ssword!"},
            follow=True,
        )
        self.assertContains(response, "Password updated")
        self.vol_1.user.refresh_from_db()
        self.assertTrue(self.vol_1.user.check_password("n3wP4ssword!"))

    def test_mismatched_passwords_show_form_errors(self):
        response = self.client.post(
            reverse(
                "set-volunteer-password",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {"new_password1": "n3wP4ssword!", "new_password2": "different!"},
            follow=True,
        )
        self.assertContains(response, "didn’t match")


class TestSendVolunteerPasswordReset(SetPasswordTestsBase):
    def test_non_superuser_forbidden(self):
        self.client.logout()
        self.client.force_login(self.vol_1.user)
        response = self.client.post(
            reverse(
                "send-volunteer-password-reset",
                kwargs={"volunteer_id": self.vol_1.id},
            )
        )
        self.assertNotEqual(response.status_code, 200)

    def test_volunteer_with_no_email_errors(self):
        self.vol_1.user.email = ""
        self.vol_1.user.save()
        response = self.client.post(
            reverse(
                "send-volunteer-password-reset",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            follow=True,
        )
        self.assertContains(response, "no linked user account or no email")

    def test_sends_email_and_confirms(self):
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            response = self.client.post(
                reverse(
                    "send-volunteer-password-reset",
                    kwargs={"volunteer_id": self.vol_1.id},
                ),
                follow=True,
            )
        self.assertContains(response, "Password reset email sent")
        self.assertEqual(len(mail.outbox), 1)


class TestVolunteerQualificationEndpoints(SetPasswordTestsBase):
    def setUp(self):
        super().setUp()
        self.qual = Qualification.objects.create(name="Bar")

    def test_add_qualification_success(self):
        response = self.client.post(
            reverse(
                "add-volunteer-qualification",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {"qualification_id": self.qual.pk, "granted_by": "Admin"},
            follow=True,
        )
        self.assertContains(response, "qualification recorded")
        self.assertTrue(
            VolunteerQualification.objects.filter(
                volunteer=self.vol_1, qualification=self.qual
            ).exists()
        )

    def test_add_qualification_already_held_warns(self):
        VolunteerQualification.objects.create(
            volunteer=self.vol_1, qualification=self.qual, granted_by="X"
        )
        response = self.client.post(
            reverse(
                "add-volunteer-qualification",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {"qualification_id": self.qual.pk},
            follow=True,
        )
        self.assertContains(response, "already holds")

    def test_add_unknown_qualification_errors(self):
        response = self.client.post(
            reverse(
                "add-volunteer-qualification",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {"qualification_id": 999999},
            follow=True,
        )
        self.assertContains(response, "Qualification not found")

    def test_remove_qualification_success(self):
        vq = VolunteerQualification.objects.create(
            volunteer=self.vol_1, qualification=self.qual, granted_by="X"
        )
        response = self.client.post(
            reverse("remove-volunteer-qualification", kwargs={"vq_id": vq.pk}),
            follow=True,
        )
        self.assertContains(response, "qualification removed")
        self.assertFalse(
            VolunteerQualification.objects.filter(pk=vq.pk).exists()
        )


class TestSaveVolunteerPermissions(SetPasswordTestsBase):
    def test_disabled_when_show_user_management_off(self):
        response = self.client.post(
            reverse(
                "save-volunteer-permissions",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {"user-username": self.vol_1.user.username},
        )
        self.assertNotEqual(response.status_code, 200)

    @override_settings(VENUE={**settings.VENUE, "show_user_management": True})
    def test_grants_programmer_status(self):
        response = self.client.post(
            reverse(
                "save-volunteer-permissions",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {
                "user-username": self.vol_1.user.username,
                "user-programmer": "on",
            },
            follow=True,
        )
        self.assertContains(response, "Permissions updated")
        self.vol_1.user.refresh_from_db()
        self.assertTrue(
            self.vol_1.user.groups.filter(name="Programmers").exists()
        )

    @override_settings(VENUE={**settings.VENUE, "show_user_management": True})
    def test_panopticon_grant_without_reason_shows_error(self):
        response = self.client.post(
            reverse(
                "save-volunteer-permissions",
                kwargs={"volunteer_id": self.vol_1.id},
            ),
            {
                "user-username": self.vol_1.user.username,
                "user-is_superuser": "on",
            },
            follow=True,
        )
        self.assertContains(response, "Permissions:")

    # Volunteer.user is a non-nullable OneToOneField, so the "no linked
    # user" branch in this view is unreachable in practice -- not tested.
