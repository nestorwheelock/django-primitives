"""Eligibility decisioning for dive operations.

This module provides rule-based eligibility checks for diving operations.
Uses temporal evaluation to determine eligibility at a specific point in time.
"""

from dataclasses import dataclass, field
from datetime import datetime

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
