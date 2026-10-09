# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Hire enquiries (9.175): an honest pipeline from enquiry to booking.

Spec: docs/tasks/hires.md. Settings live in the ``HireSettings`` singleton
(same pattern as ``InductionsSettings``); only the two ``perm_hire_*`` access
levels live on ``SiteConfiguration`` because ``feature_required`` reads them
from there.
"""

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.utils import timezone

from . import defaults


class HireSettings(models.Model):
    """Singleton (pk=1) of runtime-editable hire settings."""

    _CACHE_KEY = "hires_settings"

    enquiries_open = models.BooleanField(
        default=True,
        help_text=(
            "Open/closed switch. When closed, the form page shows the closed "
            "message instead. The honest answer when the collective is "
            "overwhelmed."
        ),
    )
    closed_message = models.TextField(
        blank=True, default=defaults.CLOSED_MESSAGE
    )
    how_we_work_text = models.TextField(
        blank=True, default=defaults.HOW_WE_WORK
    )
    tier_guidance_text = models.TextField(
        blank=True, default=defaults.TIER_GUIDANCE
    )
    acknowledgement_statements = models.TextField(
        blank=True,
        default=defaults.ACKNOWLEDGEMENTS,
        help_text="One statement per line. Hirers must tick every one.",
    )
    privacy_notice_text = models.TextField(
        blank=True, default=defaults.PRIVACY_NOTICE
    )
    privacy_contact = models.CharField(
        max_length=200,
        blank=True,
        help_text="Where privacy questions go (shown in the privacy notice).",
    )

    notification_addresses = models.TextField(
        blank=True,
        help_text=(
            "One email address per line. Receives the pre-meeting digest, "
            "last-call and maybe-callout emails."
        ),
    )

    booking_window_start = models.DateField(null=True, blank=True)
    booking_window_end = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Dates beyond this are still accepted but marked 'considered at "
            "season planning'."
        ),
    )

    min_duration_hours = models.PositiveIntegerField(default=3)
    default_setup_minutes = models.PositiveIntegerField(default=60)
    default_teardown_minutes = models.PositiveIntegerField(default=60)
    late_night_from = models.TimeField(default=datetime.time(23, 0))
    late_night_fee_gbp = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal("0")
    )
    late_night_security_cost_gbp = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0"),
        help_text="INTERNAL: never shown to hirers.",
    )
    door_staff_fee_gbp = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "What hirers are charged for the door staff we arrange for late "
            "club nights. Blank means 'an additional charge we'll confirm'."
        ),
    )
    late_night_licences_per_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "INTERNAL: how many late-night licences you have a year. Blank "
            "hides the counter shown to the meeting. Never shown to hirers."
        ),
    )
    late_night_notice_text = models.TextField(
        blank=True, default=defaults.LATE_NIGHT_NOTICE
    )
    door_staff_notice_text = models.TextField(
        blank=True, default=defaults.DOOR_STAFF_NOTICE
    )
    late_night_ack_statement = models.CharField(
        max_length=300, blank=True, default=defaults.LATE_NIGHT_ACK
    )

    min_notice_days_before_meeting = models.PositiveIntegerField(default=2)
    reply_grace_days = models.PositiveIntegerField(default=7)
    digest_days_before_meeting = models.PositiveIntegerField(default=5)
    warning_days = models.PositiveIntegerField(default=2)
    callout_days = models.PositiveIntegerField(default=14)
    fallback_reply_days = models.PositiveIntegerField(default=35)

    volunteer_event_net_cost_gbp = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("150"),
        help_text=(
            "Admin estimate of what one volunteer-programmed event costs the "
            "collective net. Used only to say 'about £300 ≈ 2 events'."
        ),
    )

    declined_purge_months = models.PositiveIntegerField(default=6)
    hirer_purge_years = models.PositiveIntegerField(default=3)

    class Meta:
        verbose_name = "Hire settings"
        verbose_name_plural = "Hire settings"

    def __str__(self):
        return "Hire settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self._CACHE_KEY)

    @classmethod
    def load(cls):
        cfg = cache.get(cls._CACHE_KEY)
        if cfg is None:
            cfg, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls._CACHE_KEY, cfg, timeout=300)
        return cfg

    def clean(self):
        try:
            self.notification_address_list(strict=True)
        except ValidationError:
            raise

    def notification_address_list(self, strict=False):
        """Return a validated list. Strict mode raises on a bad line.

        One address per line; a comma-joined line is rejected, because that
        is the vols_admin_address incident class (a list element holding
        several addresses silently breaks sending).
        """
        out = []
        for line in self.notification_addresses.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                if "," in line or ";" in line or " " in line:
                    raise ValidationError("one address per line")
                validate_email(line)
            except ValidationError:
                if strict:
                    raise ValidationError(
                        {
                            "notification_addresses": (
                                f"'{line}' is not a single valid address "
                                "(put one address on each line)."
                            )
                        }
                    )
                continue
            out.append(line)
        return out

    def acknowledgement_list(self):
        return [
            s.strip()
            for s in self.acknowledgement_statements.splitlines()
            if s.strip()
        ]


def get_hire_settings():
    return HireSettings.load()


def hires_enabled():
    """The master feature flag, kept on SiteConfiguration (site settings).

    Every public view, management view, nav link and scheduled job checks
    this. While off, the feature does not exist: URLs 404, the clock is
    paused, and the old Wagtail enquiry form keeps working unchanged.
    """
    from toolkit.diary.models import get_site_config

    return bool(get_site_config().hire_enquiries_enabled)


class HireEmailTemplate(models.Model):
    """Admin override of a default email (subject + body with {placeholders}).

    Absence of a row means the default from ``defaults.EMAIL_DEFAULTS``.
    """

    key = models.CharField(max_length=40, unique=True)
    subject = models.CharField(max_length=200)
    body = models.TextField()

    def __str__(self):
        return self.key


class Hirer(models.Model):
    name = models.CharField(max_length=200)
    organisation = models.CharField(max_length=200, blank=True)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.organisation or self.name


class HireType(models.Model):
    UNIT_CHOICES = [
        ("flat", "Flat"),
        ("hour", "Per hour"),
        ("block4", "Per 4-hour block"),
    ]
    name = models.CharField(max_length=100)
    community_fee_gbp = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal("0")
    )
    corporate_fee_gbp = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal("0")
    )
    unit = models.CharField(max_length=8, choices=UNIT_CHOICES, default="flat")
    vat_applies = models.BooleanField(default=False)
    min_duration_hours = models.PositiveIntegerField(
        null=True, blank=True, help_text="Blank = the site default."
    )
    needs_sound_tech = models.BooleanField(default=False)
    provides_door_staff = models.BooleanField(
        default=False,
        help_text=(
            "Door staff are required (and charged to the hirer) when this "
            "kind of hire runs late, e.g. club nights."
        ),
    )
    includes_late_night = models.BooleanField(
        default=False,
        help_text="Pricing already covers late finishes (no extra fee).",
    )
    public_description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def fee_for(self, tier):
        if tier == HireEnquiry.TIER_CORPORATE:
            return self.corporate_fee_gbp
        return self.community_fee_gbp


class ProgrammingMeeting(models.Model):
    KIND_CHOICES = [
        ("programming", "Programming"),
        ("development", "Programming development"),
        ("open_monday", "Open Monday"),
    ]
    date = models.DateField()
    kind = models.CharField(
        max_length=12, choices=KIND_CHOICES, default="programming"
    )
    notes = models.TextField(blank=True)
    cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.date:%-d %b %Y}"


class ApprovedTech(models.Model):
    """Freelance sound techs who know the building's gear (personal data)."""

    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    rate_text = models.CharField(max_length=200, blank=True)
    specialisms = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    share_with_hirers = models.BooleanField(default=False)
    consented_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Approved techs"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.share_with_hirers and not self.consented_at:
            self.consented_at = timezone.now()
        super().save(*args, **kwargs)


