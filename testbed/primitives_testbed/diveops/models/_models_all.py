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

import hashlib
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from django_basemodels import BaseModel
from django_singleton import EnvFallbackMixin, SingletonModel

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

    # Body Measurements / Gear Sizing
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Weight in kilograms",
    )
    height_cm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Height in centimeters",
    )
    wetsuit_size = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Wetsuit size (XS, S, M, L, XL, XXL, or custom)",
    )
    bcd_size = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="BCD/jacket size (XS, S, M, L, XL, XXL)",
    )
    fin_size = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Fin size (e.g., S/M, M/L, or shoe size)",
    )
    mask_fit = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Mask fit notes (low volume, standard, etc.)",
    )
    glove_size = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Glove size (XS, S, M, L, XL)",
    )
    weight_required_kg = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Weight needed for neutral buoyancy in kg",
    )
    gear_notes = models.TextField(
        blank=True,
        default="",
        help_text="Additional gear preferences or requirements",
    )

    # Equipment Ownership
    EQUIPMENT_OWNERSHIP_CHOICES = [
        ("none", "None - Rents All"),
        ("partial", "Partial - Own Some Gear"),
        ("full", "Full - Owns All Essential Gear"),
    ]
    equipment_ownership = models.CharField(
        max_length=20,
        choices=EQUIPMENT_OWNERSHIP_CHOICES,
        default="none",
        help_text="Equipment ownership status",
    )

    # Diver Type - Identity vs Activity
    DIVER_TYPE_CHOICES = [
        ("identity", "Diver (Identity)"),
        ("activity", "Does Diving (Activity)"),
    ]
    diver_type = models.CharField(
        max_length=20,
        choices=DIVER_TYPE_CHOICES,
        default="activity",
        help_text="Is diving their identity or just an activity they do?",
    )

    # Profile Photo - selected from photos they're tagged in
    profile_photo = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diver_profile_photos",
        help_text="Profile photo for this diver (selected from tagged photos)",
    )

    # Photo ID - uploaded during liability form completion
    photo_id = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diver_photo_ids",
        help_text="Photo ID document uploaded during liability waiver signing",
    )

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
            models.Index(fields=["equipment_ownership"]),
            models.Index(fields=["diver_type"]),
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

    @property
    def emergency_contacts(self):
        """Get all active emergency contacts ordered by priority."""
        return self.emergency_contact_entries.filter(
            deleted_at__isnull=True
        ).select_related("contact_person").order_by("priority")

    @property
    def primary_emergency_contact(self):
        """Get the primary (highest priority) emergency contact."""
        return self.emergency_contacts.first()

    # Social Graph Methods
    @property
    def relationships(self):
        """Get all relationships (outgoing) for this diver."""
        return self.relationships_from.filter(
            deleted_at__isnull=True
        ).select_related("to_diver", "to_diver__person")

    @property
    def spouse(self):
        """Get spouse/partner if relationship exists."""
        rel = self.relationships_from.filter(
            relationship_type="spouse",
            deleted_at__isnull=True,
        ).select_related("to_diver", "to_diver__person").first()
        return rel.to_diver if rel else None

    @property
    def preferred_buddies(self):
        """Get preferred dive buddies."""
        return DiverProfile.objects.filter(
            relationships_to__from_diver=self,
            relationships_to__is_preferred_buddy=True,
            relationships_to__deleted_at__isnull=True,
            deleted_at__isnull=True,
        ).select_related("person")

    def get_related_divers(self, relationship_type=None):
        """Get all divers with a relationship to this diver.

        Args:
            relationship_type: Filter by type (spouse, buddy, friend, etc.)
        """
        qs = self.relationships_from.filter(deleted_at__isnull=True)
        if relationship_type:
            qs = qs.filter(relationship_type=relationship_type)
        return [rel.to_diver for rel in qs.select_related("to_diver", "to_diver__person")]

    def is_related_to(self, other_diver, relationship_type=None):
        """Check if this diver has a relationship with another diver."""
        qs = self.relationships_from.filter(
            to_diver=other_diver,
            deleted_at__isnull=True,
        )
        if relationship_type:
            qs = qs.filter(relationship_type=relationship_type)
        return qs.exists()


