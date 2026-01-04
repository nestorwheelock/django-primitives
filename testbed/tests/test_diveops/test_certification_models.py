"""Tests for normalized certification models."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, models
from django.utils import timezone


@pytest.mark.django_db
class TestCertificationLevel:
    """Tests for CertificationLevel model."""

    def test_create_certification_level(self):
        """CertificationLevel can be created with valid data."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            code="ow",
            name="Open Water Diver",
            rank=2,
            description="Basic scuba certification",
        )

        assert level.pk is not None
        assert level.code == "ow"
        assert level.name == "Open Water Diver"
        assert level.rank == 2
        assert level.is_active is True

    def test_code_unique_constraint(self):
        """Certification level code must be unique."""
        from primitives_testbed.diveops.models import CertificationLevel

        CertificationLevel.objects.create(
            code="ow",
            name="Open Water Diver",
            rank=2,
        )

        with pytest.raises(IntegrityError):
            CertificationLevel.objects.create(
                code="ow",  # Duplicate
                name="Another Open Water",
                rank=2,
            )

    def test_rank_positive_constraint(self):
        """Certification level rank must be positive."""
        from primitives_testbed.diveops.models import CertificationLevel

        with pytest.raises(IntegrityError):
            CertificationLevel.objects.create(
                code="invalid",
                name="Invalid Level",
                rank=0,  # Must be > 0
            )

    def test_ordering_by_rank(self):
        """Certification levels are ordered by rank."""
        from primitives_testbed.diveops.models import CertificationLevel

        dm = CertificationLevel.objects.create(code="dm", name="Divemaster", rank=5)
        ow = CertificationLevel.objects.create(code="ow", name="Open Water", rank=2)
        aow = CertificationLevel.objects.create(code="aow", name="Advanced Open Water", rank=3)

        levels = list(CertificationLevel.objects.all())
        assert levels[0].code == "ow"
        assert levels[1].code == "aow"
        assert levels[2].code == "dm"

    def test_str_representation(self):
        """CertificationLevel string is its name."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            code="ow",
            name="Open Water Diver",
            rank=2,
        )

        assert str(level) == "Open Water Diver"

    def test_soft_delete_excluded_from_default_manager(self):
        """Soft deleted levels are excluded from objects manager."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            code="deprecated",
            name="Deprecated Level",
            rank=1,
        )
        level.delete()  # Soft delete

        assert CertificationLevel.objects.filter(code="deprecated").count() == 0
        assert CertificationLevel.all_objects.filter(code="deprecated").count() == 1


