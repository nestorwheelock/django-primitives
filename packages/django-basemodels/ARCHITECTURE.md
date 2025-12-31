# Architecture: django-basemodels

**Status:** Stable / Feature-Complete / v0.1.0
**Author:** Nestor Wheelock
**License:** Proprietary

This package provides abstract base models for Django applications. It is intentionally minimal and will not grow features.

---

## Design Intent

- **Boring** - No clever abstractions
- **Stable** - Changes require migration notes and justification
- **Universal** - Used by all models in the stack

---

## What This Package Provides

| Class | Purpose |
|-------|---------|
| `BaseModel` | Timestamps + soft delete (recommended default) |
| `TimeStampedModel` | Just `created_at` / `updated_at` |
| `SoftDeleteModel` | Just `deleted_at` with manager filtering |
| `UUIDModel` | UUID primary key |
| `SoftDeleteManager` | Excludes soft-deleted rows by default |

---

## What This Package Does NOT Do

- No business logic
- No domain-specific fields
- No integrations
- No views, forms, or templates
- No signals or hooks
- No cascade handling (see below)

---

## Hard Rules

1. **All application models inherit from these bases** - No redefining `created_at`, `updated_at`, `deleted_at`, or UUID fields
2. **Soft delete is the default** - `.delete()` sets `deleted_at`, never removes rows
3. **Hard deletes are explicit** - Use `.hard_delete()` only when required and documented
4. **No upward dependencies** - This package depends only on Django

---

## Soft Delete Invariants

### Manager Behavior

```python
# Default manager excludes deleted
MyModel.objects.all()        # Only active records (deleted_at IS NULL)
MyModel.objects.count()      # Only counts active records

# all_objects includes everything
MyModel.all_objects.all()    # All records including deleted
MyModel.all_objects.count()  # Total count

# Convenience methods
MyModel.objects.with_deleted()   # Includes deleted (one-off)
MyModel.objects.deleted_only()   # Only deleted records
```

### Delete Operations

```python
obj.delete()      # Sets deleted_at = now(), row stays in DB
obj.hard_delete() # Permanently removes row from DB
obj.restore()     # Sets deleted_at = None
obj.is_deleted    # Property: True if deleted_at is not None
```

---

## Known Gotchas (READ THIS)

### 1. Unique Constraints

**Problem:** Soft delete breaks naive unique constraints.

```python
# This WILL fail:
class User(BaseModel):
    email = models.EmailField(unique=True)

user1 = User.objects.create(email='bob@example.com')
user1.delete()  # deleted_at = now()
user2 = User.objects.create(email='bob@example.com')  # IntegrityError!
```

**Solution A: Conditional unique constraint (Django 4.0+)**
```python
class User(BaseModel):
    email = models.EmailField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_email'
            )
        ]
```

**Solution B: Composite unique with deleted_at**
```python
class User(BaseModel):
    email = models.EmailField()

    class Meta:
        unique_together = [('email', 'deleted_at')]
        # Note: This allows multiple deleted records with same email
        # but only ONE active record per email
```

**Decision:** This package does NOT enforce a pattern. Applications MUST choose and document their approach.

### 2. Foreign Key Behavior

**Problem:** ForeignKey to a soft-deleted record still works at DB level.

```python
class Order(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)

customer = Customer.objects.create(name='Bob')
order = Order.objects.create(customer=customer)
customer.delete()  # Soft delete

# The FK is NOT broken - row still exists:
order.customer  # Still returns the Customer instance
order.customer.is_deleted  # True

# BUT: filtered queries won't find it:
Customer.objects.filter(pk=customer.pk).exists()  # False!
Customer.all_objects.filter(pk=customer.pk).exists()  # True
```

**Decision:** Applications MUST decide how to handle FK to deleted records:
- Check `related_obj.is_deleted` in views/serializers
- Use `all_objects` when resolving FKs
- Add validation in forms/serializers

### 3. Cascade Behavior

**Problem:** Soft delete does NOT cascade to related objects.

```python
class Customer(BaseModel):
    name = models.CharField(max_length=100)

class Order(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

customer.delete()  # Soft deletes customer only
# Orders are NOT soft-deleted automatically
```

