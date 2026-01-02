"""Tests for django_audit_log models."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestAuditLogModel:
    """Tests for AuditLog model structure."""

    def test_create_audit_log(self):
        """Can create a basic audit log entry."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(
            action='create',
            model_label='myapp.MyModel',
            object_id='12345',
            object_repr='MyModel object (12345)',
        )
        assert log.pk is not None
        assert isinstance(log.pk, uuid.UUID)

    def test_audit_log_has_uuid_pk(self):
        """AuditLog uses UUID primary key."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(
            action='view',
            model_label='test.Test',
        )
        assert isinstance(log.id, uuid.UUID)

    def test_audit_log_has_created_at(self):
        """AuditLog has auto-populated created_at timestamp."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(action='view', model_label='test.Test')
        assert log.created_at is not None

    def test_audit_log_with_actor_user(self):
        """AuditLog can reference actor user."""
        from django_audit_log.models import AuditLog

        user = User.objects.create_user(username='testuser', password='test')
        log = AuditLog.objects.create(
            actor_user=user,
            actor_display='testuser',
            action='create',
            model_label='test.Test',
        )
        assert log.actor_user == user
        assert log.actor_display == 'testuser'

    def test_audit_log_actor_nullable(self):
        """AuditLog actor can be null (system actions)."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(
            action='system_cleanup',
            model_label='system.Task',
            is_system=True,
        )
        assert log.actor_user is None
        assert log.is_system is True

    def test_audit_log_changes_json(self):
        """AuditLog stores before/after changes as JSON."""
        from django_audit_log.models import AuditLog

        changes = {
            'name': {'old': 'Old Name', 'new': 'New Name'},
            'status': {'old': 'draft', 'new': 'published'},
        }
        log = AuditLog.objects.create(
            action='update',
            model_label='blog.Post',
            object_id='abc-123',
            changes=changes,
        )
        assert log.changes == changes

    def test_audit_log_metadata_json(self):
        """AuditLog stores arbitrary metadata as JSON."""
        from django_audit_log.models import AuditLog

        metadata = {
            'reason': 'User requested deletion',
            'ticket': 'SUPPORT-123',
        }
        log = AuditLog.objects.create(
            action='delete',
            model_label='crm.Customer',
            object_id='xyz-789',
            metadata=metadata,
        )
        assert log.metadata == metadata

    def test_audit_log_request_context(self):
        """AuditLog captures request context (IP, user agent)."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(
            action='login',
            model_label='auth.User',
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        )
        assert log.ip_address == '192.168.1.100'
        assert 'Mozilla' in log.user_agent

    def test_audit_log_request_id(self):
        """AuditLog can store request/trace ID for correlation."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(
            action='view',
            model_label='reports.Dashboard',
            request_id='req-abc-123',
            trace_id='trace-xyz-456',
        )
        assert log.request_id == 'req-abc-123'
        assert log.trace_id == 'trace-xyz-456'

    def test_audit_log_sensitivity_levels(self):
        """AuditLog supports sensitivity classification."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(
            action='view',
            model_label='medical.PatientRecord',
            sensitivity='critical',
        )
        assert log.sensitivity == 'critical'

    def test_audit_log_default_sensitivity(self):
        """AuditLog defaults to 'normal' sensitivity."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(
            action='view',
            model_label='blog.Post',
        )
        assert log.sensitivity == 'normal'

    def test_audit_log_str_method(self):
        """AuditLog has readable string representation."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(
            actor_display='admin@example.com',
            action='create',
            model_label='inventory.Product',
        )
        str_repr = str(log)
        assert 'admin@example.com' in str_repr
        assert 'create' in str_repr

    def test_audit_log_ordering(self):
        """AuditLog orders by created_at descending (newest first)."""
        from django_audit_log.models import AuditLog

        log1 = AuditLog.objects.create(action='view', model_label='test.A')
        log2 = AuditLog.objects.create(action='view', model_label='test.B')
        log3 = AuditLog.objects.create(action='view', model_label='test.C')

        logs = list(AuditLog.objects.all())
        assert logs[0] == log3
        assert logs[1] == log2
        assert logs[2] == log1


@pytest.mark.django_db
class TestAuditLogAPI:
    """Tests for public log() API."""

    def test_log_basic(self):
        """log() creates audit entry with minimal args."""
        from django_audit_log import log
        from django_audit_log.models import AuditLog

        log(action='view', obj_label='dashboard.Main')

        assert AuditLog.objects.count() == 1
        entry = AuditLog.objects.first()
        assert entry.action == 'view'
        assert entry.model_label == 'dashboard.Main'

    def test_log_with_model_instance(self):
        """log() extracts label and ID from model instance."""
        from django_audit_log import log
        from django_audit_log.models import AuditLog

        user = User.objects.create_user(username='testobj', password='test')
        log(action='update', obj=user, actor=user)

        entry = AuditLog.objects.first()
        assert entry.model_label == 'auth.user'
        assert entry.object_id == str(user.pk)
        assert entry.actor_user == user

    def test_log_with_changes(self):
        """log() stores change dict."""
        from django_audit_log import log
        from django_audit_log.models import AuditLog

        changes = {'email': {'old': 'a@b.com', 'new': 'x@y.com'}}
        log(action='update', obj_label='users.Profile', obj_id='123', changes=changes)

        entry = AuditLog.objects.first()
        assert entry.changes == changes

    def test_log_with_request(self):
        """log() extracts IP and user agent from request."""
        from django_audit_log import log
        from django_audit_log.models import AuditLog
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/test/', HTTP_USER_AGENT='TestAgent/1.0')
        request.META['REMOTE_ADDR'] = '10.0.0.1'

        log(action='view', obj_label='test.Page', request=request)

        entry = AuditLog.objects.first()
        assert entry.ip_address == '10.0.0.1'
        assert entry.user_agent == 'TestAgent/1.0'


