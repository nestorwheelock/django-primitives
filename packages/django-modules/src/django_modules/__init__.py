"""Django Modules - Module enable/disable per organization."""

__version__ = "0.1.0"

default_app_config = "django_modules.apps.DjangoModulesConfig"


def is_module_enabled(org, module_key: str) -> bool:
    """Check if a module is enabled for an organization."""
    from django_modules.services import is_module_enabled as _is_module_enabled

    return _is_module_enabled(org, module_key)


def require_module(org, module_key: str) -> None:
    """Require a module to be enabled, raising if disabled."""
    from django_modules.services import require_module as _require_module

    return _require_module(org, module_key)


def list_enabled_modules(org) -> set[str]:
    """List all enabled module keys for an organization."""
    from django_modules.services import list_enabled_modules as _list_enabled_modules

    return _list_enabled_modules(org)


__all__ = [
    "is_module_enabled",
    "list_enabled_modules",
    "require_module",
]
