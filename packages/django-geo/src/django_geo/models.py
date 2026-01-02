"""Models for django-geo package."""
from decimal import Decimal

from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel

from .geo import GeoPoint
from .querysets import PlaceQuerySet, ServiceAreaQuerySet


class Place(BaseModel):
    """A standalone geographic location entity.

    Represents a physical place with coordinates and address information,
    independent of any Party (Person/Organization).
    """

    PLACE_TYPES = [
        ('poi', 'Point of Interest'),
        ('landmark', 'Landmark'),
        ('facility', 'Facility'),
        ('intersection', 'Intersection'),
        ('other', 'Other'),
    ]

    # BaseModel provides: id (UUID), created_at, updated_at, deleted_at

    # Basic info
    name = models.CharField(max_length=255)
    place_type = models.CharField(max_length=20, choices=PLACE_TYPES, default='poi')

    # Address components
    address_line1 = models.CharField(max_length=255, blank=True, default='')
    address_line2 = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default='MX')

    # Coordinates (9 digits, 6 decimal places = ±0.111m precision)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # Metadata
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    objects = PlaceQuerySet.as_manager()

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    @property
    def full_address(self) -> str:
        """Return formatted full address string."""
        parts = []
        if self.address_line1:
            parts.append(self.address_line1)
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        parts.append(self.country)
        return ', '.join(parts)

    def as_geopoint(self) -> GeoPoint:
        """Return coordinates as a GeoPoint value object."""
        return GeoPoint(latitude=self.latitude, longitude=self.longitude)


class ServiceArea(BaseModel):
    """A geographic service zone defined by center and radius.

    Used for delivery zones, coverage areas, tax jurisdictions, etc.
    """

    AREA_TYPES = [
        ('delivery', 'Delivery Zone'),
        ('coverage', 'Coverage Area'),
        ('tax_jurisdiction', 'Tax Jurisdiction'),
        ('other', 'Other'),
    ]

    # BaseModel provides: id (UUID), created_at, updated_at, deleted_at

    # Basic info
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    area_type = models.CharField(max_length=20, choices=AREA_TYPES, default='delivery')

    # Center point coordinates
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # Radius in kilometers
    radius_km = models.DecimalField(max_digits=10, decimal_places=2)

    # Status
    is_active = models.BooleanField(default=True)

    objects = ServiceAreaQuerySet.as_manager()

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    def get_center(self) -> GeoPoint:
        """Return center point as a GeoPoint value object."""
        return GeoPoint(latitude=self.center_latitude, longitude=self.center_longitude)

    def contains(self, point: GeoPoint) -> bool:
        """Check if a point is within this service area.

        Args:
            point: The GeoPoint to check.

        Returns:
            True if the point is within the radius, False otherwise.
        """
        center = self.get_center()
        distance = center.distance_to(point)
        return distance <= self.radius_km
