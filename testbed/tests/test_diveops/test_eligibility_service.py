"""Tests for BookingEligibilityService.

Tests for certification-based eligibility checking and override support.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from primitives_testbed.diveops.models import (
    CertificationLevel,
    DiverCertification,
    DiverProfile,
    ExcursionType,
)

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Staff user for creating excursions and approving overrides."""
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def padi_agency(db):
    """PADI certification agency."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="PADI",
    )


@pytest.fixture
def cert_level_ow(db, padi_agency):
    """Open Water certification level."""
    return CertificationLevel.objects.create(
        agency=padi_agency,
        code="ow",
        name="Open Water Diver",
        rank=2,
        max_depth_m=18,
    )


@pytest.fixture
def cert_level_aow(db, padi_agency):
    """Advanced Open Water certification level."""
    return CertificationLevel.objects.create(
        agency=padi_agency,
        code="aow",
        name="Advanced Open Water Diver",
        rank=3,
        max_depth_m=30,
    )


@pytest.fixture
def cert_level_rescue(db, padi_agency):
    """Rescue Diver certification level."""
    return CertificationLevel.objects.create(
        agency=padi_agency,
        code="rescue",
        name="Rescue Diver",
        rank=4,
        max_depth_m=30,
    )


@pytest.fixture
def diver_ow(db, cert_level_ow):
    """Diver with Open Water certification."""
    from django_parties.models import Person

    person = Person.objects.create(
        first_name="Open",
        last_name="Water",
        email="ow@example.com",
    )
    diver = DiverProfile.objects.create(person=person)
    DiverCertification.objects.create(
        diver=diver,
        level=cert_level_ow,
        card_number="OW-123",
    )
    return diver


@pytest.fixture
def diver_aow(db, cert_level_aow):
    """Diver with Advanced Open Water certification."""
    from django_parties.models import Person

    person = Person.objects.create(
        first_name="Advanced",
        last_name="Diver",
        email="aow@example.com",
    )
    diver = DiverProfile.objects.create(person=person)
    DiverCertification.objects.create(
        diver=diver,
        level=cert_level_aow,
        card_number="AOW-456",
    )
    return diver


@pytest.fixture
def diver_uncertified(db):
    """Diver with no certifications."""
    from django_parties.models import Person

    person = Person.objects.create(
        first_name="No",
        last_name="Cert",
        email="nocert@example.com",
    )
    return DiverProfile.objects.create(person=person)


@pytest.fixture
def excursion_type_beginner(db, cert_level_ow):
    """Excursion type requiring Open Water certification."""
    return ExcursionType.objects.create(
        name="Beginner Reef Dive",
        slug="beginner-reef",
        dive_mode="boat",
        max_depth_meters=18,
        min_certification_level=cert_level_ow,
        base_price=Decimal("80.00"),
    )


@pytest.fixture
def excursion_type_advanced(db, cert_level_aow):
    """Excursion type requiring Advanced Open Water certification."""
    return ExcursionType.objects.create(
        name="Deep Wall Dive",
        slug="deep-wall",
        dive_mode="boat",
        max_depth_meters=30,
        min_certification_level=cert_level_aow,
        base_price=Decimal("100.00"),
    )


@pytest.fixture
def excursion_type_dsd(db):
    """Discover Scuba Diving - no certification required."""
    return ExcursionType.objects.create(
        name="Discover Scuba Diving",
        slug="dsd",
        dive_mode="shore",
        max_depth_meters=12,
        min_certification_level=None,
        requires_cert=False,
        is_training=True,
        base_price=Decimal("150.00"),
    )


@pytest.fixture
def excursion_type_no_cert_required(db):
    """Excursion type with no certification requirement."""
    return ExcursionType.objects.create(
        name="Easy Snorkel Dive",
        slug="easy-snorkel",
        dive_mode="shore",
        max_depth_meters=5,
        min_certification_level=None,
        requires_cert=True,  # Still checks, but no level required
        base_price=Decimal("50.00"),
    )


# =============================================================================
# Test: check_eligibility() function
# =============================================================================


@pytest.mark.django_db
class TestCheckEligibility:
    """Tests for check_eligibility function."""

    def test_eligible_when_diver_meets_certification(
        self, diver_ow, excursion_type_beginner
    ):
        """Diver with OW cert is eligible for OW-required excursion."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_ow, excursion_type_beginner)

        assert result.eligible is True
        assert result.reason == ""
        assert result.override_allowed is False  # No override needed

    def test_eligible_when_diver_exceeds_certification(
        self, diver_aow, excursion_type_beginner
    ):
        """Diver with AOW cert is eligible for OW-required excursion."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_aow, excursion_type_beginner)

        assert result.eligible is True
        assert result.reason == ""

    def test_not_eligible_when_diver_below_certification(
        self, diver_ow, excursion_type_advanced
    ):
        """Diver with OW cert is NOT eligible for AOW-required excursion."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_ow, excursion_type_advanced)

        assert result.eligible is False
        assert "certification" in result.reason.lower()
        assert result.override_allowed is True
        assert result.diver_rank == 2  # OW rank
        assert result.required_rank == 3  # AOW rank

    def test_not_eligible_when_uncertified_diver(
        self, diver_uncertified, excursion_type_beginner
    ):
        """Uncertified diver is NOT eligible for excursion requiring cert."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_uncertified, excursion_type_beginner)

        assert result.eligible is False
        assert "no certification" in result.reason.lower()
        assert result.override_allowed is True
        assert result.diver_rank is None
        assert result.required_rank == 2  # OW rank

    def test_eligible_for_dsd_without_certification(
        self, diver_uncertified, excursion_type_dsd
    ):
        """Uncertified diver IS eligible for DSD (requires_cert=False)."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_uncertified, excursion_type_dsd)

        assert result.eligible is True
        assert result.reason == ""

    def test_eligible_when_no_certification_required(
        self, diver_uncertified, excursion_type_no_cert_required
    ):
        """Uncertified diver IS eligible when type has no min cert level."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_uncertified, excursion_type_no_cert_required)

        assert result.eligible is True
        assert result.reason == ""

    def test_eligible_when_excursion_type_is_none(self, diver_uncertified):
        """Any diver is eligible when excursion has no type."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_uncertified, excursion_type=None)

        assert result.eligible is True
        assert result.reason == ""

    def test_result_is_immutable(self, diver_ow, excursion_type_beginner):
        """EligibilityResult is a frozen dataclass."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_ow, excursion_type_beginner)

        with pytest.raises(AttributeError):
            result.eligible = False


# =============================================================================
# Test: EligibilityResult dataclass
# =============================================================================


@pytest.mark.django_db
class TestEligibilityResult:
    """Tests for EligibilityResult value object."""

    def test_result_has_expected_fields(self, diver_ow, excursion_type_advanced):
        """EligibilityResult has all expected fields."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_ow, excursion_type_advanced)

        assert hasattr(result, "eligible")
        assert hasattr(result, "reason")
        assert hasattr(result, "override_allowed")
        assert hasattr(result, "diver_rank")
        assert hasattr(result, "required_rank")

    def test_result_str_representation(self, diver_ow, excursion_type_advanced):
        """EligibilityResult has useful string representation."""
        from primitives_testbed.diveops.eligibility_service import check_eligibility

        result = check_eligibility(diver_ow, excursion_type_advanced)

        str_repr = str(result)
        assert "eligible=False" in str_repr or "False" in str_repr


