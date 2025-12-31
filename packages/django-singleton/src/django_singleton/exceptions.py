"""Custom exceptions for django-singleton."""


class SingletonError(Exception):
    """Base exception for singleton errors."""
    pass


class SingletonDeletionError(SingletonError):
    """Raised when attempting to delete a singleton."""
    pass


class SingletonViolationError(SingletonError):
    """Raised when singleton invariant would be violated."""
    pass
