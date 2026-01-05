"""DiveOps pricing package.

This package provides pricing services for dive operations, composing
django-primitives (catalog, agreements, ledger, money) with diveops domain.

Key components:
- calculators: Boat cost tiers, gas pricing calculations
- services: quote_excursion, snapshot_booking_pricing, add_equipment_rental
- models: DiverEquipmentRental (glue model for equipment tracking)
- snapshots: Build immutable pricing snapshots
"""

from .exceptions import (
    PricingError,
    ConfigurationError,
    CurrencyMismatchError,
    MissingVendorAgreementError,
    MissingPriceError,
)
from .services import (
    quote_excursion,
    snapshot_booking_pricing,
    add_equipment_rental,
    validate_pricing_configuration,
)

__all__ = [
    # Exceptions
    "PricingError",
    "ConfigurationError",
    "CurrencyMismatchError",
    "MissingVendorAgreementError",
    "MissingPriceError",
    # Services
    "quote_excursion",
    "snapshot_booking_pricing",
    "add_equipment_rental",
    "validate_pricing_configuration",
]