class EmergencyContact(BaseModel):
    """Emergency contact for a diver.

    Links to a Person from django-parties. Supports multiple contacts
    with priority ordering. If the emergency contact is also a diver,
    a secondary contact should be added for situations where both
    might be on the same trip (e.g., spouses who dive together).

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse/Partner"),
        ("parent", "Parent"),
        ("child", "Child (Adult)"),
        ("sibling", "Sibling"),
        ("friend", "Friend"),
        ("other_family", "Other Family Member"),
        ("employer", "Employer"),
        ("other", "Other"),
    ]

    diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.CASCADE,
        related_name="emergency_contact_entries",
    )
    contact_person = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.PROTECT,
        related_name="emergency_contact_for",
        help_text="The person to contact in an emergency",
    )
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        help_text="Relationship to the diver",
    )
    priority = models.PositiveSmallIntegerField(
        default=1,
        help_text="Contact priority (1 = primary, 2 = secondary, etc.)",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes (e.g., 'Also a diver - may be on same trip')",
    )

    class Meta:
        ordering = ["diver", "priority"]
        constraints = [
            # Unique priority per diver (no duplicate priorities)
            models.UniqueConstraint(
                fields=["diver", "priority"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_emergency_contact_priority",
            ),
        ]
        indexes = [
            models.Index(fields=["diver", "priority"]),
        ]

    def __str__(self):
        return f"{self.contact_person} ({self.get_relationship_display()}) for {self.diver.person}"

    @property
    def is_also_diver(self) -> bool:
        """Check if the emergency contact is also a registered diver."""
        return hasattr(self.contact_person, "diver_profile") and \
               self.contact_person.diver_profile is not None and \
               self.contact_person.diver_profile.deleted_at is None

    def would_be_on_excursion(self, excursion) -> bool:
        """Check if this emergency contact is on a specific excursion roster.

        Use this to warn when both diver and emergency contact are on the
        same trip (e.g., spouses who dive together need a third contact).
        """
        if not self.is_also_diver:
            return False
        # Check if the contact's diver profile is on this excursion
        # Note: ExcursionGuest doesn't exist - should be ExcursionRoster or Booking
        # TODO: Fix this broken reference
        return ExcursionRoster.objects.filter(
            excursion=excursion,
            diver=self.contact_person.diver_profile,
            deleted_at__isnull=True,
        ).exists()


class DiverRelationship(BaseModel):
    """Relationship between two divers.

    Tracks social and diving connections between divers:
    - Spouses/partners who dive together
    - Regular dive buddies
    - Friends who travel together
    - Family members

    Relationships are bidirectional - creating one creates the inverse.
    Used for buddy pairing suggestions and group management.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse/Partner"),
        ("buddy", "Dive Buddy"),
        ("friend", "Friend"),
        ("family", "Family Member"),
        ("instructor_student", "Instructor/Student"),
        ("travel_companion", "Travel Companion"),
    ]

    from_diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.CASCADE,
        related_name="relationships_from",
    )
    to_diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.CASCADE,
        related_name="relationships_to",
    )
    relationship_type = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
    )
    is_preferred_buddy = models.BooleanField(
        default=False,
        help_text="Prefer to pair these divers together",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["from_diver", "relationship_type"]
        constraints = [
            # No duplicate relationships (same pair, same type)
            models.UniqueConstraint(
                fields=["from_diver", "to_diver", "relationship_type"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_diver_relationship",
            ),
            # Can't have relationship with self
            models.CheckConstraint(
                condition=~Q(from_diver=models.F("to_diver")),
                name="diveops_no_self_relationship",
            ),
        ]
        indexes = [
            models.Index(fields=["from_diver", "to_diver"]),
            models.Index(fields=["relationship_type"]),
        ]

    def __str__(self):
        return f"{self.from_diver.person} - {self.get_relationship_type_display()} - {self.to_diver.person}"

    @classmethod
    def get_or_create_bidirectional(cls, diver1, diver2, relationship_type, **kwargs):
        """Create relationship in both directions."""
        rel1, created1 = cls.objects.get_or_create(
            from_diver=diver1,
            to_diver=diver2,
            relationship_type=relationship_type,
            defaults=kwargs,
        )
        rel2, created2 = cls.objects.get_or_create(
            from_diver=diver2,
            to_diver=diver1,
            relationship_type=relationship_type,
            defaults=kwargs,
        )
        return rel1, rel2, created1 or created2


class DiverRelationshipMeta(BaseModel):
    """DiveOps extension metadata for PartyRelationship.

    Adds dive-specific fields to the canonical django-parties PartyRelationship.
    This follows the primitives architecture: use PartyRelationship for identity
    relationships, extend with domain-specific metadata.

    See: docs/ADR-001-RELATIONSHIP-CONSOLIDATION.md

    Fields extended:
    - priority: For emergency contact ordering (1=primary, 2=secondary, etc.)
    - is_preferred_buddy: For pairing divers together on excursions
    - notes: Dive-specific notes (e.g., "prefers morning dives")

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    party_relationship = models.OneToOneField(
        "django_parties.PartyRelationship",
        on_delete=models.CASCADE,
        related_name="diver_meta",
        help_text="The canonical PartyRelationship being extended",
    )

    # Emergency contact ordering
    priority = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Contact priority (1=primary, 2=secondary). Only for emergency_contact type.",
    )

    # Dive buddy pairing
    is_preferred_buddy = models.BooleanField(
        default=False,
        help_text="Prefer to pair these divers together on excursions",
    )

    # Dive-specific notes (separate from PartyRelationship.title)
    notes = models.TextField(
        blank=True,
        help_text="Dive-specific notes about this relationship",
    )

    class Meta:
        verbose_name = "Diver Relationship Metadata"
        verbose_name_plural = "Diver Relationship Metadata"
        constraints = [
            # Priority only makes sense for emergency contacts
            # (can't enforce at DB level which relationship_type, but we validate in clean())
        ]
        indexes = [
            models.Index(fields=["priority"]),
            models.Index(fields=["is_preferred_buddy"]),
        ]

    def __str__(self):
        return f"DiverMeta for {self.party_relationship}"

    def clean(self):
        """Validate business rules."""
        super().clean()
        # Priority is only meaningful for emergency_contact relationships
        if self.priority is not None:
            if self.party_relationship.relationship_type != "emergency_contact":
                raise ValidationError(
                    {"priority": "Priority is only valid for emergency contact relationships."}
                )


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

    # Protected area integration (optional)
    protected_area = models.ForeignKey(
        "ProtectedArea",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dive_sites",
    )
    protected_area_zone = models.ForeignKey(
        "ProtectedAreaZone",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dive_sites",
    )

    # Photos
    profile_photo = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_site_profile_photos",
        help_text="Primary profile photo for this dive site",
    )

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
            # If protected_area_zone is set, protected_area must be set
            models.CheckConstraint(
                condition=(
                    Q(protected_area_zone__isnull=True) |
                    Q(protected_area__isnull=False)
                ),
                name="diveops_site_zone_requires_area",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["protected_area"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.max_depth_meters}m)"

    def clean(self):
        """Validate zone belongs to protected_area (cross-FK validation)."""
        super().clean()
        if self.protected_area_zone and self.protected_area:
            if self.protected_area_zone.protected_area_id != self.protected_area_id:
                raise ValidationError(
                    "Zone must belong to the selected protected area."
                )

    # Photo helpers
    @property
    def featured_photos(self):
        """Get the 4 featured preview photos, ordered by position."""
        return self.site_photos.filter(
            is_featured=True,
            deleted_at__isnull=True,
        ).select_related("document").order_by("position")[:4]

    @property
    def gallery_photos(self):
        """Get all gallery photos (non-featured), ordered by position."""
        return self.site_photos.filter(
            is_featured=False,
            deleted_at__isnull=True,
        ).select_related("document").order_by("position")

    @property
    def all_photos(self):
        """Get all photos for this site, featured first then gallery."""
        return self.site_photos.filter(
            deleted_at__isnull=True,
        ).select_related("document").order_by("-is_featured", "position")


class DiveSitePhoto(BaseModel):
    """A photo associated with a dive site.

    Photos can be marked as 'featured' (shown in preview carousel)
    or regular gallery photos. Position determines display order.

    Usage:
        # Add a featured photo (positions 1-4 for carousel)
        DiveSitePhoto.objects.create(
            dive_site=site,
            document=photo_doc,
            position=1,
            is_featured=True,
            caption="Beautiful coral reef",
            uploaded_by=request.user,
        )

        # Get featured photos for preview
        site.featured_photos  # Returns up to 4 photos

        # Get full gallery
        site.gallery_photos   # Returns non-featured photos
        site.all_photos       # Returns all photos
    """

    dive_site = models.ForeignKey(
        DiveSite,
        on_delete=models.CASCADE,
        related_name="site_photos",
        help_text="The dive site this photo belongs to",
    )
    document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.CASCADE,
        related_name="dive_site_photos",
        help_text="The photo document",
    )
    position = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order (lower = first). Featured photos use 1-4.",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured photos appear in the preview carousel (max 4)",
    )
    caption = models.CharField(
        max_length=500,
        blank=True,
        help_text="Optional caption for this photo",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_site_photos_uploaded",
        help_text="User who uploaded this photo",
    )

    class Meta:
        constraints = [
            # Position must be unique per dive site for featured photos
            models.UniqueConstraint(
                fields=["dive_site", "position"],
                condition=Q(is_featured=True, deleted_at__isnull=True),
                name="diveops_site_photo_unique_featured_position",
            ),
            # Same document can't be added twice to the same site
            models.UniqueConstraint(
                fields=["dive_site", "document"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_site_photo_unique_document",
            ),
        ]
        indexes = [
            models.Index(fields=["dive_site", "is_featured", "position"]),
        ]
        ordering = ["-is_featured", "position"]

    def __str__(self):
        featured = " (featured)" if self.is_featured else ""
        return f"{self.dive_site.name} - Photo #{self.position}{featured}"


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

    # Optional link to ExcursionSeries (for recurring excursions)
    series = models.ForeignKey(
        "ExcursionSeries",
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
        # DiveSite is defined in this same file - no import needed
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
        from ..exceptions import BookingError

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
        RecurrenceRule,
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
        RecurrenceRule,
        on_delete=models.CASCADE,
        related_name="excursion_series",
    )

    # Template linkage
    excursion_type = models.ForeignKey(
        ExcursionType,
        on_delete=models.PROTECT,
        related_name="series",
        help_text="Product type template for generated excursions",
    )
    dive_site = models.ForeignKey(
        DiveSite,
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
        ExcursionType,
        blank=True,
        related_name="dive_templates",
        help_text="Excursion types that use this dive plan template",
    )

    # Site this plan is designed for (optional for generic templates)
    dive_site = models.ForeignKey(
        DiveSite,
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
        CertificationLevel,
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


# =============================================================================
# Agreement Template (Paperwork Templates)
# =============================================================================


class AgreementTemplate(BaseModel):
    """Template for agreement paperwork (waivers, releases, questionnaires).

    Agreement templates define the reusable content for standard forms that
    divers sign. When a diver needs to sign paperwork, an Agreement is created
    from this template using django_agreements.

    Template types:
    - waiver: Liability waivers/releases
    - medical: Medical questionnaires (RSTC form)
    - briefing: Briefing acknowledgment forms
    - code_of_conduct: Diver code of conduct agreements
    - rental: Equipment rental agreements
    - training: Training/certification agreements

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class TemplateType(models.TextChoices):
        WAIVER = "waiver", "Liability Waiver"
        MEDICAL = "medical", "Medical Questionnaire"
        BRIEFING = "briefing", "Briefing Acknowledgment"
        CODE_OF_CONDUCT = "code_of_conduct", "Diver Code of Conduct"
        RENTAL = "rental", "Equipment Rental Agreement"
        TRAINING = "training", "Training Agreement"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class TargetPartyType(models.TextChoices):
        DIVER = "diver", "Diver"
        EMPLOYEE = "employee", "Employee"
        VENDOR = "vendor", "Vendor"
        ANY = "any", "Any Party"

    class DiverCategory(models.TextChoices):
        """Which category of diver needs this waiver/agreement."""
        ALL = "all", "All Divers"
        CERTIFIED = "certified", "Certified Divers Only"
        STUDENT = "student", "Students in Training"
        DSD = "dsd", "Discover Scuba (DSD/Try Dive)"

    # Ownership
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="agreement_templates",
    )

    # Identity
    name = models.CharField(
        max_length=100,
        help_text="Template name (e.g., 'Standard Liability Release')",
    )
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        help_text="Type of agreement this template is for",
    )
    target_party_type = models.CharField(
        max_length=20,
        choices=TargetPartyType.choices,
        default=TargetPartyType.DIVER,
        help_text="Type of party who should sign this template (diver, employee, vendor)",
    )
    diver_category = models.CharField(
        max_length=20,
        choices=DiverCategory.choices,
        default=DiverCategory.ALL,
        help_text="Which diver category needs this agreement (for waivers)",
    )
    description = models.TextField(
        blank=True,
        help_text="Internal description or notes about this template",
    )

    # Content
    content = models.TextField(
        help_text="The agreement text/content (supports HTML)",
    )

    # Requirements
    requires_signature = models.BooleanField(
        default=True,
        help_text="Does this form require a signature?",
    )
    requires_initials = models.BooleanField(
        default=False,
        help_text="Does this form require initials on each page/section?",
    )
    is_required_for_booking = models.BooleanField(
        default=False,
        help_text="Must this form be signed before diving?",
    )

    # Validity
    validity_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="How many days this agreement is valid (null = never expires)",
    )

    # Versioning
    version = models.CharField(
        max_length=20,
        default="1.0",
        help_text="Version number of this template",
    )

    # Lifecycle
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        constraints = [
            # Only one published template of each type+category per shop
            models.UniqueConstraint(
                fields=["dive_shop", "template_type", "diver_category"],
                condition=Q(status="published") & Q(deleted_at__isnull=True),
                name="diveops_unique_published_template_per_type_category",
            ),
        ]
        indexes = [
            models.Index(fields=["dive_shop", "template_type"]),
            models.Index(fields=["dive_shop", "target_party_type"]),
            models.Index(fields=["dive_shop", "diver_category"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["dive_shop", "template_type", "-version"]

    def __str__(self):
        return f"{self.name} (v{self.version})"

    def publish(self, user):
        """Publish this template, archiving any previous published version."""
        # Archive the currently published template of this type
        AgreementTemplate.objects.filter(
            dive_shop=self.dive_shop,
            template_type=self.template_type,
            status=self.Status.PUBLISHED,
        ).exclude(pk=self.pk).update(status=self.Status.ARCHIVED)

        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.published_by = user
        self.save(update_fields=["status", "published_at", "published_by", "updated_at"])


# =============================================================================
# Signable Agreement Models (Workflow)
# =============================================================================


class SignableAgreement(BaseModel):
    """Agreement instance with workflow: draft → sent → signed → void.

    This model manages the workflow state for agreements that need to be signed.
    The django-agreements primitive is an immutable fact store (append-only ledger)
    with no workflow states. This model provides the workflow layer on top.

    When signed, a ledger_agreement is created in django_agreements.Agreement
    as the immutable record.

    Security:
    - access_token is stored as SHA-256 hash, never raw
    - Token is consumed after signing (cannot be reused)
    - expires_at is enforced at signing time

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        SIGNED = "signed", "Signed"
        VOID = "void", "Void"
        EXPIRED = "expired", "Expired"

    # Source template
    template = models.ForeignKey(
        "AgreementTemplate",
        on_delete=models.PROTECT,
        related_name="signable_agreements",
    )
    template_version = models.CharField(
        max_length=20,
        help_text="Snapshot of template.version at creation time",
    )

    # Party A (the signer) - GenericFK since Party is abstract
    party_a_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    party_a_object_id = models.CharField(max_length=255)
    party_a = GenericForeignKey("party_a_content_type", "party_a_object_id")

    # Party B (optional counter-party) - GenericFK
    party_b_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    party_b_object_id = models.CharField(max_length=255, blank=True)
    party_b = GenericForeignKey("party_b_content_type", "party_b_object_id")

    # Related object (booking, enrollment, etc.) - GenericFK
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    related_object_id = models.CharField(max_length=255, blank=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    # Content
    content_snapshot = models.TextField(
        help_text="Rendered content at send time (editable until signed)",
    )
    content_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of content_snapshot",
    )

    # Workflow state
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    # Delivery tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    delivery_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="How agreement was delivered: email, link, in_person",
    )

    # Token for signing URL
    access_token = models.CharField(
        max_length=64,
        blank=True,
        help_text="Raw token for signing URL (displayed to staff)",
    )
    access_token_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="SHA-256 hash of access token for verification",
    )
    token_consumed = models.BooleanField(
        default=False,
        help_text="Token invalidated after signing (cannot be reused)",
    )

    # Signature tracking (metadata only - image stored as Document)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by_name = models.CharField(max_length=255, blank=True)
    signed_ip = models.GenericIPAddressField(null=True, blank=True)
    signed_user_agent = models.TextField(blank=True)

    # Enhanced digital fingerprint for legal validity
    signed_screen_resolution = models.CharField(max_length=20, blank=True, help_text="e.g., 1920x1080")
    signed_timezone = models.CharField(max_length=100, blank=True, help_text="e.g., America/New_York")
    signed_timezone_offset = models.SmallIntegerField(null=True, blank=True, help_text="UTC offset in minutes")
    signed_language = models.CharField(max_length=50, blank=True, help_text="Browser language preference")
    signed_platform = models.CharField(max_length=100, blank=True, help_text="OS/Platform")
    signed_device_memory = models.CharField(max_length=20, blank=True, help_text="Device memory in GB")
    signed_hardware_concurrency = models.PositiveSmallIntegerField(null=True, blank=True, help_text="CPU cores")
    signed_touch_support = models.BooleanField(null=True, blank=True, help_text="Touch screen device")
    signed_canvas_fingerprint = models.CharField(max_length=64, blank=True, help_text="SHA-256 of canvas fingerprint")
    signed_geolocation = models.JSONField(null=True, blank=True, help_text="Lat/long if permitted")

    # E-Sign consent tracking (for legal compliance)
    agreed_to_terms = models.BooleanField(
        default=False,
        help_text="Signer checked 'I agree to be bound by its terms'",
    )
    agreed_to_esign = models.BooleanField(
        default=False,
        help_text="Signer checked 'I consent to sign electronically'",
    )

    # Signature image stored as Document (role=signature)
    signature_document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signature_for_agreements",
    )

    # Signed PDF document
    signed_document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signed_agreements",
    )

    # Linked immutable record (django-agreements primitive)
    ledger_agreement = models.ForeignKey(
        "django_agreements.Agreement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signable_agreements",
    )

    # Expiration - MUST be enforced at signing time
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this agreement expires (enforced at signing)",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["party_a_content_type", "party_a_object_id"]),
            models.Index(fields=["related_content_type", "related_object_id"]),
            models.Index(fields=["access_token_hash"]),
            models.Index(fields=["expires_at"]),
        ]
        constraints = [
            # WORKFLOW INTEGRITY: status='signed' requires signed_at
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(signed_at__isnull=False),
                name="signable_signed_requires_signed_at",
            ),
            # WORKFLOW INTEGRITY: status='sent' requires sent_at
            models.CheckConstraint(
                condition=~Q(status="sent") | Q(sent_at__isnull=False),
                name="signable_sent_requires_sent_at",
            ),
            # WORKFLOW INTEGRITY: status in (sent, signed) requires token hash
            models.CheckConstraint(
                condition=~Q(status__in=["sent", "signed"]) | ~Q(access_token_hash=""),
                name="signable_sent_signed_requires_token",
            ),
            # WORKFLOW INTEGRITY: status='signed' requires ledger_agreement
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(ledger_agreement__isnull=False),
                name="signable_signed_requires_ledger",
            ),
            # Content hash must be valid SHA-256 (64 hex chars)
            models.CheckConstraint(
                condition=Q(content_hash__regex=r"^[a-f0-9]{64}$"),
                name="signable_valid_content_hash",
            ),
            # LEGAL COMPLIANCE: status='signed' requires agreed_to_terms=True
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(agreed_to_terms=True),
                name="signable_signed_requires_terms_consent",
            ),
            # LEGAL COMPLIANCE: status='signed' requires agreed_to_esign=True
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(agreed_to_esign=True),
                name="signable_signed_requires_esign_consent",
            ),
            # DIGITAL PROOF: status='signed' requires IP address
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(signed_ip__isnull=False),
                name="signable_signed_requires_ip",
            ),
            # DIGITAL PROOF: status='signed' requires user agent fingerprint
            models.CheckConstraint(
                condition=~Q(status="signed") | ~Q(signed_user_agent=""),
                name="signable_signed_requires_user_agent",
            ),
            # DIGITAL PROOF: status='signed' requires signer name
            models.CheckConstraint(
                condition=~Q(status="signed") | ~Q(signed_by_name=""),
                name="signable_signed_requires_signer_name",
            ),
            # DEDUPING: Only one pending agreement per template+party+related_object
            # Partial unique constraint for status in (draft, sent)
            # nulls_distinct=False ensures NULL values are treated as equal for deduping
            models.UniqueConstraint(
                fields=[
                    "template",
                    "party_a_content_type",
                    "party_a_object_id",
                    "related_content_type",
                    "related_object_id",
                ],
                condition=Q(status__in=["draft", "sent"]),
                name="signable_unique_pending_per_party_object",
                nulls_distinct=False,
            ),
        ]

    def __str__(self):
        return f"{self.template.name} for {self.party_a} ({self.status})"

    @staticmethod
    def generate_token() -> tuple[str, str]:
        """Generate cryptographically random token and its hash.

        Returns:
            tuple: (raw_token, token_hash)
            - raw_token: URL-safe token to send to signer (returned ONCE)
            - token_hash: SHA-256 hash to store in database
        """
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token, token_hash

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for comparison."""
        return hashlib.sha256(token.encode()).hexdigest()

    def verify_token(self, token: str) -> bool:
        """Verify token matches stored hash and is not consumed.

        Args:
            token: Raw token from signing URL

        Returns:
            bool: True if token is valid and not consumed
        """
        if self.token_consumed:
            return False
        return secrets.compare_digest(
            self.access_token_hash,
            self.hash_token(token),
        )


class SignableAgreementRevision(BaseModel):
    """Immutable record of content changes for auditability.

    Every edit to a SignableAgreement's content creates a revision record.
    This provides a complete audit trail of all changes made before signing.

    Stores the content_before to enable diff viewing between revisions.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    agreement = models.ForeignKey(
        SignableAgreement,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    previous_content_hash = models.CharField(max_length=64)
    new_content_hash = models.CharField(max_length=64)
    content_before = models.TextField(
        blank=True,
        help_text="Content snapshot before this revision (for diff viewing)",
    )
    change_note = models.TextField(
        help_text="Required explanation of why the change was made",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )

    class Meta:
        ordering = ["revision_number"]
        unique_together = [["agreement", "revision_number"]]
        constraints = [
            # Change note is required (non-empty)
            models.CheckConstraint(
                condition=~Q(change_note=""),
                name="revision_requires_change_note",
            ),
        ]

    def __str__(self):
        return f"Revision {self.revision_number} of {self.agreement}"


# =============================================================================
# Protected Area Models (Regulatory Framework)
# =============================================================================


class ProtectedArea(BaseModel):
    """Hierarchical protected area with regulatory authority.

    Represents protected areas like Parque Nacional Arrecife de Puerto Morelos
    or Reserva de la Biosfera del Caribe Mexicano. Areas can be nested:
    - A Biosphere Reserve can be parent of multiple parks
    - Parks can have zones
    - Rules and fees can be set at any level and inherit down

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class DesignationType(models.TextChoices):
        NATIONAL_PARK = "national_park", "National Park"
        MARINE_PARK = "marine_park", "Marine Park"
        MARINE_RESERVE = "marine_reserve", "Marine Reserve"
        BIOSPHERE_RESERVE = "biosphere_reserve", "Biosphere Reserve"
        PROTECTED_AREA = "protected_area", "Protected Natural Area"
        SANCTUARY = "sanctuary", "Marine Sanctuary"

    # Hierarchy - self-referential FK for parent/child areas
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent area (e.g., biosphere reserve containing parks)",
    )

    # Identity
    name = models.CharField(max_length=200)
    code = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    # Location reference (approximate center)
    place = models.ForeignKey(
        "django_geo.Place",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="protected_areas",
    )

    # Boundary file (KML/KMZ)
    boundary_file = models.FileField(
        upload_to="protected_areas/boundaries/%Y/",
        blank=True,
        null=True,
    )
    boundary_filename = models.CharField(max_length=255, blank=True)

    # Authority/Governance
    governing_authority = models.CharField(max_length=200, blank=True)
    authority_contact = models.TextField(blank=True)
    official_website = models.URLField(blank=True)

    # Regulatory info
    established_date = models.DateField(null=True, blank=True)
    designation_type = models.CharField(
        max_length=50,
        choices=DesignationType.choices,
        default=DesignationType.PROTECTED_AREA,
    )

    max_divers_per_site = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["parent"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_ancestors(self) -> list["ProtectedArea"]:
        """Return parent chain from immediate parent to root.

        Returns:
            List of ProtectedArea instances, starting with immediate parent
            and ending with the root (topmost) ancestor.
        """
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors


# Backwards compatibility alias
MarinePark = ProtectedArea


class ProtectedAreaZone(BaseModel):
    """Zone within a protected area with specific rules.

    Protected areas are divided into zones with different use restrictions:
    - Core (no-take): No extractive activities
    - Buffer: Limited activities allowed
    - Use: Recreational activities permitted
    - Restoration: Areas under restoration
    - Research: Scientific research zones

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class ZoneType(models.TextChoices):
        CORE = "core", "Core Zone (No-Take)"
        BUFFER = "buffer", "Buffer Zone"
        USE = "use", "Use Zone (Recreational)"
        RESTORATION = "restoration", "Restoration Zone"
        RESEARCH = "research", "Research Zone"

    protected_area = models.ForeignKey(
        ProtectedArea,
        on_delete=models.CASCADE,
        related_name="zones",
    )
    name = models.CharField(max_length=100)
    code = models.SlugField()
    zone_type = models.CharField(
        max_length=20,
        choices=ZoneType.choices,
        default=ZoneType.USE,
    )

    # Boundary (KML/KMZ for zone)
    boundary_file = models.FileField(
        upload_to="protected_areas/zones/%Y/",
        blank=True,
        null=True,
    )

    # GEOMETRY HOOK: For future PostGIS integration
    # NOTE: KML parsing is NOT implemented - this is for manual entry or future use
    boundary_geojson = models.JSONField(
        null=True,
        blank=True,
        help_text="GeoJSON geometry for zone boundary (optional, manual entry)",
    )

    # Zone-level limits
    max_divers = models.PositiveIntegerField(null=True, blank=True)
    diving_allowed = models.BooleanField(default=True)
    anchoring_allowed = models.BooleanField(default=False)
    fishing_allowed = models.BooleanField(default=False)
    requires_guide = models.BooleanField(default=True)
    requires_permit = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["protected_area", "code"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_zone_code_per_area",
            ),
        ]
        indexes = [
            models.Index(fields=["protected_area", "zone_type"]),
        ]
        ordering = ["protected_area", "name"]

    def __str__(self):
        return f"{self.name} ({self.protected_area.name})"


# Backwards compatibility alias
ParkZone = ProtectedAreaZone


class ProtectedAreaRule(BaseModel):
    """Effective-dated enforceable rule for a protected area.

    Rules define what activities are permitted/prohibited and under what
    conditions. Rules can be area-wide or zone-specific, and have enforcement
    levels (info, warn, block).

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class RuleType(models.TextChoices):
        MAX_DEPTH = "max_depth", "Maximum Depth"
        MAX_DIVERS = "max_divers", "Maximum Divers"
        CERTIFICATION = "certification", "Certification Required"
        EQUIPMENT = "equipment", "Equipment Requirement"
        TIME = "time", "Time Restriction"
        ACTIVITY = "activity", "Activity Restriction"
        CONDUCT = "conduct", "Code of Conduct"

    class EnforcementLevel(models.TextChoices):
        INFO = "info", "Information Only"
        WARN = "warn", "Warning (Allow Override)"
        BLOCK = "block", "Block (Hard Enforcement)"

    class AppliesTo(models.TextChoices):
        DIVER = "diver", "Individual Diver"
        GROUP = "group", "Dive Group"
        VESSEL = "vessel", "Vessel"
        OPERATOR = "operator", "Operator/Shop"

    class Activity(models.TextChoices):
        DIVING = "diving", "Diving"
        SNORKELING = "snorkeling", "Snorkeling"
        BOATING = "boating", "Boating"
        TRAINING = "training", "Training"
        ALL = "all", "All Activities"

    class Operator(models.TextChoices):
        """Normalized comparison operators."""
        LTE = "lte", "Less than or equal (<=)"
        GTE = "gte", "Greater than or equal (>=)"
        EQ = "eq", "Equals (=)"
        IN = "in", "In list"
        CONTAINS = "contains", "Contains"
        REQUIRED_TRUE = "required_true", "Must be true"

    # Scope: area-wide or zone-specific
    protected_area = models.ForeignKey(
        ProtectedArea,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    zone = models.ForeignKey(
        ProtectedAreaZone,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="rules",
        help_text="Null = applies area-wide",
    )

    # Rule definition
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    applies_to = models.CharField(max_length=20, choices=AppliesTo.choices)
    activity = models.CharField(
        max_length=20,
        choices=Activity.choices,
        default=Activity.ALL,
        help_text="Which activity this rule applies to",
    )
    subject = models.CharField(
        max_length=100,
        help_text="What the rule governs (e.g., 'night diving', 'spearfishing')",
    )
    operator = models.CharField(
        max_length=20,
        choices=Operator.choices,
        blank=True,
        default="",
        help_text="Comparison operator for rule evaluation",
    )
    value = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Value for comparison (e.g., '18' for max_depth lte 18)",
    )
    details = models.TextField(blank=True, help_text="Full rule text")

    # Effective dating
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)

    # Enforcement
    enforcement_level = models.CharField(
        max_length=10,
        choices=EnforcementLevel.choices,
        default=EnforcementLevel.WARN,
    )

    # Source document (optional FK to django_documents.Document)
    source_document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="park_rules",
        help_text="Official document defining this rule",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["protected_area", "effective_start"]),
            models.Index(fields=["zone", "effective_start"]),
            models.Index(fields=["rule_type"]),
            models.Index(fields=["activity"]),
        ]
        ordering = ["-effective_start", "rule_type"]

    def __str__(self):
        zone_name = f" ({self.zone.name})" if self.zone else ""
        return f"{self.protected_area.name}{zone_name}: {self.subject}"


