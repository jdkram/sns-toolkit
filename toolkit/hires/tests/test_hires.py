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
            "community_case": "A local unfunded film club.",
            "title": "Film night",
            "description": "A film",
            "date_1": day.isoformat(),
            "get_in_1": "17:00",
            "get_out_1": "22:00",
        }
        data.update(over)
        return data

    def send_conf(self, e):
        """Send the booking confirmation as if the hirer had sent details."""
        e.details_completed_at = timezone.now()
        e.save()
        services.send_confirmation(e)

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
            ),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(E.objects.exists())
        self.assertContains(r, "at least 3 hours")

    def test_minimum_can_be_switched_off(self):
        self.cfg.min_duration_enabled = False
        self.cfg.save()
        r = self.client.get(reverse("hires:enquire"))
        self.assertNotContains(r, "at least 3 hours")
        self.client.post(
            reverse("hires:enquire"),
            self.post_data(get_in_1="18:00", get_out_1="19:00"),
        )
        self.assertTrue(E.objects.exists())

    def test_hire_type_minimum_applies_with_site_minimum_off(self):
        self.cfg.min_duration_enabled = False
        self.cfg.save()
        self.htype.min_duration_hours = 4
        self.htype.save()
        r = self.client.post(
            reverse("hires:enquire"),
            self.post_data(get_in_1="18:00", get_out_1="21:00"),
        )
        self.assertFalse(E.objects.exists())
        self.assertContains(r, "at least 4 hours")

    def test_honeypot_blocks(self):
        self.client.post(
            reverse("hires:enquire"), self.post_data(website="spam")
        )
        self.assertFalse(E.objects.exists())

    def test_closed_switch_shows_message(self):
        self.cfg.enquiries_open = False
        self.cfg.save()
        r = self.client.get(reverse("hires:enquire"))
        self.assertContains(r, "taking new hire enquiries")
        self.assertNotContains(r, "<form")

    def test_first_contact_asks_for_little(self):
        r = self.client.get(reverse("hires:enquire"))
        html = r.content.decode()
        for later in (
            "sound tech",
            "Rooms you",
            "Event starts",
            "offer the volunteers",
            "Please confirm you understand",
        ):
            self.assertNotIn(later, html)

    def test_event_times_default_inside_the_window(self):
        self.client.post(reverse("hires:enquire"), self.post_data())
        d = E.objects.get().hire_dates.get()
        self.assertEqual(timezone.localtime(d.get_in).hour, 17)
        self.assertEqual(timezone.localtime(d.start).hour, 18)  # +60 setup
        self.assertEqual(timezone.localtime(d.end).hour, 21)  # -60 teardown

    def test_rate_limit_per_address(self):
        for _ in range(3):
            self.client.post(reverse("hires:enquire"), self.post_data())
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertEqual(E.objects.count(), 3)

    def test_late_night_flagged(self):
        self.client.post(
            reverse("hires:enquire"),
            self.post_data(late_night_ack="on", get_out_1="23:59"),
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
            "haven't been able to take your enquiry on",
            mail.outbox[-1].body.replace("\n", " "),
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
        self.send_conf(e)
        e.refresh_from_db()
        self.assertEqual(e.status, E.AWAITING_AGREEMENT)
        self.assertIn(e.agreement_token, mail.outbox[-1].body)
        url = reverse("hires:agree", kwargs={"token": e.agreement_token})
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url)  # no ticks: refused
        e.refresh_from_db()
        self.assertEqual(e.status, E.AWAITING_AGREEMENT)
        self.client.post(url, {"ack": self.cfg.acknowledgement_list()})
        e.refresh_from_db()
        self.assertEqual(e.status, E.BOOKED)
        self.assertEqual(e.acknowledgements, self.cfg.acknowledgement_list())
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
            self.send_conf(e)

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
        self.send_conf(e)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(
            reverse("hires:agree", kwargs={"token": e.agreement_token}),
            {"ack": self.cfg.acknowledgement_list()},
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

    def test_emails_page_groups_every_email_by_stage(self):
        from toolkit.hires import defaults

        r = self.client.get(reverse("hires:emails"))
        for stage, _blurb, _keys in defaults.EMAIL_STAGES:
            self.assertContains(r, stage)
        staged = [k for _s, _b, ks in defaults.EMAIL_STAGES for k in ks]
        self.assertCountEqual(
            staged,
            list(defaults.EMAIL_DEFAULTS) + list(defaults.INTERNAL_DEFAULTS),
        )

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
            self.send_conf(e)
            self.assertIn(
                "https://example.test/hires/agree/", mail.outbox[-1].body
            )
            mail.outbox.clear()
            other = self.make_enquiry()
            services.mark_maybe(other, self.programmer, "need a keyholder")
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
                self.send_conf(e)
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

    def test_purge_clears_access_tokens(self):
        from toolkit.hires import purge

        e = self.closed(E.DECLINED, 400)
        e.details_token = "tok-d"
        e.agreement_token = "tok-a"
        e.save()
        purge.purge_expired()
        e.refresh_from_db()
        self.assertEqual((e.details_token, e.agreement_token), ("", ""))

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
        self.send_conf(e)
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
        self.send_conf(e)
        body = mail.outbox[-1].body
        self.assertIn("Plus door staff, charged to you in addition", body)
        self.assertIn("£80.00", body)

    def test_default_statements_make_no_door_promise(self):
        from toolkit.hires import defaults

        self.assertNotIn("door", defaults.ACKNOWLEDGEMENTS.lower())
        self.assertNotIn("door", defaults.HOW_WE_WORK.lower())


class LateNightTests(HireBase):
    LATE = {"get_out_1": "23:59"}

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
        self.send_conf(e)
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


class DetailsStageTests(HireBase):
    def accepted(self):
        e = self.make_enquiry()
        e.rooms_requested.clear()
        services.accept(e, self.programmer)
        e.refresh_from_db()
        return e

    def details_post(self, e, **over):
        d = e.hire_dates.get()
        data = {
            "expected_attendance": "80",
            "sound_tech": "none",
            f"start_{d.pk}": "18:00",
            f"end_{d.pk}": "21:00",
        }
        data.update(over)
        return data

    def test_accepted_email_carries_the_details_link(self):
        e = self.accepted()
        self.assertIn(
            f"/hires/details/{e.details_token}/", mail.outbox[-1].body
        )

    def test_details_form_updates_enquiry_event_and_notifies(self):
        e = self.accepted()
        mail.outbox.clear()
        url = reverse("hires:details", kwargs={"token": e.details_token})
        self.assertEqual(self.client.get(url).status_code, 200)
        data = self.details_post(
            e, rooms_requested=[self.room.pk], media_url="https://x.example"
        )
        r = self.client.post(url, data)
        self.assertContains(r, "Thank you")
        e.refresh_from_db()
        self.assertIsNotNone(e.details_completed_at)
        self.assertEqual(e.expected_attendance, 80)
        self.assertEqual(list(e.rooms_requested.all()), [self.room])
        booking = e.event.showings.get().room_bookings.get()
        self.assertEqual(booking.room, self.room)
        self.assertEqual(mail.outbox[-1].to, ["programming@example.org"])

    def test_event_must_sit_inside_the_access_window(self):
        e = self.accepted()
        d = e.hire_dates.get()
        url = reverse("hires:details", kwargs={"token": e.details_token})
        r = self.client.post(
            url, self.details_post(e, **{f"end_{d.pk}": "23:30"})
        )
        self.assertEqual(r.status_code, 200)
        e.refresh_from_db()
        self.assertIsNone(e.details_completed_at)

    def test_sound_tech_none_rejected_when_type_needs_one(self):
        self.htype.needs_sound_tech = True
        self.htype.save()
        e = self.accepted()
        url = reverse("hires:details", kwargs={"token": e.details_token})
        self.client.post(url, self.details_post(e))
        e.refresh_from_db()
        self.assertIsNone(e.details_completed_at)

    def test_own_tech_needs_a_name(self):
        e = self.accepted()
        url = reverse("hires:details", kwargs={"token": e.details_token})
        self.client.post(url, self.details_post(e, sound_tech="own"))
        e.refresh_from_db()
        self.assertIsNone(e.details_completed_at)

    def test_confirmation_blocked_until_details_arrive(self):
        e = self.accepted()
        e.event.terms = "Terms."
        e.event.save()
        with self.assertRaises(ValueError):
            services.send_confirmation(e)
        services.mark_details_received(e, "sent by email")
        services.send_confirmation(e)
        e.refresh_from_db()
        self.assertEqual(e.status, E.AWAITING_AGREEMENT)

    def test_marking_details_received_needs_a_note(self):
        e = self.accepted()
        with self.assertRaises(ValueError):
            services.mark_details_received(e, "")

    def test_details_link_dead_for_unknown_token_and_purged(self):
        self.assertEqual(
            self.client.get(
                reverse("hires:details", kwargs={"token": "nope"})
            ).status_code,
            404,
        )

    def test_details_page_404_when_flag_off(self):
        e = self.accepted()
        set_flag(False)
        self.assertEqual(
            self.client.get(
                reverse("hires:details", kwargs={"token": e.details_token})
            ).status_code,
            404,
        )

    def test_agreement_refused_without_every_tickbox(self):
        e = self.accepted()
        e.event.terms = "Terms."
        e.event.save()
        self.send_conf(e)
        url = reverse("hires:agree", kwargs={"token": e.agreement_token})
        statements = self.cfg.acknowledgement_list()
        self.client.post(url, {"ack": statements[:1]})
        e.refresh_from_db()
        self.assertEqual(e.status, E.AWAITING_AGREEMENT)
        r = self.client.get(url)
        self.assertContains(r, "Before you agree")


class ReviewTwoFixTests(HireBase):
    """Regressions from the second external (DeepSeek) review."""

    def booked(self):
        e = self.make_enquiry()
        event = services.accept(e, self.programmer)
        event.terms = "Terms."
        event.save()
        self.send_conf(e)
        services.record_agreement(e, acknowledged=["x"])
        e.refresh_from_db()
        return e

    def test_a_booked_hire_cannot_be_reopened_by_resending(self):
        e = self.booked()
        with self.assertRaises(ValueError):
            services.send_confirmation(e)
        e.refresh_from_db()
        self.assertEqual(e.status, E.BOOKED)
        self.assertIsNotNone(e.terms_agreed_at)

    def test_agreement_requires_awaiting_status(self):
        e = self.make_enquiry()
        with self.assertRaises(ValueError):
            services.record_agreement(e)

    def test_cannot_accept_twice(self):
        e = self.make_enquiry()
        services.accept(e, self.programmer)
        e.status = E.TO_DISCUSS
        e.save()
        with self.assertRaises(ValueError):
            services.accept(e, self.programmer)

    def test_moving_meeting_does_not_revert_an_accepted_enquiry(self):
        e = self.make_enquiry()
        services.accept(e, self.programmer)
        self.client.force_login(self.programmer)
        self.client.post(
            reverse("hires:act", kwargs={"pk": e.pk}),
            {"action": "assign_meeting", "meeting": self.meeting.pk},
        )
        e.refresh_from_db()
        self.assertEqual(e.status, E.ACCEPTED)

    def test_details_locked_once_terms_are_out(self):
        e = self.make_enquiry()
        event = services.accept(e, self.programmer)
        event.terms = "Terms."
        event.save()
        self.send_conf(e)
        url = reverse("hires:details", kwargs={"token": e.details_token})
        d = e.hire_dates.get()
        r = self.client.post(
            url,
            {
                "expected_attendance": "999",
                "sound_tech": "none",
                f"start_{d.pk}": "18:00",
                f"end_{d.pk}": "20:00",
            },
        )
        self.assertContains(r, "can no longer be changed")
        e.refresh_from_db()
        self.assertNotEqual(e.expected_attendance, 999)

    def test_retention_clock_counts_from_agreement(self):
        e = self.booked()
        e.status_changed_at = timezone.now() - datetime.timedelta(days=4000)
        e.save()
        ref = e.retention_reference_date()
        self.assertGreaterEqual(ref, timezone.localdate())

    def test_same_open_and_out_time_is_rejected(self):
        self.client.post(
            reverse("hires:enquire"),
            self.post_data(get_in_1="18:00", get_out_1="18:00"),
        )
        self.assertFalse(E.objects.exists())

    def test_partly_accepted_dates_drive_late_night_and_door_staff(self):
        from toolkit.hires.models import HireDate

        self.htype.provides_door_staff = True
        self.htype.save()
        e = self.make_enquiry()
        early = e.hire_dates.get()
        late_start = early.get_in + datetime.timedelta(days=1)
        late = HireDate.objects.create(
            enquiry=e,
            get_in=late_start.replace(hour=18),
            start=late_start.replace(hour=19),
            end=late_start.replace(hour=23),
            get_out=late_start.replace(hour=23, minute=59),
        )
        self.assertTrue(e.door_staff_required())  # nothing accepted yet
        early.accepted = True
        early.save()
        e.refresh_from_db()
        self.assertFalse(e.door_staff_required())  # only the early one
        late.accepted = True
        late.save()
        early.accepted = False
        early.save()
        e.refresh_from_db()
        self.assertTrue(e.door_staff_required())


class BranchReviewFixTests(HireBase):
    """Regressions from the 2026-10 branch review."""

    def _old_enquiry(self):
        e = self.make_enquiry()
        e.submitted_at = timezone.now() - datetime.timedelta(days=40)
        e.save()
        return e

    def test_cancelled_meeting_without_replacement_is_not_instant_decline(
        self,
    ):
        e = self._old_enquiry()
        services.meeting_cancelled(self.meeting)
        e.refresh_from_db()
        self.assertGreater(e.reply_deadline, timezone.localdate())
        self.assertTrue(
            any("meeting has moved" in m.subject for m in mail.outbox)
        )
        services.run_clock()
        e.refresh_from_db()
        self.assertEqual(e.status, E.TO_DISCUSS)

    def test_capacity_email_without_meeting_has_no_tbc(self):
        e = self.make_enquiry()
        e.meeting = None
        e.save()
        mail.outbox.clear()
        services.send_to_hirer(
            e,
            "declined_capacity",
            services.HIRER_EMAIL_SOURCES["declined_capacity"],
        )
        body = mail.outbox[-1].body
        self.assertNotIn("TBC", body)
        self.assertIn("Nobody was able to take it on.", body)

    def test_stranded_enquiry_rehomed_later_tells_hirer(self):
        e = self.make_enquiry()
        e.meeting = None
        e.reply_deadline = timezone.localdate() + datetime.timedelta(days=5)
        e.save()
        ProgrammingMeeting.objects.all().delete()
        ProgrammingMeeting.objects.create(
            date=timezone.localdate() + datetime.timedelta(days=60)
        )
        mail.outbox.clear()
        services.run_clock()
        self.assertTrue(
            any("meeting has moved" in m.subject for m in mail.outbox)
        )

    def test_decisions_refused_once_enquiry_has_moved_on(self):
        for status in (E.BOOKED, E.DECLINED, E.ACCEPTED):
            e = self.make_enquiry()
            e.status = status
            e.save()
            mail.outbox.clear()
            with self.assertRaises(ValueError):
                services.decline(e, self.programmer)
            with self.assertRaises(ValueError):
                services.mark_maybe(e, self.programmer, "x")
            self.assertEqual(len(mail.outbox), 0)
            e.refresh_from_db()
            self.assertEqual(e.status, status)
        done = self.make_enquiry()
        done.status = E.DECLINED
        done.save()
        with self.assertRaises(ValueError):
            services.withdraw(done)
        with self.assertRaises(ValueError):
            services.replied_outside_toolkit(done, "x")

    def test_invalid_submissions_do_not_use_up_the_rate_limit(self):
        for _ in range(4):
            self.client.post(
                reverse("hires:enquire"), self.post_data(get_out_1="17:30")
            )
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertEqual(E.objects.count(), 1)

    def test_form_closed_without_notification_address(self):
        self.cfg.notification_addresses = ""
        self.cfg.save()
        r = self.client.get(reverse("hires:enquire"))
        self.assertNotContains(r, "Send enquiry")
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:queue"))
        self.assertContains(r, "No valid notification address")

    def test_form_closed_without_hire_types(self):
        HireType.objects.all().delete()
        r = self.client.get(reverse("hires:enquire"))
        self.assertNotContains(r, "Send enquiry")

    def test_accept_creates_keyholder_slot_and_complete_details_adds_offer(
        self,
    ):
        from toolkit.diary.models import Role, RotaEntry

        role = Role.objects.create(name="Keyholder", keyholder_only=True)
        e = self.make_enquiry()
        event = services.accept(e, self.programmer)
        showing = event.showings.get()
        self.assertEqual(
            RotaEntry.objects.filter(showing=showing, role=role).count(), 1
        )
        self.assertEqual(services.unfilled_keyholder_slots(e), 1)
        e.offers_to_volunteers = "Free pizza"
        e.save()
        services.ensure_rota_for_hire(e)
        services.ensure_rota_for_hire(e)  # idempotent
        showing.refresh_from_db()
        self.assertIn(
            "Hirer offers volunteers: Free pizza", showing.rota_notes
        )
        self.assertEqual(showing.rota_notes.count("Hirer offers"), 1)
        self.assertEqual(
            RotaEntry.objects.filter(showing=showing, role=role).count(), 1
        )
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:detail", args=[e.pk]))
        self.assertContains(r, "No keyholder yet")

    def test_old_wagtail_hire_form_redirects_when_flag_on(self):
        from django.test import RequestFactory

        from toolkit.content.models import EmailFormPage

        req = RequestFactory().get("/hire-and-enquire/enquire/")
        hire = EmailFormPage(url_path="/home/hire-and-enquire/enquire/")
        r = hire.serve(req)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("hires:enquire"))


