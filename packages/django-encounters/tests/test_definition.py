"""Tests for EncounterDefinition model.

Tests model-level validation that uses validate_definition_graph.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from django_encounters.models import EncounterDefinition


@pytest.fixture
def valid_definition_data():
    """Return data for a valid encounter definition."""
    return {
        "key": "test_workflow",
        "name": "Test Workflow",
        "states": ["pending", "active", "completed"],
        "transitions": {"pending": ["active"], "active": ["completed"]},
        "initial_state": "pending",
        "terminal_states": ["completed"],
    }


@pytest.mark.django_db
class TestEncounterDefinitionCreation:
    """Tests for EncounterDefinition model creation."""

    def test_create_valid_definition(self, valid_definition_data):
        """Valid definition saves successfully."""
        definition = EncounterDefinition(**valid_definition_data)
        definition.full_clean()
        definition.save()

        assert definition.pk is not None
        assert definition.key == "test_workflow"
        assert definition.active is True

    def test_default_values(self, valid_definition_data):
        """Default values are set correctly."""
        definition = EncounterDefinition(**valid_definition_data)
        definition.full_clean()
        definition.save()

        assert definition.active is True
        assert definition.validator_paths == []

    def test_timestamps_set_on_create(self, valid_definition_data):
        """created_at and updated_at are set on creation."""
        definition = EncounterDefinition(**valid_definition_data)
        definition.full_clean()
        definition.save()

        assert definition.created_at is not None
        assert definition.updated_at is not None


@pytest.mark.django_db
class TestEncounterDefinitionValidation:
    """Tests for EncounterDefinition model validation."""

    def test_invalid_initial_state_rejected(self, valid_definition_data):
        """Definition with invalid initial_state is rejected."""
        valid_definition_data["initial_state"] = "unknown"

        definition = EncounterDefinition(**valid_definition_data)

        with pytest.raises(ValidationError) as exc_info:
            definition.full_clean()

        assert "initial_state" in str(exc_info.value)

    def test_invalid_terminal_state_rejected(self, valid_definition_data):
        """Definition with invalid terminal_state is rejected."""
        valid_definition_data["terminal_states"] = ["finished"]

        definition = EncounterDefinition(**valid_definition_data)

        with pytest.raises(ValidationError) as exc_info:
            definition.full_clean()

        assert "terminal_state" in str(exc_info.value)

    def test_transition_from_terminal_rejected(self, valid_definition_data):
        """Definition with transition from terminal state is rejected."""
        valid_definition_data["transitions"]["completed"] = ["pending"]

        definition = EncounterDefinition(**valid_definition_data)

        with pytest.raises(ValidationError) as exc_info:
            definition.full_clean()

        assert "terminal state" in str(exc_info.value)

    def test_unreachable_state_rejected(self, valid_definition_data):
        """Definition with unreachable state is rejected."""
        valid_definition_data["states"].append("orphan")

        definition = EncounterDefinition(**valid_definition_data)

        with pytest.raises(ValidationError) as exc_info:
            definition.full_clean()

        assert "unreachable" in str(exc_info.value)


@pytest.mark.django_db
class TestEncounterDefinitionUniqueness:
    """Tests for EncounterDefinition unique constraints."""

    def test_duplicate_key_rejected(self, valid_definition_data):
        """Duplicate keys are rejected."""
        definition1 = EncounterDefinition(**valid_definition_data)
        definition1.full_clean()
        definition1.save()

        definition2 = EncounterDefinition(**valid_definition_data)
        definition2.key = "test_workflow"  # Same key

        with pytest.raises(IntegrityError):
            definition2.save()

    def test_different_keys_allowed(self, valid_definition_data):
        """Different keys are allowed."""
        definition1 = EncounterDefinition(**valid_definition_data)
        definition1.full_clean()
        definition1.save()

        valid_definition_data["key"] = "another_workflow"
        definition2 = EncounterDefinition(**valid_definition_data)
        definition2.full_clean()
        definition2.save()

        assert EncounterDefinition.objects.count() == 2


@pytest.mark.django_db
class TestEncounterDefinitionQuerying:
    """Tests for querying EncounterDefinition."""

    def test_inactive_definitions_queryable(self, valid_definition_data):
        """Inactive definitions can still be queried."""
        valid_definition_data["active"] = False
        definition = EncounterDefinition(**valid_definition_data)
        definition.full_clean()
        definition.save()

        # Can query by key
        found = EncounterDefinition.objects.get(key="test_workflow")
        assert found.active is False

    def test_filter_by_active(self, valid_definition_data):
        """Can filter by active status."""
        # Create active definition
        definition1 = EncounterDefinition(**valid_definition_data)
        definition1.full_clean()
        definition1.save()

        # Create inactive definition
        valid_definition_data["key"] = "inactive_workflow"
        valid_definition_data["active"] = False
        definition2 = EncounterDefinition(**valid_definition_data)
        definition2.full_clean()
        definition2.save()

        active_count = EncounterDefinition.objects.filter(active=True).count()
        inactive_count = EncounterDefinition.objects.filter(active=False).count()

        assert active_count == 1
        assert inactive_count == 1
