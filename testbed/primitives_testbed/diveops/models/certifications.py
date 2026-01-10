"""Certification models for diveops.

This module provides certification-related models.
"""

from django.db import models
from django.db.models import Q

from django_basemodels import BaseModel


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