@pytest.mark.django_db
class TestLogEventAPI:
    """Tests for log_event() API (non-model events)."""

    def test_log_event_login(self):
        """log_event() logs non-model events like login."""
        from django_audit_log import log_event
        from django_audit_log.models import AuditLog

        user = User.objects.create_user(username='loginuser', password='test')
        log_event(
            action='login',
            actor=user,
            metadata={'method': 'password'},
        )

        entry = AuditLog.objects.first()
        assert entry.action == 'login'
        assert entry.actor_user == user
        assert entry.metadata['method'] == 'password'

    def test_log_event_permission_denied(self):
        """log_event() logs security events."""
        from django_audit_log import log_event
        from django_audit_log.models import AuditLog

        log_event(
            action='permission_denied',
            actor_display='anonymous',
            metadata={'resource': '/admin/', 'reason': 'Not authenticated'},
            sensitivity='high',
        )

        entry = AuditLog.objects.first()
        assert entry.action == 'permission_denied'
        assert entry.sensitivity == 'high'


@pytest.mark.django_db
class TestAuditLogInheritance:
    """Tests for proper basemodel inheritance."""

    def test_has_uuid_pk(self):
        """AuditLog has UUID primary key."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(action='test', model_label='test.Test')
        assert isinstance(log.pk, uuid.UUID)

    def test_has_created_at(self):
        """AuditLog has created_at timestamp."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(action='test', model_label='test.Test')
        assert log.created_at is not None

    def test_no_soft_delete(self):
        """AuditLog does NOT have soft delete (audit logs are immutable)."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(action='test', model_label='test.Test')
        # Audit logs should not have deleted_at - they're append-only
        assert not hasattr(log, 'deleted_at') or log.deleted_at is None


@pytest.mark.django_db
class TestAuditLogIndexes:
    """Tests for database indexes."""

    def test_model_has_indexes(self):
        """AuditLog has proper indexes for querying."""
        from django_audit_log.models import AuditLog

        # Check indexes exist in meta
        index_fields = []
        for index in AuditLog._meta.indexes:
            index_fields.extend(index.fields)

        # Should have indexes on common query patterns
        assert 'created_at' in index_fields or any('created_at' in f for f in index_fields)


@pytest.mark.django_db
class TestAuditLogTimeSemantics:
    """Tests for AuditLog time semantics (effective_at).

    AuditLog has:
    - created_at: When the log entry was created (recorded_at semantically)
    - effective_at: When the logged event happened (can be backdated)
    """

    def test_audit_log_has_effective_at_field(self):
        """AuditLog should have effective_at field."""
        from django_audit_log.models import AuditLog

        log = AuditLog.objects.create(action='test', model_label='test.Test')

        assert hasattr(log, 'effective_at')
        assert log.effective_at is not None

    def test_audit_log_effective_at_defaults_to_now(self):
        """AuditLog effective_at should default to now."""
        from django.utils import timezone
        from django_audit_log.models import AuditLog

        before = timezone.now()
        log = AuditLog.objects.create(action='test', model_label='test.Test')
        after = timezone.now()

        assert log.effective_at >= before
        assert log.effective_at <= after

    def test_audit_log_can_log_past_events(self):
        """AuditLog effective_at can be set to past time."""
        from django.utils import timezone
        import datetime
        from django_audit_log.models import AuditLog

        past = timezone.now() - datetime.timedelta(days=7)
        log = AuditLog.objects.create(
            action='test',
            model_label='test.Test',
            effective_at=past,
        )

        assert log.effective_at == past

    def test_audit_log_as_of_query(self):
        """AuditLog.objects.as_of(timestamp) returns logs effective at that time."""
        from django.utils import timezone
        import datetime
        from django_audit_log.models import AuditLog

        now = timezone.now()
        past = now - datetime.timedelta(days=7)

        # Old log entry
        old_log = AuditLog.objects.create(
            action='old_action',
            model_label='test.Test',
            effective_at=past,
        )

        # New log entry
        new_log = AuditLog.objects.create(
            action='new_action',
            model_label='test.Test',
            effective_at=now,
        )

        # Query as of 5 days ago (should only see old log)
        five_days_ago = now - datetime.timedelta(days=5)
        logs_then = AuditLog.objects.as_of(five_days_ago).filter(model_label='test.Test')
        assert logs_then.count() == 1
        assert logs_then.first() == old_log

        # Query as of now (should see both)
        logs_now = AuditLog.objects.as_of(now).filter(model_label='test.Test')
        assert logs_now.count() == 2
