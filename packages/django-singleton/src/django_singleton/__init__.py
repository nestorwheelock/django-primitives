"""django-singleton: Singleton settings model pattern."""

__version__ = "0.1.0"

__all__ = [
    "SingletonModel",
    "EnvFallbackMixin",
    "SingletonDeletionError",
    "SingletonViolationError",
]


def __getattr__(name):
    """Lazy imports to prevent AppRegistryNotReady errors."""
    if name == "SingletonModel":
        from .models import SingletonModel

        return SingletonModel
    if name == "EnvFallbackMixin":
        from .mixins import EnvFallbackMixin

        return EnvFallbackMixin
    if name == "SingletonDeletionError":
        from .exceptions import SingletonDeletionError

        return SingletonDeletionError
    if name == "SingletonViolationError":
        from .exceptions import SingletonViolationError

        return SingletonViolationError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
