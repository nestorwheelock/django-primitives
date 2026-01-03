"""Tests for cleanup_idempotency_keys management command."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from django_decisioning.models import IdempotencyKey


@pytest.mark.django_db
class TestCleanupIdempotencyKeysCommand:
    """Test suite for cleanup_idempotency_keys command."""

    def test_cleanup_deletes_old_keys(self):
        """Command should delete keys older than specified days."""
        # Create an old key (10 days ago)
        old_key = IdempotencyKey.objects.create(
            scope='test',
            key='old-key',
            state=IdempotencyKey.State.SUCCEEDED,
        )
        IdempotencyKey.objects.filter(pk=old_key.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        # Create a recent key
        recent_key = IdempotencyKey.objects.create(
            scope='test',
            key='recent-key',
            state=IdempotencyKey.State.SUCCEEDED,
        )

        out = StringIO()
        call_command('cleanup_idempotency_keys', '--days=7', stdout=out)

        # Old key should be deleted
        assert not IdempotencyKey.objects.filter(pk=old_key.pk).exists()
        # Recent key should remain
        assert IdempotencyKey.objects.filter(pk=recent_key.pk).exists()

    def test_cleanup_preserves_recent_keys(self):
        """Command should not delete keys newer than specified days."""
        recent_key = IdempotencyKey.objects.create(
            scope='test',
            key='recent-key',
            state=IdempotencyKey.State.SUCCEEDED,
        )

        out = StringIO()
        call_command('cleanup_idempotency_keys', '--days=7', stdout=out)

        assert IdempotencyKey.objects.filter(pk=recent_key.pk).exists()

    def test_dry_run_does_not_delete(self):
        """--dry-run should show count without deleting."""
        old_key = IdempotencyKey.objects.create(
            scope='test',
            key='old-key',
            state=IdempotencyKey.State.SUCCEEDED,
        )
        IdempotencyKey.objects.filter(pk=old_key.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        out = StringIO()
        call_command('cleanup_idempotency_keys', '--days=7', '--dry-run', stdout=out)

        # Key should still exist
        assert IdempotencyKey.objects.filter(pk=old_key.pk).exists()
        # Output should mention "Would delete"
        assert 'Would delete' in out.getvalue()

    def test_custom_days_argument(self):
        """--days argument should control cutoff age."""
        # Create a 5-day old key
        key_5_days = IdempotencyKey.objects.create(
            scope='test',
            key='5-days-old',
            state=IdempotencyKey.State.SUCCEEDED,
        )
        IdempotencyKey.objects.filter(pk=key_5_days.pk).update(
            created_at=timezone.now() - timedelta(days=5)
        )

        # With --days=7, should not be deleted
        out = StringIO()
        call_command('cleanup_idempotency_keys', '--days=7', stdout=out)
        assert IdempotencyKey.objects.filter(pk=key_5_days.pk).exists()

        # With --days=3, should be deleted
        call_command('cleanup_idempotency_keys', '--days=3', stdout=out)
        assert not IdempotencyKey.objects.filter(pk=key_5_days.pk).exists()

    def test_cleanup_deletes_expired_keys(self):
        """Command should delete keys past their expires_at."""
        expired_key = IdempotencyKey.objects.create(
            scope='test',
            key='expired-key',
            state=IdempotencyKey.State.SUCCEEDED,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        out = StringIO()
        call_command('cleanup_idempotency_keys', '--days=30', stdout=out)

        # Expired key should be deleted even though it's recent
        assert not IdempotencyKey.objects.filter(pk=expired_key.pk).exists()

    def test_excludes_processing_keys_by_default(self):
        """By default, processing keys should not be deleted."""
        old_processing_key = IdempotencyKey.objects.create(
            scope='test',
            key='processing-key',
            state=IdempotencyKey.State.PROCESSING,
        )
        IdempotencyKey.objects.filter(pk=old_processing_key.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        out = StringIO()
        call_command('cleanup_idempotency_keys', '--days=7', stdout=out)

        # Processing key should remain (might be in-flight)
        assert IdempotencyKey.objects.filter(pk=old_processing_key.pk).exists()

    def test_include_processing_flag_deletes_stale_processing(self):
        """--include-processing should also delete stale processing keys."""
        old_processing_key = IdempotencyKey.objects.create(
            scope='test',
            key='processing-key',
            state=IdempotencyKey.State.PROCESSING,
        )
        IdempotencyKey.objects.filter(pk=old_processing_key.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        out = StringIO()
        call_command('cleanup_idempotency_keys', '--days=7', '--include-processing', stdout=out)

        # Now processing key should be deleted
        assert not IdempotencyKey.objects.filter(pk=old_processing_key.pk).exists()

    def test_cleanup_output_shows_deleted_count(self):
        """Command should report how many keys were deleted."""
        for i in range(5):
            key = IdempotencyKey.objects.create(
                scope='test',
                key=f'old-key-{i}',
                state=IdempotencyKey.State.SUCCEEDED,
            )
            IdempotencyKey.objects.filter(pk=key.pk).update(
                created_at=timezone.now() - timedelta(days=10)
            )

        out = StringIO()
        call_command('cleanup_idempotency_keys', '--days=7', stdout=out)

        assert 'Deleted 5' in out.getvalue()
