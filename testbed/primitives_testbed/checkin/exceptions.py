"""Exceptions for check-in module."""


class CheckinError(Exception):
    """Base exception for check-in errors."""

    pass


class MissingConsentError(CheckinError):
    """Raised when required consents are missing."""

    def __init__(self, missing_consents: list):
        self.missing_consents = missing_consents
        super().__init__(f"Missing required consents: {', '.join(missing_consents)}")


class NoPricesAvailableError(CheckinError):
    """Raised when no prices are available for disclosure."""

    pass


class DisclosureValidationError(CheckinError):
    """Raised when invoice prices don't match disclosed prices."""

    def __init__(self, discrepancies: list):
        self.discrepancies = discrepancies
        super().__init__(f"Price discrepancies found: {len(discrepancies)} items")