class IndicativeFeeTests(HireBase):
    def test_price_list_and_info_link_on_form(self):
        r = self.client.get(reverse("hires:enquire"))
        self.assertContains(r, "Our price list")
        self.assertContains(r, "£100 per hire")
        self.assertContains(r, "/hire-and-enquire/about-hiring/")
        self.cfg.info_page_url = ""
        self.cfg.save()
        r = self.client.get(reverse("hires:enquire"))
        self.assertNotContains(r, "Read about hiring first")

    def test_quote_endpoint_matches_real_charge(self):
        day = (timezone.localdate() + datetime.timedelta(days=30)).isoformat()
        r = self.client.get(
            reverse("hires:quote"),
            {
                "hire_type": self.htype.pk,
                "tier": "corporate",
                "date": day,
                "get_in": "17:00",
                "get_out": "22:00",
            },
        )
        self.assertIn("About £200", r.json()["text"])
        self.assertIn("full rate", r.json()["text"])
        self.assertNotIn("security", r.json()["text"])

    def test_quote_is_blank_for_bad_input(self):
        r = self.client.get(reverse("hires:quote"), {"date": "nope"})
        self.assertEqual(r.json()["text"], "")

    def test_zero_fee_says_we_will_confirm(self):
        self.htype.community_fee_gbp = Decimal("0")
        self.htype.save()
        e = self.make_enquiry()
        text = services.indicative_fee_text(
            self.htype, "community", e.dates()[:1]
        )
        self.assertIn("confirm the fee", text)

    def test_acknowledgement_carries_fee_and_info_link(self):
        self.client.post(reverse("hires:enquire"), self.post_data())
        body = mail.outbox[0].body
        self.assertIn("The fee: About £100", body)
        self.assertIn("/hire-and-enquire/about-hiring/", body)