# Backwards compatibility alias
ParkRule = ProtectedAreaRule


class ProtectedAreaFeeSchedule(BaseModel):
    """Fee schedule for a protected area with stratified tiers.

    Fee schedules define categories of fees (diving, snorkeling, etc.)
    and contain tiers for different diver categories.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class FeeType(models.TextChoices):
        PER_PERSON = "per_person", "Per Person"
        PER_BOAT = "per_boat", "Per Boat"
        PER_TRIP = "per_trip", "Per Trip"
        PER_DAY = "per_day", "Per Day"
        PER_ACTIVITY = "per_activity", "Per Activity"

    class AppliesTo(models.TextChoices):
        DIVING = "diving", "Diving"
        SNORKELING = "snorkeling", "Snorkeling"
        KAYAKING = "kayaking", "Kayaking"
        FISHING = "fishing", "Fishing"
        ALL = "all", "All Activities"

    # Scope
    protected_area = models.ForeignKey(
        ProtectedArea,
        on_delete=models.CASCADE,
        related_name="fee_schedules",
    )
    zone = models.ForeignKey(
        ProtectedAreaZone,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fee_schedules",
        help_text="Null = applies area-wide",
    )

    # Schedule identity
    name = models.CharField(
        max_length=100,
        help_text="e.g., 'Diver Admission 2024'",
    )
    fee_type = models.CharField(max_length=20, choices=FeeType.choices)
    applies_to = models.CharField(max_length=20, choices=AppliesTo.choices)

    # Effective dating
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)

    # Currency and collector
    currency = models.CharField(max_length=3, default="MXN")
    collector = models.CharField(
        max_length=100,
        blank=True,
        help_text="Who collects this fee (e.g., 'CONANP', 'Dive Shop')",
    )

    # Commerce linkage (optional)
    catalog_item = models.ForeignKey(
        "django_catalog.CatalogItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="park_fee_schedules",
        help_text="Catalog item for auto-adding to pricing",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["protected_area", "effective_start"]),
            models.Index(fields=["applies_to"]),
        ]
        ordering = ["-effective_start", "name"]

    def __str__(self):
        return f"{self.name} ({self.protected_area.name})"


# Backwards compatibility alias
ParkFeeSchedule = ProtectedAreaFeeSchedule


class ProtectedAreaFeeTier(BaseModel):
    """Stratified fee tier within a schedule.

    Fee tiers define pricing for different diver categories:
    - Tourist (foreign visitors)
    - National (citizens)
    - Local (residents)
    - Student, Senior, Child, Infant

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class TierCode(models.TextChoices):
        TOURIST = "tourist", "Tourist (Foreign)"
        NATIONAL = "national", "National"
        LOCAL = "local", "Local Resident"
        STUDENT = "student", "Student"
        SENIOR = "senior", "Senior"
        CHILD = "child", "Child"
        INFANT = "infant", "Infant (Free)"

    schedule = models.ForeignKey(
        ProtectedAreaFeeSchedule,
        on_delete=models.CASCADE,
        related_name="tiers",
    )
    tier_code = models.CharField(max_length=20, choices=TierCode.choices)
    label = models.CharField(max_length=50, help_text="Display label")
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Age-based eligibility (optional)
    age_min = models.PositiveSmallIntegerField(null=True, blank=True)
    age_max = models.PositiveSmallIntegerField(null=True, blank=True)

    # Proof requirements
    requires_proof = models.BooleanField(default=False)
    proof_notes = models.TextField(
        blank=True,
        help_text="What proof is needed (e.g., 'INE card', 'Student ID')",
    )

    # Selection priority (lower = checked first)
    priority = models.PositiveSmallIntegerField(default=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "tier_code"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_fee_tier_per_schedule",
            ),
        ]
        ordering = ["priority", "tier_code"]

    def __str__(self):
        return f"{self.label}: {self.amount} {self.schedule.currency}"


