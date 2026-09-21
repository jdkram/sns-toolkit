# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Tests for task 9.174: film readiness tracking.

The unit is one film (a FilmPrep) linked to the showings it plays at: a run
of one film, a different film per date, or the films on a double or triple
bill.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.audit.models import EventAuditLog
from toolkit.diary.models import (
    Event,
    EventTag,
    FilmCopy,
    FilmMilestone,
    FilmPrep,
    Showing,
    get_site_config,
)
from toolkit.diary.models.film_prep import (
    FORMAT_DCP_FILMVAULT,
    FORMAT_DCP_HDD,
    FORMAT_DISC,
    FORMAT_MP4,
    IN_PROGRESS,
    NOT_STARTED,
    PROBLEM,
    READY,
    RESULT_OK,
    RESULT_PROBLEM,
    film_row,
    returns_outstanding,
    showings_without_film,
    upcoming_film_preps,
    urgency_for,
)
from toolkit.diary.tests.common import DiaryTestsMixin


def _keys(copy):
    return [m.key for m in copy.ordered_milestones()]


def _film(event, showings=None, title="", **kwargs):
    """A FilmPrep for ``event``, linked to ``showings`` (default: every
    showing the event has right now)."""
    prep = FilmPrep.objects.create(event=event, film_title=title, **kwargs)
    prep.showings.set(event.showings.all() if showings is None else showings)
    return prep


def _copy(prep, fmt=FORMAT_MP4, label="Main copy"):
    return FilmCopy.objects.create(film_prep=prep, label=label, format=fmt)


def _complete_all(copy, user, test_result=RESULT_OK):
    for step in copy.pre_steps():
        step.complete(user, result=test_result if step.key == "tested" else "")


class FilmCopyMilestoneTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(name="A film")
        self.prep = _film(self.event)
        self.user = get_user_model().objects.create_user("proj", password="x")

    def _copy(self, fmt=FORMAT_DISC, label="Main copy"):
        return _copy(self.prep, fmt, label)

    def test_milestones_created_per_format(self):
        self.assertEqual(
            _keys(self._copy(FORMAT_DISC)),
            ["in_building", "in_booth", "tested"],
        )
        self.assertEqual(
            _keys(self._copy(FORMAT_DCP_FILMVAULT)),
            ["on_filmvault", "ingested", "tested"],
        )
        self.assertEqual(
            _keys(self._copy(FORMAT_MP4)), ["in_building", "tested"]
        )

    def test_changing_format_drops_untouched_steps_only(self):
        copy = self._copy(FORMAT_DISC)
        copy.milestones.get(key="in_booth").complete(self.user)
        copy.format = FORMAT_MP4
        copy.save()
        keys = set(copy.milestones.values_list("key", flat=True))
        # in_booth was done, so it is kept even though MP4 has no such step.
        self.assertEqual(keys, {"in_building", "in_booth", "tested"})
        # ...but it no longer counts as a step for the new format.
        self.assertEqual(_keys(copy), ["in_building", "tested"])

    def test_changing_format_removes_claimed_steps_never(self):
        copy = self._copy(FORMAT_DISC)
        copy.milestones.get(key="in_booth").claim(self.user)
        copy.format = FORMAT_MP4
        copy.save()
        self.assertTrue(copy.milestones.filter(key="in_booth").exists())

    def test_resaving_does_not_duplicate_milestones(self):
        copy = self._copy(FORMAT_DISC)
        copy.save()
        copy.save()
        self.assertEqual(copy.milestones.count(), 3)

    def test_claim_and_complete_record_who_and_when(self):
        copy = self._copy(FORMAT_MP4)
        step = copy.milestones.get(key="tested")
        planned = datetime.date(2026, 10, 1)
        step.claim(self.user, planned_for=planned)
        step.refresh_from_db()
        self.assertEqual(step.claimed_by, self.user)
        self.assertEqual(step.planned_for, planned)
        self.assertIsNotNone(step.claimed_at)
        self.assertIsNone(step.done_at)
        step.complete(self.user, result=RESULT_OK, notes="Clean")
        step.refresh_from_db()
        self.assertEqual(step.done_by, self.user)
        self.assertIsNotNone(step.done_at)
        self.assertEqual(step.notes, "Clean")


class ReadinessTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(name="A film")
        self.prep = _film(self.event)
        self.user = get_user_model().objects.create_user("proj", password="x")

    def _copy(self, fmt=FORMAT_MP4):
        return _copy(self.prep, fmt)

    def test_no_copies_is_not_started(self):
        self.assertEqual(self.prep.readiness(), NOT_STARTED)

    def test_untouched_copy_is_not_started(self):
        self.assertEqual(self._copy().readiness(), NOT_STARTED)

    def test_partly_done_copy_is_in_progress(self):
        copy = self._copy()
        copy.milestones.get(key="in_building").complete(self.user)
        self.assertEqual(copy.readiness(), IN_PROGRESS)
        self.assertEqual(copy.next_step().key, "tested")

    def test_fully_done_copy_is_ready(self):
        copy = self._copy()
        _complete_all(copy, self.user)
        self.assertEqual(copy.readiness(), READY)
        self.assertIsNone(copy.next_step())

    def test_failed_test_is_problem(self):
        copy = self._copy()
        _complete_all(copy, self.user, test_result=RESULT_PROBLEM)
        self.assertEqual(copy.readiness(), PROBLEM)
        self.assertEqual(self.prep.readiness(), PROBLEM)

    def test_working_backup_covers_a_broken_main_copy(self):
        broken = self._copy(FORMAT_DISC)
        _complete_all(broken, self.user, test_result=RESULT_PROBLEM)
        backup = self._copy(FORMAT_MP4)
        _complete_all(backup, self.user)
        self.assertEqual(self.prep.readiness(), READY)


class FilmLinkingTests(TestCase):
    """A film only links to showings of its own event; one showing can carry
    several films (a bill); one film can play at several showings (a run)."""

    def setUp(self):
        self.now = timezone.now()
        self.event = Event.objects.create(name="Family Film Club")
        self.other = Event.objects.create(name="Community Kitchen")
        self.s1 = self._showing(self.event, 5)
        self.s2 = self._showing(self.event, 12)
        self.kitchen = self._showing(self.other, 5)

    def _showing(self, event, days):
        return Showing.objects.create(
            event=event, start=self.now + datetime.timedelta(days=days)
        )

    def test_display_title_falls_back_to_the_event_name(self):
        self.assertEqual(_film(self.event).display_title, "Family Film Club")
        self.assertEqual(
            _film(self.event, title="Paddington").display_title, "Paddington"
        )

    def test_cannot_link_a_showing_of_another_event(self):
        prep = _film(self.event, showings=[])
        with self.assertRaises(ValueError):
            prep.showings.add(self.kitchen)

    def test_cannot_link_from_the_showing_side_either(self):
        prep = _film(self.event, showings=[])
        with self.assertRaises(ValueError):
            self.kitchen.film_preps.add(prep)

    def test_one_film_can_cover_a_whole_run(self):
        prep = _film(self.event)
        self.assertEqual(set(prep.showings.all()), {self.s1, self.s2})

    def test_a_different_film_each_date_has_separate_status(self):
        first = _film(self.event, [self.s1], title="Paddington")
        second = _film(self.event, [self.s2], title="The Iron Giant")
        user = get_user_model().objects.create_user("proj", password="x")
        _complete_all(_copy(first), user)
        _copy(second)
        self.assertEqual(first.readiness(), READY)
        self.assertEqual(second.readiness(), NOT_STARTED)

    def test_double_and_triple_bills_are_separate_films_on_one_showing(self):
        a = _film(self.event, [self.s1], title="Film A", bill_position=1)
        b = _film(self.event, [self.s1], title="Film B", bill_position=2)
        c = _film(self.event, [self.s1], title="Film C", bill_position=3)
        self.assertEqual(list(self.s1.film_preps.all()), [a, b, c])
        user = get_user_model().objects.create_user("proj", password="x")
        _complete_all(_copy(b, FORMAT_DISC), user)
        self.assertEqual(a.readiness(), NOT_STARTED)
        self.assertEqual(b.readiness(), READY)

    def test_a_bill_lists_its_companions_in_running_order(self):
        _film(self.event, [self.s1], title="Second", bill_position=2)
        _film(self.event, [self.s1], title="First", bill_position=1)
        third = _film(self.event, [self.s1], title="Third", bill_position=3)
        _copy(third)
        prep = upcoming_film_preps(self.now).get(pk=third.pk)
        row = film_row(prep, self.now)
        self.assertEqual(
            [c.display_title for c in row["companions"]], ["First", "Second"]
        )

    def test_urgency_follows_the_earliest_showing(self):
        imminent = self._showing(self.event, 2)
        prep = _film(self.event, [imminent, self.s1, self.s2])
        self.assertEqual(prep.urgency(self.now), "urgent")
        imminent.delete()
        self.assertEqual(prep.urgency(self.now), "soon")

    def test_cancelled_showing_is_ignored_for_urgency(self):
        prep = _film(self.event, [self.s1])
        Showing.objects.filter(pk=self.s1.pk).update(cancelled=True)
        self.assertIsNone(prep.urgency(self.now))


