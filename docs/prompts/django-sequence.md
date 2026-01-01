# Prompt: Rebuild django-sequence

## Instruction

Create a Django package called `django-sequence` that provides human-readable sequence ID generation for multi-tenant environments.

## Package Purpose

Generate formatted sequence IDs like "INV-2026-000123" for business documents:
- Multi-tenant isolation (per-organization counters)
- Globally unique sequences (when no org specified)
- Customizable formatting (prefix, padding, year)
- Race-condition safe with database-level locking
- Atomic transactions prevent duplicate IDs

## Dependencies

- Django >= 4.2
- django.contrib.contenttypes

## File Structure

```
packages/django-sequence/
├── pyproject.toml
├── README.md
├── src/django_sequence/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── models.py
    ├── test_sequence.py
    ├── test_services.py
    └── test_integration.py
```

## Exceptions Specification

### exceptions.py

```python
class SequenceError(Exception):
    """Base exception for sequence errors."""
    pass

class SequenceNotFoundError(SequenceError):
    """Raised when sequence doesn't exist and auto_create is False."""
    pass

class SequenceLockedError(SequenceError):
    """Raised when sequence cannot be locked (timeout)."""
    pass
```

## Model Specification

### Sequence Model

```python
from django.db import models
from django.contrib.contenttypes.models import ContentType
from datetime import date

class Sequence(models.Model):
    scope = models.CharField(max_length=50)
    org_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        null=True, blank=True
    )
    org_id = models.CharField(max_length=255, blank=True, default='')
    prefix = models.CharField(max_length=20)
    current_value = models.PositiveBigIntegerField(default=0)
    pad_width = models.PositiveSmallIntegerField(default=6)
    include_year = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'django_sequence'
        unique_together = ['scope', 'org_content_type', 'org_id']
        indexes = [
            models.Index(fields=['scope', 'org_content_type', 'org_id']),
        ]

    @property
    def formatted_value(self) -> str:
        """Return formatted sequence value."""
        number = str(self.current_value).zfill(self.pad_width)
        if self.include_year:
            return f"{self.prefix}{date.today().year}-{number}"
        return f"{self.prefix}{number}"

    @property
    def org(self):
        """Get organization instance via ContentType."""
        if self.org_content_type and self.org_id:
            model = self.org_content_type.model_class()
            return model.objects.get(pk=self.org_id)
        return None

    @org.setter
    def org(self, value):
        if value is None:
            self.org_content_type = None
            self.org_id = ''
        else:
            self.org_content_type = ContentType.objects.get_for_model(value)
            self.org_id = str(value.pk)

    def __str__(self):
        org_display = f"org:{self.org_id}" if self.org_id else "global"
        return f"{self.scope} ({org_display}): {self.current_value}"
```

## Service Function

### services.py

```python
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import Sequence
from .exceptions import SequenceNotFoundError

def next_sequence(
    scope: str,
    org=None,
    prefix: str = '',
    pad_width: int = 6,
    include_year: bool = True,
    auto_create: bool = True,
) -> str:
    """
    Atomically get next sequence value with race-condition protection.

    Args:
        scope: Sequence scope identifier (e.g., 'invoice')
        org: Organization instance (None for global)
        prefix: Prefix for formatted value
        pad_width: Zero-padding width
        include_year: Include year in formatted value
        auto_create: Create sequence if not found

    Returns:
        Formatted sequence value (e.g., "INV-2026-000001")

    Raises:
        SequenceNotFoundError: If sequence doesn't exist and auto_create=False
    """
    # Resolve org to ContentType + ID
    if org is not None:
        org_content_type = ContentType.objects.get_for_model(org)
        org_id = str(org.pk)
    else:
        org_content_type = None
        org_id = ''

    with transaction.atomic():
        try:
            # Lock row for update
            seq = Sequence.objects.select_for_update().get(
                scope=scope,
                org_content_type=org_content_type,
                org_id=org_id,
            )
        except Sequence.DoesNotExist:
            if not auto_create:
                org_display = org_id or 'global'
                raise SequenceNotFoundError(
                    f"Sequence '{scope}' not found for org '{org_display}'"
                )

            # Create and lock new sequence
            seq = Sequence.objects.create(
                scope=scope,
                org_content_type=org_content_type,
                org_id=org_id,
                prefix=prefix,
                pad_width=pad_width,
                include_year=include_year,
                current_value=0,
            )
            seq = Sequence.objects.select_for_update().get(pk=seq.pk)

        # Increment and save
        seq.current_value += 1
        seq.save(update_fields=['current_value', 'updated_at'])

        return seq.formatted_value
```

## Test Models

### tests/models.py

