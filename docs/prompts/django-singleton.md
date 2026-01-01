# Prompt: Rebuild django-singleton

## Instruction

Create a Django package called `django-singleton` that provides an abstract base model for singleton configuration tables - models where exactly one row should exist.

## Package Purpose

Provide a `SingletonModel` abstract base class for settings/configuration models that:
- Enforces pk=1 (only one row allowed)
- Prevents deletion
- Detects corruption (multiple rows)
- Provides safe get_or_create via `get_instance()`

## Dependencies

- Django >= 4.2
- No other dependencies (foundation layer)

## File Structure

```
packages/django-singleton/
├── pyproject.toml
├── README.md
├── src/django_singleton/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   └── exceptions.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_models.py
    └── testapp/
        ├── __init__.py
        ├── apps.py
        └── models.py
```

## Exceptions Specification

### exceptions.py

```python
class SingletonError(Exception):
    """Base exception for singleton errors."""
    pass

class SingletonDeletionError(SingletonError):
    """Raised when attempting to delete a singleton."""
    pass

class SingletonViolationError(SingletonError):
    """Raised when singleton invariant would be violated."""
    pass
```

## Model Specification

### SingletonModel

Abstract base model that enforces single-row constraint.

**Behavior:**

1. **save() method:**
   - Always sets `self.pk = 1`
   - Before saving, checks if any rows exist with pk != 1
   - If rogue rows exist, raises `SingletonViolationError`
   - Then calls `super().save()`

2. **delete() method:**
   - Always raises `SingletonDeletionError`
   - Never deletes the row

3. **get_instance() classmethod:**
   - Uses `transaction.atomic()` with `get_or_create(pk=1)`
   - Handles race conditions via IntegrityError retry
   - Returns the singleton instance

**Implementation:**

```python
class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        existing = self.__class__.objects.exclude(pk=1).exists()
        if existing:
            raise SingletonViolationError(
                f"Multiple rows exist for singleton {self.__class__.__name__}. "
                "Remove extra rows before saving."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise SingletonDeletionError(
            f"Cannot delete singleton {self.__class__.__name__}"
        )

    @classmethod
    def get_instance(cls):
        try:
            with transaction.atomic():
                obj, _ = cls.objects.get_or_create(pk=1)
                return obj
        except IntegrityError:
            return cls.objects.get(pk=1)
```

## Test Models Required

Create in `tests/testapp/models.py`:

```python
from django.db import models
from django_singleton.models import SingletonModel

class SiteSettings(SingletonModel):
    site_name = models.CharField(max_length=100, default='')
    maintenance_mode = models.BooleanField(default=False)

    class Meta:
        app_label = 'testapp'

class TaxSettings(SingletonModel):
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        app_label = 'testapp'
```

## Test Cases (15 tests)

### Creation Tests (7)
1. `test_singleton_can_be_created` - create with objects.create()
2. `test_pk_is_always_1` - pk=999 becomes pk=1
3. `test_get_instance_creates_if_not_exists` - creates when empty
4. `test_get_instance_returns_existing` - returns existing row
5. `test_get_instance_always_returns_pk_1` - always pk=1
6. `test_second_save_still_uses_pk_1` - update keeps pk=1
7. `test_multiple_get_instance_calls_return_same_instance` - same data

### Field Tests (2)
1. `test_fields_work_correctly` - custom fields work
2. `test_singleton_persists_data` - data persists

### Multiple Singletons Test (1)
1. `test_multiple_singletons_are_independent` - SiteSettings and TaxSettings separate

### Deletion Tests (3)
1. `test_delete_raises_error` - raises SingletonDeletionError
2. `test_delete_does_not_remove_row` - row still exists after failed delete
3. `test_subclass_inherits_deletion_protection` - subclasses protected

### Violation Tests (2)
1. `test_save_with_rogue_rows_raises_error` - detects pk!=1 rows
2. `test_subclass_inherits_violation_protection` - subclasses detect

## Test Setup

The tests use raw SQL to insert rogue rows (bypassing save()) to test violation detection:

```python
with connection.cursor() as cursor:
    cursor.execute(
        "INSERT INTO testapp_sitesettings (id, site_name, maintenance_mode) "
        "VALUES (2, 'Rogue', 0)"
    )
```

## testapp Configuration

### testapp/apps.py

```python
from django.apps import AppConfig

class TestappConfig(AppConfig):
    name = 'tests.testapp'
    default_auto_field = 'django.db.models.BigAutoField'
```

### tests/settings.py

```python
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django_singleton',
    'tests.testapp',
]
```

## __init__.py Exports

```python
from .models import SingletonModel
from .exceptions import SingletonError, SingletonDeletionError, SingletonViolationError

__all__ = [
    'SingletonModel',
    'SingletonError',
    'SingletonDeletionError',
    'SingletonViolationError',
]
```

## Use Cases

1. **Site settings** - site name, maintenance mode, contact email
2. **Feature flags** - global feature toggles
3. **Cache configuration** - TTL settings
4. **API rate limits** - global rate limit config

## Known Gotchas

1. **QuerySet.delete() bypasses protection**: `Model.objects.all().delete()` will delete the row. Only instance.delete() is protected.

2. **Fixtures/migrations can corrupt**: Bulk inserts can create rows with pk!=1. The save() method detects this.

3. **Race conditions**: get_instance() handles race conditions but relies on database-level uniqueness constraint on pk.

## Acceptance Criteria

- [ ] SingletonModel abstract class implemented
- [ ] 3 custom exceptions implemented
- [ ] pk always forced to 1
- [ ] delete() always raises
- [ ] get_instance() handles race conditions
- [ ] Violation detection on save
- [ ] All 15 tests passing
- [ ] README with usage examples
