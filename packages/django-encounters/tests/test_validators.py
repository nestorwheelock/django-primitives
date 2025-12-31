"""Tests for validator loading and execution."""

import pytest
from django.contrib.contenttypes.models import ContentType

from django_encounters.conf import clear_validator_cache
from django_encounters.exceptions import TransitionBlocked, ValidatorLoadError
from django_encounters.models import Encounter, EncounterDefinition
from django_encounters.services import create_encounter, transition, validate_transition
from tests.testapp.models import Subject


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear validator cache before and after each test."""
    clear_validator_cache()
    yield
    clear_validator_cache()


@pytest.fixture
def subject(db):
    """Create a test subject."""
    return Subject.objects.create(name="Test Subject")


@pytest.fixture
def user(db, django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user(username="testuser", password="test")


def create_definition_with_validators(validators):
    """Helper to create definition with specific validators."""
    return EncounterDefinition.objects.create(
        key=f"test_{len(validators)}",
        name="Test Workflow",
        states=["pending", "active", "completed"],
        transitions={"pending": ["active"], "active": ["completed"]},
        initial_state="pending",
        terminal_states=["completed"],
        validator_paths=validators,
    )


@pytest.mark.django_db
class TestValidatorHardBlocks:
    """Tests for validators that return hard blocks."""

    def test_validator_hard_block_prevents_transition(self, subject):
        """Hard block from validator prevents transition."""
        definition = create_definition_with_validators(
            ["tests.testapp.validators.BlockingValidator"]
        )
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        with pytest.raises(TransitionBlocked) as exc_info:
            transition(encounter, "active")

        assert "Blocked by test validator" in str(exc_info.value)

    def test_override_warnings_does_not_bypass_hard_blocks(self, subject):
        """override_warnings=True does NOT bypass hard blocks."""
        definition = create_definition_with_validators(
            ["tests.testapp.validators.BlockingValidator"]
        )
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        with pytest.raises(TransitionBlocked):
            transition(encounter, "active", override_warnings=True)


@pytest.mark.django_db
class TestValidatorSoftWarnings:
    """Tests for validators that return soft warnings."""

    def test_validator_soft_warning_blocks_by_default(self, subject):
        """Soft warnings block transition by default."""
        definition = create_definition_with_validators(
            ["tests.testapp.validators.WarningValidator"]
        )
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        with pytest.raises(TransitionBlocked) as exc_info:
            transition(encounter, "active")

        assert "Warning from test validator" in str(exc_info.value)

    def test_override_warnings_bypasses_soft_warnings(self, subject):
        """override_warnings=True bypasses soft warnings."""
        definition = create_definition_with_validators(
            ["tests.testapp.validators.WarningValidator"]
        )
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        # Should not raise
        result = transition(encounter, "active", override_warnings=True)
        assert result.state == "active"


@pytest.mark.django_db
class TestMultipleValidators:
    """Tests for multiple validators."""

    def test_multiple_validators_run_in_order(self, subject):
        """Multiple validators all run."""
        definition = create_definition_with_validators([
            "tests.testapp.validators.PassingValidator",
            "tests.testapp.validators.BlockingValidator",
        ])
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        # Should be blocked by second validator
        with pytest.raises(TransitionBlocked):
            transition(encounter, "active")

    def test_all_passing_validators_allow_transition(self, subject):
        """All passing validators allow transition."""
        definition = create_definition_with_validators([
            "tests.testapp.validators.PassingValidator",
            "tests.testapp.validators.PassingValidator",
        ])
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        result = transition(encounter, "active")
        assert result.state == "active"


@pytest.mark.django_db
class TestValidateTransitionWithValidators:
    """Tests for validate_transition with validators."""

    def test_validate_returns_blocks_from_validators(self, subject):
        """validate_transition returns hard blocks from validators."""
        definition = create_definition_with_validators(
            ["tests.testapp.validators.BlockingValidator"]
        )
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        allowed, blocks, warnings = validate_transition(encounter, "active")

        assert allowed is False
        assert "Blocked by test validator" in blocks

    def test_validate_returns_warnings_from_validators(self, subject):
        """validate_transition returns soft warnings from validators."""
        definition = create_definition_with_validators(
            ["tests.testapp.validators.WarningValidator"]
        )
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        allowed, blocks, warnings = validate_transition(encounter, "active")

        assert allowed is True  # Warnings don't block
        assert "Warning from test validator" in warnings


@pytest.mark.django_db
class TestConditionalValidator:
    """Tests for validators that check encounter state."""

    def test_conditional_validator_checks_metadata(self, subject):
        """Validator can check encounter metadata."""
        definition = create_definition_with_validators(
            ["tests.testapp.validators.ConditionalBlockingValidator"]
        )
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
            metadata={"block_transition": True},
        )

        with pytest.raises(TransitionBlocked) as exc_info:
            transition(encounter, "active")

        assert "metadata flag" in str(exc_info.value)

    def test_conditional_validator_passes_without_flag(self, subject):
        """Validator passes when metadata flag not set."""
        definition = create_definition_with_validators(
            ["tests.testapp.validators.ConditionalBlockingValidator"]
        )
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
            metadata={},
        )

        result = transition(encounter, "active")
        assert result.state == "active"
