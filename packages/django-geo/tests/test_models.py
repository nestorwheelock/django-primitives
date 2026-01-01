"""Tests for django-geo models."""
import pytest
from decimal import Decimal

from django.utils import timezone


@pytest.mark.django_db
class TestPlace:
    """Tests for Place model."""

    def test_place_creation(self):
        """Place can be created with required fields."""
        from django_geo.models import Place

        place = Place.objects.create(
            name='Zócalo',
            place_type='landmark',
            address_line1='Plaza de la Constitución',
            city='Mexico City',
            state='CDMX',
            postal_code='06000',
            country='MX',
            latitude=Decimal('19.4326'),
            longitude=Decimal('-99.1332'),
        )

        assert place.pk is not None
        assert place.name == 'Zócalo'
        assert place.latitude == Decimal('19.4326')

    def test_place_has_uuid(self):
        """Place uses UUID primary key."""
        from django_geo.models import Place
        import uuid

        place = Place.objects.create(
            name='Test Place',
            place_type='poi',
            city='Test City',
            state='TS',
            postal_code='12345',
            country='MX',
            latitude=Decimal('19.0'),
            longitude=Decimal('-99.0'),
        )

        assert isinstance(place.pk, uuid.UUID)

    def test_place_full_address_property(self):
        """Place.full_address returns formatted address."""
        from django_geo.models import Place

        place = Place.objects.create(
            name='Test Place',
            place_type='poi',
            address_line1='123 Main St',
            address_line2='Suite 100',
            city='Mexico City',
            state='CDMX',
            postal_code='06000',
            country='MX',
            latitude=Decimal('19.0'),
            longitude=Decimal('-99.0'),
        )

        full = place.full_address
        assert '123 Main St' in full
        assert 'Mexico City' in full
        assert 'CDMX' in full

    def test_place_as_geopoint(self):
        """Place.as_geopoint() returns a GeoPoint."""
        from django_geo.models import Place
        from django_geo.geo import GeoPoint

        place = Place.objects.create(
            name='Test Place',
            place_type='poi',
            city='Test City',
            state='TS',
            postal_code='12345',
            country='MX',
            latitude=Decimal('19.4326'),
            longitude=Decimal('-99.1332'),
        )

        point = place.as_geopoint()

        assert isinstance(point, GeoPoint)
        assert point.latitude == Decimal('19.4326')
        assert point.longitude == Decimal('-99.1332')

    def test_place_str(self):
        """Place __str__ returns name."""
        from django_geo.models import Place

        place = Place.objects.create(
            name='Zócalo',
            place_type='landmark',
            city='Mexico City',
            state='CDMX',
            postal_code='06000',
            country='MX',
            latitude=Decimal('19.0'),
            longitude=Decimal('-99.0'),
        )

        assert str(place) == 'Zócalo'

    def test_place_types(self):
        """Place supports various place types."""
        from django_geo.models import Place

        for place_type in ['poi', 'landmark', 'facility', 'intersection', 'other']:
            place = Place.objects.create(
                name=f'Test {place_type}',
                place_type=place_type,
                city='Test City',
                state='TS',
                postal_code='12345',
                country='MX',
                latitude=Decimal('19.0'),
                longitude=Decimal('-99.0'),
            )
            assert place.place_type == place_type


