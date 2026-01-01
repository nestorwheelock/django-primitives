"""Exceptions for django-money."""


class CurrencyMismatchError(ValueError):
    """Raised when attempting operations between different currencies."""
    pass


class MoneyOverflowError(ValueError):
    """Raised when money value exceeds maximum precision."""
    pass
