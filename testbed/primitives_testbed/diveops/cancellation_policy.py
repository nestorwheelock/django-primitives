"""Cancellation policy schema and validation for DiveOps.

T-002: Cancellation Policy Schema
T-004: Cancellation Refund Decision

Defines the canonical JSON schema for cancellation policies used in
booking agreements. Policies define time-based refund tiers.

Schema structure:
{
    "version": 1,
    "tiers": [
        {"hours_before": 48, "refund_percent": 100},
        {"hours_before": 24, "refund_percent": 50},
        {"hours_before": 0, "refund_percent": 0},
    ],
    "no_show_penalty_percent": 100,  # optional
    "operator_cancel_refund_percent": 100,  # optional
}

Tiers are evaluated in order: first matching tier applies.
Tiers must be in descending order by hours_before.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class ValidationResult:
    """Result of cancellation policy validation.

    Attributes:
        is_valid: True if policy passes all validation rules
        errors: List of error messages (empty if valid)
    """

    is_valid: bool
    errors: list[str]

    def __bool__(self) -> bool:
        """Allow truthy/falsy evaluation based on is_valid."""
        return self.is_valid


# Canonical JSON schema for cancellation policies
CANCELLATION_POLICY_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["version", "tiers"],
    "properties": {
        "version": {
            "type": "integer",
            "minimum": 1,
            "description": "Schema version for forward compatibility",
        },
        "tiers": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["hours_before", "refund_percent"],
                "properties": {
                    "hours_before": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Minimum hours before departure for this tier",
                    },
                    "refund_percent": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Percentage of booking price refunded (0-100)",
                    },
                },
                "additionalProperties": False,
            },
            "description": "Refund tiers in descending order by hours_before",
        },
        "no_show_penalty_percent": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Penalty percentage for no-shows (optional)",
        },
        "operator_cancel_refund_percent": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Refund percentage when operator cancels (optional)",
        },
    },
    "additionalProperties": False,
}


# Default cancellation policy for DiveOps bookings
DEFAULT_CANCELLATION_POLICY: dict = {
    "version": 1,
    "tiers": [
        {"hours_before": 48, "refund_percent": 100},  # 48+ hours: full refund
        {"hours_before": 24, "refund_percent": 50},  # 24-48 hours: 50% refund
        {"hours_before": 0, "refund_percent": 0},  # <24 hours: no refund
    ],
    "no_show_penalty_percent": 100,
    "operator_cancel_refund_percent": 100,
}


def validate_cancellation_policy(policy: dict) -> ValidationResult:
    """Validate a cancellation policy against the canonical schema.

    Performs structural validation (required fields, types) and semantic
    validation (tier ordering, no duplicates).

    Args:
        policy: Dictionary representing the cancellation policy

    Returns:
        ValidationResult with is_valid flag and list of errors
    """
    errors: list[str] = []

    # Check required top-level fields
    if not isinstance(policy, dict):
        return ValidationResult(is_valid=False, errors=["Policy must be a dictionary"])

    if "version" not in policy:
        errors.append("Missing required field: version")

    if "tiers" not in policy:
        errors.append("Missing required field: tiers")
        return ValidationResult(is_valid=False, errors=errors)

    # Validate version
    if "version" in policy:
        version = policy["version"]
        if not isinstance(version, int) or version < 1:
            errors.append("version must be a positive integer")

    # Validate tiers
    tiers = policy.get("tiers", [])
    if not isinstance(tiers, list):
        errors.append("tiers must be a list")
        return ValidationResult(is_valid=False, errors=errors)

    if len(tiers) == 0:
        errors.append("tiers must contain at least one tier")
        return ValidationResult(is_valid=False, errors=errors)

    # Validate each tier
    seen_hours: set[int] = set()
    prev_hours: int | None = None

    for i, tier in enumerate(tiers):
        tier_prefix = f"tier[{i}]"

        if not isinstance(tier, dict):
            errors.append(f"{tier_prefix}: must be a dictionary")
            continue

        # Check hours_before
        if "hours_before" not in tier:
            errors.append(f"{tier_prefix}: missing required field hours_before")
        else:
            hours = tier["hours_before"]
            if not isinstance(hours, int):
                errors.append(f"{tier_prefix}: hours_before must be an integer")
            elif hours < 0:
                errors.append(f"{tier_prefix}: hours_before must be >= 0")
            else:
                # Check for duplicates
                if hours in seen_hours:
                    errors.append(f"{tier_prefix}: duplicate hours_before value {hours}")
                seen_hours.add(hours)

                # Check descending order
                if prev_hours is not None and hours >= prev_hours:
                    errors.append(
                        f"{tier_prefix}: tiers must be in descending order by hours_before"
                    )
                prev_hours = hours

        # Check refund_percent
        if "refund_percent" not in tier:
            errors.append(f"{tier_prefix}: missing required field refund_percent")
        else:
            percent = tier["refund_percent"]
            if not isinstance(percent, (int, float)):
                errors.append(f"{tier_prefix}: refund_percent must be a number")
            elif percent < 0:
                errors.append(f"{tier_prefix}: refund_percent must be >= 0")
            elif percent > 100:
                errors.append(f"{tier_prefix}: refund_percent must be <= 100")

    # Validate optional fields
    if "no_show_penalty_percent" in policy:
        penalty = policy["no_show_penalty_percent"]
        if not isinstance(penalty, (int, float)):
            errors.append("no_show_penalty_percent must be a number")
        elif penalty < 0 or penalty > 100:
            errors.append("no_show_penalty_percent must be between 0 and 100")

    if "operator_cancel_refund_percent" in policy:
        refund = policy["operator_cancel_refund_percent"]
        if not isinstance(refund, (int, float)):
            errors.append("operator_cancel_refund_percent must be a number")
        elif refund < 0 or refund > 100:
            errors.append("operator_cancel_refund_percent must be between 0 and 100")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


# =============================================================================
# T-004: Refund Decision
# =============================================================================


@dataclass(frozen=True)
class RefundDecision:
    """Immutable result of refund calculation.

    Captures the refund decision WITHOUT executing any money movement.
    This is a DECISION, not a transaction.

    Attributes:
        refund_amount: Amount to refund (Decimal, 2 decimal places)
        refund_percent: Percentage applied (0-100)
        original_amount: Original booking price
        currency: Currency code
        hours_before_departure: Hours between cancellation and departure
        policy_tier_applied: The tier that matched
        reason: Human-readable explanation
    """

    refund_amount: Decimal
    refund_percent: int
    original_amount: Decimal
    currency: str
    hours_before_departure: int
    policy_tier_applied: dict
    reason: str


def compute_refund_decision(
    original_amount: Decimal,
    currency: str,
    departure_time: datetime,
    cancellation_time: datetime,
    policy: dict,
) -> RefundDecision:
    """Compute refund decision based on cancellation policy.

    Evaluates the cancellation time against the policy tiers and
    determines the appropriate refund percentage and amount.

    Args:
        original_amount: Original booking price
        currency: Currency code
        departure_time: When the excursion departs
        cancellation_time: When the cancellation is requested
        policy: Cancellation policy with tiers

    Returns:
        RefundDecision with computed refund details
    """
    # Calculate hours before departure
    time_delta = departure_time - cancellation_time
    hours_before = int(time_delta.total_seconds() / 3600)

    # Handle past departures
    if hours_before < 0:
        hours_before = 0

    # Find matching tier (tiers are in descending order by hours_before)
    # First tier where hours_before >= tier.hours_before applies
    tiers = policy.get("tiers", [])
    matched_tier = None

    for tier in tiers:
        if hours_before >= tier["hours_before"]:
            matched_tier = tier
            break

    # If no tier matched (shouldn't happen with valid policy), use 0%
    if matched_tier is None:
        matched_tier = {"hours_before": 0, "refund_percent": 0}

    refund_percent = matched_tier["refund_percent"]

    # Calculate refund amount with proper rounding
    refund_amount = (original_amount * Decimal(refund_percent) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Build reason
    if refund_percent == 100:
        reason = f"Full refund - cancelled {hours_before} hours before departure"
    elif refund_percent == 0:
        reason = f"No refund - cancelled {hours_before} hours before departure"
    else:
        reason = f"{refund_percent}% refund - cancelled {hours_before} hours before departure"

    return RefundDecision(
        refund_amount=refund_amount,
        refund_percent=refund_percent,
        original_amount=original_amount,
        currency=currency,
        hours_before_departure=hours_before,
        policy_tier_applied=matched_tier,
        reason=reason,
    )
