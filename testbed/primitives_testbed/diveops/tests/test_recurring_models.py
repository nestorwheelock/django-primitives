"""Tests for recurring excursion models."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone


# =============================================================================
# RecurrenceRule Model Tests
# =============================================================================


@pytest.mark.django_db
class TestRecurrenceRuleModel:
    """Tests for RecurrenceRule model."""

    def test_recurrence_rule_creation(self):
        """RecurrenceRule can be created with required fields."""
        from primitives_testbed.diveops.models import RecurrenceRule

        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=timezone.now(),
            timezone="America/Cancun",
        )
        assert rule.pk is not None
        assert rule.rrule_text == "FREQ=WEEKLY;BYDAY=SA"

    def test_weekly_rule_generates_saturdays(self):
        """Weekly Saturday rule generates correct occurrences."""
        from primitives_testbed.diveops.models import RecurrenceRule

        # Start on a Saturday
        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            timezone="America/Cancun",
        )

        # Get occurrences for January 2025
        start = datetime(2025, 1, 1, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        end = datetime(2025, 1, 31, 23, 59, tzinfo=ZoneInfo("America/Cancun"))
        occurrences = rule.get_occurrences(start, end)

        # Should have Saturdays: Jan 4, 11, 18, 25
        assert len(occurrences) == 4
        assert all(occ.weekday() == 5 for occ in occurrences)  # Saturday = 5

    def test_rule_respects_dtend(self):
        """Rule stops generating after dtend."""
        from primitives_testbed.diveops.models import RecurrenceRule

        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        dtend = datetime(2025, 1, 15, 23, 59, tzinfo=ZoneInfo("America/Cancun"))

        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            dtend=dtend,
            timezone="America/Cancun",
        )

        start = datetime(2025, 1, 1, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        end = datetime(2025, 1, 31, 23, 59, tzinfo=ZoneInfo("America/Cancun"))
        occurrences = rule.get_occurrences(start, end)

        # Should only have Jan 4 and 11 (before dtend of Jan 15)
        assert len(occurrences) == 2

    def test_daily_rule_generates_correct_count(self):
        """Daily rule generates correct number of occurrences."""
        from primitives_testbed.diveops.models import RecurrenceRule

        dtstart = datetime(2025, 1, 1, 9, 0, tzinfo=ZoneInfo("America/Cancun"))
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=DAILY",
            dtstart=dtstart,
            timezone="America/Cancun",
        )

        start = datetime(2025, 1, 1, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        end = datetime(2025, 1, 7, 23, 59, tzinfo=ZoneInfo("America/Cancun"))
        occurrences = rule.get_occurrences(start, end)

        # Should have 7 days: Jan 1-7
        assert len(occurrences) == 7

    def test_rule_with_count_limit(self):
        """RRULE COUNT parameter limits occurrences."""
        from primitives_testbed.diveops.models import RecurrenceRule

        dtstart = datetime(2025, 1, 1, 9, 0, tzinfo=ZoneInfo("America/Cancun"))
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=DAILY;COUNT=5",
            dtstart=dtstart,
            timezone="America/Cancun",
        )

        start = datetime(2025, 1, 1, 0, 0, tzinfo=ZoneInfo("America/Cancun"))
        end = datetime(2025, 1, 31, 23, 59, tzinfo=ZoneInfo("America/Cancun"))
        occurrences = rule.get_occurrences(start, end)

        # Should only have 5 occurrences despite wider window
        assert len(occurrences) == 5

    def test_rule_description_optional(self):
        """Description field is optional."""
        from primitives_testbed.diveops.models import RecurrenceRule

        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=timezone.now(),
        )
        assert rule.description == ""

        rule_with_desc = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=timezone.now(),
            description="Saturday morning dives",
        )
        assert rule_with_desc.description == "Saturday morning dives"


# =============================================================================
# RecurrenceException Model Tests
# =============================================================================


@pytest.mark.django_db
class TestRecurrenceExceptionModel:
    """Tests for RecurrenceException model."""

    @pytest.fixture
    def weekly_rule(self):
        """Create a weekly Saturday rule."""
        from primitives_testbed.diveops.models import RecurrenceRule

        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        return RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            timezone="America/Cancun",
        )

    def test_cancelled_exception_creation(self, weekly_rule):
        """Cancelled exception can be created."""
        from primitives_testbed.diveops.models import RecurrenceException

        original_start = datetime(2025, 1, 11, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        exc = RecurrenceException.objects.create(
            rule=weekly_rule,
            original_start=original_start,
            exception_type=RecurrenceException.ExceptionType.CANCELLED,
            reason="Weather conditions",
        )
        assert exc.pk is not None
        assert exc.exception_type == "cancelled"

    def test_rescheduled_exception_creation(self, weekly_rule):
        """Rescheduled exception can be created with new_start."""
        from primitives_testbed.diveops.models import RecurrenceException

        original_start = datetime(2025, 1, 11, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        new_start = datetime(2025, 1, 12, 9, 0, tzinfo=ZoneInfo("America/Cancun"))

        exc = RecurrenceException.objects.create(
            rule=weekly_rule,
            original_start=original_start,
            exception_type=RecurrenceException.ExceptionType.RESCHEDULED,
            new_start=new_start,
            reason="Moved to Sunday",
        )
        assert exc.exception_type == "rescheduled"
        assert exc.new_start == new_start

    def test_added_exception_for_extra_occurrence(self, weekly_rule):
        """Added exception creates extra occurrence."""
        from primitives_testbed.diveops.models import RecurrenceException

        # Add an extra Wednesday dive
        extra_start = datetime(2025, 1, 15, 14, 0, tzinfo=ZoneInfo("America/Cancun"))
        exc = RecurrenceException.objects.create(
            rule=weekly_rule,
            original_start=extra_start,
            exception_type=RecurrenceException.ExceptionType.ADDED,
            reason="Extra mid-week dive",
        )
        assert exc.exception_type == "added"

    def test_exception_linked_to_rule(self, weekly_rule):
        """Exception is linked to its rule via foreign key."""
        from primitives_testbed.diveops.models import RecurrenceException

        original_start = datetime(2025, 1, 11, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        exc = RecurrenceException.objects.create(
            rule=weekly_rule,
            original_start=original_start,
            exception_type=RecurrenceException.ExceptionType.CANCELLED,
        )

        assert exc.rule == weekly_rule
        assert exc in weekly_rule.exceptions.all()


# =============================================================================
# ExcursionSeries Model Tests
# =============================================================================


@pytest.mark.django_db
class TestExcursionSeriesModel:
    """Tests for ExcursionSeries model."""

    @pytest.fixture
    def dive_shop(self):
        """Create a dive shop organization."""
        from django_parties.models import Organization

        return Organization.objects.create(
            name="Test Dive Shop",
            org_type="dive_shop",
        )

    @pytest.fixture
    def excursion_type(self, dive_shop):
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
    def recurrence_rule(self):
        """Create a recurrence rule."""
        from primitives_testbed.diveops.models import RecurrenceRule

        dtstart = datetime(2025, 1, 4, 8, 0, tzinfo=ZoneInfo("America/Cancun"))
        return RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=dtstart,
            timezone="America/Cancun",
        )

    def test_series_creation_with_defaults(self, dive_shop, excursion_type, recurrence_rule):
        """ExcursionSeries can be created with required fields."""
        from primitives_testbed.diveops.models import ExcursionSeries

        series = ExcursionSeries.objects.create(
            name="Saturday Morning Dives",
            dive_shop=dive_shop,
            recurrence_rule=recurrence_rule,
            excursion_type=excursion_type,
        )

        assert series.pk is not None
        assert series.name == "Saturday Morning Dives"
        assert series.status == "draft"  # Default
        assert series.window_days == 60  # Default
        assert series.capacity_default == 12  # Default
        assert series.duration_minutes == 240  # Default (4 hours)

    def test_series_status_choices(self, dive_shop, excursion_type, recurrence_rule):
        """Series can have different status values."""
        from primitives_testbed.diveops.models import ExcursionSeries, RecurrenceRule

        for status in ["draft", "active", "paused", "retired"]:
            series = ExcursionSeries.objects.create(
                name=f"Series {status}",
                dive_shop=dive_shop,
                recurrence_rule=RecurrenceRule.objects.create(
                    rrule_text="FREQ=DAILY",
                    dtstart=timezone.now(),
                ),
                excursion_type=excursion_type,
                status=status,
            )
            assert series.status == status

    def test_series_links_to_recurrence_rule(self, dive_shop, excursion_type, recurrence_rule):
        """Series is linked to recurrence rule."""
        from primitives_testbed.diveops.models import ExcursionSeries

        series = ExcursionSeries.objects.create(
            name="Weekly Dives",
            dive_shop=dive_shop,
            recurrence_rule=recurrence_rule,
            excursion_type=excursion_type,
        )

        assert series.recurrence_rule == recurrence_rule
        assert series.recurrence_rule.rrule_text == "FREQ=WEEKLY;BYDAY=SA"

    def test_series_with_custom_defaults(self, dive_shop, excursion_type, recurrence_rule):
        """Series can have custom default values."""
        from primitives_testbed.diveops.models import ExcursionSeries

        series = ExcursionSeries.objects.create(
            name="Premium Dives",
            dive_shop=dive_shop,
            recurrence_rule=recurrence_rule,
            excursion_type=excursion_type,
            capacity_default=8,
            price_default=Decimal("200.00"),
            currency="MXN",
            duration_minutes=300,
            meeting_place="Marina dock #3",
            notes="VIP experience",
        )

        assert series.capacity_default == 8
        assert series.price_default == Decimal("200.00")
        assert series.currency == "MXN"
        assert series.duration_minutes == 300
        assert series.meeting_place == "Marina dock #3"

    def test_series_soft_delete(self, dive_shop, excursion_type, recurrence_rule):
        """Series supports soft delete."""
        from primitives_testbed.diveops.models import ExcursionSeries

        series = ExcursionSeries.objects.create(
            name="To Be Deleted",
            dive_shop=dive_shop,
            recurrence_rule=recurrence_rule,
            excursion_type=excursion_type,
        )

        series.delete()
        series.refresh_from_db()

        assert series.deleted_at is not None
        # Should not appear in default queryset
        assert ExcursionSeries.objects.filter(pk=series.pk).count() == 0


# =============================================================================
# Excursion Model Updates Tests
# =============================================================================


@pytest.mark.django_db
class TestExcursionSeriesLinkage:
    """Tests for Excursion model series linkage."""

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
    def dive_site(self):
        """Create a dive site."""
        from primitives_testbed.diveops.models import DiveSite
        from django_geo.models import Place

        place = Place.objects.create(
            name="Test Location",
            place_type="reef",
            latitude=20.5,
            longitude=-87.4,
        )
        return DiveSite.objects.create(
            name="Test Reef",
            place=place,
            max_depth_meters=30,
            difficulty="intermediate",
            dive_mode="boat",
        )

    def test_excursion_series_field_nullable(self, dive_shop, dive_site, user):
        """Excursion.series field is nullable (for standalone excursions)."""
        from primitives_testbed.diveops.models import Excursion

        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now(),
            return_time=timezone.now() + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=user,
        )

        assert excursion.series is None
        assert excursion.is_override is False

    def test_excursion_linked_to_series(self, dive_shop, dive_site, user):
        """Excursion can be linked to a series."""
        from primitives_testbed.diveops.models import (
            Excursion,
            ExcursionSeries,
            ExcursionType,
            RecurrenceRule,
        )

        # Create series
        rule = RecurrenceRule.objects.create(
            rrule_text="FREQ=WEEKLY;BYDAY=SA",
            dtstart=timezone.now(),
        )
        excursion_type = ExcursionType.objects.create(
            name="Morning Dive",
            slug="morning-dive",
            dive_mode="boat",
            time_of_day="day",
            base_price=Decimal("150.00"),
        )
        series = ExcursionSeries.objects.create(
            name="Weekly Dives",
            dive_shop=dive_shop,
            recurrence_rule=rule,
            excursion_type=excursion_type,
        )

        # Create excursion linked to series
        occurrence_start = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=occurrence_start,
            return_time=occurrence_start + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            series=series,
            occurrence_start=occurrence_start,
            created_by=user,
        )

        assert excursion.series == series
        assert excursion.occurrence_start == occurrence_start
        assert excursion in series.excursions.all()

    def test_excursion_is_override_field(self, dive_shop, dive_site, user):
        """Excursion.is_override field tracks individual modifications."""
        from primitives_testbed.diveops.models import Excursion

        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now(),
            return_time=timezone.now() + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            is_override=True,
            override_fields={"max_divers": True, "price_per_diver": True},
            created_by=user,
        )

        assert excursion.is_override is True
        assert excursion.override_fields == {"max_divers": True, "price_per_diver": True}


