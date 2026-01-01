# Prompt: Rebuild django-geo

## Instruction

Create a Django package called `django-geo` that provides geographic primitives for location-based queries and service area management.

## Package Purpose

Provide geographic functionality without requiring PostGIS:
- `GeoPoint` - Immutable coordinate value object with Haversine distance
- `Place` - Standalone location entity with coordinates and address
- `ServiceArea` - Geographic zones defined by center point and radius
- QuerySet methods: `within_radius()`, `nearest()`, `containing()`

## Dependencies

- Django >= 4.2
- No PostGIS required (pure Python implementation)

## File Structure

```
packages/django-geo/
├── pyproject.toml
├── README.md
├── src/django_geo/
│   ├── __init__.py
│   ├── apps.py
│   ├── geo.py
│   ├── models.py
│   ├── querysets.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_geo.py
    ├── test_models.py
    └── test_queries.py
```

## GeoPoint Value Object

### geo.py

```python
import math
from dataclasses import dataclass
from decimal import Decimal

EARTH_RADIUS_KM = Decimal('6371.0')

@dataclass(frozen=True)
class GeoPoint:
    """Immutable geographic coordinate point."""
    latitude: Decimal
    longitude: Decimal

    def __post_init__(self):
        # Convert floats to Decimal
        if not isinstance(self.latitude, Decimal):
            object.__setattr__(self, 'latitude', Decimal(str(self.latitude)))
        if not isinstance(self.longitude, Decimal):
            object.__setattr__(self, 'longitude', Decimal(str(self.longitude)))

    def distance_to(self, other: 'GeoPoint') -> Decimal:
        """Calculate Haversine distance in km."""
        lat1 = math.radians(float(self.latitude))
        lat2 = math.radians(float(other.latitude))
        lon1 = math.radians(float(self.longitude))
        lon2 = math.radians(float(other.longitude))

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        distance = float(EARTH_RADIUS_KM) * c
        return Decimal(str(round(distance, 6)))

    def __str__(self) -> str:
        return f"({self.latitude}, {self.longitude})"
```

## Models Specification

### Place Model

```python
class Place(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    place_type = models.CharField(max_length=20, choices=[
        ('poi', 'Point of Interest'),
        ('landmark', 'Landmark'),
        ('facility', 'Facility'),
        ('intersection', 'Intersection'),
        ('other', 'Other'),
    ], default='poi')

    # Address components
    address_line1 = models.CharField(max_length=255, blank=True, default='')
    address_line2 = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default='MX')

    # Coordinates (6 decimal places = ±0.111m precision)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlaceQuerySet.as_manager()

    class Meta:
        ordering = ['name']

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
        return GeoPoint(latitude=self.latitude, longitude=self.longitude)
```

### ServiceArea Model

```python
class ServiceArea(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    area_type = models.CharField(max_length=20, choices=[
        ('delivery', 'Delivery Zone'),
        ('coverage', 'Coverage Area'),
        ('tax_jurisdiction', 'Tax Jurisdiction'),
        ('other', 'Other'),
    ], default='delivery')

    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_km = models.DecimalField(max_digits=10, decimal_places=2)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceAreaQuerySet.as_manager()

    class Meta:
        ordering = ['name']

    def get_center(self) -> GeoPoint:
        return GeoPoint(latitude=self.center_latitude, longitude=self.center_longitude)

    def contains(self, point: GeoPoint) -> bool:
        """Check if point is within this service area."""
        center = self.get_center()
        distance = center.distance_to(point)
        return distance <= self.radius_km
```

## QuerySet Methods

### querysets.py

```python
from decimal import Decimal
from django.db import models
from django.db.models import Case, When

class PlaceQuerySet(models.QuerySet):
    def within_radius(self, lat, lng, km):
        """Find places within radius using bounding box + Haversine."""
        lat = Decimal(str(lat))
        lng = Decimal(str(lng))
        km = Decimal(str(km))

        # Bounding box approximation (1° lat ≈ 111km)
        lat_delta = km / Decimal('111.0')
        cos_lat = max(Decimal('0.01'), abs(Decimal(str(math.cos(math.radians(float(lat)))))))
        lng_delta = km / (Decimal('111.0') * cos_lat)

        # Filter by bounding box first (fast)
        candidates = self.filter(
            latitude__gte=lat - lat_delta,
            latitude__lte=lat + lat_delta,
            longitude__gte=lng - lng_delta,
            longitude__lte=lng + lng_delta,
        )

        # Then verify with Haversine (accurate)
        from .geo import GeoPoint
        center = GeoPoint(latitude=lat, longitude=lng)
        matching_pks = []
        for place in candidates:
            point = place.as_geopoint()
            if center.distance_to(point) <= km:
                matching_pks.append(place.pk)

        return self.filter(pk__in=matching_pks)

    def nearest(self, lat, lng, limit=10):
        """Find N nearest places ordered by distance."""
        from .geo import GeoPoint
        center = GeoPoint(latitude=Decimal(str(lat)), longitude=Decimal(str(lng)))

        distances = []
        for place in self:
            point = place.as_geopoint()
            distance = center.distance_to(point)
            distances.append((place.pk, distance))

        distances.sort(key=lambda x: x[1])
        ordered_pks = [pk for pk, _ in distances[:limit]]

        if not ordered_pks:
            return self.none()

        # Preserve order with Case/When
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_pks)])
        return self.filter(pk__in=ordered_pks).order_by(preserved)


class ServiceAreaQuerySet(models.QuerySet):
    def containing(self, lat, lng):
        """Find service areas that contain the given point."""
        from .geo import GeoPoint
        point = GeoPoint(latitude=Decimal(str(lat)), longitude=Decimal(str(lng)))

        matching_pks = []
        for area in self:
            if area.contains(point):
                matching_pks.append(area.pk)

        return self.filter(pk__in=matching_pks)

    def active(self):
        return self.filter(is_active=True)
```