class UrgencyForTests(TestCase):
    def test_boundaries(self):
        now = timezone.now()
        day = datetime.timedelta(days=1)
        self.assertIsNone(urgency_for(None, now))
        self.assertEqual(urgency_for(now + 2 * day, now), "urgent")
        self.assertEqual(urgency_for(now + 5 * day, now), "soon")
        self.assertIsNone(urgency_for(now + 10 * day, now))


class ShowingsWithoutFilmTests(TestCase):
    """The prompt for a series where each date needs its own film."""

    def setUp(self):
        self.now = timezone.now()
        self.film_tag = EventTag.objects.get_or_create(
            slug="film", defaults={"name": "film"}
        )[0]
        self.club = Event.objects.create(name="Family Film Club")
        self.club.tags.add(self.film_tag)
        self.d1 = self._showing(self.club, 4)
        self.d2 = self._showing(self.club, 9)

    def _showing(self, event, days, **kw):
        return Showing.objects.create(
            event=event, start=self.now + datetime.timedelta(days=days), **kw
        )

    def test_dates_with_no_film_are_listed(self):
        self.assertEqual(
            list(showings_without_film(self.now)), [self.d1, self.d2]
        )

    def test_a_date_with_a_film_is_not(self):
        _film(self.club, [self.d1], title="Paddington")
        self.assertEqual(list(showings_without_film(self.now)), [self.d2])

    def test_lookahead_window_applies(self):
        self.assertEqual(
            list(showings_without_film(self.now, days=5)), [self.d1]
        )

    def test_events_that_are_not_film_events_are_ignored(self):
        kitchen = Event.objects.create(name="Community Kitchen")
        self._showing(kitchen, 3)
        self.assertNotIn(
            "Community Kitchen",
            [s.event.name for s in showings_without_film(self.now)],
        )

    def test_cancelled_and_past_dates_are_ignored(self):
        self._showing(self.club, 6, cancelled=True)
        past = self._showing(self.club, 1)
        Showing.objects.filter(pk=past.pk).update(
            start=self.now - datetime.timedelta(days=3)
        )
        self.assertEqual(
            list(showings_without_film(self.now)), [self.d1, self.d2]
        )


class FilmPrepViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.film_prep_enabled = True
        cfg.save()
        self.prep = _film(self.e4)
        self.copy = _copy(self.prep, FORMAT_DISC)
        self.step = self.copy.milestones.get(key="in_building")
        self.client.login(username="admin", password="T3stPassword!")

    def _disable(self):
        cfg = get_site_config()
        cfg.film_prep_enabled = False
        cfg.save()

    def _post_data(self, showings, **extra):
        data = {
            "film_title": "",
            "bill_position": "1",
            "showings": [str(s.pk) for s in showings],
            "subtitles": "none",
            "trailers_plan": "",
            "booth_notes": "",
            "handover_note": "",
            "copies-TOTAL_FORMS": "0",
            "copies-INITIAL_FORMS": "0",
            "copies-MIN_NUM_FORMS": "0",
            "copies-MAX_NUM_FORMS": "1000",
        }
        data.update(extra)
        return data

    def test_edit_and_add_pages_render(self):
        self.assertEqual(
            self.client.get(
                reverse("edit-film-prep", kwargs={"prep_id": self.prep.pk})
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("add-film-prep", kwargs={"event_id": self.e4.pk})
            ).status_code,
            200,
        )

    def test_all_endpoints_404_when_flag_off(self):
        self._disable()
        for name, args, method in [
            ("edit-film-prep", [self.prep.pk], "get"),
            ("add-film-prep", [self.e4.pk], "get"),
            ("delete-film-prep", [self.prep.pk], "post"),
            ("film-milestone-claim", [self.step.pk], "post"),
            ("film-milestone-complete", [self.step.pk], "post"),
        ]:
            resp = getattr(self.client, method)(reverse(name, args=args))
            self.assertEqual(resp.status_code, 404, name)

    def test_read_only_user_cannot_claim(self):
        self.client.logout()
        self.client.login(username="read_only", password="T3stPassword!1")
        resp = self.client.post(
            reverse("film-milestone-claim", args=[self.step.pk])
        )
        self.assertEqual(resp.status_code, 302)
        self.step.refresh_from_db()
        self.assertIsNone(self.step.claimed_by)

    def test_add_a_film_with_a_backup_copy(self):
        shows = list(self.e4.showings.all()[:1])
        resp = self.client.post(
            reverse("add-film-prep", kwargs={"event_id": self.e4.pk}),
            self._post_data(
                shows,
                film_title="Second feature",
                bill_position="2",
                backup_in_place="on",
                backup_note="MP4 in a folder",
                **{
                    "copies-TOTAL_FORMS": "1",
                    "copies-0-label": "Main copy",
                    "copies-0-format": FORMAT_DISC,
                },
            ),
        )
        self.assertEqual(resp.status_code, 302)
        prep = FilmPrep.objects.get(film_title="Second feature")
        self.assertEqual(prep.event, self.e4)
        self.assertEqual(prep.bill_position, 2)
        self.assertEqual(list(prep.showings.all()), shows)
        self.assertTrue(prep.backup_in_place)
        self.assertEqual(prep.backup_note, "MP4 in a folder")
        self.assertEqual(prep.updated_by.username, "admin")
        self.assertEqual(prep.copies.get().milestones.count(), 3)

    def test_a_film_needs_at_least_one_showing(self):
        resp = self.client.post(
            reverse("add-film-prep", kwargs={"event_id": self.e4.pk}),
            self._post_data([], film_title="Orphan"),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tick at least one showing")
        self.assertFalse(FilmPrep.objects.filter(film_title="Orphan").exists())

    def test_cannot_tick_a_showing_of_another_event(self):
        foreign = Showing.objects.filter(event=self.e1).first()
        resp = self.client.post(
            reverse("add-film-prep", kwargs={"event_id": self.e4.pk}),
            self._post_data([foreign], film_title="Wrong event"),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            FilmPrep.objects.filter(film_title="Wrong event").exists()
        )

    def test_new_film_defaults_to_the_dates_that_have_no_film(self):
        ids = {s.pk for s in self.e4.showings.all()}
        resp = self.client.get(
            reverse("add-film-prep", kwargs={"event_id": self.e4.pk})
        )
        # Every date already has the first film, so all are offered again.
        ticked = {
            int(v)
            for v in resp.context["form"]
            .initial["showings"]
            .values_list("pk", flat=True)
        }
        self.assertEqual(ticked, ids)

    def test_showing_query_param_preselects_one_date(self):
        one = self.e4.showings.first()
        resp = self.client.get(
            reverse("add-film-prep", kwargs={"event_id": self.e4.pk}),
            {"showing": one.pk},
        )
        self.assertEqual(list(resp.context["form"].initial["showings"]), [one])

    def test_delete_needs_the_confirmation_box(self):
        url = reverse("delete-film-prep", args=[self.prep.pk])
        self.client.post(url)
        self.assertTrue(FilmPrep.objects.filter(pk=self.prep.pk).exists())
        self.client.post(url, {"confirm": "1"})
        self.assertFalse(FilmPrep.objects.filter(pk=self.prep.pk).exists())
        self.assertFalse(FilmCopy.objects.filter(pk=self.copy.pk).exists())

    def test_claim_records_user_date_and_audit_row(self):
        resp = self.client.post(
            reverse("film-milestone-claim", args=[self.step.pk]),
            {"planned_for": "2026-10-01"},
        )
        self.assertEqual(resp.status_code, 302)
        self.step.refresh_from_db()
        self.assertEqual(self.step.claimed_by.username, "admin")
        self.assertEqual(self.step.planned_for, datetime.date(2026, 10, 1))
        log = EventAuditLog.objects.get(
            event=self.e4, action=EventAuditLog.ACTION_FILM_CLAIMED
        )
        self.assertIn(self.e4.name, log.detail)

    def test_complete_test_step_with_problem(self):
        tested = self.copy.milestones.get(key="tested")
        self.client.post(
            reverse("film-milestone-complete", args=[tested.pk]),
            {"result": "problem", "notes": "No sound"},
        )
        tested.refresh_from_db()
        self.assertIsNotNone(tested.done_at)
        self.assertEqual(tested.result, "problem")
        self.assertEqual(self.copy.readiness(), PROBLEM)
        self.assertTrue(
            EventAuditLog.objects.filter(
                event=self.e4, action=EventAuditLog.ACTION_FILM_STEP_DONE
            ).exists()
        )

    def test_next_redirect_rejects_external_urls(self):
        resp = self.client.post(
            reverse("film-milestone-claim", args=[self.step.pk]),
            {"next": "https://evil.example/"},
        )
        self.assertNotIn("evil.example", resp["Location"])

    def test_hub_shows_one_block_per_film_and_only_when_flag_on(self):
        _film(self.e4, title="Second feature", bill_position=2)
        url = reverse(
            "edit-event-details-view", kwargs={"event_id": self.e4.pk}
        )
        resp = self.client.get(url)
        self.assertContains(resp, 'id="film-readiness"')
        self.assertContains(resp, "Second feature")
        self.assertContains(resp, "on a bill with")
        self._disable()
        self.assertNotContains(self.client.get(url), 'id="film-readiness"')

    def test_hub_flags_dates_with_no_film(self):
        tag = EventTag.objects.get_or_create(
            slug="film", defaults={"name": "film"}
        )[0]
        club = Event.objects.create(name="Family Film Club")
        club.tags.add(tag)
        when = timezone.now() + datetime.timedelta(days=6)
        Showing.objects.create(event=club, start=when)
        resp = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": club.pk})
        )
        self.assertContains(resp, "No film recorded yet for")


