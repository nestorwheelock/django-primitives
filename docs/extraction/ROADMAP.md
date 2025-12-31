# Package Extraction Roadmap

**Status:** Planning
**Last Updated:** 2025-12-31

---

## Overview

This roadmap defines the order for extracting reusable Django packages from VetFriendly patterns. Tiers are ordered by dependency: Tier 1 must be stable before Tier 2 begins.

---

## Tier 1: Foundation (Extract First)

These packages have no dependencies on other primitives and form the foundation.

### 1.1 django-basemodels

**Purpose:** BaseModel with UUID PKs, timestamps, soft delete

**Extracts from:**
- SYSTEM_CHARTER.md: "All domain models inherit from BaseModel"
- SYSTEM_CHARTER.md: "Soft Delete & Reversibility"

**Provides:**
```python
from django_basemodels.models import BaseModel

class Pet(BaseModel):
    name = models.CharField(max_length=100)
    # Inherits: id (UUID), created_at, updated_at, deleted_at
    # Inherits: delete(), restore(), hard_delete()
    # Default manager excludes soft-deleted
```

**Why first:** Every other package depends on BaseModel.

**Status:** ✅ Complete (packages/django-basemodels, 30 tests)

---

### 1.2 django-parties

**Purpose:** Party pattern (Person, Organization, Group, Relationships)

**Extracts from:**
- SYSTEM_CHARTER.md: "Party Pattern is foundational"
- SYSTEM_CHARTER.md: "User vs Person"
- S-100: Unified People Architecture

**Provides:**
```python
from django_parties.models import Person, Organization, Group, PartyRelationship

# Relationships handle ownership, employment, guardianship, billing
rel = PartyRelationship.objects.create(
    from_person=person,
    to_organization=organization,
    relationship_type='employee'
)
```

**Depends on:** django-basemodels

**Status:** ✅ Complete (packages/django-parties, 44 tests)

---

### 1.3 django-rbac

**Purpose:** Role-based access control with hierarchy enforcement

**Extracts from:**
- SYSTEM_CHARTER.md: "RBAC Hierarchy"
- S-079: Audit Logging Staff Actions

**Provides:**
```python
from django_rbac.models import Role, UserRole
from django_rbac.mixins import RBACUserMixin
from django_rbac.decorators import require_permission, requires_hierarchy_level
from django_rbac.views import ModulePermissionMixin, HierarchyPermissionMixin

# Add mixin to User model
class User(RBACUserMixin, AbstractUser):
    pass

# User methods
user.hierarchy_level  # 60 (from highest role)
user.can_manage_user(other)  # True if level > other's level
user.get_manageable_roles()  # Roles below user's level
user.has_module_permission('practice', 'view')  # Permission check

@requires_hierarchy_level(60)  # Manager or higher
def approve_leave_request(request):
    ...
```

**Key rule:** Users can only manage users with LOWER hierarchy levels.

**Depends on:** django-basemodels

**Status:** ✅ Complete (packages/django-rbac, 30 tests)

---

### 1.4 django-audit-log

**Purpose:** Append-only audit trail for all model changes

**Extracts from:**
- SYSTEM_CHARTER.md: "Medical records are append-only"
- S-079: Audit Logging Staff Actions
- WORKITEM_SPAWN_AUDIT.md patterns

**Provides:**
```python
from django_audit_log import log, log_event

# Log a model operation
log(action='create', obj=my_instance, actor=request.user, request=request)

# Log with changes
log(action='update', obj=customer, actor=request.user,
    changes={'email': {'old': 'a@b.com', 'new': 'x@y.com'}})

# Log a non-model event
log_event(action='login', actor=user, metadata={'method': 'oauth'})
```

**Key features:**
- UUID primary keys, immutable logs (no updates/deletes)
- Actor tracking with string snapshots
- Before/after change diffs (JSON)
- Request context (IP, user agent, request ID)
- Sensitivity classification (normal/high/critical)

