"""Services for django-modules."""

from django_modules.exceptions import ModuleDisabled, ModuleNotFound
from django_modules.models import Module, OrgModuleState


def is_module_enabled(org, module_key: str) -> bool:
    """Check if a module is enabled for an organization.

    Resolution order:
    1. If OrgModuleState exists for (org, module), use its `enabled` value
    2. Otherwise, fall back to Module.active (global default)

    Args:
        org: The organization to check
        module_key: The module key to check

    Returns:
        bool: True if module is enabled, False otherwise

    Raises:
        ModuleNotFound: If the module key does not exist
    """
    try:
        module = Module.objects.get(key=module_key)
    except Module.DoesNotExist:
        raise ModuleNotFound(module_key)

    try:
        state = OrgModuleState.objects.get(org=org, module=module)
        return state.enabled
    except OrgModuleState.DoesNotExist:
        return module.active


def require_module(org, module_key: str) -> None:
    """Require a module to be enabled, raising if disabled.

    Use this in views/services to enforce module requirements.

    Args:
        org: The organization to check
        module_key: The module key to require

    Raises:
        ModuleDisabled: If the module is disabled for this org
        ModuleNotFound: If the module key does not exist
    """
    if not is_module_enabled(org, module_key):
        raise ModuleDisabled(module_key, org)


def list_enabled_modules(org) -> set[str]:
    """List all enabled module keys for an organization.

    Returns modules that are:
    1. Explicitly enabled via OrgModuleState, OR
    2. Globally active (Module.active=True) with no org override

    Args:
        org: The organization to check

    Returns:
        set[str]: Set of enabled module keys
    """
    enabled = set()

    all_modules = Module.objects.all()
    org_states = {
        state.module_id: state.enabled
        for state in OrgModuleState.objects.filter(org=org).select_related("module")
    }

    for module in all_modules:
        if module.id in org_states:
            if org_states[module.id]:
                enabled.add(module.key)
        elif module.active:
            enabled.add(module.key)

    return enabled
