# Architecture: django-geo

**Status:** Stable / v0.1.0

Geographic entities with coordinate validation and distance calculations.

---

## What This Package Is For

Answering the question: **"Where is this, and is it within our service area?"**

Use cases:
- Storing physical locations (places, addresses)
- Defining service areas (delivery zones, coverage areas)
- Point-in-radius containment checks
- Distance calculations between coordinates
- Address formatting

---

## What This Package Is NOT For

- **Not full GIS** - Use PostGIS/GeoDjango for complex geospatial queries
- **Not geocoding** - Use Google Maps/Mapbox for address → coordinates
- **Not routing** - Use mapping APIs for directions/routes
- **Not polygon shapes** - Only supports circular service areas

---

## Design Principles

1. **Decimal precision** - 6 decimal places (~0.111m precision)
2. **Constraint enforcement** - Database constraints validate lat/long ranges
3. **Value object pattern** - GeoPoint for coordinate handling
4. **Simple containment** - Circle-based service areas (center + radius)
5. **Independence** - No dependency on PostGIS/heavy GIS libraries

---

## Data Model

```
Place                                  ServiceArea
├── id (UUID, BaseModel)               ├── id (UUID, BaseModel)
├── name                               ├── name
├── place_type (poi|landmark|...)      ├── code (unique)
├── address_line1                      ├── area_type (delivery|coverage|...)
├── address_line2                      ├── center_latitude (-90 to 90)
├── city                               ├── center_longitude (-180 to 180)
├── state                              ├── radius_km (> 0)
├── postal_code                        ├── is_active
├── country                            └── BaseModel fields
├── latitude (-90 to 90)
├── longitude (-180 to 180)
├── is_verified
├── verified_at
└── BaseModel fields

GeoPoint (Value Object)
├── latitude: Decimal
├── longitude: Decimal
└── distance_to(other: GeoPoint) → km
```

---

## Public API

### Creating Places

```python
from django_geo.models import Place

place = Place.objects.create(
    name='Central Hospital',
    place_type='facility',
    address_line1='123 Main Street',
    city='Mexico City',
    state='CDMX',
    postal_code='06600',
    country='MX',
    latitude=Decimal('19.432608'),
    longitude=Decimal('-99.133209'),
)

# Full address formatting
print(place.full_address)
# "123 Main Street, Mexico City, CDMX 06600, MX"

# Convert to GeoPoint
point = place.as_geopoint()
```

### Creating Service Areas

```python
from django_geo.models import ServiceArea

zone = ServiceArea.objects.create(
    name='Downtown Delivery',
    code='DELIVERY-001',
    area_type='delivery',
    center_latitude=Decimal('19.432608'),
    center_longitude=Decimal('-99.133209'),
    radius_km=Decimal('5.0'),  # 5km radius
)

# Check if point is in zone
from django_geo.geo import GeoPoint

customer_location = GeoPoint(
    latitude=Decimal('19.440000'),
    longitude=Decimal('-99.140000')
)

if zone.contains(customer_location):
    print("Customer is in delivery zone!")
```

### Distance Calculations

```python
from django_geo.geo import GeoPoint
from decimal import Decimal

point_a = GeoPoint(Decimal('19.432608'), Decimal('-99.133209'))
point_b = GeoPoint(Decimal('19.440000'), Decimal('-99.140000'))

distance = point_a.distance_to(point_b)
print(f"Distance: {distance:.2f} km")
```

---

## Hard Rules

1. **Latitude range** - Must be -90 to 90 (database constraint)
2. **Longitude range** - Must be -180 to 180 (database constraint)
3. **Positive radius** - ServiceArea.radius_km must be > 0 (database constraint)
4. **Unique service area code** - code field is unique

---

## Invariants

- `Place.latitude` is always in range [-90, 90]
- `Place.longitude` is always in range [-180, 180]
- `ServiceArea.center_latitude` is in range [-90, 90]
- `ServiceArea.center_longitude` is in range [-180, 180]
- `ServiceArea.radius_km` is always > 0
- `ServiceArea.code` is globally unique

---

## Known Gotchas

### 1. Decimal Required for Coordinates

**Problem:** Using float causes precision issues.

```python
# CAUTION - float precision
place = Place.objects.create(
    latitude=19.432608,  # May have precision issues
    longitude=-99.133209,
)

# BETTER - use Decimal
from decimal import Decimal
place = Place.objects.create(
    latitude=Decimal('19.432608'),
    longitude=Decimal('-99.133209'),
)
```

### 2. Distance Calculation Approximation

**Problem:** Expecting exact distances.

```python
# distance_to uses Haversine formula - good for most purposes
# but assumes Earth is a perfect sphere

# For surveying-grade accuracy, use a full GIS library
```

### 3. Constraint Violations

**Problem:** Invalid coordinates rejected at database level.

```python
place = Place.objects.create(
    latitude=Decimal('100.0'),  # Invalid! > 90
    ...
)
# IntegrityError: check constraint "place_valid_latitude" violated
```

---

## Recommended Usage

### 1. Validate Before Save

```python
def create_place_safe(lat, lon, **kwargs):
    """Create place with pre-validation."""
    lat = Decimal(str(lat))
    lon = Decimal(str(lon))

    if not (-90 <= lat <= 90):
        raise ValueError(f"Invalid latitude: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Invalid longitude: {lon}")

    return Place.objects.create(
        latitude=lat,
        longitude=lon,
        **kwargs
    )
```

### 2. Use Service Areas for Zone Checks

```python
def get_delivery_zones_for_location(location: GeoPoint):
    """Find all active delivery zones containing this location."""
    zones = []
    for area in ServiceArea.objects.filter(
        area_type='delivery',
        is_active=True,
    ):
        if area.contains(location):
            zones.append(area)
    return zones
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- Place model with address and coordinates
- ServiceArea with center/radius
- GeoPoint value object
- Haversine distance calculation
- Database constraints for coordinate validation