**Depends on:** None (standalone)

**Status:** ✅ Complete (packages/django-audit-log, 23 tests)

---

## Tier 2: Domain Patterns (After Tier 1 Stable)

These packages implement domain-specific patterns and depend on Tier 1.

### 2.1 django-catalog

**Purpose:** Order catalog with basket workflow and work item spawning

**Extracts from:**
- planning/catalog/*.md
- SYSTEM_EXECUTION_RULES.md: "Catalog owns definitions"
- planning/workitems/WORKITEM_SPAWNER_RULES.md

**Provides:**
```python
from django_catalog.models import CatalogItem, Basket, BasketItem, WorkItem
from django_catalog.services import commit_basket, get_or_create_draft_basket

# CatalogItem: Definition layer for orderable items
item = CatalogItem.objects.create(
    kind='service',
    service_category='lab',
    display_name='Blood Test',
)

# Basket workflow: collect items, commit spawns WorkItems
basket = get_or_create_draft_basket(encounter, user)
BasketItem.objects.create(basket=basket, catalog_item=item, added_by=user)
work_items = commit_basket(basket, user)
```

**Key features:**
- CatalogItem: services and stock items with routing rules
- Basket: encounter-scoped container for items before commit
- WorkItem: spawned executable tasks with board routing
- DispenseLog: clinical record of pharmacy dispensing
- Configurable encounter model via settings

**Key rules:**
- Catalog items become actionable only when added to a Basket and committed
- Tasks spawn only on Basket commit (idempotent)
- Routing is deterministic and stored at spawn time

**Depends on:** Configurable encounter model, django-singleton (optional for CatalogSettings)

**Status:** ✅ Complete (packages/django-catalog, 83 tests)

---

### 2.2 django-workitems

**Purpose:** Task spawning and execution tracking

**Note:** This functionality is now included in django-catalog as WorkItem model.

**Status:** ✅ Merged into django-catalog

---

### 2.3 django-encounters

**Purpose:** Domain-agnostic encounter state machine with pluggable validators

**Provides:**
```python
from django_encounters.models import EncounterDefinition, Encounter, EncounterTransition
from django_encounters.services import create_encounter, transition, get_allowed_transitions

# Define a reusable state machine
definition = EncounterDefinition.objects.create(
    key="repair_job",
    states=["pending", "active", "review", "completed"],
    transitions={"pending": ["active"], "active": ["review"], "review": ["completed"]},
    initial_state="pending",
    terminal_states=["completed"],
    validator_paths=["myapp.validators.ChecklistValidator"],
)

# Create encounter attached to ANY subject via GenericFK
encounter = create_encounter("repair_job", subject=my_asset, created_by=user)

# Transition with validation
result = transition(encounter, "active", by_user=user)
```

**Key features:**
- Definition-driven state machines (no hardcoded states)
- GenericFK subject attachment (any model: patient, asset, case, project)
- Graph validation (reachability, no orphan states, terminal state enforcement)
- Pluggable validators for hard blocks and soft warnings
- Transition audit log with metadata

**Depends on:** None (standalone, uses Django's ContentType)

**Note:** Domain-specific encounter workflows (vet clinic pipeline, legal case flow, etc.)
should be built as vertical packages that use django-encounters as a foundation.

**Status:** ✅ Complete (packages/django-encounters, 80 tests)

---

### 2.4 django-worklog

**Purpose:** Server-side work session timing for operational work tracking

**Provides:**
```python
from django_worklog.models import WorkSession
from django_worklog.services import start_session, stop_session, get_active_session

# Start a session (context via GenericFK - any model)
session = start_session(user=user, context=task)

# ... work happens ...

# Stop the active session
stopped = stop_session(user)
print(stopped.duration_seconds)  # Computed on stop

# Switch policy: starting new session auto-stops existing
start_session(user, task_a)
start_session(user, task_b)  # Stops task_a, starts task_b
```

**Key rules:**
- Server-side timestamps only (no client timestamps)
- One active session per user (Switch policy)
- GenericFK for context attachment to any model
- duration_seconds computed on stop, immutable after

**Key features:**
- `start_session(user, context)` - Switch policy (stops old, starts new)
- `stop_session(user)` - Raises NoActiveSession if none active
- `get_active_session(user)` - Returns session or None

**Depends on:** None (standalone)

**Status:** ✅ Complete (packages/django-worklog, 31 tests)

---

## Tier 3: Infrastructure (After Tier 2 Stable)

### 3.1 django-modules

**Purpose:** Module enable/disable per organization

**Extracts from:**
- SYSTEM_CHARTER.md: "Module Configuration"

**Provides:**
```python
from django_modules import is_module_enabled, require_module, list_enabled_modules
from django_modules.models import Module, OrgModuleState

# Define a module
Module.objects.create(key='pharmacy', name='Pharmacy', active=True)

# Per-org override (disable pharmacy for this org)
OrgModuleState.objects.create(org=org, module=module, enabled=False)

# Check if enabled (resolution: org override > global default)
if is_module_enabled(org, 'pharmacy'):
    # pharmacy features available

# Enforce in views/services
require_module(org, 'pharmacy')  # Raises ModuleDisabled if disabled

# List all enabled modules for org
enabled = list_enabled_modules(org)  # {'billing', 'lab', ...}
```

**Key rules:**
- One boolean: enabled/disabled (no variants, no percentage rollout)
- Resolution order: OrgModuleState.enabled > Module.active (global default)
- Swappable org model via MODULES_ORG_MODEL setting

**Depends on:** django-basemodels

**Status:** ✅ Complete (packages/django-modules, 57 tests)

---

### 3.2 django-singleton

**Purpose:** Singleton settings pattern (pk=1 enforcement)

**Provides:**
```python
from django_singleton.models import SingletonModel

class StoreSettings(SingletonModel):
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        app_label = "store"

# Access the singleton
settings = StoreSettings.get_instance()
settings.tax_rate = 7.5
settings.save()
```

**Key features:**
- `pk=1` enforced on every save
- `get_instance()` classmethod with race condition handling
- `delete()` raises `SingletonDeletionError` (no silent no-ops)
- Detects rogue rows and raises `SingletonViolationError`

**Depends on:** None (standalone abstract model)

**Status:** ✅ Complete (packages/django-singleton, 15 tests)

**Consumers:** django-catalog (CatalogSettings singleton for allow_inactive_items behavior)

---

### 3.3 django-layers

**Purpose:** Import boundary enforcement for CI

**Extracts from:**
- ARCHITECTURE_ENFORCEMENT.md

**Provides:**
```bash
# CI command
python -m django_layers.check --config layers.yaml

# layers.yaml defines allowed import directions
```

**Status:** Not started

---

## Extraction Order Summary

```
Phase 1: Foundation
  └── django-basemodels (no deps) ✅
  └── django-parties (needs basemodels) ✅
  └── django-rbac (needs basemodels) ✅
  └── django-audit-log (standalone) ✅

Phase 2: Domain
  └── django-catalog (standalone, configurable encounter) ✅
  └── django-workitems (merged into django-catalog) ✅
  └── django-encounters (standalone, GenericFK) ✅
  └── django-worklog (standalone) ✅

Phase 3: Infrastructure
  └── django-modules (needs basemodels) ✅
  └── django-singleton (no deps) ✅
  └── django-layers (standalone tool)
```

---

## Success Criteria

Each package is "done" when:

1. [ ] Standalone repo with pyproject.toml
2. [ ] 95%+ test coverage
3. [ ] No imports from other primitives (except foundation)
4. [ ] README with installation and usage
5. [ ] Published to PyPI (or private index)
6. [ ] VetFriendly migrated to use the package
