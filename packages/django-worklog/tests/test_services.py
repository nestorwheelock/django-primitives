"""Tests for worklog services."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from freezegun import freeze_time

from django_worklog.exceptions import NoActiveSession, InvalidContext
from django_worklog.models import WorkSession
from django_worklog.services import start_session, stop_session, get_active_session
from tests.testapp.models import Task, Project


@pytest.fixture
def task(db):
    """Create a test task for context attachment."""
    return Task.objects.create(name="Test Task")


@pytest.fixture
def other_task(db):
    """Create another test task."""
    return Task.objects.create(name="Other Task")


@pytest.fixture
def project(db):
    """Create a test project for context attachment."""
    return Project.objects.create(title="Test Project")


@pytest.mark.django_db
class TestStartSession:
    """Tests for start_session service."""

    def test_start_session_creates_new_session(self, user, task):
        """start_session creates a new session when none active."""
        session = start_session(user, task)

        assert session.pk is not None
        assert session.user == user
        assert session.context == task
        assert session.stopped_at is None

    def test_start_session_switches_active_session(self, user, task, other_task):
        """start_session stops existing active session and starts new one."""
        first_session = start_session(user, task)
        first_pk = first_session.pk

        second_session = start_session(user, other_task)

        # First session should be stopped
        first_session.refresh_from_db()
        assert first_session.stopped_at is not None
        assert first_session.duration_seconds is not None

        # Second session should be active
        assert second_session.pk != first_pk
        assert second_session.stopped_at is None
        assert second_session.context == other_task

    def test_start_session_atomic_switch(self, user, task, other_task):
        """Both stop and start happen atomically."""
        first_session = start_session(user, task)
        second_session = start_session(user, other_task)

        # Only one active session should exist
        active_count = WorkSession.objects.filter(
            user=user, stopped_at__isnull=True
        ).count()
        assert active_count == 1

    def test_cannot_have_two_active_sessions(self, user, task, other_task):
        """User cannot have two active sessions at the same time."""
        start_session(user, task)
        start_session(user, other_task)

        active_sessions = WorkSession.objects.filter(
            user=user, stopped_at__isnull=True
        )
        assert active_sessions.count() == 1

    def test_start_session_with_none_context_raises(self, user):
        """start_session with None context raises InvalidContext."""
        with pytest.raises(InvalidContext):
            start_session(user, None)

    def test_different_users_independent_sessions(self, user, other_user, task):
        """Different users can have independent active sessions."""
        session1 = start_session(user, task)
        session2 = start_session(other_user, task)

        assert session1.stopped_at is None
        assert session2.stopped_at is None
        assert session1.user != session2.user

    def test_start_session_records_server_timestamp(self, user, task):
        """started_at is a server-side timestamp."""
        before = timezone.now()
        session = start_session(user, task)
        after = timezone.now()

        assert before <= session.started_at <= after

    @freeze_time("2025-01-15 10:00:00")
    def test_switching_records_correct_duration(self, user, task, other_task):
        """Switching sessions computes duration correctly."""
        with freeze_time("2025-01-15 10:00:00"):
            first_session = start_session(user, task)

        with freeze_time("2025-01-15 10:05:00"):
            start_session(user, other_task)

        first_session.refresh_from_db()
        assert first_session.duration_seconds == 300  # 5 minutes


@pytest.mark.django_db
class TestStopSession:
    """Tests for stop_session service."""

    def test_stop_session_stops_active(self, user, task):
        """stop_session stops the active session."""
        session = start_session(user, task)
        stopped = stop_session(user)

        assert stopped.pk == session.pk
        assert stopped.stopped_at is not None

    def test_stop_session_computes_duration(self, user, task):
        """stop_session computes duration_seconds correctly."""
        with freeze_time("2025-01-15 10:00:00"):
            start_session(user, task)

        with freeze_time("2025-01-15 10:10:00"):
            stopped = stop_session(user)

        assert stopped.duration_seconds == 600  # 10 minutes

    def test_stop_session_raises_when_none_active(self, user):
        """stop_session raises NoActiveSession when no active session."""
        with pytest.raises(NoActiveSession):
            stop_session(user)

    def test_stop_session_twice_raises(self, user, task):
        """Calling stop_session twice raises NoActiveSession."""
        start_session(user, task)
        stop_session(user)

        with pytest.raises(NoActiveSession):
            stop_session(user)

    def test_duration_immutable_after_stop(self, user, task):
        """duration_seconds cannot be changed after session is stopped."""
        with freeze_time("2025-01-15 10:00:00"):
            start_session(user, task)

        with freeze_time("2025-01-15 10:05:00"):
            stopped = stop_session(user)

        original_duration = stopped.duration_seconds

        # Reload and verify
        stopped.refresh_from_db()
        assert stopped.duration_seconds == original_duration == 300

    def test_stop_session_server_timestamp(self, user, task):
        """stopped_at is a server-side timestamp."""
        start_session(user, task)

        before = timezone.now()
        stopped = stop_session(user)
        after = timezone.now()

        assert before <= stopped.stopped_at <= after


@pytest.mark.django_db
class TestGetActiveSession:
    """Tests for get_active_session service."""

    def test_get_active_session_returns_active(self, user, task):
        """get_active_session returns the active session."""
        session = start_session(user, task)
        active = get_active_session(user)

        assert active.pk == session.pk

    def test_get_active_session_returns_none_when_no_active(self, user):
        """get_active_session returns None when no active session."""
        active = get_active_session(user)
        assert active is None

    def test_get_active_session_returns_none_after_stop(self, user, task):
        """get_active_session returns None after session stopped."""
        start_session(user, task)
        stop_session(user)

        active = get_active_session(user)
        assert active is None


@pytest.mark.django_db
class TestSessionInvariants:
    """Tests for session invariants."""

    def test_duration_equals_time_difference(self, user, task):
        """Total duration equals stopped_at - started_at."""
        with freeze_time("2025-01-15 10:00:00"):
            session = start_session(user, task)

        with freeze_time("2025-01-15 10:07:30"):
            stopped = stop_session(user)

        expected = int((stopped.stopped_at - stopped.started_at).total_seconds())
        assert stopped.duration_seconds == expected == 450  # 7.5 minutes

    def test_context_integrity_preserved(self, user, task):
        """Context remains accessible through session lifecycle."""
        session = start_session(user, task)
        assert session.context == task

        stopped = stop_session(user)
        assert stopped.context == task

        # Reload and check
        reloaded = WorkSession.objects.get(pk=stopped.pk)
        assert reloaded.context == task

    def test_no_overlapping_active_sessions_invariant(self, user, task, other_task, project):
        """No matter how many switches, only one active session per user."""
        start_session(user, task)
        start_session(user, other_task)
        start_session(user, project)
        start_session(user, task)

        active_count = WorkSession.objects.filter(
            user=user, stopped_at__isnull=True
        ).count()
        assert active_count == 1

        # Should have 4 total sessions (3 stopped, 1 active)
        total_count = WorkSession.objects.filter(user=user).count()
        assert total_count == 4
