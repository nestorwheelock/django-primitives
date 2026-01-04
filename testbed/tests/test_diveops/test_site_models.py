"""Tests for DiveSite model after overlay refactor.

Tests for the refactored DiveSite model that:
- Uses Place FK (required, owned per site)
- Uses CertificationLevel FK (nullable)
- Has rating (1-5 or null) with constraint
- Has tags ArrayField (Postgres-specific)
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.utils import DataError

from primitives_testbed.diveops.models import CertificationLevel, DiveSite


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
def another_place(db):
    """Create another Place."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Deep Wall Location",
        latitude=Decimal("25.234567"),
        longitude=Decimal("-80.234567"),
    )


@pytest.mark.django_db
class TestDiveSitePlaceFK:
    """Tests for DiveSite.place FK (required, owned per site)."""

    def test_dive_site_requires_place(self, db):
        """DiveSite cannot be created without place."""
        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Test Site",
                max_depth_meters=30,
                difficulty="intermediate",
            )

    def test_dive_site_with_place(self, place):
        """DiveSite can be created with place."""
        site = DiveSite.objects.create(
            name="Test Reef",
            place=place,
            max_depth_meters=30,
            difficulty="intermediate",
        )
        assert site.pk is not None
        assert site.place == place
        assert site.place.latitude == Decimal("25.123456")
        assert site.place.longitude == Decimal("-80.123456")

    def test_dive_site_place_is_owned(self, place, another_place):
        """Each DiveSite owns its Place (no sharing required)."""
        site1 = DiveSite.objects.create(
            name="Site 1",
            place=place,
            max_depth_meters=20,
            difficulty="beginner",
        )
        site2 = DiveSite.objects.create(
            name="Site 2",
            place=another_place,
            max_depth_meters=30,
            difficulty="intermediate",
        )
        # Each site has its own place
        assert site1.place != site2.place
        assert site1.place.id != site2.place.id

    def test_dive_site_coordinates_from_place(self, place):
        """DiveSite coordinates come from Place."""
        site = DiveSite.objects.create(
            name="Test Site",
            place=place,
            max_depth_meters=25,
            difficulty="intermediate",
        )
        # Access coordinates via place
        assert site.place.latitude == Decimal("25.123456")
        assert site.place.longitude == Decimal("-80.123456")

    def test_dive_site_no_latitude_longitude_fields(self, place):
        """DiveSite does not have direct latitude/longitude fields."""
        site = DiveSite.objects.create(
            name="Test Site",
            place=place,
            max_depth_meters=25,
            difficulty="intermediate",
        )
        # These attributes should NOT exist on DiveSite
        assert not hasattr(site, 'latitude') or site._meta.get_field('latitude') is None
        assert not hasattr(site, 'longitude') or site._meta.get_field('longitude') is None


@pytest.mark.django_db
class TestDiveSiteCertificationFK:
    """Tests for DiveSite.min_certification_level FK (nullable)."""

    def test_dive_site_no_certification_requirement(self, place):
        """DiveSite can be created without certification requirement."""
        site = DiveSite.objects.create(
            name="Easy Beach Dive",
            place=place,
            max_depth_meters=10,
            difficulty="beginner",
            min_certification_level=None,
        )
        assert site.min_certification_level is None

    def test_dive_site_with_certification_fk(self, place, cert_level_ow):
        """DiveSite min_certification_level is FK to CertificationLevel."""
        site = DiveSite.objects.create(
            name="Reef Dive",
            place=place,
            max_depth_meters=18,
            difficulty="intermediate",
            min_certification_level=cert_level_ow,
        )
        assert site.min_certification_level == cert_level_ow
        assert site.min_certification_level.code == "ow"
        assert site.min_certification_level.rank == 2

    def test_dive_site_certification_level_is_model_instance(self, place, cert_level_aow):
        """min_certification_level is a CertificationLevel instance, not CharField."""
        site = DiveSite.objects.create(
            name="Deep Wall",
            place=place,
            max_depth_meters=40,
            difficulty="advanced",
            min_certification_level=cert_level_aow,
        )
        # Should be a model instance, not a string
        assert isinstance(site.min_certification_level, CertificationLevel)
        # Can traverse to agency
        assert site.min_certification_level.agency.name == "PADI"


