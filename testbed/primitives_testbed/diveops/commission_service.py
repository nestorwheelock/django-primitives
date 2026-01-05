"""Commission calculation service for dive operations.

Provides functions to calculate commissions for bookings based on
effective-dated commission rules.

INV-3: Commission rules are effective-dated.
       Latest effective_at <= as_of date wins.

Rule priority (highest to lowest):
1. ExcursionType-specific rule (matching excursion_type, latest effective_at)
2. Shop default rule (excursion_type=NULL, latest effective_at)
3. Zero commission (no matching rule)
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from .models import Booking


def calculate_commission(
    booking: "Booking",
    as_of: datetime | None = None,
) -> Decimal:
    """Calculate commission amount for a booking.

    Uses the effective commission rule at the specified time.
    Rule priority: ExcursionType-specific > Shop default > Zero.

    Args:
        booking: Booking to calculate commission for
        as_of: Point in time to evaluate (defaults to now)

    Returns:
        Commission amount as Decimal (never negative)
    """
    from .models import CommissionRule

    if as_of is None:
        as_of = timezone.now()

    # Get booking details
    dive_shop = booking.excursion.dive_shop
    excursion_type = getattr(booking.excursion, "excursion_type", None)

    # Get booking price from price_snapshot
    price_snapshot = booking.price_snapshot or {}
    booking_amount = Decimal(price_snapshot.get("amount", "0.00"))

    if booking_amount <= 0:
        return Decimal("0.00")

    # Find applicable commission rule
    rule = _get_effective_commission_rule(dive_shop, excursion_type, as_of)

    if rule is None:
        return Decimal("0.00")

    # Calculate commission based on rate type
    return _calculate_commission_amount(rule, booking_amount)


def _get_effective_commission_rule(
    dive_shop,
    excursion_type,
    as_of: datetime,
):
    """Get the effective commission rule for a shop/excursion_type at a point in time.

    Rule priority:
    1. ExcursionType-specific rule (if excursion_type is set)
    2. Shop default rule (excursion_type=NULL)

    Within each priority level, the latest effective_at <= as_of wins.

    Returns:
        CommissionRule or None
    """
    from .models import CommissionRule

    # Try ExcursionType-specific rule first (if applicable)
    if excursion_type is not None:
        type_rule = (
            CommissionRule.objects.filter(
                dive_shop=dive_shop,
                excursion_type=excursion_type,
                effective_at__lte=as_of,
            )
            .order_by("-effective_at")
            .first()
        )
        if type_rule is not None:
            return type_rule

    # Fall back to shop default rule
    default_rule = (
        CommissionRule.objects.filter(
            dive_shop=dive_shop,
            excursion_type__isnull=True,
            effective_at__lte=as_of,
        )
        .order_by("-effective_at")
        .first()
    )

    return default_rule


def _calculate_commission_amount(rule, booking_amount: Decimal) -> Decimal:
    """Calculate commission amount based on rule type.

    Args:
        rule: CommissionRule with rate_type and rate_value
        booking_amount: Total booking price

    Returns:
        Commission amount (rounded to 2 decimal places)
    """
    from .models import CommissionRule

    if rule.rate_type == CommissionRule.RateType.PERCENTAGE:
        # Percentage: rate_value is the percentage (e.g., 15.00 = 15%)
        commission = booking_amount * (rule.rate_value / Decimal("100"))
    else:
        # Fixed: rate_value is the fixed amount
        commission = rule.rate_value

    # Round to 2 decimal places and ensure non-negative
    return max(Decimal("0.00"), commission.quantize(Decimal("0.01")))
