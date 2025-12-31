# Boundary Tests & Enforcement

**Purpose:** Automated checks that prevent architectural drift.

---

## What We Enforce

| Rule | Check | Blocks CI |
|------|-------|-----------|
| Layer dependencies | Primitives don't import each other | Yes |
| BaseModel usage | No redefined timestamps | Yes |
| Soft delete | Domain models use BaseModel | Yes |
| Public API | Cross-package access via services/selectors | Yes |

---

## 1. Layer Dependency Check

**Script:** `/scripts/check_dependencies.py`

**Rule:** Primitives must not import from each other. Only from foundation (django-basemodels) and Django/stdlib.

### What It Scans

```
src/django_*/
├── models.py
├── services.py
├── selectors.py
├── views.py
└── *.py (all Python files except tests)
```

### Forbidden Patterns

```python
# In any primitive package:
from django_party.models import Person      # ❌ Cross-primitive
from django_rbac.services import RoleService # ❌ Cross-primitive
import django_audit                          # ❌ Cross-primitive
```

### Allowed Patterns

```python
from django_basemodels.models import BaseModel  # ✅ Foundation
from django.db import models                    # ✅ Django
from typing import Protocol                     # ✅ stdlib
```

### Output

```
$ python scripts/check_dependencies.py

Scanning: src/django_party/
  ✓ models.py
  ✓ services.py
  ✓ selectors.py

Scanning: src/django_rbac/
  ✗ services.py:5 - imports from django_party.models
    → Primitives must not import from each other

FAILED: 1 violation found
```

---

## 2. BaseModel Usage Check

**Script:** `/scripts/check_basemodel.py`

**Rule:** Domain models must inherit from BaseModel, not define their own timestamps.

### Forbidden Patterns

```python
class Pet(models.Model):  # ❌ Should inherit BaseModel
    created_at = models.DateTimeField(auto_now_add=True)  # ❌ Redefined

class Appointment(BaseModel):
    created_at = models.DateTimeField()  # ❌ Overrides BaseModel field
    updated_at = models.DateTimeField()  # ❌ Overrides BaseModel field
```

### Correct Pattern

```python
from django_basemodels.models import BaseModel

class Pet(BaseModel):
    name = models.CharField(max_length=100)
    # Inherits id, created_at, updated_at, deleted_at from BaseModel
```

### Output

```
$ python scripts/check_basemodel.py

Scanning: src/django_party/models.py
  ✗ Line 15: Person redefines 'created_at' (inherited from BaseModel)
  ✗ Line 45: Organization does not inherit from BaseModel

FAILED: 2 violations found
```

---

## 3. Soft Delete Check

**Script:** `/scripts/check_softdelete.py`

**Rule:** Domain models must use soft delete (via BaseModel), not hard delete.

### What It Checks

- Models inherit from BaseModel (which has deleted_at)
- No `.delete()` calls that bypass soft delete
- No raw SQL DELETE statements

### Forbidden Patterns

```python
# Direct hard delete
Pet.objects.filter(id=pet_id).delete()  # ❌ Bypasses soft delete

# Raw SQL
cursor.execute("DELETE FROM pets WHERE id = %s", [pet_id])  # ❌
```

### Correct Pattern

```python
pet = Pet.objects.get(id=pet_id)
pet.delete()  # ✅ BaseModel.delete() sets deleted_at

# For permanent removal (rare, audited)
pet.hard_delete()  # ✅ Explicit, audited
```

---

## 4. Public API Check

**Script:** `/scripts/check_public_api.py`

**Rule:** Cross-package access must go through services.py or selectors.py, not direct model access.

### Forbidden Patterns

```python
# In application code or other packages:
from django_party.models import Person
persons = Person.objects.filter(...)  # ❌ Direct model access
```

### Correct Patterns

```python
from django_party.selectors import get_persons_by_organization
from django_party.services import PersonService

persons = get_persons_by_organization(org_id)  # ✅ Via selector
person = PersonService.create(...)              # ✅ Via service
```

---

## Running All Checks

```bash
# Run all boundary checks
python scripts/check_all.py

# Or individually
python scripts/check_dependencies.py
python scripts/check_basemodel.py
python scripts/check_softdelete.py
python scripts/check_public_api.py
```

---

## CI Integration

### GitHub Actions

```yaml
# .github/workflows/boundaries.yml
name: Boundary Checks

on: [push, pull_request]

jobs:
  boundaries:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e .
      - run: python scripts/check_all.py
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: boundary-checks
        name: Boundary Checks
        entry: python scripts/check_all.py
        language: python
        pass_filenames: false
```

---

## Allowlist (Grandfathering)

For legacy code that violates boundaries but can't be fixed immediately:

```yaml
# .boundary-allowlist.yaml
dependencies:
  - file: src/django_party/legacy.py
    imports: django_rbac.models
    reason: "Legacy integration, tracked in issue #123"
    expires: 2025-03-01

basemodel:
  - file: src/django_party/models.py
    field: created_at
    reason: "Migration in progress"
    expires: 2025-02-15
```

Allowlisted violations produce warnings, not failures:

```
WARNING: Allowlisted violation (expires 2025-03-01):
  src/django_party/legacy.py imports django_rbac.models
```

---

## Adding New Checks

To add a new boundary check:

1. Create script in `/scripts/check_{rule}.py`
2. Follow the pattern: scan files, detect violations, return exit code
3. Add to `check_all.py`
4. Document in this file
5. Add to CI workflow
