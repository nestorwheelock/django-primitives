"""Roster models for diveops.

Models for tracking diver participation on excursions and dives:
- ExcursionRoster: Check-in record for a diver on an excursion
- DiveAssignment: Assignment of a diver to a specific dive
- DiveLog: Per-diver personal dive record
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from django_basemodels import BaseModel


class ExcursionRoster(BaseModel):
    """Check-in record for a diver on an excursion.

    Created when diver checks in, records actual participants.
    Tracks role (diver, divemaster, instructor) on the excursion.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    ROSTER_ROLES = [
        ("DIVER", "Diver"),
        ("DM", "Divemaster"),
        ("INSTRUCTOR", "Instructor"),
    ]

    # Core relationship
    excursion = models.ForeignKey(
        "diveops.Excursion",
        on_delete=models.CASCADE,
        related_name="roster",
    )
    diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.PROTECT,
        related_name="excursion_roster_entries",
    )
    booking = models.OneToOneField(
        "diveops.Booking",
        on_delete=models.PROTECT,
        related_name="roster_entry",
    )

    # Role on this excursion
    role = models.CharField(
        max_length=20,
        choices=ROSTER_ROLES,
        default="DIVER",
        help_text="Role on this excursion (diver, divemaster, or instructor)",
    )

    # Check-in data
    checked_in_at = models.DateTimeField(default=timezone.now)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkins_performed",
    )

    # Dive completion tracking
    dive_completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["excursion", "diver"],
                name="diveops_roster_one_per_excursion",
            ),
        ]
        indexes = [
            models.Index(fields=["excursion"]),
            models.Index(fields=["role"]),
            # Performance: diver-based queries and completion filters
            models.Index(fields=["diver"]),
            models.Index(fields=["dive_completed"]),
            models.Index(fields=["checked_in_at"]),
        ]
        ordering = ["checked_in_at"]

    def __str__(self):
        role_display = self.get_role_display() if self.role != "DIVER" else ""
        suffix = f" ({role_display})" if role_display else ""
        return f"{self.diver.person} - {self.excursion} (checked in){suffix}"


# Backwards compatibility alias


