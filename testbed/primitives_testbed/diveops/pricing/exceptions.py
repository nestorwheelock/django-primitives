"""Pricing exceptions for diveops."""


class PricingError(Exception):
    """Base exception for pricing errors."""

    pass


class ConfigurationError(PricingError):
    """Raised when pricing configuration is invalid or incomplete."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class CurrencyMismatchError(PricingError):
    """Raised when currencies don't match for a calculation."""

    def __init__(self, expected: str, actual: str):
        super().__init__(f"Currency mismatch: expected {expected}, got {actual}")
        self.expected = expected
        self.actual = actual


class MissingVendorAgreementError(ConfigurationError):
    """Raised when required vendor agreement is not found."""

    def __init__(self, scope_type: str, scope_ref: str | None = None):
        message = f"No active vendor agreement found for scope_type={scope_type}"
        if scope_ref:
            message += f", scope_ref={scope_ref}"
        super().__init__(message)
        self.scope_type = scope_type
        self.scope_ref = scope_ref


class MissingPriceError(ConfigurationError):
    """Raised when required price is not found."""

    def __init__(self, catalog_item_id: str, context: str | None = None):
        message = f"No active price found for catalog_item={catalog_item_id}"
        if context:
            message += f" ({context})"
        super().__init__(message)
        self.catalog_item_id = catalog_item_id
        self.context = context


class SnapshotImmutableError(PricingError):
    """Raised when attempting to modify an immutable pricing snapshot."""

    def __init__(self, booking_id: str):
        super().__init__(f"Pricing snapshot for booking {booking_id} is immutable")
        self.booking_id = booking_id


class DuplicateRentalError(PricingError):
    """Raised when attempting to create a duplicate equipment rental."""

    def __init__(self, booking_id: str, catalog_item_id: str):
        super().__init__(
            f"Equipment rental already exists for booking={booking_id}, "
            f"catalog_item={catalog_item_id}"
        )
        self.booking_id = booking_id
        self.catalog_item_id = catalog_item_id


class MissingCatalogItemError(ConfigurationError):
    """Raised when required catalog item is not found."""

    def __init__(self, slug: str):
        super().__init__(f"Catalog item with slug '{slug}' not found or inactive")
        self.slug = slug