# Backwards compatibility alias
ParkFeeTier = ProtectedAreaFeeTier


class DiverEligibilityProof(BaseModel):
    """Verified proof of diver eligibility for fee tiers.

    Tracks documents that prove a diver's eligibility for discounted
    fee tiers (national ID, student ID, senior ID, etc.).

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class ProofType(models.TextChoices):
        STUDENT_ID = "student_id", "Student ID"
        NATIONAL_ID = "national_id", "National ID (INE/IFE)"
        RESIDENT_CARD = "resident_card", "Resident Card"
        LOCAL_ADDRESS = "local_address", "Local Address Proof"
        PASSPORT = "passport", "Passport"
        BIRTH_CERT = "birth_cert", "Birth Certificate"
        SENIOR_ID = "senior_id", "Senior ID (INAPAM)"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.CASCADE,
        related_name="eligibility_proofs",
    )
    proof_type = models.CharField(max_length=20, choices=ProofType.choices)

    # Document link
    document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eligibility_proofs",
    )

    # Verification status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_eligibility_proofs",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Validity - VERIFIED is valid only if expires_at is null or >= as_of
    expires_at = models.DateField(null=True, blank=True)

    # Metadata
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["diver", "status"]),
            models.Index(fields=["proof_type"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["-verified_at", "-created_at"]

    def __str__(self):
        return f"{self.diver}: {self.get_proof_type_display()} ({self.get_status_display()})"

    def is_valid_as_of(self, as_of: date | None = None) -> bool:
        """Check if proof is valid as of a date.

        A proof is valid if:
        - status == VERIFIED
        - expires_at is null OR expires_at >= as_of
        """
        if self.status != self.Status.VERIFIED:
            return False
        if as_of is None:
            as_of = date.today()
        if self.expires_at is None:
            return True
        return self.expires_at >= as_of


# =============================================================================
# Unified Permit Model (Replaces ProtectedAreaGuideCredential + VesselPermit)
# =============================================================================


class ProtectedAreaPermit(BaseModel):
    """Unified authorization model for operating in a protected area.

    Replaces separate ProtectedAreaGuideCredential and VesselPermit models
    with a single permit model that uses permit_type to distinguish.

    Holder fields are constrained by permit_type:
    - GUIDE: diver required, vessel_name/organization must be null
    - VESSEL: vessel_name required, diver must be null

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class PermitType(models.TextChoices):
        GUIDE = "guide", "Guide Credential"
        VESSEL = "vessel", "Vessel Permit"
        PHOTOGRAPHY = "photography", "Photography Permit"
        DIVING = "diving", "Ojo de Agua Permit"

    # Core fields - required for all permit types
    protected_area = models.ForeignKey(
        ProtectedArea,
        on_delete=models.CASCADE,
        related_name="permits",
    )
    permit_type = models.CharField(
        max_length=20,
        choices=PermitType.choices,
    )
    permit_number = models.CharField(
        max_length=50,
        help_text="Unique permit/credential number within area and type",
    )
    issued_at = models.DateField()
    expires_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Zone authorization (optional, applies to both types)
    authorized_zones = models.ManyToManyField(
        ProtectedAreaZone,
        blank=True,
        related_name="permits",
        help_text="Zones this permit authorizes (empty = all zones)",
    )

    # Holder fields - constrained by permit_type via CheckConstraint
    # GUIDE/PHOTOGRAPHY permits: diver required
    # DIVING permits: diver OR organization required
    diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="area_permits",
        help_text="Required for GUIDE/PHOTOGRAPHY permits, optional for DIVING",
    )
    # VESSEL permits: vessel_name and optionally organization
    vessel_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Required for VESSEL permits only",
    )
    vessel_registration = models.CharField(
        max_length=50,
        blank=True,
        help_text="Vessel registration number (VESSEL permits)",
    )
    # Organization - for VESSEL (optional) and DIVING (when not individual)
    organization = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="area_permits",
        help_text="Optional for VESSEL, required for DIVING if no diver",
    )

    # Vessel-specific: max divers allowed
    max_divers = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max divers capacity (VESSEL permits)",
    )

    class Meta:
        constraints = [
            # Unique permit number per area and type
            models.UniqueConstraint(
                fields=["protected_area", "permit_type", "permit_number"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_permit_number_per_area_type",
            ),
            # One permit per diver per area (for GUIDE type)
            models.UniqueConstraint(
                fields=["protected_area", "diver"],
                condition=Q(deleted_at__isnull=True, permit_type="guide"),
                name="diveops_unique_guide_permit_per_diver_area",
            ),
            # GUIDE permits MUST have diver set
            models.CheckConstraint(
                condition=~Q(permit_type="guide") | Q(diver__isnull=False),
                name="diveops_guide_permit_requires_diver",
            ),
            # GUIDE permits must NOT have vessel_name
            models.CheckConstraint(
                condition=~Q(permit_type="guide") | Q(vessel_name=""),
                name="diveops_guide_permit_no_vessel",
            ),
            # VESSEL permits MUST have vessel_name
            models.CheckConstraint(
                condition=~Q(permit_type="vessel") | ~Q(vessel_name=""),
                name="diveops_vessel_permit_requires_vessel",
            ),
            # VESSEL permits must NOT have diver
            models.CheckConstraint(
                condition=~Q(permit_type="vessel") | Q(diver__isnull=True),
                name="diveops_vessel_permit_no_diver",
            ),
            # PHOTOGRAPHY permits MUST have diver set (like GUIDE)
            models.CheckConstraint(
                condition=~Q(permit_type="photography") | Q(diver__isnull=False),
                name="diveops_photography_permit_requires_diver",
            ),
            # PHOTOGRAPHY permits must NOT have vessel_name (like GUIDE)
            models.CheckConstraint(
                condition=~Q(permit_type="photography") | Q(vessel_name=""),
                name="diveops_photography_permit_no_vessel",
            ),
            # DIVING permits MUST have diver OR organization (flexible holder)
            models.CheckConstraint(
                condition=~Q(permit_type="diving") | Q(diver__isnull=False) | Q(organization__isnull=False),
                name="diveops_diving_permit_requires_holder",
            ),
            # DIVING permits must NOT have vessel_name
            models.CheckConstraint(
                condition=~Q(permit_type="diving") | Q(vessel_name=""),
                name="diveops_diving_permit_no_vessel",
            ),
            # expires_at must be >= issued_at (if set)
            models.CheckConstraint(
                condition=Q(expires_at__isnull=True) | Q(expires_at__gte=models.F("issued_at")),
                name="diveops_permit_expires_after_issued",
            ),
        ]
        indexes = [
            models.Index(fields=["protected_area", "permit_type", "is_active"]),
            models.Index(fields=["diver"]),
            models.Index(fields=["organization"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["protected_area", "permit_type", "permit_number"]

    def __str__(self):
        if self.permit_type == self.PermitType.GUIDE:
            return f"{self.diver} - {self.protected_area.name} Guide"
        elif self.permit_type == self.PermitType.VESSEL:
            return f"{self.vessel_name} ({self.protected_area.name})"
        elif self.permit_type == self.PermitType.PHOTOGRAPHY:
            return f"{self.diver} - {self.protected_area.name} Photography"
        elif self.permit_type == self.PermitType.DIVING:
            holder = self.diver or self.organization
            return f"{holder} - {self.protected_area.name} Diving"
        else:
            return f"{self.permit_number} ({self.protected_area.name})"

    def clean(self):
        """Validate permit holder fields match permit_type."""
        super().clean()
        errors = {}

        if self.permit_type == self.PermitType.GUIDE:
            if not self.diver_id:
                errors["diver"] = "Guide permits require a diver."
            if self.vessel_name:
                errors["vessel_name"] = "Guide permits cannot have a vessel name."
            # Validate DM or higher for guide permits
            if self.diver_id:
                min_rank = 5  # DM rank per DiverProfile.LEVEL_HIERARCHY
                has_dm_or_higher = self.diver.certifications.filter(
                    level__rank__gte=min_rank,
                    deleted_at__isnull=True,
                ).exists()
                if not has_dm_or_higher:
                    errors["diver"] = "Guide must have Divemaster (DM) or higher certification."

        elif self.permit_type == self.PermitType.VESSEL:
            if not self.vessel_name:
                errors["vessel_name"] = "Vessel permits require a vessel name."
            if self.diver_id:
                errors["diver"] = "Vessel permits cannot have a diver."

        if errors:
            raise ValidationError(errors)

    def can_operate_in_zone(self, zone: "ProtectedAreaZone") -> bool:
        """Check if permit authorizes operation in a specific zone."""
        if not self.authorized_zones.exists():
            return True  # No zone restriction = all zones
        return self.authorized_zones.filter(pk=zone.pk).exists()

    @property
    def holder_display(self) -> str:
        """Return display name for the permit holder."""
        if self.permit_type == self.PermitType.GUIDE:
            return str(self.diver.person) if self.diver else ""
        else:
            parts = [self.vessel_name]
            if self.organization:
                parts.append(f"({self.organization.name})")
            return " ".join(parts)


class GuidePermitDetails(BaseModel):
    """Extended details for GUIDE permits.

    OneToOne with ProtectedAreaPermit for guide-specific fields that don't
    apply to other permit types.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    permit = models.OneToOneField(
        ProtectedAreaPermit,
        on_delete=models.CASCADE,
        related_name="guide_details",
        limit_choices_to={"permit_type": "guide"},
    )

    # Carta evaluación (signed by boat owner - can be self if owner)
    carta_eval_agreement = models.ForeignKey(
        "django_agreements.Agreement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guide_carta_evals_v2",
        help_text="Signed carta evaluación document",
    )
    carta_eval_signed_by = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signed_carta_evals_v2",
        help_text="Boat owner who signed (can be the guide themselves)",
    )
    carta_eval_signed_at = models.DateField(null=True, blank=True)
    is_owner = models.BooleanField(
        default=False,
        help_text="True if this guide is also the boat owner",
    )

    # Course refresher tracking
    last_refresher_at = models.DateField(
        null=True,
        blank=True,
        help_text="Date of last park refresher course",
    )
    next_refresher_due_at = models.DateField(
        null=True,
        blank=True,
        help_text="When next refresher is due",
    )

    # Suspension tracking
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["next_refresher_due_at"]),
        ]

    def __str__(self):
        return f"Guide Details for {self.permit}"

    def clean(self):
        """Validate this is attached to a GUIDE permit."""
        super().clean()
        if self.permit_id and self.permit.permit_type != ProtectedAreaPermit.PermitType.GUIDE:
            raise ValidationError(
                "GuidePermitDetails can only be attached to GUIDE permits."
            )

    @property
    def is_refresher_due(self) -> bool:
        """Check if refresher course is overdue."""
        if not self.next_refresher_due_at:
            return False
        return date.today() > self.next_refresher_due_at


# =============================================================================
# Pricing Models (from diveops.pricing submodule)
# =============================================================================

# Note: Pricing models are discovered automatically via primitives_testbed.pricing
# in INSTALLED_APPS. Importing here would cause circular imports.
# DiverEquipmentRental is in primitives_testbed.pricing.models


# =============================================================================
# Document Retention Policy Models (overlay on django-documents)
# =============================================================================


class DocumentRetentionPolicy(BaseModel):
    """Defines retention rules for documents by type.

    Overlay model that extends django-documents with retention policies.
    Used for compliance with regulations like GDPR, HIPAA, IRS requirements.

    Default behavior: 30 days in Trash before permanent deletion.
    Policies can override this per document type.
    """

    document_type = models.CharField(
        max_length=100,
        unique=True,
        help_text="Document type this policy applies to (e.g., 'agreement', 'certification')",
    )
    retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days to retain after creation (null = keep forever)",
    )
    trash_retention_days = models.PositiveIntegerField(
        default=30,
        help_text="Days to keep in Trash before auto-delete (default 30)",
    )
    legal_basis = models.CharField(
        max_length=200,
        blank=True,
        help_text="Regulation/standard requiring this retention (e.g., 'IRS 7-year rule', 'PADI records')",
    )
    description = models.TextField(
        blank=True,
        help_text="Explanation of why this retention period is required",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this policy is currently enforced",
    )

    class Meta:
        verbose_name = "Document Retention Policy"
        verbose_name_plural = "Document Retention Policies"
        ordering = ["document_type"]

    def __str__(self):
        if self.retention_days:
            return f"{self.document_type}: {self.retention_days} days"
        return f"{self.document_type}: keep forever"


class DocumentLegalHold(BaseModel):
    """Prevents deletion of a specific document.

    Legal holds override retention policies and prevent any deletion
    (including from Trash) until the hold is released.

    Use cases:
    - Litigation hold
    - Regulatory investigation
    - Audit preservation
    - Insurance claim
    """

    document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.CASCADE,
        related_name="legal_holds",
        help_text="Document under legal hold",
    )
    reason = models.CharField(
        max_length=200,
        help_text="Reason for the hold (e.g., 'Litigation: Smith v. DiveShop')",
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Case/ticket/reference number",
    )
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_holds_placed",
        help_text="User who placed the hold",
    )
    placed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the hold was placed",
    )
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_holds_released",
        help_text="User who released the hold",
    )
    released_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the hold was released (null = still active)",
    )
    release_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reason for releasing the hold",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this hold",
    )

    class Meta:
        verbose_name = "Document Legal Hold"
        verbose_name_plural = "Document Legal Holds"
        ordering = ["-placed_at"]
        indexes = [
            models.Index(fields=["document", "released_at"]),
        ]

    def __str__(self):
        status = "ACTIVE" if self.is_active else "Released"
        return f"{self.document.filename}: {self.reason} [{status}]"

    @property
    def is_active(self):
        """Check if hold is still active."""
        return self.released_at is None

    def release(self, user, reason=""):
        """Release the hold."""
        if self.released_at:
            raise ValueError("Hold already released")
        self.released_by = user
        self.released_at = timezone.now()
        self.release_reason = reason
        self.save(update_fields=["released_by", "released_at", "release_reason", "updated_at"])

    @classmethod
    def document_has_active_hold(cls, document):
        """Check if a document has any active legal holds."""
        return cls.objects.filter(
            document=document,
            released_at__isnull=True,
            deleted_at__isnull=True,
        ).exists()


# =============================================================================
# Photo Tagging
# =============================================================================


class PhotoTagQuerySet(models.QuerySet):
    """Custom queryset for PhotoTag model."""

    def for_document(self, document):
        """Return tags for a specific document."""
        return self.filter(document=document)

    def for_diver(self, diver):
        """Return tags for a specific diver."""
        return self.filter(diver=diver)


class PhotoTag(BaseModel):
    """Tag a diver in a photo.

    Links documents (photos) to divers, optionally with position
    coordinates for face-tagging functionality.

    Usage:
        PhotoTag.objects.create(
            document=photo_doc,
            diver=diver_profile,
            tagged_by=request.user,
        )

        # Get all divers tagged in a photo
        tags = PhotoTag.objects.for_document(photo)
        divers = [tag.diver for tag in tags]

        # Get all photos of a diver
        tags = PhotoTag.objects.for_diver(diver)
        photos = [tag.document for tag in tags]
    """

    document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.CASCADE,
        related_name="photo_tags",
        help_text="The photo document",
    )
    diver = models.ForeignKey(
        "DiverProfile",
        on_delete=models.CASCADE,
        related_name="photo_tags",
        help_text="The diver tagged in this photo",
    )
    tagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="photo_tags_created",
        help_text="User who created this tag",
    )

    # Optional position for face-tagging (percentages of image dimensions)
    position_x = models.FloatField(
        null=True,
        blank=True,
        help_text="X position as percentage (0-100) from left edge",
    )
    position_y = models.FloatField(
        null=True,
        blank=True,
        help_text="Y position as percentage (0-100) from top edge",
    )

    objects = PhotoTagQuerySet.as_manager()

    class Meta:
        verbose_name = "Photo Tag"
        verbose_name_plural = "Photo Tags"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document"]),
            models.Index(fields=["diver"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "diver"],
                name="phototag_unique_diver_per_photo",
            ),
        ]

    def __str__(self):
        return f"{self.diver} in {self.document.filename}"


class DiveSitePhotoTagQuerySet(models.QuerySet):
    """Custom queryset for DiveSitePhotoTag model."""

    def for_document(self, document):
        """Return tags for a specific document."""
        return self.filter(document=document)

    def for_dive_site(self, dive_site):
        """Return tags for a specific dive site."""
        return self.filter(dive_site=dive_site)


class DiveSitePhotoTag(BaseModel):
    """Tag a dive site in a photo.

    Links documents (photos) to dive sites, allowing photos to be
    associated with locations shown in them.

    Usage:
        DiveSitePhotoTag.objects.create(
            document=photo_doc,
            dive_site=dive_site,
            tagged_by=request.user,
        )

        # Get all dive sites tagged in a photo
        tags = DiveSitePhotoTag.objects.for_document(photo)
        sites = [tag.dive_site for tag in tags]

        # Get all photos of a dive site (via tags, not DiveSitePhoto)
        tags = DiveSitePhotoTag.objects.for_dive_site(site)
        photos = [tag.document for tag in tags]
    """

    document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.CASCADE,
        related_name="dive_site_tags",
        help_text="The photo document",
    )
    dive_site = models.ForeignKey(
        "DiveSite",
        on_delete=models.CASCADE,
        related_name="photo_tags",
        help_text="The dive site tagged in this photo",
    )
    tagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_site_photo_tags_created",
        help_text="User who created this tag",
    )

    objects = DiveSitePhotoTagQuerySet.as_manager()

    class Meta:
        verbose_name = "Dive Site Photo Tag"
        verbose_name_plural = "Dive Site Photo Tags"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document"]),
            models.Index(fields=["dive_site"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "dive_site"],
                name="divesitephototag_unique_site_per_photo",
            ),
        ]

    def __str__(self):
        return f"{self.dive_site.name} in {self.document.filename}"


# =============================================================================
# Media Link (Generic Linking with Provenance)
# =============================================================================


class MediaLinkSource(models.TextChoices):
    """How a media link was created."""
    DIRECT = "direct", "Direct"
    DERIVED_FROM_EXCURSION = "derived_from_excursion", "From Excursion"


class MediaLinkQuerySet(models.QuerySet):
    """Custom queryset for MediaLink model."""

    def for_media_asset(self, media_asset):
        """Return links for a specific media asset."""
        return self.filter(media_asset=media_asset)

    def direct(self):
        """Return only direct links (not derived)."""
        return self.filter(link_source=MediaLinkSource.DIRECT)

    def derived(self):
        """Return only derived links."""
        return self.filter(link_source=MediaLinkSource.DERIVED_FROM_EXCURSION)

    def for_target(self, target):
        """Return links to a specific target object."""
        ct = ContentType.objects.get_for_model(target)
        return self.filter(content_type=ct, object_id=str(target.pk))


class MediaLink(BaseModel):
    """Link a MediaAsset to any entity via GenericFK.

    IMPORTANT: Both direct and derived links can coexist for the same target.
    This allows a user to directly link a photo to a diver, AND that same
    photo can also have derived links from excursion tagging.

    The UniqueConstraint includes link_source and source_excursion to allow:
    - One direct link per (media_asset, target)
    - One derived link per (media_asset, target, source_excursion)

    Usage:
        from django.contrib.contenttypes.models import ContentType

        # Direct link
        MediaLink.objects.create(
            media_asset=asset,
            content_type=ContentType.objects.get_for_model(DiverProfile),
            object_id=str(diver.pk),
            link_source=MediaLinkSource.DIRECT,
            linked_by=user,
        )

        # Derived link from excursion
        MediaLink.objects.create(
            media_asset=asset,
            content_type=ContentType.objects.get_for_model(DiverProfile),
            object_id=str(diver.pk),
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
            source_excursion=excursion,
            linked_by=user,
        )
    """

    media_asset = models.ForeignKey(
        "django_documents.MediaAsset",
        on_delete=models.CASCADE,
        related_name="links",
        help_text="The media asset being linked",
    )

    # GenericFK to target entity
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Content type of the target entity",
    )
    object_id = models.CharField(
        max_length=255,
        help_text="ID of the target entity (CharField for UUID support)",
    )
    target = GenericForeignKey("content_type", "object_id")

    # Provenance tracking
    link_source = models.CharField(
        max_length=30,
        choices=MediaLinkSource.choices,
        default=MediaLinkSource.DIRECT,
        help_text="How this link was created (direct or derived from excursion)",
    )
    source_excursion = models.ForeignKey(
        "Excursion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_media_links",
        help_text="Set when link_source=derived_from_excursion",
    )

    # Who created this link
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_links_created",
        help_text="User who created this link",
    )

    objects = MediaLinkQuerySet.as_manager()

    class Meta:
        verbose_name = "Media Link"
        verbose_name_plural = "Media Links"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["media_asset"]),
            models.Index(fields=["link_source"]),
            models.Index(fields=["source_excursion"]),
        ]
        constraints = [
            # Direct links: unique per (media_asset, target) when source=direct
            # (Partial constraint because source_excursion is NULL for direct links)
            models.UniqueConstraint(
                fields=["media_asset", "content_type", "object_id"],
                condition=Q(link_source="direct"),
                name="medialink_unique_direct",
            ),
            # Derived links: unique per (media_asset, target, source_excursion)
            models.UniqueConstraint(
                fields=["media_asset", "content_type", "object_id", "source_excursion"],
                condition=Q(link_source="derived_from_excursion"),
                name="medialink_unique_derived",
            ),
            # Derived links must have source_excursion set
            models.CheckConstraint(
                condition=(
                    Q(link_source="direct") |
                    Q(link_source="derived_from_excursion", source_excursion__isnull=False)
                ),
                name="medialink_derived_requires_source_excursion",
            ),
        ]

    def __str__(self):
        return f"{self.media_asset} → {self.content_type.model}:{self.object_id}"


# =============================================================================
# AI Settings (Singleton Configuration)
# =============================================================================


class AISettings(EnvFallbackMixin, SingletonModel):
    """AI service configuration for the dive shop.

    Stores API keys and settings for AI services used in:
    - Document text extraction (OCR enhancement)
    - Agreement template processing
    - Other AI-powered features

    Uses EnvFallbackMixin: Database values take precedence,
    with fallback to environment variables if DB is blank.

    Usage:
        settings = AISettings.get_instance()
        key = settings.get_with_fallback('openrouter_api_key')
        if settings.has_value('openrouter_api_key'):
            # AI features are available
    """

    # API Keys
    openrouter_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="OpenRouter API key (falls back to OPENROUTER_API_KEY env var)",
    )
    openai_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="OpenAI API key (falls back to OPENAI_API_KEY env var)",
    )

    # Model Configuration
    default_model = models.CharField(
        max_length=100,
        default="anthropic/claude-3-haiku",
        help_text="Default AI model to use for processing",
    )

    # Feature Flags
    ocr_enhancement_enabled = models.BooleanField(
        default=True,
        help_text="Enable AI-powered OCR enhancement for scanned documents",
    )
    auto_extract_enabled = models.BooleanField(
        default=False,
        help_text="Automatically extract text from uploaded documents",
    )

    ENV_FALLBACKS = {
        "openrouter_api_key": "OPENROUTER_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
    }

    class Meta:
        verbose_name = "AI Settings"
        verbose_name_plural = "AI Settings"

    def __str__(self):
        return "AI Settings"

    def is_configured(self):
        """Check if at least one AI service is configured."""
        return self.has_value("openrouter_api_key") or self.has_value("openai_api_key")


# =============================================================================
# Medical Provider Models
# =============================================================================


class MedicalProviderProfile(BaseModel):
    """Dive-specific extension for medical provider organizations.

    Links to django_parties.Organization (1:1) and stores dive-specific
    attributes like hyperbaric chamber availability, languages spoken,
    and certifications.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    PROVIDER_TYPE_CHOICES = [
        ("clinic", "Clinic"),
        ("hospital", "Hospital"),
        ("urgent_care", "Urgent Care"),
        ("chamber", "Hyperbaric Chamber Facility"),
        ("physician", "Individual Physician"),
    ]

    organization = models.OneToOneField(
        "django_parties.Organization",
        on_delete=models.CASCADE,
        related_name="medical_provider_profile",
        help_text="Base organization record",
    )
    provider_type = models.CharField(
        max_length=20,
        choices=PROVIDER_TYPE_CHOICES,
        help_text="Type of medical provider",
    )

    # Capabilities
    has_hyperbaric_chamber = models.BooleanField(
        default=False,
        help_text="Whether facility has a hyperbaric chamber",
    )
    hyperbaric_details = models.TextField(
        blank=True,
        help_text="Details about hyperbaric chamber (type, depth rating, etc.)",
    )
    accepts_divers = models.BooleanField(
        default=True,
        help_text="Whether provider accepts diving-related cases",
    )
    accepts_emergencies = models.BooleanField(
        default=False,
        help_text="Whether provider accepts emergency cases",
    )
    is_dan_affiliated = models.BooleanField(
        default=False,
        help_text="Whether provider is affiliated with Divers Alert Network",
    )

    # Languages and certifications (stored as arrays for simplicity)
    languages = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Languages spoken by staff",
    )
    certifications = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Relevant medical certifications (DAN, UHMS, etc.)",
    )

    # Contact
    after_hours_phone = models.CharField(
        max_length=30,
        blank=True,
        help_text="After-hours emergency contact number",
    )
    notes = models.TextField(
        blank=True,
        help_text="Special instructions or notes about this provider",
    )

    # Display ordering
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order for display (lower = first)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this provider is currently active",
    )

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name = "Medical Provider Profile"
        verbose_name_plural = "Medical Provider Profiles"

    def __str__(self):
        return f"{self.organization.name} ({self.get_provider_type_display()})"


class MedicalProviderLocation(BaseModel):
    """Physical location for a medical provider.

    Supports multi-location providers with different addresses and hours.
    Stores coordinates for map links in PDFs.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    profile = models.ForeignKey(
        MedicalProviderProfile,
        on_delete=models.CASCADE,
        related_name="locations",
        help_text="Parent medical provider profile",
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Location name (e.g., 'Main Office', 'Chamber Facility')",
    )

    # Address fields (inline for simplicity)
    address_line1 = models.CharField(
        max_length=255,
        help_text="Street address line 1",
    )
    address_line2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Street address line 2",
    )
    city = models.CharField(
        max_length=100,
        help_text="City",
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        help_text="State or province",
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal/ZIP code",
    )
    country = models.CharField(
        max_length=100,
        default="Mexico",
        help_text="Country",
    )

    # Coordinates for map links (9 digits, 6 decimal places per django_geo pattern)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate",
    )

    # Operating hours
    hours_text = models.CharField(
        max_length=255,
        help_text="Hours of operation (e.g., 'Mon-Fri 9:00 AM - 5:00 PM')",
    )
    is_24_7 = models.BooleanField(
        default=False,
        help_text="Whether location is open 24/7",
    )

    # Contact overrides (if different from main org)
    phone = models.CharField(
        max_length=30,
        blank=True,
        help_text="Phone number for this location",
    )
    email = models.EmailField(
        blank=True,
        help_text="Email address for this location",
    )

    # Flags
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary/main location",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order for display (lower = first)",
    )

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name = "Medical Provider Location"
        verbose_name_plural = "Medical Provider Locations"

    def __str__(self):
        if self.name:
            return f"{self.profile.organization.name} - {self.name}"
        return f"{self.profile.organization.name} - {self.city}"

    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        city_state_zip = f"{self.city}"
        if self.state:
            city_state_zip += f", {self.state}"
        if self.postal_code:
            city_state_zip += f" {self.postal_code}"
        parts.append(city_state_zip)
        if self.country:
            parts.append(self.country)
        return "\n".join(parts)

    @property
    def google_maps_url(self):
        """Return Google Maps URL if coordinates are available."""
        if self.latitude and self.longitude:
            return f"https://maps.google.com/?q={self.latitude},{self.longitude}"
        return None


class MedicalProviderRelationship(BaseModel):
    """Links a dive shop to its recommended medical providers.

    Allows dive operators to configure their preferred medical providers
    for customer referrals. Supports ordering and marking a primary provider.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.CASCADE,
        related_name="medical_provider_relationships",
        help_text="The dive shop/operator",
    )
    provider = models.ForeignKey(
        MedicalProviderProfile,
        on_delete=models.CASCADE,
        related_name="dive_shop_relationships",
        help_text="The medical provider",
    )

    # Relationship attributes
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary/preferred provider",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order for display (lower = first)",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about this provider relationship (e.g., 'Preferred for complex cases')",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this relationship is currently active",
    )

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name = "Medical Provider Relationship"
        verbose_name_plural = "Medical Provider Relationships"
        constraints = [
            # Only one relationship per dive_shop + provider (among active records)
            models.UniqueConstraint(
                fields=["dive_shop", "provider"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_shop_provider_relationship",
            ),
        ]

    def __str__(self):
        return f"{self.dive_shop.name} -> {self.provider.organization.name}"


# =============================================================================
# Buddy System Models
# =============================================================================


class Contact(BaseModel):
    """Lightweight record for an unregistered friend/buddy.

    Used when a diver wants to add a buddy who isn't on the platform yet.
    Supports invite workflows: create contact → invite → they register → link.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        INVITED = "invited", "Invited"
        ACCEPTED = "accepted", "Accepted"
        BOUNCED = "bounced", "Bounced"
        OPTED_OUT = "opted_out", "Opted Out"

    created_by = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.CASCADE,
        related_name="created_contacts",
        help_text="Person who created this contact",
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Display name for the contact",
    )
    email = models.EmailField(
        null=True,
        blank=True,
        help_text="Contact email address",
    )
    phone = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Contact phone number",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        help_text="Contact status in invite workflow",
    )
    linked_person = models.ForeignKey(
        "django_parties.Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contact_links",
        help_text="Linked Person after they register",
    )

    class Meta:
        ordering = ["display_name"]
        constraints = [
            # Must have at least email or phone
            models.CheckConstraint(
                condition=Q(email__isnull=False) | Q(phone__isnull=False),
                name="contact_requires_email_or_phone",
            ),
        ]
        indexes = [
            models.Index(fields=["created_by"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.display_name


class BuddyIdentity(BaseModel):
    """Abstraction for team member identity: Person OR Contact.

    Allows DiveTeamMember to reference either a registered Person
    or an unregistered Contact, enabling invite-ready buddy system.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    person = models.OneToOneField(
        "django_parties.Person",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="buddy_identity",
        help_text="Reference to a registered Person",
    )
    contact = models.OneToOneField(
        Contact,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="buddy_identity",
        help_text="Reference to an unregistered Contact",
    )

    class Meta:
        verbose_name = "Buddy Identity"
        verbose_name_plural = "Buddy Identities"
        constraints = [
            # Must have exactly one of person or contact
            models.CheckConstraint(
                condition=(
                    Q(person__isnull=False, contact__isnull=True) |
                    Q(person__isnull=True, contact__isnull=False)
                ),
                name="identity_exactly_one_of_person_or_contact",
            ),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self) -> str:
        """Get display name from Person or Contact."""
        if self.person:
            return f"{self.person.first_name} {self.person.last_name}"
        if self.contact:
            return self.contact.display_name
        return "Unknown"

    @property
    def is_registered(self) -> bool:
        """Check if this identity represents a registered user.

        True if:
        - Identity references a Person directly, OR
        - Identity references a Contact that has been linked to a Person
        """
        if self.person is not None:
            return True
        if self.contact and self.contact.linked_person is not None:
            return True
        return False


class DiveTeam(BaseModel):
    """Buddy pair or group.

    Represents 2+ divers who typically dive together.
    Size 2 = buddy pair, size 3+ = buddy group with optional name.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class TeamType(models.TextChoices):
        BUDDY = "buddy", "Buddy Group"

    team_type = models.CharField(
        max_length=20,
        choices=TeamType.choices,
        default=TeamType.BUDDY,
        help_text="Type of team",
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional name for groups (blank for pairs)",
    )
    created_by = models.ForeignKey(
        "django_parties.Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_dive_teams",
        help_text="Person who created this team",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this team is currently active",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        if self.name:
            return self.name
        return f"Buddy Team {self.pk}"


class DiveTeamMember(BaseModel):
    """Membership in a dive team.

    Join table linking BuddyIdentity to DiveTeam.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    team = models.ForeignKey(
        DiveTeam,
        on_delete=models.CASCADE,
        related_name="members",
        help_text="The dive team",
    )
    identity = models.ForeignKey(
        BuddyIdentity,
        on_delete=models.CASCADE,
        related_name="team_memberships",
        help_text="The team member identity",
    )
    role = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optional role in the team",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about this team member",
    )

    class Meta:
        ordering = ["team", "created_at"]
        constraints = [
            # Can't add same identity to team twice
            models.UniqueConstraint(
                fields=["team", "identity"],
                name="unique_team_member",
            ),
        ]
        indexes = [
            models.Index(fields=["team", "identity"]),
        ]

    def __str__(self):
        return f"{self.identity.display_name} in {self.team}"


