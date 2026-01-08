"""Tests for T-002: Cancellation Policy Schema.

This module tests the cancellation policy schema validation.

A cancellation policy defines time-based refund tiers:
- hours_before: minimum hours before departure for this tier
- refund_percent: percentage of booking price refunded (0-100)

Tiers are evaluated in order: first matching tier applies.
"""

import pytest


# =============================================================================
# T-002: Cancellation Policy Schema Tests
# =============================================================================


class TestCancellationPolicySchemaValidation:
    """Test: validate_cancellation_policy() validates schema."""

    def test_valid_policy_with_tiers(self):
        """Valid policy with multiple refund tiers passes validation."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 48, "refund_percent": 100},
                {"hours_before": 24, "refund_percent": 50},
                {"hours_before": 0, "refund_percent": 0},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is True
        assert result.errors == []

    def test_valid_policy_single_tier(self):
        """Valid policy with single tier (all-or-nothing) passes."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": 100},
                {"hours_before": 0, "refund_percent": 0},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is True

    def test_valid_policy_with_no_show_penalty(self):
        """Policy can include no-show penalty percentage."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": 100},
                {"hours_before": 0, "refund_percent": 0},
            ],
            "no_show_penalty_percent": 100,
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is True

    def test_valid_policy_with_operator_cancel_rule(self):
        """Policy can include operator cancellation rule."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": 100},
                {"hours_before": 0, "refund_percent": 0},
            ],
            "operator_cancel_refund_percent": 100,
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is True


class TestCancellationPolicySchemaRejection:
    """Test: validate_cancellation_policy() rejects invalid schemas."""

    def test_missing_version_fails(self):
        """Policy without version is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "tiers": [
                {"hours_before": 24, "refund_percent": 100},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "version" in str(result.errors).lower()

    def test_missing_tiers_fails(self):
        """Policy without tiers is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "tiers" in str(result.errors).lower()

    def test_empty_tiers_fails(self):
        """Policy with empty tiers list is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "tier" in str(result.errors).lower()

    def test_tier_missing_hours_before_fails(self):
        """Tier without hours_before is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"refund_percent": 100},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "hours_before" in str(result.errors).lower()

    def test_tier_missing_refund_percent_fails(self):
        """Tier without refund_percent is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "refund_percent" in str(result.errors).lower()

    def test_negative_hours_before_fails(self):
        """Negative hours_before is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": -1, "refund_percent": 100},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "hours_before" in str(result.errors).lower()

    def test_refund_percent_over_100_fails(self):
        """refund_percent > 100 is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": 150},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "refund_percent" in str(result.errors).lower()

    def test_refund_percent_negative_fails(self):
        """refund_percent < 0 is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": -10},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "refund_percent" in str(result.errors).lower()

    def test_tiers_not_descending_fails(self):
        """Tiers must be in descending order by hours_before."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": 100},
                {"hours_before": 48, "refund_percent": 50},  # Wrong order
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "descending" in str(result.errors).lower() or "order" in str(result.errors).lower()

    def test_duplicate_hours_before_fails(self):
        """Duplicate hours_before values are invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": 100},
                {"hours_before": 24, "refund_percent": 50},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "duplicate" in str(result.errors).lower()

    def test_no_show_penalty_over_100_fails(self):
        """no_show_penalty_percent > 100 is invalid."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 0, "refund_percent": 0},
            ],
            "no_show_penalty_percent": 150,
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False
        assert "no_show" in str(result.errors).lower()

    def test_non_integer_hours_before_fails(self):
        """hours_before must be an integer."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": "24", "refund_percent": 100},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False

    def test_non_numeric_refund_percent_fails(self):
        """refund_percent must be numeric."""
        from primitives_testbed.diveops.cancellation_policy import (
            validate_cancellation_policy,
        )

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": "full"},
            ],
        }

        result = validate_cancellation_policy(policy)
        assert result.is_valid is False


class TestCancellationPolicySchemaConstants:
    """Test: CANCELLATION_POLICY_SCHEMA defines canonical structure."""

    def test_schema_has_version(self):
        """Schema defines version field."""
        from primitives_testbed.diveops.cancellation_policy import (
            CANCELLATION_POLICY_SCHEMA,
        )

        assert "version" in CANCELLATION_POLICY_SCHEMA["properties"]

    def test_schema_has_tiers(self):
        """Schema defines tiers array."""
        from primitives_testbed.diveops.cancellation_policy import (
            CANCELLATION_POLICY_SCHEMA,
        )

        assert "tiers" in CANCELLATION_POLICY_SCHEMA["properties"]
        assert CANCELLATION_POLICY_SCHEMA["properties"]["tiers"]["type"] == "array"

    def test_schema_tier_has_required_fields(self):
        """Schema tier items define hours_before and refund_percent."""
        from primitives_testbed.diveops.cancellation_policy import (
            CANCELLATION_POLICY_SCHEMA,
        )

        tier_schema = CANCELLATION_POLICY_SCHEMA["properties"]["tiers"]["items"]
        assert "hours_before" in tier_schema["properties"]
        assert "refund_percent" in tier_schema["properties"]


class TestCancellationPolicyValidationResult:
    """Test: ValidationResult dataclass behavior."""

    def test_valid_result_is_truthy(self):
        """Valid result evaluates as truthy in boolean context."""
        from primitives_testbed.diveops.cancellation_policy import ValidationResult

        result = ValidationResult(is_valid=True, errors=[])
        assert result
        assert bool(result) is True

    def test_invalid_result_is_falsy(self):
        """Invalid result evaluates as falsy in boolean context."""
        from primitives_testbed.diveops.cancellation_policy import ValidationResult

        result = ValidationResult(is_valid=False, errors=["Some error"])
        assert not result
        assert bool(result) is False


class TestDefaultCancellationPolicy:
    """Test: Default cancellation policy for DiveOps."""

    def test_default_policy_is_valid(self):
        """DEFAULT_CANCELLATION_POLICY passes validation."""
        from primitives_testbed.diveops.cancellation_policy import (
            DEFAULT_CANCELLATION_POLICY,
            validate_cancellation_policy,
        )

        result = validate_cancellation_policy(DEFAULT_CANCELLATION_POLICY)
        assert result.is_valid is True

    def test_default_policy_has_reasonable_tiers(self):
        """Default policy has sensible dive shop defaults."""
        from primitives_testbed.diveops.cancellation_policy import (
            DEFAULT_CANCELLATION_POLICY,
        )

        # Should have at least 2 tiers (refundable window + no-refund)
        assert len(DEFAULT_CANCELLATION_POLICY["tiers"]) >= 2

        # First tier should be full refund for advance cancellations
        first_tier = DEFAULT_CANCELLATION_POLICY["tiers"][0]
        assert first_tier["refund_percent"] == 100

        # Last tier should handle last-minute (0 hours)
        last_tier = DEFAULT_CANCELLATION_POLICY["tiers"][-1]
        assert last_tier["hours_before"] == 0
