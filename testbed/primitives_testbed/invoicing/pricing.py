"""Basket pricing for invoicing.

Prices all items in a basket and calculates totals.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from django_catalog.models import Basket, BasketItem
from django_money import Money
from django_parties.models import Organization, Person
from django_agreements.models import Agreement

from primitives_testbed.pricing.exceptions import NoPriceFoundError
from primitives_testbed.pricing.models import PricedBasketItem
from primitives_testbed.pricing.selectors import resolve_price

from .exceptions import MixedCurrencyError, PricingError


@dataclass(frozen=True)
class PricedLine:
    """A priced line item ready for invoicing."""

    basket_item: BasketItem
    priced_item: PricedBasketItem
    unit_price: Money
    quantity: int
    line_total: Money
    scope_type: str
    price_id: str


@dataclass
class PricedBasket:
    """A basket with all items priced and totaled."""

    basket: Basket
    lines: List[PricedLine]
    subtotal: Money
    currency: str

    @property
    def is_single_currency(self) -> bool:
        """Check if all lines have the same currency."""
        return all(line.unit_price.currency == self.currency for line in self.lines)


class PartialPricingError(PricingError):
    """Some items could not be priced."""

    def __init__(
        self, priced_lines: List[PricedLine], failed_items: List[BasketItem]
    ):
        self.priced_lines = priced_lines
        self.failed_items = failed_items
        super().__init__(
            f"{len(failed_items)} items could not be priced: "
            f"{[item.catalog_item.display_name for item in failed_items]}"
        )


def price_basket(
    basket: Basket,
    organization: Optional[Organization] = None,
    party: Optional[Person] = None,
    agreement: Optional[Agreement] = None,
    *,
    fail_on_missing: bool = True,
) -> PricedBasket:
    """Price all items in a basket.

    Args:
        basket: The basket to price
        organization: Payer organization for price resolution
        party: Individual party for price resolution
        agreement: Agreement for price resolution
        fail_on_missing: If True, raise error if any item cannot be priced

    Returns:
        PricedBasket with all lines priced and totaled

    Raises:
        PartialPricingError: If fail_on_missing=True and some items have no price
        NoPriceFoundError: If fail_on_missing=True and an item has no price
        MixedCurrencyError: If items have different currencies
    """
    priced_lines: List[PricedLine] = []
    failed_items: List[BasketItem] = []
    currency: Optional[str] = None

    for basket_item in basket.items.select_related("catalog_item"):
        try:
            resolved = resolve_price(
                basket_item.catalog_item,
                organization=organization,
                party=party,
                agreement=agreement,
            )

            # Create or update PricedBasketItem
            priced_item, _ = PricedBasketItem.objects.update_or_create(
                basket_item=basket_item,
                defaults={
                    "unit_price_amount": resolved.unit_price.amount,
                    "unit_price_currency": resolved.unit_price.currency,
                    "price_rule_id": resolved.price_id,
                },
            )

            line_total = resolved.unit_price * basket_item.quantity

            priced_lines.append(
                PricedLine(
                    basket_item=basket_item,
                    priced_item=priced_item,
                    unit_price=resolved.unit_price,
                    quantity=basket_item.quantity,
                    line_total=line_total,
                    scope_type=resolved.scope_type,
                    price_id=str(resolved.price_id),
                )
            )

            # Track currency (enforce single currency)
            if currency is None:
                currency = resolved.unit_price.currency
            elif currency != resolved.unit_price.currency:
                raise MixedCurrencyError(
                    f"Mixed currencies not supported: {currency} vs {resolved.unit_price.currency}"
                )

        except NoPriceFoundError:
            if fail_on_missing:
                raise
            failed_items.append(basket_item)

    if failed_items and fail_on_missing:
        raise PartialPricingError(priced_lines, failed_items)

    # Calculate subtotal
    if priced_lines:
        subtotal_amount = sum(line.line_total.amount for line in priced_lines)
        subtotal = Money(subtotal_amount, currency or "USD")
    else:
        subtotal = Money(Decimal("0"), currency or "USD")

    return PricedBasket(
        basket=basket,
        lines=priced_lines,
        subtotal=subtotal,
        currency=currency or "USD",
    )