@pytest.mark.django_db
class TestDiveSiteRating:
    """Tests for DiveSite.rating (1-5 or null, constrained)."""

    def test_dive_site_rating_null_allowed(self, place):
        """DiveSite rating can be null (unrated site)."""
        site = DiveSite.objects.create(
            name="Unrated Site",
            place=place,
            max_depth_meters=20,
            difficulty="intermediate",
            rating=None,
        )
        assert site.rating is None

    def test_dive_site_rating_valid_values(self, place):
        """DiveSite rating accepts 1-5."""
        for rating in [1, 2, 3, 4, 5]:
            site = DiveSite.objects.create(
                name=f"Site Rating {rating}",
                place=place,
                max_depth_meters=20,
                difficulty="intermediate",
                rating=rating,
            )
            assert site.rating == rating
            site.delete()

    def test_dive_site_rating_constraint_zero_rejected(self, place):
        """DiveSite rating of 0 is rejected by constraint."""
        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Zero Rating Site",
                place=place,
                max_depth_meters=20,
                difficulty="intermediate",
                rating=0,
            )

    def test_dive_site_rating_constraint_six_rejected(self, place):
        """DiveSite rating > 5 is rejected by constraint."""
        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Six Rating Site",
                place=place,
                max_depth_meters=20,
                difficulty="intermediate",
                rating=6,
            )

    def test_dive_site_rating_constraint_negative_rejected(self, place):
        """DiveSite negative rating is rejected by constraint."""
        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Negative Rating Site",
                place=place,
                max_depth_meters=20,
                difficulty="intermediate",
                rating=-1,
            )


@pytest.mark.django_db
class TestDiveSiteTags:
    """Tests for DiveSite.tags ArrayField."""

    def test_dive_site_tags_default_empty_list(self, place):
        """DiveSite tags defaults to empty list."""
        site = DiveSite.objects.create(
            name="Tagless Site",
            place=place,
            max_depth_meters=20,
            difficulty="intermediate",
        )
        assert site.tags == []

    def test_dive_site_tags_stores_list(self, place):
        """DiveSite tags stores list of strings."""
        tags = ["reef", "coral", "fish"]
        site = DiveSite.objects.create(
            name="Tagged Site",
            place=place,
            max_depth_meters=20,
            difficulty="intermediate",
            tags=tags,
        )
        assert site.tags == tags

    def test_dive_site_tags_queryable(self, place):
        """DiveSite can be queried by tags (contains)."""
        DiveSite.objects.create(
            name="Reef Site",
            place=place,
            max_depth_meters=20,
            difficulty="intermediate",
            tags=["reef", "tropical"],
        )
        # Query using contains
        sites = DiveSite.objects.filter(tags__contains=["reef"])
        assert sites.count() == 1
        assert sites.first().name == "Reef Site"

    def test_dive_site_tags_filter_multiple(self, place, another_place):
        """DiveSite can be filtered by multiple tag queries."""
        from django.db.models import Q

        DiveSite.objects.create(
            name="Coral Site",
            place=place,
            max_depth_meters=20,
            difficulty="intermediate",
            tags=["coral", "fish"],
        )
        DiveSite.objects.create(
            name="Wreck Site",
            place=another_place,
            max_depth_meters=30,
            difficulty="advanced",
            tags=["wreck", "history"],
        )
        # Query using OR with contains (JSONField pattern)
        sites = DiveSite.objects.filter(
            Q(tags__contains=["coral"]) | Q(tags__contains=["wreck"])
        )
        assert sites.count() == 2


@pytest.mark.django_db
class TestDiveSiteSoftDelete:
    """Tests for DiveSite soft delete behavior."""

    def test_dive_site_soft_delete(self, place):
        """DiveSite can be soft deleted."""
        site = DiveSite.objects.create(
            name="Deletable Site",
            place=place,
            max_depth_meters=20,
            difficulty="intermediate",
        )
        site_id = site.pk

        # Soft delete
        from django.utils import timezone
        site.deleted_at = timezone.now()
        site.save()

        # Excluded from default queryset
        assert DiveSite.objects.filter(pk=site_id).count() == 0
        # Still in all_objects
        assert DiveSite.all_objects.filter(pk=site_id).count() == 1

    def test_dive_site_is_active_independent_of_soft_delete(self, place):
        """DiveSite is_active is independent of soft delete."""
        site = DiveSite.objects.create(
            name="Inactive Site",
            place=place,
            max_depth_meters=20,
            difficulty="intermediate",
            is_active=False,
        )
        # is_active=False but not soft deleted
        assert DiveSite.objects.filter(pk=site.pk).exists()
        assert site.is_active is False


@pytest.mark.django_db
class TestDiveSiteConstraints:
    """Tests for DiveSite database constraints."""

    def test_dive_site_depth_must_be_positive(self, place):
        """DiveSite max_depth_meters must be > 0."""
        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Zero Depth Site",
                place=place,
                max_depth_meters=0,
                difficulty="beginner",
            )

    def test_dive_site_valid_difficulty_choices(self, place):
        """DiveSite difficulty must be valid choice."""
        valid_difficulties = ["beginner", "intermediate", "advanced", "expert"]
        for diff in valid_difficulties:
            site = DiveSite.objects.create(
                name=f"{diff.title()} Site",
                place=place,
                max_depth_meters=20,
                difficulty=diff,
            )
            assert site.difficulty == diff
            site.delete()
