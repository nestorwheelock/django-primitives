# Prompt: Rebuild django-audit-log

## Instruction

Create a Django package called `django-audit-log` that provides immutable audit logging primitives for tracking changes to any model.

## Package Purpose

Provide append-only audit trail capabilities:
- `AuditLog` - Immutable log entry with GenericFK target
- `log()` - Function to create audit log entries
- `log_event()` - Function for custom event logging
- AuditLogQuerySet for filtering and querying
- Immutability enforcement (no updates/deletes)

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel)
- django.contrib.contenttypes
- django.contrib.auth

## File Structure

```
packages/django-audit-log/
├── pyproject.toml
├── README.md
├── src/django_audit_log/
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
    ├── test_models.py
    └── test_services.py
```

## Exceptions Specification

### exceptions.py

```python
class AuditLogError(Exception):
    """Base exception for audit log errors."""
    pass


class ImmutableLogError(AuditLogError):
    """Raised when attempting to modify an immutable audit log entry."""
    def __init__(self, message="Audit log entries are immutable and cannot be modified"):
        super().__init__(message)
```

## Models Specification

### AuditLog Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django_basemodels.models import UUIDModel
from .exceptions import ImmutableLogError


class AuditAction(models.TextChoices):
    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    VIEW = 'view', 'View'
    CUSTOM = 'custom', 'Custom'


class AuditLogQuerySet(models.QuerySet):
    """QuerySet for audit log queries."""

    def for_target(self, target):
        """Get audit logs for a specific target object."""
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk)
        )

    def by_action(self, action):
        """Filter by action type."""
        return self.filter(action=action)

    def by_actor(self, actor):
        """Filter by the user who performed the action."""
        return self.filter(actor=actor)

    def in_range(self, start, end):
        """Filter by timestamp range."""
        return self.filter(created_at__gte=start, created_at__lt=end)

    def recent(self, limit=100):
        """Get the most recent entries."""
        return self.order_by('-created_at')[:limit]

    def as_of(self, timestamp):
        """Get entries up to a specific timestamp."""
        return self.filter(created_at__lte=timestamp)


class AuditLog(UUIDModel):
    """
    Immutable audit log entry.

    Once created, entries cannot be modified or deleted.
    """

    # Target via GenericFK (the object being audited)
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='+'
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Action
    action = models.CharField(
        max_length=20,
        choices=AuditAction.choices,
        db_index=True
    )
    event_type = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Custom event type for action=custom"
    )

    # Actor (who performed the action)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    actor_repr = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="String representation of actor at time of action"
    )

    # Change data
    old_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field values before change"
    )
    new_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field values after change"
    )
    changed_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="List of field names that changed"
    )

    # Context
    message = models.TextField(
        blank=True,
        default='',
        help_text="Human-readable description of the action"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context (IP, user agent, etc)"
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the action actually occurred (for backdating)"
    )

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        app_label = 'django_audit_log'
        verbose_name = 'audit log'
        verbose_name_plural = 'audit logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['actor', 'created_at']),
        ]

    def save(self, *args, **kwargs):
        # Enforce immutability
        if self.pk:
            raise ImmutableLogError()

        # Ensure target_id is string
        self.target_id = str(self.target_id)

        # Capture actor representation
        if self.actor and not self.actor_repr:
            self.actor_repr = str(self.actor)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLogError("Audit log entries cannot be deleted")

    def __str__(self):
        action_str = self.event_type if self.action == 'custom' else self.action
        return f"{action_str} on {self.target_content_type.model}:{self.target_id}"
```

## Services Specification

### services.py

```python
from typing import Any, Dict, List, Optional
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from .models import AuditLog, AuditAction


