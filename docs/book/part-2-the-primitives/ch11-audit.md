# Chapter 11: Audit

> "The absence of evidence is not the evidence of absence—but in court, it might as well be."
>
> — A lawyer explaining why audit trails matter

---

In 2002, Arthur Andersen LLP became the first major accounting firm to be convicted of a crime. The charge: obstruction of justice for shredding documents related to Enron.

Arthur Andersen had been auditing companies for 89 years. They employed 85,000 people worldwide. Within a year of the conviction, they were gone—not because they cooked the books themselves, but because they destroyed the audit trail.

The firm had a document retention policy. Unfortunately, that policy was enforced most vigorously in the weeks after Enron's collapse became public. Thousands of emails were deleted. Thousands of paper documents were shredded. When the SEC came looking for evidence, the evidence was gone.

The lesson is not subtle: you don't just need to do the right thing. You need to be able to prove you did the right thing. An audit trail that can be edited or deleted is not an audit trail. It's a fiction.

## Why Systems Lie

Most software systems lie about their history. Not maliciously—they're simply not designed to remember.

When you update a record:
```python
customer.email = 'new@example.com'
customer.save()
```

The old email is gone. There's no record it ever existed. If someone asks "what was this customer's email last month?", you have no answer.

When you delete a record:
```python
invoice.delete()
```

The invoice is gone. Not archived, not marked deleted—gone. If an auditor asks to see all invoices from Q3, you can't produce what you destroyed.

This isn't a bug. Django's default behavior is to update in place and delete physically. The framework assumes you want efficiency, not history. But for any system that handles money, compliance, or liability, this assumption is catastrophically wrong.

## The Cost of Missing History

In 2017, Equifax disclosed a data breach affecting 147 million people. During the investigation, the company struggled to determine what data had been accessed because their logging was inadequate. The eventual settlement was $700 million.

The IRS requires businesses to retain financial records for at least 7 years. HIPAA requires healthcare records for 6 years. Sarbanes-Oxley requires public companies to retain audit workpapers for 7 years. If your system can't prove what happened during that period, you're in violation.

But compliance is just the legal minimum. The real cost is operational:

- **Debugging**: "Why does this account have a negative balance?" Without history, you're guessing.
- **Disputes**: "I never agreed to those terms." Without a signature trail, they might be right.
- **Support**: "What changed between yesterday and today?" Without logs, you can't help them.

## Append-Only: The Only Acceptable Pattern

An audit log has one rule: records can only be created, never modified or deleted.

```python
class AuditLog(models.Model):
    # ... fields ...

    def save(self, *args, **kwargs):
        if self.pk:
            raise ImmutableLogError("Audit logs cannot be modified")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLogError("Audit logs cannot be deleted")
```

This is enforced at the model level, not by policy. If someone calls `audit_entry.save()` on an existing entry, the system raises an exception. If someone calls `audit_entry.delete()`, same thing.

You can't accidentally delete audit logs. You can't "fix" incorrect entries. The only path forward is to create new entries that explain what happened.

## What to Capture

Every audit log entry needs:

**What changed:**
- `target`: The object that was modified (via GenericForeignKey)
- `action`: create, update, delete, view, or custom
- `old_values`: Field values before the change
- `new_values`: Field values after the change
- `changed_fields`: Which fields were modified

**Who did it:**
- `actor`: Foreign key to the user
- `actor_repr`: String representation of the actor at the time (in case the user is later deleted or renamed)

**When it happened:**
- `created_at`: System time when the log was recorded
- `effective_at`: Business time when the action actually occurred

**Why it happened:**
- `message`: Human-readable description
- `metadata`: Additional context (IP address, user agent, session ID)

## GenericFK for Any Target

Audit logs can be attached to any model. A document change, an invoice deletion, a user login—all use the same audit infrastructure.

```python
class AuditLog(models.Model):
    target_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    target_id = models.CharField(max_length=255)  # CharField for UUID support
    target = GenericForeignKey('target_content_type', 'target_id')
```

Query the history of any object:

```python
# All changes to a specific document
logs = AuditLog.objects.for_target(document)

# All deletes across the system
deletes = AuditLog.objects.by_action('delete')

# Everything a specific user did
user_actions = AuditLog.objects.by_actor(user)
```

## The Full Prompt

Here is the complete prompt to generate an audit log package. Copy this prompt, paste it into your AI assistant, and it will generate correct append-only audit primitives.

---

````markdown
# Prompt: Build django-audit-log

## Instruction

Create a Django package called `django-audit-log` that provides immutable audit
logging primitives for tracking changes to any model.

## Package Purpose

Provide append-only audit trail capabilities:
- AuditLog - Immutable log entry with GenericFK target
- log() - Function to create audit log entries
- log_event() - Function for custom event logging
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

