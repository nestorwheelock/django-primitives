"""Tests for configuration and validator loading."""

import pytest

from django_encounters.conf import (
    load_validator,
    get_validators_for_definition,
    clear_validator_cache,
    GLOBAL_VALIDATORS,
)
from django_encounters.exceptions import ValidatorLoadError
from django_encounters.models import EncounterDefinition
from django_encounters.validators import BaseEncounterValidator


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear validator cache before and after each test."""
    clear_validator_cache()
    yield
    clear_validator_cache()


class TestLoadValidator:
    """Tests for load_validator function."""

    def test_load_valid_validator(self):
        """Can load a valid validator class."""
        validator = load_validator("tests.testapp.validators.PassingValidator")

        assert isinstance(validator, BaseEncounterValidator)

    def test_bad_dotted_path_format(self):
        """Invalid dotted path format raises error."""
        with pytest.raises(ValidatorLoadError) as exc_info:
            load_validator("invalid")

        assert "Invalid dotted path format" in str(exc_info.value)

    def test_module_not_found(self):
        """Non-existent module raises error."""
        with pytest.raises(ValidatorLoadError) as exc_info:
            load_validator("nonexistent.module.Validator")

        assert "Cannot import module" in str(exc_info.value)

    def test_class_not_found(self):
        """Non-existent class in valid module raises error."""
        with pytest.raises(ValidatorLoadError) as exc_info:
            load_validator("tests.testapp.validators.NonexistentValidator")

        assert "not found in module" in str(exc_info.value)

    def test_not_a_validator_subclass(self):
        """Class not subclassing BaseEncounterValidator raises error."""
        with pytest.raises(ValidatorLoadError) as exc_info:
            load_validator("tests.testapp.validators.NotAValidator")

        assert "must be a subclass of BaseEncounterValidator" in str(exc_info.value)


class TestValidatorCaching:
    """Tests for validator caching."""

    def test_same_validator_returned_on_multiple_loads(self):
        """Same instance returned when loading same validator twice."""
        validator1 = load_validator("tests.testapp.validators.PassingValidator")
        validator2 = load_validator("tests.testapp.validators.PassingValidator")

        assert validator1 is validator2

    def test_different_validators_are_different_instances(self):
        """Different validators are different instances."""
        validator1 = load_validator("tests.testapp.validators.PassingValidator")
        validator2 = load_validator("tests.testapp.validators.BlockingValidator")

        assert validator1 is not validator2

    def test_clear_cache_creates_new_instances(self):
        """Clearing cache causes new instances to be created."""
        validator1 = load_validator("tests.testapp.validators.PassingValidator")
        clear_validator_cache()
        validator2 = load_validator("tests.testapp.validators.PassingValidator")

        assert validator1 is not validator2


@pytest.mark.django_db
class TestGetValidatorsForDefinition:
    """Tests for get_validators_for_definition."""

    def test_returns_validators_from_definition(self):
        """Returns validators specified in definition."""
        definition = EncounterDefinition.objects.create(
            key="test_validators",
            name="Test",
            states=["a", "b"],
            transitions={"a": ["b"]},
            initial_state="a",
            terminal_states=["b"],
            validator_paths=["tests.testapp.validators.PassingValidator"],
        )

        validators = get_validators_for_definition(definition)

        assert len(validators) == 1
        assert isinstance(validators[0], BaseEncounterValidator)

    def test_returns_empty_list_when_no_validators(self):
        """Returns empty list when no validators configured."""
        definition = EncounterDefinition.objects.create(
            key="test_no_validators",
            name="Test",
            states=["a", "b"],
            transitions={"a": ["b"]},
            initial_state="a",
            terminal_states=["b"],
            validator_paths=[],
        )

        validators = get_validators_for_definition(definition)

        assert validators == []

    def test_returns_multiple_validators(self):
        """Returns all validators from definition."""
        definition = EncounterDefinition.objects.create(
            key="test_multi_validators",
            name="Test",
            states=["a", "b"],
            transitions={"a": ["b"]},
            initial_state="a",
            terminal_states=["b"],
            validator_paths=[
                "tests.testapp.validators.PassingValidator",
                "tests.testapp.validators.WarningValidator",
            ],
        )

        validators = get_validators_for_definition(definition)

        assert len(validators) == 2


class TestGlobalValidators:
    """Tests for global validators setting."""

    def test_global_validators_default_empty(self):
        """Default GLOBAL_VALIDATORS is empty in test settings."""
        assert GLOBAL_VALIDATORS == []
