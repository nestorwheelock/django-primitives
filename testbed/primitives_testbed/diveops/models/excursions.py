"""Excursion-related models for dive operations.

This module provides models for dive excursions and related scheduling:
- ExcursionRequirement: Requirements for joining an excursion
- Trip: Commercial dive trip package (multi-day itinerary)
- Excursion: Operational dive excursion (single calendar day)
- Dive: Atomic dive within an excursion
- ExcursionType: Template for bookable excursion products
- DiveSegmentType: Configurable dive profile segment types
- ExcursionTypeDive: Template for dives within an excursion type
- RecurrenceRule: RRULE-based recurrence pattern
- RecurrenceException: Exception to recurrence pattern
- ExcursionSeries: Template for recurring excursions
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from django_basemodels import BaseModel


class ExcursionRequirement(BaseModel):
    """Requirements for joining an excursion.

    Supports multiple requirement types (certification, medical, gear, experience).
    Applied at the excursion level for operational validation.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    REQUIREMENT_TYPES = [
        ("certification", "Certification Level"),
        ("medical", "Medical Clearance"),
        ("gear", "Equipment/Gear"),
        ("experience", "Dive Experience"),
    ]

    excursion = models.ForeignKey(
        "diveops.Excursion",
        on_delete=models.CASCADE,
        related_name="requirements",
    )
    requirement_type = models.CharField(
        max_length=20,
        choices=REQUIREMENT_TYPES,
    )

    # For certification requirements
    certification_level = models.ForeignKey(
        "diveops.CertificationLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trip_requirements",
    )

    # For experience requirements
    min_dives = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Minimum number of logged dives",
    )

    description = models.TextField(blank=True)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # Only one requirement of each type per excursion (among active records)
            models.UniqueConstraint(
                fields=["excursion", "requirement_type"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_requirement_type_per_excursion",
            ),
        ]
        ordering = ["requirement_type"]

    def __str__(self):
        if self.certification_level:
            return f"{self.excursion}: {self.certification_level.name} required"
        return f"{self.excursion}: {self.get_requirement_type_display()}"

    def clean(self):
        """Validate that certification requirements have a certification_level."""
        if self.requirement_type == "certification" and not self.certification_level:
            raise ValidationError({
                "certification_level": "Certification level is required for certification requirements."
            })


# Backwards compatibility alias


