"""Tests for Protected Area models.

TDD tests for the hierarchical ProtectedArea system:
- ProtectedArea: Hierarchical protected area (biosphere reserve, park, etc.)
- ProtectedAreaZone: Zones within an area with specific rules
- ProtectedAreaRule: Effective-dated enforceable rules with inheritance
- ProtectedAreaFeeSchedule / ProtectedAreaFeeTier: Stratified fee tiers
- DiverEligibilityProof: Verified proof for fee tier eligibility
- ProtectedAreaGuideCredential: Permission to guide in protected areas
- VesselPermit: Per-area vessel permits
- DiveSite updates: protected_area and protected_area_zone FKs
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError


# === Fixtures ===


@pytest.fixture
def place(db):
    """Create a Place for protected area center."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Protected Area Centro",
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


# === ProtectedArea Model Tests ===


@pytest.mark.django_db
class TestProtectedAreaModel:
    """Tests for ProtectedArea model creation and validation."""

    def test_protected_area_creation_minimal(self, db):
        """ProtectedArea can be created with minimal required fields."""
        from primitives_testbed.diveops.models import ProtectedArea

        area = ProtectedArea.objects.create(
            name="Parque Nacional Arrecife de Puerto Morelos",
            code="pnapm",
        )
        assert area.pk is not None
        assert area.name == "Parque Nacional Arrecife de Puerto Morelos"
        assert area.code == "pnapm"
        assert area.is_active is True
        assert area.parent is None

    def test_protected_area_creation_full(self, place):
        """ProtectedArea can be created with all fields."""
        from primitives_testbed.diveops.models import ProtectedArea

        area = ProtectedArea.objects.create(
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
        assert area.governing_authority == "CONANP"
        assert area.established_date == date(1998, 2, 2)
        assert area.designation_type == "national_park"
        assert area.max_divers_per_site == 10

    def test_protected_area_code_unique(self, db):
        """ProtectedArea.code must be unique."""
        from primitives_testbed.diveops.models import ProtectedArea

        ProtectedArea.objects.create(name="Area 1", code="area1")
        with pytest.raises(IntegrityError):
            ProtectedArea.objects.create(name="Area 2", code="area1")

    def test_protected_area_boundary_file_optional(self, db):
        """ProtectedArea.boundary_file is optional."""
        from primitives_testbed.diveops.models import ProtectedArea

        area = ProtectedArea.objects.create(
            name="Test Area",
            code="test",
        )
        assert not area.boundary_file


# === ProtectedArea Hierarchy Tests ===


@pytest.mark.django_db
class TestProtectedAreaHierarchy:
    """Tests for ProtectedArea parent/child hierarchy."""

    def test_protected_area_with_parent(self, db):
        """ProtectedArea can have a parent area."""
        from primitives_testbed.diveops.models import ProtectedArea

        biosphere = ProtectedArea.objects.create(
            name="Reserva de la Biosfera del Caribe Mexicano",
            code="rbcm",
            designation_type="biosphere_reserve",
        )
        park = ProtectedArea.objects.create(
            name="Parque Nacional Arrecife de Puerto Morelos",
            code="pnapm",
            designation_type="marine_park",
            parent=biosphere,
        )
        assert park.parent == biosphere
        assert park in biosphere.children.all()

    def test_get_ancestors_no_parent(self, db):
        """get_ancestors() returns empty list for root area."""
        from primitives_testbed.diveops.models import ProtectedArea

        area = ProtectedArea.objects.create(
            name="Root Area",
            code="root",
        )
        assert area.get_ancestors() == []

    def test_get_ancestors_single_parent(self, db):
        """get_ancestors() returns parent for child area."""
        from primitives_testbed.diveops.models import ProtectedArea

        biosphere = ProtectedArea.objects.create(
            name="Biosphere Reserve",
            code="biosphere",
            designation_type="biosphere_reserve",
        )
        park = ProtectedArea.objects.create(
            name="Marine Park",
            code="park",
            designation_type="marine_park",
            parent=biosphere,
        )
        ancestors = park.get_ancestors()
        assert len(ancestors) == 1
        assert ancestors[0] == biosphere

    def test_get_ancestors_multiple_levels(self, db):
        """get_ancestors() returns full parent chain."""
        from primitives_testbed.diveops.models import ProtectedArea

        region = ProtectedArea.objects.create(
            name="Caribbean Region",
            code="caribbean",
            designation_type="protected_area",
        )
        biosphere = ProtectedArea.objects.create(
            name="Biosphere Reserve",
            code="biosphere",
            designation_type="biosphere_reserve",
            parent=region,
        )
        park = ProtectedArea.objects.create(
            name="Marine Park",
            code="park",
            designation_type="marine_park",
            parent=biosphere,
        )
        ancestors = park.get_ancestors()
        assert len(ancestors) == 2
        assert ancestors[0] == biosphere  # immediate parent first
        assert ancestors[1] == region  # grandparent second

    def test_children_reverse_relation(self, db):
        """children relation returns child areas."""
        from primitives_testbed.diveops.models import ProtectedArea

        biosphere = ProtectedArea.objects.create(
            name="Biosphere Reserve",
            code="biosphere",
            designation_type="biosphere_reserve",
        )
        park1 = ProtectedArea.objects.create(
            name="Park 1",
            code="park1",
            parent=biosphere,
        )
        park2 = ProtectedArea.objects.create(
            name="Park 2",
            code="park2",
            parent=biosphere,
        )
        children = list(biosphere.children.all())
        assert len(children) == 2
        assert park1 in children
        assert park2 in children


# === ProtectedAreaZone Model Tests ===


@pytest.mark.django_db
class TestProtectedAreaZoneModel:
    """Tests for ProtectedAreaZone model creation and constraints."""

    @pytest.fixture
    def protected_area(self, db):
        """Create a protected area for zone tests."""
        from primitives_testbed.diveops.models import ProtectedArea

        return ProtectedArea.objects.create(
            name="Test Area",
            code="testarea",
        )

    def test_zone_creation(self, protected_area):
        """ProtectedAreaZone can be created with required fields."""
        from primitives_testbed.diveops.models import ProtectedAreaZone

        zone = ProtectedAreaZone.objects.create(
            protected_area=protected_area,
            name="Zona Núcleo",
            code="nucleo",
            zone_type="core",
        )
        assert zone.pk is not None
        assert zone.protected_area == protected_area
        assert zone.zone_type == "core"

    def test_zone_defaults(self, protected_area):
        """ProtectedAreaZone has correct default values."""
        from primitives_testbed.diveops.models import ProtectedAreaZone

        zone = ProtectedAreaZone.objects.create(
            protected_area=protected_area,
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

    def test_zone_unique_code_per_area(self, protected_area):
        """Zone code must be unique within an area."""
        from primitives_testbed.diveops.models import ProtectedAreaZone

        ProtectedAreaZone.objects.create(
            protected_area=protected_area,
            name="Zone 1",
            code="zone1",
        )
        with pytest.raises(IntegrityError):
            ProtectedAreaZone.objects.create(
                protected_area=protected_area,
                name="Zone 1 Duplicate",
                code="zone1",
            )

    def test_zone_same_code_different_areas(self, protected_area):
        """Same zone code can exist in different areas."""
        from primitives_testbed.diveops.models import ProtectedArea, ProtectedAreaZone

        other_area = ProtectedArea.objects.create(
            name="Other Area",
            code="other",
        )
        ProtectedAreaZone.objects.create(
            protected_area=protected_area,
            name="Zone 1",
            code="zone1",
        )
        zone2 = ProtectedAreaZone.objects.create(
            protected_area=other_area,
            name="Zone 1",
            code="zone1",
        )
        assert zone2.pk is not None


# === ProtectedAreaRule Model Tests ===


@pytest.mark.django_db
class TestProtectedAreaRuleModel:
    """Tests for ProtectedAreaRule model with effective dating."""

    @pytest.fixture
    def protected_area(self, db):
        """Create a protected area for rule tests."""
        from primitives_testbed.diveops.models import ProtectedArea

        return ProtectedArea.objects.create(
            name="Test Area",
            code="testarea",
        )

    @pytest.fixture
    def zone(self, protected_area):
        """Create a zone for rule tests."""
        from primitives_testbed.diveops.models import ProtectedAreaZone

        return ProtectedAreaZone.objects.create(
            protected_area=protected_area,
            name="Test Zone",
            code="testzone",
        )

    def test_rule_creation_area_wide(self, protected_area):
        """ProtectedAreaRule can be created at area level (no zone)."""
        from primitives_testbed.diveops.models import ProtectedAreaRule

        rule = ProtectedAreaRule.objects.create(
            protected_area=protected_area,
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

    def test_rule_creation_zone_specific(self, protected_area, zone):
        """ProtectedAreaRule can be created at zone level."""
        from primitives_testbed.diveops.models import ProtectedAreaRule

        rule = ProtectedAreaRule.objects.create(
            protected_area=protected_area,
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

    def test_rule_effective_date_required(self, protected_area):
        """ProtectedAreaRule requires effective_start date."""
        from primitives_testbed.diveops.models import ProtectedAreaRule

        with pytest.raises(IntegrityError):
            ProtectedAreaRule.objects.create(
                protected_area=protected_area,
                rule_type="max_depth",
                applies_to="diver",
                subject="depth limit",
                # Missing effective_start
            )

    def test_rule_operator_enum(self, protected_area):
        """ProtectedAreaRule.operator uses normalized enum values."""
        from primitives_testbed.diveops.models import ProtectedAreaRule

        rule = ProtectedAreaRule.objects.create(
            protected_area=protected_area,
            rule_type="certification",
            applies_to="diver",
            activity="diving",
            subject="nitrox certification",
            operator="required_true",
            effective_start=date.today(),
        )
        assert rule.operator == "required_true"


# === ProtectedAreaFeeSchedule and ProtectedAreaFeeTier Tests ===


@pytest.mark.django_db
class TestProtectedAreaFeeModels:
    """Tests for ProtectedAreaFeeSchedule and ProtectedAreaFeeTier models."""

    @pytest.fixture
    def protected_area(self, db):
        """Create a protected area for fee tests."""
        from primitives_testbed.diveops.models import ProtectedArea

        return ProtectedArea.objects.create(
            name="Test Area",
            code="testarea",
        )

    @pytest.fixture
    def fee_schedule(self, protected_area):
        """Create a fee schedule."""
        from primitives_testbed.diveops.models import ProtectedAreaFeeSchedule

        return ProtectedAreaFeeSchedule.objects.create(
            protected_area=protected_area,
            name="Diver Admission 2024",
            fee_type="per_person",
            applies_to="diving",
            effective_start=date(2024, 1, 1),
            effective_end=date(2024, 12, 31),
            currency="MXN",
            collector="CONANP",
        )

    def test_fee_schedule_creation(self, fee_schedule):
        """ProtectedAreaFeeSchedule can be created."""
        assert fee_schedule.pk is not None
        assert fee_schedule.fee_type == "per_person"
        assert fee_schedule.currency == "MXN"

    def test_fee_tier_creation(self, fee_schedule):
        """ProtectedAreaFeeTier can be created with stratified pricing."""
        from primitives_testbed.diveops.models import ProtectedAreaFeeTier

        tourist_tier = ProtectedAreaFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="tourist",
            label="Tourist (Foreign)",
            amount=Decimal("280.00"),
            priority=100,
        )
        national_tier = ProtectedAreaFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="national",
            label="Mexican National",
            amount=Decimal("100.00"),
            requires_proof=True,
            proof_notes="INE/IFE required",
            priority=50,
        )
        child_tier = ProtectedAreaFeeTier.objects.create(
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
        from primitives_testbed.diveops.models import ProtectedAreaFeeTier

        ProtectedAreaFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="tourist",
            label="Tourist",
            amount=Decimal("280.00"),
        )
        with pytest.raises(IntegrityError):
            ProtectedAreaFeeTier.objects.create(
                schedule=fee_schedule,
                tier_code="tourist",
                label="Tourist Duplicate",
                amount=Decimal("300.00"),
            )

    def test_fee_tier_ordering_by_priority(self, fee_schedule):
        """Fee tiers are ordered by priority ascending."""
        from primitives_testbed.diveops.models import ProtectedAreaFeeTier

        ProtectedAreaFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="tourist",
            label="Tourist",
            amount=Decimal("280.00"),
            priority=100,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=fee_schedule,
            tier_code="child",
            label="Child",
            amount=Decimal("0.00"),
            priority=10,
        )
        ProtectedAreaFeeTier.objects.create(
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


# === DiverEligibilityProof Tests (unchanged) ===


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


# === DiveSite Protected Area Integration Tests ===


@pytest.mark.django_db
class TestDiveSiteProtectedAreaIntegration:
    """Tests for DiveSite protected_area and protected_area_zone fields."""

    @pytest.fixture
    def protected_area(self, db):
        """Create a protected area."""
        from primitives_testbed.diveops.models import ProtectedArea

        return ProtectedArea.objects.create(
            name="Test Area",
            code="testarea",
        )

    @pytest.fixture
    def zone(self, protected_area):
        """Create a zone in the area."""
        from primitives_testbed.diveops.models import ProtectedAreaZone

        return ProtectedAreaZone.objects.create(
            protected_area=protected_area,
            name="Use Zone",
            code="use",
        )

    def test_dive_site_with_protected_area(self, protected_area, dive_site_place):
        """DiveSite can have a protected_area FK."""
        from primitives_testbed.diveops.models import DiveSite

        site = DiveSite.objects.create(
            name="Test Reef",
            place=dive_site_place,
            max_depth_meters=18,
            protected_area=protected_area,
        )
        assert site.protected_area == protected_area

    def test_dive_site_with_zone_requires_area(self, zone, dive_site_place):
        """DiveSite with protected_area_zone must also have protected_area."""
        from primitives_testbed.diveops.models import DiveSite

        site = DiveSite.objects.create(
            name="Test Reef",
            place=dive_site_place,
            max_depth_meters=18,
            protected_area=zone.protected_area,
            protected_area_zone=zone,
        )
        assert site.protected_area_zone == zone

    def test_dive_site_zone_without_area_fails(self, zone, dive_site_place):
        """DiveSite cannot have protected_area_zone without protected_area (DB constraint)."""
        from primitives_testbed.diveops.models import DiveSite

        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Test Reef",
                place=dive_site_place,
                max_depth_meters=18,
                protected_area=None,
                protected_area_zone=zone,
            )

    def test_dive_site_zone_must_belong_to_area_clean(self, protected_area, dive_site_place):
        """DiveSite.clean() validates zone belongs to area."""
        from primitives_testbed.diveops.models import DiveSite, ProtectedArea, ProtectedAreaZone

        other_area = ProtectedArea.objects.create(
            name="Other Area",
            code="other",
        )
        wrong_zone = ProtectedAreaZone.objects.create(
            protected_area=other_area,
            name="Wrong Zone",
            code="wrong",
        )

        site = DiveSite(
            name="Test Reef",
            place=dive_site_place,
            max_depth_meters=18,
            protected_area=protected_area,
            protected_area_zone=wrong_zone,
        )
        with pytest.raises(ValidationError) as exc_info:
            site.full_clean()
        assert "Zone must belong" in str(exc_info.value)


# === ProtectedAreaPermit (Unified) Tests ===


@pytest.mark.django_db
class TestProtectedAreaPermitModel:
    """Tests for unified ProtectedAreaPermit model with type discrimination."""

    @pytest.fixture
    def protected_area(self, db):
        """Create a protected area."""
        from primitives_testbed.diveops.models import ProtectedArea

        return ProtectedArea.objects.create(
            name="Test Area",
            code="testarea",
        )

    @pytest.fixture
    def zone(self, protected_area):
        """Create a zone in the area."""
        from primitives_testbed.diveops.models import ProtectedAreaZone

        return ProtectedAreaZone.objects.create(
            protected_area=protected_area,
            name="Use Zone",
            code="use",
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

    # === GUIDE Permit Tests ===

    def test_guide_permit_creation(self, protected_area, dm_diver):
        """GUIDE permit can be created with diver."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        permit = ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="GUIDE-001",
            issued_at=date.today(),
            diver=dm_diver,
        )
        assert permit.pk is not None
        assert permit.permit_type == "guide"
        assert permit.diver == dm_diver
        assert permit.vessel_name == ""
        assert permit.is_active is True

    def test_guide_permit_with_authorized_zones(self, protected_area, dm_diver, zone):
        """GUIDE permit can have authorized zones."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        permit = ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="GUIDE-002",
            issued_at=date.today(),
            diver=dm_diver,
        )
        permit.authorized_zones.add(zone)
        assert zone in permit.authorized_zones.all()

    def test_guide_permit_requires_diver_db_constraint(self, protected_area):
        """GUIDE permit must have a diver (DB constraint)."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        with pytest.raises(IntegrityError):
            ProtectedAreaPermit.objects.create(
                protected_area=protected_area,
                permit_type=ProtectedAreaPermit.PermitType.GUIDE,
                permit_number="GUIDE-003",
                issued_at=date.today(),
                diver=None,  # Violates constraint
            )

    def test_guide_permit_cannot_have_vessel_name_db_constraint(self, protected_area, dm_diver):
        """GUIDE permit must not have vessel_name (DB constraint)."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        with pytest.raises(IntegrityError):
            ProtectedAreaPermit.objects.create(
                protected_area=protected_area,
                permit_type=ProtectedAreaPermit.PermitType.GUIDE,
                permit_number="GUIDE-004",
                issued_at=date.today(),
                diver=dm_diver,
                vessel_name="Some Boat",  # Violates constraint
            )

    def test_guide_permit_unique_per_diver_per_area(self, protected_area, dm_diver):
        """Only one GUIDE permit per diver per area."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="GUIDE-005",
            issued_at=date.today(),
            diver=dm_diver,
        )
        with pytest.raises(IntegrityError):
            ProtectedAreaPermit.objects.create(
                protected_area=protected_area,
                permit_type=ProtectedAreaPermit.PermitType.GUIDE,
                permit_number="GUIDE-006",  # Different number
                issued_at=date.today(),
                diver=dm_diver,  # Same diver - violates constraint
            )

    def test_guide_permit_same_diver_different_areas(self, protected_area, dm_diver):
        """Same diver can have GUIDE permits in different areas."""
        from primitives_testbed.diveops.models import ProtectedArea, ProtectedAreaPermit

        other_area = ProtectedArea.objects.create(
            name="Other Area",
            code="other",
        )
        ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="GUIDE-007",
            issued_at=date.today(),
            diver=dm_diver,
        )
        permit2 = ProtectedAreaPermit.objects.create(
            protected_area=other_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="GUIDE-008",
            issued_at=date.today(),
            diver=dm_diver,
        )
        assert permit2.pk is not None

    # === VESSEL Permit Tests ===

    def test_vessel_permit_creation(self, protected_area, dive_shop):
        """VESSEL permit can be created with vessel_name."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        permit = ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.VESSEL,
            permit_number="VESSEL-001",
            issued_at=date.today(),
            vessel_name="MV Test Boat",
            vessel_registration="TUL-123",
            organization=dive_shop,
            max_divers=12,
        )
        assert permit.pk is not None
        assert permit.permit_type == "vessel"
        assert permit.vessel_name == "MV Test Boat"
        assert permit.diver is None
        assert permit.organization == dive_shop

    def test_vessel_permit_requires_vessel_name_db_constraint(self, protected_area):
        """VESSEL permit must have vessel_name (DB constraint)."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        with pytest.raises(IntegrityError):
            ProtectedAreaPermit.objects.create(
                protected_area=protected_area,
                permit_type=ProtectedAreaPermit.PermitType.VESSEL,
                permit_number="VESSEL-002",
                issued_at=date.today(),
                vessel_name="",  # Violates constraint
            )

    def test_vessel_permit_cannot_have_diver_db_constraint(self, protected_area, dm_diver):
        """VESSEL permit must not have diver (DB constraint)."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        with pytest.raises(IntegrityError):
            ProtectedAreaPermit.objects.create(
                protected_area=protected_area,
                permit_type=ProtectedAreaPermit.PermitType.VESSEL,
                permit_number="VESSEL-003",
                issued_at=date.today(),
                vessel_name="MV Test Boat",
                diver=dm_diver,  # Violates constraint
            )

    # === Unique Permit Number Tests ===

    def test_permit_number_unique_per_area_and_type(self, protected_area, dm_diver, dive_shop):
        """Permit number must be unique within area and type."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="PERM-001",
            issued_at=date.today(),
            diver=dm_diver,
        )
        # Same number, same type, same area - should fail
        with pytest.raises(IntegrityError):
            from django_parties.models import Person

            from primitives_testbed.diveops.models import DiverProfile

            other_person = Person.objects.create(
                first_name="Other",
                last_name="Guide",
                date_of_birth=date(1990, 1, 1),
            )
            other_diver = DiverProfile.objects.create(person=other_person)
            ProtectedAreaPermit.objects.create(
                protected_area=protected_area,
                permit_type=ProtectedAreaPermit.PermitType.GUIDE,
                permit_number="PERM-001",  # Duplicate
                issued_at=date.today(),
                diver=other_diver,
            )

    def test_same_permit_number_different_types_allowed(self, protected_area, dm_diver, dive_shop):
        """Same permit number can exist for different types in same area."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="PERM-001",
            issued_at=date.today(),
            diver=dm_diver,
        )
        permit2 = ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.VESSEL,
            permit_number="PERM-001",  # Same number, different type - OK
            issued_at=date.today(),
            vessel_name="MV Test Boat",
            organization=dive_shop,
        )
        assert permit2.pk is not None

    def test_same_permit_number_different_areas_allowed(self, protected_area, dm_diver):
        """Same permit number can exist in different areas."""
        from primitives_testbed.diveops.models import ProtectedArea, ProtectedAreaPermit

        other_area = ProtectedArea.objects.create(
            name="Other Area",
            code="other",
        )
        ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="PERM-001",
            issued_at=date.today(),
            diver=dm_diver,
        )
        from django_parties.models import Person

        from primitives_testbed.diveops.models import DiverProfile

        other_person = Person.objects.create(
            first_name="Other",
            last_name="Guide",
            date_of_birth=date(1990, 1, 1),
        )
        other_diver = DiverProfile.objects.create(person=other_person)
        permit2 = ProtectedAreaPermit.objects.create(
            protected_area=other_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="PERM-001",  # Same number, different area - OK
            issued_at=date.today(),
            diver=other_diver,
        )
        assert permit2.pk is not None

    # === Expiry Date Constraint Tests ===

    def test_expires_at_must_be_after_issued_at(self, protected_area, dm_diver):
        """expires_at must be >= issued_at (DB constraint)."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        with pytest.raises(IntegrityError):
            ProtectedAreaPermit.objects.create(
                protected_area=protected_area,
                permit_type=ProtectedAreaPermit.PermitType.GUIDE,
                permit_number="GUIDE-EXP",
                issued_at=date(2024, 6, 1),
                expires_at=date(2024, 5, 1),  # Before issued_at - violates constraint
                diver=dm_diver,
            )

    def test_expires_at_null_allowed(self, protected_area, dm_diver):
        """expires_at can be null (no expiry)."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        permit = ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="GUIDE-NOEXP",
            issued_at=date.today(),
            expires_at=None,
            diver=dm_diver,
        )
        assert permit.expires_at is None


