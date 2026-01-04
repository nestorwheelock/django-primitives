"""Exceptions for diveops module."""


class DiveOpsError(Exception):
    """Base exception for dive operations."""


class BookingError(DiveOpsError):
    """Error during booking process."""


class EligibilityError(DiveOpsError):
    """Error related to diver eligibility."""


class TripStateError(DiveOpsError):
    """Error related to trip state transitions."""


class CheckInError(DiveOpsError):
    """Error during check-in process."""


class TripCapacityError(BookingError):
    """Trip is at capacity."""


class DiverNotEligibleError(BookingError):
    """Diver is not eligible for this trip."""


class CertificationError(DiveOpsError):
    """Error related to diver certification operations."""
