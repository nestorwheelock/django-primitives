# Architecture: django-audit-log

**Status:** Stable / v0.1.0
**Author:** Nestor Wheelock
**License:** Proprietary

Generic, B2B-grade audit logging for Django applications. Zero domain assumptions.

---

## What This Package Is For

Answering the question: **"Who did what, when, and where?"**

Use cases:
- Compliance auditing (HIPAA, GDPR, SOX, PCI-DSS)
- Security incident investigation
- User activity tracking
- Change history for sensitive records
- Login/logout monitoring

---

## What This Package Is NOT For

- **Not an analytics event bus** - Don't log page views for analytics here
- **Not a changelog** - Use django-reversion for full object history
- **Not a message queue** - Don't use for async job tracking
- **Not for high-frequency events** - Rate limit noisy actions

---

## Design Principles

1. **Append-only** - Audit logs are immutable. No updates, no deletes.
2. **Zero domain assumptions** - Works with any Django project
3. **Actor as User** - v0.1.0 tracks auth.User, not Party (keeps dependency minimal)
4. **String snapshots** - Actor display and object repr are captured at log time
5. **JSON flexibility** - Changes and metadata are JSON fields for extensibility

---

## Data Model

```
AuditLog
├── id (UUID)
├── created_at (auto timestamp)
├── actor_user (FK to AUTH_USER_MODEL, nullable)
├── actor_display (string snapshot)
├── action (string: create/update/delete/view/login/etc.)
├── model_label (string: "app.model")
├── object_id (string: PK as string)
├── object_repr (string snapshot)
├── changes (JSON: {"field": {"old": x, "new": y}})
├── ip_address (GenericIPAddressField)
├── user_agent (string)
├── request_id (string for correlation)
├── trace_id (string for distributed tracing)
├── metadata (JSON for anything else)
├── sensitivity (normal/high/critical)
└── is_system (bool)
```

---

## Public API

The package exposes two functions. This is the entire public interface:

```python
from django_audit_log import log, log_event

# Log a model operation
log(
    action='create',           # Required: what happened
    obj=my_instance,           # Optional: extracts label/id/repr automatically
    actor=request.user,        # Optional: who did it
    request=request,           # Optional: extracts IP/UA
    changes={'field': {'old': 'a', 'new': 'b'}},  # Optional
    metadata={'reason': 'User requested'},         # Optional
    sensitivity='high',        # Optional: normal/high/critical
)

# Log a non-model event (login, permission denied, etc.)
log_event(
    action='login',
    actor=user,
    metadata={'method': 'oauth', 'provider': 'google'},
)
```

### API Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | str | Yes | What happened (create, update, delete, view, login, etc.) |
| `obj` | Model | No | Django model instance (extracts label/id/repr) |
| `obj_label` | str | No | Model label if obj not provided ("app.model") |
| `obj_id` | str | No | Object PK if obj not provided |
| `obj_repr` | str | No | Object string repr if obj not provided |
| `actor` | User | No | User who performed action |
| `actor_display` | str | No | Actor display name (defaults to email/username) |
| `request` | HttpRequest | No | HTTP request for IP/UA extraction |
| `changes` | dict | No | Field changes: {"field": {"old": x, "new": y}} |
| `metadata` | dict | No | Additional context |
| `sensitivity` | str | No | normal, high, or critical (default: normal) |
| `is_system` | bool | No | True if system action, not user (default: False) |
| `request_id` | str | No | Request correlation ID |
| `trace_id` | str | No | Distributed trace ID |

---

## Installation

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_audit_log',
]

# Run migrations
# python manage.py migrate django_audit_log
```

### Optional: Middleware

Add middleware to automatically capture request context:

```python
MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_audit_log.middleware.AuditContextMiddleware',  # After auth
    ...
]
```

---

## Integration Patterns

### Pattern 1: Service Layer (Recommended)

Call `log()` in your service functions:

```python
# services.py
from django_audit_log import log

def update_customer(customer, data, actor, request=None):
    old_email = customer.email
    customer.email = data['email']
    customer.save()

    log(
        action='update',
        obj=customer,
        actor=actor,
        request=request,
        changes={'email': {'old': old_email, 'new': customer.email}},
    )
    return customer
```

### Pattern 2: View Layer

Log in views when service layer isn't practical:

```python
# views.py
from django_audit_log import log

class CustomerUpdateView(UpdateView):
    def form_valid(self, form):
        response = super().form_valid(form)
        log(
            action='update',
            obj=self.object,
            actor=self.request.user,
            request=self.request,
        )
        return response
```

### Pattern 3: Signal Handlers (Use Sparingly)

Automatic logging via signals - noisy, use only when needed:

```python
# signals.py
from django.db.models.signals import post_save
from django_audit_log import log

def audit_customer_save(sender, instance, created, **kwargs):
    log(
        action='create' if created else 'update',
        obj=instance,
        is_system=True,  # No user context in signals
    )

post_save.connect(audit_customer_save, sender=Customer)
```

---

## Known Gotchas (READ THIS)

### 1. Audit Logs Are Immutable

**Problem:** Trying to update or delete an audit log raises an error.

```python
log = AuditLog.objects.first()
log.action = 'view'
log.save()  # ValueError: Audit logs are immutable