@pytest.mark.django_db
class TestDiverCertification:
    """Tests for DiverCertification model."""

    @pytest.fixture
    def certification_level(self):
        from primitives_testbed.diveops.models import CertificationLevel

        return CertificationLevel.objects.create(
            code="ow",
            name="Open Water Diver",
            rank=2,
        )

    @pytest.fixture
    def certification_agency(self):
        from django_parties.models import Organization

        return Organization.objects.create(
            name="PADI",
            org_type="certification_agency",
        )

    def test_create_diver_certification(
        self, diver_profile, certification_level, certification_agency
    ):
        """DiverCertification can be created with valid data."""
        from primitives_testbed.diveops.models import DiverCertification

        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=certification_agency,
            certification_number="12345",
            certified_on=date.today() - timedelta(days=365),
        )

        assert cert.pk is not None
        assert cert.diver == diver_profile
        assert cert.level == certification_level
        assert cert.agency == certification_agency
        assert cert.is_verified is False

    def test_diver_can_have_multiple_certifications(
        self, diver_profile, certification_agency
    ):
        """A diver can have multiple certification levels."""
        from primitives_testbed.diveops.models import CertificationLevel, DiverCertification

        ow = CertificationLevel.objects.create(code="ow", name="Open Water", rank=2)
        aow = CertificationLevel.objects.create(code="aow", name="Advanced Open Water", rank=3)

        cert1 = DiverCertification.objects.create(
            diver=diver_profile,
            level=ow,
            agency=certification_agency,
            certification_number="OW123",
            certified_on=date.today() - timedelta(days=365),
        )

        cert2 = DiverCertification.objects.create(
            diver=diver_profile,
            level=aow,
            agency=certification_agency,
            certification_number="AOW456",
            certified_on=date.today() - timedelta(days=180),
        )

        assert diver_profile.certifications.count() == 2

    def test_unique_diver_level_agency_constraint(
        self, diver_profile, certification_level, certification_agency
    ):
        """Only one certification per diver+level+agency combination."""
        from primitives_testbed.diveops.models import DiverCertification

        DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=certification_agency,
            certification_number="12345",
            certified_on=date.today(),
        )

        with pytest.raises(IntegrityError):
            DiverCertification.objects.create(
                diver=diver_profile,
                level=certification_level,  # Same level
                agency=certification_agency,  # Same agency
                certification_number="99999",
                certified_on=date.today(),
            )

    def test_different_agency_same_level_allowed(
        self, diver_profile, certification_level
    ):
        """Same diver can have same level from different agencies."""
        from django_parties.models import Organization
        from primitives_testbed.diveops.models import DiverCertification

        padi = Organization.objects.create(name="PADI", org_type="certification_agency")
        ssi = Organization.objects.create(name="SSI", org_type="certification_agency")

        cert1 = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=padi,
            certification_number="PADI123",
            certified_on=date.today(),
        )

        cert2 = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=ssi,
            certification_number="SSI456",
            certified_on=date.today(),
        )

        assert cert1.pk != cert2.pk

    def test_expires_after_certified_constraint(
        self, diver_profile, certification_level, certification_agency
    ):
        """Expiration date must be after certification date."""
        from primitives_testbed.diveops.models import DiverCertification

        with pytest.raises(IntegrityError):
            DiverCertification.objects.create(
                diver=diver_profile,
                level=certification_level,
                agency=certification_agency,
                certification_number="12345",
                certified_on=date.today(),
                expires_on=date.today() - timedelta(days=1),  # Before certified_on
            )

    def test_certification_can_expire(
        self, diver_profile, certification_level, certification_agency
    ):
        """Certification with expiration date can be created."""
        from primitives_testbed.diveops.models import DiverCertification

        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=certification_agency,
            certification_number="12345",
            certified_on=date.today() - timedelta(days=365),
            expires_on=date.today() + timedelta(days=365),
        )

        assert cert.expires_on is not None

    def test_is_current_property_no_expiry(
        self, diver_profile, certification_level, certification_agency
    ):
        """Certification without expiry is always current."""
        from primitives_testbed.diveops.models import DiverCertification

        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=certification_agency,
            certification_number="12345",
            certified_on=date.today(),
            expires_on=None,
        )

        assert cert.is_current is True

    def test_is_current_property_not_expired(
        self, diver_profile, certification_level, certification_agency
    ):
        """Certification with future expiry is current."""
        from primitives_testbed.diveops.models import DiverCertification

        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=certification_agency,
            certification_number="12345",
            certified_on=date.today() - timedelta(days=365),
            expires_on=date.today() + timedelta(days=30),
        )

        assert cert.is_current is True

    def test_is_current_property_expired(
        self, diver_profile, certification_level, certification_agency
    ):
        """Certification with past expiry is not current."""
        from primitives_testbed.diveops.models import DiverCertification

        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=certification_agency,
            certification_number="12345",
            certified_on=date.today() - timedelta(days=730),
            expires_on=date.today() - timedelta(days=30),
        )

        assert cert.is_current is False

    def test_verification_fields(
        self, diver_profile, certification_level, certification_agency, user
    ):
        """Certification can be marked as verified."""
        from primitives_testbed.diveops.models import DiverCertification

        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=certification_agency,
            certification_number="12345",
            certified_on=date.today(),
            is_verified=True,
            verified_by=user,
            verified_at=timezone.now(),
        )

        assert cert.is_verified is True
        assert cert.verified_by == user
        assert cert.verified_at is not None

    def test_str_representation(
        self, diver_profile, certification_level, certification_agency
    ):
        """DiverCertification string shows diver and level."""
        from primitives_testbed.diveops.models import DiverCertification

        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=certification_level,
            agency=certification_agency,
            certification_number="12345",
            certified_on=date.today(),
        )

        expected = f"{diver_profile} - Open Water Diver (PADI)"
        assert str(cert) == expected

    def test_highest_level_queryset_method(self, diver_profile):
        """Can query for diver's highest certification level."""
        from django_parties.models import Organization
        from primitives_testbed.diveops.models import CertificationLevel, DiverCertification

        agency = Organization.objects.create(name="PADI", org_type="certification_agency")
        ow = CertificationLevel.objects.create(code="ow", name="Open Water", rank=2)
        aow = CertificationLevel.objects.create(code="aow", name="Advanced Open Water", rank=3)
        dm = CertificationLevel.objects.create(code="dm", name="Divemaster", rank=5)

        DiverCertification.objects.create(
            diver=diver_profile, level=ow, agency=agency,
            certification_number="1", certified_on=date.today()
        )
        DiverCertification.objects.create(
            diver=diver_profile, level=aow, agency=agency,
            certification_number="2", certified_on=date.today()
        )

        highest = diver_profile.certifications.order_by("-level__rank").first()
        assert highest.level.code == "aow"