class WhatsOnTests(HireBase):
    def _showing(self, event_name, day_offset, hour, hours=2, **ev):
        from toolkit.diary.models import Event, Showing

        event = Event.objects.create(name=event_name, **ev)
        start = timezone.make_aware(
            datetime.datetime.combine(
                timezone.localdate() + datetime.timedelta(days=day_offset),
                datetime.time(hour, 0),
            )
        )
        return Showing.objects.create(
            event=event, start=start, booked_by="t", confirmed=True
        )

    def test_overlap_without_rooms_is_a_check_and_window_is_seven_days(self):
        e = self.make_enquiry()  # 17:00-22:00 building, 30 days out
        self._showing("Overlapping gig", 30, 19)
        self._showing("Earlier film", 30, 10, programming_status="active")
        self._showing("Next week", 33, 19)
        self._showing("Far away", 45, 19)
        info = services.whats_on([e])[e.pk][0]
        self.assertEqual(info["same_day"], 2)
        self.assertEqual(info["clashes"], 0)  # no rooms known: not certain
        self.assertEqual(info["checks"], 1)
        titles = [it["title"] for day in info["days"] for it in day["items"]]
        self.assertIn("Next week", titles)
        self.assertNotIn("Far away", titles)

    def test_own_event_and_cancelled_are_excluded(self):
        e = self.make_enquiry()
        event = services.accept(e, self.programmer)
        sh = self._showing("Cancelled thing", 30, 19)
        sh.cancelled = True
        sh.save()
        info = services.whats_on([e])[e.pk][0]
        self.assertEqual(info["week"], 0)
        self.assertEqual(event.showings.count(), 1)

    def test_other_undecided_hires_appear(self):
        a = self.make_enquiry()
        b = self.make_enquiry()
        b.title = "Rival hire"
        b.save()
        info = services.whats_on([a])[a.pk][0]
        self.assertEqual(info["checks"], 1)
        self.assertTrue(
            any(
                it["kind"] == "enquiry"
                for day in info["days"]
                for it in day["items"]
            )
        )

    def test_queue_and_detail_show_the_panel(self):
        e = self.make_enquiry()
        self._showing("Overlapping gig", 30, 19)
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:queue"))
        self.assertContains(r, "1 to check")
        r = self.client.get(reverse("hires:detail", args=[e.pk]))
        self.assertContains(r, "Overlapping gig")
        self.assertContains(r, "What else is on")


