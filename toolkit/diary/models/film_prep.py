# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Film readiness: has the film arrived, is it in the booth, has anyone
test-played it, who said they would, and (for hired drives) has it gone back.

Task 9.174 (docs/tasks/events-and-rota.md). The unit is one *film*, not one
event or one showing:

- A one-off or a run of the same film: one FilmPrep linked to all its
  showings, so a test done once counts for every screening.
- Family Film Club, where each date shows a different film: one FilmPrep per
  showing.
- A double or triple bill: two or three FilmPreps linked to the same showing,
  each with its own title, copies, subtitles and backup. ``bill_position``
  gives the running order.

A FilmPrep only links to showings of its own event. A film that is an add-on
to something else (Community Kitchen) is programmed as an event of its own,
which also puts it on the public programme.

Three models:

- FilmPrep: one film, its checklist answers and the handover note.
- FilmCopy: one physical or digital copy of that film (main, backup).
- FilmMilestone: one step for one copy (arrived, ingested, tested...), with
  who claimed it, who did it, and when.

Which milestones a copy has depends on its format, and that mapping lives in
FORMAT_MILESTONES below rather than in the schema, so adding a format or a
step needs no migration.
"""

import datetime

from django.conf import settings
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone

# --- Format and milestone vocabulary -------------------------------------

FORMAT_DISC = "disc"
FORMAT_DCP_FILMVAULT = "dcp_filmvault"
FORMAT_DCP_HDD = "dcp_hdd"
FORMAT_MP4 = "mp4"
FORMAT_OTHER = "other"

FORMAT_CHOICES = [
    (FORMAT_DISC, "Disc (Blu-ray / DVD)"),
    (FORMAT_DCP_FILMVAULT, "DCP, delivered to FilmVault"),
    (FORMAT_DCP_HDD, "DCP, on a hard drive (CRU)"),
    (FORMAT_MP4, "MP4 / video file"),
    (FORMAT_OTHER, "Other (35mm, etc.)"),
]

TESTED = "tested"

# Ordered: the playback test is the last step that decides readiness. "other"
# only gets the test step, because we cannot say what arrival looks like.
FORMAT_MILESTONES = {
    FORMAT_DISC: ["in_building", "in_booth", TESTED],
    FORMAT_DCP_FILMVAULT: ["on_filmvault", "ingested", TESTED],
    FORMAT_DCP_HDD: [
        "hdd_arrived",
        "ingested",
        TESTED,
        "returned",
        "return_confirmed",
    ],
    FORMAT_MP4: ["in_building", TESTED],
    FORMAT_OTHER: [TESTED],
}

MILESTONE_LABELS = {
    "in_building": "In the building",
    "in_booth": "In the booth",
    "on_filmvault": "Arrived on FilmVault",
    "hdd_arrived": "Hard drive arrived",
    "ingested": "Ingested",
    TESTED: "Test-played",
    "returned": "Sent back by courier",
    "return_confirmed": "Return confirmed by distributor",
}

# Steps that happen after the last showing. They are not part of "is the
# film ready to screen": a tested drive still waiting to be posted back is
# ready, and is a separate problem (loads of drives about the place).
POST_SCREENING_KEYS = ("returned", "return_confirmed")
RETURNED = "returned"
RETURN_CONFIRMED = "return_confirmed"

# Readiness states, used for both a copy and a whole film.
NOT_STARTED = "not_started"
IN_PROGRESS = "in_progress"
READY = "ready"
PROBLEM = "problem"

# Days before the first showing at which an untested film becomes urgent, and
# how far ahead the dashboard looks. Guesses: promote to site config only if
# they prove wrong.
URGENT_DAYS = 3
LOOKAHEAD_DAYS = 7

# Return of hired hard drives, counted from the last showing. Guesses, like
# the urgency thresholds above.
RETURN_OVERDUE_DAYS = 3
RETURN_CHASE_DAYS = 14
# Confirmed returns stay listed this long, so a misclick can be undone.
RETURN_KEEP_DAYS = 14

# How far back a rota entry on a projectionist role still counts as "being a
# projectionist". Volunteers drift in and out of the booth, so this is a
# rolling window rather than a permanent flag on the person.
PROJECTIONIST_WINDOW_DAYS = 180

# Milestone.result values.
RESULT_OK = "ok"
RESULT_PROBLEM = "problem"


def user_display_name(user):
    """How to show a user on pages other volunteers can see: the volunteer's
    display name (9.170, first name and last initial by default), never the
    private member name. Falls back to the username for accounts with no
    volunteer record."""
    if user is None:
        return ""
    volunteer = getattr(user, "volunteer", None)
    if volunteer is not None:
        return volunteer.display_name_or_default
    return user.get_username()


class FilmPrep(models.Model):
    """One film we are running, and where it is up to.

    Linked to the showings it plays at (all of an event's showings for a
    normal run, one for a Family Film Club date, one of several for a bill).
    """

    SUBTITLES_UNKNOWN = "unknown"
    SUBTITLES_NONE = "none"
    SUBTITLES_BURNED_IN = "burned_in"
    SUBTITLES_SEPARATE = "separate"
    SUBTITLES_TO_SOURCE = "to_source"
    SUBTITLES_CHOICES = [
        (SUBTITLES_UNKNOWN, "Not checked yet"),
        (SUBTITLES_NONE, "Not needed (English audio)"),
        (SUBTITLES_BURNED_IN, "Needed, burned into the picture"),
        (
            SUBTITLES_SEPARATE,
            "Needed, separate file or track (check it loads)",
        ),
        (SUBTITLES_TO_SOURCE, "Needed, still to source"),
    ]

    event = models.ForeignKey(
        "diary.Event",
        on_delete=models.CASCADE,
        related_name="film_preps",
    )
    showings = models.ManyToManyField(
        "diary.Showing",
        related_name="film_preps",
        blank=True,
        help_text="The showings this film plays at. Must belong to the same event.",
    )
    film_title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Film title",
        help_text=(
            "Leave blank if the event is the film. Fill in for a double bill "
            "or a different film each night."
        ),
    )
    bill_position = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Running order",
        help_text="On a double or triple bill: 1 plays first, 2 second.",
    )
    subtitles = models.CharField(
        max_length=16,
        choices=SUBTITLES_CHOICES,
        default=SUBTITLES_UNKNOWN,
        verbose_name="Subtitles",
    )
    backup_in_place = models.BooleanField(
        default=False,
        verbose_name="Backup in place",
        help_text="Is there a second way to play the film if the main copy fails?",
    )
    backup_note = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="What and where is the backup?",
        help_text="e.g. 'disc in the booth', 'MP4 in the Films folder on the booth PC'.",
    )
    trailers_plan = models.TextField(
        blank=True,
        verbose_name="Trailers",
        help_text="Which trailers play before the film, and where they come from.",
    )
    booth_notes = models.TextField(
        blank=True,
        verbose_name="Booth notes",
        help_text="Anything odd about playback: aspect ratio, audio channels, menu quirks.",
    )
    handover_note = models.TextField(
        blank=True,
        verbose_name="Note for the projectionist",
        help_text=(
            "What someone else needs to know to run this film, in case the "
            "programmer is not there."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        db_table = "FilmPreps"
        ordering = ("bill_position", "id")

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.film_title or self.event.name

    def readiness(self):
        """Ready as soon as any copy is ready, so a working backup covers a
        broken main copy. Problem only when a copy has failed and none is
        ready."""
        states = [c.readiness() for c in self.copies.all()]
        if not states:
            return NOT_STARTED
        if READY in states:
            return READY
        if PROBLEM in states:
            return PROBLEM
        if IN_PROGRESS in states:
            return IN_PROGRESS
        return NOT_STARTED

    def next_showing_start(self, now=None):
        """Start of the next non-cancelled showing not yet begun, or None."""
        now = now or timezone.now()
        return (
            self.showings.filter(cancelled=False, start__gte=now)
            .order_by("start")
            .values_list("start", flat=True)
            .first()
        )

    def urgency(self, now=None):
        """'urgent', 'soon' or None, from days to the next showing. Only
        meaningful for films that are not ready: callers decide whether to
        show it."""
        now = now or timezone.now()
        return urgency_for(self.next_showing_start(now), now)


@receiver(m2m_changed, sender=FilmPrep.showings.through)
def _showings_must_share_the_event(
    sender, instance, action, reverse, pk_set, **kwargs  # noqa: ARG001
):
    """A film only links to showings of its own event. An add-on film (a
    film shown with Community Kitchen) is an event of its own instead."""
    if action != "pre_add" or not pk_set:
        return
    from toolkit.diary.models.showing import Showing

    if reverse:
        # instance is a Showing, pk_set holds FilmPrep pks.
        bad = FilmPrep.objects.filter(pk__in=pk_set).exclude(
            event_id=instance.event_id
        )
    else:
        bad = Showing.objects.filter(pk__in=pk_set).exclude(
            event_id=instance.event_id
        )
    if bad.exists():
        raise ValueError(
            "A film can only be linked to showings of its own event."
        )


class FilmCopy(models.Model):
    """One copy of a film: a disc, a DCP, a file."""

    film_prep = models.ForeignKey(
        FilmPrep,
        on_delete=models.CASCADE,
        related_name="copies",
    )
    label = models.CharField(
        max_length=64,
        default="Main copy",
        help_text="e.g. Main copy, Backup.",
    )
    format = models.CharField(max_length=16, choices=FORMAT_CHOICES)
    location_note = models.CharField(
        max_length=128,
        blank=True,
        help_text="Where it physically is, e.g. 'CRU bay 2', 'booth shelf' or 'Library, shelf D3'.",
    )

    class Meta:
        db_table = "FilmCopies"
        ordering = ("id",)

    def __str__(self):
        return "%s (%s)" % (self.label, self.get_format_display())

    def expected_keys(self):
        return FORMAT_MILESTONES.get(self.format, [TESTED])

    def sync_milestones(self):
        """Make the milestone rows match the format.

        Missing steps are created. Steps that no longer apply are removed
        only if nobody has done or claimed them, so changing a copy's format
        never silently discards someone's recorded work.
        """
        expected = self.expected_keys()
        existing = {m.key: m for m in self.milestones.all()}
        for key in expected:
            if key not in existing:
                FilmMilestone.objects.create(copy=self, key=key)
        for key, milestone in existing.items():
            if key not in expected and not (
                milestone.done_at or milestone.claimed_by_id
            ):
                milestone.delete()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_milestones()

    def ordered_milestones(self):
        """Milestones for the current format, in step order."""
        order = {key: i for i, key in enumerate(self.expected_keys())}
        return sorted(
            (m for m in self.milestones.all() if m.key in order),
            key=lambda m: order[m.key],
        )

    def pre_steps(self):
        """The steps that decide readiness: everything before the screening."""
        return [
            m
            for m in self.ordered_milestones()
            if m.key not in POST_SCREENING_KEYS
        ]

    def return_steps(self):
        """The steps after the last showing (drives sent back), if any."""
        return [
            m
            for m in self.ordered_milestones()
            if m.key in POST_SCREENING_KEYS
        ]

    def readiness(self):
        steps = self.pre_steps()
        if not steps:
            return NOT_STARTED
        test = next((m for m in steps if m.key == TESTED), None)
        if test and test.done_at and test.result == RESULT_PROBLEM:
            return PROBLEM
        if all(m.done_at for m in steps):
            return READY
        if any(m.done_at for m in steps):
            return IN_PROGRESS
        return NOT_STARTED

    def next_step(self):
        """First readiness step not yet done, or None."""
        return next((m for m in self.pre_steps() if not m.done_at), None)


class FilmMilestone(models.Model):
    """One step for one copy, with the who and when."""

    RESULT_CHOICES = [(RESULT_OK, "Fine"), (RESULT_PROBLEM, "Problem")]

    copy = models.ForeignKey(
        FilmCopy,
        on_delete=models.CASCADE,
        related_name="milestones",
    )
    key = models.CharField(max_length=32)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    result = models.CharField(
        max_length=8,
        choices=RESULT_CHOICES,
        blank=True,
        help_text="Used by the playback test: did it play properly?",
    )
    notes = models.CharField(max_length=256, blank=True)
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Someone who has said they will do this step.",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    planned_for = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "FilmMilestones"
        constraints = [
            models.UniqueConstraint(
                fields=["copy", "key"], name="unique_milestone_per_copy"
            )
        ]

    def __str__(self):
        return "%s: %s" % (self.copy, self.label)

    @property
    def label(self):
        return MILESTONE_LABELS.get(self.key, self.key)

    @property
    def claimed_by_name(self):
        return user_display_name(self.claimed_by)

    @property
    def done_by_name(self):
        return user_display_name(self.done_by)

    def claim(self, user, planned_for=None):
        self.claimed_by = user
        self.claimed_at = timezone.now()
        self.planned_for = planned_for
        self.save()

    def unclaim(self):
        self.claimed_by = None
        self.claimed_at = None
        self.planned_for = None
        self.save()

    def undo(self):
        """Step back: a misclick, or the step turned out not to be done."""
        self.done_at = None
        self.done_by = None
        self.result = ""
        self.notes = ""
        self.save()

    def complete(self, user, result="", notes=""):
        self.done_at = timezone.now()
        self.done_by = user
        self.result = result
        self.notes = notes
        self.save()


# --- Urgency -------------------------------------------------------------


def urgency_for(start, now):
    """'urgent', 'soon' or None for a showing starting at ``start``."""
    if start is None:
        return None
    if start - now <= datetime.timedelta(days=URGENT_DAYS):
        return "urgent"
    if start - now <= datetime.timedelta(days=LOOKAHEAD_DAYS):
        return "soon"
    return None


# --- Who may update film readiness ---------------------------------------


def user_is_projectionist(user, now=None):
    """True if the user's volunteer record holds (or recently held) a rota
    entry on a role flagged ``is_projectionist``."""
    from toolkit.diary.models.rota import RotaEntry

    volunteer = getattr(user, "volunteer", None)
    if volunteer is None:
        return False
    cutoff = (now or timezone.now()) - datetime.timedelta(
        days=PROJECTIONIST_WINDOW_DAYS
    )
    return RotaEntry.objects.filter(
        volunteer=volunteer,
        role__is_projectionist=True,
        showing__start__gte=cutoff,
    ).exists()


def user_can_update_film_prep(user):
    """Programmer+ (toolkit.write), or a volunteer who is a projectionist.

    A programmer who is also a projectionist takes the first branch, so
    they are never treated as two different people: one permission check,
    one set of dashboard cards (see index/views.py for the de-duplication).
    """
    if not user.is_authenticated:
        return False
    if user.has_perm("toolkit.write"):
        return True
    # Rota-only volunteers hold no toolkit permissions at all (the dashboard
    # asks only for a login), so being a projectionist is the whole test.
    return user_is_projectionist(user)


# --- Dashboard and overview rows ------------------------------------------


def upcoming_film_preps(now, days=None):
    """Films with a future, non-cancelled showing (within ``days`` if given),
    each carrying ``upcoming_showings`` (soonest first, with the films on
    each bill prefetched) and its copies and milestones, so callers cost a
    fixed number of queries however many films there are."""
    from django.db.models import Prefetch

    from toolkit.diary.models.showing import Showing

    showings = Showing.objects.filter(cancelled=False, start__gte=now)
    if days is not None:
        showings = showings.filter(
            start__lte=now + datetime.timedelta(days=days)
        )
    return (
        FilmPrep.objects.filter(showings__in=showings)
        .distinct()
        .select_related("event__programmer__member")
        .prefetch_related(
            Prefetch(
                "showings",
                queryset=showings.order_by("start").prefetch_related(
                    "film_preps__event"
                ),
                to_attr="upcoming_showings",
            ),
            "copies__milestones__claimed_by__volunteer__member",
            "copies__milestones__done_by__volunteer__member",
        )
    )


def film_row(prep, now):
    """One row for the dashboard or overview: status, urgency, the next
    missing step, the playback-test step someone could claim (least-claimed
    copy first), and which other films share its bill. Needs a prep from
    upcoming_film_preps."""
    copies = list(prep.copies.all())
    start = prep.upcoming_showings[0].start
    readiness = prep.readiness()
    tests = []
    if readiness != READY:
        tests = [
            m
            for c in copies
            for m in c.pre_steps()
            if m.key == TESTED and not m.done_at
        ]
    unclaimed = [m for m in tests if not m.claimed_by_id]
    companions = []
    for showing in prep.upcoming_showings:
        for other in showing.film_preps.all():
            if other.pk != prep.pk and other not in companions:
                companions.append(other)
    companions.sort(key=lambda p: (p.bill_position, p.pk))
    return {
        "prep": prep,
        "event": prep.event,
        "title": prep.display_title,
        "start": start,
        "showing_count": len(prep.upcoming_showings),
        "companions": companions,
        "readiness": readiness,
        "urgency": urgency_for(start, now),
        "has_copies": bool(copies),
        "copies": [
            {
                "copy": c,
                "steps": c.pre_steps(),
                "readiness": c.readiness(),
            }
            for c in copies
        ],
        "next_step": next(
            (s for s in (c.next_step() for c in copies) if s), None
        ),
        "test_step": (unclaimed or tests or [None])[0],
        "test_unclaimed": bool(tests) and len(unclaimed) == len(tests),
    }


def showings_without_film(now, days=None):
    """Upcoming showings of film events that have no film recorded yet: the
    prompt for a series like Family Film Club, where each date needs its own
    film. A film event is one tagged "film", linked to a Film record, or
    already carrying at least one FilmPrep."""
    from django.db.models import Q

    from toolkit.diary.models.showing import Showing

    showings = Showing.objects.filter(
        cancelled=False, start__gte=now, film_preps__isnull=True
    ).filter(
        Q(event__tags__slug="film")
        | Q(event__film__isnull=False)
        | Q(event__film_preps__isnull=False)
    )
    if days is not None:
        showings = showings.filter(
            start__lte=now + datetime.timedelta(days=days)
        )
    return (
        showings.distinct()
        .select_related("event__programmer__member")
        .order_by("start")
    )


# --- Returns: drives that need to go back after the screening -------------


def _return_row(copy, now, include_closed=False):
    """Return status for one copy, or None if nothing is outstanding.

    A copy is due back once its drive has arrived and the film has no future
    non-cancelled showing. The reference date is the last showing that went
    ahead (or, if every showing was cancelled, the last one booked), so a
    cancelled screening still leaves a drive to send back.
    """
    steps = {m.key: m for m in copy.milestones.all()}
    if RETURNED not in steps or steps.get("hdd_arrived") is None:
        return None
    if not steps["hdd_arrived"].done_at:
        return None
    confirmed = steps.get(RETURN_CONFIRMED)
    closed = confirmed is not None and confirmed.done_at
    if closed and (
        not include_closed
        or (now - confirmed.done_at).days >= RETURN_KEEP_DAYS
    ):
        return None
    showings = list(copy.film_prep.showings.all())
    if any(s.start >= now and not s.cancelled for s in showings):
        return None
    went_ahead = [s.start for s in showings if not s.cancelled]
    reference = max(went_ahead or [s.start for s in showings], default=None)
    if reference is None:
        return None
    sent = steps[RETURNED]
    days = max((now - reference).days, 0)
    if closed:
        status = "confirmed"
        overdue = False
    elif not sent.done_at:
        status = "to_return"
        overdue = days >= RETURN_OVERDUE_DAYS
    else:
        status = "sent"
        overdue = (now - sent.done_at).days >= RETURN_CHASE_DAYS
    return {
        "copy": copy,
        "prep": copy.film_prep,
        "event": copy.film_prep.event,
        "title": copy.film_prep.display_title,
        "last_showing": reference,
        "days_since": days,
        "status": status,
        "overdue": overdue,
        "returned_step": sent,
        "confirm_step": confirmed,
    }


def returns_outstanding(now=None, include_closed=False):
    """Drives to post back or awaiting the distributor's confirmation, the
    ones to post first (most overdue), then the ones awaiting confirmation.
    With ``include_closed``, also drives confirmed within the last
    RETURN_KEEP_DAYS, last, so a misclicked confirmation can be undone."""
    now = now or timezone.now()
    copies = (
        FilmCopy.objects.filter(format=FORMAT_DCP_HDD)
        .select_related("film_prep__event")
        .prefetch_related(
            "milestones__claimed_by__volunteer__member",
            "milestones__done_by__volunteer__member",
            "film_prep__showings",
        )
    )
    rows = [
        r for r in (_return_row(c, now, include_closed) for c in copies) if r
    ]
    order = {"to_return": 0, "sent": 1, "confirmed": 2}
    rows.sort(key=lambda r: (order[r["status"]], -r["days_since"]))
    return rows
