# Architecture: django-worklog

**Status:** Stable / v0.1.0

Work session tracking with automatic duration calculation.

---

## What This Package Is For

Answering the question: **"How long did this user work on that task?"**

Use cases:
- Time tracking for billable work
- Session-based activity logging
- Duration calculations with server-side timestamps
- Context-attached work sessions (any model)
- Active session enforcement (one per user)

---

## What This Package Is NOT For

- **Not a time clock** - Use dedicated HR software for payroll
- **Not scheduling** - This tracks actual work, not planned work
- **Not project management** - Use separate PM tools for task assignment
- **Not analytics** - Export data for analytics/reporting systems

---

## Design Principles

1. **Server-side timestamps** - started_at/stopped_at set by server, not client
2. **One active session** - Each user can have only one active session
3. **Duration immutability** - duration_seconds set when stopped, never changes
4. **GenericFK context** - Attach sessions to any model
5. **Time semantics** - effective_at vs recorded_at for backdating

---

## Data Model

```
WorkSession
├── id (UUID, BaseModel)
├── user (FK → AUTH_USER_MODEL)
├── context (GenericFK)
│   ├── context_content_type (FK → ContentType)
│   └── context_object_id (CharField for UUID)
├── started_at (auto_now_add)
├── stopped_at (nullable)
├── duration_seconds (nullable, set when stopped)
├── metadata (JSON)
├── effective_at (time semantics)
├── recorded_at (time semantics)
├── created_at (auto)
├── updated_at (auto)
└── deleted_at (soft delete)

Session States:
  Active:   stopped_at IS NULL, duration_seconds IS NULL
  Stopped:  stopped_at IS NOT NULL, duration_seconds IS NOT NULL

Constraints:
  - One active session per user (unique on user WHERE stopped_at IS NULL)
  - Duration consistency: both NULL or both NOT NULL
```

---

## Public API

### Service Functions

```python
from django_worklog.services import (
    start_session,
    stop_session,
    get_active_session,
    get_sessions_for_context,
)

# Start a session (stops any active session first)
session = start_session(
    user=user,
    context=task,
    metadata={'source': 'web'},
)

# Get active session for user
active = get_active_session(user)
if active:
    print(f"Working on: {active.context}")

# Stop the session
stopped = stop_session(session)
print(f"Duration: {stopped.duration_seconds} seconds")

# Get all sessions for a context
sessions = get_sessions_for_context(task)
total_seconds = sum(s.duration_seconds or 0 for s in sessions)
```

### Direct Model Usage

```python
from django_worklog.models import WorkSession
from django.contrib.contenttypes.models import ContentType

# Create session (prefer service functions)
session = WorkSession.objects.create(
    user=user,
    context_content_type=ContentType.objects.get_for_model(task),
    context_object_id=str(task.pk),
)

# Query active sessions
active_sessions = WorkSession.objects.filter(stopped_at__isnull=True)

# Query by context
task_sessions = WorkSession.objects.filter(
    context_content_type=ContentType.objects.get_for_model(task),
    context_object_id=str(task.pk),
)

# Time semantics queries
sessions_today = WorkSession.objects.as_of(today)
```

---

## Hard Rules

1. **One active session per user** - Database constraint enforces this
2. **Server-side timestamps only** - Cannot set started_at/stopped_at from client
3. **Duration consistency** - Either both NULL (active) or both NOT NULL (stopped)
4. **Duration immutable** - Once set, duration_seconds cannot change

---

## Invariants

- Active session: `stopped_at IS NULL` AND `duration_seconds IS NULL`
- Stopped session: `stopped_at IS NOT NULL` AND `duration_seconds IS NOT NULL`
- Only one WorkSession per user can have `stopped_at IS NULL` (constraint)
- `duration_seconds = stopped_at - started_at` when stopped
- `context_object_id` is always stored as string

---

## Known Gotchas

### 1. Starting Session Stops Previous

**Problem:** User has active session when starting new one.

```python
# User working on task1
session1 = start_session(user, task1)

# Start new session - task1 session auto-stopped
session2 = start_session(user, task2)

# session1 is now stopped with duration calculated
```

**Solution:** This is intentional. Check `get_active_session()` first if you want different behavior.

### 2. Unique Constraint Violation

**Problem:** Creating session when one already active.

```python
# Using models directly can fail
session1 = WorkSession.objects.create(user=user, context=task1)
session2 = WorkSession.objects.create(user=user, context=task2)
# IntegrityError: unique_active_session_per_user
```

**Solution:** Use `start_session()` service which handles stopping existing session.

### 3. Duration Not Calculated on save()

**Problem:** Setting stopped_at without duration.

```python
session.stopped_at = timezone.now()
session.save()
# Violates constraint: stopped_at NOT NULL, duration_seconds NULL
```

**Solution:** Use `stop_session()` service which calculates duration:

```python
stopped = stop_session(session)
# stopped.duration_seconds is now set
```

### 4. Soft Delete Interaction

**Problem:** Soft-deleted sessions still count for uniqueness.

```python
session = start_session(user, task)
session.soft_delete()  # Sets deleted_at

# Can start new session because constraint checks deleted_at IS NULL
new_session = start_session(user, task)  # Works!
```

### 5. Context Object ID Must Be String

**Problem:** Using integer or UUID directly.

```python
# WRONG - may fail for UUID PKs
session.context_object_id = task.pk

# CORRECT - always stringify
session.context_object_id = str(task.pk)
```

---

## Recommended Usage

### 1. Use Service Functions

```python
from django_worklog.services import start_session, stop_session

# RECOMMENDED - handles edge cases
session = start_session(user, context)
# ... work happens ...
stopped = stop_session(session)

# AVOID - bypasses safety checks
WorkSession.objects.create(...)
session.stopped_at = timezone.now()
session.save()
```

### 2. Calculate Total Time for Context

```python
from django_worklog.services import get_sessions_for_context

def total_time_spent(context):
    """Get total seconds spent on a context."""
    sessions = get_sessions_for_context(context)
    return sum(s.duration_seconds or 0 for s in sessions)

# For billing
hours = total_time_spent(project) / 3600
billable = Decimal(str(hours)) * hourly_rate
```

### 3. Handle Active Sessions on Context Delete

```python
def delete_task(task):
    """Delete task and stop any active sessions."""
    from django_worklog.services import get_sessions_for_context, stop_session

    for session in get_sessions_for_context(task):
        if session.stopped_at is None:
            stop_session(session)

    task.delete()
```

### 4. Track Session Metadata

```python
session = start_session(
    user=user,
    context=task,
    metadata={
        'source': 'mobile_app',
        'app_version': '1.2.3',
        'location': 'office',
    },
)
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)
- django-decisioning (for time semantics)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- WorkSession model with GenericFK context
- One active session per user constraint
- Duration consistency constraint
- Service functions for session management
- Time semantics (effective_at, recorded_at)
