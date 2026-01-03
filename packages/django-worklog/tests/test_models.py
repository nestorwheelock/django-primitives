"""Tests for WorkSession model."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_worklog.models import WorkSession
from tests.testapp.models import Task, Project


@pytest.fixture
def task(db):
    """Create a test task for context attachment."""
    return Task.objects.create(name="Test Task")


@pytest.fixture
def project(db):
    """Create a test project for context attachment."""
    return Project.objects.create(title="Test Project")


@pytest.mark.django_db
class TestWorkSessionUniqueActiveConstraint:
    """Tests for one active session per user constraint.

    The WorkSession model docstring says: "One active session per user (stopped_at IS NULL)"
    This is enforced by a partial UniqueConstraint.
    """

    def test_cannot_create_two_active_sessions_for_same_user(self, user, task, project):
        """Cannot create two active sessions for the same user."""
        from django.db import IntegrityError

        task_ct = ContentType.objects.get_for_model(task)
        project_ct = ContentType.objects.get_for_model(project)

        # First active session - OK
        WorkSession.objects.create(
            user=user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
        )

        # Second active session - should fail
        with pytest.raises(IntegrityError):
            WorkSession.objects.create(
                user=user,
                context_content_type=project_ct,
                context_object_id=str(project.pk),
            )

    def test_can_create_active_after_stopping_previous(self, user, task, project):
        """Can create new active session after stopping the previous one."""
        task_ct = ContentType.objects.get_for_model(task)
        project_ct = ContentType.objects.get_for_model(project)

        # First session - stop it
        session1 = WorkSession.objects.create(
            user=user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
        )
        session1.stopped_at = timezone.now()
        session1.duration_seconds = 100
        session1.save()

        # Second session - should work since first is stopped
        session2 = WorkSession.objects.create(
            user=user,
            context_content_type=project_ct,
            context_object_id=str(project.pk),
        )

        assert session2.pk is not None
        assert session2.stopped_at is None

    def test_can_create_active_after_soft_deleting_previous(self, user, task, project):
        """Can create new active session after soft-deleting the previous one."""
        task_ct = ContentType.objects.get_for_model(task)
        project_ct = ContentType.objects.get_for_model(project)

        # First session - soft delete it
        session1 = WorkSession.objects.create(
            user=user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
        )
        session1.delete()  # BaseModel soft delete

        # Second session - should work since first is soft-deleted
        session2 = WorkSession.objects.create(
            user=user,
            context_content_type=project_ct,
            context_object_id=str(project.pk),
        )

        assert session2.pk is not None
        assert session2.stopped_at is None

    def test_different_users_can_have_active_sessions(self, user, other_user, task):
        """Different users can each have an active session."""
        task_ct = ContentType.objects.get_for_model(task)

        # Both should work - different users
        session1 = WorkSession.objects.create(
            user=user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
        )
        session2 = WorkSession.objects.create(
            user=other_user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
        )

        assert session1.pk is not None
        assert session2.pk is not None


@pytest.mark.django_db
class TestWorkSessionDurationConsistency:
    """Tests for duration consistency constraint.

    When stopped_at IS NULL, duration_seconds must be NULL.
    When stopped_at IS NOT NULL, duration_seconds must be NOT NULL.
    """

    def test_cannot_set_duration_without_stopped_at(self, user, task):
        """Cannot have duration_seconds set when stopped_at is null."""
        from django.db import IntegrityError

        task_ct = ContentType.objects.get_for_model(task)

        with pytest.raises(IntegrityError):
            WorkSession.objects.create(
                user=user,
                context_content_type=task_ct,
                context_object_id=str(task.pk),
                stopped_at=None,
                duration_seconds=100,  # Invalid: has duration but not stopped
            )

    def test_cannot_have_stopped_at_without_duration(self, user, task):
        """Cannot have stopped_at set without duration_seconds."""
        from django.db import IntegrityError

        task_ct = ContentType.objects.get_for_model(task)

        with pytest.raises(IntegrityError):
            WorkSession.objects.create(
                user=user,
                context_content_type=task_ct,
                context_object_id=str(task.pk),
                stopped_at=timezone.now(),
                duration_seconds=None,  # Invalid: stopped but no duration
            )

    def test_valid_active_session(self, user, task):
        """Active session has null stopped_at and null duration_seconds."""
        task_ct = ContentType.objects.get_for_model(task)

        session = WorkSession.objects.create(
            user=user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
        )

        assert session.stopped_at is None
        assert session.duration_seconds is None

    def test_valid_stopped_session(self, user, task):
        """Stopped session has both stopped_at and duration_seconds set."""
        task_ct = ContentType.objects.get_for_model(task)

        session = WorkSession.objects.create(
            user=user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
            stopped_at=timezone.now(),
            duration_seconds=100,
        )

        assert session.stopped_at is not None
        assert session.duration_seconds == 100


@pytest.mark.django_db
class TestWorkSessionCreation:
    """Tests for WorkSession model creation."""

    def test_worksession_created_with_required_fields(self, user, task):
        """WorkSession can be created with required fields."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        assert session.pk is not None
        assert session.user == user
        assert session.context_content_type == content_type
        assert session.context_object_id == str(task.pk)

    def test_started_at_auto_populated(self, user, task):
        """started_at is automatically populated on creation."""
        content_type = ContentType.objects.get_for_model(task)
        before = timezone.now()

        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        after = timezone.now()
        assert session.started_at is not None
        assert before <= session.started_at <= after

    def test_stopped_at_initially_null(self, user, task):
        """stopped_at is null on creation (session is active)."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        assert session.stopped_at is None

    def test_duration_seconds_null_when_active(self, user, task):
        """duration_seconds is null when session is active."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        assert session.duration_seconds is None

    def test_metadata_defaults_to_empty_dict(self, user, task):
        """metadata defaults to empty dict."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        assert session.metadata == {}


@pytest.mark.django_db
class TestWorkSessionGenericFK:
    """Tests for GenericForeignKey context attachment."""

    def test_generic_fk_attaches_to_task(self, user, task):
        """GenericFK correctly attaches to Task model."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        assert session.context == task

    def test_generic_fk_attaches_to_project(self, user, project):
        """GenericFK correctly attaches to Project model."""
        content_type = ContentType.objects.get_for_model(project)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(project.pk),
        )

        assert session.context == project

    def test_context_preserved_through_save(self, user, task):
        """Context reference is preserved after save and reload."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        reloaded = WorkSession.objects.get(pk=session.pk)
        assert reloaded.context == task


@pytest.mark.django_db
class TestWorkSessionUserRelation:
    """Tests for user relationship."""

    def test_user_cascade_delete_removes_sessions(self, user, task):
        """Deleting user cascades to delete their sessions."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )
        session_pk = session.pk

        user.delete()

        assert not WorkSession.objects.filter(pk=session_pk).exists()

    def test_multiple_sessions_per_user_allowed(self, user, task, project):
        """User can have multiple session records (historical)."""
        task_ct = ContentType.objects.get_for_model(task)
        project_ct = ContentType.objects.get_for_model(project)

        session1 = WorkSession.objects.create(
            user=user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
            stopped_at=timezone.now(),
            duration_seconds=100,
        )
        session2 = WorkSession.objects.create(
            user=user,
            context_content_type=project_ct,
            context_object_id=str(project.pk),
        )

        assert WorkSession.objects.filter(user=user).count() == 2


