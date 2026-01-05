"""Models for dive operations.

This module provides domain models for a diving operation built on django-primitives:
- CertificationLevel: Reference data for certification levels
- DiverCertification: Diver's certification records (normalized)
- TripRequirement: Requirements for joining a trip
- DiverProfile: Extends Person with diving-specific data
- DiveSite: Location with diving metadata (depth, difficulty, certification required)
- DiveTrip: Scheduled dive trip connecting shop, site, and divers
- Booking: Reservation linking diver to trip
- TripRoster: Check-in record for actual participants
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from django_basemodels import BaseModel

# Configurable waiver validity period (default 365 days, None = never expires)
DIVEOPS_WAIVER_VALIDITY_DAYS = getattr(settings, "DIVEOPS_WAIVER_VALIDITY_DAYS", 365)


class CertificationLevel(BaseModel):
    """Reference data for certification levels, scoped by agency.

    Each certification agency (PADI, SSI, NAUI, etc.) defines their own levels.
    The rank field enables comparison within and across agencies.

    Example: PADI OW (rank=2) and SSI OW (rank=2) are equivalent.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    # Agency that defines this level
    agency = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="certification_levels",
        help_text="Certification agency that defines this level (PADI, SSI, etc.)",
    )
    code = models.SlugField(
        max_length=20,
        help_text="Short code like 'ow', 'aow', 'dm' (unique per agency)",
    )
    name = models.CharField(
        max_length=100,
        help_text="Full name like 'Open Water Diver'",
    )
    rank = models.PositiveIntegerField(
        help_text="Numeric rank for comparison (higher = more advanced)",
    )
    max_depth_m = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Maximum depth in meters for this level (optional)",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # Unique code per agency (among active records)
            models.UniqueConstraint(
                fields=["agency", "code"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_agency_level_code",
            ),
            # Rank must be positive
            models.CheckConstraint(
                condition=Q(rank__gt=0),
                name="diveops_cert_level_rank_gt_zero",
            ),
            # Max depth must be positive if set
            models.CheckConstraint(
                condition=Q(max_depth_m__isnull=True) | Q(max_depth_m__gt=0),
                name="diveops_cert_level_depth_gt_zero",
            ),
        ]
        ordering = ["agency", "rank"]

    def __str__(self):
        return f"{self.name} ({self.agency.name})"


class DiverCertification(BaseModel):
    """A diver's certification record.

    Normalized join table allowing multiple certifications per diver.
    Links to CertificationLevel (which is agency-scoped).

    Invariant: level.agency is the issuing agency (no separate agency FK needed).

    Proof documents (certification card photos/PDFs) are attached via
    django_documents.Document with GenericFK to this model.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    diver = models.ForeignKey(
        "DiverProfile",
        on_delete=models.CASCADE,
        related_name="certifications",
    )
    level = models.ForeignKey(
        CertificationLevel,
        on_delete=models.PROTECT,
        related_name="diver_certifications",
        help_text="Certification level (determines agency)",
    )

    # Card details
    card_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Certification card number",
    )
    issued_on = models.DateField(
        null=True,
        blank=True,
        help_text="Date certification was issued",
    )
    expires_on = models.DateField(
        null=True,
        blank=True,
        help_text="Leave blank if certification never expires",
    )

    # Proof document - uses django_documents primitive
    # Documents are attached via GenericFK (target=this certification)
    # This FK provides a shortcut to the primary proof document
    proof_document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certification_proofs",
        help_text="Primary proof document (certification card photo/scan)",
    )

    # Verification tracking
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certifications_verified",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # Only one certification per diver+level (among active records)
            # Since level is agency-scoped, this is effectively diver+agency+level_code
            models.UniqueConstraint(
                fields=["diver", "level"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_active_certification",
            ),
            # Expiration must be after issue date
            models.CheckConstraint(
                condition=Q(expires_on__isnull=True) | Q(issued_on__isnull=True) | Q(expires_on__gt=F("issued_on")),
                name="diveops_cert_expires_after_issued",
            ),
        ]
        ordering = ["-level__rank", "-issued_on"]

    def __str__(self):
        return f"{self.diver} - {self.level.name} ({self.agency.name})"

    @property
    def agency(self):
        """Get the certification agency (from level)."""
        return self.level.agency

    @property
    def is_current(self) -> bool:
        """Check if certification is not expired."""
        if self.expires_on is None:
            return True
        return self.expires_on > date.today()


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
        "Excursion",
        on_delete=models.CASCADE,
        related_name="requirements",
    )
    requirement_type = models.CharField(
        max_length=20,
        choices=REQUIREMENT_TYPES,
    )

    # For certification requirements
    certification_level = models.ForeignKey(
        CertificationLevel,
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
TripRequirement = ExcursionRequirement


class DiverProfile(BaseModel):
    """Diver-specific profile extending a Person.

    Stores certification, experience, and medical clearance data.
    One profile per person (enforced by DB constraint).

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
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

    # Link to Person from django-parties
    person = models.OneToOneField(
        "django_parties.Person",
        on_delete=models.CASCADE,
        related_name="diver_profile",
    )

    # Legacy certification fields (deprecated - use DiverCertification instead)
    # Kept for backwards compatibility during migration
    certification_level = models.CharField(
        max_length=20,
        choices=CERTIFICATION_LEVELS,
        blank=True,
        default="",
        help_text="DEPRECATED: Use DiverCertification model instead",
    )
    certification_agency = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="diver_profiles",
        null=True,
        blank=True,
        help_text="DEPRECATED: Use DiverCertification model instead",
    )
    certification_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="DEPRECATED: Use DiverCertification model instead",
    )
    certification_date = models.DateField(
        null=True,
        blank=True,
        help_text="DEPRECATED: Use DiverCertification model instead",
    )

    # Experience
    total_dives = models.PositiveIntegerField(default=0)

    # Medical clearance
    medical_clearance_date = models.DateField(null=True, blank=True)
    medical_clearance_valid_until = models.DateField(null=True, blank=True)

    # Waiver tracking
    waiver_signed_at = models.DateTimeField(null=True, blank=True)

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