class Trip(BaseModel):
    """A commercial dive trip package (itinerary).

    Trip is the commercial/sales wrapper that may span multiple days
    and contains one or more Excursions. Trips are what customers book
    and pay for; Excursions are the operational fulfillment.

    Trips can be linked to CatalogItem for commerce integration.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    # Identity
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Ownership
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="trip_packages",
    )

    # Schedule (date range for multi-day trips)
    start_date = models.DateField()
    end_date = models.DateField()

    # Commerce linkage
    catalog_item = models.ForeignKey(
        "django_catalog.CatalogItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_packages",
        help_text="Catalog item representing this trip package",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trip_packages_created",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=models.F("start_date")),
                name="diveops_trip_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["start_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["dive_shop", "status"]),
        ]
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

    @property
    def duration_days(self) -> int:
        """Return number of days in the trip."""
        return (self.end_date - self.start_date).days + 1


class Excursion(BaseModel):
    """An operational dive excursion (single calendar day).

    Excursion is the operational fulfillment unit - a single-day outing
    containing one or more Dives. Excursions can be standalone (walk-ins)
    or part of a Trip package.

    This replaces the former DiveTrip model with correct semantics.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("boarding", "Boarding"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    # Relationships
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="excursions",
    )
    dive_site = models.ForeignKey(
        "diveops.DiveSite",
        on_delete=models.PROTECT,
        related_name="excursions",
        null=True,
        blank=True,
        help_text="Primary dive site (optional - sites can be set per dive)",
    )

    # Optional link to Trip package (null = standalone/walk-in)
    trip = models.ForeignKey(
        "diveops.Trip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="excursions",
        help_text="Trip package this excursion belongs to (null = standalone)",
    )

    # Optional link to ExcursionSeries (for recurring excursions)
    series = models.ForeignKey(
        "diveops.ExcursionSeries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="excursions",
        help_text="Series this excursion was generated from (null = standalone)",
    )
    occurrence_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Original occurrence datetime from RRULE (stable identity)",
    )
    is_override = models.BooleanField(
        default=False,
        help_text="True if this excursion was individually modified",
    )
    override_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Which fields were overridden: {'capacity': true, 'price': true}",
    )

    # Optional link to ExcursionType (product template)
    excursion_type = models.ForeignKey(
        "diveops.ExcursionType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="excursions",
        help_text="Product type template (for pricing and eligibility)",
    )

    # Optional encounter for workflow tracking
    encounter = models.OneToOneField(
        "django_encounters.Encounter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="excursion",
    )

    # Schedule (must be same calendar day)
    departure_time = models.DateTimeField()
    return_time = models.DateTimeField()

    # Capacity
    max_divers = models.PositiveIntegerField()

    # Pricing (for standalone excursions)
    price_per_diver = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="excursions_created",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(return_time__gt=models.F("departure_time")),
                name="diveops_excursion_return_after_departure",
            ),
            models.CheckConstraint(
                condition=Q(max_divers__gt=0),
                name="diveops_excursion_max_divers_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(price_per_diver__gte=0),
                name="diveops_excursion_price_gte_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["departure_time"]),
            models.Index(fields=["status"]),
            models.Index(fields=["dive_shop", "status"]),
        ]
        ordering = ["-departure_time"]

    def __str__(self):
        site_name = self.dive_site.name if self.dive_site else self.site_names or "No site"
        return f"{site_name} - {self.departure_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def site_names(self) -> str:
        """Return comma-separated list of dive site names.

        Prefers dive site names from child dives, falls back to
        the excursion's dive_site if no dives exist.
        """
        sites = list(self.dives.values_list("dive_site__name", flat=True).distinct())
        if sites:
            return ", ".join(sites)
        if self.dive_site:
            return self.dive_site.name
        return ""

    @property
    def dive_sites(self):
        """Return queryset of all dive sites for this excursion's dives."""
        from .sites import DiveSite
        return DiveSite.objects.filter(dives__excursion=self).distinct()

    def clean(self):
        """Validate that departure and return are on the same calendar day."""
        super().clean()
        if self.departure_time and self.return_time:
            dep_date = self.departure_time.date()
            ret_date = self.return_time.date()
            if dep_date != ret_date:
                raise ValidationError(
                    "Excursion departure and return must be on the same calendar day. "
                    f"Departure: {dep_date}, Return: {ret_date}"
                )

    @property
    def spots_available(self) -> int:
        """Return number of available spots (excluding cancelled bookings)."""
        confirmed_count = self.bookings.filter(
            status__in=["confirmed", "checked_in"]
        ).count()
        return max(0, self.max_divers - confirmed_count)

    @property
    def is_full(self) -> bool:
        """Check if excursion is at capacity."""
        return self.spots_available == 0


# Backwards compatibility alias