def log(
    target,
    action: str,
    actor=None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    changed_fields: Optional[List[str]] = None,
    message: str = '',
    metadata: Optional[Dict[str, Any]] = None,
    effective_at=None,
) -> AuditLog:
    """
    Create an audit log entry for a model change.

    Args:
        target: The model instance being audited
        action: One of 'create', 'update', 'delete', 'view', 'custom'
        actor: User who performed the action (optional)
        old_values: Dictionary of field values before change
        new_values: Dictionary of field values after change
        changed_fields: List of field names that changed
        message: Human-readable description
        metadata: Additional context (IP, user agent, etc)
        effective_at: When the action actually occurred (for backdating)

    Returns:
        AuditLog instance
    """
    return AuditLog.objects.create(
        target=target,
        action=action,
        actor=actor,
        old_values=old_values or {},
        new_values=new_values or {},
        changed_fields=changed_fields or [],
        message=message,
        metadata=metadata or {},
        effective_at=effective_at or timezone.now(),
    )


def log_create(target, actor=None, message: str = '', metadata: Optional[Dict] = None) -> AuditLog:
    """
    Log a create action.

    Args:
        target: The created model instance
        actor: User who created it
        message: Optional description
        metadata: Additional context

    Returns:
        AuditLog instance
    """
    # Capture all field values as new_values
    new_values = {}
    for field in target._meta.fields:
        if field.name in ('id', 'pk'):
            continue
        value = getattr(target, field.name)
        new_values[field.name] = _serialize_value(value)

    return log(
        target=target,
        action=AuditAction.CREATE,
        actor=actor,
        new_values=new_values,
        changed_fields=list(new_values.keys()),
        message=message or f"Created {target._meta.model_name}",
        metadata=metadata,
    )


def log_update(
    target,
    old_values: Dict[str, Any],
    actor=None,
    message: str = '',
    metadata: Optional[Dict] = None
) -> AuditLog:
    """
    Log an update action.

    Args:
        target: The updated model instance
        old_values: Field values before the update
        actor: User who made the update
        message: Optional description
        metadata: Additional context

    Returns:
        AuditLog instance
    """
    # Calculate changed fields and new values
    new_values = {}
    changed_fields = []

    for field_name, old_value in old_values.items():
        current_value = getattr(target, field_name, None)
        new_value = _serialize_value(current_value)

        if _serialize_value(old_value) != new_value:
            changed_fields.append(field_name)
            new_values[field_name] = new_value

    return log(
        target=target,
        action=AuditAction.UPDATE,
        actor=actor,
        old_values={k: _serialize_value(v) for k, v in old_values.items()},
        new_values=new_values,
        changed_fields=changed_fields,
        message=message or f"Updated {target._meta.model_name}",
        metadata=metadata,
    )


def log_delete(target, actor=None, message: str = '', metadata: Optional[Dict] = None) -> AuditLog:
    """
    Log a delete action.

    Args:
        target: The model instance being deleted
        actor: User who deleted it
        message: Optional description
        metadata: Additional context

    Returns:
        AuditLog instance
    """
    # Capture all field values as old_values
    old_values = {}
    for field in target._meta.fields:
        if field.name in ('id', 'pk'):
            continue
        value = getattr(target, field.name)
        old_values[field.name] = _serialize_value(value)

    return log(
        target=target,
        action=AuditAction.DELETE,
        actor=actor,
        old_values=old_values,
        message=message or f"Deleted {target._meta.model_name}",
        metadata=metadata,
    )


def log_event(
    target,
    event_type: str,
    actor=None,
    message: str = '',
    metadata: Optional[Dict] = None,
    effective_at=None,
) -> AuditLog:
    """
    Log a custom event.

    Args:
        target: The model instance the event relates to
        event_type: Custom event type identifier
        actor: User who triggered the event
        message: Human-readable description
        metadata: Additional context
        effective_at: When the event occurred

    Returns:
        AuditLog instance
    """
    return log(
        target=target,
        action=AuditAction.CUSTOM,
        actor=actor,
        message=message or event_type,
        metadata=metadata or {},
        effective_at=effective_at,
    )


def _serialize_value(value) -> Any:
    """Serialize a value for JSON storage."""
    if value is None:
        return None
    if hasattr(value, 'pk'):
        return str(value.pk)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)
