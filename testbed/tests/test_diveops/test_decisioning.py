"""Tests for diveops decisioning (eligibility checks)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


@pytest.mark.django_db
class TestCanDiverJoinTrip:
    """Tests for can_diver_join_trip eligibility decisioning."""

    def test_eligible_diver_returns_allowed(self, dive_trip, diver_profile):
        """Eligible diver returns allowed=True with no required actions."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        assert result.allowed is True
        assert len(result.reasons) == 0
        assert len(result.required_actions) == 0

    def test_ineligible_certification_returns_reasons(self, deep_site, beginner_diver, dive_shop, user):
        """Diver without required certification returns allowed=False with reasons."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiveTrip

        tomorrow = timezone.now() + timedelta(days=1)
        trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=deep_site,  # Requires AOW
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=user,
        )

        result = can_diver_join_trip(
            diver=beginner_diver,
            trip=trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("certification" in reason.lower() for reason in result.reasons)
        assert any("aow" in action.lower() or "advanced" in action.lower() for action in result.required_actions)

    def test_expired_medical_returns_reasons(self, dive_trip, person2):
        """Diver with expired medical clearance returns allowed=False."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverProfile

        # Create diver with expired medical
        diver = DiverProfile.objects.create(
            person=person2,
            certification_level="aow",
            certification_agency="PADI",
            certification_number="12345",
            certification_date=date.today() - timedelta(days=365),
            total_dives=50,
            medical_clearance_date=date.today() - timedelta(days=400),
            medical_clearance_valid_until=date.today() - timedelta(days=35),  # Expired
        )

        result = can_diver_join_trip(
            diver=diver,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("medical" in reason.lower() for reason in result.reasons)
        assert any("medical" in action.lower() for action in result.required_actions)

    def test_no_medical_on_file_returns_reasons(self, dive_trip, person2):
        """Diver with no medical clearance returns allowed=False."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverProfile

        # Create diver with no medical
        diver = DiverProfile.objects.create(
            person=person2,
            certification_level="aow",
            certification_agency="PADI",
            certification_number="12345",
            certification_date=date.today() - timedelta(days=365),
            total_dives=50,
            # No medical clearance dates
        )

        result = can_diver_join_trip(
            diver=diver,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("medical" in reason.lower() for reason in result.reasons)

    def test_full_trip_returns_reasons(self, full_trip, beginner_diver):
        """Full trip returns allowed=False with capacity reason."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip

        result = can_diver_join_trip(
            diver=beginner_diver,
            trip=full_trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("capacity" in reason.lower() or "full" in reason.lower() for reason in result.reasons)

    def test_cancelled_trip_returns_reasons(self, dive_trip, diver_profile):
        """Cancelled trip returns allowed=False."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip

        dive_trip.status = "cancelled"
        dive_trip.save()

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("cancelled" in reason.lower() for reason in result.reasons)

    def test_past_trip_returns_reasons(self, dive_shop, dive_site, diver_profile, user):
        """Past trip returns allowed=False."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiveTrip

        yesterday = timezone.now() - timedelta(days=1)
        trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=yesterday,
            return_time=yesterday + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("past" in reason.lower() or "departed" in reason.lower() for reason in result.reasons)

    def test_multiple_failures_returns_all_reasons(self, deep_site, dive_shop, person2, user):
        """Multiple eligibility failures return all reasons."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverProfile, DiveTrip

        # Create diver with multiple issues
        diver = DiverProfile.objects.create(
            person=person2,
            certification_level="ow",  # Not advanced enough
            certification_agency="PADI",
            certification_number="12345",
            certification_date=date.today() - timedelta(days=30),
            total_dives=4,
            medical_clearance_date=date.today() - timedelta(days=400),
            medical_clearance_valid_until=date.today() - timedelta(days=35),  # Expired
        )

        tomorrow = timezone.now() + timedelta(days=1)
        trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=deep_site,  # Requires AOW
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=user,
        )

        result = can_diver_join_trip(
            diver=diver,
            trip=trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        # Should have at least 2 reasons (certification + medical)
        assert len(result.reasons) >= 2

    def test_as_of_parameter_evaluates_at_point_in_time(self, dive_trip, person2):
        """as_of parameter evaluates eligibility at that point in time."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverProfile

        # Create diver whose medical will expire tomorrow
        tomorrow = date.today() + timedelta(days=1)
        diver = DiverProfile.objects.create(
            person=person2,
            certification_level="aow",
            certification_agency="PADI",
            certification_number="12345",
            certification_date=date.today() - timedelta(days=365),
            total_dives=50,
            medical_clearance_date=date.today() - timedelta(days=364),
            medical_clearance_valid_until=tomorrow,  # Expires tomorrow
        )

        # Check eligibility today (should be allowed)
        result_today = can_diver_join_trip(
            diver=diver,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        # Check eligibility in 2 days (should not be allowed)
        result_future = can_diver_join_trip(
            diver=diver,
            trip=dive_trip,
            as_of=timezone.now() + timedelta(days=2),
        )

        assert result_today.allowed is True
        assert result_future.allowed is False


@pytest.mark.django_db
class TestEligibilityResult:
    """Tests for EligibilityResult dataclass."""

    def test_eligibility_result_structure(self, dive_trip, diver_profile):
        """EligibilityResult has expected structure."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        # Check result has expected attributes
        assert hasattr(result, "allowed")
        assert hasattr(result, "reasons")
        assert hasattr(result, "required_actions")

        # Check types
        assert isinstance(result.allowed, bool)
        assert isinstance(result.reasons, list)
        assert isinstance(result.required_actions, list)
