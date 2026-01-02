"""Django Base Models - Reusable abstract models for Django projects."""

__version__ = "0.2.0"

__all__ = [
    "TimeStampedModel",
    "UUIDModel",
    "SoftDeleteManager",
    "SoftDeleteModel",
    "BaseModel",
]


def __getattr__(name):
    """Lazy import models to avoid AppRegistryNotReady errors."""
    if name in __all__:
        from django_basemodels import models
        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
