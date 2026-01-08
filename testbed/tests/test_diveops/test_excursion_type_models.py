"""Tests for ExcursionType and SitePriceAdjustment models.

Tests the new excursion type feature:
- ExcursionType: Template for bookable excursion products
- SitePriceAdjustment: Site-specific price adjustments (distance, fees)
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.db.models import Q


@pytest.fixture
def padi_agency(db):
    """Create PADI certification agency."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="PADI",
        org_type="certification_agency",
    )


@pytest.fixture
def cert_level_ow(db, padi_agency):
    """Create Open Water certification level."""
    from primitives_testbed.diveops.models import CertificationLevel

    return CertificationLevel.objects.create(
        agency=padi_agency,
        code="ow",
        name="Open Water Diver",
        rank=2,
        max_depth_m=18,
    )


@pytest.fixture
def cert_level_aow(db, padi_agency):
    """Create Advanced Open Water certification level."""
    from primitives_testbed.diveops.models import CertificationLevel

    return CertificationLevel.objects.create(
        agency=padi_agency,
        code="aow",
        name="Advanced Open Water Diver",
        rank=3,
        max_depth_m=30,
    )


@pytest.fixture
def place(db):
    """Create a Place for dive site."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Test Reef Location",
        latitude=Decimal("25.123456"),
        longitude=Decimal("-80.123456"),
    )


@pytest.fixture
def dive_site(db, place):
    """Create a dive site."""
    from primitives_testbed.diveops.models import DiveSite

    return DiveSite.objects.create(
        name="Blue Hole",
        place=place,
        max_depth_meters=40,
        difficulty="advanced",
    )


@pytest.fixture
def another_place(db):
    """Create another Place."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Shore Entry Point",
        latitude=Decimal("25.200000"),
        longitude=Decimal("-80.200000"),
    )


@pytest.fixture
def shore_site(db, another_place):
    """Create a shore dive site."""
    from primitives_testbed.diveops.models import DiveSite

    return DiveSite.objects.create(
        name="Beach Entry",
        place=another_place,
        max_depth_meters=12,
        difficulty="beginner",
    )


# =============================================================================
# ExcursionType Model Tests
# =============================================================================


@pytest.mark.django_db
class TestExcursionTypeCreation:
    """Tests for ExcursionType model creation."""

    def test_excursion_type_creation_minimal(self, db):
        """ExcursionType can be created with required fields."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Beginner Reef Dive",
            slug="beginner-reef",
            dive_mode="boat",
            max_depth_meters=18,
            base_price=Decimal("75.00"),
        )
        assert etype.pk is not None
        assert etype.name == "Beginner Reef Dive"
        assert etype.slug == "beginner-reef"
        assert etype.dive_mode == "boat"
        assert etype.max_depth_meters == 18
        assert etype.base_price == Decimal("75.00")

    def test_excursion_type_creation_full(self, cert_level_ow, dive_site):
        """ExcursionType can be created with all fields."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Advanced Deep Dive",
            slug="advanced-deep",
            description="Deep wall diving for experienced divers",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=40,
            typical_duration_minutes=90,
            dives_per_excursion=2,
            min_certification_level=cert_level_ow,
            requires_cert=True,
            is_training=False,
            base_price=Decimal("150.00"),
            currency="USD",
            is_active=True,
        )
        etype.suitable_sites.add(dive_site)

        assert etype.description == "Deep wall diving for experienced divers"
        assert etype.time_of_day == "day"
        assert etype.typical_duration_minutes == 90
        assert etype.dives_per_excursion == 2
        assert etype.min_certification_level == cert_level_ow
        assert etype.requires_cert is True
        assert etype.is_training is False
        assert etype.currency == "USD"
        assert dive_site in etype.suitable_sites.all()


