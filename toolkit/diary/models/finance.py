# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Event settlement records: per-showing attendance/income actuals, plus the
event-level distributor-payment outcome.

Task 9.171 (docs/tasks/finance.md). Deliberately separate models rather than
new fields on Showing/Event, for two reasons:

1. Showing.save() refuses to persist a past showing at all (see showing.py)
   -- and settlement data is by definition entered *after* a showing has
   happened. Fields on Showing itself would be unsaveable the moment they
   were needed. A related model with its own save() sidesteps the guard
   entirely.
2. The scoping/user-stories pass (docs/EVENT_SETTLEMENT_SCOPING.md,
   docs/EVENT_SETTLEMENT_USER_STORIES.md) is explicit that this is a
   different shape of data to the 9.54 deal-terms/9.149 budget-line fields
   it sits alongside, not a replacement for them.

Ticket sales are free-text line items with a *never-required* category tag
(the core resolution of the Persona A vs Persona B conflict in the
user-stories doc) -- see SettlementLineItem.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models


class ShowingSettlement(models.Model):
    """Actuals for one Showing: attendance, bar contribution, notes.

    Ticket-sales income lives in the related SettlementLineItem rows, not
    here, so the free-text line items can be edited independently of the
    single-value fields.
    """

    showing = models.OneToOneField(
        "diary.Showing",
        on_delete=models.CASCADE,
        related_name="settlement",
    )
    attendance = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Attendance",
        help_text="A rough headcount is fine.",
    )
    bar_contribution_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Bar/café contribution (£)",
        help_text=(
            "Optional. Often filled in later by whoever has till access."
        ),
    )
    notes = models.TextField(
        max_length=2048,
        blank=True,
        verbose_name="Notes",
        help_text="Exceptions Finance needs to know about, e.g. a private hire or charity split.",
    )
    nothing_to_report = models.BooleanField(
        default=False,
        help_text=(
            "Nothing to log for this showing. Set in bulk from the event hub "
            "for recurring showings, so no zero-value line item skews the "
            "ticket-income totals or PRS/PPL report. A free showing can "
            "still have a headcount."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Whoever last saved this record.",
    )

    class Meta:
        db_table = "ShowingSettlements"

    def __str__(self):
        return f"Settlement for showing {self.showing_id}"

    def has_any_data(self):
        return (
            self.attendance is not None
            or self.bar_contribution_gbp is not None
            or bool(self.notes.strip())
            or self.line_items.exists()
            or self.nothing_to_report
        )

    def ticket_income_total(self):
        total = Decimal("0")
        for item in self.line_items.all():
            total += item.line_total()
        return total


class SettlementLineItem(models.Model):
    """One free-text ticket-sales row.

    No fixed price-band schema -- deliberately, per the scoping doc's
    Evidence A (six real paper forms, six different breakdowns). category
    is an optional aggregation aid for Finance, never a requirement: a row
    entered on the night with no category is still useful data.
    """

    CATEGORY_ADVANCE = "advance"
    CATEGORY_DOOR = "door"
    CATEGORY_CONCESSION = "concession"
    CATEGORY_GUEST_LIST = "guest_list"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        ("", "— no category —"),
        ("advance", "Advance"),
        ("door", "Door"),
        ("concession", "Concession"),
        ("guest_list", "Guest list"),
        ("other", "Other"),
    ]

    settlement = models.ForeignKey(
        ShowingSettlement,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    description = models.CharField(
        max_length=128,
        help_text="Free text, e.g. '40 advance online'.",
    )
    category = models.CharField(
        max_length=16,
        choices=CATEGORY_CHOICES,
        blank=True,
        default="",
    )
    count = models.PositiveIntegerField(default=1)
    unit_price_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Unit price (£)",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "SettlementLineItems"
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.description} ({self.settlement_id})"

    def line_total(self):
        if self.unit_price_gbp is None:
            return Decimal("0")
        return self.unit_price_gbp * self.count


