"""Django Decisioning - Decision surface contract and time semantics for Django."""

__version__ = "0.1.0"

__all__ = [
    # Mixins
    "TimeSemanticsMixin",
    "EffectiveDatedMixin",
    # QuerySets
    "EventAsOfQuerySet",
    "EffectiveDatedQuerySet",
    # Models
    "IdempotencyKey",
    "Decision",
    # Decorators
    "idempotent",
    # Utils
    "TargetRef",
    # Exceptions
    "DecisioningError",
    "IdempotencyError",
    "StaleRequestError",
]


def __getattr__(name):
    """Lazy import to avoid AppRegistryNotReady errors."""
    if name in ("TimeSemanticsMixin", "EffectiveDatedMixin"):
        from django_decisioning import mixins
        return getattr(mixins, name)
    if name in ("EventAsOfQuerySet", "EffectiveDatedQuerySet"):
        from django_decisioning import querysets
        return getattr(querysets, name)
    if name in ("IdempotencyKey", "Decision"):
        from django_decisioning import models
        return getattr(models, name)
    if name == "idempotent":
        from django_decisioning import decorators
        return getattr(decorators, name)
    if name == "TargetRef":
        from django_decisioning import utils
        return getattr(utils, name)
    if name in ("DecisioningError", "IdempotencyError", "StaleRequestError"):
        from django_decisioning import exceptions
        return getattr(exceptions, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