@pytest.mark.django_db
class TestExcursionTypeDiveMode:
    """Tests for ExcursionType dive_mode choices."""

    def test_excursion_type_boat_mode(self, db):
        """ExcursionType can have boat dive mode."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Boat Dive",
            slug="boat-dive",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        assert etype.dive_mode == "boat"

    def test_excursion_type_shore_mode(self, db):
        """ExcursionType can have shore dive mode."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Shore Dive",
            slug="shore-dive",
            dive_mode="shore",
            max_depth_meters=15,
            base_price=Decimal("50.00"),
        )
        assert etype.dive_mode == "shore"


@pytest.mark.django_db
class TestExcursionTypeTimeOfDay:
    """Tests for ExcursionType time_of_day choices."""

    def test_excursion_type_day_dive(self, db):
        """ExcursionType can be day dive."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Day Dive",
            slug="day-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        assert etype.time_of_day == "day"

    def test_excursion_type_night_dive(self, db):
        """ExcursionType can be night dive."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Night Dive",
            slug="night-dive",
            dive_mode="shore",
            time_of_day="night",
            max_depth_meters=15,
            base_price=Decimal("75.00"),
        )
        assert etype.time_of_day == "night"

    def test_excursion_type_dawn_dive(self, db):
        """ExcursionType can be dawn dive."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Dawn Dive",
            slug="dawn-dive",
            dive_mode="boat",
            time_of_day="dawn",
            max_depth_meters=20,
            base_price=Decimal("90.00"),
        )
        assert etype.time_of_day == "dawn"

    def test_excursion_type_dusk_dive(self, db):
        """ExcursionType can be dusk dive."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Dusk Dive",
            slug="dusk-dive",
            dive_mode="boat",
            time_of_day="dusk",
            max_depth_meters=20,
            base_price=Decimal("85.00"),
        )
        assert etype.time_of_day == "dusk"

    def test_excursion_type_time_of_day_default(self, db):
        """ExcursionType time_of_day defaults to day."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Default Time",
            slug="default-time",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        assert etype.time_of_day == "day"


@pytest.mark.django_db
class TestExcursionTypeDSD:
    """Tests for DSD (Discover Scuba Diving) excursion types."""

    def test_dsd_intro_shore_no_cert_required(self, db):
        """DSD intro can be created without certification requirement."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="DSD Intro from Beach",
            slug="dsd-intro-beach",
            dive_mode="shore",
            max_depth_meters=6,
            requires_cert=False,
            is_training=True,
            base_price=Decimal("125.00"),
        )
        assert etype.requires_cert is False
        assert etype.is_training is True
        assert etype.min_certification_level is None

    def test_dsd_defaults_require_cert_true(self, db):
        """ExcursionType requires_cert defaults to True."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Regular Dive",
            slug="regular-dive",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        assert etype.requires_cert is True

    def test_dsd_defaults_is_training_false(self, db):
        """ExcursionType is_training defaults to False."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Regular Dive",
            slug="regular-dive-2",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        assert etype.is_training is False


@pytest.mark.django_db
class TestExcursionTypeCertification:
    """Tests for ExcursionType certification level FK."""

    def test_excursion_type_no_min_cert(self, db):
        """ExcursionType can have no minimum certification."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="No Cert Required",
            slug="no-cert",
            dive_mode="shore",
            max_depth_meters=10,
            min_certification_level=None,
            base_price=Decimal("50.00"),
        )
        assert etype.min_certification_level is None

    def test_excursion_type_with_min_cert(self, cert_level_aow):
        """ExcursionType can have minimum certification FK."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Advanced Dive",
            slug="advanced-dive",
            dive_mode="boat",
            max_depth_meters=40,
            min_certification_level=cert_level_aow,
            base_price=Decimal("150.00"),
        )
        assert etype.min_certification_level == cert_level_aow
        assert etype.min_certification_level.rank == 3


