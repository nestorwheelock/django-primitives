"""Tests for EventAsOfQuerySet and EffectiveDatedQuerySet."""
import pytest
from datetime import timedelta
from django.utils import timezone
from freezegun import freeze_time

from tests.models import EventTestModel, EffectiveDatedTestModel


@pytest.mark.django_db
class TestEventAsOfQuerySet:
    """Test suite for EventAsOfQuerySet."""

    def test_as_of_returns_events_before_timestamp(self):
        """as_of() should return events where effective_at <= timestamp."""
        now = timezone.now()
        past_1 = now - timedelta(days=2)
        past_2 = now - timedelta(days=1)

        # Create events at different times
        event1 = EventTestModel.objects.create(name="event1", effective_at=past_1)
        event2 = EventTestModel.objects.create(name="event2", effective_at=past_2)
        event3 = EventTestModel.objects.create(name="event3", effective_at=now)

        # Query as of past_2 - should include event1 and event2
        query_time = past_2
        results = EventTestModel.objects.as_of(query_time)

        assert event1 in results
        assert event2 in results
        assert event3 not in results

    def test_as_of_excludes_future_events(self):
        """as_of() should exclude events where effective_at > timestamp."""
        now = timezone.now()
        future = now + timedelta(days=1)

        # Create event in the future
        past_event = EventTestModel.objects.create(name="past", effective_at=now)
        future_event = EventTestModel.objects.create(name="future", effective_at=future)

        results = EventTestModel.objects.as_of(now)

        assert past_event in results
        assert future_event not in results

    def test_as_of_with_backdated_event(self):
        """Backdated events should be included correctly by as_of()."""
        now = timezone.now()
        backdate = now - timedelta(days=7)

        # Create backdated event (effective_at is in the past)
        backdated = EventTestModel.objects.create(
            name="backdated",
            effective_at=backdate
        )

        # Query as of 3 days ago - should include backdated event
        query_time = now - timedelta(days=3)
        results = EventTestModel.objects.as_of(query_time)

        assert backdated in results

    def test_as_of_includes_exact_timestamp(self):
        """Events with effective_at == timestamp should be included."""
        exact_time = timezone.now()
        event = EventTestModel.objects.create(name="exact", effective_at=exact_time)

        results = EventTestModel.objects.as_of(exact_time)

        assert event in results

    def test_queryset_is_chainable(self):
        """as_of() should return a queryset that can be further filtered."""
        now = timezone.now()
        past = now - timedelta(days=1)

        EventTestModel.objects.create(name="alpha", effective_at=past)
        EventTestModel.objects.create(name="beta", effective_at=past)

        results = EventTestModel.objects.as_of(now).filter(name="alpha")

        assert results.count() == 1
        assert results.first().name == "alpha"


@pytest.mark.django_db
class TestEffectiveDatedQuerySet:
    """Test suite for EffectiveDatedQuerySet."""

    def test_as_of_returns_valid_records(self):
        """as_of() should return records where valid_from <= ts AND (valid_to IS NULL OR valid_to > ts)."""
        now = timezone.now()

        # Record valid from past, no end (open-ended)
        open_ended = EffectiveDatedTestModel.objects.create(
            name="open_ended",
            valid_from=now - timedelta(days=10)
        )

        # Record valid from past to future (bounded, currently valid)
        bounded_valid = EffectiveDatedTestModel.objects.create(
            name="bounded_valid",
            valid_from=now - timedelta(days=5),
            valid_to=now + timedelta(days=5)
        )

        results = EffectiveDatedTestModel.objects.as_of(now)

        assert open_ended in results
        assert bounded_valid in results

    def test_as_of_excludes_expired(self):
        """as_of() should exclude records where valid_to < timestamp."""
        now = timezone.now()

        # Record that expired yesterday
        expired = EffectiveDatedTestModel.objects.create(
            name="expired",
            valid_from=now - timedelta(days=10),
            valid_to=now - timedelta(days=1)
        )

        results = EffectiveDatedTestModel.objects.as_of(now)

        assert expired not in results

    def test_as_of_excludes_not_yet_valid(self):
        """as_of() should exclude records where valid_from > timestamp."""
        now = timezone.now()

        # Record that starts tomorrow
        future = EffectiveDatedTestModel.objects.create(
            name="future",
            valid_from=now + timedelta(days=1)
        )

        results = EffectiveDatedTestModel.objects.as_of(now)

        assert future not in results

    def test_current_returns_now_valid(self):
        """current() should return records valid right now."""
        now = timezone.now()

        # Create a valid record
        valid_now = EffectiveDatedTestModel.objects.create(
            name="valid_now",
            valid_from=now - timedelta(days=1)
        )

        # Create an expired record
        expired = EffectiveDatedTestModel.objects.create(
            name="expired",
            valid_from=now - timedelta(days=10),
            valid_to=now - timedelta(days=1)
        )

        results = EffectiveDatedTestModel.objects.current()

        assert valid_now in results
        assert expired not in results

    def test_as_of_with_boundary_valid_to(self):
        """Records with valid_to == timestamp should be excluded (valid_to > ts)."""
        now = timezone.now()

        # Record that ends exactly at query time
        ends_now = EffectiveDatedTestModel.objects.create(
            name="ends_now",
            valid_from=now - timedelta(days=5),
            valid_to=now  # Ends exactly at query time
        )

        results = EffectiveDatedTestModel.objects.as_of(now)

        # valid_to > ts means ends_now should be EXCLUDED
        assert ends_now not in results

    def test_as_of_with_boundary_valid_from(self):
        """Records with valid_from == timestamp should be included (valid_from <= ts)."""
        now = timezone.now()

        # Record that starts exactly at query time
        starts_now = EffectiveDatedTestModel.objects.create(
            name="starts_now",
            valid_from=now
        )

        results = EffectiveDatedTestModel.objects.as_of(now)

        # valid_from <= ts means starts_now should be INCLUDED
        assert starts_now in results

    def test_queryset_is_chainable(self):
        """as_of() and current() should return querysets that can be further filtered."""
        now = timezone.now()

        EffectiveDatedTestModel.objects.create(
            name="alpha",
            valid_from=now - timedelta(days=1)
        )
        EffectiveDatedTestModel.objects.create(
            name="beta",
            valid_from=now - timedelta(days=1)
        )

        results = EffectiveDatedTestModel.objects.current().filter(name="alpha")

        assert results.count() == 1
        assert results.first().name == "alpha"