# === GuidePermitDetails Extension Tests ===


@pytest.mark.django_db
class TestGuidePermitDetailsModel:
    """Tests for GuidePermitDetails extension model."""

    @pytest.fixture
    def protected_area(self, db):
        """Create a protected area."""
        from primitives_testbed.diveops.models import ProtectedArea

        return ProtectedArea.objects.create(
            name="Test Area",
            code="testarea",
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
    def guide_permit(self, protected_area, dm_diver):
        """Create a guide permit."""
        from primitives_testbed.diveops.models import ProtectedAreaPermit

        return ProtectedAreaPermit.objects.create(
            protected_area=protected_area,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            permit_number="GUIDE-DET",
            issued_at=date.today(),
            diver=dm_diver,
        )

    def test_guide_details_creation(self, guide_permit):
        """GuidePermitDetails can be created for a guide permit."""
        from primitives_testbed.diveops.models import GuidePermitDetails

        details = GuidePermitDetails.objects.create(
            permit=guide_permit,
            is_owner=True,
            last_refresher_at=date(2024, 1, 15),
            next_refresher_due_at=date(2025, 1, 15),
        )
        assert details.pk is not None
        assert details.permit == guide_permit
        assert details.is_owner is True

    def test_guide_details_one_to_one_constraint(self, guide_permit):
        """Only one GuidePermitDetails per permit."""
        from primitives_testbed.diveops.models import GuidePermitDetails

        GuidePermitDetails.objects.create(
            permit=guide_permit,
        )
        with pytest.raises(IntegrityError):
            GuidePermitDetails.objects.create(
                permit=guide_permit,
            )

    def test_guide_details_accessible_via_permit(self, guide_permit):
        """GuidePermitDetails is accessible via permit.guide_details."""
        from primitives_testbed.diveops.models import GuidePermitDetails

        details = GuidePermitDetails.objects.create(
            permit=guide_permit,
            is_owner=True,
        )
        assert guide_permit.guide_details == details

    def test_guide_details_suspension_fields(self, guide_permit):
        """GuidePermitDetails can track suspension info."""
        from django.utils import timezone

        from primitives_testbed.diveops.models import GuidePermitDetails

        details = GuidePermitDetails.objects.create(
            permit=guide_permit,
            suspended_at=timezone.now(),
            suspension_reason="Failed to complete refresher course",
        )
        assert details.suspended_at is not None
        assert "refresher" in details.suspension_reason