@pytest.mark.django_db
class TestWorkSessionStringRepresentation:
    """Tests for string representation."""

    def test_str_representation(self, user, task):
        """String representation is meaningful."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        str_repr = str(session)
        assert user.username in str_repr or str(session.pk) in str_repr


@pytest.mark.django_db
class TestWorkSessionTimeSemantics:
    """Tests for WorkSession time semantics (effective_at/recorded_at).

    WorkSession has effective_at for when session "actually" started
    (can differ from recorded_at if backdated).
    """

    def test_worksession_has_effective_at_field(self, user, task):
        """WorkSession should have effective_at field."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        assert hasattr(session, 'effective_at')
        assert session.effective_at is not None

    def test_worksession_has_recorded_at_field(self, user, task):
        """WorkSession should have recorded_at field."""
        content_type = ContentType.objects.get_for_model(task)
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )

        assert hasattr(session, 'recorded_at')
        assert session.recorded_at is not None

    def test_worksession_effective_at_defaults_to_now(self, user, task):
        """WorkSession effective_at should default to now."""
        content_type = ContentType.objects.get_for_model(task)
        before = timezone.now()
        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
        )
        after = timezone.now()

        assert session.effective_at >= before
        assert session.effective_at <= after

    def test_worksession_can_be_backdated(self, user, task):
        """WorkSession effective_at can be set to past time."""
        import datetime
        content_type = ContentType.objects.get_for_model(task)
        past = timezone.now() - datetime.timedelta(days=7)

        session = WorkSession.objects.create(
            user=user,
            context_content_type=content_type,
            context_object_id=str(task.pk),
            effective_at=past,
        )

        assert session.effective_at == past

    def test_worksession_as_of_query(self, user, task, project):
        """WorkSession.objects.as_of(timestamp) returns sessions effective at that time."""
        import datetime
        task_ct = ContentType.objects.get_for_model(task)
        project_ct = ContentType.objects.get_for_model(project)

        now = timezone.now()
        past = now - datetime.timedelta(days=7)

        # Old session - stopped so we can create another
        old_session = WorkSession.objects.create(
            user=user,
            context_content_type=task_ct,
            context_object_id=str(task.pk),
            effective_at=past,
            stopped_at=past + datetime.timedelta(hours=1),
            duration_seconds=3600,
        )

        # New session - can be active since old one is stopped
        new_session = WorkSession.objects.create(
            user=user,
            context_content_type=project_ct,
            context_object_id=str(project.pk),
            effective_at=now,
        )

        # Query as of 5 days ago (should only see old session)
        five_days_ago = now - datetime.timedelta(days=5)
        sessions_then = WorkSession.objects.as_of(five_days_ago).filter(user=user)
        assert sessions_then.count() == 1
        assert sessions_then.first() == old_session

        # Query as of now (should see both)
        sessions_now = WorkSession.objects.as_of(now).filter(user=user)
        assert sessions_now.count() == 2
