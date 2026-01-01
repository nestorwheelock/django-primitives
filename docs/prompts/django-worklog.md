# Prompt: Rebuild django-worklog

## Instruction

Create a Django package called `django-worklog` that provides work session timing primitives with automatic switch policy.

## Package Purpose

Provide work session tracking capabilities:
- `WorkSession` - Track timed work sessions with start/stop
- `start_session()` - Start a new session (auto-stops previous)
- `stop_session()` - End an active session
- Switch policy: starting new session stops previous
- Duration calculation on stop

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel, BaseModel)
- django.contrib.contenttypes
- django.contrib.auth

## File Structure

```
packages/django-worklog/
├── pyproject.toml
├── README.md
├── src/django_worklog/
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
class WorklogError(Exception):
    """Base exception for worklog errors."""
    pass


class NoActiveSessionError(WorklogError):
    """Raised when trying to stop a session that doesn't exist."""
    def __init__(self, user=None, target=None):
        self.user = user
        self.target = target
        message = "No active session"
        if user:
            message += f" for user {user}"
        if target:
            message += f" on target {target}"
        super().__init__(message)


class SessionAlreadyStoppedError(WorklogError):
    """Raised when trying to stop an already stopped session."""
    def __init__(self, session_id):
        self.session_id = session_id
        super().__init__(f"Session {session_id} is already stopped")
```

## Models Specification

### WorkSession Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django_basemodels.models import UUIDModel, BaseModel


class WorkSessionQuerySet(models.QuerySet):
    """QuerySet for work sessions."""

    def for_user(self, user):
        """Get sessions for a specific user."""
        return self.filter(user=user)

    def for_target(self, target):
        """Get sessions for a specific target object."""
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk)
        )

    def active(self):
        """Get currently active (not stopped) sessions."""
        return self.filter(stopped_at__isnull=True)

    def completed(self):
        """Get completed (stopped) sessions."""
        return self.filter(stopped_at__isnull=False)

    def in_range(self, start, end):
        """Get sessions that overlap with a time range."""
        return self.filter(
            started_at__lt=end,
        ).filter(
            models.Q(stopped_at__isnull=True) | models.Q(stopped_at__gt=start)
        )

    def total_duration(self):
        """Get total duration of all sessions in seconds."""
        from django.db.models import Sum
        result = self.aggregate(total=Sum('duration_seconds'))
        return result['total'] or 0


class WorkSession(UUIDModel, BaseModel):
    """A timed work session."""

    # Who is working
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='work_sessions'
    )

    # What they're working on (optional GenericFK)
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='+'
    )
    target_id = models.CharField(max_length=255, blank=True, default='')
    target = GenericForeignKey('target_content_type', 'target_id')

    # Session type/category
    session_type = models.CharField(max_length=100, blank=True, default='')

    # Timing
    started_at = models.DateTimeField(default=timezone.now)
    stopped_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Time semantics
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the session actually started (for backdating)"
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this record was created"
    )

    # Notes and metadata
    notes = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    objects = WorkSessionQuerySet.as_manager()

    class Meta:
        app_label = 'django_worklog'
        verbose_name = 'work session'
        verbose_name_plural = 'work sessions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'stopped_at']),
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['session_type']),
            models.Index(fields=['started_at']),
        ]

    def save(self, *args, **kwargs):
        if self.target_id:
            self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.stopped_at is None

    @property
    def duration(self):
        """Get duration as timedelta."""
        from datetime import timedelta
        if self.duration_seconds is not None:
            return timedelta(seconds=self.duration_seconds)
        if self.stopped_at:
            return self.stopped_at - self.started_at
        return timezone.now() - self.started_at

    @property
    def duration_hours(self) -> float:
        """Get duration in hours."""
        return self.duration.total_seconds() / 3600

    def stop(self, stopped_at=None):
        """
        Stop this session.

        Args:
            stopped_at: When to mark as stopped (defaults to now)
        """
        if self.stopped_at is not None:
            from .exceptions import SessionAlreadyStoppedError
            raise SessionAlreadyStoppedError(self.pk)

        self.stopped_at = stopped_at or timezone.now()
        self.duration_seconds = int(
            (self.stopped_at - self.started_at).total_seconds()
        )
        self.save()

    def __str__(self):
        status = 'active' if self.is_active else 'stopped'
        duration = f"{self.duration_hours:.2f}h"
        return f"Session ({status}) - {duration}"
