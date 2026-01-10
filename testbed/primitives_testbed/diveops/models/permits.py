"""Protected Area and Permit models for dive operations.

This module provides regulatory framework models:
- ProtectedArea: Hierarchical protected area with regulatory authority
- ProtectedAreaZone: Zone within a protected area with specific rules
- ProtectedAreaRule: Effective-dated enforceable rule for a protected area
- ProtectedAreaFeeSchedule: Fee schedule with stratified tiers
- ProtectedAreaFeeTier: Stratified fee tier within a schedule
- ProtectedAreaPermit: Unified authorization model for operating in a protected area
- GuidePermitDetails: Extended details for GUIDE permits
"""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from django_basemodels import BaseModel


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
        "diveops.DiverProfile",
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
                condition=Q(expires_at__isnull=True) | Q(expires_at__gte=F("issued_at")),
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

    # Carta evaluacion (signed by boat owner - can be self if owner)
    carta_eval_agreement = models.ForeignKey(
        "django_agreements.Agreement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guide_carta_evals_v2",
        help_text="Signed carta evaluacion document",
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
