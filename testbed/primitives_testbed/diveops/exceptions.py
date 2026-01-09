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


class DiverError(DiveOpsError):
    """Error related to diver operations."""


# =============================================================================
# Agreement Exceptions
# =============================================================================


class AgreementError(DiveOpsError):
    """Base exception for agreement operations."""


class AgreementNotEditable(AgreementError):
    """Agreement cannot be edited (wrong status)."""


class ChangeNoteRequired(AgreementError):
    """Change note is required for editing an agreement."""


class VoidReasonRequired(AgreementError):
    """Reason is required for voiding an agreement."""


class InvalidToken(AgreementError):
    """Token is invalid or expired."""


class AgreementExpired(AgreementError):
    """Agreement has expired and cannot be signed."""


class AgreementAlreadySigned(AgreementError):
    """Agreement has already been signed."""


class InvalidStateTransition(AgreementError):
    """Invalid state transition attempted (e.g., voiding a signed agreement)."""