class DiveSite(BaseModel):
    """A dive site location composing primitives.

    Thin overlay model that composes:
    - django_geo.Place for location (required, owned per site)
    - CertificationLevel FK for eligibility (nullable)
    - Domain-only fields: rating, tags, max_depth, difficulty

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
        ("expert", "Expert"),
    ]

    class DiveMode(models.TextChoices):
        BOAT = "boat", "Boat Accessible"
        SHORE = "shore", "Shore Accessible"
        CENOTE = "cenote", "Cenote"
        CAVERN = "cavern", "Cavern/Cave"

    # Basic info
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Location - owned Place (required, coordinates accessed via place.latitude/longitude)
    place = models.ForeignKey(
        "django_geo.Place",
        on_delete=models.PROTECT,
        related_name="dive_sites",
        help_text="Location (owned per site, not shared)",
    )

    # Diving characteristics
    max_depth_meters = models.PositiveIntegerField()
    min_certification_level = models.ForeignKey(
        CertificationLevel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dive_sites",
        help_text="Minimum certification required (null = no requirement)",
    )
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="intermediate",
    )
    dive_mode = models.CharField(
        max_length=10,
        choices=DiveMode.choices,
        default=DiveMode.BOAT,
        help_text="How this site is accessed (boat, shore, cenote, cavern)",
    )

    # Quality/categorization
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Site rating 1-5 (null = unrated)",
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for categorization (e.g., ['reef', 'coral', 'wreck'])",
    )

    # Status
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(max_depth_meters__gt=0),
                name="diveops_site_depth_gt_zero",
            ),
            # Rating must be 1-5 or null
            models.CheckConstraint(
                condition=Q(rating__isnull=True) | (Q(rating__gte=1) & Q(rating__lte=5)),
                name="diveops_site_rating_1_to_5",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.max_depth_meters}m)"


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
        DiveSite,
        on_delete=models.PROTECT,
        related_name="excursions",
        null=True,
        blank=True,
        help_text="Primary dive site (optional - sites can be set per dive)",
    )

    # Optional link to Trip package (null = standalone/walk-in)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="excursions",
        help_text="Trip package this excursion belongs to (null = standalone)",
    )

    # Optional link to ExcursionType (product template)
    excursion_type = models.ForeignKey(
        "ExcursionType",
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
        from .models import DiveSite
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
DiveTrip = Excursion


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
        Excursion,
        on_delete=models.CASCADE,
        related_name="dives",
    )

    # Dive site (may differ from excursion's site for multi-site excursions)
    dive_site = models.ForeignKey(
        DiveSite,
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


class Booking(BaseModel):
    """A diver's reservation for an excursion.

    Links diver to excursion and tracks booking status.
    Can link to basket/invoice for payment tracking.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("checked_in", "Checked In"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]

    # Core relationship - links to Excursion (operational unit)
    excursion = models.ForeignKey(
        Excursion,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    # Backwards compatibility: 'trip' as alias for 'excursion'
    @property
    def trip(self):
        """Backwards compatibility alias for excursion."""
        return self.excursion

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

    # Audit (booked_by is application-specific, not from BaseModel)
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dive_bookings_made",
    )
    # Domain-specific: when this booking was cancelled (distinct from soft delete)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # INV-3: Price Immutability - price locked at booking creation
    # The price_snapshot captures full pricing context at booking time
    # price_amount/price_currency are denormalized for efficient queries
    price_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Full pricing context at booking time (immutable snapshot)",
    )
    price_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price locked at booking (denormalized from snapshot)",
    )
    price_currency = models.CharField(
        max_length=3,
        blank=True,
        default="",
        help_text="Currency code (denormalized from snapshot)",
    )

    class Meta:
        constraints = [
            # Conditional unique: only one active booking per diver per excursion
            # Cancelled bookings are excluded, allowing rebooking after cancellation
            models.UniqueConstraint(
                fields=["excursion", "diver"],
                name="diveops_booking_one_active_per_excursion",
                condition=Q(status__in=["pending", "confirmed", "checked_in"]),
            ),
        ]
        indexes = [
            models.Index(fields=["excursion", "status"]),
            models.Index(fields=["diver"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.diver.person} - {self.excursion}"

    # -------------------------------------------------------------------------
    # T-011: Financial State Properties and Methods
    # -------------------------------------------------------------------------

    @property
    def is_settled(self) -> bool:
        """Check if booking has a revenue settlement.

        Returns True if any revenue SettlementRecord exists for this booking.
        """
        return self.settlements.filter(settlement_type="revenue").exists()

    @property
    def has_refund(self) -> bool:
        """Check if booking has a refund settlement.

        Returns True if any refund SettlementRecord exists for this booking.
        """
        return self.settlements.filter(settlement_type="refund").exists()

    def get_financial_state(self) -> str:
        """Get the current financial state of the booking.

        Returns:
            'unsettled': No settlements exist
            'settled': Has revenue settlement but no refund
            'refunded': Has refund settlement
        """
        if self.has_refund:
            return "refunded"
        if self.is_settled:
            return "settled"
        return "unsettled"

    def delete(self, *args, **kwargs):
        """Override delete to block deletion of settled bookings.

        INV-5: Bookings with settlements cannot be deleted.
        """
        from .exceptions import BookingError

        if self.is_settled:
            raise BookingError(
                "Booking has settlement records and cannot be deleted. "
                "Financial records must be preserved for audit trail."
            )
        return super().delete(*args, **kwargs)


class EligibilityOverride(BaseModel):
    """INV-1: Booking-scoped eligibility override.

    Allows staff to override eligibility checks for a SPECIFIC booking.
    NOT a global override for a diver, excursion, or trip.

    Key constraints:
    - OneToOne relationship to Booking (booking-scoped ONLY)
    - No FK to Excursion, Trip, or TripDay
    - Override does NOT modify requirements - only bypasses check for this booking
    - Requires approved_by and reason

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    # OneToOne to Booking - one override per booking maximum
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="eligibility_override",
    )

    # The diver this override applies to (denormalized for clarity)
    diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.PROTECT,
        related_name="eligibility_overrides",
    )

    # What requirement was bypassed
    requirement_type = models.CharField(
        max_length=50,
        help_text="Type of requirement bypassed (certification, experience, medical, etc.)",
    )
    original_requirement = models.JSONField(
        help_text="Original requirement that was bypassed (for audit trail)",
    )

    # Approval details (required)
    reason = models.TextField(
        help_text="Justification for the override (required)",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eligibility_overrides_approved",
    )
    approved_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        indexes = [
            models.Index(fields=["booking"]),
            models.Index(fields=["diver"]),
            models.Index(fields=["approved_at"]),
        ]
        ordering = ["-approved_at"]

    def __str__(self):
        return f"Override: {self.booking} ({self.requirement_type})"


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
        Excursion,
        on_delete=models.CASCADE,
        related_name="roster",
    )
    diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.PROTECT,
        related_name="excursion_roster_entries",
    )
    booking = models.OneToOneField(
        Booking,
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
        ]
        ordering = ["checked_in_at"]

    def __str__(self):
        role_display = self.get_role_display() if self.role != "DIVER" else ""
        suffix = f" ({role_display})" if role_display else ""
        return f"{self.diver.person} - {self.excursion} (checked in){suffix}"


# Backwards compatibility alias
TripRoster = ExcursionRoster


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
    max_depth_meters = models.PositiveIntegerField()
    typical_duration_minutes = models.PositiveIntegerField(default=60)
    dives_per_excursion = models.PositiveSmallIntegerField(default=2)

    # Eligibility
    min_certification_level = models.ForeignKey(
        CertificationLevel,
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
        DiveSite,
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

    # Status
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(base_price__gte=0),
                name="diveops_excursion_type_base_price_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(max_depth_meters__gt=0),
                name="diveops_excursion_type_depth_gt_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["dive_mode"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_dive_mode_display()})"


class ExcursionTypeDive(BaseModel):
    """Template for a dive within an excursion type.

    Defines the individual dives that make up an excursion product.
    For example, a "Morning 2-Tank Boat Dive" would have two dive templates:
    - Dive 1: First tank, typically shallower reef
    - Dive 2: Second tank, possibly deeper or different site

    When an excursion is created from this type, these templates are used
    to pre-populate the actual Dive records.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    excursion_type = models.ForeignKey(
        ExcursionType,
        on_delete=models.CASCADE,
        related_name="dive_templates",
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

    # Optional: specific certification for this dive (may differ from excursion type)
    min_certification_level = models.ForeignKey(
        CertificationLevel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dive_templates",
        help_text="Specific certification for this dive (overrides excursion type if set)",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["excursion_type", "sequence"],
                name="diveops_excursion_type_dive_unique_sequence",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="diveops_excursion_type_dive_sequence_gte_1",
            ),
        ]
        indexes = [
            models.Index(fields=["excursion_type", "sequence"]),
        ]
        ordering = ["excursion_type", "sequence"]

    def __str__(self):
        return f"{self.excursion_type.name} - Dive {self.sequence}: {self.name}"


class SitePriceAdjustment(BaseModel):
    """Site-specific price adjustment for excursions.

    Represents cost factors that vary by dive site location:
    - Distance/fuel surcharge (farther sites cost more)
    - Park entry fees (marine parks, national parks)
    - Night dive surcharge
    - Boat charter fees

    These adjustments are added to ExcursionType.base_price by the
    ExcursionTypePricingService to compute final excursion price.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class AdjustmentKind(models.TextChoices):
        DISTANCE = "distance", "Distance/Fuel Surcharge"
        PARK_FEE = "park_fee", "Park Entry Fee"
        NIGHT = "night", "Night Dive Surcharge"
        BOAT = "boat", "Boat Charter Fee"

    dive_site = models.ForeignKey(
        DiveSite,
        on_delete=models.CASCADE,
        related_name="price_adjustments",
    )
    kind = models.CharField(
        max_length=20,
        choices=AdjustmentKind.choices,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Adjustment amount (added to base price)",
    )
    currency = models.CharField(max_length=3, default="USD")

    # Optional mode filter
    applies_to_mode = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="If set, only applies to this dive mode (boat/shore)",
    )

    # Pricing behavior
    is_per_diver = models.BooleanField(
        default=True,
        help_text="If True, applied per diver; if False, applied per trip",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # Only one adjustment of each kind per site (among active records)
            models.UniqueConstraint(
                fields=["dive_site", "kind"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_site_adjustment_kind",
            ),
        ]
        indexes = [
            models.Index(fields=["dive_site", "is_active"]),
        ]
        ordering = ["dive_site", "kind"]

    def __str__(self):
        return f"{self.dive_site.name}: {self.get_kind_display()} ({self.amount} {self.currency})"


# =============================================================================
# Settlement Records - INV-4: Idempotent Financial Postings
# =============================================================================


class SettlementRecord(BaseModel):
    """INV-4: Idempotent settlement record for booking payments.

    Tracks financial settlements for bookings with ledger integration.
    The idempotency_key ensures duplicate settlements are rejected.

    Settlement types:
    - revenue: Initial revenue recognition for a booking
    - refund: Refund posting for cancelled bookings (T-006)

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class SettlementType(models.TextChoices):
        REVENUE = "revenue", "Revenue"
        REFUND = "refund", "Refund"

    # Core relationship
    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        related_name="settlements",
    )

    # Settlement type
    settlement_type = models.CharField(
        max_length=20,
        choices=SettlementType.choices,
        default=SettlementType.REVENUE,
    )

    # Idempotency - unique key prevents duplicate settlements
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Deterministic key: {booking_id}:{type}:{sequence}",
    )

    # Amount and currency (from booking price_snapshot)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Settlement amount",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
    )

    # Ledger integration - links to posted transaction
    transaction = models.ForeignKey(
        "django_ledger.Transaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="diveops_settlements",
        help_text="Linked ledger transaction (immutable after posting)",
    )

    # Link to settlement run (if part of a batch)
    settlement_run = models.ForeignKey(
        "SettlementRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settlements",
        help_text="Settlement run this record belongs to (if batch processed)",
    )

    # Audit
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_settlements",
    )
    settled_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the settlement was recorded",
    )
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            # Unique idempotency key is handled by unique=True on field
        ]
        indexes = [
            models.Index(fields=["booking", "settlement_type"]),
            models.Index(fields=["settled_at"]),
            models.Index(fields=["settlement_run"]),
        ]
        ordering = ["-settled_at"]

    def __str__(self):
        return f"Settlement {self.idempotency_key}: {self.amount} {self.currency}"


