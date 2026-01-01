"""Tests for IdempotencyKey model."""
import pytest
from datetime import timedelta
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from django_decisioning.models import IdempotencyKey
from tests.models import TimeSemanticTestModel


@pytest.mark.django_db
class TestIdempotencyKey:
    """Test suite for IdempotencyKey model."""

    def test_unique_scope_key_constraint(self):
        """(scope, key) should be unique together."""
        IdempotencyKey.objects.create(
            scope="basket_commit",
            key="abc123"
        )

        with pytest.raises(IntegrityError):
            IdempotencyKey.objects.create(
                scope="basket_commit",
                key="abc123"  # Same scope+key
            )

    def test_different_scopes_same_key_allowed(self):
        """Same key in different scopes should be allowed."""
        IdempotencyKey.objects.create(scope="basket_commit", key="abc123")
        IdempotencyKey.objects.create(scope="payment", key="abc123")

        assert IdempotencyKey.objects.count() == 2

    def test_state_defaults_to_pending(self):
        """State should default to 'pending'."""
        idem = IdempotencyKey.objects.create(
            scope="test",
            key="key1"
        )
        assert idem.state == IdempotencyKey.State.PENDING

    def test_state_transitions_to_processing(self):
        """State can transition from pending to processing."""
        idem = IdempotencyKey.objects.create(scope="test", key="key1")
        assert idem.state == IdempotencyKey.State.PENDING

        idem.state = IdempotencyKey.State.PROCESSING
        idem.locked_at = timezone.now()
        idem.save()

        idem.refresh_from_db()
        assert idem.state == IdempotencyKey.State.PROCESSING

    def test_state_transitions_to_succeeded(self):
        """State can transition from processing to succeeded."""
        idem = IdempotencyKey.objects.create(scope="test", key="key1")
        idem.state = IdempotencyKey.State.PROCESSING
        idem.save()

        idem.state = IdempotencyKey.State.SUCCEEDED
        idem.save()

        idem.refresh_from_db()
        assert idem.state == IdempotencyKey.State.SUCCEEDED

    def test_state_transitions_to_failed(self):
        """State can transition from processing to failed."""
        idem = IdempotencyKey.objects.create(scope="test", key="key1")
        idem.state = IdempotencyKey.State.PROCESSING
        idem.save()

        idem.state = IdempotencyKey.State.FAILED
        idem.error_code = "VALIDATION_ERROR"
        idem.error_message = "Invalid input data"
        idem.save()

        idem.refresh_from_db()
        assert idem.state == IdempotencyKey.State.FAILED

    def test_locked_at_for_stale_lock_detection(self):
        """locked_at should be set when transitioning to processing."""
        idem = IdempotencyKey.objects.create(scope="test", key="key1")
        assert idem.locked_at is None

        lock_time = timezone.now()
        idem.state = IdempotencyKey.State.PROCESSING
        idem.locked_at = lock_time
        idem.save()

        idem.refresh_from_db()
        assert idem.locked_at == lock_time

    def test_error_fields_populated_on_failure(self):
        """error_code and error_message should be populated on failure."""
        idem = IdempotencyKey.objects.create(
            scope="test",
            key="key1",
            state=IdempotencyKey.State.FAILED,
            error_code="TIMEOUT",
            error_message="Request timed out after 30 seconds"
        )

        idem.refresh_from_db()
        assert idem.error_code == "TIMEOUT"
        assert idem.error_message == "Request timed out after 30 seconds"

    def test_result_reference_stored(self):
        """result_type and result_id should store reference to created object."""
        # Create a test model instance to reference
        test_obj = TimeSemanticTestModel.objects.create(name="result")
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        idem = IdempotencyKey.objects.create(
            scope="test",
            key="key1",
            state=IdempotencyKey.State.SUCCEEDED,
            result_type=content_type,
            result_id=str(test_obj.pk)  # CharField for UUID support
        )

        idem.refresh_from_db()
        assert idem.result_type == content_type
        assert idem.result_id == str(test_obj.pk)

    def test_expires_at_for_cleanup(self):
        """expires_at field should be available for cleanup jobs."""
        expiry = timezone.now() + timedelta(hours=24)
        idem = IdempotencyKey.objects.create(
            scope="test",
            key="key1",
            expires_at=expiry
        )

        idem.refresh_from_db()
        assert idem.expires_at == expiry

    def test_expires_at_nullable(self):
        """expires_at should be nullable (no expiration)."""
        idem = IdempotencyKey.objects.create(
            scope="test",
            key="key1"
        )

        assert idem.expires_at is None

    def test_created_at_auto_now_add(self):
        """created_at should be set automatically."""
        before = timezone.now()
        idem = IdempotencyKey.objects.create(scope="test", key="key1")
        after = timezone.now()

        assert idem.created_at is not None
        assert before <= idem.created_at <= after

    def test_request_hash_stored(self):
        """request_hash should store hash of request body for validation."""
        idem = IdempotencyKey.objects.create(
            scope="test",
            key="key1",
            request_hash="sha256:abcdef123456"
        )

        idem.refresh_from_db()
        assert idem.request_hash == "sha256:abcdef123456"

    def test_response_snapshot_stored(self):
        """response_snapshot should store cached response for replay."""
        response_data = {"status": "success", "id": "12345"}
        idem = IdempotencyKey.objects.create(
            scope="test",
            key="key1",
            state=IdempotencyKey.State.SUCCEEDED,
            response_snapshot=response_data
        )

        idem.refresh_from_db()
        assert idem.response_snapshot == response_data
