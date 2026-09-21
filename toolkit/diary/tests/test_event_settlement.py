# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Tests for task 9.171: event settlement records."""

import csv
import io
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import (
    Event,
    PerformerRegistration,
    PRSPerformerEntry,
    SettlementLineItem,
    SettlementRevision,
    Showing,
    ShowingSettlement,
    get_site_config,
)
from toolkit.diary.tests.common import DiaryTestsMixin
from toolkit.members.models import Volunteer
from toolkit.test_common import _create_toolkit_permissions


class ShowingSettlementModelTests(TestCase):
    def setUp(self):
        self.event = Event(name="Gig", cost_type=Event.COST_TYPE_PERFORMER_FEE)
        self.event.save()
        self.showing = Showing(
            event=self.event, start="2013-06-01T19:00:00+00:00"
        )
        self.showing.save(force=True)

    def test_no_settlement_row_is_not_recorded(self):
        self.assertEqual(self.showing.settlement_status(), "not_recorded")

    def test_settlement_with_no_data_is_not_recorded(self):
        ShowingSettlement.objects.create(showing=self.showing)
        self.assertEqual(self.showing.settlement_status(), "not_recorded")

    def test_settlement_with_only_attendance_is_partial(self):
        ShowingSettlement.objects.create(showing=self.showing, attendance=40)
        self.assertEqual(self.showing.settlement_status(), "partial")

    def test_settlement_with_attendance_and_line_item_is_recorded(self):
        settlement = ShowingSettlement.objects.create(
            showing=self.showing, attendance=40
        )
        SettlementLineItem.objects.create(
            settlement=settlement,
            description="40 door",
            count=40,
            unit_price_gbp=Decimal("5.00"),
        )
        self.assertEqual(self.showing.settlement_status(), "recorded")

    def test_nothing_to_report_status(self):
        ShowingSettlement.objects.create(
            showing=self.showing, nothing_to_report=True
        )
        self.assertEqual(self.showing.settlement_status(), "nothing_to_report")

    def test_nothing_to_report_with_attendance_still_nothing_to_report(self):
        """Attendance stays independent of the flag (Jonny: "yes, keep
        attendance separate") -- a free showing can have a headcount and
        still have nothing financial to report."""
        ShowingSettlement.objects.create(
            showing=self.showing, attendance=15, nothing_to_report=True
        )
        self.assertEqual(self.showing.settlement_status(), "nothing_to_report")

    def test_no_financial_activity_is_not_applicable(self):
        no_money_event = Event(
            name="Cleaning club", no_financial_activity=True
        )
        no_money_event.save()
        showing = Showing(
            event=no_money_event, start="2013-06-01T19:00:00+00:00"
        )
        showing.save(force=True)
        self.assertEqual(showing.settlement_status(), "not_applicable")

    def test_ticket_income_total(self):
        settlement = ShowingSettlement.objects.create(showing=self.showing)
        SettlementLineItem.objects.create(
            settlement=settlement,
            description="advance",
            count=10,
            unit_price_gbp=Decimal("5.00"),
        )
        SettlementLineItem.objects.create(
            settlement=settlement,
            description="door, no price entered",
            count=3,
        )
        self.assertEqual(settlement.ticket_income_total(), Decimal("50.00"))