# =============================================================================
# T-009: Commission Rule Definition
# =============================================================================


class CommissionRule(BaseModel):
    """INV-3: Effective-dated commission rule for revenue sharing.

    Commission rules define how revenue is split for bookings:
    - Shop default commission rate (excursion_type=NULL)
    - ExcursionType-specific overrides (higher priority)
    - Rate can be percentage of booking price or fixed amount
    - Effective dating allows rate changes without losing history

    Rule priority (highest to lowest):
    1. ExcursionType-specific rule (matching excursion_type, latest effective_at)
    2. Shop default rule (excursion_type=NULL, latest effective_at)
    3. Zero commission (no matching rule)

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class RateType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed Amount"

    # Ownership - which shop this rule applies to
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="commission_rules",
    )

    # Optional scope - if NULL, applies as shop default
    excursion_type = models.ForeignKey(
        ExcursionType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commission_rules",
        help_text="If set, rule only applies to this ExcursionType. NULL = shop default.",
    )

    # Rate configuration
    rate_type = models.CharField(
        max_length=20,
        choices=RateType.choices,
        default=RateType.PERCENTAGE,
    )
    rate_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Percentage (e.g., 15.00 = 15%) or fixed amount (e.g., 25.00)",
    )

    # Effective dating (INV-3)
    effective_at = models.DateTimeField(
        help_text="When this rule becomes effective. Latest effective_at <= as_of wins.",
    )

    # Optional description
    description = models.TextField(
        blank=True,
        help_text="Reason for this rate or notes about the rule",
    )

    class Meta:
        constraints = [
            # Rate value must be non-negative
            models.CheckConstraint(
                condition=Q(rate_value__gte=0),
                name="diveops_commission_rate_non_negative",
            ),
            # Percentage must be <= 100
            models.CheckConstraint(
                condition=~Q(rate_type="percentage") | Q(rate_value__lte=100),
                name="diveops_commission_percentage_max_100",
            ),
        ]
        indexes = [
            models.Index(fields=["dive_shop", "excursion_type", "effective_at"]),
            models.Index(fields=["effective_at"]),
        ]
        ordering = ["-effective_at"]

    def __str__(self):
        scope = self.excursion_type.name if self.excursion_type else "Shop Default"
        if self.rate_type == self.RateType.PERCENTAGE:
            return f"{scope}: {self.rate_value}%"
        return f"{scope}: ${self.rate_value} fixed"


# =============================================================================
# T-010: Settlement Run (Batch Posting)
# =============================================================================


class SettlementRun(BaseModel):
    """Batch settlement run record.

    Tracks a batch of settlements processed together:
    - Period (date range) of bookings included
    - Success/failure counts
    - Total amount settled
    - Audit trail

    Individual SettlementRecords link to their SettlementRun.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # Shop this run is for
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="settlement_runs",
    )

    # Period covered by this run
    period_start = models.DateTimeField(
        help_text="Start of period for eligible bookings",
    )
    period_end = models.DateTimeField(
        help_text="End of period for eligible bookings",
    )

    # Run status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Counts
    total_bookings = models.IntegerField(
        default=0,
        help_text="Total eligible bookings found",
    )
    settled_count = models.IntegerField(
        default=0,
        help_text="Number of bookings successfully settled",
    )
    failed_count = models.IntegerField(
        default=0,
        help_text="Number of bookings that failed to settle",
    )

    # Total amount
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total amount settled in this run",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
    )

    # Audit
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="settlement_runs_processed",
    )
    run_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the run was executed",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the run finished",
    )
    notes = models.TextField(blank=True)
    error_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Details of any failures during the run",
    )

    class Meta:
        indexes = [
            models.Index(fields=["dive_shop", "run_at"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-run_at"]

    def __str__(self):
        return f"SettlementRun {self.pk}: {self.dive_shop.name} ({self.settled_count}/{self.total_bookings})"


# =============================================================================
# Dive Assignment and Dive Log Models (DiveLog System)
# =============================================================================


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
        Dive,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    diver = models.ForeignKey(
        DiverProfile,
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
        DiverProfile,
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
        Dive,
        on_delete=models.PROTECT,
        related_name="dive_logs",
    )
    diver = models.ForeignKey(
        DiverProfile,
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
        DiverProfile,
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


