"""Concurrency probes for database constraint enforcement.

These tests verify that database constraints hold under concurrent access.
"""

import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.contrib.contenttypes.models import ContentType


@pytest.mark.django_db(transaction=True)
class TestSequenceConcurrency:
    """Verify sequence atomic increment under concurrent access."""

    def test_concurrent_sequence_allocations(self, seeded_database):
        """Two concurrent allocations for same scope+org produce unique values."""
        from django_sequence.models import Sequence

        seq = Sequence.objects.first()
        if not seq:
            pytest.skip("No sequence available")

        initial_value = seq.current_value
        results = []
        errors = []

        def allocate_next():
            """Atomically increment and return new value."""
            try:
                # Use select_for_update to ensure atomic increment
                with transaction.atomic():
                    s = Sequence.objects.select_for_update().get(pk=seq.pk)
                    s.current_value += 1
                    s.save()
                    return s.current_value
            except Exception as e:
                return e

        # Run 10 concurrent allocations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(allocate_next) for _ in range(10)]
            for future in as_completed(futures):
                result = future.result()
                if isinstance(result, Exception):
                    errors.append(result)
                else:
                    results.append(result)

        # Close extra connections created by threads
        connection.close()

        # Verify no errors
        assert len(errors) == 0, f"Errors during concurrent allocation: {errors}"

        # Verify all results are unique
        assert len(results) == len(set(results)), "Duplicate values generated"

        # Verify final value is correct
        seq.refresh_from_db()
        assert seq.current_value == initial_value + 10, (
            f"Expected {initial_value + 10}, got {seq.current_value}"
        )


@pytest.mark.django_db(transaction=True)
class TestWorklogConcurrency:
    """Verify one-active-session constraint under race conditions."""

    def test_concurrent_active_session_creation(self, seeded_database):
        """Simulate race condition: only one active session should succeed."""
        from django.contrib.auth import get_user_model
        from django_worklog.models import WorkSession
        from django_parties.models import Person

        User = get_user_model()
        user = User.objects.first()
        person = Person.objects.first()

        if not user or not person:
            pytest.skip("No user or person available")

        person_ct = ContentType.objects.get_for_model(Person)

        # Clear any existing active sessions for this user
        WorkSession.objects.filter(
            user=user,
            stopped_at__isnull=True,
            deleted_at__isnull=True,
        ).update(deleted_at=None)  # Soft delete existing

        # Actually delete them for clean test
        WorkSession.objects.filter(user=user).delete()

        successes = []
        failures = []
        barrier = threading.Barrier(3)  # Synchronize 3 threads

        def try_create_active_session(context_id):
            """Try to create an active session."""
            try:
                barrier.wait()  # All threads start together
                with transaction.atomic():
                    session = WorkSession.objects.create(
                        user=user,
                        context_content_type=person_ct,
                        context_object_id=f"test-race-{context_id}",
                        stopped_at=None,
                        duration_seconds=None,
                    )
                    return ("success", session.pk)
            except IntegrityError as e:
                return ("integrity_error", str(e))
            except Exception as e:
                return ("other_error", str(e))

        # Run 3 concurrent attempts
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(try_create_active_session, i) for i in range(3)]
            for future in as_completed(futures):
                result_type, detail = future.result()
                if result_type == "success":
                    successes.append(detail)
                else:
                    failures.append((result_type, detail))

        # Close extra connections
        connection.close()

        # Constraint enforcement: exactly one should succeed
        assert len(successes) == 1, (
            f"Expected exactly 1 success, got {len(successes)}. "
            f"Successes: {successes}, Failures: {failures}"
        )

        # The others should fail with IntegrityError
        assert len(failures) == 2, (
            f"Expected 2 failures, got {len(failures)}. Failures: {failures}"
        )

        for failure_type, _ in failures:
            assert failure_type == "integrity_error", (
                f"Expected IntegrityError, got {failure_type}"
            )

        # Verify only one active session exists
        active_count = WorkSession.objects.filter(
            user=user,
            stopped_at__isnull=True,
            deleted_at__isnull=True,
        ).count()
        assert active_count == 1, f"Expected 1 active session, found {active_count}"
