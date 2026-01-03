"""Selectors for the pricing module.

Provides the price resolution algorithm and query functions.
"""

from datetime import datetime

from django.utils import timezone

from django_money import Money

from .exceptions import NoPriceFoundError
from .models import Price
from .value_objects import ResolvedPrice


def resolve_price(
    catalog_item,
    *,
    organization=None,
    party=None,
    agreement=None,
    as_of: datetime | None = None,
) -> ResolvedPrice:
    """Resolve the unit price for a catalog item.

    Resolution order (first match wins):
    1. Agreement-specific price (if agreement provided)
    2. Party-specific price (if party provided)
    3. Organization-specific price (if organization provided)
    4. Global price (no scope)

    Within each scope level, prefer:
    - Higher priority value
    - More recent valid_from (tie-breaker)

    Args:
        catalog_item: The CatalogItem to price
        organization: Optional payer organization
        party: Optional individual person
        agreement: Optional contract/agreement
        as_of: Point in time for price resolution (defaults to now)

    Returns:
        ResolvedPrice with unit_price (Money) and explanation.

    Raises:
        NoPriceFoundError: If no applicable price exists.
    """
    check_time = as_of or timezone.now()

    # Get all current prices for this item
    base_qs = Price.objects.for_catalog_item(catalog_item).current(as_of=check_time)

    # Try each scope level in order of specificity
    price = None

    # 1. Agreement-specific price (highest priority)
    if agreement is not None:
        price = (
            base_qs.for_agreement(agreement)
            .order_by("-priority", "-valid_from")
            .first()
        )
        if price:
            return _to_resolved_price(price)

    # 2. Party-specific price
    if party is not None:
        price = (
            base_qs.for_party(party)
            .filter(agreement__isnull=True)  # Not tied to an agreement
            .order_by("-priority", "-valid_from")
            .first()
        )
        if price:
            return _to_resolved_price(price)

    # 3. Organization-specific price
    if organization is not None:
        price = (
            base_qs.for_organization(organization)
            .filter(party__isnull=True, agreement__isnull=True)
            .order_by("-priority", "-valid_from")
            .first()
        )
        if price:
            return _to_resolved_price(price)

    # 4. Global price (fallback)
    price = base_qs.global_scope().order_by("-priority", "-valid_from").first()

    if price:
        return _to_resolved_price(price)

    # No price found
    raise NoPriceFoundError(
        catalog_item,
        context={
            "organization": organization,
            "party": party,
            "agreement": agreement,
            "as_of": check_time,
        },
    )


def list_applicable_prices(
    catalog_item,
    *,
    organization=None,
    party=None,
    agreement=None,
    as_of: datetime | None = None,
) -> list[Price]:
    """List all prices that could apply to a catalog item.

    Returns prices in resolution order (most specific first).
    Useful for debugging and transparency.
    """
    check_time = as_of or timezone.now()
    base_qs = Price.objects.for_catalog_item(catalog_item).current(as_of=check_time)

    prices = []

    # Agreement-specific prices
    if agreement:
        prices.extend(
            base_qs.for_agreement(agreement).order_by("-priority", "-valid_from")
        )

    # Party-specific prices
    if party:
        prices.extend(
            base_qs.for_party(party)
            .filter(agreement__isnull=True)
            .order_by("-priority", "-valid_from")
        )

    # Organization-specific prices
    if organization:
        prices.extend(
            base_qs.for_organization(organization)
            .filter(party__isnull=True, agreement__isnull=True)
            .order_by("-priority", "-valid_from")
        )

    # Global prices
    prices.extend(base_qs.global_scope().order_by("-priority", "-valid_from"))

    return prices


def explain_price_resolution(
    catalog_item,
    *,
    organization=None,
    party=None,
    agreement=None,
    as_of: datetime | None = None,
) -> dict:
    """Explain how price resolution works for a catalog item.

    Returns a dictionary with:
    - selected_price: The price that would be used
    - candidates: All applicable prices in resolution order
    - explanation: Human-readable explanation

    Useful for debugging and auditing.
    """
    check_time = as_of or timezone.now()

    candidates = list_applicable_prices(
        catalog_item,
        organization=organization,
        party=party,
        agreement=agreement,
        as_of=check_time,
    )

    try:
        resolved = resolve_price(
            catalog_item,
            organization=organization,
            party=party,
            agreement=agreement,
            as_of=check_time,
        )
        selected = resolved
        explanation = resolved.explain()
    except NoPriceFoundError:
        selected = None
        explanation = "No applicable price found"

    return {
        "selected_price": selected,
        "candidates": [
            {
                "id": str(p.pk),
                "amount": str(p.amount),
                "currency": p.currency,
                "scope_type": p.scope_type,
                "priority": p.priority,
                "valid_from": p.valid_from.isoformat(),
                "valid_to": p.valid_to.isoformat() if p.valid_to else None,
            }
            for p in candidates
        ],
        "explanation": explanation,
        "context": {
            "catalog_item": str(catalog_item.pk),
            "organization": str(organization.pk) if organization else None,
            "party": str(party.pk) if party else None,
            "agreement": str(agreement.pk) if agreement else None,
            "as_of": check_time.isoformat(),
        },
    }


def _to_resolved_price(price: Price) -> ResolvedPrice:
    """Convert a Price model to a ResolvedPrice value object."""
    return ResolvedPrice(
        unit_price=price.money,
        price_id=price.pk,
        scope_type=price.scope_type,
        scope_id=price.scope_id,
        valid_from=price.valid_from,
        valid_to=price.valid_to,
        priority=price.priority,
    )