class DiveAssignment(BaseModel):
    """Assignment of a diver to a specific dive within an excursion.

    Tracks participation and real-time status during the dive.
    A diver may participate in some dives in an excursion and sit out others.

    Status state machine:
    assigned → briefed → gearing_up → in_water → surfaced → on_boat
                                   ↘ sat_out / aborted

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class Role(models.TextChoices):
        DIVER = "diver", "Diver"
        GUIDE = "guide", "Guide"
        INSTRUCTOR = "instructor", "Instructor"
        STUDENT = "student", "Student"

    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        BRIEFED = "briefed", "Briefed"
        GEARING_UP = "gearing_up", "Gearing Up"
        IN_WATER = "in_water", "In Water"
        SURFACED = "surfaced", "Surfaced"
        ON_BOAT = "on_boat", "On Boat"
        SAT_OUT = "sat_out", "Sat Out"
        ABORTED = "aborted", "Aborted"

    # Core relationships
    dive = models.ForeignKey(
        "diveops.Dive",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.PROTECT,
        related_name="dive_assignments",
    )

    # Role on this dive
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.DIVER,
    )

    # Buddy pairing (optional)
    buddy = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buddy_assignments",
        help_text="Assigned buddy for this dive",
    )

    # Planning overrides (optional, overrides dive plan for this diver)
    planned_max_depth = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Planned max depth for this diver (overrides dive plan)",
    )
    planned_bottom_time = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Planned bottom time for this diver (overrides dive plan)",
    )

    # Real-time status tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ASSIGNED,
    )

    # Timestamps for status transitions
    entered_water_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When diver entered the water",
    )
    surfaced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When diver surfaced",
    )

    # Safety tracking (optional)
    last_known_bearing = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Last known compass bearing (for tracking)",
    )

    class Meta:
        constraints = [
            # Unique diver per dive
            models.UniqueConstraint(
                fields=["dive", "diver"],
                name="diveops_dive_assignment_unique_diver",
            ),
        ]
        indexes = [
            models.Index(fields=["dive", "status"]),
            models.Index(fields=["diver"]),
        ]
        ordering = ["dive", "role", "created_at"]

    def __str__(self):
        return f"{self.diver} - {self.dive} ({self.get_status_display()})"

    @property
    def is_participating(self) -> bool:
        """Check if diver participated (entered water)."""
        return self.status in [
            self.Status.IN_WATER,
            self.Status.SURFACED,
            self.Status.ON_BOAT,
        ]


class DiveLog(BaseModel):
    """Per-diver personal dive record.

    DiveLog is the diver's permanent history. It references the master Dive
    and can override metrics using the overlay pattern:
    - Null fields = inherit from Dive
    - Non-null fields = diver's personal override

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class SuitType(models.TextChoices):
        NONE = "none", "None"
        SHORTY = "shorty", "Shorty"
        MM3 = "3mm", "3mm"
        MM5 = "5mm", "5mm"
        MM7 = "7mm", "7mm"
        DRY = "dry", "Drysuit"

    class Source(models.TextChoices):
        SHOP = "shop", "Shop System"
        MANUAL = "manual", "Manual Entry"

    # Core relationships
    dive = models.ForeignKey(
        "diveops.Dive",
        on_delete=models.PROTECT,
        related_name="dive_logs",
    )
    diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.PROTECT,
        related_name="dive_logs",
    )
    assignment = models.OneToOneField(
        DiveAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_log",
        help_text="Link to assignment (expected when created through ops)",
    )

    # Buddy info
    buddy = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buddy_logs",
        help_text="Buddy profile (if in system)",
    )
    buddy_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Buddy name (if not in system or for display)",
    )

    # Personal override metrics (null = use Dive values)
    max_depth_meters = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Personal max depth (null = use dive value)",
    )
    bottom_time_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Personal bottom time (null = use dive value)",
    )

    # Air consumption
    air_start_bar = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Starting tank pressure in bar",
    )
    air_end_bar = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Ending tank pressure in bar",
    )

    # Equipment used
    weight_kg = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Weight used in kg",
    )
    suit_type = models.CharField(
        max_length=10,
        choices=SuitType.choices,
        blank=True,
        default="",
    )
    tank_size_liters = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Tank size in liters",
    )
    nitrox_percentage = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Nitrox O2 percentage (21-40 for recreational)",
    )

    # Dive computer import
    computer_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw dive computer import payload",
    )
    computer_max_depth = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Max depth from dive computer",
    )
    computer_avg_depth = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Average depth from dive computer",
    )
    computer_bottom_time = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Bottom time from dive computer",
    )
    computer_dive_time = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Total dive time from dive computer",
    )

    # Notes
    notes = models.TextField(blank=True)

    # Dive numbering
    dive_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Diver's sequential dive number (auto-assigned or manual)",
    )

    # Verification (for certification credit)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_logs_verified",
        help_text="Staff who verified this log",
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the log was verified",
    )

    # Source tracking
    source = models.CharField(
        max_length=10,
        choices=Source.choices,
        default=Source.SHOP,
        help_text="How this log was created",
    )

    class Meta:
        constraints = [
            # Unique diver per dive
            models.UniqueConstraint(
                fields=["dive", "diver"],
                name="diveops_dive_log_unique_diver",
            ),
            # Air consumption: end must be less than start when both present
            models.CheckConstraint(
                condition=(
                    Q(air_start_bar__isnull=True) |
                    Q(air_end_bar__isnull=True) |
                    Q(air_end_bar__lt=F("air_start_bar"))
                ),
                name="diveops_dive_log_air_end_lt_start",
            ),
            # Nitrox percentage must be 21-40 (recreational range) when set
            models.CheckConstraint(
                condition=(
                    Q(nitrox_percentage__isnull=True) |
                    (Q(nitrox_percentage__gte=21) & Q(nitrox_percentage__lte=40))
                ),
                name="diveops_dive_log_nitrox_21_40",
            ),
        ]
        indexes = [
            models.Index(fields=["diver", "dive"]),
            models.Index(fields=["verified_at"]),
            models.Index(fields=["dive_number"]),
        ]
        ordering = ["-dive__planned_start"]

    def __str__(self):
        return f"DiveLog: {self.diver} - {self.dive}"

    @property
    def effective_max_depth(self):
        """Return personal max depth or inherit from dive."""
        if self.max_depth_meters is not None:
            return self.max_depth_meters
        return self.dive.max_depth_meters

    @property
    def effective_bottom_time(self):
        """Return personal bottom time or inherit from dive."""
        if self.bottom_time_minutes is not None:
            return self.bottom_time_minutes
        return self.dive.bottom_time_minutes

    @property
    def air_consumed_bar(self):
        """Calculate air consumed (start - end) if both values present."""
        if self.air_start_bar is not None and self.air_end_bar is not None:
            return self.air_start_bar - self.air_end_bar
        return None

    @property
    def is_verified(self) -> bool:
        """Check if log has been verified."""
        return self.verified_at is not None
