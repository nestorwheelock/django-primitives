"""Service functions for django-worklog.

Provides:
- start_session: Start a work session (switches if one exists)
- stop_session: Stop the user's active session
- get_active_session: Get the user's active session
"""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .exceptions import NoActiveSession, InvalidContext
from .models import WorkSession


def get_active_session(user) -> WorkSession | None:
    """
    Get the user's active (unstopped) session.

    Args:
        user: The user to check

    Returns:
        The active WorkSession or None if no active session
    """
    return WorkSession.objects.filter(
        user=user,
        stopped_at__isnull=True,
    ).first()


def _stop_session_internal(session: WorkSession) -> WorkSession:
    """
    Internal helper to stop a session.

    Sets stopped_at and computes duration_seconds.
    """
    session.stopped_at = timezone.now()
    session.duration_seconds = int(
        (session.stopped_at - session.started_at).total_seconds()
    )
    session.save(update_fields=["stopped_at", "duration_seconds", "updated_at"])
    return session


@transaction.atomic
def start_session(user, context) -> WorkSession:
    """
    Start a work session.

    If no active session: create new.
    If active session exists: stop it, start new (Switch policy).
    All timestamps server-side. Atomic operation.

    Args:
        user: The user starting the session
        context: The model instance to attach (GenericFK target)

    Returns:
        The new WorkSession

    Raises:
        InvalidContext: If context is None
    """
    if context is None:
        raise InvalidContext("Context cannot be None")

    # Check for existing active session and stop it (Switch policy)
    active_session = get_active_session(user)
    if active_session is not None:
        _stop_session_internal(active_session)

    # Create new session
    content_type = ContentType.objects.get_for_model(context)
    session = WorkSession.objects.create(
        user=user,
        context_content_type=content_type,
        context_object_id=str(context.pk),
    )

    return session


@transaction.atomic
def stop_session(user) -> WorkSession:
    """
    Stop the user's active session.

    Computes duration_seconds.

    Args:
        user: The user whose session to stop

    Returns:
        The stopped WorkSession

    Raises:
        NoActiveSession: If no active session exists
    """
    active_session = get_active_session(user)
    if active_session is None:
        raise NoActiveSession(user)

    return _stop_session_internal(active_session)