class SettlementRevision(models.Model):
    """Snapshot of a ShowingSettlement immediately before a correction.

    Task 9.171's "revision history on corrections" ask, following the
    EventTermsRevision precedent (toolkit/diary/models/event.py) rather than
    inventing a third audit pattern -- one row per save that actually changes
    something, holding the *prior* values. Unlike EventTermsRevision this
    isn't wired via a pre_save signal: the scalar fields on ShowingSettlement
    only tell half the story, since line items are a separate formset that
    saves after the parent row does, so the "before" state (scalars + line
    items together) is captured explicitly in
    edit_views/finance.py:showing_settlement_edit, the one place that sees
    both the old and new state before either is written.

    No revision is recorded for the *first* time a settlement gets data --
    only for a save that overwrites something already there, matching
    Persona B's "correct without destroying the original" requirement; a
    first-pass entry has nothing before it worth keeping.
    """

    settlement = models.ForeignKey(
        ShowingSettlement, on_delete=models.CASCADE, related_name="revisions"
    )
    saved_at = models.DateTimeField(auto_now_add=True)
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # Snapshot of ShowingSettlement's own fields immediately before this save
    attendance = models.PositiveIntegerField(null=True, blank=True)
    bar_contribution_gbp = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    # Snapshot of the line items immediately before this save, since they
    # can't be reconstructed from the (mutated) live SettlementLineItem rows
    # afterwards -- a list of {description, category, count, unit_price_gbp}.
    line_items_snapshot = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-saved_at"]

    def __str__(self):
        return (
            f"Revision of settlement {self.settlement_id} at {self.saved_at}"
        )


class PerformerRegistration(models.Model):
    """PRS/PPL performer-registration record for one Event (task 9.171).

    Deliberately optional and never a blocker on the settlement critical
    path -- docs/tasks/finance.md's "deliberately open" decision, resolved
    2026-09-12: PRS/PPL reporting has already stalled on paper (see the
    scoping doc's Evidence B), so a mandatory structured field here would
    just move the same compliance gap into an equally skippable digital
    one. This exists so whoever *does* want to keep it running -- the
    volunteer who expressed interest in Evidence B -- has somewhere to put
    it, and so prs_report() (edit_views/finance.py) has something to draw
    on.

    One row per Event, not per Showing, matching the paper form: the
    scoping doc's six real examples were all recorded once per event
    regardless of how many showings it covered.
    """

    event = models.OneToOneField(
        "diary.Event",
        on_delete=models.CASCADE,
        related_name="performer_registration",
    )
    filled_in_by = models.CharField(
        max_length=128,
        blank=True,
        help_text=(
            "Who filled this in: the programmer, an outside hirer or "
            "whoever reconciled it later."
        ),
    )
    vat_on_tickets = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="VAT charged on tickets?",
        help_text="Mainly for outside hires. Leave blank if unknown or not applicable.",
    )
    notes = models.TextField(max_length=2048, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        db_table = "PerformerRegistrations"

    def __str__(self):
        return f"Performer registration for event {self.event_id}"

    def has_any_data(self):
        return (
            bool(self.filled_in_by.strip())
            or self.vat_on_tickets is not None
            or bool(self.notes.strip())
            or self.performers.exists()
        )


class PRSPerformerEntry(models.Model):
    """One performer/artist line on a PerformerRegistration (task 9.171).

    registered is a tri-state choice rather than a nullable boolean --
    "don't know" was a real, common answer in the scoping doc's six real
    paper examples, not an edge case a yes/no checkbox can represent
    honestly.
    """

    REGISTERED_YES = "yes"
    REGISTERED_NO = "no"
    REGISTERED_UNKNOWN = "unknown"
    REGISTERED_CHOICES = [
        (REGISTERED_UNKNOWN, "Don't know"),
        (REGISTERED_YES, "Registered"),
        (REGISTERED_NO, "Not registered"),
    ]

    registration = models.ForeignKey(
        PerformerRegistration,
        on_delete=models.CASCADE,
        related_name="performers",
    )
    name = models.CharField(max_length=128)
    registered = models.CharField(
        max_length=16,
        choices=REGISTERED_CHOICES,
        default=REGISTERED_UNKNOWN,
    )
    is_volunteer_or_amateur = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Volunteer/amateur performer?",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "PRSPerformerEntries"
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.name} ({self.registration_id})"
