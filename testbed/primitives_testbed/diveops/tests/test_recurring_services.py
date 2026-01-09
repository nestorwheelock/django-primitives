"""Tests for recurring excursion services."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone


# =============================================================================
# sync_series_occurrences Service Tests
# =============================================================================


@pytest.mark.django_db
class TestSyncSeriesOccurrences:
    """Tests for sync_series_occurrences service."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username="teststaff",
            email="teststaff@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def dive_shop(self):
        """Create a dive shop organization."""
        from django_parties.models import Organization
        return Organization.objects.create(
            name="Test Dive Shop",
            org_type="dive_shop",
        )

    @pytest.fixture
    def excursion_type(self):
        """Create an excursion type."""
        from primitives_testbed.diveops.models import ExcursionType
        return ExcursionType.objects.create(
            name="Morning 2-Tank",
            slug="morning-2-tank",
            dive_mode="boat",
            time_of_day="day",
            base_price=Decimal("150.00"),
        )

    @pytest.fixture
    def weekly_series(self, dive_shop, excursion_type):
        """Create a weekly Saturday series."""
        from primitives_testbed.diveops.models import ExcursionSeries, RecurrenceRule

        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            timezone="America/Cancun",
        )
        return ExcursionSeries.objects.create(
            name="Saturday Morning Dives",
            dive_shop=dive_shop,
            recurrence_rule=rule,
            excursion_type=excursion_type,
            status="active",
            window_days=30,
            capacity_default=12,
            price_default=Decimal("150.00"),
            duration_minutes=240,
        )

    def test_sync_creates_excursions_in_window(self, weekly_series, user):
        """sync_series_occurrences creates excursions for occurrences in window."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion

        # Sync with a reference date of Jan 4, 2025 and 30-day window
        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        created = sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Should create excursions for Saturdays: Jan 4, 11, 18, 25, Feb 1
        assert len(created) == 5
        excursions = Excursion.objects.filter(series=weekly_series).order_by("departure_time")
        assert excursions.count() == 5

        # Verify each excursion has correct properties
        for exc in excursions:
            assert exc.dive_shop == weekly_series.dive_shop
            assert exc.max_divers == weekly_series.capacity_default
            assert exc.price_per_diver == weekly_series.price_default
            assert exc.series == weekly_series
            assert exc.occurrence_start is not None
            assert exc.created_by == user

    def test_sync_is_idempotent(self, weekly_series, user):
        """Running sync twice doesn't create duplicates."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion

        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))

        # First sync
        created1 = sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Second sync
        created2 = sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Should not create new excursions on second run
        assert len(created2) == 0
        assert Excursion.objects.filter(series=weekly_series).count() == len(created1)

    def test_sync_respects_cancelled_exception(self, weekly_series, user):
        """Sync skips occurrences with cancelled exceptions."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion, RecurrenceException

        # Add cancelled exception for Jan 11
        cancelled_date = datetime(2025, 1, 11, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        RecurrenceException.objects.create(
            rule=weekly_series.recurrence_rule,
            original_start=cancelled_date,
            exception_type=RecurrenceException.ExceptionType.CANCELLED,
            reason="Weather",
        )

        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        created = sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Should create 4 excursions (skipped Jan 11)
        assert len(created) == 4
        excursion_dates = [e.occurrence_start.date() for e in created]
        assert datetime(2025, 1, 11).date() not in excursion_dates

    def test_sync_respects_rescheduled_exception(self, weekly_series, user):
        """Sync uses new_start for rescheduled occurrences."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion, RecurrenceException

        # Reschedule Jan 11 to Jan 12
        original_start = datetime(2025, 1, 11, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        new_start = datetime(2025, 1, 12, 9, 0, tzinfo=ZoneInfo("America/Cancun"))
        RecurrenceException.objects.create(
            rule=weekly_series.recurrence_rule,
            original_start=original_start,
            exception_type=RecurrenceException.ExceptionType.RESCHEDULED,
            new_start=new_start,
            reason="Moved to Sunday",
        )

        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        created = sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Should have 5 excursions, one on Jan 12 instead of Jan 11
        assert len(created) == 5
        departure_dates = [e.departure_time.date() for e in created]
        assert datetime(2025, 1, 11).date() not in departure_dates
        assert datetime(2025, 1, 12).date() in departure_dates

    def test_sync_includes_added_exception(self, weekly_series, user):
        """Sync includes extra occurrences from added exceptions."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion, RecurrenceException

        # Add extra occurrence on Wednesday Jan 15
        extra_start = datetime(2025, 1, 15, 14, 0, tzinfo=ZoneInfo("America/Cancun"))
        RecurrenceException.objects.create(
            rule=weekly_series.recurrence_rule,
            original_start=extra_start,
            exception_type=RecurrenceException.ExceptionType.ADDED,
            reason="Extra mid-week dive",
        )

        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        created = sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Should have 6 excursions (5 Saturdays + 1 extra Wednesday)
        assert len(created) == 6
        departure_dates = [e.departure_time.date() for e in created]
        assert datetime(2025, 1, 15).date() in departure_dates

    def test_sync_preserves_excursions_with_bookings(self, weekly_series, user):
        """Sync preserves existing excursions that have bookings."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion, Booking, DiverProfile
        from django_parties.models import Person

        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))

        # First sync
        sync_series_occurrences(weekly_series, user, reference_date=reference_date)
        excursions = Excursion.objects.filter(series=weekly_series).order_by("departure_time")
        first_excursion = excursions.first()
        original_id = first_excursion.pk

        # Create a diver profile and booking on the first excursion
        person = Person.objects.create(first_name="John", last_name="Diver")
        diver = DiverProfile.objects.create(person=person)
        Booking.objects.create(
            excursion=first_excursion,
            diver=diver,
            status="confirmed",
            booked_by=user,
        )

        # Second sync - shouldn't affect booked excursion
        sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Booked excursion should still exist unchanged
        first_excursion.refresh_from_db()
        assert first_excursion.pk == original_id

    def test_sync_updates_unbooked_non_override(self, weekly_series, user):
        """Sync can update unbooked, non-override excursions when series changes."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion

        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))

        # First sync
        sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Update series defaults
        weekly_series.capacity_default = 8
        weekly_series.price_default = Decimal("175.00")
        weekly_series.save()

        # Second sync with update_existing=True
        sync_series_occurrences(weekly_series, user, reference_date=reference_date, update_existing=True)

        # Excursions should reflect new defaults
        excursions = Excursion.objects.filter(series=weekly_series)
        for exc in excursions:
            assert exc.max_divers == 8
            assert exc.price_per_diver == Decimal("175.00")

    def test_sync_preserves_override_excursions(self, weekly_series, user):
        """Sync preserves excursions marked as is_override=True."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion

        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))

        # First sync
        sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        # Mark first excursion as override with custom capacity
        first_excursion = Excursion.objects.filter(series=weekly_series).order_by("departure_time").first()
        first_excursion.max_divers = 6
        first_excursion.is_override = True
        first_excursion.override_fields = {"max_divers": True}
        first_excursion.save()

        # Update series defaults
        weekly_series.capacity_default = 10
        weekly_series.save()

        # Second sync with update_existing=True
        sync_series_occurrences(weekly_series, user, reference_date=reference_date, update_existing=True)

        # Override excursion should keep its custom value
        first_excursion.refresh_from_db()
        assert first_excursion.max_divers == 6

        # Other excursions should be updated
        other_excursions = Excursion.objects.filter(series=weekly_series, is_override=False)
        for exc in other_excursions:
            assert exc.max_divers == 10

    def test_sync_only_active_series(self, weekly_series, user):
        """Sync does nothing for non-active series."""
        from primitives_testbed.diveops.services import sync_series_occurrences
        from primitives_testbed.diveops.models import Excursion

        # Set series to draft
        weekly_series.status = "draft"
        weekly_series.save()

        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        created = sync_series_occurrences(weekly_series, user, reference_date=reference_date)

        assert len(created) == 0
        assert Excursion.objects.filter(series=weekly_series).count() == 0