class Dive(BaseModel):
    """An atomic dive within an excursion.

    Dive is the loggable unit of underwater activity. Each excursion
    contains one or more dives (e.g., morning dive, afternoon dive).

    This is the authoritative operational record entered by staff/guide.
    Contains both planned and actual dive metrics plus environmental conditions.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class SurfaceConditions(models.TextChoices):
        CALM = "calm", "Calm"
        SLIGHT = "slight", "Slight"
        MODERATE = "moderate", "Moderate"
        ROUGH = "rough", "Rough"

    class Current(models.TextChoices):
        NONE = "none", "None"
        MILD = "mild", "Mild"
        MODERATE = "moderate", "Moderate"
        STRONG = "strong", "Strong"

    # Core relationship
    excursion = models.ForeignKey(
        "diveops.Excursion",
        on_delete=models.CASCADE,
        related_name="dives",
    )

    # Dive site (may differ from excursion's site for multi-site excursions)
    dive_site = models.ForeignKey(
        "diveops.DiveSite",
        on_delete=models.PROTECT,
        related_name="dives",
    )

    # Sequence within excursion (1st dive, 2nd dive, etc.)
    sequence = models.PositiveSmallIntegerField(
        help_text="Dive number within the excursion (1, 2, 3...)",
    )

    # Planned timing
    planned_start = models.DateTimeField()
    planned_duration_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Planned dive duration in minutes",
    )

    # Actual timing (logged after dive)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)

    # Dive metrics (logged after dive)
    max_depth_meters = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Maximum depth reached in meters",
    )
    bottom_time_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Total bottom time in minutes",
    )

    # Environmental conditions (logged after dive)
    visibility_meters = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Underwater visibility in meters",
    )
    water_temp_celsius = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Water temperature in Celsius",
    )
    surface_conditions = models.CharField(
        max_length=10,
        choices=SurfaceConditions.choices,
        blank=True,
        default="",
        help_text="Surface water conditions",
    )
    current = models.CharField(
        max_length=10,
        choices=Current.choices,
        blank=True,
        default="",
        help_text="Current strength during dive",
    )

    # Notes
    notes = models.TextField(blank=True)

    # Logging audit (who logged the dive results)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dives_logged",
        help_text="Staff member who logged the dive results",
    )
    logged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the dive results were logged",
    )

    # ─────────────────────────────────────────────────────────────
    # Plan Snapshot (Dive Plan Extension)
    # ─────────────────────────────────────────────────────────────

    plan_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Frozen copy of plan at time of briefing lock",
    )

    plan_locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the plan was locked (briefing sent)",
    )

    plan_locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Staff member who locked the plan",
    )

    # ─────────────────────────────────────────────────────────────
    # Plan Provenance (tracks where snapshot came from)
    # ─────────────────────────────────────────────────────────────

    plan_template_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of ExcursionTypeDive template used for snapshot",
    )

    plan_template_published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the source template was published",
    )

    # ─────────────────────────────────────────────────────────────
    # Snapshot Status
    # ─────────────────────────────────────────────────────────────

    plan_snapshot_outdated = models.BooleanField(
        default=False,
        help_text="True if planned fields changed after lock (needs resend)",
    )

    class Meta:
        constraints = [
            # Unique sequence per excursion
            models.UniqueConstraint(
                fields=["excursion", "sequence"],
                name="diveops_dive_unique_sequence",
            ),
            # Sequence must be positive
            models.CheckConstraint(
                condition=Q(sequence__gt=0),
                name="diveops_dive_sequence_gt_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["excursion", "sequence"]),
            models.Index(fields=["logged_at"]),
            models.Index(fields=["plan_locked_at"]),
        ]
        ordering = ["excursion", "sequence"]

    def __str__(self):
        return f"Dive {self.sequence} - {self.excursion}"

    @property
    def duration_minutes(self) -> int | None:
        """Return actual dive duration if logged."""
        if self.actual_start and self.actual_end:
            delta = self.actual_end - self.actual_start
            return int(delta.total_seconds() / 60)
        return None

    @property
    def is_logged(self) -> bool:
        """Check if dive results have been logged."""
        return self.logged_at is not None

    @property
    def is_plan_locked(self) -> bool:
        """Check if dive plan has been locked."""
        return self.plan_locked_at is not None


class ExcursionType(BaseModel):
    """Template for a bookable excursion product.

    Thin overlay model defining standardized excursion offerings that customers
    can browse and book. Includes dive characteristics, eligibility requirements,
    and base pricing.

    Pricing note: base_price is the starting point. Final price is computed by
    ExcursionTypePricingService which adds site-specific adjustments (distance,
    park fees, night surcharges, etc.).

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class DiveMode(models.TextChoices):
        BOAT = "boat", "Boat Dive"
        SHORE = "shore", "Shore Dive"
        CENOTE = "cenote", "Cenote Dive"
        CAVERN = "cavern", "Cavern/Cave Dive"

    class TimeOfDay(models.TextChoices):
        DAY = "day", "Day Dive"
        NIGHT = "night", "Night Dive"
        DAWN = "dawn", "Dawn Dive"
        DUSK = "dusk", "Dusk Dive"

    # Identity
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    # Dive characteristics
    dive_mode = models.CharField(
        max_length=10,
        choices=DiveMode.choices,
    )
    time_of_day = models.CharField(
        max_length=10,
        choices=TimeOfDay.choices,
        default=TimeOfDay.DAY,
    )
    typical_duration_minutes = models.PositiveIntegerField(default=60)
    dives_per_excursion = models.PositiveSmallIntegerField(default=2)

    # Eligibility
    min_certification_level = models.ForeignKey(
        "diveops.CertificationLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="excursion_types",
        help_text="Minimum certification required (null = no requirement)",
    )
    requires_cert = models.BooleanField(
        default=True,
        help_text="If False, no certification check (for DSD)",
    )
    is_training = models.BooleanField(
        default=False,
        help_text="If True, this is a training/intro dive (DSD)",
    )

    # Site constraints
    suitable_sites = models.ManyToManyField(
        "diveops.DiveSite",
        blank=True,
        related_name="excursion_types",
        help_text="Sites where this type can be run (empty = all sites)",
    )

    # Base pricing
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Base price before site adjustments",
    )
    currency = models.CharField(max_length=3, default="USD")

    # Commerce linkage - auto-created when excursion type is created
    catalog_item = models.ForeignKey(
        "django_catalog.CatalogItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="excursion_types",
        help_text="Catalog item representing this excursion type product",
    )

    # Status
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(base_price__gte=0),
                name="diveops_excursion_type_base_price_gte_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["dive_mode"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_dive_mode_display()})"

    @property
    def max_depth_meters(self) -> int | None:
        """Calculate max depth from dive templates.

        Returns the maximum planned_depth_meters across all dive templates,
        or None if no templates have depth specified.
        """
        max_depth = self.dive_templates.aggregate(
            max_depth=models.Max("planned_depth_meters")
        )["max_depth"]
        return max_depth


