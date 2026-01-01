# Prompt: Rebuild django-modules

## Instruction

Create a Django package called `django-modules` that provides feature flags on a per-organization basis.

## Package Purpose

Enable/disable features (modules) per organization:
- Module model for global module definitions
- OrgModuleState model for per-org overrides
- Hierarchical resolution: org override > global default
- Services for checking and requiring modules

## Dependencies

- Django >= 4.2
- django-basemodels (for soft delete)
- django.contrib.contenttypes

## File Structure

```
packages/django-modules/
├── pyproject.toml
├── README.md
├── src/django_modules/
│   ├── __init__.py
│   ├── apps.py
│   ├── conf.py
│   ├── models.py
│   ├── services.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── testapp/
    │   ├── __init__.py
    │   └── models.py
    ├── test_models.py
    ├── test_services.py
    └── test_config.py
```

## Configuration

### conf.py

```python
from django.conf import settings

class ModulesConfigError(Exception):
    pass

def get_org_model() -> str:
    """Get the configured organization model string."""
    org_model = getattr(settings, 'MODULES_ORG_MODEL', None)
    if not org_model:
        raise ModulesConfigError(
            "MODULES_ORG_MODEL setting is required. "
            "Set it to your organization model path, e.g. 'myapp.Organization'"
        )
    return org_model

def get_org_model_string() -> str:
    """Get org model as string for ForeignKey declarations."""
    return get_org_model()
```

## Exceptions Specification

### exceptions.py

```python
class ModuleError(Exception):
    """Base exception for module errors."""
    pass

class ModuleDisabled(ModuleError):
    """Raised when attempting to use a disabled module."""
    def __init__(self, module_key: str, org=None):
        self.module_key = module_key
        self.org = org
        if org:
            super().__init__(f"Module '{module_key}' is disabled for organization '{org}'")
        else:
            super().__init__(f"Module '{module_key}' is disabled")

class ModuleNotFound(ModuleError):
    """Raised when module key does not exist."""
    def __init__(self, module_key: str):
        self.module_key = module_key
        super().__init__(f"Module '{module_key}' does not exist")

class ModulesConfigError(ModuleError):
    """Raised when modules configuration is invalid."""
    pass
```

## Models Specification

### Module Model

```python
from django.db import models
from django_basemodels.models import BaseModel

class Module(BaseModel):
    """System-wide module definitions with global activation status."""
    key = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    active = models.BooleanField(default=True)  # Global default

    class Meta:
        app_label = 'django_modules'
        verbose_name = 'module'
        verbose_name_plural = 'modules'
        ordering = ['key']

    def __str__(self):
        status = 'active' if self.active else 'inactive'
        return f"{self.name} ({self.key}) - {status}"
```

### OrgModuleState Model

```python
from .conf import get_org_model_string

class OrgModuleState(BaseModel):
    """Per-organization override of global module settings."""
    org = models.ForeignKey(
        get_org_model_string(),
        on_delete=models.CASCADE,
        related_name='module_states'
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='org_states'
    )
    enabled = models.BooleanField()  # Override value

    class Meta:
        app_label = 'django_modules'
        verbose_name = 'organization module state'
        verbose_name_plural = 'organization module states'
        constraints = [
            models.UniqueConstraint(
                fields=['org', 'module'],
                name='unique_org_module_state'
            )
        ]

    def __str__(self):
        status = 'enabled' if self.enabled else 'disabled'
        return f"{self.module.key} → {status} for org {self.org_id}"
```

## Service Functions

### services.py

```python
from typing import Set
from .models import Module, OrgModuleState
from .exceptions import ModuleDisabled, ModuleNotFound

def is_module_enabled(org, module_key: str) -> bool:
    """
    Check if a module is enabled for an organization.

    Resolution order:
    1. OrgModuleState for (org, module) → use its enabled value
    2. No override → use Module.active (global default)

    Args:
        org: Organization instance
        module_key: Module identifier

    Returns:
        True if enabled, False if disabled

    Raises:
        ModuleNotFound: If module_key doesn't exist
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
    """
    Require a module to be enabled, raising if disabled.

    Args:
        org: Organization instance
        module_key: Module identifier

    Raises:
        ModuleDisabled: If module is disabled
        ModuleNotFound: If module doesn't exist
    """
    if not is_module_enabled(org, module_key):
        raise ModuleDisabled(module_key, org)


def list_enabled_modules(org) -> Set[str]:
    """
    List all enabled module keys for an organization.

    Args:
        org: Organization instance

    Returns:
        Set of enabled module keys
    """
    enabled = set()

    # Get all modules and org overrides
    modules = Module.objects.all()
    org_states = {
        state.module_id: state.enabled
        for state in OrgModuleState.objects.filter(org=org)
    }

    for module in modules:
        if module.id in org_states:
            if org_states[module.id]:
                enabled.add(module.key)
        elif module.active:
            enabled.add(module.key)

    return enabled
```

## Test Models

### tests/testapp/models.py

```python
from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'testapp'
```

### tests/settings.py

```python
MODULES_ORG_MODEL = 'testapp.Organization'

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django_basemodels',
    'django_modules',
    'tests.testapp',
]
```

## Test Cases (57 tests)

### Module Model Tests (9 tests)
1. `test_module_creation` - Create with required fields
2. `test_module_has_pk` - PK assigned
3. `test_module_has_timestamps` - created_at, updated_at
4. `test_module_unique_key` - IntegrityError on duplicate
5. `test_module_active_defaults_to_true` - Default active
6. `test_module_description_optional` - Can omit
7. `test_module_str_active` - String representation active
8. `test_module_str_inactive` - String representation inactive
9. `test_module_ordering_by_key` - Alphabetical order