class EventSettlementStatusTests(TestCase):
    def setUp(self):
        self.event = Event(
            name="Series", cost_type=Event.COST_TYPE_PERFORMER_FEE
        )
        self.event.save()
        self.past1 = Showing(
            event=self.event, start="2013-06-01T19:00:00+00:00"
        )
        self.past1.save(force=True)
        self.past2 = Showing(
            event=self.event, start="2013-06-02T19:00:00+00:00"
        )
        self.past2.save(force=True)

    def test_no_elapsed_showings_returns_none(self):
        event = Event(
            name="All future", cost_type=Event.COST_TYPE_PERFORMER_FEE
        )
        event.save()
        self.assertIsNone(event.settlement_status())

    def test_not_applicable_without_financial_terms(self):
        event = Event(name="No deal recorded")
        event.save()
        Showing(event=event, start="2013-06-01T19:00:00+00:00").save(
            force=True
        )
        self.assertEqual(event.settlement_status(), "not_applicable")

    def test_none_recorded(self):
        self.assertEqual(self.event.settlement_status(), "not_recorded")

    def test_partial_when_only_one_showing_settled(self):
        settlement = ShowingSettlement.objects.create(
            showing=self.past1, attendance=10
        )
        SettlementLineItem.objects.create(
            settlement=settlement, description="x", count=10
        )
        self.assertEqual(self.event.settlement_status(), "partial")

    def test_recorded_when_every_elapsed_showing_settled(self):
        for showing in (self.past1, self.past2):
            settlement = ShowingSettlement.objects.create(
                showing=showing, attendance=10
            )
            SettlementLineItem.objects.create(
                settlement=settlement, description="x", count=10
            )
        self.assertEqual(self.event.settlement_status(), "recorded")

    def test_cancelled_showings_excluded(self):
        self.past2.cancelled = True
        self.past2.save(force=True)
        settlement = ShowingSettlement.objects.create(
            showing=self.past1, attendance=10
        )
        SettlementLineItem.objects.create(
            settlement=settlement, description="x", count=10
        )
        self.assertEqual(self.event.settlement_status(), "recorded")

    def test_nothing_to_report_counts_as_recorded_in_rollup(self):
        """Per Jonny: a showing marked "nothing to report" counts as done
        for the event-level rollup, same as "recorded" -- the point of the
        bulk action is to stop the event nagging once cleared."""
        settlement = ShowingSettlement.objects.create(
            showing=self.past1, attendance=10
        )
        SettlementLineItem.objects.create(
            settlement=settlement, description="x", count=10
        )
        ShowingSettlement.objects.create(
            showing=self.past2, nothing_to_report=True
        )
        self.assertEqual(self.event.settlement_status(), "recorded")

    def test_all_nothing_to_report_counts_as_recorded(self):
        for showing in (self.past1, self.past2):
            ShowingSettlement.objects.create(
                showing=showing, nothing_to_report=True
            )
        self.assertEqual(self.event.settlement_status(), "recorded")


class DistributorPaymentStatusTests(TestCase):
    def test_none_without_cost_type(self):
        event = Event(name="No deal")
        event.save()
        self.assertIsNone(event.distributor_payment_status())

    def test_outstanding_with_cost_type_and_no_dates(self):
        event = Event(name="Deal", cost_type=Event.COST_TYPE_FILM_LICENSE)
        event.save()
        self.assertEqual(event.distributor_payment_status(), "outstanding")

    def test_invoiced(self):
        event = Event(
            name="Deal",
            cost_type=Event.COST_TYPE_FILM_LICENSE,
            distributor_invoiced_date="2026-01-01",
        )
        event.save()
        self.assertEqual(event.distributor_payment_status(), "invoiced")

    def test_paid(self):
        event = Event(
            name="Deal",
            cost_type=Event.COST_TYPE_FILM_LICENSE,
            distributor_invoiced_date="2026-01-01",
            distributor_paid_date="2026-01-15",
        )
        event.save()
        self.assertEqual(event.distributor_payment_status(), "paid")

    def test_none_when_no_financial_activity(self):
        """A cost type can be set (e.g. left over from before the event was
        flagged) but no_financial_activity must still suppress this, same
        as settlement_status() -- found live 2026-09-14, the flag was only
        wired into has_financial_terms()/settlement_status(), not here."""
        event = Event(
            name="Actually free",
            cost_type=Event.COST_TYPE_INTERNAL,
            no_financial_activity=True,
        )
        event.save()
        self.assertIsNone(event.distributor_payment_status())


