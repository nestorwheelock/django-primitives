"""Pricing module - flexible, auditable pricing on top of primitives.

This is an APPLICATION layer module, NOT a primitive.
It builds on top of:
- django-catalog: CatalogItem (what's being priced)
- django-parties: Organization, Person (pricing scopes)
- django-agreements: Agreement (contract-based pricing)
- django-money: Money value object (price representation)

Why NOT a primitive:
- Pricing rules are business policy, not infrastructure
- Different businesses have different pricing strategies
- Primitives must be policy-free; this module encodes policy
"""

default_app_config = "primitives_testbed.pricing.apps.PricingConfig"

__all__ = [
    "Price",
    "PricedBasketItem",
    "ResolvedPrice",
    "resolve_price",
    "list_applicable_prices",
    "explain_price_resolution",
    "NoPriceFoundError",
    "PricingError",
]


def __getattr__(name):
    """Lazy imports to prevent AppRegistryNotReady errors."""
    if name == "Price":
        from .models import Price

        return Price
    if name == "PricedBasketItem":
        from .models import PricedBasketItem

        return PricedBasketItem
    if name == "ResolvedPrice":
        from .value_objects import ResolvedPrice

        return ResolvedPrice
    if name == "resolve_price":
        from .selectors import resolve_price

        return resolve_price
    if name == "list_applicable_prices":
        from .selectors import list_applicable_prices

        return list_applicable_prices
    if name == "explain_price_resolution":
        from .selectors import explain_price_resolution

        return explain_price_resolution
    if name == "NoPriceFoundError":
        from .exceptions import NoPriceFoundError

        return NoPriceFoundError
    if name == "PricingError":
        from .exceptions import PricingError

        return PricingError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
