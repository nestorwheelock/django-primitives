# django-basemodels

Reusable Django base models with timestamps and soft delete.

## Installation

```bash
pip install django-basemodels
```

## Usage

```python
from django_basemodels import BaseModel

class Customer(BaseModel):
    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        pass  # No need to set abstract
```

## Available Base Classes

### BaseModel (Recommended)

Combines timestamps and soft delete - use this for most models.

```python
from django_basemodels import BaseModel

class Invoice(BaseModel):
    number = models.CharField(max_length=20)
    total = models.DecimalField(max_digits=10, decimal_places=2)
```

Features:
- `created_at` - Auto-set on creation
- `updated_at` - Auto-updated on save
- `deleted_at` - Soft delete timestamp
- `objects` - Manager excluding deleted records
- `all_objects` - Manager including deleted records

### TimeStampedModel

Just timestamps, no soft delete.

```python
from django_basemodels import TimeStampedModel

class AuditLog(TimeStampedModel):
    action = models.CharField(max_length=100)
```

### SoftDeleteModel

Just soft delete, no timestamps.

```python
from django_basemodels import SoftDeleteModel

class Document(SoftDeleteModel):
    title = models.CharField(max_length=200)
```

### UUIDModel

UUID primary key instead of auto-increment.

```python
from django_basemodels import UUIDModel

class APIKey(UUIDModel):
    name = models.CharField(max_length=100)
```

## Soft Delete Operations

```python
# Soft delete (sets deleted_at, doesn't remove from DB)
customer.delete()

# Check if deleted
customer.is_deleted  # True

# Restore
customer.restore()

# Permanent delete
customer.hard_delete()

# Query only active records (default)
Customer.objects.all()

# Query all records including deleted
Customer.all_objects.all()

# Query only deleted records
Customer.objects.deleted_only()
```

## Requirements

- Python >= 3.10
- Django >= 4.2

## License

Copyright (c) 2025 Nestor Wheelock. All Rights Reserved.

This software is proprietary and confidential.
