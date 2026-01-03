"""Models for dive operations.

This module provides domain models for a diving operation built on django-primitives:
- DiverProfile: Extends Person with diving-specific data
- DiveSite: Location with diving metadata (depth, difficulty, certification required)
- DiveTrip: Scheduled dive trip connecting shop, site, and divers
- Booking: Reservation linking diver to trip
- TripRoster: Check-in record for actual participants
"""

import uuid
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

# Configurable waiver validity period (default 365 days, None = never expires)
DIVEOPS_WAIVER_VALIDITY_DAYS = getattr(settings, "DIVEOPS_WAIVER_VALIDITY_DAYS", 365)


class DiverProfile(models.Model):
    """Diver-specific profile extending a Person.

    Stores certification, experience, and medical clearance data.
    One profile per person (enforced by DB constraint).
    """

    CERTIFICATION_LEVELS = [
        ("sd", "Scuba Diver"),
        ("ow", "Open Water"),
        ("aow", "Advanced Open Water"),
        ("rescue", "Rescue Diver"),
        ("dm", "Divemaster"),
        ("instructor", "Instructor"),
    ]

    # Level hierarchy for comparison
    LEVEL_HIERARCHY = {
        "sd": 1,
        "ow": 2,
        "aow": 3,
        "rescue": 4,
        "dm": 5,
        "instructor": 6,
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to Person from django-parties
    person = models.OneToOneField(
        "django_parties.Person",
        on_delete=models.CASCADE,
        related_name="diver_profile",
    )

    # Certification
    certification_level = models.CharField(
        max_length=20,
        choices=CERTIFICATION_LEVELS,
    )
    certification_agency = models.CharField(
        max_length=50,
        help_text="e.g., PADI, SSI, NAUI, SDI",
    )
    certification_number = models.CharField(max_length=100)
    certification_date = models.DateField()

    # Experience
    total_dives = models.PositiveIntegerField(default=0)

    # Medical clearance
    medical_clearance_date = models.DateField(null=True, blank=True)
    medical_clearance_valid_until = models.DateField(null=True, blank=True)

    # Waiver tracking
    waiver_signed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(total_dives__gte=0),
                name="diveops_diver_total_dives_gte_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["certification_level"]),
            models.Index(fields=["person"]),
        ]

    def __str__(self):
        return f"{self.person} - {self.get_certification_level_display()}"

    @property
    def is_medical_current(self) -> bool:
        """Check if medical clearance is current."""
        if not self.medical_clearance_valid_until:
            return False
        return self.medical_clearance_valid_until >= date.today()

    def is_medical_current_as_of(self, as_of_date: date) -> bool:
        """Check if medical clearance was current as of a specific date."""
        if not self.medical_clearance_valid_until:
            return False
        return self.medical_clearance_valid_until >= as_of_date

    def meets_certification_level(self, required_level: str) -> bool:
        """Check if diver meets or exceeds required certification level."""
        my_rank = self.LEVEL_HIERARCHY.get(self.certification_level, 0)
        required_rank = self.LEVEL_HIERARCHY.get(required_level, 0)
        return my_rank >= required_rank

    def is_waiver_valid(self, as_of: datetime | None = None) -> bool:
        """Check if waiver is valid at a specific point in time.

        Args:
            as_of: Point in time to check (defaults to now)

        Returns:
            True if waiver was signed within the configured validity period
        """
        if self.waiver_signed_at is None:
            return False

        if as_of is None:
            as_of = timezone.now()

        # If no expiration configured, waiver never expires
        if DIVEOPS_WAIVER_VALIDITY_DAYS is None:
            return True

        # Check if waiver was signed within validity period
        expiration_date = self.waiver_signed_at + timedelta(days=DIVEOPS_WAIVER_VALIDITY_DAYS)
        return as_of <= expiration_date


class DiveSite(models.Model):
    """A dive site location with diving-specific metadata.

    Stores coordinates, depth limits, and certification requirements.
    """

    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
        ("expert", "Expert"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic info
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Diving characteristics
    max_depth_meters = models.PositiveIntegerField()
    min_certification_level = models.CharField(
        max_length=20,
        choices=DiverProfile.CERTIFICATION_LEVELS,
        default="ow",
    )
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="intermediate",
    )

    # Location (coordinates)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # Optional link to django-geo Place
    place = models.ForeignKey(
        "django_geo.Place",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_sites",
    )

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(max_depth_meters__gt=0),
                name="diveops_site_depth_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name="diveops_site_valid_latitude",
            ),
            models.CheckConstraint(
                condition=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name="diveops_site_valid_longitude",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["min_certification_level"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.max_depth_meters}m)"


