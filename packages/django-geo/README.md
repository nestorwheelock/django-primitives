# django-geo

Geographic primitives for Django applications. Provides location entities, coordinate handling, and geographic queries without requiring PostGIS.

## Features

- **GeoPoint**: Immutable coordinate value object with Haversine distance calculation
- **Place**: Standalone location entity with coordinates and address
- **ServiceArea**: Geographic zones defined by center point and radius
- **Geographic QuerySet methods**: `within_radius()`, `nearest()`, `containing()`

## Installation

```bash
pip install django-geo
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_geo',
]
```

Run migrations:

```bash
python manage.py migrate django_geo
```

## Usage

### GeoPoint Value Object

```python
from decimal import Decimal
from django_geo.geo import GeoPoint

# Create coordinates
mexico_city = GeoPoint(
    latitude=Decimal('19.4326'),
    longitude=Decimal('-99.1332')
)

guadalajara = GeoPoint(
    latitude=Decimal('20.6597'),
    longitude=Decimal('-103.3496')
)

# Calculate distance (Haversine formula)
distance = mexico_city.distance_to(guadalajara)
print(f"Distance: {distance} km")  # ~460 km
```

### Place Model

```python
from decimal import Decimal
from django_geo.models import Place

# Create a location
zocalo = Place.objects.create(
    name='Zocalo',
    place_type='landmark',
    address_line1='Plaza de la Constitucion',
    city='Mexico City',
    state='CDMX',
    postal_code='06000',
    country='MX',
    latitude=Decimal('19.4326'),
    longitude=Decimal('-99.1332'),
)

# Get as GeoPoint
point = zocalo.as_geopoint()

# Full address string
print(zocalo.full_address)
# "Plaza de la Constitucion, Mexico City, CDMX 06000, MX"
```

### Geographic Queries

```python
from decimal import Decimal
from django_geo.models import Place

# Find places within 10km of a point
nearby = Place.objects.within_radius(
    lat=Decimal('19.4326'),
    lng=Decimal('-99.1332'),
    km=Decimal('10.0'),
)

# Find 5 nearest places
nearest = Place.objects.nearest(
    lat=Decimal('19.4326'),
    lng=Decimal('-99.1332'),
    limit=5,
)
```

### ServiceArea Model

```python
from decimal import Decimal
from django_geo.models import ServiceArea
from django_geo.geo import GeoPoint

# Create a delivery zone
centro_zone = ServiceArea.objects.create(
    name='Centro Delivery Zone',
    code='centro',
    area_type='delivery',
    center_latitude=Decimal('19.4326'),
    center_longitude=Decimal('-99.1332'),
    radius_km=Decimal('5.0'),
)

# Check if a point is within the zone
customer_location = GeoPoint(
    latitude=Decimal('19.4400'),
    longitude=Decimal('-99.1400')
)

if centro_zone.contains(customer_location):
    print("Delivery available!")

# Find all zones containing a point
zones = ServiceArea.objects.containing(
    lat=Decimal('19.4400'),
    lng=Decimal('-99.1400'),
)
```

## Models

### Place

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `name` | CharField | Location name |
| `place_type` | CharField | poi, landmark, facility, intersection, other |
| `address_line1` | CharField | Street address |
| `address_line2` | CharField | Additional address info (optional) |
| `city` | CharField | City name |
| `state` | CharField | State/province |
| `postal_code` | CharField | Postal/ZIP code |
| `country` | CharField | 2-letter country code (default: MX) |
| `latitude` | DecimalField | Latitude coordinate |
| `longitude` | DecimalField | Longitude coordinate |
| `is_verified` | BooleanField | Whether location is verified |
| `verified_at` | DateTimeField | When verified (optional) |

### ServiceArea

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `name` | CharField | Zone name |
| `code` | CharField | Unique zone code |
| `area_type` | CharField | delivery, coverage, tax_jurisdiction, other |
| `center_latitude` | DecimalField | Center point latitude |
| `center_longitude` | DecimalField | Center point longitude |
| `radius_km` | DecimalField | Radius in kilometers |
| `is_active` | BooleanField | Whether zone is active |

## QuerySet Methods

### PlaceQuerySet

- `within_radius(lat, lng, km)` - Find places within radius of a point
- `nearest(lat, lng, limit=10)` - Find N nearest places to a point

### ServiceAreaQuerySet

- `containing(lat, lng)` - Find areas that contain a point
- `active()` - Filter to active areas only

## Testing

```bash
cd packages/django-geo
pip install -e .
pytest tests/ -v
```

## License

MIT
