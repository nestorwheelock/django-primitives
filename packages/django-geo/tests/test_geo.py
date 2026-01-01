"""Tests for GeoPoint value object."""
import pytest
from decimal import Decimal


class TestGeoPoint:
    """Tests for GeoPoint coordinate value object."""

    def test_geopoint_creation(self):
        """GeoPoint can be created with lat/lng."""
        from django_geo.geo import GeoPoint

        point = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))

        assert point.latitude == Decimal('19.4326')
        assert point.longitude == Decimal('-99.1332')

    def test_geopoint_creation_from_floats(self):
        """GeoPoint accepts floats and converts to Decimal."""
        from django_geo.geo import GeoPoint

        point = GeoPoint(latitude=19.4326, longitude=-99.1332)

        assert isinstance(point.latitude, Decimal)
        assert isinstance(point.longitude, Decimal)

    def test_geopoint_distance_to_same_point_is_zero(self):
        """Distance from a point to itself is zero."""
        from django_geo.geo import GeoPoint

        point = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))

        assert point.distance_to(point) == Decimal('0')

    def test_geopoint_distance_to_known_cities(self):
        """Test Haversine distance with known city distances."""
        from django_geo.geo import GeoPoint

        # Mexico City
        cdmx = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))
        # Guadalajara
        gdl = GeoPoint(latitude=Decimal('20.6597'), longitude=Decimal('-103.3496'))

        # Known distance is approximately 460 km
        distance = cdmx.distance_to(gdl)

        assert Decimal('450') < distance < Decimal('470')

    def test_geopoint_distance_nyc_to_la(self):
        """Test NYC to LA distance (~3944 km)."""
        from django_geo.geo import GeoPoint

        nyc = GeoPoint(latitude=Decimal('40.7128'), longitude=Decimal('-74.0060'))
        la = GeoPoint(latitude=Decimal('34.0522'), longitude=Decimal('-118.2437'))

        distance = nyc.distance_to(la)

        # Known distance is approximately 3944 km
        assert Decimal('3900') < distance < Decimal('4000')

    def test_geopoint_distance_is_symmetric(self):
        """Distance A->B equals distance B->A."""
        from django_geo.geo import GeoPoint

        point_a = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))
        point_b = GeoPoint(latitude=Decimal('20.6597'), longitude=Decimal('-103.3496'))

        assert point_a.distance_to(point_b) == point_b.distance_to(point_a)

    def test_geopoint_equality(self):
        """Two GeoPoints with same coordinates are equal."""
        from django_geo.geo import GeoPoint

        point_a = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))
        point_b = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))

        assert point_a == point_b

    def test_geopoint_inequality(self):
        """Two GeoPoints with different coordinates are not equal."""
        from django_geo.geo import GeoPoint

        point_a = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))
        point_b = GeoPoint(latitude=Decimal('20.6597'), longitude=Decimal('-103.3496'))

        assert point_a != point_b

    def test_geopoint_str(self):
        """GeoPoint has readable string representation."""
        from django_geo.geo import GeoPoint

        point = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))

        assert '19.4326' in str(point)
        assert '-99.1332' in str(point)

    def test_geopoint_repr(self):
        """GeoPoint has debuggable repr."""
        from django_geo.geo import GeoPoint

        point = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))

        assert 'GeoPoint' in repr(point)
