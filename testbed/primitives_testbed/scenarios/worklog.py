"""Worklog scenario: WorkSession with timing and duration constraints."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_worklog.models import WorkSession
from django_parties.models import Person


User = get_user_model()


def seed():
    """Create sample worklog data."""
    count = 0

    user = User.objects.filter(username="staff_testbed").first()
    if not user:
        user = User.objects.first()

    person = Person.objects.first()
    if not person:
        return count

    person_ct = ContentType.objects.get_for_model(Person)

    if user:
        now = timezone.now()

        # Create a completed session
        yesterday_start = now - timezone.timedelta(days=1, hours=8)
        duration_secs = 4 * 3600  # 4 hours in seconds

        # Check if a session with this context already exists
        existing = WorkSession.objects.filter(
            user=user,
            context_content_type=person_ct,
            context_object_id=str(person.pk),
            stopped_at__isnull=False,
        ).exists()

        if not existing:
            session1 = WorkSession.objects.create(
                user=user,
                context_content_type=person_ct,
                context_object_id=str(person.pk),
                stopped_at=now,
                duration_seconds=duration_secs,
                metadata={"task": "Completed work session"},
            )
            count += 1

        # Create an active session (only one allowed per user)
        # First check if there's already an active session
        active_exists = WorkSession.objects.filter(
            user=user,
            stopped_at__isnull=True,
            deleted_at__isnull=True,
        ).exists()

        if not active_exists:
            # Need a different context for the active session
            second_person = Person.objects.exclude(pk=person.pk).first()
            if second_person:
                session2 = WorkSession.objects.create(
                    user=user,
                    context_content_type=person_ct,
                    context_object_id=str(second_person.pk),
                    stopped_at=None,
                    duration_seconds=None,
                    metadata={"task": "Currently working"},
                )
                count += 1

    return count


def verify():
    """Verify worklog constraints with negative writes."""
    results = []

    user = User.objects.filter(username="staff_testbed").first()
    if not user:
        user = User.objects.first()

    person = Person.objects.first()
    if not person:
        results.append(("worklog_tests", None, "Skipped - no person"))
        return results

    person_ct = ContentType.objects.get_for_model(Person)

    if user:
        # Test 1: Only one active session per user
        active_session = WorkSession.objects.filter(
            user=user,
            stopped_at__isnull=True,
            deleted_at__isnull=True,
        ).first()

        if active_session:
            try:
                with transaction.atomic():
                    WorkSession.objects.create(
                        user=user,
                        context_content_type=person_ct,
                        context_object_id=str(person.pk),
                        stopped_at=None,  # Another active session - should fail
                        duration_seconds=None,
                    )
                results.append(("unique_active_session_per_user", False, "Should have raised IntegrityError"))
            except IntegrityError:
                results.append(("unique_active_session_per_user", True, "Correctly rejected"))
        else:
            results.append(("unique_active_session_per_user", None, "Skipped - no active session"))

        # Test 2: Duration consistency (stopped_at and duration_seconds must both be null or both set)
        try:
            with transaction.atomic():
                WorkSession.objects.create(
                    user=user,
                    context_content_type=person_ct,
                    context_object_id="test-duration-stopped",
                    stopped_at=timezone.now(),  # Set
                    duration_seconds=None,  # Not set - should fail
                )
            results.append(("worksession_duration_consistency (stopped but no duration)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("worksession_duration_consistency (stopped but no duration)", True, "Correctly rejected"))

        try:
            with transaction.atomic():
                WorkSession.objects.create(
                    user=user,
                    context_content_type=person_ct,
                    context_object_id="test-duration-active",
                    stopped_at=None,  # Not set
                    duration_seconds=3600,  # Set - should fail
                )
            results.append(("worksession_duration_consistency (duration but not stopped)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("worksession_duration_consistency (duration but not stopped)", True, "Correctly rejected"))

    else:
        results.append(("worklog_tests", None, "Skipped - no user"))

    return results
