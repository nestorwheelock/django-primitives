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
