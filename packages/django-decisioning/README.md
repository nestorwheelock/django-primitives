# django-decisioning

Decision surface contract, time semantics, and idempotency primitives for Django.

## Overview

This package provides the "constitutional law" for decision surfaces in the django-primitives framework:

- **TimeSemanticsMixin**: Dual timestamps (`effective_at` + `recorded_at`) for business facts
- **EffectiveDatedMixin**: Validity periods (`valid_from` + `valid_to`) for temporal records
- **EventAsOfQuerySet**: Query helper for append-only events
- **EffectiveDatedQuerySet**: Query helper for validity-period records
- **IdempotencyKey**: Request-level idempotency with state tracking
- **Decision**: Generic decision record for audit trails
- **@idempotent**: Decorator for retry-safe operations

## Installation

```bash
pip install django-decisioning
```

## Quick Start

```python
from django.db import models
from django_decisioning import TimeSemanticsMixin, EffectiveDatedMixin

class MyBusinessFact(TimeSemanticsMixin, models.Model):
    """A fact with dual timestamps."""
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = 'myapp'

class MyAgreement(EffectiveDatedMixin, models.Model):
    """A record with validity period."""
    terms = models.JSONField()

    class Meta:
        app_label = 'myapp'
```

## Time Semantics Contract

Every business fact has two timestamps:

| Field | Meaning | Who Controls |
|-------|---------|--------------|
| `effective_at` | When the fact is true in the business world | Business logic (may be backdated) |
| `recorded_at` | When the system learned the fact | System only (`auto_now_add=True`) |

## License

Proprietary