class EventPrsRelevantTests(TestCase):
    def test_performer_fee_is_relevant(self):
        event = Event(name="Gig", cost_type=Event.COST_TYPE_PERFORMER_FEE)
        self.assertTrue(event.prs_relevant())

    def test_venue_hire_is_relevant(self):
        event = Event(name="Hire", cost_type=Event.COST_TYPE_VENUE_HIRE)
        self.assertTrue(event.prs_relevant())

    def test_film_license_not_relevant(self):
        event = Event(name="Film", cost_type=Event.COST_TYPE_FILM_LICENSE)
        self.assertFalse(event.prs_relevant())

    def test_no_cost_type_not_relevant(self):
        event = Event(name="TBC")
        self.assertFalse(event.prs_relevant())


class PerformerRegistrationModelTests(TestCase):
    def setUp(self):
        self.event = Event(name="Gig", cost_type=Event.COST_TYPE_PERFORMER_FEE)
        self.event.save()

    def test_no_data_is_false(self):
        registration = PerformerRegistration.objects.create(event=self.event)
        self.assertFalse(registration.has_any_data())

    def test_filled_in_by_counts_as_data(self):
        registration = PerformerRegistration.objects.create(
            event=self.event, filled_in_by="Alex"
        )
        self.assertTrue(registration.has_any_data())

    def test_vat_flag_counts_as_data(self):
        registration = PerformerRegistration.objects.create(
            event=self.event, vat_on_tickets=False
        )
        self.assertTrue(registration.has_any_data())

    def test_performer_entry_counts_as_data(self):
        registration = PerformerRegistration.objects.create(event=self.event)
        PRSPerformerEntry.objects.create(
            registration=registration, name="The Band"
        )
        self.assertTrue(registration.has_any_data())