# =============================================================================
# Recurring Excursion Models
# =============================================================================


class RecurrenceRule(BaseModel):
    """RRULE-based recurrence pattern for scheduling.

    Stores an iCalendar RRULE string and provides occurrence generation using
    python-dateutil. Can be linked to ExcursionSeries or other recurring patterns.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    rrule_text = models.CharField(
        max_length=500,
        help_text="RFC 5545 RRULE string (e.g., 'FREQ=WEEKLY;BYDAY=SA;BYHOUR=8')",
    )
    dtstart = models.DateTimeField(
        help_text="Series start date/time (anchor for RRULE calculation)",
    )
    dtend = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional series end date (no occurrences after this)",
    )
    timezone = models.CharField(
        max_length=50,
        default="America/Cancun",
        help_text="IANA timezone for occurrence calculation",
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Human-readable description (e.g., 'Every Saturday at 8am')",
    )

    class Meta:
        indexes = [
            models.Index(fields=["dtstart"]),
        ]

    def __str__(self):
        return self.description or self.rrule_text[:50]

    def get_occurrences(self, start_dt, end_dt):
        """Generate occurrences between start_dt and end_dt.

        Uses python-dateutil's rrulestr parser. Respects dtend if set.

        Args:
            start_dt: Start of query window (inclusive)
            end_dt: End of query window (inclusive)

        Returns:
            List of datetime objects for each occurrence
        """
        from dateutil.rrule import rrulestr

        # Parse the RRULE with dtstart
        rule = rrulestr(self.rrule_text, dtstart=self.dtstart)

        # Respect dtend if set
        effective_end = end_dt
        if self.dtend and self.dtend < end_dt:
            effective_end = self.dtend

        # Get occurrences in range
        occurrences = list(rule.between(start_dt, effective_end, inc=True))
        return occurrences


class RecurrenceException(BaseModel):
    """Exception to a recurrence pattern (cancel, reschedule, add).

    Used to modify individual occurrences without changing the overall pattern.
    Each exception targets a specific original occurrence by its start time.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    class ExceptionType(models.TextChoices):
        CANCELLED = "cancelled", "Cancelled"
        RESCHEDULED = "rescheduled", "Rescheduled"
        ADDED = "added", "Added (extra)"

    rule = models.ForeignKey(
        "diveops.RecurrenceRule",
        on_delete=models.CASCADE,
        related_name="exceptions",
        help_text="The recurrence rule this exception modifies",
    )
    original_start = models.DateTimeField(
        help_text="The occurrence being modified (its original start time)",
    )
    exception_type = models.CharField(
        max_length=20,
        choices=ExceptionType.choices,
        help_text="Type of exception",
    )
    new_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="New start time (for rescheduled exceptions)",
    )
    reason = models.TextField(
        blank=True,
        help_text="Reason for the exception (e.g., 'Weather conditions')",
    )

    class Meta:
        constraints = [
            # One exception per occurrence
            models.UniqueConstraint(
                fields=["rule", "original_start"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_recurrence_exception",
            ),
        ]
        indexes = [
            models.Index(fields=["rule", "original_start"]),
        ]

    def __str__(self):
        return f"{self.get_exception_type_display()}: {self.original_start}"


class ExcursionSeries(BaseModel):
    """Template for generating recurring excursions.

    Links a recurrence pattern with excursion defaults. The sync service
    generates concrete Excursion instances in a rolling window.

    Edit behaviors:
    - "This occurrence only": Edit the Excursion, mark is_override=True
    - "All occurrences": Edit the series template, re-sync unbooked future
    - "This and future": Split the series at cutoff date

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        RETIRED = "retired", "Retired"

    # Core identity
    name = models.CharField(
        max_length=200,
        help_text="Series name (e.g., 'Saturday Morning 2-Tank')",
    )
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.CASCADE,
        related_name="excursion_series",
    )

    # Recurrence pattern (one-to-one with rule)
    recurrence_rule = models.OneToOneField(
        "diveops.RecurrenceRule",
        on_delete=models.CASCADE,
        related_name="excursion_series",
    )

    # Template linkage
    excursion_type = models.ForeignKey(
        "diveops.ExcursionType",
        on_delete=models.PROTECT,
        related_name="series",
        help_text="Product type template for generated excursions",
    )
    dive_site = models.ForeignKey(
        "diveops.DiveSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="series",
        help_text="Default dive site (can be overridden per occurrence)",
    )

    # Defaults for generated excursions
    duration_minutes = models.PositiveIntegerField(
        default=240,
        help_text="Default excursion duration (4 hours default)",
    )
    capacity_default = models.PositiveIntegerField(
        default=12,
        help_text="Default max divers per occurrence",
    )
    price_default = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Default price (null = use excursion_type base_price)",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
    )
    meeting_place = models.TextField(
        blank=True,
        help_text="Default meeting location",
    )
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this series",
    )

    # Generation control
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    window_days = models.PositiveIntegerField(
        default=60,
        help_text="Generate occurrences this many days ahead",
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When occurrences were last synchronized",
    )

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="excursion_series_created",
    )

    class Meta:
        verbose_name_plural = "Excursion series"
        indexes = [
            models.Index(fields=["dive_shop", "status"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class DiveSegmentType(BaseModel):
    """Configurable dive profile segment types.

    Defines the types of segments that can be used in dive profiles
    (e.g., descent, level, safety stop, exploration, wreck tour).

    Setup allows operators to customize segment types for their operations.
    """

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Segment type name (e.g., 'descent', 'level', 'wreck_exploration')",
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable name (e.g., 'Descent', 'Level Section', 'Wreck Exploration')",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this segment type",
    )
    color = models.CharField(
        max_length=20,
        default="blue",
        help_text="Color for UI display (tailwind color name: blue, green, yellow, etc.)",
    )
    is_depth_transition = models.BooleanField(
        default=False,
        help_text="True for descent/ascent segments that have from/to depths",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=100,
        help_text="Order in dropdown menus (lower = first)",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "display_name"]

    def __str__(self):
        return self.display_name

    @classmethod
    def get_default_types(cls):
        """Return default segment types for initial setup."""
        return [
            {"name": "descent", "display_name": "Descent", "is_depth_transition": True, "sort_order": 10, "color": "cyan"},
            {"name": "level", "display_name": "Level Section", "is_depth_transition": False, "sort_order": 20, "color": "blue"},
            {"name": "exploration", "display_name": "Exploration", "is_depth_transition": False, "sort_order": 30, "color": "indigo"},
            {"name": "wreck_tour", "display_name": "Wreck Tour", "is_depth_transition": False, "sort_order": 40, "color": "purple"},
            {"name": "reef_tour", "display_name": "Reef Tour", "is_depth_transition": False, "sort_order": 50, "color": "teal"},
            {"name": "safety_stop", "display_name": "Safety Stop", "is_depth_transition": False, "sort_order": 90, "color": "green"},
            {"name": "ascent", "display_name": "Ascent", "is_depth_transition": True, "sort_order": 100, "color": "amber"},
        ]


class ExcursionTypeDive(BaseModel):
    """Template for a dive within an excursion type (Dive Plan Template).

    Defines the individual dives that make up an excursion product.
    For example, a "Morning 2-Tank Boat Dive" would have two dive templates:
    - Dive 1: First tank, typically shallower reef
    - Dive 2: Second tank, possibly deeper or different site

    When an excursion is created from this type, these templates are used
    to pre-populate the actual Dive records.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    excursion_types = models.ManyToManyField(
        "diveops.ExcursionType",
        blank=True,
        related_name="dive_templates",
        help_text="Excursion types that use this dive plan template",
    )

    # Site this plan is designed for (optional for generic templates)
    dive_site = models.ForeignKey(
        "diveops.DiveSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dive_plan_templates",
        help_text="Specific site this plan is for (null = generic template)",
    )

    # Sequence within excursion (1st dive, 2nd dive, etc.)
    sequence = models.PositiveSmallIntegerField(
        help_text="Dive number within the excursion (1, 2, 3...)",
    )

    # Dive details
    name = models.CharField(
        max_length=100,
        help_text="Name for this dive (e.g., 'First Tank', 'Deep Dive')",
    )
    description = models.TextField(
        blank=True,
        help_text="Description or notes about this dive",
    )

    # Dive specifications
    planned_depth_meters = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Target maximum depth in meters",
    )
    planned_duration_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Planned dive duration in minutes",
    )

    # Timing offset from excursion start (for scheduling)
    offset_minutes = models.PositiveSmallIntegerField(
        default=0,
        help_text="Minutes after excursion departure that this dive starts",
    )

    # Surface interval BEFORE this dive (for repetitive dive planning)
    surface_interval_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Surface interval before this dive (minutes). Null for first dive.",
    )

    # Optional: specific certification for this dive (may differ from excursion type)
    min_certification_level = models.ForeignKey(
        "diveops.CertificationLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dive_templates",
        help_text="Specific certification for this dive (overrides excursion type if set)",
    )

    # Commerce linkage - links to sellable product for this dive
    catalog_item = models.ForeignKey(
        "django_catalog.CatalogItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="dive_plan_templates",
        help_text="Product sold for this dive (includes components like tank, weights, etc.).",
    )

    # ─────────────────────────────────────────────────────────────
    # Access & Transport
    # ─────────────────────────────────────────────────────────────

    class AccessMode(models.TextChoices):
        BOAT = "boat", "Boat"
        VEHICLE = "vehicle", "Vehicle Transport"
        BEACH_MEET = "beach_meet", "Meet at Beach"
        SHORE_WALK = "shore_walk", "Shore Walk-In"
        DOCK = "dock", "Dock Entry"

    access_mode = models.CharField(
        max_length=20,
        choices=AccessMode.choices,
        blank=True,
        default="",
        help_text="How divers get to the dive site",
    )

    # ─────────────────────────────────────────────────────────────
    # Briefing Content Fields (Dive Plan Extension)
    # ─────────────────────────────────────────────────────────────

    class GasType(models.TextChoices):
        AIR = "air", "Air"
        EAN32 = "ean32", "EAN32"
        EAN36 = "ean36", "EAN36"
        TRIMIX = "trimix", "Trimix"

    gas = models.CharField(
        max_length=20,
        choices=GasType.choices,
        blank=True,
        default="",
        help_text="Gas mix for this dive",
    )

    equipment_requirements = models.JSONField(
        default=dict,
        blank=True,
        help_text="Equipment requirements by category: {required: [], recommended: [], rental_available: []}",
    )

    skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Skills to practice (for training dives)",
    )

    route = models.TextField(
        blank=True,
        default="",
        help_text="Dive profile, route description, or navigation plan",
    )

    hazards = models.TextField(
        blank=True,
        default="",
        help_text="Known hazards and safety considerations",
    )

    briefing_text = models.TextField(
        blank=True,
        default="",
        help_text="Full briefing content for communication to divers",
    )

    briefing_video_url = models.URLField(
        blank=True,
        default="",
        help_text="YouTube video URL for dive briefing",
    )

    boat_instructions = models.TextField(
        blank=True,
        default="",
        help_text="Instructions for boat dives (boarding, gear storage, entry/exit procedures)",
    )

    route_segments = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured dive profile: [{phase, depth_m, duration_min, description}, ...]",
    )

    # ─────────────────────────────────────────────────────────────
    # Publish Lifecycle (Dive Plan Extension)
    # ─────────────────────────────────────────────────────────────

    class PlanStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    status = models.CharField(
        max_length=10,
        choices=PlanStatus.choices,
        default=PlanStatus.DRAFT,
    )

    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="User who published this template",
    )

    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="User who retired this template",
    )

    class Meta:
        verbose_name = "Dive Plan Template"
        verbose_name_plural = "Dive Plan Templates"
        constraints = [
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="diveops_excursion_type_dive_sequence_gte_1",
            ),
        ]
        indexes = [
            models.Index(fields=["sequence"]),
            models.Index(fields=["dive_site"]),
        ]
        ordering = ["sequence", "name"]

    def __str__(self):
        return f"Dive {self.sequence}: {self.name}"