class HireEnquiry(models.Model):
    TIER_COMMUNITY = "community"
    TIER_CORPORATE = "corporate"
    TIER_CHOICES = [
        (TIER_COMMUNITY, "Community"),
        (TIER_CORPORATE, "Corporate"),
    ]

    SOUND_CHOICES = [
        ("approved", "Bringing an approved tech"),
        ("want_approved", "Would like an approved tech"),
        ("own", "Bringing their own tech"),
        ("none", "Not needed"),
        ("unsure", "Not sure"),
    ]

    # Statuses
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    TO_DISCUSS = "to_discuss"
    ACCEPTED = "accepted"
    AWAITING_AGREEMENT = "awaiting_agreement"
    BOOKED = "booked"
    COMPLETED = "completed"
    MAYBE = "maybe"
    DECLINED = "declined"
    DECLINED_CAPACITY = "declined_capacity"
    DECLINED_NO_SUPPORT = "declined_no_support"
    WITHDRAWN = "withdrawn"
    STATUS_CHOICES = [
        (SUBMITTED, "Submitted"),
        (ACKNOWLEDGED, "Acknowledged"),
        (TO_DISCUSS, "To discuss"),
        (ACCEPTED, "Accepted"),
        (AWAITING_AGREEMENT, "Awaiting hirer agreement"),
        (BOOKED, "Booked"),
        (COMPLETED, "Completed"),
        (MAYBE, "Maybe (looking for a coordinator)"),
        (DECLINED, "Declined"),
        (DECLINED_CAPACITY, "Declined (no capacity, timed out)"),
        (DECLINED_NO_SUPPORT, "Declined (no support found)"),
        (WITHDRAWN, "Withdrawn"),
    ]
    # States where the reply clock is running
    CLOCK_STATES = (ACKNOWLEDGED, TO_DISCUSS)
    OPEN_STATES = (
        SUBMITTED,
        ACKNOWLEDGED,
        TO_DISCUSS,
        MAYBE,
        ACCEPTED,
        AWAITING_AGREEMENT,
    )
    CLOSED_NEGATIVE = (
        DECLINED,
        DECLINED_CAPACITY,
        DECLINED_NO_SUPPORT,
        WITHDRAWN,
    )

    hirer = models.ForeignKey(
        Hirer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="enquiries",
    )
    # Contact as typed on this enquiry. Kept here (not only on Hirer) because
    # a Hirer link is a human decision, never automatic (spec: Hirer).
    contact_name = models.CharField(max_length=200)
    contact_organisation = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=40, blank=True)

    hire_type = models.ForeignKey(
        HireType, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    tier_requested = models.CharField(
        max_length=10, choices=TIER_CHOICES, default=TIER_COMMUNITY
    )
    tier_agreed = models.CharField(
        max_length=10, choices=TIER_CHOICES, blank=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    date_flexible = models.BooleanField(default=False)
    flexibility_notes = models.TextField(blank=True)
    sound_tech = models.CharField(
        max_length=14, choices=SOUND_CHOICES, default="unsure"
    )
    sound_tech_name = models.CharField(max_length=200, blank=True)
    rooms_requested = models.ManyToManyField(
        "diary.Room", blank=True, related_name="+"
    )
    expected_attendance = models.PositiveIntegerField(null=True, blank=True)
    media_url = models.URLField(blank=True)
    offers_to_volunteers = models.TextField(blank=True)
    acknowledgements = models.JSONField(default=list, blank=True)
    custom_answers = models.JSONField(default=list, blank=True)
    beyond_booking_window = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=SUBMITTED, db_index=True
    )
    status_changed_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(default=timezone.now)
    coordinator = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    meeting = models.ForeignKey(
        ProgrammingMeeting,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="enquiries",
    )
    reply_deadline = models.DateField(null=True, blank=True)
    warning_sent_at = models.DateTimeField(null=True, blank=True)
    digest_sent_at = models.DateTimeField(null=True, blank=True)
    callout_what_we_need = models.TextField(blank=True)
    callout_deadline = models.DateField(null=True, blank=True)
    callout_warning_sent_at = models.DateTimeField(null=True, blank=True)
    replied_outside_toolkit_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)

    # Second stage: asked only once we have said yes in principle.
    details_token = models.CharField(max_length=64, blank=True, db_index=True)
    details_requested_at = models.DateTimeField(null=True, blank=True)
    details_completed_at = models.DateTimeField(null=True, blank=True)

    agreement_token = models.CharField(
        max_length=64, blank=True, db_index=True
    )
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    terms_agreed_at = models.DateTimeField(null=True, blank=True)
    terms_agreed_snapshot = models.TextField(blank=True)
    terms_agreed_ip = models.GenericIPAddressField(null=True, blank=True)

    event = models.OneToOneField(
        "diary.Event",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hire_enquiry",
    )
    agreed_fee_gbp = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    door_staff_fee_gbp = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    estimated_income_gbp = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    personal_data_purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name_plural = "Hire enquiries"

    def __str__(self):
        return f"{self.title} ({self.contact_name})"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATES

    @property
    def tier(self):
        return self.tier_agreed or self.tier_requested

    def dates(self):
        return list(self.hire_dates.all())

    def door_staff_required(self):
        """Door staff are required (and charged) for late club nights only.

        Both must hold: the hire type is one we staff the door for (club
        nights), and at least one requested date finishes after the
        late-night time. Presented to the hirer as an expectation and an
        additional cost, not as a perk.
        """
        return bool(
            self.hire_type
            and self.hire_type.provides_door_staff
            and bool(self.late_dates())
        )

    @property
    def is_purged(self):
        return self.personal_data_purged_at is not None

    @property
    def keeps_financial_record(self):
        return self.status in (self.BOOKED, self.COMPLETED)

    def retention_reference_date(self):
        """The date the retention clock counts from, or None while open.

        Declined or withdrawn: when it was closed. Booked or completed:
        the later of the agreement and the end of the last booked date, so
        a hire is never purged before it has happened.
        """
        if self.status in self.CLOSED_NEGATIVE:
            return timezone.localtime(self.status_changed_at).date()
        if self.keeps_financial_record:
            ref = timezone.localtime(self.status_changed_at).date()
            if self.terms_agreed_at:
                ref = max(ref, timezone.localtime(self.terms_agreed_at).date())
            for d in self.hire_dates.all():
                ref = max(ref, timezone.localtime(d.end).date())
            return ref
        return None

    def purge_due_on(self, cfg=None):
        """When personal details will be deleted (approximate), or None."""
        cfg = cfg or get_hire_settings()
        ref = self.retention_reference_date()
        if ref is None:
            return None
        if self.keeps_financial_record:
            return ref + datetime.timedelta(
                days=int(cfg.hirer_purge_years * 365.25)
            )
        return ref + datetime.timedelta(
            days=int(cfg.declined_purge_months * 30.4375)
        )

    def charge_gbp(self, n_dates=None):
        """What the hirer is charged (pre-VAT), before door staff.

        Price-list fee for the agreed (else requested) tier, plus the
        late-night fee where it applies. This is the number a hirer is ever
        quoted: it never has our internal costs taken off.
        """
        if not self.hire_type:
            return Decimal("0")
        cfg = get_hire_settings()
        ds = self.dates()
        accepted = [d for d in ds if d.accepted]
        use = accepted or ds[:1]
        if n_dates is not None:
            use = ds[:n_dates]
        total = Decimal("0")
        fee = self.hire_type.fee_for(self.tier)
        for d in use:
            hours = Decimal(d.access_hours())
            if self.hire_type.unit == "hour":
                total += fee * hours
            elif self.hire_type.unit == "block4":
                blocks = max(
                    1,
                    int(
                        (hours / 4).to_integral_value(rounding="ROUND_CEILING")
                    ),
                )
                total += fee * blocks
            else:
                total += fee
            if d.is_late_night() and not self.hire_type.includes_late_night:
                total += cfg.late_night_fee_gbp
        return total

    def estimate_gbp(self, n_dates=None):
        """INTERNAL net income estimate: the charge minus late-night security.

        So a late finish shows what it actually nets (spec: Income). Never
        quoted to a hirer; see charge_gbp for that.
        """
        cfg = get_hire_settings()
        late = self.dates() if n_dates is None else self.dates()[:n_dates]
        accepted = [d for d in late if d.accepted]
        use = accepted or late[:1]
        security = sum(
            (
                cfg.late_night_security_cost_gbp
                for d in use
                if d.is_late_night()
            ),
            Decimal("0"),
        )
        return self.charge_gbp(n_dates) - security

    def _relevant_dates(self):
        """The accepted dates once any are accepted, else all requested.

        Keeps what the hirer is quoted (charge, late fee, door staff) and
        what we plan for computed over the same dates.
        """
        ds = self.dates()
        return [d for d in ds if d.accepted] or ds

    def late_dates(self):
        return [d for d in self._relevant_dates() if d.is_late_night()]


class HireDate(models.Model):
    """One candidate date, with the whole access window (get-in to get-out)."""

    enquiry = models.ForeignKey(
        HireEnquiry, on_delete=models.CASCADE, related_name="hire_dates"
    )
    get_in = models.DateTimeField()
    start = models.DateTimeField()
    end = models.DateTimeField()
    get_out = models.DateTimeField()
    accepted = models.BooleanField(default=False)

    class Meta:
        ordering = ["start"]

    def __str__(self):
        return f"{self.start:%a %-d %b %Y %H:%M}"

    def access_hours(self):
        return (self.get_out - self.get_in).total_seconds() / 3600

    def is_late_night(self):
        cutoff = get_hire_settings().late_night_from
        end_local = timezone.localtime(self.get_out)
        start_local = timezone.localtime(self.get_in)
        if end_local.date() > start_local.date():
            return True
        return end_local.time() > cutoff