# =============================================================================
# Test: get_diver_highest_certification_rank() helper
# =============================================================================


@pytest.mark.django_db
class TestGetDiverHighestCertificationRank:
    """Tests for get_diver_highest_certification_rank helper."""

    def test_returns_highest_rank(self, db, cert_level_ow, cert_level_aow):
        """Returns highest rank when diver has multiple certifications."""
        from django_parties.models import Person

        from primitives_testbed.diveops.eligibility_service import get_diver_highest_certification_rank

        person = Person.objects.create(
            first_name="Multi",
            last_name="Cert",
            email="multi@example.com",
        )
        diver = DiverProfile.objects.create(person=person)
        DiverCertification.objects.create(diver=diver, level=cert_level_ow)
        DiverCertification.objects.create(diver=diver, level=cert_level_aow)

        rank = get_diver_highest_certification_rank(diver)

        assert rank == 3  # AOW rank is 3

    def test_returns_none_for_uncertified(self, diver_uncertified):
        """Returns None when diver has no certifications."""
        from primitives_testbed.diveops.eligibility_service import get_diver_highest_certification_rank

        rank = get_diver_highest_certification_rank(diver_uncertified)

        assert rank is None

    def test_ignores_expired_certifications(self, db, cert_level_aow):
        """Does not count expired certifications."""
        from datetime import date, timedelta

        from django_parties.models import Person

        from primitives_testbed.diveops.eligibility_service import get_diver_highest_certification_rank

        person = Person.objects.create(
            first_name="Expired",
            last_name="Cert",
            email="expired@example.com",
        )
        diver = DiverProfile.objects.create(person=person)
        # Create expired certification
        DiverCertification.objects.create(
            diver=diver,
            level=cert_level_aow,
            issued_on=date.today() - timedelta(days=365 * 3),
            expires_on=date.today() - timedelta(days=30),  # Expired
        )

        rank = get_diver_highest_certification_rank(diver)

        assert rank is None  # Expired cert not counted


