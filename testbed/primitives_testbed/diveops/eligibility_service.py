"""Eligibility service for booking excursions.

Checks if a diver is eligible for an excursion based on certification requirements.
Supports explicit overrides with audit trail.

The service applies checks based on:
- ExcursionType.requires_cert (False for DSD = skip check)
- ExcursionType.min_certification_level (diver must meet or exceed)
- Diver's highest active certification rank

INV-2: Layered Eligibility Hierarchy
    - Single entry point: check_layered_eligibility(diver, target, *, effective_at=None)
    - Target can be: ExcursionType, Excursion, Trip, or Booking
    - Evaluates layers: ExcursionType → Excursion → Trip
    - Short-circuits on first failure
    - Respects effective_at time parameter
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils import timezone

from .audit import Actions, log_eligibility_event
from .models import DiverProfile, Excursion, ExcursionType

if TYPE_CHECKING:
    from .models import Booking, Trip


@dataclass(frozen=True)
class EligibilityResult:
    """Immutable result of eligibility check.

    Attributes:
        eligible: True if diver meets requirements
        reason: Empty if eligible, else explanation of why not
        override_allowed: True if an override can be applied
        diver_rank: Diver's highest certification rank (None if uncertified)
        required_rank: Required certification rank (None if no requirement)
    """

    eligible: bool
    reason: str
    override_allowed: bool
    diver_rank: int | None
    required_rank: int | None


@dataclass(frozen=True)
class EligibilityOverrideResult:
    """Result of an eligibility override request.

    Attributes:
        success: True if override was recorded
        approver: User who approved the override
        reason: Justification for the override
    """

    success: bool
    approver: object  # User
    reason: str


def get_diver_highest_certification_rank(diver: DiverProfile) -> int | None:
    """Get the highest active certification rank for a diver.

    Only considers current (non-expired) certifications.

    Args:
        diver: DiverProfile to check

    Returns:
        Highest rank number, or None if no active certifications
    """
    today = date.today()

    # Get all active certifications (not soft-deleted)
    certifications = diver.certifications.select_related("level").all()

    highest_rank = None
    for cert in certifications:
        # Skip expired certifications
        if cert.expires_on is not None and cert.expires_on <= today:
            continue

        rank = cert.level.rank
        if highest_rank is None or rank > highest_rank:
            highest_rank = rank

    return highest_rank


def check_eligibility(
    diver: DiverProfile,
    excursion_type: ExcursionType | None,
) -> EligibilityResult:
    """Check if a diver is eligible for an excursion type.

    Eligibility rules:
    1. If excursion_type is None → eligible (no restrictions)
    2. If excursion_type.requires_cert is False → eligible (DSD)
    3. If excursion_type.min_certification_level is None → eligible (no cert required)
    4. Otherwise, diver's highest cert rank must >= required rank

    Args:
        diver: DiverProfile to check
        excursion_type: ExcursionType with requirements (None = no restrictions)

    Returns:
        EligibilityResult with eligibility status and details
    """
    # Rule 1: No excursion type = no restrictions
    if excursion_type is None:
        return EligibilityResult(
            eligible=True,
            reason="",
            override_allowed=False,
            diver_rank=None,
            required_rank=None,
        )

    # Rule 2: DSD and training dives don't require certification
    if not excursion_type.requires_cert:
        return EligibilityResult(
            eligible=True,
            reason="",
            override_allowed=False,
            diver_rank=None,
            required_rank=None,
        )

    # Rule 3: No minimum certification level = eligible
    if excursion_type.min_certification_level is None:
        return EligibilityResult(
            eligible=True,
            reason="",
            override_allowed=False,
            diver_rank=None,
            required_rank=None,
        )

    # Rule 4: Check diver's certification against required level
    required_rank = excursion_type.min_certification_level.rank
    diver_rank = get_diver_highest_certification_rank(diver)

    if diver_rank is None:
        return EligibilityResult(
            eligible=False,
            reason=f"Diver has no certification. Required: {excursion_type.min_certification_level.name}",
            override_allowed=True,
            diver_rank=None,
            required_rank=required_rank,
        )

    if diver_rank < required_rank:
        return EligibilityResult(
            eligible=False,
            reason=f"Diver certification rank ({diver_rank}) is below required ({required_rank})",
            override_allowed=True,
            diver_rank=diver_rank,
            required_rank=required_rank,
        )

    # Diver meets or exceeds certification requirement
    return EligibilityResult(
        eligible=True,
        reason="",
        override_allowed=False,
        diver_rank=diver_rank,
        required_rank=required_rank,
    )


def check_booking_eligibility(
    diver: DiverProfile,
    excursion: Excursion,
) -> EligibilityResult:
    """Check if a diver is eligible to book an excursion.

    Delegates to check_eligibility using the excursion's type.

    Args:
        diver: DiverProfile to check
        excursion: Excursion to book

    Returns:
        EligibilityResult with eligibility status and details
    """
    return check_eligibility(diver, excursion.excursion_type)


def record_eligibility_override(
    *,
    diver: DiverProfile,
    excursion_type: ExcursionType,
    approver,
    reason: str,
    request=None,
) -> EligibilityOverrideResult:
    """Record an eligibility override with audit trail.

    Creates an audit event documenting that a diver's eligibility
    requirements were overridden by an authorized approver.

    Args:
        diver: DiverProfile being overridden
        excursion_type: ExcursionType the diver is being allowed to book
        approver: User who approved the override (required)
        reason: Justification for the override (required)
        request: Optional HTTP request for IP/UA extraction

    Returns:
        EligibilityOverrideResult with success status

    Raises:
        ValueError: If approver or reason is missing/empty
    """
    if not approver:
        raise ValueError("approver is required for eligibility override")

    if not reason or not reason.strip():
        raise ValueError("reason is required for eligibility override")

    # Log the override event
    log_eligibility_event(
        action=Actions.ELIGIBILITY_OVERRIDDEN,
        diver=diver,
        excursion=excursion_type,  # Using excursion_type as the "excursion" for audit
        actor=approver,
        data={
            "reason": reason,
            "excursion_type_id": str(excursion_type.pk),
            "excursion_type_name": excursion_type.name,
        },
        request=request,
    )

    return EligibilityOverrideResult(
        success=True,
        approver=approver,
        reason=reason,
    )


# =============================================================================
# INV-1: Booking-Scoped Eligibility Override
# =============================================================================


def record_booking_eligibility_override(
    booking: "Booking",
    diver: DiverProfile,
    *,
    requirement_type: str,
    original_requirement: dict,
    approver,
    reason: str,
    effective_at: datetime | None = None,
) -> "EligibilityOverride":
    """Record a booking-level eligibility override (INV-1).

    Creates an EligibilityOverride record that allows a specific booking
    to bypass eligibility requirements. This is booking-scoped ONLY and
    does not affect any other bookings, excursions, or trips.

    Args:
        booking: Booking to override eligibility for
        diver: DiverProfile being overridden
        requirement_type: Type of requirement being bypassed (e.g., "certification")
        original_requirement: Original requirement that was bypassed (dict for audit)
        approver: User who approved the override (required)
        reason: Justification for the override (required)
        effective_at: When the override was approved (defaults to now)

    Returns:
        EligibilityOverride instance

    Raises:
        ValueError: If approver or reason is missing/empty
    """
    from .audit import log_booking_override_event
    from .models import EligibilityOverride

    if not approver:
        raise ValueError("approver is required for booking eligibility override")

    if not reason or not reason.strip():
        raise ValueError("reason is required for booking eligibility override")

    if effective_at is None:
        effective_at = timezone.now()

    # Create the override record
    override = EligibilityOverride.objects.create(
        booking=booking,
        diver=diver,
        requirement_type=requirement_type,
        original_requirement=original_requirement,
        reason=reason,
        approved_by=approver,
        approved_at=effective_at,
    )

    # Emit audit event
    log_booking_override_event(override=override, actor=approver)

    return override


# =============================================================================
# INV-2: Unified Layered Eligibility Engine
# =============================================================================


@dataclass(frozen=True)
class LayeredEligibilityResult:
    """Immutable result of layered eligibility check.

    This is the unified result type for check_layered_eligibility().

    Attributes:
        eligible: True if diver meets all requirements
        reason: Empty if eligible, else explanation of why not
        override_allowed: True if an override can be applied
        checked_layers: List of layers that were evaluated (e.g., ["excursion_type", "excursion"])
        diver_rank: Diver's highest certification rank (None if uncertified)
        required_rank: Required certification rank (None if no requirement)
        override_used: True if eligibility granted via booking-level override (INV-1)
    """

    eligible: bool
    reason: str
    override_allowed: bool
    checked_layers: list[str] = field(default_factory=list)
    diver_rank: int | None = None
    required_rank: int | None = None
    override_used: bool = False


def get_diver_highest_certification_rank_as_of(
    diver: DiverProfile,
    as_of: date | None = None,
) -> int | None:
    """Get the highest active certification rank for a diver at a point in time.

    Only considers certifications that were valid at the specified time.

    Args:
        diver: DiverProfile to check
        as_of: Date to evaluate (defaults to today)

    Returns:
        Highest rank number, or None if no active certifications
    """
    if as_of is None:
        as_of = date.today()

    # Get all active certifications (not soft-deleted)
    certifications = diver.certifications.select_related("level").filter(
        Q(expires_on__isnull=True) | Q(expires_on__gt=as_of)
    )

    highest_rank = None
    for cert in certifications:
        rank = cert.level.rank
        if highest_rank is None or rank > highest_rank:
            highest_rank = rank

    return highest_rank


def _check_excursion_type_eligibility(
    diver: DiverProfile,
    excursion_type: ExcursionType | None,
    as_of_date: date,
) -> tuple[bool, str, bool, int | None, int | None]:
    """Check eligibility for an ExcursionType.

    Returns:
        Tuple of (eligible, reason, override_allowed, diver_rank, required_rank)
    """
    # No excursion type = no restrictions
    if excursion_type is None:
        return True, "", False, None, None

    # DSD and training dives don't require certification
    if not excursion_type.requires_cert:
        return True, "", False, None, None

    # No minimum certification level = eligible
    if excursion_type.min_certification_level is None:
        return True, "", False, None, None

    # Check diver's certification against required level
    required_rank = excursion_type.min_certification_level.rank
    diver_rank = get_diver_highest_certification_rank_as_of(diver, as_of_date)

    if diver_rank is None:
        return (
            False,
            f"Diver has no certification. Required: {excursion_type.min_certification_level.name}",
            True,
            None,
            required_rank,
        )

    if diver_rank < required_rank:
        return (
            False,
            f"Diver certification rank ({diver_rank}) is below required ({required_rank})",
            True,
            diver_rank,
            required_rank,
        )

    # Diver meets or exceeds certification requirement
    return True, "", False, diver_rank, required_rank


def _check_trip_eligibility(
    diver: DiverProfile,
    trip: "Trip",
    as_of: datetime,
) -> tuple[bool, str]:
    """Check Trip-level eligibility (status, capacity, medical, departure).

    Returns:
        Tuple of (eligible, reason)
    """
    as_of_date = as_of.date() if hasattr(as_of, "date") else as_of

    # Check: Trip is not cancelled
    if trip.status == "cancelled":
        return False, "Trip has been cancelled"

    # Check: Trip has not started (compare start_date to as_of_date)
    if trip.start_date <= as_of_date:
        return False, "Trip has already started or is in the past"

    return True, ""


def check_layered_eligibility(
    diver: DiverProfile,
    target: "ExcursionType | Excursion | Trip | Booking",
    *,
    effective_at: datetime | None = None,
) -> LayeredEligibilityResult:
    """Unified eligibility check supporting layered hierarchy.

    INV-2: Single authoritative entry point for all eligibility checks.
    INV-1: Booking-level overrides are checked for Booking targets.

    Layer evaluation order:
    1. ExcursionType (certification requirements)
    2. Excursion (operational requirements)
    3. Trip (commercial/status requirements)

    Short-circuits on first failure, UNLESS a booking-level override exists (INV-1).

    Args:
        diver: DiverProfile to check
        target: The target entity to check eligibility for.
                Can be ExcursionType, Excursion, Trip, or Booking.
        effective_at: Point in time to evaluate (defaults to now)

    Returns:
        LayeredEligibilityResult with eligibility status, reason, and checked_layers
    """
    from .models import Booking, EligibilityOverride, Trip

    if effective_at is None:
        effective_at = timezone.now()

    as_of_date = effective_at.date() if hasattr(effective_at, "date") else effective_at
    checked_layers: list[str] = []

    # Determine target type and extract layers
    excursion_type: ExcursionType | None = None
    excursion: Excursion | None = None
    trip: Trip | None = None
    booking: Booking | None = None

    if isinstance(target, ExcursionType):
        excursion_type = target
    elif isinstance(target, Excursion):
        excursion = target
        excursion_type = target.excursion_type
        trip = target.trip
    elif isinstance(target, Trip):
        trip = target
        # Trip may have excursions with types, but Trip-level check doesn't
        # require excursion_type layer
    elif isinstance(target, Booking):
        booking = target
        excursion = target.excursion
        excursion_type = excursion.excursion_type if excursion else None
        trip = excursion.trip if excursion else None
    else:
        raise TypeError(f"Unsupported target type: {type(target).__name__}")

    # INV-1: Check for booking-level override (only for Booking targets)
    has_override = False
    if booking is not None:
        has_override = EligibilityOverride.objects.filter(
            booking=booking, diver=diver
        ).exists()

    # Layer 1: ExcursionType eligibility (certification)
    if excursion_type is not None:
        checked_layers.append("excursion_type")
        eligible, reason, override_allowed, diver_rank, required_rank = (
            _check_excursion_type_eligibility(diver, excursion_type, as_of_date)
        )
        if not eligible:
            # INV-1: Check if booking-level override permits eligibility
            if has_override:
                return LayeredEligibilityResult(
                    eligible=True,
                    reason="",
                    override_allowed=False,
                    checked_layers=checked_layers,
                    diver_rank=diver_rank,
                    required_rank=required_rank,
                    override_used=True,
                )
            return LayeredEligibilityResult(
                eligible=False,
                reason=reason,
                override_allowed=override_allowed,
                checked_layers=checked_layers,
                diver_rank=diver_rank,
                required_rank=required_rank,
            )

    # Layer 2: Excursion eligibility (operational requirements)
    # For now, excursion layer delegates to excursion_type (already checked)
    # Future: Add ExcursionRequirement checks here
    if excursion is not None and "excursion_type" not in checked_layers:
        # If excursion has a type but we haven't checked it yet
        if excursion.excursion_type is not None:
            checked_layers.append("excursion_type")
            eligible, reason, override_allowed, diver_rank, required_rank = (
                _check_excursion_type_eligibility(diver, excursion.excursion_type, as_of_date)
            )
            if not eligible:
                # INV-1: Check if booking-level override permits eligibility
                if has_override:
                    return LayeredEligibilityResult(
                        eligible=True,
                        reason="",
                        override_allowed=False,
                        checked_layers=checked_layers,
                        diver_rank=diver_rank,
                        required_rank=required_rank,
                        override_used=True,
                    )
                return LayeredEligibilityResult(
                    eligible=False,
                    reason=reason,
                    override_allowed=override_allowed,
                    checked_layers=checked_layers,
                    diver_rank=diver_rank,
                    required_rank=required_rank,
                )

    # Layer 3: Trip eligibility (status, capacity, etc.)
    if trip is not None:
        checked_layers.append("trip")
        eligible, reason = _check_trip_eligibility(diver, trip, effective_at)
        if not eligible:
            return LayeredEligibilityResult(
                eligible=False,
                reason=reason,
                override_allowed=False,  # Trip-level issues can't be overridden
                checked_layers=checked_layers,
            )

    # All layers passed
    return LayeredEligibilityResult(
        eligible=True,
        reason="",
        override_allowed=False,
        checked_layers=checked_layers,
    )