# =============================================================================
# cancel_occurrence Service Tests
# =============================================================================


@pytest.mark.django_db
class TestCancelOccurrence:
    """Tests for cancel_occurrence service."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username="teststaff",
            email="teststaff@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def dive_shop(self):
        """Create a dive shop organization."""
        from django_parties.models import Organization
        return Organization.objects.create(
            name="Test Dive Shop",
            org_type="dive_shop",
        )

    @pytest.fixture
    def series_with_excursion(self, dive_shop, user):
        """Create a series with a synced excursion."""
        from primitives_testbed.diveops.models import (
            ExcursionSeries, RecurrenceRule, ExcursionType, Excursion
        )

        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            timezone="America/Cancun",
        )
        excursion_type = ExcursionType.objects.create(
            name="Morning Dive",
            slug="morning-dive-cancel",
            dive_mode="boat",
            time_of_day="day",
            base_price=Decimal("150.00"),
        )
        series = ExcursionSeries.objects.create(
            name="Weekly Dives",
            dive_shop=dive_shop,
            recurrence_rule=rule,
            excursion_type=excursion_type,
            status="active",
            capacity_default=12,
            price_default=Decimal("150.00"),
        )

        # Create excursion for Jan 11
        occurrence_start = datetime(2025, 1, 11, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            departure_time=occurrence_start,
            return_time=occurrence_start + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            series=series,
            occurrence_start=occurrence_start,
            created_by=user,
        )

        return series, excursion

    def test_cancel_creates_exception(self, series_with_excursion, user):
        """cancel_occurrence creates a RecurrenceException."""
        from primitives_testbed.diveops.services import cancel_occurrence
        from primitives_testbed.diveops.models import RecurrenceException

        series, excursion = series_with_excursion

        cancel_occurrence(excursion, reason="Weather conditions", actor=user)

        # Should have created an exception
        exception = RecurrenceException.objects.get(
            rule=series.recurrence_rule,
            original_start=excursion.occurrence_start,
        )
        assert exception.exception_type == "cancelled"
        assert exception.reason == "Weather conditions"

    def test_cancel_sets_excursion_status(self, series_with_excursion, user):
        """cancel_occurrence sets excursion.status to cancelled."""
        from primitives_testbed.diveops.services import cancel_occurrence

        series, excursion = series_with_excursion

        cancel_occurrence(excursion, reason="Weather", actor=user)

        excursion.refresh_from_db()
        assert excursion.status == "cancelled"

    def test_cancel_cancels_bookings(self, series_with_excursion, user):
        """cancel_occurrence cancels all bookings on the excursion."""
        from primitives_testbed.diveops.services import cancel_occurrence
        from primitives_testbed.diveops.models import Booking, DiverProfile
        from django_parties.models import Person

        series, excursion = series_with_excursion

        # Create diver profiles and bookings
        person1 = Person.objects.create(first_name="John", last_name="Diver")
        person2 = Person.objects.create(first_name="Jane", last_name="Diver")
        diver1 = DiverProfile.objects.create(person=person1)
        diver2 = DiverProfile.objects.create(person=person2)
        booking1 = Booking.objects.create(excursion=excursion, diver=diver1, status="confirmed", booked_by=user)
        booking2 = Booking.objects.create(excursion=excursion, diver=diver2, status="confirmed", booked_by=user)

        cancel_occurrence(excursion, reason="Weather", actor=user)

        # Bookings should be cancelled
        booking1.refresh_from_db()
        booking2.refresh_from_db()
        assert booking1.status == "cancelled"
        assert booking2.status == "cancelled"


# =============================================================================
# edit_occurrence Service Tests
# =============================================================================


@pytest.mark.django_db
class TestEditOccurrence:
    """Tests for edit_occurrence service."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username="teststaff",
            email="teststaff@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def dive_shop(self):
        """Create a dive shop organization."""
        from django_parties.models import Organization
        return Organization.objects.create(
            name="Test Dive Shop",
            org_type="dive_shop",
        )

    @pytest.fixture
    def series_with_excursions(self, dive_shop, user):
        """Create a series with synced excursions."""
        from primitives_testbed.diveops.models import ExcursionSeries, RecurrenceRule, ExcursionType
        from primitives_testbed.diveops.services import sync_series_occurrences

        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            timezone="America/Cancun",
        )
        excursion_type = ExcursionType.objects.create(
            name="Morning Dive",
            slug="morning-dive-edit",
            dive_mode="boat",
            time_of_day="day",
            base_price=Decimal("150.00"),
        )
        series = ExcursionSeries.objects.create(
            name="Weekly Dives",
            dive_shop=dive_shop,
            recurrence_rule=rule,
            excursion_type=excursion_type,
            status="active",
            capacity_default=12,
            price_default=Decimal("150.00"),
            window_days=30,
        )

        # Sync to create excursions
        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        sync_series_occurrences(series, user, reference_date=reference_date)

        return series

    def test_edit_occurrence_sets_is_override(self, series_with_excursions, user):
        """edit_occurrence marks excursion as override."""
        from primitives_testbed.diveops.services import edit_occurrence
        from primitives_testbed.diveops.models import Excursion

        excursion = Excursion.objects.filter(series=series_with_excursions).first()
        assert excursion.is_override is False

        edit_occurrence(excursion, changes={"max_divers": 8}, actor=user)

        excursion.refresh_from_db()
        assert excursion.is_override is True
        assert excursion.max_divers == 8

    def test_edit_occurrence_records_override_fields(self, series_with_excursions, user):
        """edit_occurrence tracks which fields were overridden."""
        from primitives_testbed.diveops.services import edit_occurrence
        from primitives_testbed.diveops.models import Excursion

        excursion = Excursion.objects.filter(series=series_with_excursions).first()

        edit_occurrence(
            excursion,
            changes={"max_divers": 8, "price_per_diver": Decimal("175.00")},
            actor=user,
        )

        excursion.refresh_from_db()
        assert excursion.override_fields.get("max_divers") is True
        assert excursion.override_fields.get("price_per_diver") is True

    def test_edit_occurrence_preserves_other_occurrences(self, series_with_excursions, user):
        """edit_occurrence doesn't affect other excursions in series."""
        from primitives_testbed.diveops.services import edit_occurrence
        from primitives_testbed.diveops.models import Excursion

        excursions = list(Excursion.objects.filter(series=series_with_excursions).order_by("departure_time"))
        first_excursion = excursions[0]
        second_excursion = excursions[1]

        original_capacity = second_excursion.max_divers

        edit_occurrence(first_excursion, changes={"max_divers": 6}, actor=user)

        # Second excursion should be unchanged
        second_excursion.refresh_from_db()
        assert second_excursion.max_divers == original_capacity
        assert second_excursion.is_override is False

    def test_edit_occurrence_multiple_edits(self, series_with_excursions, user):
        """Multiple edits to same occurrence accumulate override_fields."""
        from primitives_testbed.diveops.services import edit_occurrence
        from primitives_testbed.diveops.models import Excursion

        excursion = Excursion.objects.filter(series=series_with_excursions).first()

        # First edit
        edit_occurrence(excursion, changes={"max_divers": 8}, actor=user)

        # Second edit
        edit_occurrence(excursion, changes={"price_per_diver": Decimal("200.00")}, actor=user)

        excursion.refresh_from_db()
        assert excursion.max_divers == 8
        assert excursion.price_per_diver == Decimal("200.00")
        assert excursion.override_fields.get("max_divers") is True
        assert excursion.override_fields.get("price_per_diver") is True


