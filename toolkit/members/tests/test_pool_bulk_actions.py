# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Tests for the destructive bulk pool-admin actions: bulk_anonymise_volunteers
and bulk_delete_never_onboarded. Both are two-step (select -> confirm) flows
gated behind a typed confirmation phrase; these tests cover both steps, the
phrase mismatch guard, and the delete/anonymise split in the delete flow."""

import datetime
import os
import tempfile

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from toolkit.diary.models import (
    Role,
    RotaEntry,
    Showing,
    Event,
    get_site_config,
)
from toolkit.members.models import (
    AnonymisationLog,
    LastGaspEmailLog,
    Member,
    Volunteer,
)

from .common import MembersTestsMixin


def _days_ago(days):
    return timezone.now() - datetime.timedelta(days=days)


class BulkActionsBase(MembersTestsMixin, TestCase):
    def _make_vol(
        self,
        username,
        status=Volunteer.STATUS_DORMANT,
        last_login=None,
        joined_days_ago=1200,
    ):
        member = Member.objects.create(
            name=f"BA {username}", email=f"{username}@ba.test"
        )
        user = User.objects.create_user(username, f"{username}@ba.test", "pw")
        User.objects.filter(pk=user.pk).update(
            date_joined=_days_ago(joined_days_ago), last_login=last_login
        )
        vol = Volunteer.objects.create(member=member, user=user, status=status)
        Volunteer.objects.filter(pk=vol.pk).update(
            created_at=_days_ago(joined_days_ago)
        )
        return Volunteer.objects.get(pk=vol.pk)

    def setUp(self):
        super().setUp()
        config = get_site_config()
        config.volunteer_purge_days = 1095
        config.save()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )


class TestBulkAnonymiseVolunteers(BulkActionsBase):
    def test_select_with_no_ids_warns_and_redirects(self):
        resp = self.client.post(
            reverse("bulk-anonymise-volunteers"), {"action": "select"}
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_select_with_invalid_ids_errors(self):
        resp = self.client.post(
            reverse("bulk-anonymise-volunteers"),
            {"action": "select", "volunteer_ids": ["not-a-number"]},
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_select_with_non_candidate_ids_warns(self):
        # An active volunteer is never a purge candidate.
        vol = self._make_vol(
            "active", status=Volunteer.STATUS_ACTIVE, joined_days_ago=1
        )
        resp = self.client.post(
            reverse("bulk-anonymise-volunteers"),
            {"action": "select", "volunteer_ids": [str(vol.pk)]},
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_select_shows_confirmation_page(self):
        vol = self._make_vol("cand", last_login=_days_ago(1200))
        resp = self.client.post(
            reverse("bulk-anonymise-volunteers"),
            {"action": "select", "volunteer_ids": [str(vol.pk)]},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "bulk_anonymise_confirm.html")
        self.assertEqual(resp.context["count"], 1)
        self.assertEqual(
            resp.context["expected_phrase"], "anonymise 1 volunteer"
        )
        self.assertContains(resp, "BA cand")

    def test_confirm_with_wrong_phrase_re_renders(self):
        vol = self._make_vol("wrongphrase", last_login=_days_ago(1200))
        resp = self.client.post(
            reverse("bulk-anonymise-volunteers"),
            {
                "action": "confirm",
                "volunteer_ids": [str(vol.pk)],
                "confirm_phrase": "not the right phrase",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "bulk_anonymise_confirm.html")
        self.assertContains(resp, "did not match")
        self.assertEqual(
            resp.context["expected_phrase"], "anonymise 1 volunteer"
        )
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_DORMANT)
        self.assertEqual(AnonymisationLog.objects.count(), 0)

    def test_confirm_with_invalid_ids_errors(self):
        resp = self.client.post(
            reverse("bulk-anonymise-volunteers"),
            {"action": "confirm", "volunteer_ids": ["not-a-number"]},
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_confirm_with_correct_phrase_anonymises(self):
        vol = self._make_vol("realconfirm", last_login=_days_ago(1200))
        role = Role.objects.create(name="BA Role", standard=True)
        event = Event.objects.create(name="BA Event")
        showing = Showing.objects.create(
            event=event,
            start=timezone.now() - datetime.timedelta(days=30),
            confirmed=True,
        )
        entry = RotaEntry.objects.create(
            showing=showing,
            role=role,
            volunteer=vol,
            name=vol.member.name,
            rank=1,
        )
        resp = self.client.post(
            reverse("bulk-anonymise-volunteers"),
            {
                "action": "confirm",
                "volunteer_ids": [str(vol.pk)],
                "confirm_phrase": "anonymise 1 volunteer",
            },
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ANONYMISED)
        self.assertEqual(
            AnonymisationLog.objects.filter(volunteer_pk=vol.pk).count(), 1
        )
        entry.refresh_from_db()
        self.assertIsNone(entry.volunteer_id)

    def test_get_redirects_without_side_effects(self):
        vol = self._make_vol("getreq", last_login=_days_ago(1200))
        resp = self.client.get(reverse("bulk-anonymise-volunteers"))
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_DORMANT)

    def test_non_superuser_forbidden(self):
        vol = self._make_vol(
            "plain", status=Volunteer.STATUS_ACTIVE, joined_days_ago=1
        )
        self.client.logout()
        self.client.force_login(vol.user)
        resp = self.client.post(
            reverse("bulk-anonymise-volunteers"), {"action": "select"}
        )
        self.assertNotEqual(resp.status_code, 200)


class TestBulkDeleteNeverOnboarded(BulkActionsBase):
    def _make_never_onboarded(self, username, joined_days_ago=1200):
        return self._make_vol(
            username,
            status=Volunteer.STATUS_DORMANT,
            last_login=None,
            joined_days_ago=joined_days_ago,
        )

    def test_select_with_no_ids_warns(self):
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"), {"action": "select"}
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_select_with_invalid_ids_errors(self):
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"),
            {"action": "select", "volunteer_ids": ["nope"]},
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_select_excludes_ineligible_volunteers(self):
        # Logged in at least once -> not eligible for the "never onboarded" flow.
        vol = self._make_vol("loggedin", last_login=_days_ago(1200))
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"),
            {"action": "select", "volunteer_ids": [str(vol.pk)]},
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_select_splits_clean_from_rota_history(self):
        clean = self._make_never_onboarded("clean1")
        has_history = self._make_never_onboarded("hashist1")
        role = Role.objects.create(name="BA Role2", standard=True)
        event = Event.objects.create(name="BA Event2")
        showing = Showing.objects.create(
            event=event,
            start=timezone.now() - datetime.timedelta(days=30),
            confirmed=True,
        )
        RotaEntry.objects.create(
            showing=showing,
            role=role,
            volunteer=has_history,
            name=has_history.member.name,
            rank=1,
        )
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"),
            {
                "action": "select",
                "volunteer_ids": [str(clean.pk), str(has_history.pk)],
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(
            resp, "bulk_delete_never_onboarded_confirm.html"
        )
        self.assertEqual(resp.context["delete_count"], 1)
        self.assertEqual(resp.context["anonymise_count"], 1)
        self.assertEqual(resp.context["to_delete"][0].pk, clean.pk)
        self.assertEqual(resp.context["to_anonymise"][0].pk, has_history.pk)

    def test_select_splits_by_last_gasp_history_too(self):
        gasped = self._make_never_onboarded("gasped1")
        LastGaspEmailLog.objects.create(volunteer=gasped, sent_by=None)
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"),
            {"action": "select", "volunteer_ids": [str(gasped.pk)]},
        )
        self.assertEqual(resp.context["delete_count"], 0)
        self.assertEqual(resp.context["anonymise_count"], 1)

    def test_confirm_wrong_phrase_re_renders_without_deleting(self):
        vol = self._make_never_onboarded("wrongdel")
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"),
            {
                "action": "confirm",
                "volunteer_ids": [str(vol.pk)],
                "confirm_phrase": "definitely not it",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(
            resp, "bulk_delete_never_onboarded_confirm.html"
        )
        self.assertContains(resp, "did not match")
        self.assertTrue(Volunteer.objects.filter(pk=vol.pk).exists())

    def test_confirm_with_invalid_ids_errors(self):
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"),
            {"action": "confirm", "volunteer_ids": ["nope"]},
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_confirm_hard_deletes_clean_volunteers(self):
        vol = self._make_never_onboarded("harddel")
        member_pk = vol.member.pk
        user_pk = vol.user.pk
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"),
            {
                "action": "confirm",
                "volunteer_ids": [str(vol.pk)],
                "confirm_phrase": "delete 1 volunteer",
            },
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))
        self.assertFalse(Volunteer.objects.filter(pk=vol.pk).exists())
        self.assertFalse(Member.objects.filter(pk=member_pk).exists())
        self.assertFalse(User.objects.filter(pk=user_pk).exists())

    def test_confirm_hard_delete_also_removes_portrait_file(self):
        vol = self._make_never_onboarded("harddelportrait")
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media):
                vol.portrait.save(
                    "portrait.jpg",
                    SimpleUploadedFile("portrait.jpg", b"fake-image-bytes"),
                    save=True,
                )
                portrait_path = vol.portrait.path
                self.assertTrue(os.path.exists(portrait_path))

                resp = self.client.post(
                    reverse("bulk-delete-never-onboarded"),
                    {
                        "action": "confirm",
                        "volunteer_ids": [str(vol.pk)],
                        "confirm_phrase": "delete 1 volunteer",
                    },
                )
                self.assertRedirects(
                    resp, reverse("view-volunteer-pool-health")
                )
                self.assertFalse(Volunteer.objects.filter(pk=vol.pk).exists())
                self.assertFalse(os.path.exists(portrait_path))

    def test_confirm_falls_back_to_anonymise_when_rota_history_exists(self):
        vol = self._make_never_onboarded("fallback")
        role = Role.objects.create(name="BA Role3", standard=True)
        event = Event.objects.create(name="BA Event3")
        showing = Showing.objects.create(
            event=event,
            start=timezone.now() - datetime.timedelta(days=30),
            confirmed=True,
        )
        entry = RotaEntry.objects.create(
            showing=showing,
            role=role,
            volunteer=vol,
            name=vol.member.name,
            rank=1,
        )
        # expected_phrase is keyed on delete_count only (0 here, since the
        # sole candidate has rota history and falls into to_anonymise).
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"),
            {
                "action": "confirm",
                "volunteer_ids": [str(vol.pk)],
                "confirm_phrase": "delete 0 volunteers",
            },
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ANONYMISED)
        entry.refresh_from_db()
        self.assertIsNone(entry.volunteer_id)

    def test_get_redirects_without_side_effects(self):
        vol = self._make_never_onboarded("getdel")
        resp = self.client.get(reverse("bulk-delete-never-onboarded"))
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))
        self.assertTrue(Volunteer.objects.filter(pk=vol.pk).exists())

    def test_non_superuser_forbidden(self):
        vol = self._make_vol(
            "plain2", status=Volunteer.STATUS_ACTIVE, joined_days_ago=1
        )
        self.client.logout()
        self.client.force_login(vol.user)
        resp = self.client.post(
            reverse("bulk-delete-never-onboarded"), {"action": "select"}
        )
        self.assertNotEqual(resp.status_code, 200)


class TestAdminRestoreVolunteerNoOp(BulkActionsBase):
    def test_active_volunteer_unchanged_with_warning(self):
        vol = self._make_vol(
            "activenoop", status=Volunteer.STATUS_ACTIVE, joined_days_ago=1
        )
        resp = self.client.post(
            reverse("admin-restore-volunteer", kwargs={"volunteer_id": vol.pk})
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ACTIVE)


class TestLastGaspEmailDisabled(BulkActionsBase):
    def test_get_when_disabled_redirects_with_warning(self):
        config = get_site_config()
        config.last_gasp_email_enabled = False
        config.save()
        vol = self._make_vol("lgdisabled", last_login=_days_ago(1200))
        resp = self.client.get(
            reverse("last-gasp-email", kwargs={"volunteer_id": vol.pk})
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))


class TestAutoDormancyApplyDisabled(BulkActionsBase):
    def test_apply_warns_when_thresholds_unset(self):
        config = get_site_config()
        config.volunteer_dormancy_days = 0
        config.volunteer_never_logged_in_grace_days = 0
        config.save()
        resp = self.client.post(reverse("auto-dormancy-apply"))
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))


class TestBulkLastGaspEmail(BulkActionsBase):
    def setUp(self):
        super().setUp()
        config = get_site_config()
        config.last_gasp_email_enabled = True
        config.last_gasp_email_subject = "Still with us, {name}?"
        config.last_gasp_email_body = "Hi {name}, we miss you at {venue}."
        config.last_gasp_cooldown_days = 30
        config.save()

    def test_disabled_flag_redirects_with_warning(self):
        config = get_site_config()
        config.last_gasp_email_enabled = False
        config.save()
        resp = self.client.post(
            reverse("bulk-last-gasp-email"),
            {"volunteer_ids": ["1"]},
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_get_redirects(self):
        resp = self.client.get(reverse("bulk-last-gasp-email"))
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_no_ids_warns(self):
        resp = self.client.post(reverse("bulk-last-gasp-email"), {})
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_invalid_ids_errors(self):
        resp = self.client.post(
            reverse("bulk-last-gasp-email"),
            {"volunteer_ids": ["not-a-number"]},
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_unknown_ids_warns(self):
        resp = self.client.post(
            reverse("bulk-last-gasp-email"), {"volunteer_ids": ["999999"]}
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_compose_step_shows_recipients_and_cooldown_flag(self):
        vol = self._make_vol("compose1", last_login=_days_ago(1200))
        LastGaspEmailLog.objects.create(volunteer=vol, sent_by=None)
        resp = self.client.post(
            reverse("bulk-last-gasp-email"),
            {"volunteer_ids": [str(vol.pk)]},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "bulk_last_gasp_email.html")
        self.assertEqual(resp.context["ready_count"], 0)
        self.assertEqual(resp.context["cooldown_count"], 1)

    def test_send_step_empty_body_errors(self):
        vol = self._make_vol("sendempty", last_login=_days_ago(1200))
        config = get_site_config()
        config.last_gasp_email_body = ""
        config.save()
        resp = self.client.post(
            reverse("bulk-last-gasp-email"),
            {
                "action": "send",
                "volunteer_ids": [str(vol.pk)],
                "subject": "",
                "body": "",
            },
        )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))

    def test_send_step_sends_and_logs(self):
        vol = self._make_vol("sendok", last_login=_days_ago(1200))
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            resp = self.client.post(
                reverse("bulk-last-gasp-email"),
                {
                    "action": "send",
                    "volunteer_ids": [str(vol.pk)],
                    "subject": "Still with us, {name}?",
                    "body": "Hi {name}, we miss you at {venue}.",
                },
            )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))
        self.assertEqual(
            LastGaspEmailLog.objects.filter(volunteer=vol).count(), 1
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [vol.member.email])
        self.assertIn("BA sendok", mail.outbox[0].subject)

    def test_send_step_skips_volunteers_in_cooldown(self):
        vol = self._make_vol("sendcd", last_login=_days_ago(1200))
        LastGaspEmailLog.objects.create(volunteer=vol, sent_by=None)
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            resp = self.client.post(
                reverse("bulk-last-gasp-email"),
                {
                    "action": "send",
                    "volunteer_ids": [str(vol.pk)],
                    "subject": "Still with us, {name}?",
                    "body": "Hi {name}, we miss you at {venue}.",
                },
            )
        self.assertRedirects(resp, reverse("view-volunteer-pool-health"))
        # Still just the one log entry created above, before the POST.
        self.assertEqual(
            LastGaspEmailLog.objects.filter(volunteer=vol).count(), 1
        )
        self.assertEqual(len(mail.outbox), 0)