```

## Test Models

### tests/models.py

```python
from django.db import models

class Document(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    status = models.CharField(max_length=50, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'tests'
```

## Test Cases (23 tests)

### AuditLog Model Tests (10 tests)
1. `test_audit_log_creation` - Create with required fields
2. `test_audit_log_has_uuid_pk` - UUID primary key
3. `test_audit_log_target_generic_fk` - GenericFK works
4. `test_audit_log_action_choices` - All action types work
5. `test_audit_log_immutable_save` - Cannot update after create
6. `test_audit_log_immutable_delete` - Cannot delete
7. `test_audit_log_actor_optional` - Actor is nullable
8. `test_audit_log_actor_repr_captured` - String representation saved
9. `test_audit_log_ordering` - Ordered by created_at desc
10. `test_audit_log_str_representation` - String format

### AuditLogQuerySet Tests (6 tests)
1. `test_for_target_filters_by_object` - Filters to specific object
2. `test_by_action_filters` - Filters by action type
3. `test_by_actor_filters` - Filters by user
4. `test_in_range_filters` - Date range filter
5. `test_recent_limits_results` - Limited recent entries
6. `test_as_of_filters_by_timestamp` - Historical query

### Service Function Tests (7 tests)
1. `test_log_creates_entry` - Basic log() works
2. `test_log_create_captures_values` - log_create() captures fields
3. `test_log_update_calculates_diff` - log_update() finds changes
4. `test_log_update_tracks_changed_fields` - Changed fields list
5. `test_log_delete_captures_old_values` - log_delete() captures fields
6. `test_log_event_custom_type` - log_event() works
7. `test_log_with_metadata` - Metadata stored

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    'AuditLog',
    'AuditAction',
    'log',
    'log_create',
    'log_update',
    'log_delete',
    'log_event',
    'AuditLogError',
    'ImmutableLogError',
]

def __getattr__(name):
    if name in ('AuditLog', 'AuditAction'):
        from .models import AuditLog, AuditAction
        return locals()[name]
    if name in ('log', 'log_create', 'log_update', 'log_delete', 'log_event'):
        from .services import log, log_create, log_update, log_delete, log_event
        return locals()[name]
    if name in ('AuditLogError', 'ImmutableLogError'):
        from .exceptions import AuditLogError, ImmutableLogError
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Immutability**: Entries cannot be modified or deleted after creation
2. **GenericFK Target**: Attach audit logs to any model
3. **Change Tracking**: old_values, new_values, changed_fields
4. **Actor Capture**: Store user and string representation
5. **Effective Dating**: effective_at for backdating support

## Usage Examples

```python
from django_audit_log import (
    AuditLog, log, log_create, log_update, log_delete, log_event
)

# Log a create
document = Document.objects.create(title='Report', content='...')
log_create(document, actor=request.user)

# Log an update
old_values = {'title': document.title, 'status': document.status}
document.title = 'Updated Report'
document.status = 'published'
document.save()
log_update(document, old_values, actor=request.user)

# Log a delete
log_delete(document, actor=request.user)
document.delete()

# Log a custom event
log_event(
    target=document,
    event_type='downloaded',
    actor=request.user,
    message='User downloaded the document',
    metadata={'ip': '192.168.1.1', 'format': 'pdf'}
)

# Query audit logs
logs = AuditLog.objects.for_target(document)
create_logs = AuditLog.objects.by_action('create')
user_logs = AuditLog.objects.by_actor(request.user)
recent = AuditLog.objects.recent(limit=50)
```

## Acceptance Criteria

- [ ] AuditLog model with GenericFK target
- [ ] Immutability enforcement (no save/delete after create)
- [ ] log(), log_create(), log_update(), log_delete(), log_event()
- [ ] AuditLogQuerySet with filtering methods
- [ ] Change tracking (old_values, new_values, changed_fields)
- [ ] All 23 tests passing
- [ ] README with usage examples
