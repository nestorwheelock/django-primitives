"""Test validators for django-encounters tests."""

from django_encounters.validators import BaseEncounterValidator


class BlockingValidator(BaseEncounterValidator):
    """Validator that always blocks."""

    def validate(self, encounter, from_state, to_state):
        return ["Blocked by test validator"], []


class WarningValidator(BaseEncounterValidator):
    """Validator that always warns."""

    def validate(self, encounter, from_state, to_state):
        return [], ["Warning from test validator"]


class PassingValidator(BaseEncounterValidator):
    """Validator that always passes."""

    def validate(self, encounter, from_state, to_state):
        return [], []


class ConditionalBlockingValidator(BaseEncounterValidator):
    """Validator that blocks based on metadata."""

    def validate(self, encounter, from_state, to_state):
        if encounter.metadata.get("block_transition"):
            return ["Blocked due to metadata flag"], []
        return [], []


class NotAValidator:
    """Not a validator - for testing error handling."""
    pass
