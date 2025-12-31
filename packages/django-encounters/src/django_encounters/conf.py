"""Configuration helpers for django-encounters."""

from functools import lru_cache
from importlib import import_module

from django.conf import settings

from .exceptions import ValidatorLoadError


# Optional: Global validators applied to all definitions
GLOBAL_VALIDATORS = getattr(settings, 'ENCOUNTERS_GLOBAL_VALIDATORS', [])


def get_setting(name: str, default=None):
    """Get a setting with ENCOUNTERS_ prefix."""
    return getattr(settings, f"ENCOUNTERS_{name}", default)


@lru_cache(maxsize=128)
def load_validator(dotted_path: str):
    """
    Import and instantiate a validator from dotted path.

    Raises ValidatorLoadError for bad imports or non-subclass validators.
    """
    from .validators import BaseEncounterValidator

    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError:
        raise ValidatorLoadError(dotted_path, "Invalid dotted path format")

    try:
        module = import_module(module_path)
    except ImportError as e:
        raise ValidatorLoadError(dotted_path, f"Cannot import module: {e}")

    try:
        validator_class = getattr(module, class_name)
    except AttributeError:
        raise ValidatorLoadError(dotted_path, f"Class '{class_name}' not found in module")

    if not isinstance(validator_class, type) or not issubclass(validator_class, BaseEncounterValidator):
        raise ValidatorLoadError(
            dotted_path,
            f"'{class_name}' must be a subclass of BaseEncounterValidator"
        )

    return validator_class()


def get_validators_for_definition(definition) -> list:
    """
    Load validator instances from definition.validator_paths + GLOBAL_VALIDATORS.

    Caches loaded validators per definition to avoid repeated imports.
    """
    validators = []

    # Load global validators first
    for path in GLOBAL_VALIDATORS:
        validators.append(load_validator(path))

    # Load definition-specific validators
    for path in (definition.validator_paths or []):
        validators.append(load_validator(path))

    return validators


def clear_validator_cache():
    """Clear the validator loading cache. Useful for testing."""
    load_validator.cache_clear()