```python
from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'
```

## Test Cases (40 tests)

### TestSequenceModel (16 tests)
1. `test_sequence_has_scope_field` - Scope stored correctly
2. `test_sequence_has_org_field` - Org property works
3. `test_sequence_org_nullable_for_global` - Global sequences allowed
4. `test_sequence_has_prefix_field` - Prefix stored correctly
5. `test_sequence_has_current_value_field` - Current value stored
6. `test_sequence_has_pad_width_field` - Default is 6
7. `test_sequence_custom_pad_width` - Custom padding works
8. `test_sequence_has_include_year_field` - Default is True
9. `test_sequence_include_year_can_be_false` - Can disable year
10. `test_sequence_unique_scope_org` - Unique constraint works
11. `test_sequence_same_scope_different_orgs_allowed` - Different orgs OK
12. `test_formatted_value_with_year` - "INV-2026-000123"
13. `test_formatted_value_without_year` - "TKT-000042"
14. `test_formatted_value_respects_pad_width` - Custom padding
15. `test_formatted_value_large_number_exceeds_padding` - No truncation
16. `test_sequence_str_representation` - Useful __str__

### TestNextSequenceService (9 tests)
1. `test_next_sequence_increments_value` - Sequential values
2. `test_next_sequence_returns_formatted_value` - Correct format
3. `test_next_sequence_creates_sequence_if_not_exists` - Auto-create
4. `test_next_sequence_auto_create_disabled_raises` - SequenceNotFoundError
5. `test_next_sequence_without_year` - Year disabled works
6. `test_next_sequence_global_without_org` - Global sequences
7. `test_next_sequence_is_atomic` - Transaction safety
8. `test_next_sequence_custom_pad_width_on_create` - Custom padding
9. `test_next_sequence_returns_incrementing_values` - 1, 2, 3...

### TestOrgIsolation (3 tests)
1. `test_sequences_isolated_by_org` - Each org has own counter
2. `test_global_sequence_separate_from_org_sequences` - Global separate
3. `test_different_scopes_independent` - Different scopes independent

### TestGapPolicy (2 tests)
1. `test_gaps_allowed_by_default` - Gaps are expected
2. `test_sequence_never_goes_backward` - Only increases

### TestIntegration (7 tests)
1. `test_invoice_numbering_workflow` - Invoice use case
2. `test_multi_tenant_invoice_isolation` - Multi-tenant
3. `test_multiple_sequence_types_per_org` - Multiple sequences
4. `test_predefined_sequence_configuration` - Admin pre-config
5. `test_year_rollover_behavior` - Year in format
6. `test_sequence_for_django_model_integration` - In model.save()
7. `test_global_sequence_for_system_wide_numbering` - System-wide

### TestConcurrencySafety (3 tests)
1. `test_service_uses_atomic_transaction` - Uses atomic
2. `test_service_uses_select_for_update` - Uses locking
3. `test_sequence_increment_is_persistent` - Persisted immediately

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = ['Sequence', 'next_sequence', 'SequenceError', 'SequenceNotFoundError']

def __getattr__(name):
    if name == 'Sequence':
        from .models import Sequence
        return Sequence
    if name == 'next_sequence':
        from .services import next_sequence
        return next_sequence
    if name in ('SequenceError', 'SequenceNotFoundError'):
        from .exceptions import SequenceError, SequenceNotFoundError
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Atomic Operations**: `select_for_update()` prevents race conditions
2. **Multi-Tenant Isolation**: Each (scope, org) has independent counter
3. **Gaps Expected**: Transaction rollbacks can cause gaps
4. **Counter Only Increases**: Never decrements
5. **GenericFK for Org**: Supports any organization model
6. **Year in Format Only**: Counter continues across year boundary

## Usage Examples

```python
# Basic invoice numbering
invoice_number = next_sequence('invoice', org=my_org, prefix='INV-')
# Returns: "INV-2026-000001"

# Pre-configured sequence
Sequence.objects.create(
    scope='purchase_order',
    org=organization,
    prefix='PO-',
    current_value=1000,
    pad_width=8,
)
po_number = next_sequence('purchase_order', org=organization)
# Returns: "PO-2026-00001001"

# Global sequence
ticket = next_sequence('support_ticket', org=None, prefix='SUPP-', include_year=False)
# Returns: "SUPP-000001"
```

## Acceptance Criteria

- [ ] Sequence model with all fields
- [ ] next_sequence() with atomic locking
- [ ] Multi-tenant isolation working
- [ ] Global sequences supported
- [ ] SequenceNotFoundError for auto_create=False
- [ ] All 40 tests passing
- [ ] README with usage examples