class DiveTrip(models.Model):
    """A scheduled dive trip.

    Links a dive shop, dive site, and manages bookings.
    Can optionally link to django-encounters for workflow tracking.
    """

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("boarding", "Boarding"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="dive_trips",
    )
    dive_site = models.ForeignKey(
        DiveSite,
        on_delete=models.PROTECT,
        related_name="trips",
    )

    # Optional encounter for workflow tracking
    encounter = models.OneToOneField(
        "django_encounters.Encounter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_trip",
    )

    # Schedule
    departure_time = models.DateTimeField()
    return_time = models.DateTimeField()

    # Capacity
    max_divers = models.PositiveIntegerField()

    # Pricing
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
        related_name="dive_trips_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(return_time__gt=models.F("departure_time")),
                name="diveops_trip_return_after_departure",
            ),
            models.CheckConstraint(
                condition=Q(max_divers__gt=0),
                name="diveops_trip_max_divers_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(price_per_diver__gte=0),
                name="diveops_trip_price_gte_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["departure_time"]),
            models.Index(fields=["status"]),
            models.Index(fields=["dive_shop", "status"]),
        ]
        ordering = ["-departure_time"]

    def __str__(self):
        return f"{self.dive_site.name} - {self.departure_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def spots_available(self) -> int:
        """Return number of available spots (excluding cancelled bookings)."""
        confirmed_count = self.bookings.filter(
            status__in=["confirmed", "checked_in"]
        ).count()
        return max(0, self.max_divers - confirmed_count)

    @property
    def is_full(self) -> bool:
        """Check if trip is at capacity."""
        return self.spots_available == 0


class Booking(models.Model):
    """A diver's reservation for a trip.

    Links diver to trip and tracks booking status.
    Can link to basket/invoice for payment tracking.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("checked_in", "Checked In"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core relationship
    trip = models.ForeignKey(
        DiveTrip,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    # Commerce links
    basket = models.ForeignKey(
        "django_catalog.Basket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_bookings",
    )
    invoice = models.ForeignKey(
        "invoicing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_bookings",
    )

    # Waiver agreement
    waiver_agreement = models.ForeignKey(
        "django_agreements.Agreement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_bookings",
    )

    # Audit
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dive_bookings_made",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # Conditional unique: only one active booking per diver per trip
            # Cancelled bookings are excluded, allowing rebooking after cancellation
            models.UniqueConstraint(
                fields=["trip", "diver"],
                name="diveops_booking_one_active_per_trip",
                condition=Q(status__in=["pending", "confirmed", "checked_in"]),
            ),
        ]
        indexes = [
            models.Index(fields=["trip", "status"]),
            models.Index(fields=["diver"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.diver.person} - {self.trip}"


class TripRoster(models.Model):
    """Check-in record for a diver on a trip.

    Created when diver checks in, records actual participants.
    Tracks role (diver, divemaster, instructor) on the trip.
    """

    ROSTER_ROLES = [
        ("DIVER", "Diver"),
        ("DM", "Divemaster"),
        ("INSTRUCTOR", "Instructor"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core relationship
    trip = models.ForeignKey(
        DiveTrip,
        on_delete=models.CASCADE,
        related_name="roster",
    )
    diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.PROTECT,
        related_name="trip_roster_entries",
    )
    booking = models.OneToOneField(
        Booking,
        on_delete=models.PROTECT,
        related_name="roster_entry",
    )

    # Role on this trip
    role = models.CharField(
        max_length=20,
        choices=ROSTER_ROLES,
        default="DIVER",
        help_text="Role on this trip (diver, divemaster, or instructor)",
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
                fields=["trip", "diver"],
                name="diveops_roster_one_per_trip",
            ),
        ]
        indexes = [
            models.Index(fields=["trip"]),
            models.Index(fields=["role"]),
        ]
        ordering = ["checked_in_at"]

    def __str__(self):
        role_display = self.get_role_display() if self.role != "DIVER" else ""
        suffix = f" ({role_display})" if role_display else ""
        return f"{self.diver.person} - {self.trip} (checked in){suffix}"