log.delete()  # ValueError: Audit logs are immutable
```

**Why:** Audit logs are append-only by design. This is a feature, not a bug.

**Solution:** If you need to annotate/correct, create a new log entry with `action='correction'`.

### 2. No Soft Delete

**Problem:** AuditLog doesn't inherit from BaseModel's soft delete.

**Why:** Audit logs must be permanent for compliance. Soft delete would defeat the purpose.

**Solution:** If you need to "hide" logs, add a separate `is_visible` field in your application layer, but the underlying log stays.

### 3. Actor Display is a Snapshot

**Problem:** `actor_display` shows the user's email at log time, even if they change it later.

```python
user.email = 'old@example.com'
log(action='create', obj=doc, actor=user)
# actor_display = 'old@example.com'

user.email = 'new@example.com'
user.save()
# Log still shows 'old@example.com'
```

**Why:** This is intentional. Audit trails must reflect state at the time of action.

**Solution:** This is correct behavior. Don't "fix" it.

### 4. Changes Dict Format

**Problem:** Changes field expects specific format.

```python
# WRONG
changes={'email': 'new@example.com'}

# CORRECT
changes={'email': {'old': 'old@example.com', 'new': 'new@example.com'}}
```

**Solution:** Always use `{"field": {"old": x, "new": y}}` format.

### 5. Sensitivity Doesn't Enforce Access Control

**Problem:** Setting `sensitivity='critical'` doesn't hide the log.

**Why:** This package provides classification, not access control.

**Solution:** Implement access control in your views:

```python
def audit_log_list(request):
    logs = AuditLog.objects.all()
    if not request.user.is_superuser:
        logs = logs.exclude(sensitivity='critical')
    return logs
```

### 6. No Automatic Change Tracking

**Problem:** You must manually construct the changes dict.

**Why:** Automatic dirty tracking adds complexity and magic. Explicit is better.

**Solution:** Track changes in your service layer:

```python
def update_customer(customer, data, actor):
    changes = {}
    for field, new_value in data.items():
        old_value = getattr(customer, field)
        if old_value != new_value:
            changes[field] = {'old': old_value, 'new': new_value}
            setattr(customer, field, new_value)
    customer.save()
    log(action='update', obj=customer, actor=actor, changes=changes)
```

### 7. Request Context Requires Middleware

**Problem:** IP/UA not captured without middleware.

```python
log(action='view', obj=doc, actor=user)
# ip_address = None, user_agent = ''
```

**Solution:** Either pass `request=request` explicitly, or add the middleware.

### 8. High Volume Can Hurt Performance

**Problem:** Logging every action creates many database writes.

**Solution:**
- Don't log high-frequency read operations
- Consider async logging for high-volume systems
- Archive old logs to cold storage

---

## Database Indexes

The model includes indexes for common query patterns:

| Fields | Use Case |
|--------|----------|
| `created_at` | Time-based queries |
| `actor_user, created_at` | "What did this user do?" |
| `model_label, created_at` | "What happened to this model type?" |
| `action, created_at` | "Show all deletes" |
| `object_id, model_label` | "History for this specific object" |

---

## Querying Examples

```python
from django_audit_log.models import AuditLog
from datetime import timedelta
from django.utils import timezone

# All actions by a user
AuditLog.objects.filter(actor_user=user)

# All changes to a specific object
AuditLog.objects.filter(
    model_label='customers.Customer',
    object_id=str(customer.pk),
)

# All deletes in the last 24 hours
AuditLog.objects.filter(
    action='delete',
    created_at__gte=timezone.now() - timedelta(hours=24),
)

# High sensitivity actions
AuditLog.objects.filter(sensitivity__in=['high', 'critical'])

# Login failures (assuming you log them)
AuditLog.objects.filter(
    action='login_failed',
    created_at__gte=timezone.now() - timedelta(hours=1),
).values('ip_address').annotate(count=Count('id'))
```

---

## Extending

### Custom Actions

Actions are just strings. Define your own:

```python
log(action='approve', obj=invoice, actor=manager)
log(action='export_pdf', obj=report, actor=user)
log(action='bulk_delete', metadata={'count': 150, 'model': 'Order'})
```

### Metadata Schema

Metadata is freeform JSON. Establish conventions:

```python
# For exports
metadata={'format': 'csv', 'row_count': 1000, 'filters': {...}}

# For bulk operations
metadata={'affected_ids': [...], 'reason': 'Cleanup'}

# For failed actions
metadata={'error': 'Validation failed', 'details': {...}}
```

---

## Compliance Notes

For HIPAA/GDPR/SOX compliance, ensure:

1. **Retention policy** - Implement archival, not deletion
2. **Access control** - Restrict who can view audit logs
3. **Export capability** - Provide CSV/JSON export for auditors
4. **Integrity** - Consider signing/hashing logs (future feature)

---

## Dependencies

- Django >= 4.2

Note: This package intentionally does NOT depend on django-basemodels. Audit logs
are append-only and don't need soft delete. UUID PKs are implemented directly.

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial stable release
- AuditLog model with UUID PK
- `log()` and `log_event()` API
- Optional middleware for request context
- 23 comprehensive tests