```

## Services Specification

### services.py

```python
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import WorkSession
from .exceptions import NoActiveSessionError


def get_active_session(user, target=None) -> Optional[WorkSession]:
    """
    Get the currently active session for a user.

    Args:
        user: User to check
        target: Optional target to filter by

    Returns:
        Active WorkSession or None
    """
    qs = WorkSession.objects.for_user(user).active()
    if target:
        qs = qs.for_target(target)
    return qs.order_by('-started_at').first()


@transaction.atomic
def start_session(
    user,
    target=None,
    session_type: str = '',
    notes: str = '',
    metadata: Optional[Dict] = None,
    started_at=None,
    stop_existing: bool = True,
) -> WorkSession:
    """
    Start a new work session.

    By default, implements switch policy: stops any existing active session
    for the user before starting a new one.

    Args:
        user: User starting the session
        target: Optional target object being worked on
        session_type: Type/category of session
        notes: Session notes
        metadata: Additional metadata
        started_at: When session started (defaults to now)
        stop_existing: Whether to stop existing active sessions (switch policy)

    Returns:
        New WorkSession instance
    """
    # Switch policy: stop existing active session
    if stop_existing:
        existing = get_active_session(user)
        if existing:
            existing.stop(stopped_at=started_at or timezone.now())

    # Create new session
    session = WorkSession.objects.create(
        user=user,
        target=target,
        session_type=session_type,
        notes=notes,
        metadata=metadata or {},
        started_at=started_at or timezone.now(),
        effective_at=started_at or timezone.now(),
    )

    return session


@transaction.atomic
def stop_session(
    user,
    target=None,
    stopped_at=None,
    notes: str = '',
) -> WorkSession:
    """
    Stop the active session for a user.

    Args:
        user: User whose session to stop
        target: Optional target to filter by
        stopped_at: When to mark as stopped (defaults to now)
        notes: Additional notes to append

    Returns:
        Stopped WorkSession instance

    Raises:
        NoActiveSessionError: If no active session exists
    """
    session = get_active_session(user, target)

    if not session:
        raise NoActiveSessionError(user, target)

    if notes:
        session.notes = f"{session.notes}\n{notes}".strip() if session.notes else notes

    session.stop(stopped_at=stopped_at)

    return session


def toggle_session(
    user,
    target=None,
    session_type: str = '',
    notes: str = '',
    metadata: Optional[Dict] = None,
) -> WorkSession:
    """
    Toggle session state: stop if active, start if not.

    Args:
        user: User to toggle session for
        target: Optional target object
        session_type: Type for new session (if starting)
        notes: Notes for session
        metadata: Metadata for new session

    Returns:
        WorkSession (either stopped or newly started)
    """
    existing = get_active_session(user, target)

    if existing:
        existing.stop()
        return existing
    else:
        return start_session(
            user=user,
            target=target,
            session_type=session_type,
            notes=notes,
            metadata=metadata,
        )


def get_user_sessions(
    user,
    start_date=None,
    end_date=None,
    target=None,
    session_type: str = None,
):
    """
    Get sessions for a user with optional filters.

    Args:
        user: User to get sessions for
        start_date: Filter sessions starting after this date
        end_date: Filter sessions starting before this date
        target: Filter by target object
        session_type: Filter by session type

    Returns:
        QuerySet of WorkSession
    """
    qs = WorkSession.objects.for_user(user)

    if start_date:
        qs = qs.filter(started_at__gte=start_date)
    if end_date:
        qs = qs.filter(started_at__lt=end_date)
    if target:
        qs = qs.for_target(target)
    if session_type:
        qs = qs.filter(session_type=session_type)

    return qs


def get_total_time(
    user,
    start_date=None,
    end_date=None,
    target=None,
    session_type: str = None,
) -> int:
    """
    Get total time worked in seconds.

    Args:
        user: User to calculate for
        start_date: Start of period
        end_date: End of period
        target: Filter by target
        session_type: Filter by type

    Returns:
        Total seconds worked
    """
    qs = get_user_sessions(
        user,
        start_date=start_date,
        end_date=end_date,
        target=target,
        session_type=session_type,
    ).completed()

    return qs.total_duration()
