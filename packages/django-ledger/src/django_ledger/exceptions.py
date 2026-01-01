"""Exceptions for django-ledger."""


class LedgerError(Exception):
    """Base exception for ledger errors."""
    pass


class UnbalancedTransactionError(LedgerError):
    """Raised when a transaction doesn't balance."""
    pass


class CurrencyMismatchError(LedgerError):
    """Raised when entry currency doesn't match account currency."""
    pass


class ImmutableEntryError(LedgerError):
    """Raised when attempting to modify a posted entry."""
    pass


class TransactionNotPostedError(LedgerError):
    """Raised when operating on an unposted transaction."""
    pass
