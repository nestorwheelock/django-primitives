"""Tests for django-geo QuerySet methods."""
import pytest
from decimal import Decimal


@pytest.mark.django_db
class TestPlaceQuerySet:
    """Tests for Place QuerySet methods."""

    @pytest.fixture
    def places(self):
        """Create test places at known locations."""
        from django_geo.models import Place

        # Mexico City center
        cdmx = Place.objects.create(
            name='Zócalo',
            place_type='landmark',
            city='Mexico City',
            state='CDMX',
            postal_code='06000',
            country='MX',
            latitude=Decimal('19.4326'),
            longitude=Decimal('-99.1332'),
        )

        # ~5km from center
        roma = Place.objects.create(
            name='Roma Norte',
            place_type='poi',
            city='Mexico City',
            state='CDMX',
            postal_code='06700',
            country='MX',
            latitude=Decimal('19.4195'),
            longitude=Decimal('-99.1670'),
        )

        # ~15km from center
        santa_fe = Place.objects.create(
            name='Santa Fe',
            place_type='poi',
            city='Mexico City',
            state='CDMX',
            postal_code='01219',
            country='MX',
            latitude=Decimal('19.3590'),
            longitude=Decimal('-99.2600'),
        )

        # Guadalajara (~460km away)
        gdl = Place.objects.create(
            name='Guadalajara Centro',
            place_type='landmark',
            city='Guadalajara',
            state='JAL',
            postal_code='44100',
            country='MX',
            latitude=Decimal('20.6597'),
            longitude=Decimal('-103.3496'),
        )

        return {'cdmx': cdmx, 'roma': roma, 'santa_fe': santa_fe, 'gdl': gdl}

    def test_within_radius_finds_nearby_places(self, places):
        """within_radius() finds places within specified distance."""
        from django_geo.models import Place

        # Search 10km from Zócalo center
        nearby = Place.objects.within_radius(
            lat=Decimal('19.4326'),
            lng=Decimal('-99.1332'),
            km=Decimal('10.0'),
        )

        assert places['cdmx'] in nearby
        assert places['roma'] in nearby
        assert places['santa_fe'] not in nearby  # ~15km away
        assert places['gdl'] not in nearby  # ~460km away

    def test_within_radius_excludes_far_places(self, places):
        """within_radius() excludes places beyond radius."""
        from django_geo.models import Place

        # Search 3km from Zócalo
        very_close = Place.objects.within_radius(
            lat=Decimal('19.4326'),
            lng=Decimal('-99.1332'),
            km=Decimal('3.0'),
        )

        assert places['cdmx'] in very_close
        assert places['roma'] not in very_close  # ~5km away

    def test_within_radius_empty_when_none_nearby(self, places):
        """within_radius() returns empty when no places in radius."""
        from django_geo.models import Place

        # Search in middle of ocean
        empty = Place.objects.within_radius(
            lat=Decimal('0.0'),
            lng=Decimal('0.0'),
            km=Decimal('10.0'),
        )

        assert empty.count() == 0

    def test_nearest_returns_ordered_by_distance(self, places):
        """nearest() returns places ordered by distance."""
        from django_geo.models import Place

        # Search from Zócalo
        nearest = Place.objects.nearest(
            lat=Decimal('19.4326'),
            lng=Decimal('-99.1332'),
            limit=4,
        )

        result = list(nearest)

        # First should be Zócalo itself (distance 0)
        assert result[0] == places['cdmx']
        # Second should be Roma (~5km)
        assert result[1] == places['roma']
        # Third should be Santa Fe (~15km)
        assert result[2] == places['santa_fe']
        # Last should be Guadalajara (~460km)
        assert result[3] == places['gdl']

    def test_nearest_respects_limit(self, places):
        """nearest() returns only limit results."""
        from django_geo.models import Place

        nearest_2 = Place.objects.nearest(
            lat=Decimal('19.4326'),
            lng=Decimal('-99.1332'),
            limit=2,
        )

        assert nearest_2.count() == 2


@pytest.mark.django_db
class TestServiceAreaQuerySet:
    """Tests for ServiceArea QuerySet methods."""

    @pytest.fixture
    def areas(self):
        """Create test service areas."""
        from django_geo.models import ServiceArea

        # Centro zone (5km radius around Zócalo)
        centro = ServiceArea.objects.create(
            name='Centro',
            code='centro',
            area_type='delivery',
            center_latitude=Decimal('19.4326'),
            center_longitude=Decimal('-99.1332'),
            radius_km=Decimal('5.0'),
        )

        # Roma zone (3km radius)
        roma = ServiceArea.objects.create(
            name='Roma',
            code='roma',
            area_type='delivery',
            center_latitude=Decimal('19.4195'),
            center_longitude=Decimal('-99.1670'),
            radius_km=Decimal('3.0'),
        )

        # Santa Fe zone (10km radius, partially overlaps)
        santa_fe = ServiceArea.objects.create(
            name='Santa Fe',
            code='santa-fe',
            area_type='delivery',
            center_latitude=Decimal('19.3590'),
            center_longitude=Decimal('-99.2600'),
            radius_km=Decimal('10.0'),
        )

        return {'centro': centro, 'roma': roma, 'santa_fe': santa_fe}

    def test_containing_finds_areas(self, areas):
        """containing() finds areas that contain a point."""
        from django_geo.models import ServiceArea

        # Point in Centro zone
        containing = ServiceArea.objects.containing(
            lat=Decimal('19.4326'),
            lng=Decimal('-99.1332'),
        )

        assert areas['centro'] in containing

    def test_containing_finds_overlapping_areas(self, areas):
        """containing() finds all overlapping areas for a point."""
        from django_geo.models import ServiceArea

        # Point in Roma zone (may also be in Centro due to overlap)
        containing = ServiceArea.objects.containing(
            lat=Decimal('19.4195'),
            lng=Decimal('-99.1670'),
        )

        assert areas['roma'] in containing

    def test_containing_excludes_non_matching(self, areas):
        """containing() excludes areas that don't contain the point."""
        from django_geo.models import ServiceArea

        # Point far outside all zones
        containing = ServiceArea.objects.containing(
            lat=Decimal('20.6597'),  # Guadalajara
            lng=Decimal('-103.3496'),
        )

        assert areas['centro'] not in containing
        assert areas['roma'] not in containing
        assert areas['santa_fe'] not in containing

    def test_containing_empty_when_outside_all(self, areas):
        """containing() returns empty when point outside all areas."""
        from django_geo.models import ServiceArea

        # Point in ocean
        containing = ServiceArea.objects.containing(
            lat=Decimal('0.0'),
            lng=Decimal('0.0'),
        )

        assert containing.count() == 0

    def test_active_only_filter(self, areas):
        """active() filters to only active areas."""
        from django_geo.models import ServiceArea

        # Deactivate one area
        areas['roma'].is_active = False
        areas['roma'].save()

        active = ServiceArea.objects.filter(is_active=True)

        assert areas['centro'] in active
        assert areas['roma'] not in active
        assert areas['santa_fe'] in active