class ClashTierTests(WhatsOnTests):
    """Red only when certain; amber for what a person should look at."""

    def at(self, days, hour, minute=0):
        return timezone.make_aware(
            datetime.datetime.combine(
                timezone.localdate() + datetime.timedelta(days=days),
                datetime.time(hour, minute),
            )
        )

    def booked(self, name, room, start, end):
        from toolkit.diary.models import Event, RoomBooking, Showing

        sh = Showing.objects.create(
            event=Event.objects.create(name=name),
            start=start,
            booked_by="t",
            confirmed=True,
        )
        RoomBooking.objects.create(showing=sh, room=room, start=start, end=end)
        return sh

    def hire_at(self, start, end, room=None):
        e = self.make_enquiry()
        hd = e.hire_dates.get()
        hd.get_in = hd.start = start
        hd.end = hd.get_out = end
        hd.save()
        if room:
            e.rooms_requested.add(room)
        return e

    def rows(self, e):
        info = services.whats_on([e])[e.pk][0]
        return info, {
            it["title"]: (it["tier"], it["reason"])
            for day in info["days"]
            for it in day["items"]
        }

    def test_same_time_same_space_is_a_clash(self):
        e = self.hire_at(self.at(30, 17), self.at(30, 22), self.room)
        self.booked("Gig", self.room, self.at(30, 19), self.at(30, 21))
        info, rows = self.rows(e)
        self.assertEqual(rows["Gig"], ("clash", "Same time, same space"))
        self.assertEqual(info["clashes"], 1)

    def test_same_time_different_space_is_a_check(self):
        cafe = Room.objects.create(name="Cafe")
        e = self.hire_at(self.at(30, 17), self.at(30, 22), self.room)
        self.booked("Talk", cafe, self.at(30, 19), self.at(30, 21))
        _, rows = self.rows(e)
        self.assertEqual(rows["Talk"], ("check", "Same time, different space"))

    def test_time_in_between_is_clear(self):
        e = self.hire_at(self.at(30, 17), self.at(30, 22), self.room)
        self.booked("Matinee", self.room, self.at(30, 11), self.at(30, 14))
        info, rows = self.rows(e)
        self.assertEqual(rows["Matinee"], ("", ""))
        self.assertEqual((info["clashes"], info["checks"]), (0, 0))
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:detail", args=[e.pk]))
        self.assertNotContains(r, "Clash:")
        self.assertContains(r, "Clear schedule")

    def test_tight_changeover_in_the_same_space(self):
        e = self.hire_at(self.at(30, 17), self.at(30, 22), self.room)
        self.booked("Film", self.room, self.at(30, 14), self.at(30, 16, 30))
        _, rows = self.rows(e)
        self.assertEqual(rows["Film"], ("check", "Tight changeover (30 min)"))

    def test_tight_changeover_elsewhere_is_fine(self):
        cafe = Room.objects.create(name="Cafe")
        e = self.hire_at(self.at(30, 17), self.at(30, 22), self.room)
        self.booked("Brunch", cafe, self.at(30, 14), self.at(30, 16, 30))
        _, rows = self.rows(e)
        self.assertEqual(rows["Brunch"], ("", ""))

    def test_late_night_before_flags_a_morning_hire(self):
        e = self.hire_at(self.at(30, 9), self.at(30, 13), self.room)
        self.booked("Club night", self.room, self.at(29, 22), self.at(30, 3))
        _, rows = self.rows(e)
        self.assertEqual(rows["Club night"][0], "check")
        self.assertIn("clearing up", rows["Club night"][1])

    def test_late_hire_flags_the_next_morning(self):
        e = self.hire_at(self.at(30, 20), self.at(31, 1), self.room)
        self.booked(
            "Coffee morning", self.room, self.at(31, 10), self.at(31, 12)
        )
        _, rows = self.rows(e)
        self.assertEqual(rows["Coffee morning"][0], "check")
        self.assertIn("clean-up", rows["Coffee morning"][1])


