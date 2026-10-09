# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime
from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.diary.models import Room, SiteConfiguration, get_site_config
from toolkit.hires import services
from toolkit.hires.models import (
    HireEnquiry as E,
    HireSettings,
    HireType,
    ProgrammingMeeting,
)


def set_flag(on):
    cfg = get_site_config()
    cfg.hire_enquiries_enabled = on
    cfg.save()
    cache.delete(SiteConfiguration._CACHE_KEY)


class HireBase(TestCase):
    def setUp(self):
        cache.clear()
        set_flag(True)
        self.cfg = HireSettings.load()
        self.cfg.notification_addresses = "programming@example.org"
        self.cfg.save()
        self.room = Room.objects.create(name="Cinema")
        self.htype = HireType.objects.create(
            name="Cinema",
            community_fee_gbp=Decimal("100"),
            corporate_fee_gbp=Decimal("200"),
        )
        today = timezone.localdate()
        self.meeting = ProgrammingMeeting.objects.create(
            date=today + datetime.timedelta(days=10)
        )
        from toolkit.test_common import create_toolkit_test_users

        self.programmer = create_toolkit_test_users().admin

    def post_data(self, **over):
        day = timezone.localdate() + datetime.timedelta(days=30)
        data = {
            "contact_name": "Ada",
            "contact_email": "ada@example.org",
            "hire_type": self.htype.pk,
            "tier_requested": "community",
            "title": "Film night",
            "description": "A film",
            "sound_tech": "none",
            "acknowledgements": self.cfg.acknowledgement_list(),
            "date_1": day.isoformat(),
            "get_in_1": "17:00",
            "start_1": "18:00",
            "end_1": "21:00",
            "get_out_1": "22:00",
        }
        data.update(over)
        return data

    def make_enquiry(self, **kw):
        e = E.objects.create(
            contact_name="Ada",
            contact_email="ada@example.org",
            hire_type=self.htype,
            title="Film night",
            description="x",
            **kw,
        )
        from toolkit.hires.models import HireDate

        # Fixed 17:00 to 22:00 local, so "late night" never depends on the
        # time of day the tests happen to run.
        day = timezone.make_aware(
            datetime.datetime.combine(
                timezone.localdate() + datetime.timedelta(days=30),
                datetime.time(17, 0),
            )
        )
        HireDate.objects.create(
            enquiry=e,
            get_in=day,
            start=day + datetime.timedelta(hours=1),
            end=day + datetime.timedelta(hours=4),
            get_out=day + datetime.timedelta(hours=5),
        )
        services.assign_meeting(e, self.meeting)
        e.status = E.TO_DISCUSS
        e.save()
        return e


class FeatureFlagTests(HireBase):
    def test_everything_404s_when_flag_off(self):
        e = self.make_enquiry()
        set_flag(False)
        self.client.force_login(self.programmer)
        for name, kw in [
            ("enquire", {}),
            ("thanks", {}),
            ("queue", {}),
            ("settings", {}),
            ("meetings", {}),
            ("types", {}),
            ("techs", {}),
            ("emails", {}),
            ("detail", {"pk": e.pk}),
            ("agree", {"token": "abc"}),
        ]:
            r = self.client.get(reverse(f"hires:{name}", kwargs=kw))
            self.assertEqual(r.status_code, 404, name)
        r = self.client.post(
            reverse("hires:act", kwargs={"pk": e.pk}), {"action": "decline"}
        )
        self.assertEqual(r.status_code, 404)

    def test_clock_paused_when_flag_off(self):
        e = self.make_enquiry()
        e.reply_deadline = timezone.localdate() - datetime.timedelta(days=1)
        e.save()
        set_flag(False)
        result = services.run_clock()
        self.assertTrue(result["paused"])
        e.refresh_from_db()
        self.assertEqual(e.status, E.TO_DISCUSS)
        self.assertEqual(len(mail.outbox), 0)

    def test_nav_link_hidden_when_flag_off(self):
        self.client.force_login(self.programmer)
        set_flag(False)
        r = self.client.get(reverse("programming-queue"))
        self.assertNotContains(r, "/hires/manage/")