```

## Test Cases (31 tests)

### WorkSession Model Tests (12 tests)
1. `test_session_creation` - Create with required fields
2. `test_session_has_uuid_pk` - UUID primary key
3. `test_session_user_fk` - FK to user
4. `test_session_target_generic_fk` - GenericFK works
5. `test_session_target_optional` - Target is nullable
6. `test_session_is_active_property` - Active when not stopped
7. `test_session_is_active_false` - Not active when stopped
8. `test_session_duration_property` - Duration calculated
9. `test_session_duration_hours_property` - Hours calculation
10. `test_session_stop_method` - Stop sets fields
11. `test_session_stop_already_stopped` - Error on re-stop
12. `test_session_str_representation` - String format

### WorkSessionQuerySet Tests (6 tests)
1. `test_for_user_filters` - Filters by user
2. `test_for_target_filters` - Filters by target
3. `test_active_filters` - Active only
4. `test_completed_filters` - Completed only
5. `test_in_range_filters` - Time range filter
6. `test_total_duration_aggregates` - Sum of durations

### start_session Service Tests (6 tests)
1. `test_start_session_creates` - Creates session
2. `test_start_session_with_target` - Target attached
3. `test_start_session_stops_existing` - Switch policy
4. `test_start_session_no_stop_existing` - Flag respected
5. `test_start_session_with_time` - Custom start time
6. `test_start_session_with_metadata` - Metadata stored

### stop_session Service Tests (4 tests)
1. `test_stop_session_stops` - Stops active session
2. `test_stop_session_with_time` - Custom stop time
3. `test_stop_session_appends_notes` - Notes appended
4. `test_stop_session_no_active_raises` - Error when none

### toggle_session Service Tests (3 tests)
1. `test_toggle_starts_when_none` - Starts new session
2. `test_toggle_stops_when_active` - Stops active session
3. `test_toggle_returns_session` - Returns session

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    # Models
    'WorkSession',
    # Services
    'get_active_session',
    'start_session',
    'stop_session',
    'toggle_session',
    'get_user_sessions',
    'get_total_time',
    # Exceptions
    'WorklogError',
    'NoActiveSessionError',
    'SessionAlreadyStoppedError',
]

def __getattr__(name):
    if name == 'WorkSession':
        from .models import WorkSession
        return WorkSession
    if name in ('get_active_session', 'start_session', 'stop_session',
                'toggle_session', 'get_user_sessions', 'get_total_time'):
        from .services import (
            get_active_session, start_session, stop_session,
            toggle_session, get_user_sessions, get_total_time
        )
        return locals()[name]
    if name in ('WorklogError', 'NoActiveSessionError', 'SessionAlreadyStoppedError'):
        from .exceptions import WorklogError, NoActiveSessionError, SessionAlreadyStoppedError
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Switch Policy**: Starting new session auto-stops previous
2. **Duration Calculation**: Computed on stop
3. **GenericFK Target**: Sessions for any model type
4. **Time Semantics**: effective_at vs recorded_at
5. **QuerySet Aggregation**: total_duration() for reporting

## Usage Examples

```python
from django_worklog import (
    WorkSession, start_session, stop_session, toggle_session,
    get_user_sessions, get_total_time
)

# Start a work session
session = start_session(
    user=request.user,
    target=project,
    session_type='development',
    notes='Working on feature X'
)

# Start new session (auto-stops previous via switch policy)
new_session = start_session(
    user=request.user,
    target=other_project,
    session_type='review'
)

# Stop current session
stopped = stop_session(request.user)

# Toggle (start if not active, stop if active)
session = toggle_session(request.user, target=task)

# Get all sessions for a user
sessions = get_user_sessions(
    user=request.user,
    start_date=week_start,
    end_date=week_end
)

# Get total time
total_seconds = get_total_time(
    user=request.user,
    start_date=month_start,
    target=project
)
hours = total_seconds / 3600

# Query active sessions
active = WorkSession.objects.for_user(user).active()
```

## Acceptance Criteria

- [ ] WorkSession model with timing fields
- [ ] Switch policy (start stops previous)
- [ ] Duration calculation on stop
- [ ] GenericFK target support
- [ ] start_session, stop_session, toggle_session services
- [ ] WorkSessionQuerySet with filtering and aggregation
- [ ] All 31 tests passing
- [ ] README with usage examples
