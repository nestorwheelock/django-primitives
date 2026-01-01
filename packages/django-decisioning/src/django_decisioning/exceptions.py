"""Exceptions for django-decisioning."""


class DecisioningError(Exception):
    """Base exception for decisioning errors."""
    pass


class IdempotencyError(DecisioningError):
    """Error related to idempotency operations."""
    pass


class StaleRequestError(IdempotencyError):
    """Request is stale and cannot be processed."""
    pass


class DuplicateRequestError(IdempotencyError):
    """Request has already been processed."""
    pass


class InFlightRequestError(IdempotencyError):
    """Request is currently being processed by another worker."""
    pass


class TimeValidationError(DecisioningError):
    """Error related to time semantics validation."""
    pass


class BackdateNotAllowedError(TimeValidationError):
    """Backdating is not allowed for this record type."""
    pass


class FutureDateNotAllowedError(TimeValidationError):
    """Future effective_at is not allowed for this record type."""
    pass


class BackdateTooFarError(TimeValidationError):
    """Backdating exceeds the maximum allowed period."""
    pass


class DecisionValidationError(DecisioningError):
    """Error validating a Decision record."""
    pass


class NoActorError(DecisionValidationError):
    """Decision must have at least one actor."""
    pass