@pytest.mark.django_db
class TestExcursionTypeSuitableSites:
    """Tests for ExcursionType suitable_sites M2M."""

    def test_excursion_type_no_suitable_sites(self, db):
        """ExcursionType can have no suitable sites (all sites allowed)."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Any Site Dive",
            slug="any-site",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        assert etype.suitable_sites.count() == 0

    def test_excursion_type_with_suitable_sites(self, dive_site, shore_site):
        """ExcursionType can have specific suitable sites."""
        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Specific Sites Dive",
            slug="specific-sites",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        etype.suitable_sites.add(dive_site, shore_site)

        assert etype.suitable_sites.count() == 2
        assert dive_site in etype.suitable_sites.all()
        assert shore_site in etype.suitable_sites.all()

    def test_site_can_be_suitable_for_multiple_types(self, dive_site):
        """A DiveSite can be suitable for multiple excursion types."""
        from primitives_testbed.diveops.models import ExcursionType

        etype1 = ExcursionType.objects.create(
            name="Type 1",
            slug="type-1",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        etype2 = ExcursionType.objects.create(
            name="Type 2",
            slug="type-2",
            dive_mode="boat",
            max_depth_meters=30,
            base_price=Decimal("120.00"),
        )
        etype1.suitable_sites.add(dive_site)
        etype2.suitable_sites.add(dive_site)

        assert dive_site in etype1.suitable_sites.all()
        assert dive_site in etype2.suitable_sites.all()
        # Reverse relation
        assert etype1 in dive_site.excursion_types.all()
        assert etype2 in dive_site.excursion_types.all()


@pytest.mark.django_db
class TestExcursionTypeConstraints:
    """Tests for ExcursionType database constraints."""

    def test_excursion_type_slug_unique(self, db):
        """ExcursionType slug must be unique."""
        from primitives_testbed.diveops.models import ExcursionType

        ExcursionType.objects.create(
            name="Type 1",
            slug="unique-slug",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        with pytest.raises(IntegrityError):
            ExcursionType.objects.create(
                name="Type 2",
                slug="unique-slug",  # Duplicate slug
                dive_mode="shore",
                max_depth_meters=15,
                base_price=Decimal("50.00"),
            )

    def test_excursion_type_base_price_positive(self, db):
        """ExcursionType base_price must be positive."""
        from primitives_testbed.diveops.models import ExcursionType

        with pytest.raises(IntegrityError):
            ExcursionType.objects.create(
                name="Negative Price",
                slug="negative-price",
                dive_mode="boat",
                max_depth_meters=20,
                base_price=Decimal("-10.00"),
            )

    def test_excursion_type_max_depth_positive(self, db):
        """ExcursionType max_depth_meters must be positive."""
        from primitives_testbed.diveops.models import ExcursionType

        with pytest.raises(IntegrityError):
            ExcursionType.objects.create(
                name="Zero Depth",
                slug="zero-depth",
                dive_mode="boat",
                max_depth_meters=0,
                base_price=Decimal("100.00"),
            )


@pytest.mark.django_db
class TestExcursionTypeSoftDelete:
    """Tests for ExcursionType soft delete behavior."""

    def test_excursion_type_soft_delete(self, db):
        """ExcursionType can be soft deleted."""
        from django.utils import timezone

        from primitives_testbed.diveops.models import ExcursionType

        etype = ExcursionType.objects.create(
            name="Deletable Type",
            slug="deletable",
            dive_mode="boat",
            max_depth_meters=20,
            base_price=Decimal("100.00"),
        )
        etype_id = etype.pk

        # Soft delete
        etype.deleted_at = timezone.now()
        etype.save()

        # Excluded from default queryset
        assert ExcursionType.objects.filter(pk=etype_id).count() == 0
        # Still in all_objects
        assert ExcursionType.all_objects.filter(pk=etype_id).count() == 1


# =============================================================================
# SitePriceAdjustment Model Tests
# =============================================================================


@pytest.mark.django_db
class TestSitePriceAdjustmentCreation:
    """Tests for SitePriceAdjustment model creation."""

    def test_site_price_adjustment_creation(self, dive_site):
        """SitePriceAdjustment can be created."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("25.00"),
            currency="USD",
        )
        assert adj.pk is not None
        assert adj.dive_site == dive_site
        assert adj.kind == "distance"
        assert adj.amount == Decimal("25.00")
        assert adj.currency == "USD"

    def test_site_price_adjustment_full(self, dive_site):
        """SitePriceAdjustment can be created with all fields."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="boat",
            amount=Decimal("30.00"),
            currency="USD",
            applies_to_mode="boat",
            is_per_diver=True,
            is_active=True,
        )
        assert adj.applies_to_mode == "boat"
        assert adj.is_per_diver is True
        assert adj.is_active is True


@pytest.mark.django_db
class TestSitePriceAdjustmentKinds:
    """Tests for SitePriceAdjustment kind choices."""

    def test_adjustment_kind_distance(self, dive_site):
        """SitePriceAdjustment can have distance kind."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("20.00"),
        )
        assert adj.kind == "distance"

    def test_adjustment_kind_park_fee(self, dive_site):
        """SitePriceAdjustment can have park_fee kind."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="park_fee",
            amount=Decimal("15.00"),
        )
        assert adj.kind == "park_fee"

    def test_adjustment_kind_night(self, dive_site):
        """SitePriceAdjustment can have night surcharge kind."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="night",
            amount=Decimal("25.00"),
        )
        assert adj.kind == "night"

    def test_adjustment_kind_boat(self, dive_site):
        """SitePriceAdjustment can have boat fee kind."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="boat",
            amount=Decimal("50.00"),
        )
        assert adj.kind == "boat"


@pytest.mark.django_db
class TestSitePriceAdjustmentConstraints:
    """Tests for SitePriceAdjustment database constraints."""

    def test_unique_site_adjustment_kind(self, dive_site):
        """Only one adjustment of each kind per site."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("20.00"),
        )
        with pytest.raises(IntegrityError):
            SitePriceAdjustment.objects.create(
                dive_site=dive_site,
                kind="distance",  # Duplicate kind for same site
                amount=Decimal("30.00"),
            )

    def test_different_sites_can_have_same_kind(self, dive_site, shore_site):
        """Different sites can have adjustments of the same kind."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj1 = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("20.00"),
        )
        adj2 = SitePriceAdjustment.objects.create(
            dive_site=shore_site,
            kind="distance",
            amount=Decimal("10.00"),
        )
        assert adj1.pk is not None
        assert adj2.pk is not None

    def test_same_site_different_kinds(self, dive_site):
        """Same site can have adjustments of different kinds."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj1 = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("20.00"),
        )
        adj2 = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="park_fee",
            amount=Decimal("15.00"),
        )
        assert adj1.pk is not None
        assert adj2.pk is not None
        assert dive_site.price_adjustments.count() == 2