## Test Cases (45 tests)

### GeoPoint Tests (8 tests)
1. `test_geopoint_creation` - Create with Decimal coordinates
2. `test_geopoint_creation_from_floats` - Floats auto-convert
3. `test_geopoint_distance_to_same_point_is_zero` - Zero distance
4. `test_geopoint_distance_to_known_cities` - CDMX to Guadalajara ≈ 460km
5. `test_geopoint_distance_nyc_to_la` - ~3944km
6. `test_geopoint_distance_is_symmetric` - A→B = B→A
7. `test_geopoint_equality` - Same coords are equal
8. `test_geopoint_str` - "(lat, lng)" format

### Place Model Tests (8 tests)
1. `test_place_creation` - Create with all fields
2. `test_place_has_uuid` - UUID primary key
3. `test_place_full_address_property` - Formats address components
4. `test_place_as_geopoint` - Converts to GeoPoint
5. `test_place_str` - Returns name
6. `test_place_types` - All type choices work

### ServiceArea Model Tests (8 tests)
1. `test_service_area_creation` - Create with all fields
2. `test_service_area_code_unique` - Code is unique constraint
3. `test_service_area_contains_center` - Center is contained
4. `test_service_area_contains_point_inside` - Point within radius
5. `test_service_area_excludes_point_outside` - Point beyond radius
6. `test_service_area_str` - Returns name
7. `test_service_area_is_active_default` - Defaults to True
8. `test_service_area_types` - All type choices work

### PlaceQuerySet Tests (4 tests)
1. `test_within_radius_finds_nearby_places` - 10km search
2. `test_within_radius_excludes_far_places` - Beyond radius excluded
3. `test_within_radius_empty_when_none_nearby` - Empty result
4. `test_nearest_returns_ordered_by_distance` - Ordered correctly
5. `test_nearest_respects_limit` - Limit parameter works

### ServiceAreaQuerySet Tests (4 tests)
1. `test_containing_finds_areas` - Finds containing areas
2. `test_containing_finds_overlapping_areas` - Multiple overlapping
3. `test_containing_excludes_non_matching` - Excludes non-matching
4. `test_active_only_filter` - Filters inactive

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = ['GeoPoint', 'Place', 'ServiceArea']

def __getattr__(name):
    if name == 'GeoPoint':
        from .geo import GeoPoint
        return GeoPoint
    if name == 'Place':
        from .models import Place
        return Place
    if name == 'ServiceArea':
        from .models import ServiceArea
        return ServiceArea
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Test Data Fixtures

```python
@pytest.fixture
def places(db):
    from django_geo.models import Place
    cdmx = Place.objects.create(
        name='Zócalo', city='Mexico City', state='CDMX',
        postal_code='06000', latitude=Decimal('19.4326'), longitude=Decimal('-99.1332')
    )
    roma = Place.objects.create(
        name='Roma Norte', city='Mexico City', state='CDMX',
        postal_code='06700', latitude=Decimal('19.4195'), longitude=Decimal('-99.1670')
    )
    santa_fe = Place.objects.create(
        name='Santa Fe', city='Mexico City', state='CDMX',
        postal_code='05348', latitude=Decimal('19.3590'), longitude=Decimal('-99.2600')
    )
    gdl = Place.objects.create(
        name='Guadalajara', city='Guadalajara', state='Jalisco',
        postal_code='44100', latitude=Decimal('20.6597'), longitude=Decimal('-103.3496')
    )
    return {'cdmx': cdmx, 'roma': roma, 'santa_fe': santa_fe, 'gdl': gdl}
```

## Key Behaviors

1. **Haversine Formula**: Great-circle distance calculation
2. **Bounding Box Optimization**: Fast DB filter before expensive calculation
3. **Coordinate Precision**: 6 decimal places = ±0.111m
4. **UUID Primary Keys**: Both Place and ServiceArea use UUIDs
5. **Service Area Containment**: Distance from center ≤ radius

## Acceptance Criteria

- [ ] GeoPoint value object with distance_to()
- [ ] Place model with full_address property
- [ ] ServiceArea model with contains() method
- [ ] PlaceQuerySet with within_radius(), nearest()
- [ ] ServiceAreaQuerySet with containing(), active()
- [ ] All 45 tests passing
- [ ] README with usage examples
