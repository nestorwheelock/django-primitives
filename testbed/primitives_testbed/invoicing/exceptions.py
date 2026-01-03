"""Exceptions for invoicing module."""


class InvoicingError(Exception):
    """Base exception for invoicing module."""

    pass


class ContextExtractionError(InvoicingError):
    """Failed to extract invoice context from basket/encounter."""

    pass


class BasketNotCommittedError(InvoicingError):
    """Basket must be committed before invoicing."""

    pass


class PricingError(InvoicingError):
    """Error during basket pricing."""

    pass


class MixedCurrencyError(PricingError):
    """Basket contains items with different currencies."""

    pass


class InvoiceStateError(InvoicingError):
    """Invalid invoice state transition."""

    pass


class LedgerIntegrationError(InvoicingError):
    """Failed to record ledger transaction."""

    pass
