# Prompt: Rebuild django-decisioning

## Instruction

Create a Django package called `django-decisioning` that provides time semantics, idempotency patterns, and decision tracking primitives.

## Package Purpose

Provide infrastructure for time-aware operations and decision tracking:
- `TimeSemanticsMixin` - Add effective_at/recorded_at to any model
- `EffectiveDatedMixin` - Add valid_from/valid_to for temporal validity
- `IdempotencyKey` - Track idempotent operation status
- `@idempotent` decorator - Make functions idempotent
- `Decision` - Track decisions with GenericFK target
- QuerySets for temporal queries (as_of, current, etc.)

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel, BaseModel)
- django.contrib.contenttypes

## File Structure

```
packages/django-decisioning/
├── pyproject.toml
├── README.md
├── src/django_decisioning/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── mixins.py
│   ├── querysets.py
│   ├── decorators.py
│   ├── utils.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_models.py
    ├── test_mixins.py
    ├── test_querysets.py
    ├── test_decorators.py
    └── test_utils.py
```

## Exceptions Specification

### exceptions.py

```python
class DecisioningError(Exception):
    """Base exception for decisioning errors."""
    pass


class IdempotencyError(DecisioningError):
    """Base exception for idempotency errors."""
    pass


class OperationInFlightError(IdempotencyError):
    """Raised when operation is already in progress."""
    def __init__(self, key: str, started_at):
        self.key = key
        self.started_at = started_at
        super().__init__(
            f"Operation with key '{key}' is already in flight (started at {started_at})"
        )


class DuplicateOperationError(IdempotencyError):
    """Raised when operation was already completed."""
    def __init__(self, key: str, completed_at, result):
        self.key = key
        self.completed_at = completed_at
        self.result = result
        super().__init__(
            f"Operation with key '{key}' already completed at {completed_at}"
        )
```

## QuerySets Specification

### querysets.py

```python
from django.db import models
from django.utils import timezone


class EventAsOfQuerySet(models.QuerySet):
    """QuerySet for event-sourced models with effective_at/recorded_at."""

    def as_of(self, timestamp):
        """Get records effective as of a timestamp."""
        return self.filter(effective_at__lte=timestamp)

    def recorded_before(self, timestamp):
        """Get records recorded before a timestamp."""
        return self.filter(recorded_at__lte=timestamp)

    def recorded_after(self, timestamp):
        """Get records recorded after a timestamp."""
        return self.filter(recorded_at__gt=timestamp)

    def effective_between(self, start, end):
        """Get records effective within a range."""
        return self.filter(effective_at__gte=start, effective_at__lt=end)


class EffectiveDatedQuerySet(models.QuerySet):
    """QuerySet for models with valid_from/valid_to fields."""

    def current(self):
        """Get currently valid records."""
        return self.as_of(timezone.now())

    def as_of(self, timestamp):
        """Get records valid at a specific timestamp."""
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=timestamp)
        )

    def expired(self):
        """Get records that have expired."""
        now = timezone.now()
        return self.filter(valid_to__lte=now)

    def future(self):
        """Get records not yet valid."""
        now = timezone.now()
        return self.filter(valid_from__gt=now)

    def overlapping(self, start, end):
        """Get records that overlap with a time range."""
        return self.filter(
            valid_from__lt=end
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=start)
        )
```

## Mixins Specification

### mixins.py

```python
from django.db import models
from django.utils import timezone


class TimeSemanticsMixin(models.Model):
    """
    Mixin for event-sourced models with clear time semantics.

    effective_at: When the event actually happened (business time)
    recorded_at: When we recorded the event (system time)
    """
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When this event actually occurred (business time)"
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this record was created (system time)"
    )

    class Meta:
        abstract = True


class EffectiveDatedMixin(models.Model):
    """
    Mixin for models with temporal validity periods.

    valid_from: When this record becomes valid
    valid_to: When this record expires (null = indefinite)
    """
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text="When this record becomes valid"
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this record expires (null = indefinite)"
    )

    class Meta:
        abstract = True

    @property
    def is_active(self) -> bool:
        """Check if this record is currently valid."""
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_to and now >= self.valid_to:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        """Check if this record has expired."""
        if not self.valid_to:
            return False
        return timezone.now() >= self.valid_to

    @property
    def is_future(self) -> bool:
        """Check if this record is not yet valid."""
        return timezone.now() < self.valid_from
```