class SettlementViewsFeatureFlagTests(DiaryTestsMixin, TestCase):
    """The whole feature 404s when SiteConfiguration.event_settlement_enabled
    is off -- ships dormant, per the rest of this codebase's speculative
    features."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_settlement_edit_404s_when_disabled(self):
        cfg = get_site_config()
        cfg.event_settlement_enabled = False
        cfg.save()
        resp = self.client.get(
            reverse(
                "edit-showing-settlement", kwargs={"showing_id": self.e4s3.pk}
            )
        )
        self.assertEqual(resp.status_code, 404)

    def test_distributor_payment_edit_404s_when_disabled(self):
        cfg = get_site_config()
        cfg.event_settlement_enabled = False
        cfg.save()
        resp = self.client.get(
            reverse(
                "edit-distributor-payment", kwargs={"event_id": self.e4.pk}
            )
        )
        self.assertEqual(resp.status_code, 404)

    def test_programmer_past_events_404s_when_disabled(self):
        cfg = get_site_config()
        cfg.event_settlement_enabled = False
        cfg.save()
        resp = self.client.get(reverse("programmer-past-events"))
        self.assertEqual(resp.status_code, 404)

    def test_prs_registration_edit_404s_when_disabled(self):
        cfg = get_site_config()
        cfg.event_settlement_enabled = False
        cfg.save()
        resp = self.client.get(
            reverse("edit-prs-registration", kwargs={"event_id": self.e4.pk})
        )
        self.assertEqual(resp.status_code, 404)

    def test_prs_report_404s_when_disabled(self):
        cfg = get_site_config()
        cfg.event_settlement_enabled = False
        cfg.save()
        resp = self.client.get(reverse("prs-report"))
        self.assertEqual(resp.status_code, 404)


class ShowingSettlementEditViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.e4.save()
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_renders_form(self):
        resp = self.client.get(
            reverse(
                "edit-showing-settlement", kwargs={"showing_id": self.e4s3.pk}
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_post_creates_settlement_and_line_items(self):
        url = reverse(
            "edit-showing-settlement", kwargs={"showing_id": self.e4s3.pk}
        )
        resp = self.client.post(
            url,
            {
                "attendance": "40",
                "bar_contribution_gbp": "",
                "notes": "",
                "line_items-TOTAL_FORMS": "1",
                "line_items-INITIAL_FORMS": "0",
                "line_items-MIN_NUM_FORMS": "0",
                "line_items-MAX_NUM_FORMS": "1000",
                "line_items-0-description": "40 door",
                "line_items-0-category": "door",
                "line_items-0-count": "40",
                "line_items-0-unit_price_gbp": "5.00",
                "line_items-0-order": "0",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.e4s3.refresh_from_db()
        self.assertEqual(self.e4s3.settlement_status(), "recorded")
        self.assertEqual(
            self.e4s3.settlement.line_items.get().description, "40 door"
        )

    def test_does_not_hit_showing_save_past_guard(self):
        """The whole point of a separate model: saving settlement data for
        an elapsed showing must not go anywhere near Showing.save()'s
        past-showing refusal (see toolkit/diary/models/showing.py)."""
        self.assertTrue(self.e4s3.in_past())
        url = reverse(
            "edit-showing-settlement", kwargs={"showing_id": self.e4s3.pk}
        )
        resp = self.client.post(
            url,
            {
                "attendance": "10",
                "bar_contribution_gbp": "",
                "notes": "",
                "line_items-TOTAL_FORMS": "0",
                "line_items-INITIAL_FORMS": "0",
                "line_items-MIN_NUM_FORMS": "0",
                "line_items-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(resp.status_code, 302)


class EventHubSettlementDisplayTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.e4.save()
        self.client.login(username="admin", password="T3stPassword!")

    def test_outstanding_settlement_banner_shown(self):
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(resp, "Finances not recorded")

    def test_past_showings_expanded_when_outstanding(self):
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        # <details open> -- past showings section not collapsed by default
        self.assertContains(resp, '<details class="mb-3" open>')

    def test_no_banner_when_no_financial_activity(self):
        """settlement_status() correctly returns "not_applicable" here, but
        the banner condition used to show it anyway (any truthy non-
        "recorded" status), so a no_financial_activity event was wrongly
        told it had an outstanding settlement/distributor payment. Found
        live 2026-09-14."""
        self.e4.no_financial_activity = True
        self.e4.save()
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertNotContains(resp, "Finances not recorded")
        self.assertNotContains(resp, "Finances partially recorded")
        self.assertNotContains(resp, "Distributor payment: Outstanding")

    def test_settlement_column_hidden_when_flag_off(self):
        cfg = get_site_config()
        cfg.event_settlement_enabled = False
        cfg.save()
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertNotContains(resp, "Finances not recorded")

    def test_prs_link_shown_for_performer_fee_event(self):
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(resp, "PRS/PPL registration")
        self.assertNotContains(resp, "PRS/PPL registration (recorded)")

    def test_prs_link_marks_recorded_once_data_entered(self):
        registration = PerformerRegistration.objects.create(
            event=self.e4, filled_in_by="Alex"
        )
        self.assertTrue(registration.has_any_data())
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(resp, "PRS/PPL registration (recorded)")

    def test_prs_link_hidden_for_film_license_event(self):
        self.e4.cost_type = Event.COST_TYPE_FILM_LICENSE
        self.e4.save()
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertNotContains(resp, "PRS/PPL registration")

    def test_bulk_checkboxes_shown_for_series_with_outstanding_showings(self):
        # e4 has two past showings (e4s3, e4s4) -- a series by the view's
        # own is_series = len(all_showings) > 1 definition.
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(resp, "nothing-to-report-checkbox")
        self.assertContains(resp, "Mark selected as nothing to report")

    def test_bulk_checkboxes_hidden_for_single_showing_event(self):
        single = Event(
            name="One-off gig", cost_type=Event.COST_TYPE_FILM_LICENSE
        )
        single.save()
        Showing(event=single, start="2013-06-01T19:00:00+00:00").save(
            force=True
        )
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": single.pk})
        )
        self.assertNotContains(resp, "nothing-to-report-checkbox")

    def test_no_checkbox_for_already_recorded_showing(self):
        settlement = ShowingSettlement.objects.create(
            showing=self.e4s3, attendance=10
        )
        SettlementLineItem.objects.create(
            settlement=settlement, description="x", count=10
        )
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        content = resp.content.decode()
        # Only e4s4 (still outstanding) should get a checkbox, not e4s3.
        self.assertEqual(
            content.count('class="nothing-to-report-checkbox"'), 1
        )

    def test_nothing_to_report_badge_shown(self):
        ShowingSettlement.objects.create(
            showing=self.e4s3, nothing_to_report=True
        )
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(resp, "Nothing to report")


class BulkMarkNothingToReportViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.e4.save()
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse("bulk-nothing-to-report")

    def test_marks_selected_showings(self):
        resp = self.client.post(
            self.url, {"showing_ids": [self.e4s3.pk, self.e4s4.pk]}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.e4s3.settlement_status(), "nothing_to_report")
        self.assertEqual(self.e4s4.settlement_status(), "nothing_to_report")

    def test_redirects_to_event_hub(self):
        resp = self.client.post(self.url, {"showing_ids": [self.e4s3.pk]})
        self.assertRedirects(
            resp,
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
            + "#showings-heading",
        )

    def test_does_not_clear_existing_attendance(self):
        ShowingSettlement.objects.create(showing=self.e4s3, attendance=20)
        self.client.post(self.url, {"showing_ids": [self.e4s3.pk]})
        self.e4s3.settlement.refresh_from_db()
        self.assertEqual(self.e4s3.settlement.attendance, 20)
        self.assertTrue(self.e4s3.settlement.nothing_to_report)

    def test_no_showings_selected_is_a_no_op(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ShowingSettlement.objects.exists())

    def test_non_numeric_id_is_ignored_not_a_500(self):
        """pk__in with a non-numeric string raises ValueError from the
        field, so an unfiltered list would 500 on a mangled POST."""
        resp = self.client.post(
            self.url, {"showing_ids": ["not-a-number", self.e4s3.pk]}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            ShowingSettlement.objects.get(showing=self.e4s3).nothing_to_report
        )

    def test_only_non_numeric_ids_is_a_no_op(self):
        resp = self.client.post(self.url, {"showing_ids": ["../../etc"]})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ShowingSettlement.objects.exists())

    def test_404s_when_disabled(self):
        cfg = get_site_config()
        cfg.event_settlement_enabled = False
        cfg.save()
        resp = self.client.post(self.url, {"showing_ids": [self.e4s3.pk]})
        self.assertEqual(resp.status_code, 404)

    def test_get_not_allowed(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)


class ProgrammerPastEventsViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.programmer = Volunteer.objects.first()
        self.e4.programmer = self.programmer
        self.e4.save()
        # Being Event.programmer is a data field, not a permission tier --
        # still needs toolkit.write (Programmer+) to reach a write_required
        # view at all.
        write_perm, _ = _create_toolkit_permissions()
        self.programmer.user.user_permissions.add(write_perm)

    def test_scoped_to_own_events_only(self):
        self.client.force_login(self.programmer.user)
        resp = self.client.get(reverse("programmer-past-events"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.e4.name)
        self.assertNotContains(resp, self.e7.name)


class FinanceSettlementReviewViewTests(DiaryTestsMixin, TestCase):
    """e4's showings: e4s3 9/6/13, e4s4 14/9/13 -- latest_showing_start
    (the same Max() annotation past_events_search uses) is 14/9/13, so a
    date range has to bracket September, not June, to catch this event."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.e4.save()
        self.client.login(username="admin", password="T3stPassword!")

    def test_404s_when_disabled(self):
        cfg = get_site_config()
        cfg.event_settlement_enabled = False
        cfg.save()
        resp = self.client.get(reverse("finance-settlement-review"))
        self.assertEqual(resp.status_code, 404)

    def test_event_shown_when_in_range(self):
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.e4.name)

    def test_event_excluded_when_out_of_range(self):
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-01-01", "date_to": "2013-02-28"},
        )
        self.assertNotContains(resp, self.e4.name)

    def test_status_and_drilldown_links_shown(self):
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertContains(resp, "Finances not recorded")
        self.assertContains(
            resp,
            reverse(
                "edit-showing-settlement", kwargs={"showing_id": self.e4s4.pk}
            ),
        )
        self.assertContains(
            resp,
            reverse(
                "edit-distributor-payment", kwargs={"event_id": self.e4.pk}
            ),
        )

    def test_nothing_to_report_badge_shown_in_drilldown(self):
        ShowingSettlement.objects.create(
            showing=self.e4s4, nothing_to_report=True
        )
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertContains(resp, "Nothing to report")

    def test_no_financial_activity_excluded(self):
        self.e4.no_financial_activity = True
        self.e4.save()
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertNotContains(resp, self.e4.name)

    def test_prs_badge_not_recorded_by_default(self):
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertContains(resp, "PRS/PPL not recorded")

    def test_prs_badge_recorded_once_data_entered(self):
        PerformerRegistration.objects.create(
            event=self.e4, filled_in_by="Alex"
        )
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertContains(resp, "PRS/PPL recorded")

    def test_no_prs_badge_for_film_license_event(self):
        self.e4.cost_type = Event.COST_TYPE_FILM_LICENSE
        self.e4.save()
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertNotContains(resp, "PRS/PPL not recorded")
        self.assertNotContains(resp, "PRS/PPL recorded")

    def test_recurring_event_with_future_showing_still_shown_in_range(self):
        """A recurring event's overall latest showing is routinely a future
        date outside any reporting month -- filtering on that (rather than
        the latest *elapsed* showing) wrongly excluded the whole event, so
        every S+S weekly regular (Art Club, Creative Writing, ...) silently
        vanished from this screen the moment it had a future date on the
        books. Found live 2026-09-14."""
        Showing(
            start=self.e4s4.start.replace(year=self.e4s4.start.year + 20),
            event=self.e4,
            booked_by="Future booking",
            confirmed=True,
        ).save()
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertContains(resp, self.e4.name)

    def test_range_is_narrowed_in_the_db_not_just_in_python(self):
        """The Python pass decides the answer, but the DB has to narrow the
        candidate set first, or every event the venue has ever run is
        loaded (with all its showings) to report on one month."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(
                reverse("finance-settlement-review"),
                {"date_from": "2013-09-01", "date_to": "2013-09-30"},
            )
        event_query = next(
            q["sql"]
            for q in ctx.captured_queries
            if "Events" in q["sql"] and "Showings" in q["sql"]
        )
        self.assertIn("2013-09-01", event_query)
        self.assertIn("2013-09-30", event_query)

    def test_csv_download_link_present(self):
        resp = self.client.get(
            reverse("finance-settlement-review"),
            {"date_from": "2013-09-01", "date_to": "2013-09-30"},
        )
        self.assertContains(resp, reverse("prs-report"))


class EventPrsRegistrationEditViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.e4.save()
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_renders_form(self):
        resp = self.client.get(
            reverse("edit-prs-registration", kwargs={"event_id": self.e4.pk})
        )
        self.assertEqual(resp.status_code, 200)

    def test_post_creates_registration_and_performer(self):
        url = reverse("edit-prs-registration", kwargs={"event_id": self.e4.pk})
        resp = self.client.post(
            url,
            {
                "filled_in_by": "Alex",
                "vat_on_tickets": "true",
                "notes": "",
                "performers-TOTAL_FORMS": "1",
                "performers-INITIAL_FORMS": "0",
                "performers-MIN_NUM_FORMS": "0",
                "performers-MAX_NUM_FORMS": "1000",
                "performers-0-name": "The Band",
                "performers-0-registered": PRSPerformerEntry.REGISTERED_YES,
                "performers-0-is_volunteer_or_amateur": "unknown",
                "performers-0-order": "0",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.e4.refresh_from_db()
        registration = self.e4.performer_registration
        self.assertEqual(registration.filled_in_by, "Alex")
        self.assertTrue(registration.vat_on_tickets)
        performer = registration.performers.get()
        self.assertEqual(performer.name, "The Band")
        self.assertEqual(
            performer.registered, PRSPerformerEntry.REGISTERED_YES
        )
        self.assertIsNone(performer.is_volunteer_or_amateur)

    def test_never_gates_settlement_status(self):
        """No PerformerRegistration exists at all -- settlement_status()
        must not care, since this feature is deliberately optional."""
        self.assertEqual(self.e4.settlement_status(), "not_recorded")


class PrsReportViewTests(DiaryTestsMixin, TestCase):
    """e4's showings: e4s3 9/6/13, e4s4 14/9/13 (both elapsed, matching
    FinanceSettlementReviewViewTests above)."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.e4.save()
        self.client.login(username="admin", password="T3stPassword!")

    def _rows(self, **params):
        resp = self.client.get(reverse("prs-report"), params)
        return resp, list(csv.reader(io.StringIO(resp.content.decode())))

    def test_csv_content_type_and_filename(self):
        resp, _ = self._rows(date_from="2013-09-01", date_to="2013-09-30")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("attachment", resp["Content-Disposition"])

    def test_event_without_performers_gets_blank_row(self):
        _, rows = self._rows(date_from="2013-09-01", date_to="2013-09-30")
        data_row = rows[1]
        self.assertEqual(data_row[0], self.e4.name)
        self.assertEqual(data_row[6], "")  # Performer
        self.assertEqual(data_row[7], "")  # Registered

    def test_performer_row_data(self):
        registration = PerformerRegistration.objects.create(
            event=self.e4, filled_in_by="Alex", vat_on_tickets=True
        )
        PRSPerformerEntry.objects.create(
            registration=registration,
            name="The Band",
            registered=PRSPerformerEntry.REGISTERED_YES,
        )
        _, rows = self._rows(date_from="2013-09-01", date_to="2013-09-30")
        data_row = rows[1]
        self.assertEqual(data_row[0], self.e4.name)
        self.assertEqual(data_row[4], "Alex")
        self.assertEqual(data_row[5], "Yes")
        self.assertEqual(data_row[6], "The Band")
        self.assertEqual(data_row[7], "Registered")

    def test_film_license_events_excluded(self):
        film_event = Event(
            name="Some Film", cost_type=Event.COST_TYPE_FILM_LICENSE
        )
        film_event.save()
        Showing(event=film_event, start="2013-09-05T19:00:00+00:00").save(
            force=True
        )
        _, rows = self._rows(date_from="2013-09-01", date_to="2013-09-30")
        names = [row[0] for row in rows[1:]]
        self.assertIn(self.e4.name, names)
        self.assertNotIn("Some Film", names)

    def test_out_of_range_events_excluded(self):
        _, rows = self._rows(date_from="2013-01-01", date_to="2013-02-28")
        self.assertEqual(len(rows), 1)  # header only


