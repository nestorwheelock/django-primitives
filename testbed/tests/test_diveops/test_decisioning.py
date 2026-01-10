"""Tests for diveops decisioning (eligibility checks)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import models
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

    def test_ineligible_certification_returns_reasons(self, dive_site, dive_shop, user, person2, padi_agency):
        """Diver without required certification returns allowed=False with reasons."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            DiverProfile,
            Excursion,
            ExcursionRequirement,
        )

        # Create AOW and OW certification levels
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow", name="Advanced Open Water", rank=3
        )
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow", name="Open Water", rank=2
        )

        # Create trip with AOW requirement
        tomorrow = timezone.now() + timedelta(days=1)
        trip = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=user,
        )
        ExcursionRequirement.objects.create(
            excursion=trip, requirement_type="certification", certification_level=aow_level, is_mandatory=True
        )

        # Create diver with only OW certification
        diver = DiverProfile.objects.create(
            person=person2,
            total_dives=10,
            medical_clearance_date=date.today(),
            medical_clearance_valid_until=date.today() + timedelta(days=365),
        )
        DiverCertification.objects.create(
            diver=diver, level=ow_level, card_number="12345", issued_on=date.today() - timedelta(days=30)
        )

        result = can_diver_join_trip(
            diver=diver,
            trip=trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("certification" in reason.lower() for reason in result.reasons)
        assert any("aow" in action.lower() or "advanced" in action.lower() for action in result.required_actions)

    def test_expired_medical_returns_reasons(self, dive_trip, person2, padi_agency):
        """Diver with expired medical clearance returns allowed=False."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverProfile

        # Create diver with expired medical
        diver = DiverProfile.objects.create(
            person=person2,
            certification_level="aow",
            certification_agency=padi_agency,
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

    def test_no_medical_on_file_returns_reasons(self, dive_trip, person2, padi_agency):
        """Diver with no medical clearance returns allowed=False."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverProfile

        # Create diver with no medical
        diver = DiverProfile.objects.create(
            person=person2,
            certification_level="aow",
            certification_agency=padi_agency,
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
        from primitives_testbed.diveops.models import Excursion

        yesterday = timezone.now() - timedelta(days=1)
        trip = Excursion.objects.create(
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

    def test_multiple_failures_returns_all_reasons(self, dive_site, dive_shop, person2, user, padi_agency):
        """Multiple eligibility failures return all reasons."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            DiverProfile,
            Excursion,
            ExcursionRequirement,
        )

        # Create AOW and OW certification levels
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow", name="Advanced Open Water", rank=3
        )
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow", name="Open Water", rank=2
        )

        # Create diver with multiple issues: OW cert (not advanced enough) AND expired medical
        diver = DiverProfile.objects.create(
            person=person2,
            total_dives=4,
            medical_clearance_date=date.today() - timedelta(days=400),
            medical_clearance_valid_until=date.today() - timedelta(days=35),  # Expired
        )
        # Add OW certification (not advanced enough for AOW requirement)
        DiverCertification.objects.create(
            diver=diver, level=ow_level, card_number="12345", issued_on=date.today() - timedelta(days=30)
        )

        # Create trip with AOW requirement
        tomorrow = timezone.now() + timedelta(days=1)
        trip = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=user,
        )
        # Add AOW requirement to trip
        ExcursionRequirement.objects.create(
            excursion=trip, requirement_type="certification", certification_level=aow_level, is_mandatory=True
        )

        result = can_diver_join_trip(
            diver=diver,
            trip=trip,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        # Should have at least 2 reasons (certification + medical)
        assert len(result.reasons) >= 2

    def test_as_of_parameter_evaluates_at_point_in_time(self, dive_trip, person2, padi_agency):
        """as_of parameter evaluates eligibility at that point in time."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverProfile

        # Create diver whose medical will expire tomorrow
        tomorrow = date.today() + timedelta(days=1)
        diver = DiverProfile.objects.create(
            person=person2,
            certification_level="aow",
            certification_agency=padi_agency,
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


@pytest.mark.django_db
class TestExcursionRequirementDecisioning:
    """Tests for ExcursionRequirement-based eligibility checks."""

    @pytest.fixture
    def padi_agency(self):
        """Create PADI certification agency."""
        from django_parties.models import Organization

        return Organization.objects.create(
            name="PADI",
            org_type="other",
        )

    @pytest.fixture
    def aow_level(self, padi_agency):
        """Create Advanced Open Water certification level."""
        from primitives_testbed.diveops.models import CertificationLevel

        return CertificationLevel.objects.create(
            agency=padi_agency,
            code="aow",
            name="Advanced Open Water",
            rank=3,
        )

    @pytest.fixture
    def ow_level(self, padi_agency):
        """Create Open Water certification level."""
        from primitives_testbed.diveops.models import CertificationLevel

        return CertificationLevel.objects.create(
            agency=padi_agency,
            code="ow",
            name="Open Water",
            rank=2,
        )

    @pytest.fixture
    def trip_with_aow_requirement(self, dive_trip, aow_level):
        """Create trip with AOW certification requirement."""
        from primitives_testbed.diveops.models import ExcursionRequirement

        ExcursionRequirement.objects.create(
            excursion=dive_trip,
            requirement_type="certification",
            certification_level=aow_level,
            is_mandatory=True,
        )
        return dive_trip

    def test_diver_with_higher_cert_meets_requirement(
        self, trip_with_aow_requirement, diver_profile, aow_level, ow_level, padi_agency
    ):
        """Diver with higher certification meets lower requirement."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import CertificationLevel, DiverCertification

        # Create DM level (higher than AOW) - now requires agency
        dm_level = CertificationLevel.objects.create(
            agency=padi_agency, code="dm", name="Divemaster", rank=5
        )

        # Give diver DM certification - agency derived from level.agency
        DiverCertification.objects.create(
            diver=diver_profile,
            level=dm_level,
            card_number="DM123",
            issued_on=date.today() - timedelta(days=365),
        )

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=trip_with_aow_requirement,
            as_of=timezone.now(),
        )

        assert result.allowed is True

    def test_diver_with_exact_cert_meets_requirement(
        self, trip_with_aow_requirement, diver_profile, aow_level, padi_agency
    ):
        """Diver with exact certification meets requirement."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverCertification

        # Give diver AOW certification - agency derived from level.agency
        DiverCertification.objects.create(
            diver=diver_profile,
            level=aow_level,
            card_number="AOW123",
            issued_on=date.today() - timedelta(days=180),
        )

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=trip_with_aow_requirement,
            as_of=timezone.now(),
        )

        assert result.allowed is True

    def test_diver_with_lower_cert_fails_requirement(
        self, trip_with_aow_requirement, diver_profile, ow_level, padi_agency
    ):
        """Diver with lower certification fails requirement."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverCertification

        # Give diver only OW certification (lower than required AOW)
        DiverCertification.objects.create(
            diver=diver_profile,
            level=ow_level,
            card_number="OW123",
            issued_on=date.today() - timedelta(days=365),
        )

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=trip_with_aow_requirement,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("certification" in r.lower() for r in result.reasons)

    def test_diver_with_no_certifications_fails_requirement(
        self, trip_with_aow_requirement, diver_profile
    ):
        """Diver with no certifications fails requirement."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=trip_with_aow_requirement,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("certification" in r.lower() for r in result.reasons)

    def test_expired_certification_not_counted(
        self, trip_with_aow_requirement, diver_profile, aow_level, padi_agency
    ):
        """Expired certification is not counted for requirements."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverCertification

        # Give diver expired AOW certification
        DiverCertification.objects.create(
            diver=diver_profile,
            level=aow_level,
            card_number="AOW123",
            issued_on=date.today() - timedelta(days=730),
            expires_on=date.today() - timedelta(days=30),  # Expired
        )

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=trip_with_aow_requirement,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        assert any("certification" in r.lower() for r in result.reasons)

    def test_required_actions_include_level_details(
        self, trip_with_aow_requirement, diver_profile, ow_level, padi_agency
    ):
        """Required actions include specific certification level details."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverCertification

        # Give diver only OW certification
        DiverCertification.objects.create(
            diver=diver_profile,
            level=ow_level,
            card_number="OW123",
            issued_on=date.today() - timedelta(days=365),
        )

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=trip_with_aow_requirement,
            as_of=timezone.now(),
        )

        assert result.allowed is False
        # Required actions should mention the specific level needed
        assert any("advanced open water" in action.lower() for action in result.required_actions)

    def test_experience_requirement_checked(self, dive_trip, diver_profile, padi_agency, aow_level):
        """Experience requirement is checked."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverCertification, ExcursionRequirement

        # Add experience requirement
        ExcursionRequirement.objects.create(
            excursion=dive_trip,
            requirement_type="experience",
            min_dives=50,
            is_mandatory=True,
        )

        # Give diver certification but not enough dives
        DiverCertification.objects.create(
            diver=diver_profile,
            level=aow_level,
            card_number="AOW123",
            issued_on=date.today() - timedelta(days=180),
        )

        # Diver has only default dives (from fixture)
        result = can_diver_join_trip(
            diver=diver_profile,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        # Should fail if diver has fewer than 50 dives
        if diver_profile.total_dives < 50:
            assert result.allowed is False
            assert any("experience" in r.lower() or "dives" in r.lower() for r in result.reasons)

    def test_trip_without_requirements_allows_any_certified_diver(
        self, dive_trip, diver_profile, ow_level, padi_agency
    ):
        """Trip without ExcursionRequirements allows any certified diver."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverCertification

        # Give diver basic OW certification
        DiverCertification.objects.create(
            diver=diver_profile,
            level=ow_level,
            card_number="OW123",
            issued_on=date.today() - timedelta(days=365),
        )

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        assert result.allowed is True

    def test_optional_requirements_dont_block(
        self, dive_trip, diver_profile, aow_level, ow_level, padi_agency
    ):
        """Optional (non-mandatory) requirements don't block eligibility."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiverCertification, ExcursionRequirement

        # Add optional AOW requirement
        ExcursionRequirement.objects.create(
            excursion=dive_trip,
            requirement_type="certification",
            certification_level=aow_level,
            is_mandatory=False,  # Optional
        )

        # Give diver only OW certification
        DiverCertification.objects.create(
            diver=diver_profile,
            level=ow_level,
            card_number="OW123",
            issued_on=date.today() - timedelta(days=365),
        )

        result = can_diver_join_trip(
            diver=diver_profile,
            trip=dive_trip,
            as_of=timezone.now(),
        )

        # Should be allowed since requirement is optional
        assert result.allowed is True