## Models Specification

### IdempotencyKey Model

```python
from django.db import models
from django_basemodels.models import UUIDModel

class IdempotencyStatus(models.TextChoices):
    IN_FLIGHT = 'in_flight', 'In Flight'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class IdempotencyKey(UUIDModel):
    """Track idempotent operation status."""
    key = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=IdempotencyStatus.choices,
        default=IdempotencyStatus.IN_FLIGHT
    )

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Result storage
    result_type = models.CharField(max_length=255, blank=True, default='')
    result_id = models.CharField(max_length=255, blank=True, default='')
    result_data = models.JSONField(default=dict, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True, default='')

    # Expiry for cleanup
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'django_decisioning'
        verbose_name = 'idempotency key'
        verbose_name_plural = 'idempotency keys'
        indexes = [
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['expires_at']),
        ]

    def mark_completed(self, result=None, result_type='', result_id=''):
        """Mark operation as completed."""
        from django.utils import timezone
        self.status = IdempotencyStatus.COMPLETED
        self.completed_at = timezone.now()
        if result:
            self.result_data = result if isinstance(result, dict) else {'value': result}
        self.result_type = result_type
        self.result_id = str(result_id) if result_id else ''
        self.save()

    def mark_failed(self, error_message: str):
        """Mark operation as failed."""
        from django.utils import timezone
        self.status = IdempotencyStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save()

    def __str__(self):
        return f"{self.key} ({self.status})"
```

### Decision Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django_basemodels.models import UUIDModel, BaseModel
from .mixins import TimeSemanticsMixin


class DecisionOutcome(models.TextChoices):
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    PENDING = 'pending', 'Pending'
    DEFERRED = 'deferred', 'Deferred'
    ESCALATED = 'escalated', 'Escalated'


class Decision(UUIDModel, BaseModel, TimeSemanticsMixin):
    """Track a decision made about a target entity."""

    # Target via GenericFK
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Decision details
    decision_type = models.CharField(max_length=100)
    outcome = models.CharField(
        max_length=20,
        choices=DecisionOutcome.choices,
        default=DecisionOutcome.PENDING
    )
    reason = models.TextField(blank=True, default='')

    # Decision maker
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decisions_made'
    )

    # Context and evidence
    context = models.JSONField(default=dict, blank=True)
    evidence = models.JSONField(default=dict, blank=True)

    # Linked idempotency key (optional)
    idempotency_key = models.ForeignKey(
        IdempotencyKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decisions'
    )

    class Meta:
        app_label = 'django_decisioning'
        verbose_name = 'decision'
        verbose_name_plural = 'decisions'
        ordering = ['-effective_at', '-recorded_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['decision_type']),
            models.Index(fields=['outcome']),
        ]

    def save(self, *args, **kwargs):
        self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.decision_type}: {self.outcome}"
```

## Decorators Specification

### decorators.py

```python
import functools
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import IdempotencyKey, IdempotencyStatus
from .exceptions import OperationInFlightError, DuplicateOperationError


