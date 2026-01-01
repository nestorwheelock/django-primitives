"""QuerySet classes for django-geo models."""
import math
from decimal import Decimal
from typing import Union

from django.db import models

from .geo import EARTH_RADIUS_KM


class PlaceQuerySet(models.QuerySet):
    """QuerySet for Place model with geographic queries."""

    def within_radius(
        self,
        lat: Union[Decimal, float],
        lng: Union[Decimal, float],
        km: Union[Decimal, float],
    ) -> 'PlaceQuerySet':
        """Find places within a given radius of a point.

        Uses the Haversine formula approximation for distance filtering.

        Args:
            lat: Latitude of the center point.
            lng: Longitude of the center point.
            km: Radius in kilometers.

        Returns:
            QuerySet of places within the specified radius.
        """
        lat = Decimal(str(lat))
        lng = Decimal(str(lng))
        km = Decimal(str(km))

        # Use bounding box for initial filtering (faster)
        # 1 degree latitude ≈ 111km
        lat_delta = km / Decimal('111.0')
        # 1 degree longitude varies by latitude
        cos_lat = abs(math.cos(math.radians(float(lat))))
        lng_delta = km / (Decimal('111.0') * Decimal(str(cos_lat))) if cos_lat > 0 else km / Decimal('111.0')

        # Bounding box filter
        qs = self.filter(
            latitude__gte=lat - lat_delta,
            latitude__lte=lat + lat_delta,
            longitude__gte=lng - lng_delta,
            longitude__lte=lng + lng_delta,
        )

        # Apply Haversine formula for accurate filtering
        # Using database functions for calculation
        results = []
        for place in qs:
            from .geo import GeoPoint
            center = GeoPoint(latitude=lat, longitude=lng)
            place_point = place.as_geopoint()
            distance = center.distance_to(place_point)
            if distance <= km:
                results.append(place.pk)

        return self.filter(pk__in=results)

    def nearest(
        self,
        lat: Union[Decimal, float],
        lng: Union[Decimal, float],
        limit: int = 10,
    ) -> 'PlaceQuerySet':
        """Find the N nearest places to a point.

        Args:
            lat: Latitude of the center point.
            lng: Longitude of the center point.
            limit: Maximum number of results to return.

        Returns:
            QuerySet of nearest places, ordered by distance.
        """
        lat = Decimal(str(lat))
        lng = Decimal(str(lng))

        # Calculate distances and sort
        from .geo import GeoPoint
        center = GeoPoint(latitude=lat, longitude=lng)

        # Get all places with their distances
        places_with_distance = []
        for place in self.all():
            place_point = place.as_geopoint()
            distance = center.distance_to(place_point)
            places_with_distance.append((place.pk, distance))

        # Sort by distance and get top N
        places_with_distance.sort(key=lambda x: x[1])
        top_pks = [pk for pk, _ in places_with_distance[:limit]]

        # Preserve order using CASE WHEN
        if not top_pks:
            return self.none()

        # Return queryset preserving order
        preserved = models.Case(
            *[models.When(pk=pk, then=pos) for pos, pk in enumerate(top_pks)]
        )
        return self.filter(pk__in=top_pks).order_by(preserved)


class ServiceAreaQuerySet(models.QuerySet):
    """QuerySet for ServiceArea model with geographic queries."""

    def containing(
        self,
        lat: Union[Decimal, float],
        lng: Union[Decimal, float],
    ) -> 'ServiceAreaQuerySet':
        """Find service areas that contain a given point.

        Args:
            lat: Latitude of the point.
            lng: Longitude of the point.

        Returns:
            QuerySet of service areas containing the point.
        """
        lat = Decimal(str(lat))
        lng = Decimal(str(lng))

        from .geo import GeoPoint
        point = GeoPoint(latitude=lat, longitude=lng)

        # Check each area's containment
        containing_pks = []
        for area in self.all():
            if area.contains(point):
                containing_pks.append(area.pk)

        return self.filter(pk__in=containing_pks)

    def active(self) -> 'ServiceAreaQuerySet':
        """Filter to only active service areas.

        Returns:
            QuerySet of active service areas.
        """
        return self.filter(is_active=True)