class HireMenuSeedTests(HireBase):
    def test_seeded_menu_shows_info_page_and_enquiry_link(self):
        from django.core.management import call_command

        call_command("seed_hire_dev_data", verbosity=0)
        call_command("seed_hire_dev_data", verbosity=0)  # idempotent
        html = self.client.get("/").content.decode()
        self.assertIn("Hire &amp; Enquire", html)
        self.assertIn("About hiring", html)
        self.assertLess(
            html.index("About hiring"), html.index('href="/hires/enquire/"')
        )
        self.assertIn('href="/hires/enquire/"', html)
        self.assertEqual(html.count("Hire &amp; Enquire"), 1)

    def test_seeded_meetings_are_second_and_fourth_mondays(self):
        from django.core.management import call_command

        stray = ProgrammingMeeting.objects.create(
            date=timezone.localdate() + datetime.timedelta(days=9)
        )
        e = self.make_enquiry(meeting=stray)
        call_command("seed_hire_dev_data", verbosity=0)
        meetings = ProgrammingMeeting.objects.filter(
            date__gt=timezone.localdate()
        )
        self.assertTrue(meetings.exists())
        for m in meetings:
            self.assertEqual(m.date.weekday(), 0, m)
            self.assertIn((m.date.day - 1) // 7 + 1, (2, 4), m)
        e.refresh_from_db()
        self.assertIn(e.meeting, meetings)


class CommunityRateTests(HireBase):
    def test_rate_must_be_chosen_and_community_needs_a_case(self):
        r = self.client.post(
            reverse("hires:enquire"), self.post_data(tier_requested="")
        )
        self.assertEqual(E.objects.count(), 0)
        r = self.client.post(
            reverse("hires:enquire"), self.post_data(community_case="  ")
        )
        self.assertEqual(E.objects.count(), 0)
        self.assertContains(r, "why the community rate fits")

    def test_full_rate_needs_no_case_and_stores_none(self):
        self.client.post(
            reverse("hires:enquire"),
            self.post_data(
                tier_requested="corporate",
                community_case="ignored",
                community_evidence="ignored",
            ),
        )
        e = E.objects.get()
        self.assertEqual(e.community_case, "")
        self.assertEqual(e.community_evidence, "")

    def test_case_is_stored_and_shown_to_the_meeting_with_the_subsidy(self):
        self.client.post(
            reverse("hires:enquire"),
            self.post_data(community_evidence="charity 123"),
        )
        e = E.objects.get()
        self.assertEqual(e.community_case, "A local unfunded film club.")
        self.assertEqual(e.subsidy_gbp(), Decimal("100"))  # 200 full - 100
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:queue"))
        self.assertContains(r, "Asks for community rate")
        self.assertContains(r, "A local unfunded film club.")
        r = self.client.get(reverse("hires:detail", args=[e.pk]))
        self.assertContains(r, "subsidy of about")
        self.assertContains(r, "charity 123")

    def test_form_explains_rate_and_quote_gives_the_full_rate_too(self):
        r = self.client.get(reverse("hires:enquire"))
        self.assertContains(r, "in effect, a subsidy")
        e = self.make_enquiry()
        text = services.indicative_fee_text(
            self.htype, "community", e.dates()[:1]
        )
        self.assertIn("if the volunteers agree it", text)
        self.assertIn("full rate it would be about £200", text)

    def test_acknowledgement_and_digest_mention_the_request(self):
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertIn("asked for the community rate", mail.outbox[0].body)
        e = E.objects.get()
        self.assertIn(
            "community rate: subsidy about £100", services._digest_lines([e])
        )

    def test_declined_community_rate_is_stated_in_the_terms(self):
        e = self.make_enquiry(tier_requested="community")
        services.accept(e, self.programmer, tier_agreed="corporate")
        self.assertIn(
            "We weren't able to offer the community rate",
            services.fee_text(e),
        )
        self.assertEqual(e.agreed_fee_gbp, Decimal("200"))

    def test_case_is_purged_with_the_rest(self):
        from toolkit.hires.purge import anonymise_enquiry

        e = self.make_enquiry(
            community_case="private story", community_evidence="x"
        )
        anonymise_enquiry(e)
        e.refresh_from_db()
        self.assertEqual(e.community_case, "")
        self.assertEqual(e.community_evidence, "")


class MeetingSlotTests(HireBase):
    def later_meeting(self, days=24, **kw):
        return ProgrammingMeeting.objects.create(
            date=timezone.localdate() + datetime.timedelta(days=days), **kw
        )

    def test_full_meeting_is_skipped(self):
        self.meeting.hire_slots = 1
        self.meeting.save()
        later = self.later_meeting()
        self.make_enquiry()
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertEqual(E.objects.latest("pk").meeting, later)

    def test_championed_enquiry_does_not_use_a_slot(self):
        self.meeting.hire_slots = 1
        self.meeting.save()
        e = self.make_enquiry()
        services.champion(e, self.programmer)
        self.assertTrue(services.has_space(self.meeting))

    def test_open_meeting_takes_no_hires_by_default(self):
        self.meeting.kind = "open_monday"
        self.meeting.save()
        dev = self.later_meeting(kind="development")
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertEqual(E.objects.get().meeting, dev)

    def test_form_closes_when_full_within_horizon(self):
        self.cfg.full_horizon_weeks = 2
        self.cfg.save()
        self.meeting.hire_slots = 0
        self.meeting.save()
        self.later_meeting(days=60)
        r = self.client.get(reverse("hires:enquire"))
        self.assertContains(r, "full for now")
        self.client.post(reverse("hires:enquire"), self.post_data())
        self.assertFalse(E.objects.exists())

    def test_form_stays_open_with_no_meetings_or_no_horizon(self):
        self.meeting.hire_slots = 0
        self.meeting.save()
        self.cfg.full_horizon_weeks = None
        self.cfg.save()
        self.assertNotContains(
            self.client.get(reverse("hires:enquire")), "full for now"
        )
        self.cfg.full_horizon_weeks = 8
        self.cfg.save()
        ProgrammingMeeting.objects.all().delete()
        self.assertNotContains(
            self.client.get(reverse("hires:enquire")), "full for now"
        )

    def test_meetings_page_shows_agenda_and_saves_slots(self):
        self.make_enquiry()
        self.client.force_login(self.programmer)
        r = self.client.get(reverse("hires:meetings"))
        self.assertContains(r, "1 of 10 hire slots")
        self.client.post(
            reverse("hires:meetings"),
            {"slots_for": self.meeting.pk, "hire_slots": "4"},
        )
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.slots(), 4)

    def test_moving_into_a_full_meeting_warns(self):
        later = self.later_meeting(hire_slots=0)
        e = self.make_enquiry()
        self.client.force_login(self.programmer)
        r = self.client.post(
            reverse("hires:act", kwargs={"pk": e.pk}),
            {"action": "assign_meeting", "meeting": later.pk},
            follow=True,
        )
        self.assertContains(r, "over its 0 hire slots")
        e.refresh_from_db()
        self.assertEqual(e.meeting, later)

    def test_hire_before_its_answer_is_flagged(self):
        # Hire is in 30 days; a meeting in 28 promises an answer in 35.
        late = self.later_meeting(days=28)
        e = self.make_enquiry()
        self.assertFalse(e.answer_after_hire())
        services.assign_meeting(e, late)
        e.save()
        self.assertTrue(e.answer_after_hire())
        self.client.force_login(self.programmer)
        self.assertContains(
            self.client.get(reverse("hires:queue")), "Hire before its answer"
        )
        self.assertContains(
            self.client.get(reverse("hires:meetings")),
            "answer due after the hire date",
        )