class SettlementRevisionTests(DiaryTestsMixin, TestCase):
    """Task 9.171's revision-history ask: a save that overwrites an
    already-recorded settlement keeps the prior state; a first-ever entry
    keeps nothing, since there's no "original" to protect yet."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.e4.save()
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse(
            "edit-showing-settlement", kwargs={"showing_id": self.e4s3.pk}
        )

    def _post(self, attendance, description="", unit_price="", count="1"):
        # Updating (rather than duplicating) an existing line item needs its
        # id in the formset data, exactly as a real edit's pre-populated
        # hidden field would supply -- otherwise Django's formset treats a
        # blank id as "new row" and the item count would grow each POST.
        existing = list(
            SettlementLineItem.objects.filter(
                settlement__showing=self.e4s3
            ).order_by("pk")
        )
        data = {
            "attendance": attendance,
            "bar_contribution_gbp": "",
            "notes": "",
            "line_items-TOTAL_FORMS": (
                "1" if (description or existing) else "0"
            ),
            "line_items-INITIAL_FORMS": "1" if existing else "0",
            "line_items-MIN_NUM_FORMS": "0",
            "line_items-MAX_NUM_FORMS": "1000",
        }
        if existing:
            data["line_items-0-id"] = str(existing[0].pk)
        if description or existing:
            data.update(
                {
                    "line_items-0-description": description,
                    "line_items-0-category": "",
                    "line_items-0-count": count,
                    "line_items-0-unit_price_gbp": unit_price,
                    "line_items-0-order": "0",
                }
            )
        return self.client.post(self.url, data)

    def test_no_revision_on_first_entry(self):
        self._post("40")
        self.assertEqual(SettlementRevision.objects.count(), 0)

    def test_revision_created_on_correction(self):
        self._post("40")
        self._post("55")
        self.assertEqual(SettlementRevision.objects.count(), 1)
        rev = SettlementRevision.objects.get()
        self.assertEqual(rev.attendance, 40)

    def test_no_revision_when_nothing_actually_changes(self):
        self._post("40")
        self._post("40")
        self.assertEqual(SettlementRevision.objects.count(), 0)

    def test_revision_captures_prior_line_items(self):
        self._post("40", description="40 door", unit_price="5.00")
        self._post("40", description="45 door", unit_price="5.00")
        rev = SettlementRevision.objects.get()
        self.assertEqual(len(rev.line_items_snapshot), 1)
        self.assertEqual(rev.line_items_snapshot[0]["description"], "40 door")
        self.assertEqual(
            self.e4s3.settlement.line_items.get().description, "45 door"
        )

    def test_revision_records_saved_by(self):
        self._post("40")
        self._post("55")
        rev = SettlementRevision.objects.get()
        self.assertEqual(rev.saved_by.username, "admin")

    def test_settlement_edit_page_shows_change_history(self):
        self._post("40")
        self._post("55")
        resp = self.client.get(self.url)
        self.assertContains(resp, "Change history")
        self.assertContains(resp, "1 correction")

    def test_event_hub_audit_trail_shows_settlement_correction(self):
        self._post("40")
        self._post("55")
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(resp, "Finances corrected for")


class DistributorPaymentRevisionTests(DiaryTestsMixin, TestCase):
    """Distributor-payment fields reuse EventTermsRevision (9.171 extends
    the existing precedent rather than inventing a new audit model)."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.event_settlement_enabled = True
        cfg.save()
        self.e4.cost_type = Event.COST_TYPE_PERFORMER_FEE
        self.e4.save()
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse(
            "edit-distributor-payment", kwargs={"event_id": self.e4.pk}
        )

    def test_revision_on_first_save_from_blank(self):
        """Event rows already exist (unlike ShowingSettlement, which is
        get_or_create'd fresh) -- so unlike the settlement view's explicit
        "first entry vs correction" carve-out, any change from Event's
        existing (blank) state is still a real change and gets recorded,
        matching the pre-existing terms/outside_hire/private behaviour."""
        self.client.post(
            self.url,
            {
                "distributor_invoiced_date": "2026-09-01",
                "distributor_paid_date": "",
                "distributor_paid_amount_gbp": "",
            },
        )
        self.assertEqual(self.e4.terms_revisions.count(), 1)
        rev = self.e4.terms_revisions.first()
        self.assertEqual(rev.changed_fields, "distributor_invoiced_date")

    def test_revision_on_correction(self):
        self.client.post(
            self.url,
            {
                "distributor_invoiced_date": "2026-09-01",
                "distributor_paid_date": "2026-09-05",
                "distributor_paid_amount_gbp": "100.00",
            },
        )
        self.client.post(
            self.url,
            {
                "distributor_invoiced_date": "2026-09-01",
                "distributor_paid_date": "2026-09-10",
                "distributor_paid_amount_gbp": "100.00",
            },
        )
        self.e4.refresh_from_db()
        rev = self.e4.terms_revisions.first()
        self.assertIsNotNone(rev)
        self.assertEqual(rev.changed_fields, "distributor_paid_date")
        self.assertEqual(str(rev.distributor_paid_date), "2026-09-05")
        self.assertIn("distributor paid", rev.summary())

    def test_revision_records_saved_by(self):
        self.client.post(
            self.url,
            {
                "distributor_invoiced_date": "2026-09-01",
                "distributor_paid_date": "",
                "distributor_paid_amount_gbp": "",
            },
        )
        self.client.post(
            self.url,
            {
                "distributor_invoiced_date": "2026-09-05",
                "distributor_paid_date": "",
                "distributor_paid_amount_gbp": "",
            },
        )
        self.e4.refresh_from_db()
        rev = self.e4.terms_revisions.first()
        self.assertEqual(rev.saved_by.username, "admin")