class ProjectionistPermissionTests(DiaryTestsMixin, TestCase):
    """Rota-only projectionists may claim and complete steps, but nothing
    else; a programmer who is also a projectionist is simply a programmer."""

    def setUp(self):
        super().setUp()
        from toolkit.diary.models import Role, RotaEntry
        from toolkit.members.models import Member, Volunteer

        cfg = get_site_config()
        cfg.film_prep_enabled = True
        cfg.save()
        self.prep = _film(self.e4)
        self.copy = _copy(self.prep, FORMAT_DISC)
        self.step = self.copy.milestones.get(key="tested")
        role = Role.objects.create(name="Projectionist", is_projectionist=True)
        user = get_user_model().objects.create_user("rota_proj", password="pw")
        member = Member.objects.create(
            name="Rota Proj", email="rp@example.com"
        )
        volunteer = Volunteer.objects.create(member=member, user=user)
        # A showing near the real "now": the fixture showings are old enough
        # to fall outside the projectionist window.
        shift = Showing.objects.create(
            event=self.e4, start=timezone.now() + datetime.timedelta(days=1)
        )
        RotaEntry.objects.create(role=role, showing=shift, volunteer=volunteer)
        self.client.login(username="rota_proj", password="pw")

    def test_projectionist_can_claim_and_complete(self):
        resp = self.client.post(
            reverse("film-milestone-claim", args=[self.step.pk])
        )
        self.assertEqual(resp.status_code, 302)
        self.step.refresh_from_db()
        self.assertEqual(self.step.claimed_by.username, "rota_proj")
        self.client.post(
            reverse("film-milestone-complete", args=[self.step.pk]),
            {"result": "ok"},
        )
        self.step.refresh_from_db()
        self.assertIsNotNone(self.step.done_at)

    def test_projectionist_redirects_to_dashboard_not_the_hub(self):
        resp = self.client.post(
            reverse("film-milestone-claim", args=[self.step.pk])
        )
        self.assertEqual(resp["Location"], reverse("default-edit"))

    def test_projectionist_cannot_open_the_edit_pages(self):
        for name, args in [
            ("edit-film-prep", [self.prep.pk]),
            ("add-film-prep", [self.e4.pk]),
        ]:
            resp = self.client.get(reverse(name, args=args))
            self.assertEqual(resp.status_code, 302)
            self.assertIn("login", resp["Location"])

    def test_volunteer_without_projectionist_role_is_refused(self):
        self.client.logout()
        self.client.login(username="read_only", password="T3stPassword!1")
        self.client.post(reverse("film-milestone-claim", args=[self.step.pk]))
        self.step.refresh_from_db()
        self.assertIsNone(self.step.claimed_by)

    def test_programmer_who_is_also_projectionist_is_allowed_once(self):
        from toolkit.diary.models.film_prep import user_can_update_film_prep

        admin = get_user_model().objects.get(username="admin")
        self.assertTrue(user_can_update_film_prep(admin))