class ChampionTests(HireBase):
    def test_championed_enquiry_is_never_auto_declined(self):
        e = self.make_enquiry()
        services.champion(e, self.programmer)
        e.reply_deadline = timezone.localdate()
        e.save()
        mail.outbox.clear()
        out = services.run_clock()
        e.refresh_from_db()
        self.assertEqual(e.status, E.TO_DISCUSS)
        self.assertEqual(out["champion_nudges"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("ada@example.org", mail.outbox[0].to)
        self.assertIn(self.programmer.email, mail.outbox[0].to)
        services.run_clock()
        self.assertEqual(len(mail.outbox), 1)  # once only

    def test_champion_and_release_through_the_page(self):
        e = self.make_enquiry()
        self.client.force_login(self.programmer)
        url = reverse("hires:act", kwargs={"pk": e.pk})
        self.client.post(url, {"action": "champion"})
        e.refresh_from_db()
        self.assertTrue(e.championed)
        r = self.client.get(reverse("hires:queue"))
        self.assertContains(r, "Taken on by")
        self.client.post(url, {"action": "release"})
        e.refresh_from_db()
        self.assertFalse(e.championed)
        self.assertEqual(e.meeting, self.meeting)

    def test_someone_else_cannot_take_over_a_champion(self):
        from django.contrib.auth.models import User

        e = self.make_enquiry()
        services.champion(e, self.programmer)
        other = User.objects.create_user("other", password="x")
        with self.assertRaises(ValueError):
            services.champion(e, other)


class DecisionDraftTests(HireBase):
    def setUp(self):
        super().setUp()
        self.e = self.make_enquiry()
        self.client.force_login(self.programmer)
        self.url = reverse("hires:act", kwargs={"pk": self.e.pk})

    def test_detail_page_shows_editable_drafts(self):
        r = self.client.get(reverse("hires:detail", args=[self.e.pk]))
        self.assertContains(r, 'name="email_body"', count=3)
        self.assertContains(r, "Hi Ada")
        self.e.refresh_from_db()
        self.assertContains(r, self.e.details_token)

    def test_edited_decline_is_sent_as_written(self):
        mail.outbox.clear()
        self.client.post(
            self.url,
            {
                "action": "decline",
                "email_mode": "send",
                "email_subject": "About your night",
                "email_body": "Hi Ada,\r\n\r\nSorry, not this time.",
            },
        )
        self.assertEqual(mail.outbox[-1].subject, "About your night")
        self.assertIn("Sorry, not this time.", mail.outbox[-1].body)
        self.assertIn("privacy", mail.outbox[-1].body)

    def test_ill_be_in_touch_myself_sends_nothing(self):
        mail.outbox.clear()
        self.client.post(
            self.url,
            {"action": "decline", "email_mode": "self", "email_body": "x"},
        )
        self.e.refresh_from_db()
        self.assertEqual(self.e.status, E.DECLINED)
        self.assertEqual(mail.outbox, [])
        self.assertIn("Not emailed by the system", self.e.internal_notes)
