"""Tests for Marine Park models.

TDD tests for:
- MarinePark: Marine protected area with regulatory authority
- ParkZone: Zones within a park with specific rules
- ParkRule: Effective-dated enforceable rules
- ParkFeeSchedule / ParkFeeTier: Stratified fee tiers
- DiverEligibilityProof: Verified proof for fee tier eligibility
- ParkGuideCredential: Permission to guide in park areas
- VesselPermit: Per-park vessel permits
- DiveSite updates: marine_park and park_zone FKs
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError


# === Fixtures ===


@pytest.fixture
def place(db):
    """Create a Place for marine park center."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Parque Nacional Centro",
        latitude=Decimal("20.867"),
        longitude=Decimal("-86.867"),
    )


@pytest.fixture
def dive_site_place(db):
    """Create a Place for dive site."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Reef Location",
        latitude=Decimal("20.870"),
        longitude=Decimal("-86.870"),
    )


@pytest.fixture
def padi_agency(db):
    """Create PADI certification agency."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="PADI",
        org_type="certification_agency",
    )


@pytest.fixture
def dive_shop(db):
    """Create a dive shop organization."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Test Dive Shop",
        org_type="dive_shop",
    )


@pytest.fixture
def cert_level_dm(db, padi_agency):
    """Create Divemaster certification level (rank 5)."""
    from primitives_testbed.diveops.models import CertificationLevel

    return CertificationLevel.objects.create(
        agency=padi_agency,
        code="dm",
        name="Divemaster",
        rank=5,
        max_depth_m=40,
    )


@pytest.fixture
def cert_level_ow(db, padi_agency):
    """Create Open Water certification level (rank 2)."""
    from primitives_testbed.diveops.models import CertificationLevel

    return CertificationLevel.objects.create(
        agency=padi_agency,
        code="ow",
        name="Open Water Diver",
        rank=2,
        max_depth_m=18,
    )


# === MarinePark Model Tests ===


@pytest.mark.django_db
class TestMarineParkModel:
    """Tests for MarinePark model creation and validation."""

    def test_marine_park_creation_minimal(self, db):
        """MarinePark can be created with minimal required fields."""
        from primitives_testbed.diveops.models import MarinePark

        park = MarinePark.objects.create(
            name="Parque Nacional Arrecife de Puerto Morelos",
            code="pnapm",
        )
        assert park.pk is not None
        assert park.name == "Parque Nacional Arrecife de Puerto Morelos"
        assert park.code == "pnapm"
        assert park.is_active is True

    def test_marine_park_creation_full(self, place):
        """MarinePark can be created with all fields."""
        from primitives_testbed.diveops.models import MarinePark

        park = MarinePark.objects.create(
            name="Parque Nacional Arrecife de Puerto Morelos",
            code="pnapm",
            description="Marine park in Puerto Morelos, Mexico",
            place=place,
            governing_authority="CONANP",
            authority_contact="contact@conanp.gob.mx",
            official_website="https://conanp.gob.mx",
            established_date=date(1998, 2, 2),
            designation_type="national_park",
            max_divers_per_site=10,
        )
        assert park.governing_authority == "CONANP"
        assert park.established_date == date(1998, 2, 2)
        assert park.designation_type == "national_park"
        assert park.max_divers_per_site == 10

    def test_marine_park_code_unique(self, db):
        """MarinePark.code must be unique."""
        from primitives_testbed.diveops.models import MarinePark

        MarinePark.objects.create(name="Park 1", code="park1")
        with pytest.raises(IntegrityError):
            MarinePark.objects.create(name="Park 2", code="park1")

    def test_marine_park_boundary_file_optional(self, db):
        """MarinePark.boundary_file is optional."""
        from primitives_testbed.diveops.models import MarinePark

        park = MarinePark.objects.create(
            name="Test Park",
            code="test",
        )
        # FileField returns None or "" for empty file - check falsy
        assert not park.boundary_file


# === ParkZone Model Tests ===


@pytest.mark.django_db
class TestParkZoneModel:
    """Tests for ParkZone model creation and constraints."""

    @pytest.fixture
    def marine_park(self, db):
        """Create a marine park for zone tests."""
        from primitives_testbed.diveops.models import MarinePark

        return MarinePark.objects.create(
            name="Test Park",
            code="testpark",
        )

    def test_park_zone_creation(self, marine_park):
        """ParkZone can be created with required fields."""
        from primitives_testbed.diveops.models import ParkZone

        zone = ParkZone.objects.create(
            marine_park=marine_park,
            name="Zona Núcleo",
            code="nucleo",
            zone_type="core",
        )
        assert zone.pk is not None
        assert zone.marine_park == marine_park
        assert zone.zone_type == "core"

    def test_park_zone_defaults(self, marine_park):
        """ParkZone has correct default values."""
        from primitives_testbed.diveops.models import ParkZone

        zone = ParkZone.objects.create(
            marine_park=marine_park,
            name="Use Zone",
            code="use",
        )
        assert zone.zone_type == "use"
        assert zone.diving_allowed is True
        assert zone.anchoring_allowed is False
        assert zone.fishing_allowed is False
        assert zone.requires_guide is True
        assert zone.requires_permit is True
        assert zone.is_active is True

    def test_park_zone_unique_code_per_park(self, marine_park):
        """Zone code must be unique within a park."""
        from primitives_testbed.diveops.models import ParkZone

        ParkZone.objects.create(
            marine_park=marine_park,
            name="Zone 1",
            code="zone1",
        )
        with pytest.raises(IntegrityError):
            ParkZone.objects.create(
                marine_park=marine_park,
                name="Zone 1 Duplicate",
                code="zone1",
            )

    def test_park_zone_same_code_different_parks(self, marine_park):
        """Same zone code can exist in different parks."""
        from primitives_testbed.diveops.models import MarinePark, ParkZone

        other_park = MarinePark.objects.create(
            name="Other Park",
            code="other",
        )
        ParkZone.objects.create(
            marine_park=marine_park,
            name="Zone 1",
            code="zone1",
        )
        zone2 = ParkZone.objects.create(
            marine_park=other_park,
            name="Zone 1",
            code="zone1",
        )
        assert zone2.pk is not None


# === ParkRule Model Tests ===


@pytest.mark.django_db
class TestParkRuleModel:
    """Tests for ParkRule model with effective dating."""

    @pytest.fixture
    def marine_park(self, db):
        """Create a marine park for rule tests."""
        from primitives_testbed.diveops.models import MarinePark

        return MarinePark.objects.create(
            name="Test Park",
            code="testpark",
        )

    @pytest.fixture
    def zone(self, marine_park):
        """Create a zone for rule tests."""
        from primitives_testbed.diveops.models import ParkZone

        return ParkZone.objects.create(
            marine_park=marine_park,
            name="Test Zone",
            code="testzone",
        )

    def test_park_rule_creation_park_wide(self, marine_park):
        """ParkRule can be created at park level (no zone)."""
        from primitives_testbed.diveops.models import ParkRule

        rule = ParkRule.objects.create(
            marine_park=marine_park,
            rule_type="max_depth",
            applies_to="diver",
            activity="diving",
            subject="maximum depth",
            operator="lte",
            value="18",
            effective_start=date.today(),
            enforcement_level="block",
        )
        assert rule.pk is not None
        assert rule.zone is None
        assert rule.enforcement_level == "block"

    def test_park_rule_creation_zone_specific(self, marine_park, zone):
        """ParkRule can be created at zone level."""
        from primitives_testbed.diveops.models import ParkRule

        rule = ParkRule.objects.create(
            marine_park=marine_park,
            zone=zone,
            rule_type="max_divers",
            applies_to="group",
            activity="diving",
            subject="group size",
            operator="lte",
            value="6",
            effective_start=date.today(),
            enforcement_level="warn",
        )
        assert rule.zone == zone

    def test_park_rule_effective_date_required(self, marine_park):
        """ParkRule requires effective_start date."""
        from primitives_testbed.diveops.models import ParkRule

        with pytest.raises(IntegrityError):
            ParkRule.objects.create(
                marine_park=marine_park,
                rule_type="max_depth",
                applies_to="diver",
                subject="depth limit",
                # Missing effective_start
            )

    def test_park_rule_operator_enum(self, marine_park):
        """ParkRule.operator uses normalized enum values."""
        from primitives_testbed.diveops.models import ParkRule

        # Valid operators: lte, gte, eq, in, contains, required_true
        rule = ParkRule.objects.create(
            marine_park=marine_park,
            rule_type="certification",
            applies_to="diver",
            activity="diving",
            subject="nitrox certification",
            operator="required_true",
            effective_start=date.today(),
        )
        assert rule.operator == "required_true"


# === ParkFeeSchedule and ParkFeeTier Tests ===


@pytest.mark.django_db
class TestParkFeeModels:
    """Tests for ParkFeeSchedule and ParkFeeTier models."""

    @pytest.fixture
    def marine_park(self, db):
        """Create a marine park for fee tests."""
        from primitives_testbed.diveops.models import MarinePark

        return MarinePark.objects.create(
            name="Test Park",
            code="testpark",
        )

    @pytest.fixture
    def fee_schedule(self, marine_park):
        """Create a fee schedule."""
        from primitives_testbed.diveops.models import ParkFeeSchedule

        return ParkFeeSchedule.objects.create(
            marine_park=marine_park,
            name="Diver Admission 2024",
            fee_type="per_person",
            applies_to="diving",
            effective_start=date(2024, 1, 1),
            effective_end=date(2024, 12, 31),
            currency="MXN",
            collector="CONANP",
        )

    def test_fee_schedule_creation(self, fee_schedule):
        """ParkFeeSchedule can be created."""
        assert fee_schedule.pk is not None
        assert fee_schedule.fee_type == "per_person"
        assert fee_schedule.currency == "MXN"

    def test_fee_tier_creation(self, fee_schedule):
        """ParkFeeTier can be created with stratified pricing."""
        from primitives_testbed.diveops.models import ParkFeeTier

        tourist_tier = ParkFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="tourist",
            label="Tourist (Foreign)",
            amount=Decimal("280.00"),
            priority=100,
        )
        national_tier = ParkFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="national",
            label="Mexican National",
            amount=Decimal("100.00"),
            requires_proof=True,
            proof_notes="INE/IFE required",
            priority=50,
        )
        child_tier = ParkFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="child",
            label="Child (0-12)",
            amount=Decimal("0.00"),
            age_min=0,
            age_max=12,
            priority=10,
        )

        assert tourist_tier.pk is not None
        assert national_tier.requires_proof is True
        assert child_tier.age_max == 12

    def test_fee_tier_unique_per_schedule(self, fee_schedule):
        """Each tier_code can only appear once per schedule."""
        from primitives_testbed.diveops.models import ParkFeeTier

        ParkFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="tourist",
            label="Tourist",
            amount=Decimal("280.00"),
        )
        with pytest.raises(IntegrityError):
            ParkFeeTier.objects.create(
                schedule=fee_schedule,
                tier_code="tourist",
                label="Tourist Duplicate",
                amount=Decimal("300.00"),
            )

    def test_fee_tier_ordering_by_priority(self, fee_schedule):
        """Fee tiers are ordered by priority ascending."""
        from primitives_testbed.diveops.models import ParkFeeTier

        ParkFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="tourist",
            label="Tourist",
            amount=Decimal("280.00"),
            priority=100,
        )
        ParkFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="child",
            label="Child",
            amount=Decimal("0.00"),
            priority=10,
        )
        ParkFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="national",
            label="National",
            amount=Decimal("100.00"),
            priority=50,
        )

        tiers = list(fee_schedule.tiers.all())
        assert tiers[0].tier_code == "child"  # priority=10
        assert tiers[1].tier_code == "national"  # priority=50
        assert tiers[2].tier_code == "tourist"  # priority=100


# === DiverEligibilityProof Tests ===


@pytest.mark.django_db
class TestDiverEligibilityProofModel:
    """Tests for DiverEligibilityProof model."""

    @pytest.fixture
    def diver_profile(self, db, padi_agency):
        """Create a diver profile for eligibility tests."""
        from django_parties.models import Person

        from primitives_testbed.diveops.models import DiverProfile

        person = Person.objects.create(
            first_name="Test",
            last_name="Diver",
            date_of_birth=date(1990, 1, 1),
        )
        return DiverProfile.objects.create(
            person=person,
        )

    def test_eligibility_proof_creation(self, diver_profile):
        """DiverEligibilityProof can be created."""
        from primitives_testbed.diveops.models import DiverEligibilityProof

        proof = DiverEligibilityProof.objects.create(
            diver=diver_profile,
            proof_type="national_id",
        )
        assert proof.pk is not None
        assert proof.status == "pending"

    def test_eligibility_proof_is_valid_as_of_verified_no_expiry(self, diver_profile):
        """Verified proof with no expiry is always valid."""
        from django.utils import timezone

        from primitives_testbed.diveops.models import DiverEligibilityProof

        proof = DiverEligibilityProof.objects.create(
            diver=diver_profile,
            proof_type="national_id",
            status="verified",
            verified_at=timezone.now(),
            expires_at=None,
        )
        assert proof.is_valid_as_of(date.today()) is True

    def test_eligibility_proof_is_valid_as_of_expired(self, diver_profile):
        """Verified proof past expiry is not valid."""
        from django.utils import timezone

        from primitives_testbed.diveops.models import DiverEligibilityProof

        proof = DiverEligibilityProof.objects.create(
            diver=diver_profile,
            proof_type="student_id",
            status="verified",
            verified_at=timezone.now(),
            expires_at=date.today() - timedelta(days=1),
        )
        assert proof.is_valid_as_of(date.today()) is False

    def test_eligibility_proof_pending_not_valid(self, diver_profile):
        """Pending proof is not valid regardless of expiry."""
        from primitives_testbed.diveops.models import DiverEligibilityProof

        proof = DiverEligibilityProof.objects.create(
            diver=diver_profile,
            proof_type="student_id",
            status="pending",
        )
        assert proof.is_valid_as_of(date.today()) is False


# === ParkGuideCredential Tests ===


@pytest.mark.django_db
class TestParkGuideCredentialModel:
    """Tests for ParkGuideCredential model."""

    @pytest.fixture
    def marine_park(self, db):
        """Create a marine park."""
        from primitives_testbed.diveops.models import MarinePark

        return MarinePark.objects.create(
            name="Test Park",
            code="testpark",
        )

    @pytest.fixture
    def dm_diver(self, db, padi_agency, cert_level_dm):
        """Create a diver with Divemaster certification."""
        from django_parties.models import Person

        from primitives_testbed.diveops.models import DiverCertification, DiverProfile

        person = Person.objects.create(
            first_name="Dive",
            last_name="Master",
            date_of_birth=date(1985, 5, 15),
        )
        diver = DiverProfile.objects.create(person=person)
        DiverCertification.objects.create(
            diver=diver,
            level=cert_level_dm,
            issued_on=date(2020, 1, 1),
        )
        return diver

    @pytest.fixture
    def ow_diver(self, db, padi_agency, cert_level_ow):
        """Create a diver with only Open Water certification."""
        from django_parties.models import Person

        from primitives_testbed.diveops.models import DiverCertification, DiverProfile

        person = Person.objects.create(
            first_name="Open",
            last_name="Water",
            date_of_birth=date(1995, 10, 20),
        )
        diver = DiverProfile.objects.create(person=person)
        DiverCertification.objects.create(
            diver=diver,
            level=cert_level_ow,
            issued_on=date(2022, 6, 1),
        )
        return diver

    def test_guide_credential_creation_dm_diver(self, marine_park, dm_diver):
        """ParkGuideCredential can be created for DM or higher."""
        from primitives_testbed.diveops.models import ParkGuideCredential

        credential = ParkGuideCredential.objects.create(
            marine_park=marine_park,
            diver=dm_diver,
            issued_at=date.today(),
        )
        assert credential.pk is not None
        assert credential.is_active is True

    def test_guide_credential_clean_rejects_ow_diver(self, marine_park, ow_diver):
        """ParkGuideCredential.clean() rejects divers without DM+."""
        from primitives_testbed.diveops.models import ParkGuideCredential

        credential = ParkGuideCredential(
            marine_park=marine_park,
            diver=ow_diver,
            issued_at=date.today(),
        )
        with pytest.raises(ValidationError) as exc_info:
            credential.full_clean()
        assert "Divemaster" in str(exc_info.value)

    def test_guide_credential_unique_per_park(self, marine_park, dm_diver):
        """Only one credential per diver per park."""
        from primitives_testbed.diveops.models import ParkGuideCredential

        ParkGuideCredential.objects.create(
            marine_park=marine_park,
            diver=dm_diver,
            issued_at=date.today(),
        )
        with pytest.raises(IntegrityError):
            ParkGuideCredential.objects.create(
                marine_park=marine_park,
                diver=dm_diver,
                issued_at=date.today(),
            )

    def test_guide_credential_is_refresher_due(self, marine_park, dm_diver):
        """is_refresher_due property checks next_refresher_due_at."""
        from primitives_testbed.diveops.models import ParkGuideCredential

        credential = ParkGuideCredential.objects.create(
            marine_park=marine_park,
            diver=dm_diver,
            issued_at=date.today(),
            next_refresher_due_at=date.today() - timedelta(days=1),
        )
        assert credential.is_refresher_due is True

    def test_guide_credential_can_guide_in_zone_all_zones(self, marine_park, dm_diver):
        """Credential with no zone restriction can guide anywhere."""
        from primitives_testbed.diveops.models import ParkGuideCredential, ParkZone

        zone = ParkZone.objects.create(
            marine_park=marine_park,
            name="Test Zone",
            code="test",
        )
        credential = ParkGuideCredential.objects.create(
            marine_park=marine_park,
            diver=dm_diver,
            issued_at=date.today(),
        )
        # No zones assigned = can guide in all zones
        assert credential.can_guide_in_zone(zone) is True


# === VesselPermit Tests ===


@pytest.mark.django_db
class TestVesselPermitModel:
    """Tests for VesselPermit model."""

    @pytest.fixture
    def marine_park(self, db):
        """Create a marine park."""
        from primitives_testbed.diveops.models import MarinePark

        return MarinePark.objects.create(
            name="Test Park",
            code="testpark",
        )

    def test_vessel_permit_creation(self, marine_park, dive_shop):
        """VesselPermit can be created."""
        from primitives_testbed.diveops.models import VesselPermit

        permit = VesselPermit.objects.create(
            marine_park=marine_park,
            vessel_name="MV Test Boat",
            vessel_registration="TUL-123",
            operator=dive_shop,
            permit_number="PERM-001",
            issued_at=date.today(),
            expires_at=date.today() + timedelta(days=365),
            max_divers=12,
        )
        assert permit.pk is not None
        assert permit.is_active is True

    def test_vessel_permit_unique_per_park(self, marine_park, dive_shop):
        """Permit number must be unique per park."""
        from primitives_testbed.diveops.models import VesselPermit

        VesselPermit.objects.create(
            marine_park=marine_park,
            vessel_name="Boat 1",
            operator=dive_shop,
            permit_number="PERM-001",
            issued_at=date.today(),
            expires_at=date.today() + timedelta(days=365),
        )
        with pytest.raises(IntegrityError):
            VesselPermit.objects.create(
                marine_park=marine_park,
                vessel_name="Boat 2",
                operator=dive_shop,
                permit_number="PERM-001",  # Same permit number
                issued_at=date.today(),
                expires_at=date.today() + timedelta(days=365),
            )

    def test_vessel_permit_same_number_different_parks(self, marine_park, dive_shop):
        """Same permit number can exist in different parks."""
        from primitives_testbed.diveops.models import MarinePark, VesselPermit

        other_park = MarinePark.objects.create(
            name="Other Park",
            code="other",
        )
        VesselPermit.objects.create(
            marine_park=marine_park,
            vessel_name="Boat 1",
            operator=dive_shop,
            permit_number="PERM-001",
            issued_at=date.today(),
            expires_at=date.today() + timedelta(days=365),
        )
        permit2 = VesselPermit.objects.create(
            marine_park=other_park,
            vessel_name="Boat 2",
            operator=dive_shop,
            permit_number="PERM-001",  # Same number, different park
            issued_at=date.today(),
            expires_at=date.today() + timedelta(days=365),
        )
        assert permit2.pk is not None


# === DiveSite Marine Park Integration Tests ===


@pytest.mark.django_db
class TestDiveSiteMarineParkIntegration:
    """Tests for DiveSite marine_park and park_zone fields."""

    @pytest.fixture
    def marine_park(self, db):
        """Create a marine park."""
        from primitives_testbed.diveops.models import MarinePark

        return MarinePark.objects.create(
            name="Test Park",
            code="testpark",
        )

    @pytest.fixture
    def zone(self, marine_park):
        """Create a zone in the park."""
        from primitives_testbed.diveops.models import ParkZone

        return ParkZone.objects.create(
            marine_park=marine_park,
            name="Use Zone",
            code="use",
        )

    def test_dive_site_with_marine_park(self, marine_park, dive_site_place):
        """DiveSite can have a marine_park FK."""
        from primitives_testbed.diveops.models import DiveSite

        site = DiveSite.objects.create(
            name="Test Reef",
            place=dive_site_place,
            max_depth_meters=18,
            marine_park=marine_park,
        )
        assert site.marine_park == marine_park

    def test_dive_site_with_zone_requires_park(self, zone, dive_site_place):
        """DiveSite with park_zone must also have marine_park."""
        from primitives_testbed.diveops.models import DiveSite

        # DB constraint: zone requires park
        site = DiveSite.objects.create(
            name="Test Reef",
            place=dive_site_place,
            max_depth_meters=18,
            marine_park=zone.marine_park,
            park_zone=zone,
        )
        assert site.park_zone == zone

    def test_dive_site_zone_without_park_fails(self, zone, dive_site_place):
        """DiveSite cannot have park_zone without marine_park (DB constraint)."""
        from primitives_testbed.diveops.models import DiveSite

        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Test Reef",
                place=dive_site_place,
                max_depth_meters=18,
                marine_park=None,
                park_zone=zone,
            )

    def test_dive_site_zone_must_belong_to_park_clean(self, marine_park, dive_site_place):
        """DiveSite.clean() validates zone belongs to park."""
        from primitives_testbed.diveops.models import DiveSite, MarinePark, ParkZone

        other_park = MarinePark.objects.create(
            name="Other Park",
            code="other",
        )
        wrong_zone = ParkZone.objects.create(
            marine_park=other_park,
            name="Wrong Zone",
            code="wrong",
        )

        site = DiveSite(
            name="Test Reef",
            place=dive_site_place,
            max_depth_meters=18,
            marine_park=marine_park,
            park_zone=wrong_zone,  # Zone from different park
        )
        with pytest.raises(ValidationError) as exc_info:
            site.full_clean()
        assert "Zone must belong" in str(exc_info.value)