@pytest.mark.django_db
class TestTripRequirement:
    """Tests for TripRequirement model."""

    @pytest.fixture
    def certification_level(self):
        from primitives_testbed.diveops.models import CertificationLevel

        return CertificationLevel.objects.create(
            code="aow",
            name="Advanced Open Water",
            rank=3,
        )

    def test_create_certification_requirement(self, dive_trip, certification_level):
        """TripRequirement for certification can be created."""
        from primitives_testbed.diveops.models import TripRequirement

        req = TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="certification",
            certification_level=certification_level,
            description="Minimum AOW certification required",
            is_mandatory=True,
        )

        assert req.pk is not None
        assert req.requirement_type == "certification"
        assert req.certification_level == certification_level
        assert req.is_mandatory is True

    def test_create_medical_requirement(self, dive_trip):
        """TripRequirement for medical can be created."""
        from primitives_testbed.diveops.models import TripRequirement

        req = TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="medical",
            description="Valid medical clearance required",
            is_mandatory=True,
        )

        assert req.pk is not None
        assert req.requirement_type == "medical"
        assert req.certification_level is None

    def test_create_gear_requirement(self, dive_trip):
        """TripRequirement for gear can be created."""
        from primitives_testbed.diveops.models import TripRequirement

        req = TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="gear",
            description="Dive computer required",
            is_mandatory=False,
        )

        assert req.pk is not None
        assert req.requirement_type == "gear"
        assert req.is_mandatory is False

    def test_create_experience_requirement(self, dive_trip):
        """TripRequirement for experience can be created."""
        from primitives_testbed.diveops.models import TripRequirement

        req = TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="experience",
            description="Minimum 50 logged dives",
            is_mandatory=True,
            min_dives=50,
        )

        assert req.pk is not None
        assert req.requirement_type == "experience"
        assert req.min_dives == 50

    def test_trip_can_have_multiple_requirements(self, dive_trip, certification_level):
        """A trip can have multiple requirements."""
        from primitives_testbed.diveops.models import TripRequirement

        TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="certification",
            certification_level=certification_level,
            description="AOW required",
            is_mandatory=True,
        )

        TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="medical",
            description="Medical clearance required",
            is_mandatory=True,
        )

        TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="experience",
            description="20 dives minimum",
            is_mandatory=False,
            min_dives=20,
        )

        assert dive_trip.requirements.count() == 3

    def test_unique_requirement_type_per_trip_constraint(self, dive_trip, certification_level):
        """Only one requirement of each type per trip (for certification, medical)."""
        from primitives_testbed.diveops.models import TripRequirement

        TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="certification",
            certification_level=certification_level,
            description="AOW required",
            is_mandatory=True,
        )

        with pytest.raises(IntegrityError):
            TripRequirement.objects.create(
                trip=dive_trip,
                requirement_type="certification",  # Duplicate type
                certification_level=certification_level,
                description="Another cert requirement",
                is_mandatory=True,
            )

    def test_mandatory_requirements_queryset(self, dive_trip, certification_level):
        """Can filter for mandatory requirements only."""
        from primitives_testbed.diveops.models import TripRequirement

        TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="certification",
            certification_level=certification_level,
            is_mandatory=True,
        )

        TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="gear",
            description="Nice to have",
            is_mandatory=False,
        )

        mandatory = dive_trip.requirements.filter(is_mandatory=True)
        assert mandatory.count() == 1
        assert mandatory.first().requirement_type == "certification"

    def test_str_representation(self, dive_trip, certification_level):
        """TripRequirement string shows trip and level name."""
        from primitives_testbed.diveops.models import TripRequirement

        req = TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="certification",
            certification_level=certification_level,
            is_mandatory=True,
        )

        # String includes level name and "required"
        assert "advanced open water" in str(req).lower()
        assert "required" in str(req).lower()

    def test_certification_level_required_for_cert_type(self, dive_trip):
        """Certification requirement should have certification_level set."""
        from primitives_testbed.diveops.models import TripRequirement

        # This tests the model validation, not a DB constraint
        req = TripRequirement(
            trip=dive_trip,
            requirement_type="certification",
            certification_level=None,  # Missing!
            is_mandatory=True,
        )

        with pytest.raises(Exception):  # ValidationError or IntegrityError
            req.full_clean()