class DiveBuddy(BaseModel):
    """Simple buddy relationship for a diver.

    Links a diver to their buddies. Buddy can be:
    - Another DiverProfile (buddy field), or
    - Just a Person who isn't a diver yet (buddy_person field)

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse/Partner"),
        ("friend", "Friend"),
        ("dive_club", "Dive Club Member"),
        ("instructor", "Instructor"),
        ("family", "Family Member"),
        ("coworker", "Coworker"),
        ("other", "Other"),
    ]

    diver = models.ForeignKey(
        DiverProfile,
        on_delete=models.CASCADE,
        related_name="dive_buddies",
        help_text="The diver who owns this buddy relationship",
    )
    buddy = models.ForeignKey(
        DiverProfile,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="buddy_of",
        help_text="The buddy (if they are a diver)",
    )
    buddy_person = models.ForeignKey(
        "django_parties.Person",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="buddy_person_for",
        help_text="The buddy (if they are just a person, not a diver)",
    )
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        help_text="Type of relationship",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about this buddy",
    )

    class Meta:
        ordering = ["diver", "relationship"]
        verbose_name = "Dive Buddy"
        verbose_name_plural = "Dive Buddies"
        indexes = [
            models.Index(fields=["diver"]),
        ]

    def __str__(self):
        return f"{self.diver.person} -> {self.buddy_name} ({self.get_relationship_display()})"

    @property
    def buddy_name(self) -> str:
        """Get the buddy's display name."""
        if self.buddy:
            person = self.buddy.person
            return f"{person.first_name} {person.last_name}"
        if self.buddy_person:
            return f"{self.buddy_person.first_name} {self.buddy_person.last_name}"
        return "Unknown"