@pytest.mark.django_db
class TestSitePriceAdjustmentAppliesTo:
    """Tests for SitePriceAdjustment applies_to_mode field."""

    def test_adjustment_applies_to_all(self, dive_site):
        """Adjustment with empty applies_to_mode applies to all modes."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="park_fee",
            amount=Decimal("15.00"),
            applies_to_mode="",  # Applies to all
        )
        assert adj.applies_to_mode == ""

    def test_adjustment_applies_to_boat_only(self, dive_site):
        """Adjustment can apply only to boat dives."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="boat",
            amount=Decimal("50.00"),
            applies_to_mode="boat",
        )
        assert adj.applies_to_mode == "boat"

    def test_adjustment_applies_to_shore_only(self, dive_site):
        """Adjustment can apply only to shore dives."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="night",
            amount=Decimal("20.00"),
            applies_to_mode="shore",
        )
        assert adj.applies_to_mode == "shore"


@pytest.mark.django_db
class TestSitePriceAdjustmentRelations:
    """Tests for SitePriceAdjustment relations."""

    def test_dive_site_price_adjustments_relation(self, dive_site):
        """DiveSite has price_adjustments reverse relation."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("20.00"),
        )
        SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="park_fee",
            amount=Decimal("15.00"),
        )

        assert dive_site.price_adjustments.count() == 2
        kinds = list(dive_site.price_adjustments.values_list("kind", flat=True))
        assert "distance" in kinds
        assert "park_fee" in kinds

    def test_adjustment_cascade_delete_with_site(self, dive_site):
        """SitePriceAdjustment is deleted when site is hard deleted."""
        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("20.00"),
        )
        adj_id = adj.pk

        # Hard delete the site
        dive_site.hard_delete()

        # Adjustment should be gone
        assert SitePriceAdjustment.objects.filter(pk=adj_id).count() == 0


