"""Eligibility decisioning for dive operations.

This module provides rule-based eligibility checks for diving operations.
Uses temporal evaluation to determine eligibility at a specific point in time.

Two versions available:
- can_diver_join_trip: Uses legacy string-based certification fields
- can_diver_join_trip_v2: Uses normalized TripRequirement and DiverCertification models
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from django.db.models import Q
from django.utils import timezone

from .models import DiverProfile, DiveTrip


@dataclass
class EligibilityResult:
    """Result of an eligibility check.

    Attributes:
        allowed: Whether the action is allowed
        reasons: List of reasons why action is not allowed (if any)
        required_actions: List of actions the user can take to become eligible
    """

    allowed: bool
    reasons: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)


def can_diver_join_trip(
    diver: DiverProfile,
    trip: DiveTrip,
    as_of: datetime | None = None,
) -> EligibilityResult:
    """Check if a diver is eligible to join a trip.

    Evaluates:
    - Trip status (not cancelled, not past)
    - Trip capacity (spots available)
    - Diver certification level (meets site requirements)
    - Medical clearance (current as of evaluation date)

    Args:
        diver: The diver profile to check
        trip: The trip to join
        as_of: Point in time to evaluate (defaults to now)

    Returns:
        EligibilityResult with allowed status, reasons, and required actions
    """
    if as_of is None:
        as_of = timezone.now()

    as_of_date = as_of.date() if hasattr(as_of, "date") else as_of

    reasons: list[str] = []
    required_actions: list[str] = []

    # Check 1: Trip is not cancelled
    if trip.status == "cancelled":
        reasons.append("Trip has been cancelled")
        # No action - trip is cancelled

    # Check 2: Trip has not departed
    if trip.departure_time <= as_of:
        reasons.append("Trip has already departed")
        # No action - past trip

    # Check 3: Trip has capacity
    if trip.spots_available <= 0:
        reasons.append("Trip is at full capacity")
        required_actions.append("Check for cancellations or book a different trip")

    # Check 4: Diver meets certification requirements
    site = trip.dive_site
    if not diver.meets_certification_level(site.min_certification_level):
        level_display = dict(DiverProfile.CERTIFICATION_LEVELS).get(
            site.min_certification_level, site.min_certification_level
        )
        reasons.append(
            f"Diver certification ({diver.get_certification_level_display()}) "
            f"does not meet site requirement ({level_display})"
        )
        required_actions.append(
            f"Obtain {level_display} certification or higher (AOW/Advanced certification required)"
        )

    # Check 5: Diver has current medical clearance
    if not diver.is_medical_current_as_of(as_of_date):
        if diver.medical_clearance_valid_until is None:
            reasons.append("No medical clearance on file")
        else:
            reasons.append("Medical clearance has expired")
        required_actions.append("Provide current medical clearance certificate")

    allowed = len(reasons) == 0

    return EligibilityResult(
        allowed=allowed,
        reasons=reasons,
        required_actions=required_actions,
    )


def can_diver_join_trip_v2(
    diver: DiverProfile,
    trip: DiveTrip,
    as_of: datetime | None = None,
) -> EligibilityResult:
    """Check if a diver is eligible to join a trip using normalized models.

    Uses TripRequirement and DiverCertification models instead of legacy fields.

    Evaluates:
    - Trip status (not cancelled, not past)
    - Trip capacity (spots available)
    - TripRequirements (certification, experience, medical, gear)
    - DiverCertification records (current, not expired)

    Args:
        diver: The diver profile to check
        trip: The trip to join
        as_of: Point in time to evaluate (defaults to now)

    Returns:
        EligibilityResult with allowed status, reasons, and required actions
    """
    if as_of is None:
        as_of = timezone.now()

    as_of_date = as_of.date() if hasattr(as_of, "date") else as_of

    reasons: list[str] = []
    required_actions: list[str] = []

    # Check 1: Trip is not cancelled
    if trip.status == "cancelled":
        reasons.append("Trip has been cancelled")

    # Check 2: Trip has not departed
    if trip.departure_time <= as_of:
        reasons.append("Trip has already departed")

    # Check 3: Trip has capacity
    if trip.spots_available <= 0:
        reasons.append("Trip is at full capacity")
        required_actions.append("Check for cancellations or book a different trip")

    # Check 4: Diver has current medical clearance
    if not diver.is_medical_current_as_of(as_of_date):
        if diver.medical_clearance_valid_until is None:
            reasons.append("No medical clearance on file")
        else:
            reasons.append("Medical clearance has expired")
        required_actions.append("Provide current medical clearance certificate")

    # Check 5: Trip requirements (from TripRequirement model)
    _check_trip_requirements(diver, trip, as_of_date, reasons, required_actions)

    allowed = len(reasons) == 0

    return EligibilityResult(
        allowed=allowed,
        reasons=reasons,
        required_actions=required_actions,
    )


def _check_trip_requirements(
    diver: DiverProfile,
    trip: DiveTrip,
    as_of_date: date,
    reasons: list[str],
    required_actions: list[str],
) -> None:
    """Check trip requirements against diver qualifications.

    Modifies reasons and required_actions lists in place.
    """
    from .models import TripRequirement

    # Get mandatory requirements only
    mandatory_reqs = trip.requirements.filter(is_mandatory=True)

    for req in mandatory_reqs:
        if req.requirement_type == "certification":
            _check_certification_requirement(diver, req, as_of_date, reasons, required_actions)
        elif req.requirement_type == "experience":
            _check_experience_requirement(diver, req, reasons, required_actions)
        # Medical is already checked above (Check 4)
        # Gear requirements would need additional diver gear tracking


def _check_certification_requirement(
    diver: DiverProfile,
    req,  # TripRequirement
    as_of_date: date,
    reasons: list[str],
    required_actions: list[str],
) -> None:
    """Check if diver meets certification requirement."""
    required_level = req.certification_level
    if required_level is None:
        return  # No specific level required

    # Get diver's current (non-expired) certifications
    current_certs = diver.certifications.filter(
        Q(expires_on__isnull=True) | Q(expires_on__gt=as_of_date)
    ).select_related("level")

    # Find highest certification rank
    highest_rank = 0
    for cert in current_certs:
        if cert.level.rank > highest_rank:
            highest_rank = cert.level.rank

    # Check if diver meets requirement
    if highest_rank < required_level.rank:
        if highest_rank == 0:
            reasons.append(
                f"No valid certification on file. "
                f"This trip requires {required_level.name} certification."
            )
        else:
            # Get diver's highest cert for display
            highest_cert = current_certs.order_by("-level__rank").first()
            reasons.append(
                f"Diver certification ({highest_cert.level.name}) "
                f"does not meet trip requirement ({required_level.name})"
            )

        required_actions.append(
            f"Obtain {required_level.name} certification or higher"
        )


def _check_experience_requirement(
    diver: DiverProfile,
    req,  # TripRequirement
    reasons: list[str],
    required_actions: list[str],
) -> None:
    """Check if diver meets experience requirement."""
    if req.min_dives is None:
        return  # No specific dive count required

    if diver.total_dives < req.min_dives:
        reasons.append(
            f"Diver has {diver.total_dives} logged dives, "
            f"but this trip requires at least {req.min_dives} dives"
        )
        required_actions.append(
            f"Log at least {req.min_dives - diver.total_dives} more dives"
        )
