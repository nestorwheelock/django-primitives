"""Exceptions for django-sequence."""


class SequenceError(Exception):
    """Base exception for sequence errors."""
    pass


class SequenceNotFoundError(SequenceError):
    """Raised when a sequence doesn't exist and auto_create is False."""
    pass


class SequenceLockedError(SequenceError):
    """Raised when a sequence cannot be locked (timeout)."""
    pass