def idempotent(
    key_func=None,
    expires_in: timedelta = None,
    raise_on_duplicate: bool = False
):
    """
    Decorator to make a function idempotent.

    Args:
        key_func: Function to generate idempotency key from args/kwargs.
                  If None, uses first positional arg as key.
        expires_in: How long until the idempotency key expires.
        raise_on_duplicate: If True, raise error on duplicate. If False, return cached result.

    Usage:
        @idempotent(key_func=lambda order_id, **kw: f"process_order:{order_id}")
        def process_order(order_id, items):
            # This will only run once per order_id
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate idempotency key
            if key_func:
                key = key_func(*args, **kwargs)
            elif args:
                key = f"{func.__module__}.{func.__name__}:{args[0]}"
            else:
                raise ValueError("Cannot generate idempotency key - provide key_func or positional arg")

            # Check for existing operation
            try:
                existing = IdempotencyKey.objects.get(key=key)

                if existing.status == IdempotencyStatus.IN_FLIGHT:
                    raise OperationInFlightError(key, existing.started_at)

                if existing.status == IdempotencyStatus.COMPLETED:
                    if raise_on_duplicate:
                        raise DuplicateOperationError(
                            key, existing.completed_at, existing.result_data
                        )
                    # Return cached result
                    return existing.result_data.get('value', existing.result_data)

                # Failed - allow retry by falling through to create new
                existing.delete()

            except IdempotencyKey.DoesNotExist:
                pass

            # Create new idempotency key
            expires_at = None
            if expires_in:
                expires_at = timezone.now() + expires_in

            idem_key = IdempotencyKey.objects.create(
                key=key,
                status=IdempotencyStatus.IN_FLIGHT,
                expires_at=expires_at
            )

            try:
                with transaction.atomic():
                    result = func(*args, **kwargs)

                    # Store result
                    result_type = ''
                    result_id = ''
                    if hasattr(result, '__class__'):
                        result_type = f"{result.__class__.__module__}.{result.__class__.__name__}"
                    if hasattr(result, 'pk'):
                        result_id = str(result.pk)

                    idem_key.mark_completed(
                        result={'value': result} if not isinstance(result, dict) else result,
                        result_type=result_type,
                        result_id=result_id
                    )

                    return result

            except Exception as e:
                idem_key.mark_failed(str(e))
                raise

        return wrapper
    return decorator
```

## Utils Specification

### utils.py

```python
from django.contrib.contenttypes.models import ContentType


def get_target_ref(obj):
    """
    Get a serializable reference to any Django model instance.

    Args:
        obj: Django model instance

    Returns:
        Dict with content_type and object_id
    """
    content_type = ContentType.objects.get_for_model(obj)
    return {
        'content_type_id': content_type.id,
        'app_label': content_type.app_label,
        'model': content_type.model,
        'object_id': str(obj.pk)
    }


def resolve_target_ref(ref):
    """
    Resolve a target reference back to a model instance.

    Args:
        ref: Dict from get_target_ref()

    Returns:
        Django model instance or None
    """
    try:
        if 'content_type_id' in ref:
            content_type = ContentType.objects.get(id=ref['content_type_id'])
        else:
            content_type = ContentType.objects.get(
                app_label=ref['app_label'],
                model=ref['model']
            )
        return content_type.get_object_for_this_type(pk=ref['object_id'])
    except Exception:
        return None
```

## Test Cases (78 tests)

### IdempotencyKey Model Tests (12 tests)
1. `test_idempotency_key_creation` - Create with required fields
2. `test_idempotency_key_has_uuid_pk` - UUID primary key
3. `test_idempotency_key_unique_key` - Unique constraint
4. `test_idempotency_key_status_choices` - All status values work
5. `test_idempotency_key_started_at_auto` - Auto-set on create
6. `test_idempotency_key_mark_completed` - Transition to completed
7. `test_idempotency_key_mark_completed_with_result` - Store result
8. `test_idempotency_key_mark_failed` - Transition to failed
9. `test_idempotency_key_result_data_json` - JSONField works
10. `test_idempotency_key_expires_at_optional` - Nullable
11. `test_idempotency_key_str_representation` - String format
12. `test_idempotency_key_indexes` - Indexes exist

### Decision Model Tests (10 tests)
1. `test_decision_creation` - Create with required fields
2. `test_decision_has_uuid_pk` - UUID primary key
3. `test_decision_has_time_semantics` - effective_at, recorded_at
4. `test_decision_target_generic_fk` - GenericFK works
5. `test_decision_outcome_choices` - All outcomes work
6. `test_decision_decided_by_optional` - Nullable
7. `test_decision_context_json` - JSONField works
8. `test_decision_evidence_json` - JSONField works
9. `test_decision_soft_delete` - Soft delete works
10. `test_decision_ordering` - Ordered by effective_at desc

### TimeSemanticsMixin Tests (8 tests)
1. `test_effective_at_defaults_to_now` - Default value
2. `test_effective_at_can_be_backdated` - Custom value
3. `test_recorded_at_auto_set` - Auto on create
4. `test_recorded_at_not_editable` - Cannot change
5. `test_effective_before_recorded` - Backdating works
6. `test_effective_equals_recorded` - Same time works
7. `test_mixin_is_abstract` - Cannot instantiate
8. `test_multiple_inheritance` - Works with other mixins

### EffectiveDatedMixin Tests (10 tests)
1. `test_valid_from_defaults_to_now` - Default value
2. `test_valid_to_nullable` - Can be indefinite
3. `test_is_active_when_valid` - True for current
4. `test_is_active_false_when_expired` - False for expired
5. `test_is_active_false_when_future` - False for future
6. `test_is_expired_when_past_valid_to` - Expired check
7. `test_is_expired_false_when_indefinite` - No end date
8. `test_is_future_when_valid_from_ahead` - Future check
9. `test_is_future_false_when_started` - Not future
10. `test_mixin_is_abstract` - Cannot instantiate

### EventAsOfQuerySet Tests (8 tests)
1. `test_as_of_returns_effective_before` - Filter by effective_at
2. `test_as_of_excludes_future` - Future excluded
3. `test_recorded_before_filters` - Filter by recorded_at
4. `test_recorded_after_filters` - Filter by recorded_at
5. `test_effective_between_range` - Range query
6. `test_as_of_empty_when_none_exist` - Empty result
7. `test_as_of_multiple_records` - Multiple matches
8. `test_chained_queries` - Methods chainable

### EffectiveDatedQuerySet Tests (10 tests)
1. `test_current_returns_active` - Currently valid only
2. `test_current_excludes_expired` - Expired excluded
3. `test_current_excludes_future` - Future excluded
4. `test_as_of_historical` - Historical query
5. `test_expired_returns_only_expired` - Expired filter
6. `test_future_returns_only_future` - Future filter
7. `test_overlapping_finds_intersecting` - Overlap detection
8. `test_overlapping_excludes_non_intersecting` - Non-overlap excluded
9. `test_current_with_indefinite` - Null valid_to
10. `test_chained_queries` - Methods chainable

### @idempotent Decorator Tests (12 tests)
1. `test_first_call_executes_function` - Function runs
2. `test_second_call_returns_cached` - Cached result
3. `test_in_flight_raises_error` - Concurrent protection
4. `test_failed_allows_retry` - Retry after failure
5. `test_custom_key_func` - Custom key generation
6. `test_default_key_from_args` - Auto key from args
7. `test_raise_on_duplicate_true` - Raises instead of cache
8. `test_expires_in_sets_expiry` - Expiry timestamp
9. `test_result_stored_in_key` - Result persistence
10. `test_exception_marks_failed` - Error handling
11. `test_atomic_transaction` - Transaction wrapper
12. `test_model_result_stored` - Model PK stored

### Utils Tests (8 tests)
1. `test_get_target_ref_returns_dict` - Returns reference
2. `test_get_target_ref_includes_content_type` - Has CT info
3. `test_get_target_ref_includes_object_id` - Has object ID
4. `test_resolve_target_ref_returns_object` - Resolves to instance
5. `test_resolve_target_ref_by_id` - Resolve by CT ID
6. `test_resolve_target_ref_by_label` - Resolve by app/model
7. `test_resolve_target_ref_returns_none_missing` - Missing object
8. `test_roundtrip_get_resolve` - Full roundtrip

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    # Models
    'IdempotencyKey',
    'IdempotencyStatus',
    'Decision',
    'DecisionOutcome',
    # Mixins
    'TimeSemanticsMixin',
    'EffectiveDatedMixin',
    # QuerySets
    'EventAsOfQuerySet',
    'EffectiveDatedQuerySet',
    # Decorators
    'idempotent',
    # Utils
    'get_target_ref',
    'resolve_target_ref',
    # Exceptions
    'DecisioningError',
    'IdempotencyError',
    'OperationInFlightError',
    'DuplicateOperationError',
]

def __getattr__(name):
    if name in ('IdempotencyKey', 'IdempotencyStatus', 'Decision', 'DecisionOutcome'):
        from .models import IdempotencyKey, IdempotencyStatus, Decision, DecisionOutcome
        return locals()[name]
    if name in ('TimeSemanticsMixin', 'EffectiveDatedMixin'):
        from .mixins import TimeSemanticsMixin, EffectiveDatedMixin
        return locals()[name]
    if name in ('EventAsOfQuerySet', 'EffectiveDatedQuerySet'):
        from .querysets import EventAsOfQuerySet, EffectiveDatedQuerySet
        return locals()[name]
    if name == 'idempotent':
        from .decorators import idempotent
        return idempotent
    if name in ('get_target_ref', 'resolve_target_ref'):
        from .utils import get_target_ref, resolve_target_ref
        return locals()[name]
    if name in ('DecisioningError', 'IdempotencyError', 'OperationInFlightError', 'DuplicateOperationError'):
        from .exceptions import DecisioningError, IdempotencyError, OperationInFlightError, DuplicateOperationError
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Time Semantics**: effective_at (business time) vs recorded_at (system time)
2. **Effective Dating**: valid_from/valid_to for temporal validity
3. **Idempotency**: Prevent duplicate operations with key tracking
4. **Decision Tracking**: Record decisions about any entity
5. **Temporal Queries**: as_of(), current(), expired(), future()

## Usage Examples

```python
from datetime import timedelta
from django_decisioning import (
    TimeSemanticsMixin, EffectiveDatedMixin,
    EventAsOfQuerySet, EffectiveDatedQuerySet,
    idempotent, Decision, DecisionOutcome,
    get_target_ref, resolve_target_ref
)

# Model with time semantics
class PaymentEvent(TimeSemanticsMixin, models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    objects = EventAsOfQuerySet.as_manager()

# Model with effective dating
class PriceOverride(EffectiveDatedMixin, models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    objects = EffectiveDatedQuerySet.as_manager()

# Idempotent function
@idempotent(
    key_func=lambda order_id, **kw: f"process_order:{order_id}",
    expires_in=timedelta(hours=24)
)
def process_order(order_id, items):
    # Only runs once per order_id
    order = Order.objects.get(id=order_id)
    order.process(items)
    return order

# Record a decision
decision = Decision.objects.create(
    target=loan_application,
    decision_type='credit_approval',
    outcome=DecisionOutcome.APPROVED,
    reason='Credit score meets threshold',
    decided_by=request.user,
    context={'credit_score': 720},
    evidence={'report_id': 'CR-123'}
)

# Query by time
events = PaymentEvent.objects.as_of(last_month)
active_prices = PriceOverride.objects.current()
historical = PriceOverride.objects.as_of(audit_date)
```

## Acceptance Criteria

- [ ] TimeSemanticsMixin with effective_at/recorded_at
- [ ] EffectiveDatedMixin with valid_from/valid_to
- [ ] IdempotencyKey model with status tracking
- [ ] @idempotent decorator with key generation
- [ ] Decision model with GenericFK target
- [ ] EventAsOfQuerySet and EffectiveDatedQuerySet
- [ ] All 78 tests passing
- [ ] README with usage examples
