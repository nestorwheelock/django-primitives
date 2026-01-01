# Prompt: Rebuild django-basemodels

## Instruction

Create a Django package called `django-basemodels` that provides reusable abstract base model classes for timestamps, UUID primary keys, and soft delete functionality.

## Package Purpose

Provide foundational abstract models that all other domain models inherit from:
- `TimeStampedModel` - automatic created_at/updated_at timestamps
- `UUIDModel` - UUID primary key instead of auto-increment integer
- `SoftDeleteModel` - soft delete with restore capability
- `BaseModel` - combines TimeStampedModel + SoftDeleteModel (recommended default)

## Dependencies

- Django >= 4.2
- No other dependencies (this is the foundation layer)

## File Structure

```
packages/django-basemodels/
├── pyproject.toml
├── README.md
├── src/django_basemodels/
│   ├── __init__.py
│   ├── apps.py
│   └── models.py
└── tests/
    ├── __init__.py
    ├── settings.py
    ├── models.py
    └── test_basemodels.py
```

## Models Specification

### TimeStampedModel

Abstract model with automatic timestamps.

**Fields:**
- `created_at`: DateTimeField, auto_now_add=True
- `updated_at`: DateTimeField, auto_now=True

**Behavior:**
- `created_at` set once on creation, never changes
- `updated_at` updates on every save

### UUIDModel

Abstract model with UUID primary key.

**Fields:**
- `id`: UUIDField, primary_key=True, default=uuid.uuid4, editable=False

**Behavior:**
- UUID auto-generated before first save
- Not editable after creation
- Each instance gets unique UUID

### SoftDeleteManager

Custom manager that filters out soft-deleted records.

**Methods:**
- `get_queryset()`: Returns only records where deleted_at IS NULL
- `with_deleted()`: Returns ALL records including soft-deleted
- `deleted_only()`: Returns ONLY soft-deleted records

### SoftDeleteModel

Abstract model with soft delete functionality.

**Fields:**
- `deleted_at`: DateTimeField, null=True, blank=True

**Managers:**
- `objects`: SoftDeleteManager (default, excludes deleted)
- `all_objects`: models.Manager (includes deleted)

**Methods:**
- `delete()`: Sets deleted_at to timezone.now(), does NOT remove row
- `hard_delete()`: Permanently removes row from database
- `restore()`: Sets deleted_at to None

**Properties:**
- `is_deleted`: Returns True if deleted_at is not None

### BaseModel

Combines TimeStampedModel and SoftDeleteModel.

**Inheritance:** `class BaseModel(TimeStampedModel, SoftDeleteModel)`

**Fields (inherited):**
- `created_at`
- `updated_at`
- `deleted_at`

## Test Cases (30 tests)

### TimeStampedModel Tests (4)
1. `test_created_at_auto_populated` - created_at set on creation
2. `test_updated_at_auto_populated` - updated_at set on creation
3. `test_updated_at_changes_on_save` - updated_at changes when modified
4. `test_created_at_unchanged_on_save` - created_at never changes

### UUIDModel Tests (4)
1. `test_uuid_primary_key` - pk is UUID type
2. `test_uuid_auto_generated` - UUID generated before save
3. `test_uuid_unique_per_instance` - each instance unique UUID
4. `test_uuid_not_editable` - editable=False on field

### SoftDeleteManager Tests (5)
1. `test_default_excludes_deleted` - objects.all() excludes deleted
2. `test_with_deleted_includes_all` - with_deleted() includes deleted
3. `test_deleted_only_returns_deleted` - deleted_only() returns only deleted
4. `test_count_excludes_deleted` - count() excludes deleted
5. `test_all_objects_includes_everything` - all_objects includes all

### SoftDeleteModel Tests (6)
1. `test_delete_sets_timestamp` - delete() sets deleted_at
2. `test_delete_does_not_remove_row` - delete() keeps row in DB
3. `test_hard_delete_removes_row` - hard_delete() removes row
4. `test_restore_clears_deleted_at` - restore() sets deleted_at=None
5. `test_restore_makes_visible_in_default_queryset` - restored visible in objects
6. `test_is_deleted_property` - is_deleted returns correct bool

### BaseModel Tests (4)
1. `test_has_timestamps` - has created_at and updated_at
2. `test_has_soft_delete` - has soft delete functionality
3. `test_has_restore` - restore works
4. `test_manager_order` - default manager is SoftDeleteManager

### UUIDModel + BaseModel Combined Tests (2)
1. `test_combined_uuid_and_basemodel` - all features work together
2. `test_conditional_unique_constraint` - unique constraints respect soft delete

### Gotcha Tests (2)
1. `test_queryset_delete_is_hard_delete` - QuerySet.delete() is HARD delete (gotcha!)
2. `test_bulk_soft_delete_with_update` - correct way: update(deleted_at=now())

### Meta Tests (3)
1. `test_base_classes_are_abstract` - all base classes abstract=True
2. `test_concrete_model_has_table` - concrete models have tables
3. `test_field_names` - expected fields present

## Test Models Required

Create concrete test models in `tests/models.py`:

```python
class TimestampedTestModel(TimeStampedModel):
    name = models.CharField(max_length=100)
    class Meta:
        app_label = 'tests'

class UUIDTestModel(UUIDModel):
    name = models.CharField(max_length=100)
    class Meta:
        app_label = 'tests'

class SoftDeleteTestModel(SoftDeleteModel):
    name = models.CharField(max_length=100)
    class Meta:
        app_label = 'tests'

class BaseTestModel(BaseModel):
    name = models.CharField(max_length=100)
    class Meta:
        app_label = 'tests'

class UUIDBaseTestModel(UUIDModel, BaseModel):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    class Meta:
        app_label = 'tests'
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_test_email'
            )
        ]
```

## Known Gotchas to Document

1. **QuerySet.delete() is HARD delete**: `Model.objects.filter(...).delete()` bypasses soft delete and permanently removes rows. Use `update(deleted_at=timezone.now())` for bulk soft delete.

2. **Unique constraints with soft delete**: Use conditional UniqueConstraint with `condition=Q(deleted_at__isnull=True)` so deleted records don't block new ones.

3. **Manager inheritance**: When combining with other mixins, ensure SoftDeleteManager is the default manager.

## __init__.py Exports

```python
from .models import TimeStampedModel, UUIDModel, SoftDeleteModel, SoftDeleteManager, BaseModel

__all__ = [
    'TimeStampedModel',
    'UUIDModel',
    'SoftDeleteModel',
    'SoftDeleteManager',
    'BaseModel',
]
```

## README Content

Document:
- Installation instructions
- Quick start example
- Each model class with usage
- The bulk delete gotcha
- Recommended pattern: `class MyModel(UUIDModel, BaseModel)`
- Conditional unique constraint example

## Acceptance Criteria

- [ ] All 4 abstract models implemented
- [ ] SoftDeleteManager with 3 methods
- [ ] All 30 tests passing
- [ ] No database migrations (abstract models only)
- [ ] README with usage examples
- [ ] Gotchas documented
