"""Exceptions for the pricing module."""


class PricingError(Exception):
    """Base exception for pricing errors."""

    pass


class NoPriceFoundError(PricingError):
    """Raised when no applicable price exists for a catalog item."""

    def __init__(self, catalog_item, context=None):
        self.catalog_item = catalog_item
        self.context = context or {}
        item_name = getattr(catalog_item, "display_name", str(catalog_item))
        super().__init__(f"No price found for: {item_name}")


class MultiplePricesError(PricingError):
    """Raised when multiple prices match (should not happen with proper constraints)."""

    def __init__(self, catalog_item, prices):
        self.catalog_item = catalog_item
        self.prices = prices
        item_name = getattr(catalog_item, "display_name", str(catalog_item))
        super().__init__(f"Multiple prices found for: {item_name}")