# =============================================================================
# Test: record_eligibility_override() function
# =============================================================================


@pytest.mark.django_db
class TestRecordEligibilityOverride:
    """Tests for record_eligibility_override function."""

    def test_creates_audit_event_for_override(
        self, staff_user, diver_ow, excursion_type_advanced
    ):
        """Override creates audit event with correct action."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.eligibility_service import record_eligibility_override

        initial_count = AuditLog.objects.count()

        result = record_eligibility_override(
            diver=diver_ow,
            excursion_type=excursion_type_advanced,
            approver=staff_user,
            reason="Diver has equivalent experience from SSI",
        )

        assert AuditLog.objects.count() == initial_count + 1
        audit = AuditLog.objects.latest("created_at")
        assert audit.action == Actions.ELIGIBILITY_OVERRIDDEN
        assert audit.actor_user == staff_user

    def test_override_includes_reason_in_metadata(
        self, staff_user, diver_ow, excursion_type_advanced
    ):
        """Override audit event includes reason in metadata."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.eligibility_service import record_eligibility_override

        record_eligibility_override(
            diver=diver_ow,
            excursion_type=excursion_type_advanced,
            approver=staff_user,
            reason="Equivalent experience",
        )

        audit = AuditLog.objects.latest("created_at")
        assert audit.metadata["reason"] == "Equivalent experience"
        assert str(diver_ow.pk) in str(audit.metadata.get("diver_id", ""))
        assert str(excursion_type_advanced.pk) in str(
            audit.metadata.get("excursion_type_id", "")
        )

    def test_override_returns_result(
        self, staff_user, diver_ow, excursion_type_advanced
    ):
        """Override returns EligibilityOverrideResult."""
        from primitives_testbed.diveops.eligibility_service import record_eligibility_override

        result = record_eligibility_override(
            diver=diver_ow,
            excursion_type=excursion_type_advanced,
            approver=staff_user,
            reason="Equivalent experience",
        )

        assert result.success is True
        assert result.approver == staff_user
        assert result.reason == "Equivalent experience"

    def test_override_requires_reason(
        self, staff_user, diver_ow, excursion_type_advanced
    ):
        """Override fails without a reason."""
        from primitives_testbed.diveops.eligibility_service import record_eligibility_override

        with pytest.raises(ValueError, match="reason"):
            record_eligibility_override(
                diver=diver_ow,
                excursion_type=excursion_type_advanced,
                approver=staff_user,
                reason="",  # Empty reason
            )

    def test_override_requires_approver(self, diver_ow, excursion_type_advanced):
        """Override fails without an approver."""
        from primitives_testbed.diveops.eligibility_service import record_eligibility_override

        with pytest.raises(ValueError, match="approver"):
            record_eligibility_override(
                diver=diver_ow,
                excursion_type=excursion_type_advanced,
                approver=None,
                reason="Some reason",
            )


# =============================================================================
# Test: check_booking_eligibility() high-level function
# =============================================================================


@pytest.mark.django_db
class TestCheckBookingEligibility:
    """Tests for check_booking_eligibility which works with Excursion objects."""

    def test_eligible_for_excursion_without_type(
        self, db, diver_uncertified, staff_user
    ):
        """Diver is eligible for excursion without excursion_type."""
        from datetime import timedelta

        from django.utils import timezone

        from django_parties.models import Organization

        from primitives_testbed.diveops.eligibility_service import check_booking_eligibility
        from primitives_testbed.diveops.models import Excursion

        shop = Organization.objects.create(name="Test Shop")
        now = timezone.now()

        excursion = Excursion.objects.create(
            dive_shop=shop,
            excursion_type=None,  # No type
            departure_time=now + timedelta(days=1),
            return_time=now + timedelta(days=1, hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            created_by=staff_user,
        )

        result = check_booking_eligibility(diver_uncertified, excursion)

        assert result.eligible is True

    def test_uses_excursion_type_for_eligibility(
        self, db, diver_ow, excursion_type_advanced, staff_user
    ):
        """Uses excursion's type for eligibility check."""
        from datetime import timedelta

        from django.utils import timezone

        from django_parties.models import Organization

        from primitives_testbed.diveops.eligibility_service import check_booking_eligibility
        from primitives_testbed.diveops.models import Excursion

        shop = Organization.objects.create(name="Test Shop")
        now = timezone.now()

        excursion = Excursion.objects.create(
            dive_shop=shop,
            excursion_type=excursion_type_advanced,  # AOW required
            departure_time=now + timedelta(days=1),
            return_time=now + timedelta(days=1, hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            created_by=staff_user,
        )

        result = check_booking_eligibility(diver_ow, excursion)

        # OW diver not eligible for AOW excursion
        assert result.eligible is False
        assert result.override_allowed is True