@pytest.mark.django_db
class TestServiceArea:
    """Tests for ServiceArea model."""

    def test_service_area_creation(self):
        """ServiceArea can be created with center and radius."""
        from django_geo.models import ServiceArea

        area = ServiceArea.objects.create(
            name='Centro Delivery Zone',
            code='centro',
            area_type='delivery',
            center_latitude=Decimal('19.4326'),
            center_longitude=Decimal('-99.1332'),
            radius_km=Decimal('5.0'),
        )

        assert area.pk is not None
        assert area.name == 'Centro Delivery Zone'
        assert area.radius_km == Decimal('5.0')

    def test_service_area_code_unique(self):
        """ServiceArea code must be unique."""
        from django_geo.models import ServiceArea
        from django.db import IntegrityError

        ServiceArea.objects.create(
            name='Zone A',
            code='zone-a',
            area_type='delivery',
            center_latitude=Decimal('19.0'),
            center_longitude=Decimal('-99.0'),
            radius_km=Decimal('5.0'),
        )

        with pytest.raises(IntegrityError):
            ServiceArea.objects.create(
                name='Zone A Duplicate',
                code='zone-a',  # Same code
                area_type='delivery',
                center_latitude=Decimal('20.0'),
                center_longitude=Decimal('-100.0'),
                radius_km=Decimal('5.0'),
            )

    def test_service_area_contains_center(self):
        """ServiceArea.contains() returns True for center point."""
        from django_geo.models import ServiceArea
        from django_geo.geo import GeoPoint

        area = ServiceArea.objects.create(
            name='Test Zone',
            code='test',
            area_type='delivery',
            center_latitude=Decimal('19.4326'),
            center_longitude=Decimal('-99.1332'),
            radius_km=Decimal('5.0'),
        )

        center = GeoPoint(latitude=Decimal('19.4326'), longitude=Decimal('-99.1332'))

        assert area.contains(center) is True

    def test_service_area_contains_point_inside(self):
        """ServiceArea.contains() returns True for point inside radius."""
        from django_geo.models import ServiceArea
        from django_geo.geo import GeoPoint

        area = ServiceArea.objects.create(
            name='Test Zone',
            code='test-inside',
            area_type='delivery',
            center_latitude=Decimal('19.4326'),
            center_longitude=Decimal('-99.1332'),
            radius_km=Decimal('10.0'),  # 10km radius
        )

        # Point ~1km away from center
        nearby = GeoPoint(latitude=Decimal('19.4400'), longitude=Decimal('-99.1332'))

        assert area.contains(nearby) is True

    def test_service_area_excludes_point_outside(self):
        """ServiceArea.contains() returns False for point outside radius."""
        from django_geo.models import ServiceArea
        from django_geo.geo import GeoPoint

        area = ServiceArea.objects.create(
            name='Small Zone',
            code='small',
            area_type='delivery',
            center_latitude=Decimal('19.4326'),
            center_longitude=Decimal('-99.1332'),
            radius_km=Decimal('1.0'),  # 1km radius
        )

        # Point ~50km away
        far_away = GeoPoint(latitude=Decimal('20.0000'), longitude=Decimal('-99.1332'))

        assert area.contains(far_away) is False

    def test_service_area_str(self):
        """ServiceArea __str__ returns name."""
        from django_geo.models import ServiceArea

        area = ServiceArea.objects.create(
            name='Centro Zone',
            code='centro',
            area_type='delivery',
            center_latitude=Decimal('19.0'),
            center_longitude=Decimal('-99.0'),
            radius_km=Decimal('5.0'),
        )

        assert str(area) == 'Centro Zone'

    def test_service_area_is_active_default(self):
        """ServiceArea.is_active defaults to True."""
        from django_geo.models import ServiceArea

        area = ServiceArea.objects.create(
            name='Active Zone',
            code='active',
            area_type='delivery',
            center_latitude=Decimal('19.0'),
            center_longitude=Decimal('-99.0'),
            radius_km=Decimal('5.0'),
        )

        assert area.is_active is True

    def test_service_area_types(self):
        """ServiceArea supports various area types."""
        from django_geo.models import ServiceArea

        for area_type in ['delivery', 'coverage', 'tax_jurisdiction', 'other']:
            area = ServiceArea.objects.create(
                name=f'Test {area_type}',
                code=f'test-{area_type}',
                area_type=area_type,
                center_latitude=Decimal('19.0'),
                center_longitude=Decimal('-99.0'),
                radius_km=Decimal('5.0'),
            )
            assert area.area_type == area_type