__all__ = [
    "CertificationLevel",
    "DiverCertification",
    "ExcursionRequirement",
    "TripRequirement",
    "DiverProfile",
    "DiveSite",
    "Trip",
    "Excursion",
    "DiveTrip",
    "Dive",
    "Booking",
    "EligibilityOverride",
    "ExcursionRoster",
    "TripRoster",
    "ExcursionType",
    "ExcursionTypeDive",
    "SitePriceAdjustment",
    "SettlementRecord",
    "CommissionRule",
    "SettlementRun",
    "DiveAssignment",
    "DiveLog",
    "DiverEquipmentRental",
    "AgreementTemplate",
    # Protected Area Models (new names)
    "ProtectedArea",
    "ProtectedAreaZone",
    "ProtectedAreaRule",
    "ProtectedAreaFeeSchedule",
    "ProtectedAreaFeeTier",
    "DiverEligibilityProof",
    # Unified Permit Model (replaces ProtectedAreaGuideCredential + VesselPermit)
    "ProtectedAreaPermit",
    "GuidePermitDetails",
    # Legacy models (deprecated - use ProtectedAreaPermit instead)
    "ProtectedAreaGuideCredential",
    "VesselPermit",
    # Backwards compatibility aliases
    "MarinePark",
    "ParkZone",
    "ParkRule",
    "ParkFeeSchedule",
    "ParkFeeTier",
    "ParkGuideCredential",
    # Document Retention Policy (overlay on django-documents)
    "DocumentRetentionPolicy",
    "DocumentLegalHold",
    # Photo Tagging
    "PhotoTag",
    # AI Configuration
    "AISettings",
    # Medical Provider Models
    "MedicalProviderProfile",
    "MedicalProviderLocation",
    "MedicalProviderRelationship",
    # Entitlements
    "EntitlementGrant",
    # Preferences
    "PreferenceDefinition",
    "PartyPreference",
    # Buddy System Models
    "Contact",
    "BuddyIdentity",
    "DiveTeam",
    "DiveTeamMember",
    "DiveBuddy",
    # Recurring Excursion Models
    "RecurrenceRule",
    "RecurrenceException",
    "ExcursionSeries",
]

# Import EntitlementGrant from submodule for migration discovery
from ..entitlements.models import EntitlementGrant

# Import Preference models from submodule for migration discovery
from ..preferences.models import PreferenceDefinition, PartyPreference
