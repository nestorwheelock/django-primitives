"""Custom exceptions for django-encounters."""


class EncounterError(Exception):
    """Base exception for encounter errors."""
    pass


class InvalidTransition(EncounterError):
    """Raised when attempting an invalid state transition."""

    def __init__(self, from_state: str, to_state: str, reason: str = None):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason or f"Cannot transition from '{from_state}' to '{to_state}'"
        super().__init__(self.reason)


class TransitionBlocked(EncounterError):
    """Raised when validators block a transition."""

    def __init__(self, blocks: list[str]):
        self.blocks = blocks
        message = "Transition blocked: " + "; ".join(blocks)
        super().__init__(message)


class DefinitionNotFound(EncounterError):
    """Raised when encounter definition key not found."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Encounter definition '{key}' not found")


class ValidatorLoadError(EncounterError):
    """Raised when a validator cannot be loaded."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Cannot load validator '{path}': {reason}")
