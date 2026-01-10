"""Diver-related models for dive operations.

This module contains models for diver profiles, certifications, and eligibility proofs.
"""

from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from django_basemodels import BaseModel

# Configurable waiver validity period (default 365 days, None = never expires)
DIVEOPS_WAIVER_VALIDITY_DAYS = getattr(settings, "DIVEOPS_WAIVER_VALIDITY_DAYS", 365)


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
        "CertificationLevel",
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