class FilmOverviewTests(DiaryTestsMixin, TestCase):
    """The all-films overview: any logged-in volunteer, every state."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.film_prep_enabled = True
        cfg.save()
        self.url = reverse("film-readiness-overview")
        self.now = timezone.now()

    def _film(self, name, days=5, title="", **prep):
        event = Event.objects.create(name=name)
        Showing.objects.create(
            event=event, start=self.now + datetime.timedelta(days=days)
        )
        film = _film(event, title=title, **prep)
        _copy(film, FORMAT_DISC)
        return film

    def test_404_when_flag_off(self):
        cfg = get_site_config()
        cfg.film_prep_enabled = False
        cfg.save()
        self.client.login(username="admin", password="T3stPassword!")
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_anonymous_is_sent_to_login(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    def test_visible_to_a_volunteer_with_no_permissions(self):
        self._film("Visible film")
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Visible film")

    def test_shows_ready_films_as_well_as_unready(self):
        ready = self._film("Ready film")
        for m in ready.copies.get().milestones.all():
            m.complete(None)
        self._film("Waiting film", days=6)
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(self.url)
        self.assertContains(resp, "Ready film")
        self.assertContains(resp, "Waiting film")
        self.assertEqual(resp.context["counts"]["ready"], 1)

    def test_a_series_shows_one_row_per_film_with_titles(self):
        club = Event.objects.create(name="Family Film Club")
        one = Showing.objects.create(
            event=club, start=self.now + datetime.timedelta(days=4)
        )
        two = Showing.objects.create(
            event=club, start=self.now + datetime.timedelta(days=11)
        )
        for showing, title in [(one, "Paddington"), (two, "The Iron Giant")]:
            _copy(_film(club, [showing], title=title), FORMAT_DISC)
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(self.url)
        self.assertContains(resp, "Paddington")
        self.assertContains(resp, "The Iron Giant")
        self.assertEqual(len(resp.context["rows"]), 2)

    def test_a_bill_shows_its_companions(self):
        event = Event.objects.create(name="Double bill night")
        showing = Showing.objects.create(
            event=event, start=self.now + datetime.timedelta(days=5)
        )
        _copy(_film(event, [showing], title="First half", bill_position=1))
        _copy(_film(event, [showing], title="Second half", bill_position=2))
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(self.url)
        self.assertContains(resp, "on a bill with Second half")
        self.assertContains(resp, "on a bill with First half")

    def test_dates_with_no_film_are_listed(self):
        tag = EventTag.objects.get_or_create(
            slug="film", defaults={"name": "film"}
        )[0]
        club = Event.objects.create(name="Family Film Club")
        club.tags.add(tag)
        Showing.objects.create(
            event=club, start=self.now + datetime.timedelta(days=5)
        )
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(self.url)
        self.assertContains(resp, "Dates with no film recorded yet")
        self.assertContains(resp, "Family Film Club")

    def test_past_and_cancelled_are_excluded(self):
        past = self._film("Past film", days=-3)
        cancelled = self._film("Cancelled film", days=4)
        cancelled.event.showings.update(cancelled=True)
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(self.url)
        for name in (past.event.name, cancelled.event.name):
            self.assertNotContains(resp, name)

    def test_backup_state_is_shown(self):
        self._film(
            "Has backup",
            backup_in_place=True,
            backup_note="Blu-ray in the booth drawer",
        )
        self._film("No backup", days=6, subtitles="none")
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(self.url)
        self.assertContains(resp, "Blu-ray in the booth drawer")
        self.assertContains(resp, '<span class="text-muted">None</span>')

    def test_event_links_only_for_programmers(self):
        film = self._film("Linked film")
        hub = reverse(
            "edit-event-details-view", kwargs={"event_id": film.event.pk}
        )
        self.client.login(username="no_perm", password="T3stPassword!2")
        self.assertNotContains(self.client.get(self.url), hub)
        self.client.logout()
        self.client.login(username="admin", password="T3stPassword!")
        self.assertContains(self.client.get(self.url), hub)

    def test_shows_display_name_not_username_for_claims(self):
        from toolkit.members.models import Member, Volunteer

        film = self._film("Claimed film")
        user = get_user_model().objects.create_user(
            "secret_login", password="x"
        )
        member = Member.objects.create(
            name="Alexandra Longsurname", email="a@example.com"
        )
        Volunteer.objects.create(member=member, user=user)
        film.copies.get().milestones.get(key="tested").claim(user)
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(self.url)
        self.assertContains(resp, "Alexandra L.")
        self.assertNotContains(resp, "secret_login")
        self.assertNotContains(resp, "Longsurname")


class ReturnsTests(DiaryTestsMixin, TestCase):
    """Hired hard drives that have to go back by courier after the run."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.film_prep_enabled = True
        cfg.save()
        self.now = timezone.now()
        self.event = Event.objects.create(name="Drive film")
        self.prep = FilmPrep.objects.create(event=self.event)
        self.copy = _copy(self.prep, FORMAT_DCP_HDD)
        self.user = get_user_model().objects.get(username="admin")

    def _showing(self, days, cancelled=False, linked=True):
        showing = Showing.objects.create(
            event=self.event,
            start=self.now + datetime.timedelta(days=days),
            cancelled=cancelled,
        )
        if linked:
            self.prep.showings.add(showing)
        return showing

    def _step(self, key):
        return self.copy.milestones.get(key=key)

    def _arrive(self):
        self._step("hdd_arrived").complete(self.user)

    def _rows(self):
        return returns_outstanding(self.now)

    def test_hdd_copy_has_return_steps_after_the_test(self):
        self.assertEqual(
            _keys(self.copy),
            [
                "hdd_arrived",
                "ingested",
                "tested",
                "returned",
                "return_confirmed",
            ],
        )

    def test_return_steps_do_not_hold_up_readiness(self):
        for key in ("hdd_arrived", "ingested", "tested"):
            self._step(key).complete(self.user, result=RESULT_OK)
        self.assertEqual(self.copy.readiness(), READY)
        self.assertIsNone(self.copy.next_step())
        self.assertEqual(
            [m.key for m in self.copy.return_steps()],
            ["returned", "return_confirmed"],
        )

    def test_nothing_due_while_a_showing_is_still_to_come(self):
        self._arrive()
        self._showing(-2)
        self._showing(3)
        self.assertEqual(self._rows(), [])

    def test_nothing_due_if_the_drive_never_arrived(self):
        self._showing(-5)
        self.assertEqual(self._rows(), [])

    def test_due_once_the_last_showing_has_gone(self):
        self._arrive()
        self._showing(-2)
        (row,) = self._rows()
        self.assertEqual(row["status"], "to_return")
        self.assertEqual(row["days_since"], 2)
        self.assertFalse(row["overdue"])

    def test_overdue_after_three_days(self):
        self._arrive()
        self._showing(-4)
        self.assertTrue(self._rows()[0]["overdue"])

    def test_cancelled_run_still_leaves_a_drive_to_send_back(self):
        self._arrive()
        self._showing(-3, cancelled=True)
        (row,) = self._rows()
        self.assertEqual(row["status"], "to_return")

    def test_only_this_films_showings_decide_when_it_is_due(self):
        """A drive for one date of a recurring event is due back after that
        date, not after the whole series has finished."""
        self._arrive()
        self._showing(-3)
        self._showing(20, linked=False)  # a later date, a different film
        (row,) = self._rows()
        self.assertEqual(row["status"], "to_return")
        self.assertEqual(row["title"], "Drive film")

    def test_sent_then_confirmed_leaves_the_list(self):
        self._arrive()
        self._showing(-5)
        self._step("returned").complete(self.user, notes="DPD 12345")
        (row,) = self._rows()
        self.assertEqual(row["status"], "sent")
        self.assertEqual(row["returned_step"].notes, "DPD 12345")
        self._step("return_confirmed").complete(self.user)
        self.assertEqual(self._rows(), [])

    def test_sent_drive_is_worth_chasing_after_two_weeks(self):
        self._arrive()
        self._showing(-30)
        self._step("returned").complete(self.user)
        self.assertFalse(self._rows()[0]["overdue"])
        FilmMilestone.objects.filter(pk=self._step("returned").pk).update(
            done_at=self.now - datetime.timedelta(days=15)
        )
        self.assertTrue(self._rows()[0]["overdue"])

    def test_discs_never_appear_in_returns(self):
        disc_event = Event.objects.create(name="Disc film")
        disc = _film(disc_event, showings=[])
        _copy(disc, FORMAT_DISC)
        past = Showing.objects.create(
            event=disc_event, start=self.now - datetime.timedelta(days=9)
        )
        disc.showings.add(past)
        self.assertEqual(self._rows(), [])

    def test_mark_sent_records_the_courier_reference(self):
        self._arrive()
        self._showing(-2)
        self.client.login(username="admin", password="T3stPassword!")
        step = self._step("returned")
        self.client.post(
            reverse("film-milestone-complete", args=[step.pk]),
            {"notes": "Courier X, ref 998"},
        )
        step.refresh_from_db()
        self.assertIsNotNone(step.done_at)
        self.assertEqual(step.notes, "Courier X, ref 998")

    def test_overview_shows_returns_to_everyone_and_buttons_only_to_updaters(
        self,
    ):
        self._arrive()
        self._showing(-4)
        self.client.login(username="no_perm", password="T3stPassword!2")
        resp = self.client.get(reverse("film-readiness-overview"))
        self.assertContains(resp, "Hard drives to send back")
        self.assertContains(resp, "Overdue")
        self.assertNotContains(resp, "Mark sent")
        self.client.logout()
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.get(reverse("film-readiness-overview"))
        self.assertContains(resp, "Mark sent")
        self.assertContains(resp, "Courier and tracking ref")

    def test_confirmed_return_stays_listed_then_drops_off(self):
        self._arrive()
        self._showing(-20)
        self._step("returned").complete(self.user)
        confirm = self._step("return_confirmed")
        confirm.complete(self.user)
        self.assertEqual(self._rows(), [])
        (row,) = returns_outstanding(self.now, include_closed=True)
        self.assertEqual(row["status"], "confirmed")
        confirm.done_at = self.now - datetime.timedelta(days=15)
        confirm.save()
        self.assertEqual(
            returns_outstanding(self.now, include_closed=True), []
        )

    def test_undo_steps_a_return_back_and_is_logged(self):
        self._arrive()
        self._showing(-2)
        self.client.login(username="admin", password="T3stPassword!")
        sent = self._step("returned")
        sent.complete(self.user, notes="Courier X")
        self._step("return_confirmed").complete(self.user)
        # Can't un-send while the confirmation stands.
        self.client.post(reverse("film-milestone-undo", args=[sent.pk]))
        sent.refresh_from_db()
        self.assertIsNotNone(sent.done_at)
        confirm = self._step("return_confirmed")
        self.client.post(reverse("film-milestone-undo", args=[confirm.pk]))
        self.client.post(reverse("film-milestone-undo", args=[sent.pk]))
        sent.refresh_from_db()
        self.assertIsNone(sent.done_at)
        self.assertEqual(sent.notes, "")
        (row,) = self._rows()
        self.assertEqual(row["status"], "to_return")
        log = EventAuditLog.objects.filter(
            event=self.event, action=EventAuditLog.ACTION_FILM_STEP_UNDONE
        ).first()
        self.assertIn("Courier X", log.detail)

    def test_unclaim_clears_the_claim_and_logs_who_had_it(self):
        self.client.login(username="admin", password="T3stPassword!")
        step = self._step("hdd_arrived")
        step.claim(self.user, planned_for=self.now.date())
        self.client.post(reverse("film-milestone-unclaim", args=[step.pk]))
        step.refresh_from_db()
        self.assertIsNone(step.claimed_by)
        self.assertIsNone(step.planned_for)
        log = EventAuditLog.objects.get(
            event=self.event, action=EventAuditLog.ACTION_FILM_UNCLAIMED
        )
        self.assertEqual(log.actor, self.user)
        self.assertIn("had been claimed by", log.detail)

    def test_undo_and_unclaim_refuse_get_and_anonymous(self):
        step = self._step("hdd_arrived")
        for name in ("film-milestone-undo", "film-milestone-unclaim"):
            url = reverse(name, args=[step.pk])
            self.assertEqual(self.client.post(url).status_code, 302)
            self.client.login(username="admin", password="T3stPassword!")
            self.assertEqual(self.client.get(url).status_code, 405)
            self.client.logout()