@pytest.mark.django_db
class TestDiverCertificationQueries:
    """Tests for certification-related queries and selectors."""

    @pytest.fixture
    def setup_certifications(self, diver_profile, person2):
        """Set up test certification data."""
        from django_parties.models import Organization
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            DiverProfile,
        )

        padi = Organization.objects.create(name="PADI", org_type="certification_agency")
        ssi = Organization.objects.create(name="SSI", org_type="certification_agency")

        sd = CertificationLevel.objects.create(code="sd", name="Scuba Diver", rank=1)
        ow = CertificationLevel.objects.create(code="ow", name="Open Water", rank=2)
        aow = CertificationLevel.objects.create(code="aow", name="Advanced Open Water", rank=3)
        rescue = CertificationLevel.objects.create(code="rescue", name="Rescue Diver", rank=4)
        dm = CertificationLevel.objects.create(code="dm", name="Divemaster", rank=5)

        # Diver 1: has OW and AOW from PADI
        DiverCertification.objects.create(
            diver=diver_profile, level=ow, agency=padi,
            certification_number="OW1", certified_on=date.today() - timedelta(days=365)
        )
        DiverCertification.objects.create(
            diver=diver_profile, level=aow, agency=padi,
            certification_number="AOW1", certified_on=date.today() - timedelta(days=180)
        )

        # Diver 2: has OW from SSI, expired
        diver2 = DiverProfile.objects.create(
            person=person2,
            certification_level="ow",  # Legacy field
            certification_agency="SSI",
            certification_date=date.today(),
            total_dives=5,
        )
        DiverCertification.objects.create(
            diver=diver2, level=ow, agency=ssi,
            certification_number="OW2", certified_on=date.today() - timedelta(days=730),
            expires_on=date.today() - timedelta(days=30)  # Expired
        )

        return {
            "padi": padi,
            "ssi": ssi,
            "levels": {"sd": sd, "ow": ow, "aow": aow, "rescue": rescue, "dm": dm},
            "diver1": diver_profile,
            "diver2": diver2,
        }

    def test_diver_meets_level_true(self, setup_certifications):
        """Diver with AOW meets OW requirement."""
        diver = setup_certifications["diver1"]
        required_level = setup_certifications["levels"]["ow"]

        # Diver has AOW (rank 3), requirement is OW (rank 2)
        highest = diver.certifications.order_by("-level__rank").first()
        assert highest.level.rank >= required_level.rank

    def test_diver_meets_level_false(self, setup_certifications):
        """Diver with AOW does not meet DM requirement."""
        diver = setup_certifications["diver1"]
        required_level = setup_certifications["levels"]["dm"]

        highest = diver.certifications.order_by("-level__rank").first()
        assert highest.level.rank < required_level.rank

    def test_current_certifications_filter(self, setup_certifications):
        """Can filter for current (non-expired) certifications."""
        from primitives_testbed.diveops.models import DiverCertification

        # Diver 1 has 2 current certs
        diver1 = setup_certifications["diver1"]
        current = diver1.certifications.filter(
            models.Q(expires_on__isnull=True) | models.Q(expires_on__gt=date.today())
        )
        assert current.count() == 2

        # Diver 2 has 1 expired cert
        diver2 = setup_certifications["diver2"]
        current = diver2.certifications.filter(
            models.Q(expires_on__isnull=True) | models.Q(expires_on__gt=date.today())
        )
        assert current.count() == 0

    def test_prefetch_certifications_no_n_plus_1(self, setup_certifications, django_assert_num_queries):
        """Certifications can be prefetched to avoid N+1."""
        from primitives_testbed.diveops.models import DiverProfile

        # Without prefetch: N+1 queries (one per diver for each related object)
        # With prefetch: 4 queries (divers + certifications + levels + agencies)
        # This is efficient: constant queries regardless of number of divers
        with django_assert_num_queries(4):
            divers = DiverProfile.objects.prefetch_related(
                "certifications__level", "certifications__agency"
            )
            for diver in divers:
                list(diver.certifications.all())