**Decision:** This package does NOT implement cascade soft delete. Reasons:
1. Cascade behavior varies by domain
2. Some relations should NOT cascade (audit logs, history)
3. Explicit is better than implicit

Applications MUST implement cascade logic explicitly:
```python
def delete_customer_with_orders(customer):
    customer.orders.all().update(deleted_at=timezone.now())
    customer.delete()
```

### 4. Bulk Operations

**CRITICAL:** QuerySet.delete() does NOT call the model's delete() method.

```python
# This HARD DELETES all matching rows:
Customer.objects.filter(inactive=True).delete()  # GONE FOREVER

# This soft-deletes:
Customer.objects.filter(inactive=True).update(deleted_at=timezone.now())
```

**Decision:** This is Django behavior and cannot be changed without significant complexity. Document and use `.update(deleted_at=...)` for bulk soft delete.

### 5. Admin Integration

Django admin's delete action uses QuerySet.delete() by default, which means **hard delete**.

**Solution:** Override admin delete action:
```python
@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    def delete_queryset(self, request, queryset):
        queryset.update(deleted_at=timezone.now())

    def delete_model(self, request, obj):
        obj.delete()  # Uses soft delete
```

### 6. Manager Declaration Order

**CRITICAL:** The first manager declared becomes the default.

```python
# CORRECT:
class MyModel(SoftDeleteModel):
    objects = SoftDeleteManager()  # First = default
    all_objects = models.Manager()

# WRONG:
class MyModel(SoftDeleteModel):
    all_objects = models.Manager()  # First = default (WRONG!)
    objects = SoftDeleteManager()
```

BaseModel and SoftDeleteModel declare managers in the correct order.

---

## Recommended Usage

### Standard Model (Most Cases)

```python
from django_basemodels import BaseModel, UUIDModel

class Customer(UUIDModel, BaseModel):
    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_customer_email'
            )
        ]
```

### Immutable Records (No Soft Delete)

```python
from django_basemodels import UUIDModel, TimeStampedModel

class AuditLog(UUIDModel, TimeStampedModel):
    # No soft delete - audit logs are permanent
    action = models.CharField(max_length=50)
    details = models.JSONField()
```

### Reference Data (No UUID)

```python
from django_basemodels import BaseModel

class Country(BaseModel):
    # Integer PK is fine for reference data
    code = models.CharField(max_length=2, unique=True)
    name = models.CharField(max_length=100)
```

---

## Testing Your Models

Verify soft delete behavior in your tests:

```python
def test_soft_delete_excludes_from_default_queryset(self):
    obj = MyModel.objects.create(name='Test')
    obj.delete()

    assert MyModel.objects.filter(pk=obj.pk).exists() is False
    assert MyModel.all_objects.filter(pk=obj.pk).exists() is True
    assert obj.is_deleted is True

def test_restore_includes_in_default_queryset(self):
    obj = MyModel.objects.create(name='Test')
    obj.delete()
    obj.restore()

    assert MyModel.objects.filter(pk=obj.pk).exists() is True
    assert obj.is_deleted is False

def test_hard_delete_removes_permanently(self):
    obj = MyModel.objects.create(name='Test')
    obj.hard_delete()

    assert MyModel.all_objects.filter(pk=obj.pk).exists() is False
```

---

## Versioning

This package follows semantic versioning:
- **MAJOR**: Breaking changes to model fields or manager behavior
- **MINOR**: New features (new model classes, new manager methods)
- **PATCH**: Bug fixes only

Pin to specific versions in requirements:
```
django-basemodels==0.1.0
```

---

## Changes

Any modifications to this package require:
- Clear justification
- Migration notes for downstream consumers
- Review of all dependent packages

**Do not "fix" things casually. If it works, leave it alone.**

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial stable release
- TimeStampedModel: created_at, updated_at
- UUIDModel: UUID primary key
- SoftDeleteModel: deleted_at with manager filtering
- BaseModel: Combined timestamps + soft delete
- SoftDeleteManager: Default excludes deleted, with_deleted(), deleted_only()