class PublicFormTests(HireBase):
    def test_submit_creates_enquiry_and_acknowledges(self):
        r = self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertRedirects(r, reverse("hires:thanks"))
        e = E.objects.get()
        self.assertEqual(e.status, E.ACKNOWLEDGED)
        self.assertEqual(e.meeting, self.meeting)
        self.assertEqual(
            e.reply_deadline,
            self.meeting.date + datetime.timedelta(days=7),
        )
        self.assertEqual(e.hire_dates.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("by", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["ada@example.org"])

    def test_too_short_access_window_rejected(self):
        r = self.client.post(
            reverse("hires:enquire"),
            self.post_data(
                get_in_1="18:00",
                get_out_1="20:00",
                start_1="18:30",
                end_1="19:30",
            ),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(E.objects.exists())
        self.assertContains(r, "at least 3 hours")

    def test_honeypot_blocks(self):
        self.client.post(
            reverse("hires:enquire"), self.post_data(website="spam")
        )
        self.assertFalse(E.objects.exists())

    def test_must_tick_all_acknowledgements(self):
        data = self.post_data()
        data["acknowledgements"] = data["acknowledgements"][:1]
        self.client.post(reverse("hires:enquire"), data)
        self.assertFalse(E.objects.exists())

    def test_closed_switch_shows_message(self):
        self.cfg.enquiries_open = False
        self.cfg.save()
        r = self.client.get(reverse("hires:enquire"))
        self.assertContains(r, "taking new hire enquiries")
        self.assertNotContains(r, "<form")

    def test_sound_tech_none_rejected_when_type_needs_one(self):
        self.htype.needs_sound_tech = True
        self.htype.save()
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertFalse(E.objects.exists())

    def test_rate_limit_per_address(self):
        for _ in range(3):
            self.client.post(reverse("hires:enquire"), self.post_data())
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertEqual(E.objects.count(), 3)

    def test_late_night_flagged(self):
        self.client.post(
            reverse("hires:enquire"),
            self.post_data(
                late_night_ack="on", end_1="23:30", get_out_1="23:59"
            ),
        )
        e = E.objects.get()
        self.assertTrue(e.hire_dates.get().is_late_night())


class ClockTests(HireBase):
    def test_auto_decline_at_deadline_sends_honest_email(self):
        e = self.make_enquiry()
        e.reply_deadline = timezone.localdate()
        e.save()
        services.run_clock()
        e.refresh_from_db()
        self.assertEqual(e.status, E.DECLINED_CAPACITY)
        self.assertIn(
            "capacity", mail.outbox[-1].subject + mail.outbox[-1].body
        )
        self.assertEqual(mail.outbox[-1].to, ["ada@example.org"])

    def test_person_decision_stops_clock(self):
        e = self.make_enquiry()
        e.reply_deadline = timezone.localdate()
        e.save()
        services.decline(e, self.programmer)
        mail.outbox.clear()
        services.run_clock()
        self.assertEqual(len(mail.outbox), 0)

    def test_digest_sent_once(self):
        self.make_enquiry()
        out = services.run_clock(
            today=self.meeting.date - datetime.timedelta(days=4)
        )
        self.assertEqual(out["digests"], 1)
        self.assertEqual(mail.outbox[0].to, ["programming@example.org"])
        self.assertNotIn("@", mail.outbox[0].body.replace("example.org", ""))
        out = services.run_clock(
            today=self.meeting.date - datetime.timedelta(days=3)
        )
        self.assertEqual(out["digests"], 0)

    def test_last_call_only_for_undecided(self):
        e = self.make_enquiry()
        e.reply_deadline = timezone.localdate() + datetime.timedelta(days=1)
        e.save()
        out = services.run_clock()
        self.assertEqual(out["last_calls"], 1)

    def test_outside_reply_postpones_not_stops(self):
        later = ProgrammingMeeting.objects.create(
            date=self.meeting.date + datetime.timedelta(days=30)
        )
        e = self.make_enquiry()
        with self.assertRaises(ValueError):
            services.replied_outside_toolkit(e, "")
        services.replied_outside_toolkit(e, "told them we'd look")
        e.refresh_from_db()
        self.assertEqual(e.meeting, later)
        self.assertTrue(e.is_open)

    def test_cancelled_meeting_moves_enquiries_and_tells_hirer(self):
        later = ProgrammingMeeting.objects.create(
            date=self.meeting.date + datetime.timedelta(days=30)
        )
        e = self.make_enquiry()
        services.meeting_cancelled(self.meeting)
        e.refresh_from_db()
        self.assertEqual(e.meeting, later)
        self.assertEqual(len(mail.outbox), 1)

    def test_no_meetings_falls_back(self):
        ProgrammingMeeting.objects.all().delete()
        e = E.objects.create(
            contact_name="A",
            contact_email="a@example.org",
            title="t",
            description="d",
            hire_type=self.htype,
        )
        services.assign_meeting(e)
        self.assertEqual(
            e.reply_deadline,
            timezone.localdate()
            + datetime.timedelta(days=self.cfg.fallback_reply_days),
        )

    def test_maybe_callout_and_timeout(self):
        e = self.make_enquiry()
        services.mark_maybe(e, self.programmer, "need a keyholder")
        self.assertEqual(len(mail.outbox), 2)  # hirer + list
        e.callout_deadline = timezone.localdate()
        e.save()
        mail.outbox.clear()
        services.run_clock()
        e.refresh_from_db()
        self.assertEqual(e.status, E.DECLINED_NO_SUPPORT)
        self.assertEqual(mail.outbox[0].to, ["ada@example.org"])


class DecisionTests(HireBase):
    def test_accept_creates_proposed_event(self):
        e = self.make_enquiry()
        e.rooms_requested.add(self.room)
        event = services.accept(e, self.programmer)
        e.refresh_from_db()
        self.assertEqual(e.status, E.ACCEPTED)
        self.assertTrue(event.outside_hire)
        self.assertEqual(event.programming_status, "proposed")
        self.assertEqual(event.cost_type, "venue_hire")
        self.assertEqual(event.showings.count(), 1)
        self.assertEqual(
            event.showings.get().room_bookings.get().room, self.room
        )
        self.assertEqual(e.agreed_fee_gbp, Decimal("100"))

    def test_terms_agreement_flow(self):
        e = self.make_enquiry()
        event = services.accept(e, self.programmer)
        event.terms = "Hirer pays £100 and clears up."
        event.save()
        services.send_confirmation(e)
        e.refresh_from_db()
        self.assertEqual(e.status, E.AWAITING_AGREEMENT)
        self.assertIn(e.agreement_token, mail.outbox[-1].body)
        url = reverse("hires:agree", kwargs={"token": e.agreement_token})
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url)
        e.refresh_from_db()
        self.assertEqual(e.status, E.BOOKED)
        self.assertIn("£100", e.terms_agreed_snapshot)
        event.refresh_from_db()
        self.assertEqual(event.programming_status, "active")

    def test_cannot_confirm_without_terms(self):
        e = self.make_enquiry()
        event = services.accept(e, self.programmer)
        event.terms = ""
        event.cost_type = "tbc"
        event.save()
        with self.assertRaises(ValueError):
            services.send_confirmation(e)

    def test_estimate_subtracts_late_night_security(self):
        self.cfg.late_night_fee_gbp = Decimal("50")
        self.cfg.late_night_security_cost_gbp = Decimal("80")
        self.cfg.save()
        e = self.make_enquiry()
        d = e.hire_dates.get()
        d.get_out = d.get_in.replace(hour=23, minute=50) + datetime.timedelta(
            days=1
        )
        d.save()
        self.assertEqual(e.estimate_gbp(), Decimal("100") + 50 - 80)


class ViewTests(HireBase):
    def test_queue_requires_login(self):
        r = self.client.get(reverse("hires:queue"))
        self.assertEqual(r.status_code, 302)

    def test_queue_and_detail_render(self):
        e = self.make_enquiry()
        self.client.force_login(self.programmer)
        self.assertContains(
            self.client.get(reverse("hires:queue")), "Film night"
        )
        self.assertContains(
            self.client.get(reverse("hires:detail", kwargs={"pk": e.pk})),
            "Film night",
        )

    def test_decline_via_view(self):
        e = self.make_enquiry()
        self.client.force_login(self.programmer)
        self.client.post(
            reverse("hires:act", kwargs={"pk": e.pk}), {"action": "decline"}
        )
        e.refresh_from_db()
        self.assertEqual(e.status, E.DECLINED)

    def test_settings_rejects_comma_joined_addresses(self):
        self.client.force_login(self.programmer)
        from toolkit.hires.forms import HireSettingsForm

        form = HireSettingsForm(
            {
                **{
                    f: getattr(self.cfg, f)
                    for f in HireSettingsForm.base_fields
                    if getattr(self.cfg, f) is not None
                },
                "notification_addresses": "a@example.org, b@example.org",
            },
            instance=self.cfg,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("notification_addresses", form.errors)


class ScreenRenderTests(HireBase):
    """Every management screen renders, in every state that has a link."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.programmer)

    def test_detail_renders_in_each_state(self):
        e = self.make_enquiry()
        url = reverse("hires:detail", kwargs={"pk": e.pk})
        self.assertEqual(self.client.get(url).status_code, 200)
        services.accept(e, self.programmer)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Open the event")
        e.event.terms = "Hirer pays and clears up."
        e.event.save()
        services.send_confirmation(e)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(
            reverse("hires:agree", kwargs={"token": e.agreement_token})
        )
        self.assertContains(self.client.get(url), "Frozen terms")

    def test_settings_screens_render(self):
        for name in ("settings", "meetings", "types", "techs", "emails"):
            r = self.client.get(reverse(f"hires:{name}"))
            self.assertEqual(r.status_code, 200, name)

    def test_every_email_template_page_renders(self):
        from toolkit.hires import defaults

        for key in list(defaults.EMAIL_DEFAULTS) + list(
            defaults.INTERNAL_DEFAULTS
        ):
            r = self.client.get(reverse("hires:emails") + f"?key={key}")
            self.assertEqual(r.status_code, 200, key)

    def test_thanks_page_renders(self):
        self.assertEqual(
            self.client.get(reverse("hires:thanks")).status_code, 200
        )

    def test_nav_link_shown_when_flag_on(self):
        r = self.client.get(reverse("programming-queue"))
        self.assertContains(r, reverse("hires:queue"))

    def test_email_override_is_used(self):
        from toolkit.hires.models import HireEmailTemplate

        HireEmailTemplate.objects.create(
            key="declined", subject="Custom {title}", body="Custom body"
        )
        e = self.make_enquiry()
        services.decline(e, self.programmer)
        self.assertEqual(mail.outbox[-1].subject, "Custom Film night")

    def test_bad_placeholder_does_not_block_email(self):
        from toolkit.hires.models import HireEmailTemplate

        HireEmailTemplate.objects.create(
            key="declined", subject="Hi {nonsense}", body="Body {oops}"
        )
        e = self.make_enquiry()
        services.decline(e, self.programmer)
        self.assertEqual(len(mail.outbox), 1)


class EmailLinkTests(HireBase):
    def test_links_in_emails_are_absolute(self):
        from django.test import override_settings

        with override_settings(
            VENUE={
                **__import__("django.conf").conf.settings.VENUE,
                "siteurl": "https://example.test",
            }
        ):
            e = self.make_enquiry()
            event = services.accept(e, self.programmer)
            event.terms = "Terms."
            event.save()
            services.send_confirmation(e)
            self.assertIn(
                "https://example.test/hires/agree/", mail.outbox[-1].body
            )
            mail.outbox.clear()
            services.mark_maybe(e, self.programmer, "need a keyholder")
            self.assertIn(
                "https://example.test/hires/manage/", mail.outbox[-1].body
            )


class ReviewFixTests(HireBase):
    """Regressions from the external (DeepSeek) review of services.py."""

    def test_notification_failure_does_not_stop_auto_decline(self):
        from unittest import mock

        e = self.make_enquiry()
        e.reply_deadline = timezone.localdate()
        e.save()
        real = services._send

        def flaky(to, subject, body, source):
            if to == ["programming@example.org"]:
                raise OSError("smtp down")
            return real(to, subject, body, source)

        with mock.patch.object(services, "_send", flaky):
            services.run_clock(today=self.meeting.date - datetime.timedelta(1))
            services.run_clock()
        e.refresh_from_db()
        self.assertEqual(e.status, E.DECLINED_CAPACITY)

    def test_outside_reply_with_no_later_meeting_still_postpones(self):
        e = self.make_enquiry()
        old = e.reply_deadline
        services.replied_outside_toolkit(e, "told them we'd look")
        e.refresh_from_db()
        self.assertGreater(e.reply_deadline, old)
        self.assertIsNone(e.meeting)

    def test_moving_meeting_resets_digest(self):
        e = self.make_enquiry()
        e.digest_sent_at = timezone.now()
        services.assign_meeting(e, self.meeting)
        self.assertIsNone(e.digest_sent_at)

    def test_failed_confirmation_email_rolls_back(self):
        from unittest import mock

        e = self.make_enquiry()
        event = services.accept(e, self.programmer)
        event.terms = "Terms."
        event.save()
        with mock.patch.object(services, "_send", side_effect=OSError("x")):
            with self.assertRaises(ValueError):
                services.send_confirmation(e)
        e.refresh_from_db()
        self.assertEqual(e.status, E.ACCEPTED)
        self.assertEqual(e.agreement_token, "")

    def test_failed_accept_leaves_status_untouched(self):
        e = self.make_enquiry()
        e.status = E.MAYBE
        e.save()
        services.volunteer_to_coordinate(e, self.programmer)
        e.refresh_from_db()
        self.assertEqual(e.status, E.ACCEPTED)


class ErrorSummaryTests(HireBase):
    def test_summary_has_one_entry_per_date_and_links(self):
        r = self.client.post(reverse("hires:enquire"), {})
        self.assertContains(r, "Please fix the problems below")
        self.assertContains(r, 'href="#date-row-1"', count=1)
        self.assertContains(r, 'href="#field-contact_name"')
        self.assertNotContains(r, 'href="#field-get_in_1"')


class MessageHistoryTests(HireBase):
    def log(self, enquiry, source, success=True, to=None, subject="Subject"):
        from toolkit.audit.models import SentEmailLog

        return SentEmailLog.objects.create(
            recipients=to or enquiry.contact_email,
            subject=subject,
            success=success,
            error="" if success else "smtp down",
            backend="x",
            trigger_source=source,
        )

    def test_detail_lists_messages_and_hides_other_addresses(self):
        e = self.make_enquiry()
        self.log(e, "Hire enquiry: acknowledgement", subject="We got it")
        self.log(
            e,
            "Hire enquiry: declined",
            to="bada@example.org",
            subject="Not for you",
        )
        self.log(
            e,
            "Hire enquiry: declined",
            to="x@example.org, ada@example.org",
            subject="Shared",
        )
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:detail", kwargs={"pk": e.pk}))
        self.assertContains(r, "We got it")
        self.assertContains(r, "Shared")
        self.assertNotContains(r, "Not for you")

    def test_failed_email_shows_banner_and_queue_badge(self):
        e = self.make_enquiry()
        self.log(e, "Hire enquiry: acknowledgement", success=False)
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:detail", kwargs={"pk": e.pk}))
        self.assertContains(r, "did not send")
        self.assertContains(r, "Try sending again")
        self.assertContains(
            self.client.get(reverse("hires:queue")), "Hirer email failed"
        )

    def test_later_success_clears_the_problem(self):
        e = self.make_enquiry()
        self.log(e, "Hire enquiry: acknowledgement", success=False)
        self.log(e, "Hire enquiry: acknowledgement", success=True)
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:detail", kwargs={"pk": e.pk}))
        self.assertNotContains(r, "did not send")
        self.assertNotContains(
            self.client.get(reverse("hires:queue")), "Hirer email failed"
        )

    def test_old_mail_before_the_enquiry_is_ignored(self):
        from toolkit.audit.models import SentEmailLog

        e = self.make_enquiry()
        row = self.log(e, "Hire enquiry: acknowledgement", success=False)
        SentEmailLog.objects.filter(pk=row.pk).update(
            sent_at=e.submitted_at - datetime.timedelta(days=5)
        )
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:detail", kwargs={"pk": e.pk}))
        self.assertNotContains(r, "did not send")

    def test_retry_resends_and_unknown_key_is_refused(self):
        e = self.make_enquiry()
        e.status = E.DECLINED
        e.save()
        self.client.force_login(self.programmer)
        url = reverse("hires:act", kwargs={"pk": e.pk})
        self.client.post(url, {"action": "resend", "key": "declined"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ada@example.org"])
        self.client.post(url, {"action": "resend", "key": "nonsense"})
        self.assertEqual(len(mail.outbox), 1)

    def test_other_users_cannot_resend(self):
        e = self.make_enquiry()
        from django.contrib.auth.models import User

        User.objects.create_user("plain", password="x")
        self.client.login(username="plain", password="x")
        r = self.client.post(
            reverse("hires:act", kwargs={"pk": e.pk}),
            {"action": "resend", "key": "declined"},
        )
        self.assertIn(r.status_code, (302, 403))
        self.assertEqual(len(mail.outbox), 0)


class PurgeTests(HireBase):
    def closed(self, status, days_ago, **kw):
        e = self.make_enquiry(**kw)
        e.status = status
        e.status_changed_at = timezone.now() - datetime.timedelta(
            days=days_ago
        )
        e.contact_phone = "07000 111111"
        e.internal_notes = "Rang twice"
        e.save()
        return e

    def test_declined_enquiry_purged_after_retention_period(self):
        from toolkit.hires import purge

        old = self.closed(E.DECLINED, 200)  # default 6 months
        fresh = self.closed(E.DECLINED, 60)
        out = purge.purge_expired()
        self.assertEqual(out["enquiries"], 1)
        old.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(old.contact_email, "")
        self.assertEqual(old.contact_name, "[deleted]")
        self.assertEqual(old.contact_phone, "")
        self.assertEqual(old.internal_notes, "")
        self.assertEqual(old.title, "Deleted enquiry")
        self.assertIsNotNone(old.personal_data_purged_at)
        self.assertEqual(fresh.contact_email, "ada@example.org")
        # the shape is kept
        self.assertEqual(old.hire_type, self.htype)
        self.assertEqual(old.hire_dates.count(), 1)
        self.assertEqual(old.status, E.DECLINED)

    def test_open_enquiries_are_never_purged(self):
        from toolkit.hires import purge

        for status in (
            E.TO_DISCUSS,
            E.MAYBE,
            E.ACCEPTED,
            E.AWAITING_AGREEMENT,
        ):
            self.closed(status, 5000)
        self.assertEqual(purge.purge_expired()["enquiries"], 0)

    def test_dry_run_changes_nothing(self):
        from toolkit.hires import purge

        e = self.closed(E.WITHDRAWN, 400)
        out = purge.purge_expired(dry_run=True)
        self.assertEqual(out["enquiries"], 1)
        e.refresh_from_db()
        self.assertEqual(e.contact_email, "ada@example.org")

    def test_purge_is_idempotent(self):
        from toolkit.hires import purge

        self.closed(E.DECLINED, 400)
        purge.purge_expired()
        self.assertEqual(purge.purge_expired()["enquiries"], 0)

    def test_booked_hire_keeps_financial_record_but_loses_contact(self):
        from toolkit.hires import purge

        e = self.make_enquiry()
        event = services.accept(e, self.programmer)
        event.terms = "Hirer pays."
        event.save()
        services.send_confirmation(e)
        services.record_agreement(e, ip="203.0.113.9")
        e.refresh_from_db()
        self.assertEqual(e.terms_agreed_ip, "203.0.113.9")
        # age it past hirer_purge_years (3) after the hire itself
        far = timezone.localdate() + datetime.timedelta(days=30 + 1200)
        out = purge.purge_expired(today=far)
        self.assertEqual(out["enquiries"], 1)
        e.refresh_from_db()
        self.assertEqual(e.contact_email, "")
        self.assertIsNone(e.terms_agreed_ip)
        self.assertEqual(e.title, "Film night")
        self.assertIn("Hirer pays.", e.terms_agreed_snapshot)
        self.assertEqual(e.agreed_fee_gbp, Decimal("100"))
        self.assertEqual(e.event, event)

    def test_booked_hire_not_purged_before_it_has_happened(self):
        from toolkit.hires import purge

        e = self.make_enquiry()
        e.status = E.BOOKED
        e.status_changed_at = timezone.now() - datetime.timedelta(days=2000)
        e.save()
        # hire date is 30 days in the future, so it is not due
        self.assertEqual(purge.purge_expired()["enquiries"], 0)

    def test_agreed_terms_record_has_no_personal_name(self):
        e = self.make_enquiry(contact_organisation="")
        services.accept(e, self.programmer)
        self.assertNotIn("Ada", services.agreement_snapshot(e))
        e.contact_organisation = "Zine Club"
        self.assertIn("Zine Club", services.agreement_snapshot(e))

    def test_hirer_record_deleted_after_inactivity_unless_open(self):
        from toolkit.hires import purge
        from toolkit.hires.models import Hirer

        h = Hirer.objects.create(name="A", email="a@example.org")
        Hirer.objects.filter(pk=h.pk).update(
            last_activity_at=timezone.now() - datetime.timedelta(days=2000)
        )
        open_enq = self.make_enquiry()
        open_enq.hirer = h
        open_enq.save()
        self.assertEqual(purge.purge_expired()["hirers"], 0)
        self.assertTrue(Hirer.objects.filter(pk=h.pk).exists())
        open_enq.hirer = None
        open_enq.save()
        self.assertEqual(purge.purge_expired()["hirers"], 1)
        self.assertFalse(Hirer.objects.filter(pk=h.pk).exists())

    def test_purge_writes_deletion_log_without_personal_data(self):
        from toolkit.audit.models import DeletionLog
        from toolkit.hires import purge

        self.closed(E.DECLINED, 400)
        purge.purge_expired()
        row = DeletionLog.objects.get(model="HireEnquiry")
        self.assertNotIn("Ada", row.description)
        self.assertNotIn("example.org", row.description)

    def test_purge_runs_even_when_flag_off(self):
        from django.core.management import call_command

        from toolkit.hires import purge  # noqa: F401

        e = self.closed(E.DECLINED, 400)
        set_flag(False)
        call_command("purge_hire_data", stdout=__import__("io").StringIO())
        e.refresh_from_db()
        self.assertEqual(e.contact_email, "")


class PrivacySurfaceTests(HireBase):
    def test_form_shows_retention_before_submit_with_configured_figures(self):
        self.cfg.declined_purge_months = 4
        self.cfg.hirer_purge_years = 2
        self.cfg.save()
        r = self.client.get(reverse("hires:enquire"))
        self.assertContains(r, "up to 4 months")
        self.assertContains(r, "2 years")
        html = r.content.decode()
        self.assertLess(
            html.index("retention-notice"), html.index("Send enquiry")
        )

    def test_public_privacy_page_renders_with_figures(self):
        r = self.client.get(reverse("hires:privacy"))
        self.assertContains(r, "6 months")

    def test_every_hirer_email_links_the_privacy_notice(self):
        e = self.make_enquiry()
        services.decline(e, self.programmer)
        services.send_acknowledgement(e)
        for m in mail.outbox:
            self.assertIn("/hires/privacy/", m.body)

    def test_detail_shows_deletion_date(self):
        e = self.make_enquiry()
        self.client.force_login(self.programmer)
        url = reverse("hires:detail", kwargs={"pk": e.pk})
        self.assertContains(
            self.client.get(url), "once this enquiry is closed"
        )
        services.decline(e, self.programmer)
        self.assertContains(self.client.get(url), "Will be deleted on about")

    def test_privacy_page_404_when_flag_off(self):
        set_flag(False)
        self.assertEqual(
            self.client.get(reverse("hires:privacy")).status_code, 404
        )


class DoorStaffTests(HireBase):
    """Door staff: required and charged for late club nights only."""

    def make_late(self, enquiry):
        d = enquiry.hire_dates.get()
        d.get_out = d.get_in.replace(hour=23, minute=50) + datetime.timedelta(
            days=1
        )
        d.save()

    def club_night(self):
        self.htype.provides_door_staff = True
        self.htype.save()
        e = self.make_enquiry()
        self.make_late(e)
        e.refresh_from_db()
        return e

    def test_required_only_for_late_club_nights(self):
        e = self.make_enquiry()
        self.assertFalse(e.door_staff_required())
        self.make_late(e)
        self.assertFalse(e.door_staff_required())  # late, wrong type
        self.htype.provides_door_staff = True
        self.htype.save()
        e.refresh_from_db()
        self.assertTrue(e.door_staff_required())

    def test_club_night_type_not_late_does_not_need_door_staff(self):
        self.htype.provides_door_staff = True
        self.htype.save()
        self.assertFalse(self.make_enquiry().door_staff_required())

    def test_text_presents_door_staff_as_an_extra_cost_not_a_perk(self):
        self.cfg.door_staff_fee_gbp = Decimal("80")
        self.cfg.save()
        e = self.club_night()
        e.door_staff_fee_gbp = Decimal("80")
        text = services.guarantee_text(e)
        guaranteed = text.split("What is guaranteed:")[1].split("\n")[0]
        self.assertNotIn("door", guaranteed.lower())
        self.assertIn("Door staff:", text)
        self.assertIn("£80", text)
        self.assertIn("additional charge", text)

    def test_no_door_line_for_ordinary_hires(self):
        text = services.guarantee_text(self.make_enquiry())
        self.assertNotIn("Door staff:", text)
        self.assertIn("door staff", text.split("best-effort:")[1])

    def test_accept_records_door_fee_from_settings_or_override(self):
        self.cfg.door_staff_fee_gbp = Decimal("80")
        self.cfg.save()
        e = self.club_night()
        services.accept(e, self.programmer)
        e.refresh_from_db()
        self.assertEqual(e.door_staff_fee_gbp, Decimal("80"))
        e2 = self.club_night()
        services.accept(e2, self.programmer, door_fee=Decimal("95"))
        e2.refresh_from_db()
        self.assertEqual(e2.door_staff_fee_gbp, Decimal("95"))

    def test_ordinary_hire_gets_no_door_fee(self):
        e = self.make_enquiry()
        services.accept(e, self.programmer)
        e.refresh_from_db()
        self.assertIsNone(e.door_staff_fee_gbp)

    def test_confirmation_quotes_door_staff_as_extra(self):
        self.cfg.door_staff_fee_gbp = Decimal("80")
        self.cfg.save()
        e = self.club_night()
        event = services.accept(e, self.programmer)
        event.terms = "Terms."
        event.save()
        services.send_confirmation(e)
        body = mail.outbox[-1].body
        self.assertIn("Plus door staff, charged to you in addition", body)
        self.assertIn("£80.00", body)

    def test_default_statements_make_no_door_promise(self):
        from toolkit.hires import defaults

        self.assertNotIn("door", defaults.ACKNOWLEDGEMENTS.lower())
        self.assertNotIn("door", defaults.HOW_WE_WORK.lower())


class LateNightTests(HireBase):
    LATE = {"end_1": "23:30", "get_out_1": "23:59"}

    def setUp(self):
        super().setUp()
        self.cfg.late_night_fee_gbp = Decimal("50")
        self.cfg.late_night_security_cost_gbp = Decimal("75")
        self.cfg.door_staff_fee_gbp = Decimal("80")
        self.cfg.late_night_licences_per_year = 12
        self.cfg.save()

    def test_late_request_needs_the_acknowledgement(self):
        r = self.client.post(
            reverse("hires:enquire"), self.post_data(**self.LATE)
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(E.objects.exists())
        self.assertContains(r, "note about late finishes")
        self.client.post(
            reverse("hires:enquire"),
            self.post_data(late_night_ack="on", **self.LATE),
        )
        self.assertEqual(E.objects.count(), 1)

    def test_normal_hours_do_not_need_it(self):
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertEqual(E.objects.count(), 1)

    def test_form_page_carries_the_configured_notice_and_fee(self):
        r = self.client.get(reverse("hires:enquire"))
        self.assertContains(r, "Finishing late?")
        self.assertContains(r, "limited number of late nights")
        self.assertContains(r, "£50")

    def test_notice_text_is_configurable(self):
        self.cfg.late_night_notice_text = "Custom nudge after {late_from}."
        self.cfg.save()
        r = self.client.get(reverse("hires:enquire"))
        self.assertContains(r, "Custom nudge after 23:00.")

    def test_internal_figures_never_reach_the_hirer(self):
        self.cfg.late_night_security_cost_gbp = Decimal("7531")
        self.cfg.late_night_licences_per_year = 4242
        self.cfg.save()
        self.htype.provides_door_staff = True
        self.htype.save()
        pages = [self.client.get(reverse("hires:enquire")).content.decode()]
        e = self.make_enquiry()
        d = e.hire_dates.get()
        d.get_out = d.get_in.replace(hour=23, minute=50) + datetime.timedelta(
            days=1
        )
        d.save()
        event = services.accept(e, self.programmer)
        event.terms = "Terms."
        event.save()
        services.send_confirmation(e)
        pages += [m.body for m in mail.outbox]
        pages.append(
            self.client.get(
                reverse("hires:agree", kwargs={"token": e.agreement_token})
            ).content.decode()
        )
        for text in pages:
            self.assertNotIn("7531", text)
            self.assertNotIn("4242", text)
            self.assertNotIn("taxi", text.lower())

    def test_quoted_fee_is_not_net_of_security_cost(self):
        e = self.make_enquiry()
        self.htype.provides_door_staff = False
        d = e.hire_dates.get()
        d.get_out = d.get_in.replace(hour=23, minute=50) + datetime.timedelta(
            days=1
        )
        d.save()
        self.assertEqual(e.charge_gbp(), Decimal("150"))  # 100 + 50 late fee
        self.assertEqual(e.estimate_gbp(), Decimal("75"))  # minus security
        services.accept(e, self.programmer)
        e.refresh_from_db()
        self.assertEqual(e.agreed_fee_gbp, Decimal("150"))
        self.assertEqual(e.estimated_income_gbp, Decimal("75"))

    def test_detail_shows_licence_count_to_the_meeting_only(self):
        first = self.make_enquiry()
        d = first.hire_dates.get()
        d.get_out = d.get_in.replace(hour=23, minute=50) + datetime.timedelta(
            days=1
        )
        d.save()
        services.accept(first, self.programmer)
        second = self.make_enquiry()
        d = second.hire_dates.get()
        d.get_out = d.get_in.replace(hour=23, minute=50) + datetime.timedelta(
            days=1
        )
        d.save()
        usage = services.late_licence_usage(second)
        self.assertEqual(usage["used"], 1)
        self.assertEqual(usage["limit"], 12)
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:detail", kwargs={"pk": second.pk}))
        self.assertContains(r, "1 late-night hire already accepted")

    def test_no_licence_counter_when_limit_blank(self):
        self.cfg.late_night_licences_per_year = None
        self.cfg.save()
        e = self.make_enquiry()
        d = e.hire_dates.get()
        d.get_out = d.get_in.replace(hour=23, minute=50) + datetime.timedelta(
            days=1
        )
        d.save()
        self.assertIsNone(services.late_licence_usage(e))
