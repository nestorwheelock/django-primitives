"""Booking models for diveops.

Contains:
- Booking: A diver's reservation for an excursion
- EligibilityOverride: Booking-scoped eligibility override for staff approval
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from django_basemodels import BaseModel


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
        "diveops.Excursion",
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    # Backwards compatibility: 'trip' as alias for 'excursion'
    @property
    def trip(self):
        """Backwards compatibility alias for excursion."""
        return self.excursion

    diver = models.ForeignKey(
        "diveops.DiverProfile",
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
        "diveops.DiverProfile",
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
