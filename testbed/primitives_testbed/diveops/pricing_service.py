"""Pricing service for excursion types.

Computes final excursion prices by combining:
- ExcursionType base_price (starting point)
- SitePriceAdjustment factors (distance, park fees, night surcharges, boat fees)

The service applies adjustments based on:
- Dive mode filtering (boat vs shore)
- Time of day (night surcharge only for night dives)
- Active status (inactive adjustments excluded)
"""

from dataclasses import dataclass, field
from decimal import Decimal

from .models import DiveSite, ExcursionType, SitePriceAdjustment


@dataclass(frozen=True)
class ComputedPrice:
    """Immutable result of price computation.

    Attributes:
        base_price: Starting price from ExcursionType
        adjustments: List of (kind, amount) tuples applied
        total_price: Final computed price
        currency: Currency code (e.g., "USD")
        breakdown: Dict with pricing details for display/audit
    """

    base_price: Decimal
    adjustments: tuple[tuple[str, Decimal], ...]  # Immutable tuple of tuples
    total_price: Decimal
    currency: str
    breakdown: dict = field(default_factory=dict)

    def __post_init__(self):
        # For frozen dataclass, use object.__setattr__ for computed fields
        if not self.breakdown:
            breakdown = {
                "base": self.base_price,
                "adjustments": [
                    {"kind": kind, "amount": amount}
                    for kind, amount in self.adjustments
                ],
                "total": self.total_price,
            }
            object.__setattr__(self, "breakdown", breakdown)


def compute_excursion_price(
    excursion_type: ExcursionType,
    dive_site: DiveSite,
) -> ComputedPrice:
    """Compute the final price for an excursion.

    Combines the excursion type's base price with applicable site adjustments.

    Adjustment application rules:
    - Distance: Always applied if present and active
    - Park fee: Always applied if present and active
    - Boat fee: Only applied if excursion_type.dive_mode == "boat"
    - Night surcharge: Only applied if excursion_type.time_of_day == "night"

    Args:
        excursion_type: The product template with base price
        dive_site: The dive site with potential price adjustments

    Returns:
        ComputedPrice with base, adjustments, total, and breakdown
    """
    base_price = excursion_type.base_price
    currency = excursion_type.currency
    adjustments: list[tuple[str, Decimal]] = []

    # Get all active adjustments for this site
    site_adjustments = dive_site.price_adjustments.filter(is_active=True)

    for adj in site_adjustments:
        # Check mode filter
        if adj.applies_to_mode and adj.applies_to_mode != excursion_type.dive_mode:
            continue

        # Check night surcharge - only apply if excursion is night dive
        if adj.kind == "night" and excursion_type.time_of_day != "night":
            continue

        # Apply this adjustment
        adjustments.append((adj.kind, adj.amount))

    # Calculate total
    adjustment_total = sum(amount for _, amount in adjustments)
    total_price = base_price + adjustment_total

    return ComputedPrice(
        base_price=base_price,
        adjustments=tuple(adjustments),
        total_price=total_price,
        currency=currency,
    )


def create_price_snapshot(
    computed_price: ComputedPrice,
    excursion_type_id: str,
    dive_site_id: str,
) -> dict:
    """Serialize a ComputedPrice to a snapshot dict for storage.

    INV-3: Price Immutability - create immutable snapshot at booking time.

    The snapshot stores all pricing context so the price can be reconstructed
    without re-querying pricing rules. Decimal values are stored as strings
    to avoid float drift in JSON.

    Args:
        computed_price: The computed price result
        excursion_type_id: UUID of the excursion type (as string)
        dive_site_id: UUID of the dive site (as string)

    Returns:
        Dict with snapshot data suitable for JSONField storage
    """
    from django.utils import timezone

    return {
        "total": str(computed_price.total_price),
        "currency": computed_price.currency,
        "base_price": str(computed_price.base_price),
        "adjustments": [
            {"kind": kind, "amount": str(amount)}
            for kind, amount in computed_price.adjustments
        ],
        "excursion_type_id": excursion_type_id,
        "dive_site_id": dive_site_id,
        "computed_at": timezone.now().isoformat(),
    }
