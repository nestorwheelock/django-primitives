"""Tests for encounter transition services."""

import pytest
from django.contrib.contenttypes.models import ContentType

from django_encounters.exceptions import InvalidTransition, TransitionBlocked
from django_encounters.models import Encounter, EncounterDefinition, EncounterTransition
from django_encounters.services import (
    create_encounter,
    transition,
    get_allowed_transitions,
    validate_transition,
)
from tests.testapp.models import Subject


@pytest.fixture
def definition(db):
    """Create a test definition."""
    return EncounterDefinition.objects.create(
        key="test_workflow",
        name="Test Workflow",
        states=["pending", "active", "review", "completed", "cancelled"],
        transitions={
            "pending": ["active", "cancelled"],
            "active": ["review", "cancelled"],
            "review": ["completed", "active"],
        },
        initial_state="pending",
        terminal_states=["completed", "cancelled"],
    )


@pytest.fixture
def subject(db):
    """Create a test subject."""
    return Subject.objects.create(name="Test Subject")


@pytest.fixture
def user(db, django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user(username="testuser", password="test")


@pytest.mark.django_db
class TestCreateEncounter:
    """Tests for create_encounter service."""

    def test_create_encounter_starts_in_initial_state(self, definition, subject, user):
        """New encounter starts in initial_state from definition."""
        encounter = create_encounter(
            definition_key="test_workflow",
            subject=subject,
            created_by=user,
        )

        assert encounter.state == "pending"
        assert encounter.definition == definition
        assert encounter.subject == subject
        assert encounter.created_by == user

    def test_create_encounter_with_metadata(self, definition, subject):
        """Can create encounter with initial metadata."""
        encounter = create_encounter(
            definition_key="test_workflow",
            subject=subject,
            metadata={"source": "api"},
        )

        assert encounter.metadata == {"source": "api"}

    def test_create_encounter_without_user(self, definition, subject):
        """Can create encounter without created_by user."""
        encounter = create_encounter(
            definition_key="test_workflow",
            subject=subject,
        )

        assert encounter.created_by is None


@pytest.mark.django_db
class TestGetAllowedTransitions:
    """Tests for get_allowed_transitions service."""

    def test_returns_allowed_transitions(self, definition, subject):
        """Returns list of allowed next states."""
        encounter = create_encounter("test_workflow", subject)

        allowed = get_allowed_transitions(encounter)

        assert "active" in allowed
        assert "cancelled" in allowed
        assert "completed" not in allowed  # Not directly reachable from pending

    def test_terminal_state_returns_empty(self, definition, subject):
        """Terminal states have no allowed transitions."""
        encounter = create_encounter("test_workflow", subject)
        encounter.state = "completed"
        encounter.save()

        allowed = get_allowed_transitions(encounter)

        assert allowed == []


@pytest.mark.django_db
class TestTransition:
    """Tests for transition service."""

    def test_allowed_transition_succeeds(self, definition, subject, user):
        """Valid transition updates state and creates audit record."""
        encounter = create_encounter("test_workflow", subject)

        result = transition(encounter, "active", by_user=user)

        assert result.state == "active"
        assert EncounterTransition.objects.filter(encounter=encounter).count() == 1

    def test_transition_creates_audit_record(self, definition, subject, user):
        """Transition creates EncounterTransition with correct data."""
        encounter = create_encounter("test_workflow", subject)

        transition(encounter, "active", by_user=user)

        audit = EncounterTransition.objects.get(encounter=encounter)
        assert audit.from_state == "pending"
        assert audit.to_state == "active"
        assert audit.transitioned_by == user

    def test_transition_with_metadata(self, definition, subject):
        """Transition can include metadata in audit record."""
        encounter = create_encounter("test_workflow", subject)

        transition(encounter, "active", metadata={"reason": "test"})

        audit = EncounterTransition.objects.get(encounter=encounter)
        assert audit.metadata == {"reason": "test"}

    def test_disallowed_transition_raises(self, definition, subject):
        """Transition to non-allowed state raises InvalidTransition."""
        encounter = create_encounter("test_workflow", subject)

        with pytest.raises(InvalidTransition) as exc_info:
            transition(encounter, "completed")

        assert "pending" in str(exc_info.value)
        assert "completed" in str(exc_info.value)

    def test_terminal_state_cannot_transition(self, definition, subject):
        """Terminal state raises InvalidTransition."""
        encounter = create_encounter("test_workflow", subject)
        encounter.state = "completed"
        encounter.save()

        with pytest.raises(InvalidTransition):
            transition(encounter, "pending")

    def test_ended_at_set_on_terminal_state(self, definition, subject):
        """ended_at is set when reaching terminal state."""
        encounter = create_encounter("test_workflow", subject)

        # pending -> cancelled (terminal)
        result = transition(encounter, "cancelled")

        assert result.ended_at is not None

    def test_ended_at_not_set_on_non_terminal(self, definition, subject):
        """ended_at remains null for non-terminal transitions."""
        encounter = create_encounter("test_workflow", subject)

        result = transition(encounter, "active")

        assert result.ended_at is None

    def test_multiple_transitions_create_history(self, definition, subject, user):
        """Multiple transitions create ordered history."""
        encounter = create_encounter("test_workflow", subject)

        transition(encounter, "active", by_user=user)
        transition(encounter, "review", by_user=user)
        transition(encounter, "completed", by_user=user)

        transitions = list(encounter.transitions.order_by("transitioned_at"))
        assert len(transitions) == 3
        assert transitions[0].to_state == "active"
        assert transitions[1].to_state == "review"
        assert transitions[2].to_state == "completed"


@pytest.mark.django_db
class TestValidateTransition:
    """Tests for validate_transition service."""

    def test_valid_transition_returns_true(self, definition, subject):
        """Valid transition returns (True, [], [])."""
        encounter = create_encounter("test_workflow", subject)

        allowed, blocks, warnings = validate_transition(encounter, "active")

        assert allowed is True
        assert blocks == []
        assert warnings == []

    def test_invalid_transition_returns_blocks(self, definition, subject):
        """Invalid transition returns hard blocks."""
        encounter = create_encounter("test_workflow", subject)

        allowed, blocks, warnings = validate_transition(encounter, "completed")

        assert allowed is False
        assert len(blocks) > 0

    def test_terminal_state_returns_blocks(self, definition, subject):
        """Terminal state returns hard blocks."""
        encounter = create_encounter("test_workflow", subject)
        encounter.state = "completed"
        encounter.save()

        allowed, blocks, warnings = validate_transition(encounter, "pending")

        assert allowed is False
        assert "terminal" in str(blocks).lower() or "cannot" in str(blocks).lower()


@pytest.mark.django_db
class TestTransitionWithValidators:
    """Tests for transition with pluggable validators."""

    def test_transition_without_validators(self, definition, subject):
        """Transition works when no validators configured."""
        encounter = create_encounter("test_workflow", subject)

        # Should not raise
        result = transition(encounter, "active")
        assert result.state == "active"
