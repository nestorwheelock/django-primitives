# Architecture: django-modules

**Status:** Stable / v0.1.0

Feature flag system with per-organization overrides.

---

## What This Package Is For

Answering the question: **"Is this feature enabled for this organization?"**

Use cases:
- Feature toggles (enable/disable features globally)
- Per-organization feature overrides
- Multi-tenant feature gating
- Gradual rollouts (enable for specific orgs first)
- Module licensing (org pays for specific modules)

---

## What This Package Is NOT For

- **Not percentage-based rollouts** - Use LaunchDarkly for A/B testing
- **Not user-level flags** - This is org-level only
- **Not runtime config** - Use environment variables for settings
- **Not permission system** - Use django-rbac for access control

---

## Design Principles

1. **Global default, org override** - Modules have default state, orgs can override
2. **Explicit over implicit** - No OrgModuleState = use global default
3. **Key-based lookup** - Modules identified by unique string keys
4. **Soft delete aware** - Uses BaseModel for soft delete support
5. **Configurable org model** - Works with any organization model

---

## Data Model

```
Module                                 OrgModuleState
├── id (UUID, BaseModel)               ├── id (UUID, BaseModel)
├── key (unique)                       ├── org (FK → configurable model)
├── name                               ├── module (FK → Module)
├── description                        ├── enabled (bool)
├── active (global default)            └── BaseModel fields
└── BaseModel fields

State Resolution:
  1. Check OrgModuleState for (org, module)
  2. If exists → use OrgModuleState.enabled
  3. If not exists → use Module.active

Example:
  Module(key='pharmacy', active=True)   # Global: enabled
  OrgModuleState(org=A, enabled=False)  # Org A: disabled
  # Org B has no OrgModuleState         # Org B: enabled (global default)
```

---

## Public API

### Defining Modules

```python
from django_modules.models import Module

# Create a module
module = Module.objects.create(
    key='pharmacy',
    name='Pharmacy Module',
    description='Enables pharmacy dispensing features',
    active=True,  # Enabled by default
)

# Or with fixtures/migrations
Module.objects.get_or_create(
    key='billing',
    defaults={
        'name': 'Billing Module',
        'description': 'Enables invoicing and payments',
        'active=False,  # Disabled by default
    }
)
```

### Checking Module State

```python
from django_modules.services import is_module_enabled

# Check if module is enabled for an org
if is_module_enabled('pharmacy', org):
    # Show pharmacy features
    pass

# Check global default (no org)
if is_module_enabled('pharmacy'):
    # Module is globally active
    pass
```

### Per-Org Overrides

```python
from django_modules.models import OrgModuleState, Module

# Enable a module for specific org
module = Module.objects.get(key='pharmacy')
OrgModuleState.objects.update_or_create(
    org=my_org,
    module=module,
    defaults={'enabled': True},
)

# Disable a module for specific org
OrgModuleState.objects.update_or_create(
    org=my_org,
    module=module,
    defaults={'enabled': False},
)

# Remove override (revert to global default)
OrgModuleState.objects.filter(
    org=my_org,
    module=module,
).delete()
```

---

## Configuration

```python
# settings.py

# Specify your organization model
DJANGO_MODULES_ORG_MODEL = 'django_parties.Organization'

# Or with full path
DJANGO_MODULES_ORG_MODEL = 'myapp.Company'
```

---

## Hard Rules

1. **Module.key is unique** - No duplicate module keys allowed
2. **One override per org+module** - UniqueConstraint on (org, module)
3. **Org model configurable** - Set via DJANGO_MODULES_ORG_MODEL setting

---

## Invariants

- Module.key is globally unique
- OrgModuleState(org, module) is unique per combination
- If no OrgModuleState exists: result = Module.active
- If OrgModuleState exists: result = OrgModuleState.enabled

---

## Known Gotchas

### 1. Missing Org Model Configuration

**Problem:** DJANGO_MODULES_ORG_MODEL not set.

```python
# Error on startup:
# ImproperlyConfigured: DJANGO_MODULES_ORG_MODEL setting is required

# Fix: Add to settings.py
DJANGO_MODULES_ORG_MODEL = 'myapp.Organization'
```

### 2. Override vs Default Confusion

**Problem:** Not understanding state resolution.

```python
# Module: pharmacy, active=True

# No OrgModuleState for org_a
is_module_enabled('pharmacy', org_a)  # True (uses global)

# OrgModuleState for org_b with enabled=False
is_module_enabled('pharmacy', org_b)  # False (uses override)

# OrgModuleState for org_c with enabled=True
is_module_enabled('pharmacy', org_c)  # True (uses override, same as global)
```

### 3. Deleting Module with OrgModuleStates

**Problem:** Cascade delete on module removal.

```python
module.delete()
# All OrgModuleStates for this module are also deleted
# (CASCADE on module FK)
```

---

## Recommended Usage

### 1. Define Modules in Migrations

```python
# migrations/0002_add_modules.py
from django.db import migrations

def create_modules(apps, schema_editor):
    Module = apps.get_model('django_modules', 'Module')
    modules = [
        ('pharmacy', 'Pharmacy', 'Pharmacy dispensing features', True),
        ('billing', 'Billing', 'Invoicing and payments', False),
        ('inventory', 'Inventory', 'Stock management', True),
    ]
    for key, name, desc, active in modules:
        Module.objects.get_or_create(
            key=key,
            defaults={'name': name, 'description': desc, 'active': active}
        )

class Migration(migrations.Migration):
    dependencies = [('django_modules', '0001_initial')]
    operations = [migrations.RunPython(create_modules)]
```

### 2. Use in Views/Templates

```python
# views.py
from django_modules.services import is_module_enabled

def dashboard(request):
    context = {
        'show_pharmacy': is_module_enabled('pharmacy', request.org),
        'show_billing': is_module_enabled('billing', request.org),
    }
    return render(request, 'dashboard.html', context)

# template
{% if show_pharmacy %}
  <a href="{% url 'pharmacy:list' %}">Pharmacy</a>
{% endif %}
```

### 3. Middleware for Module Context

```python
class ModuleMiddleware:
    """Add module checks to request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_module_enabled = lambda key: is_module_enabled(
            key, getattr(request, 'org', None)
        )
        return self.get_response(request)
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- Module model with global active flag
- OrgModuleState for per-org overrides
- is_module_enabled() service function
- Configurable organization model