# =============================================================================
# edit_series Service Tests
# =============================================================================


@pytest.mark.django_db
class TestEditSeries:
    """Tests for edit_series service."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username="teststaff",
            email="teststaff@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def dive_shop(self):
        """Create a dive shop organization."""
        from django_parties.models import Organization
        return Organization.objects.create(
            name="Test Dive Shop",
            org_type="dive_shop",
        )

    @pytest.fixture
    def series_with_excursions(self, dive_shop, user):
        """Create a series with synced excursions."""
        from primitives_testbed.diveops.models import ExcursionSeries, RecurrenceRule, ExcursionType
        from primitives_testbed.diveops.services import sync_series_occurrences

        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            timezone="America/Cancun",
        )
        excursion_type = ExcursionType.objects.create(
            name="Morning Dive",
            slug="morning-dive-edit-series",
            dive_mode="boat",
            time_of_day="day",
            base_price=Decimal("150.00"),
        )
        series = ExcursionSeries.objects.create(
            name="Weekly Dives",
            dive_shop=dive_shop,
            recurrence_rule=rule,
            excursion_type=excursion_type,
            status="active",
            capacity_default=12,
            price_default=Decimal("150.00"),
            window_days=30,
        )

        # Sync to create excursions
        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        sync_series_occurrences(series, user, reference_date=reference_date)

        return series

    def test_edit_series_updates_template(self, series_with_excursions, user):
        """edit_series updates the series template fields."""
        from primitives_testbed.diveops.services import edit_series

        edit_series(
            series_with_excursions,
            changes={"capacity_default": 10, "price_default": Decimal("175.00")},
            actor=user,
        )

        series_with_excursions.refresh_from_db()
        assert series_with_excursions.capacity_default == 10
        assert series_with_excursions.price_default == Decimal("175.00")

    def test_edit_series_updates_future_unbooked(self, series_with_excursions, user):
        """edit_series updates future unbooked, non-override excursions."""
        from primitives_testbed.diveops.services import edit_series
        from primitives_testbed.diveops.models import Excursion

        edit_series(
            series_with_excursions,
            changes={"capacity_default": 8},
            actor=user,
        )

        # All non-override excursions should be updated
        excursions = Excursion.objects.filter(
            series=series_with_excursions,
            is_override=False,
        )
        for exc in excursions:
            assert exc.max_divers == 8

    def test_edit_series_preserves_overrides(self, series_with_excursions, user):
        """edit_series preserves excursions marked as override."""
        from primitives_testbed.diveops.services import edit_series, edit_occurrence
        from primitives_testbed.diveops.models import Excursion

        # Mark first excursion as override
        first_excursion = Excursion.objects.filter(
            series=series_with_excursions
        ).order_by("departure_time").first()
        edit_occurrence(first_excursion, changes={"max_divers": 6}, actor=user)

        # Edit series
        edit_series(
            series_with_excursions,
            changes={"capacity_default": 10},
            actor=user,
        )

        # Override should keep its value
        first_excursion.refresh_from_db()
        assert first_excursion.max_divers == 6

        # Non-overrides should be updated
        other_excursions = Excursion.objects.filter(
            series=series_with_excursions,
            is_override=False,
        )
        for exc in other_excursions:
            assert exc.max_divers == 10

    def test_edit_series_preserves_booked(self, series_with_excursions, user):
        """edit_series preserves excursions that have bookings."""
        from primitives_testbed.diveops.services import edit_series
        from primitives_testbed.diveops.models import Excursion, Booking, DiverProfile
        from django_parties.models import Person

        # Book the first excursion
        first_excursion = Excursion.objects.filter(
            series=series_with_excursions
        ).order_by("departure_time").first()
        original_capacity = first_excursion.max_divers

        person = Person.objects.create(first_name="John", last_name="Diver")
        diver = DiverProfile.objects.create(person=person)
        Booking.objects.create(
            excursion=first_excursion,
            diver=diver,
            status="confirmed",
            booked_by=user,
        )

        # Edit series
        edit_series(
            series_with_excursions,
            changes={"capacity_default": 8},
            actor=user,
        )

        # Booked excursion should keep original value
        first_excursion.refresh_from_db()
        assert first_excursion.max_divers == original_capacity


# =============================================================================
# split_series Service Tests
# =============================================================================


@pytest.mark.django_db
class TestSplitSeries:
    """Tests for split_series service."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username="teststaff",
            email="teststaff@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def dive_shop(self):
        """Create a dive shop organization."""
        from django_parties.models import Organization
        return Organization.objects.create(
            name="Test Dive Shop",
            org_type="dive_shop",
        )

    @pytest.fixture
    def series_with_excursions(self, dive_shop, user):
        """Create a series with synced excursions."""
        from primitives_testbed.diveops.models import ExcursionSeries, RecurrenceRule, ExcursionType
        from primitives_testbed.diveops.services import sync_series_occurrences

        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            timezone="America/Cancun",
        )
        excursion_type = ExcursionType.objects.create(
            name="Morning Dive",
            slug="morning-dive-split",
            dive_mode="boat",
            time_of_day="day",
            base_price=Decimal("150.00"),
        )
        series = ExcursionSeries.objects.create(
            name="Weekly Dives",
            dive_shop=dive_shop,
            recurrence_rule=rule,
            excursion_type=excursion_type,
            status="active",
            capacity_default=12,
            price_default=Decimal("150.00"),
            window_days=30,
        )

        # Sync to create excursions
        reference_date = datetime(2025, 1, 4, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        sync_series_occurrences(series, user, reference_date=reference_date)

        return series

    def test_split_creates_new_series(self, series_with_excursions, user):
        """split_series creates a new series starting at cutoff."""
        from primitives_testbed.diveops.services import split_series
        from primitives_testbed.diveops.models import ExcursionSeries

        cutoff_date = datetime(2025, 1, 18, 0, 0, tzinfo=ZoneInfo("America/Cancun"))

        new_series = split_series(series_with_excursions, cutoff_date, actor=user)

        assert new_series is not None
        assert new_series.pk != series_with_excursions.pk
        assert new_series.name == f"{series_with_excursions.name} (from Jan 18)"
        assert new_series.dive_shop == series_with_excursions.dive_shop
        assert new_series.excursion_type == series_with_excursions.excursion_type

    def test_split_sets_original_dtend(self, series_with_excursions, user):
        """split_series sets dtend on original series recurrence rule."""
        from primitives_testbed.diveops.services import split_series

        cutoff_date = datetime(2025, 1, 18, 0, 0, tzinfo=ZoneInfo("America/Cancun"))

        split_series(series_with_excursions, cutoff_date, actor=user)

        series_with_excursions.refresh_from_db()
        series_with_excursions.recurrence_rule.refresh_from_db()

        # Original rule should end before cutoff
        assert series_with_excursions.recurrence_rule.dtend is not None
        assert series_with_excursions.recurrence_rule.dtend.date() < cutoff_date.date()

    def test_split_new_series_starts_at_cutoff(self, series_with_excursions, user):
        """New series recurrence starts at cutoff date."""
        from primitives_testbed.diveops.services import split_series

        cutoff_date = datetime(2025, 1, 18, 8, 0, tzinfo=ZoneInfo("America/Cancun"))

        new_series = split_series(series_with_excursions, cutoff_date, actor=user)

        assert new_series.recurrence_rule.dtstart == cutoff_date

    def test_split_reassigns_future_excursions(self, series_with_excursions, user):
        """split_series reassigns future excursions to new series."""
        from primitives_testbed.diveops.services import split_series
        from primitives_testbed.diveops.models import Excursion

        cutoff_date = datetime(2025, 1, 18, 0, 0, tzinfo=ZoneInfo("America/Cancun"))

        new_series = split_series(series_with_excursions, cutoff_date, actor=user)

        # Excursions before cutoff should stay with original
        past_excursions = Excursion.objects.filter(
            series=series_with_excursions,
            departure_time__lt=cutoff_date,
        )
        assert past_excursions.exists()

        # Excursions at or after cutoff should move to new series
        future_excursions = Excursion.objects.filter(
            series=new_series,
            departure_time__gte=cutoff_date,
        )
        assert future_excursions.exists()

    def test_split_preserves_past_excursions(self, series_with_excursions, user):
        """split_series doesn't modify past excursions."""
        from primitives_testbed.diveops.services import split_series
        from primitives_testbed.diveops.models import Excursion

        # Get IDs of excursions before split
        cutoff_date = datetime(2025, 1, 18, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        past_exc_ids = list(
            Excursion.objects.filter(
                series=series_with_excursions,
                departure_time__lt=cutoff_date,
            ).values_list("pk", flat=True)
        )

        split_series(series_with_excursions, cutoff_date, actor=user)

        # Past excursions should still exist and belong to original
        for exc_id in past_exc_ids:
            exc = Excursion.objects.get(pk=exc_id)
            assert exc.series == series_with_excursions