## Key Behaviors

1. Immutability: Entries cannot be modified or deleted after creation
2. GenericFK Target: Attach audit logs to any model
3. Change Tracking: old_values, new_values, changed_fields
4. Actor Capture: Store user and string representation
5. Effective Dating: effective_at for backdating support

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
````

---

## Hands-On: Generate Your Audit Log Package

Copy the prompt above and paste it into your AI assistant. The AI will generate:

1. The complete package structure
2. Immutable AuditLog model with GenericFK
3. Service functions for all action types
4. QuerySet methods for filtering
5. 23 test cases covering all behaviors

After generation, run the tests:

```bash
cd packages/django-audit-log
pip install -e .
pytest tests/ -v
```

All 23 tests should pass.

### Exercise: Add Request Metadata Middleware

Create middleware that automatically captures request context:

```
Create Django middleware that adds audit context to every request:

1. AuditContextMiddleware that captures:
   - IP address (with X-Forwarded-For handling)
   - User agent
   - Session ID
   - Request path
   - Request method

2. Store in thread-local or context variable

3. Modify log() to automatically include this metadata if available

4. Ensure metadata is cleared after request completes
```

### Exercise: Reconstruct Object State

Use the audit log to reconstruct an object at a point in time:

```
Write a function reconstruct_state(target, as_of) that:

1. Finds the object's creation log
2. Applies all updates in order up to as_of timestamp
3. Returns a dictionary of field values at that moment

Handle edge cases:
- Object didn't exist at as_of
- Object was deleted before as_of
- No audit logs exist for object
```

## What AI Gets Wrong

Without explicit constraints, AI-generated audit logging typically:

1. **Allows updates** — Someone "fixes" a log entry. The correction destroys the original evidence.

2. **Allows deletes** — Logs can be purged, either intentionally or by accident. Arthur Andersen would be proud.

3. **No old_values capture** — Records that something changed, but not what it changed from.

4. **No actor snapshot** — Stores a foreign key to the user, but if the user is deleted, the actor is lost.

5. **Uses IntegerField for target_id** — Breaks with UUID primary keys.

6. **No effective_at** — Can't distinguish between when something happened and when it was logged.

7. **Stores only message** — A string description instead of structured before/after data. Useless for programmatic analysis.

The prompt above prevents all of these mistakes.

## Audit vs. Decisions vs. Transitions

These three primitives capture different types of historical data:

**Audit Log**: What changed in the system, when, and by whom. Low-level field changes. "The email field changed from X to Y."

**Decisions** (Chapter 10): Human choices with context. "The loan was approved because the credit score exceeded 650."

**Transitions** (Chapter 9): State changes in workflows. "The encounter moved from 'checked_in' to 'in_progress'."

All three are append-only. All three capture who and when. But they serve different purposes:

- Audit logs answer: "What changed?"
- Decisions answer: "Why was this choice made?"
- Transitions answer: "What stage is this process in?"

In a complete system, you might have all three for a single event. When a loan is approved:
- A Decision records the approval with context and reasoning
- An EncounterTransition moves the loan from "pending" to "approved"
- An AuditLog records that the status field changed from "pending" to "approved"

The redundancy is intentional. Each serves a different audience: auditors want the audit log, business analysts want decisions, operations teams want transitions.

## Why This Matters Later

The audit log is the system's memory:

- **Compliance**: Regulators ask for proof. The audit log provides it.

- **Debugging**: When something goes wrong, the audit log shows what led to the failure.

- **Disputes**: When a customer claims they didn't make a change, the audit log shows who did.

- **Recovery**: When you need to undo a mistake, the audit log shows what the original state was.

- **Analytics**: The audit log is a complete history of system activity—useful for understanding patterns.

Get auditing wrong, and you're flying blind. Get it right, and you have a permanent, tamper-proof record of everything that happened.

---

## Sources and References

1. **Arthur Andersen Conviction** — United States v. Arthur Andersen LLP, 544 U.S. 696 (2005). The Supreme Court ultimately overturned the conviction, but by then the firm had already collapsed.

2. **Equifax Settlement** — Federal Trade Commission. "Equifax Data Breach Settlement." July 2019. The $700 million settlement for inadequate data protection and logging.

3. **IRS Record Retention** — IRS Publication 583. "Starting a Business and Keeping Records." The 7-year retention requirement for tax records.

4. **HIPAA Requirements** — 45 CFR § 164.530(j). The 6-year retention requirement for HIPAA-related documentation.

5. **Sarbanes-Oxley Section 802** — 18 U.S.C. § 1519. Criminal penalties for altering, destroying, or falsifying records in federal investigations.

---

*Status: Complete*
