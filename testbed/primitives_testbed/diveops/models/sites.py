"""Dive site models for dive operations.

This module provides models for dive site management:
- DiveSite: Location with diving metadata (depth, difficulty, certification required)
- DiveSitePhoto: Photo associated with a dive site
- SitePriceAdjustment: Site-specific price adjustment for excursions
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from django_basemodels import BaseModel


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
        "diveops.CertificationLevel",
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
        "diveops.ProtectedArea",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dive_sites",
    )
    protected_area_zone = models.ForeignKey(
        "diveops.ProtectedAreaZone",
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