### Module Soft Delete Tests (4 tests)
1. `test_soft_delete_sets_deleted_at` - Sets timestamp
2. `test_soft_deleted_excluded_from_queryset` - Excluded
3. `test_soft_deleted_in_all_objects` - Accessible
4. `test_soft_deleted_can_be_restored` - Restores

### OrgModuleState Tests (10 tests)
1. `test_org_module_state_creation` - Create state
2. `test_org_module_state_has_pk` - PK assigned
3. `test_org_module_state_unique_constraint` - IntegrityError
4. `test_multiple_orgs_same_module` - Allowed
5. `test_same_org_different_modules` - Allowed
6. `test_org_module_state_str_enabled` - String enabled
7. `test_org_module_state_str_disabled` - String disabled
8. `test_cascade_delete_module` - Cascades from module
9. `test_cascade_delete_org` - Cascades from org
10. `test_org_module_state_soft_delete` - Soft delete works

### is_module_enabled Tests (8 tests)
1. `test_returns_true_for_active_no_override` - Active module
2. `test_returns_false_for_inactive_no_override` - Inactive module
3. `test_override_enables_inactive_module` - Override=True wins
4. `test_override_disables_active_module` - Override=False wins
5. `test_override_only_affects_specific_org` - Org isolation
6. `test_raises_module_not_found` - Missing module
7. `test_soft_deleted_module_not_found` - Soft deleted
8. `test_soft_deleted_override_falls_back` - Falls back

### require_module Tests (6 tests)
1. `test_does_not_raise_for_enabled` - Silent pass
2. `test_raises_module_disabled` - ModuleDisabled
3. `test_raises_with_message` - Message includes key
4. `test_raises_for_override_disabled` - Override disabled
5. `test_does_not_raise_for_override_enabled` - Override enabled
6. `test_raises_module_not_found` - Missing module

### list_enabled_modules Tests (9 tests)
1. `test_returns_empty_set_when_no_modules` - Empty
2. `test_returns_active_modules` - Active included
3. `test_excludes_inactive_modules` - Inactive excluded
4. `test_includes_override_enabled` - Override enabled
5. `test_excludes_override_disabled` - Override disabled
6. `test_different_orgs_different_results` - Org isolation
7. `test_returns_deterministic_set` - Consistent
8. `test_excludes_soft_deleted_modules` - Soft deleted
9. `test_ignores_soft_deleted_overrides` - Falls back

### Module Resolution Tests (3 tests)
1. `test_override_true_beats_module_false` - Override wins
2. `test_override_false_beats_module_true` - Override wins
3. `test_no_override_uses_module_active` - Falls back

### Edge Case Tests (3 tests)
1. `test_many_modules_many_orgs` - Scale test
2. `test_module_keys_special_chars` - Underscores/hyphens
3. `test_empty_module_key_not_found` - Empty key error

### Config Tests (4 tests)
1. `test_get_org_model_returns_string` - Returns model string
2. `test_get_org_model_string_returns_string` - Same
3. `test_missing_setting_raises` - ModulesConfigError
4. `test_unset_setting_raises` - ModulesConfigError

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    'Module',
    'OrgModuleState',
    'is_module_enabled',
    'require_module',
    'list_enabled_modules',
    'ModuleError',
    'ModuleDisabled',
    'ModuleNotFound',
    'ModulesConfigError',
]

def __getattr__(name):
    if name in ('Module', 'OrgModuleState'):
        from .models import Module, OrgModuleState
        return locals()[name]
    if name in ('is_module_enabled', 'require_module', 'list_enabled_modules'):
        from .services import is_module_enabled, require_module, list_enabled_modules
        return locals()[name]
    if name in ('ModuleError', 'ModuleDisabled', 'ModuleNotFound', 'ModulesConfigError'):
        from .exceptions import ModuleError, ModuleDisabled, ModuleNotFound, ModulesConfigError
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Hierarchical Resolution**: Org override > global default
2. **Soft Delete Support**: Via BaseModel inheritance
3. **Cascade Delete**: Org/module delete cascades to states
4. **Unique Constraint**: One override per org+module pair
5. **Swappable Org Model**: Via MODULES_ORG_MODEL setting

## Usage Examples

```python
from django_modules import (
    Module, OrgModuleState,
    is_module_enabled, require_module, list_enabled_modules
)

# Create modules
billing = Module.objects.create(key='billing', name='Billing', active=False)
pharmacy = Module.objects.create(key='pharmacy', name='Pharmacy', active=True)

# Enable billing for specific org
OrgModuleState.objects.create(org=my_org, module=billing, enabled=True)

# Check if enabled
if is_module_enabled(my_org, 'billing'):
    show_billing_features()

# Require module (raises if disabled)
require_module(my_org, 'pharmacy')

# List all enabled modules
enabled = list_enabled_modules(my_org)
# {'billing', 'pharmacy'}
```

## Acceptance Criteria

- [ ] Module model with soft delete
- [ ] OrgModuleState model with unique constraint
- [ ] MODULES_ORG_MODEL setting for swappable org
- [ ] is_module_enabled with hierarchical resolution
- [ ] require_module raising ModuleDisabled
- [ ] list_enabled_modules returning set
- [ ] All 57 tests passing
- [ ] README with usage examples
