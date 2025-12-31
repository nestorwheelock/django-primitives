# Dependency Rules

**Status:** Authoritative
**Enforcement:** CI blocks violations

---

## Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│   Your Django project (vetfriendly, etc.)                   │
│   → May import from any primitive package                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    PRIMITIVE PACKAGES                        │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ django-     │  │ django-     │  │ django-     │         │
│  │ party       │  │ rbac        │  │ audit       │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  → Primitives may import from Foundation only                │
│  → Primitives must NOT import from each other               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    FOUNDATION LAYER                          │
│   django-basemodels (BaseModel, soft delete, timestamps)    │
│   → Imported by all primitives                               │
│   → Imports from Django/stdlib only                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Dependency Direction

```
Application  →  can import from  →  Primitives
Primitives   →  can import from  →  Foundation
Foundation   →  can import from  →  Django, stdlib
```

### Forbidden Patterns

```python
# ❌ FORBIDDEN - primitive importing another primitive
# In django-party/models.py:
from django_rbac.models import Role  # NO

# ❌ FORBIDDEN - foundation importing primitive
# In django-basemodels/models.py:
from django_party.models import Person  # NO

# ❌ FORBIDDEN - primitive importing application
# In django-audit/services.py:
from apps.pets.models import Pet  # NO
```

### Allowed Patterns

```python
# ✅ ALLOWED - application importing primitive
from django_party.models import Person, Organization
from django_rbac.models import Role
from django_basemodels.models import BaseModel

# ✅ ALLOWED - primitive importing foundation
from django_basemodels.models import BaseModel

# ✅ ALLOWED - foundation importing Django
from django.db import models
from django.utils import timezone
```

---

## Package Isolation Rules

Each primitive package must be:

1. **Self-contained**: No cross-primitive imports
2. **Configurable**: Settings via Django settings, not hardcoded
3. **Optional**: Application can use any subset of primitives
4. **Testable**: Full test suite runs without other primitives installed

### If primitives need to interact

Use **protocols** (abstract interfaces):

```python
# In django-audit (wants to log party changes)
# Does NOT import django-party

class AuditableModel(Protocol):
    """Any model that can be audited."""
    id: UUID
    created_at: datetime
    updated_at: datetime

def log_change(instance: AuditableModel, action: str) -> None:
    # Works with any model matching the protocol
    ...
```

The **application layer** wires things together:

```python
# In your Django project
from django_party.models import Person
from django_audit.services import log_change

# Application-level integration
Person.add_listener(lambda p: log_change(p, 'updated'))
```

---

## Import Checking

Enforcement script: `/scripts/check_dependencies.py`

```bash
# Run before commit
python scripts/check_dependencies.py

# CI runs this automatically
```

Violations produce:

```
ERROR: django_party/models.py imports from django_rbac
  Line 5: from django_rbac.models import Role

  Primitives must not import from each other.
  Use protocols or application-layer integration.
```

---

## Why This Matters

| Without boundaries | With boundaries |
|-------------------|-----------------|
| Change in one package breaks others | Packages evolve independently |
| Must install everything | Install only what you need |
| Circular imports | Clean dependency graph |
| Tight coupling | Loose coupling via protocols |
| Hard to test in isolation | Each package fully testable |