# =============================================================================
# Excursion.excursion_type FK Tests
# =============================================================================


@pytest.fixture
def dive_shop(db):
    """Create a dive shop organization."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Test Dive Shop",
        org_type="dive_shop",
    )


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        username="staff",
        email="staff@test.com",
        password="testpass123",
    )


@pytest.fixture
def excursion_type_beginner(db):
    """Create a beginner reef excursion type."""
    from primitives_testbed.diveops.models import ExcursionType

    return ExcursionType.objects.create(
        name="Beginner Reef Dive",
        slug="beginner-reef",
        dive_mode="boat",
        max_depth_meters=18,
        base_price=Decimal("75.00"),
    )


@pytest.mark.django_db
class TestExcursionTypeFK:
    """Tests for Excursion.excursion_type FK."""

    def test_excursion_without_type(self, dive_site, dive_shop, staff_user):
        """Excursion can be created without excursion_type (nullable FK)."""
        from datetime import timedelta

        from django.utils import timezone

        from primitives_testbed.diveops.models import Excursion

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            created_by=staff_user,
        )
        assert excursion.excursion_type is None

    def test_excursion_with_type(self, dive_site, dive_shop, staff_user, excursion_type_beginner):
        """Excursion can be linked to an excursion_type."""
        from datetime import timedelta

        from django.utils import timezone

        from primitives_testbed.diveops.models import Excursion

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type_beginner,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            created_by=staff_user,
        )
        assert excursion.excursion_type == excursion_type_beginner
        assert excursion.excursion_type.name == "Beginner Reef Dive"

    def test_excursion_type_reverse_relation(self, dive_site, dive_shop, staff_user, excursion_type_beginner):
        """ExcursionType has excursions reverse relation."""
        from datetime import timedelta

        from django.utils import timezone

        from primitives_testbed.diveops.models import Excursion

        now = timezone.now()
        Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type_beginner,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            created_by=staff_user,
        )
        assert excursion_type_beginner.excursions.count() == 1

    def test_excursion_type_protected_on_hard_delete(self, dive_site, dive_shop, staff_user, excursion_type_beginner):
        """Cannot hard delete ExcursionType if excursions exist."""
        from datetime import timedelta

        from django.db.models import ProtectedError
        from django.utils import timezone

        from primitives_testbed.diveops.models import Excursion

        now = timezone.now()
        Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type_beginner,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            created_by=staff_user,
        )
        # Soft delete works (sets deleted_at)
        excursion_type_beginner.delete()
        assert excursion_type_beginner.deleted_at is not None

        # Hard delete raises ProtectedError
        with pytest.raises(ProtectedError):
            excursion_type_beginner.hard_delete()


@pytest.mark.django_db
class TestSitePriceAdjustmentSoftDelete:
    """Tests for SitePriceAdjustment soft delete behavior."""

    def test_site_price_adjustment_soft_delete(self, dive_site):
        """SitePriceAdjustment can be soft deleted."""
        from django.utils import timezone

        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("20.00"),
        )
        adj_id = adj.pk

        # Soft delete
        adj.deleted_at = timezone.now()
        adj.save()

        # Excluded from default queryset
        assert SitePriceAdjustment.objects.filter(pk=adj_id).count() == 0
        # Still in all_objects
        assert SitePriceAdjustment.all_objects.filter(pk=adj_id).count() == 1

    def test_soft_deleted_adjustment_allows_new_same_kind(self, dive_site):
        """After soft delete, can create new adjustment of same kind."""
        from django.utils import timezone

        from primitives_testbed.diveops.models import SitePriceAdjustment

        adj1 = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("20.00"),
        )
        adj1.deleted_at = timezone.now()
        adj1.save()

        # Should be able to create new one with same kind
        adj2 = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("25.00"),
        )
        assert adj2.pk is not None
        assert adj2.amount == Decimal("25.00")
