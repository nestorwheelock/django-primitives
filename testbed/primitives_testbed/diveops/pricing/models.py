"""Pricing glue models for diveops.

These models connect django-primitives to diveops domain objects.
Kept minimal - only what's needed for domain-specific pricing.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel
from django_money import Money


class DiverEquipmentRental(BaseModel):
    """Equipment rented to a specific diver on a booking.

    This is a glue model linking:
    - Booking (diveops domain)
    - DiverProfile (diveops domain)
    - CatalogItem (django-catalog primitive)

    Snapshots pricing at rental time for immutability.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    # Core relationships
    booking = models.ForeignKey(
        "diveops.Booking",
        on_delete=models.CASCADE,
        related_name="equipment_rentals",
        help_text="The booking this rental belongs to",
    )
    diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.PROTECT,
        related_name="equipment_rentals",
        help_text="The diver renting the equipment",
    )
    catalog_item = models.ForeignKey(
        "django_catalog.CatalogItem",
        on_delete=models.PROTECT,
        related_name="diveops_rentals",
        help_text="The equipment catalog item",
    )

    # Quantity
    quantity = models.PositiveSmallIntegerField(
        default=1,
        help_text="Number of items rented",
    )

    # Snapshot pricing at rental time (immutable)
    unit_cost_amount = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Shop cost per unit at rental time",
    )
    unit_cost_currency = models.CharField(
        max_length=3,
        default="MXN",
        help_text="Currency for shop cost",
    )
    unit_charge_amount = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Customer charge per unit at rental time",
    )
    unit_charge_currency = models.CharField(
        max_length=3,
        default="MXN",
        help_text="Currency for customer charge",
    )

    # Audit trail - references to pricing sources
    price_rule_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of Price rule used for customer charge",
    )
    vendor_agreement_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of vendor Agreement used for shop cost",
    )

    # Snapshot of item details (in case catalog item changes)
    item_name_snapshot = models.CharField(
        max_length=200,
        help_text="Equipment name at rental time",
    )

    # Rental audit
    rented_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the rental was created",
    )
    rented_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_rentals_created",
        help_text="User who created the rental",
    )

    class Meta:
        app_label = "diveops"
        verbose_name = "Diver Equipment Rental"
        verbose_name_plural = "Diver Equipment Rentals"
        constraints = [
            # Quantity must be positive
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="diveops_rental_quantity_positive",
            ),
            # Cost and charge must be non-negative
            models.CheckConstraint(
                condition=models.Q(unit_cost_amount__gte=0),
                name="diveops_rental_cost_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_charge_amount__gte=0),
                name="diveops_rental_charge_non_negative",
            ),
            # Prevent duplicate rentals for same item on same booking
            models.UniqueConstraint(
                fields=["booking", "diver", "catalog_item"],
                condition=models.Q(deleted_at__isnull=True),
                name="diveops_rental_unique_per_booking",
            ),
        ]
        indexes = [
            models.Index(fields=["booking", "diver"]),
            models.Index(fields=["rented_at"]),
        ]

    def __str__(self):
        return f"{self.diver} - {self.item_name_snapshot} x{self.quantity}"

    @property
    def unit_cost(self) -> Money:
        """Return unit cost as Money object."""
        return Money(self.unit_cost_amount, self.unit_cost_currency)

    @property
    def unit_charge(self) -> Money:
        """Return unit charge as Money object."""
        return Money(self.unit_charge_amount, self.unit_charge_currency)

    @property
    def total_cost(self) -> Money:
        """Calculate total cost (unit_cost * quantity)."""
        return Money(
            self.unit_cost_amount * self.quantity,
            self.unit_cost_currency,
        )

    @property
    def total_charge(self) -> Money:
        """Calculate total charge (unit_charge * quantity)."""
        return Money(
            self.unit_charge_amount * self.quantity,
            self.unit_charge_currency,
        )

    @property
    def total_margin(self) -> Money | None:
        """Calculate total margin (charge - cost)."""
        if self.unit_cost_currency != self.unit_charge_currency:
            return None
        margin_amount = (self.unit_charge_amount - self.unit_cost_amount) * self.quantity
        return Money(margin_amount, self.unit_charge_currency)

    def save(self, *args, **kwargs):
        """Snapshot item name on first save."""
        if not self.item_name_snapshot:
            self.item_name_snapshot = self.catalog_item.display_name
        super().save(*args, **kwargs)
