# Chapter 15: Geography

> "Where in the world is this?"

---

Business happens in places. Customers have addresses. Deliveries have destinations. Service areas have boundaries. Tax rates depend on jurisdiction. Shipping costs depend on distance.

The Geography primitive captures location data with the precision that logistics, compliance, and customer service require.

## The Problem Geography Solves

Location data fails in predictable ways:

**Unstructured addresses.** "123 Main St" stored in a single text field can't be searched, validated, or geocoded reliably.

**Missing coordinates.** Addresses without latitude/longitude can't be plotted on maps, used for distance calculations, or matched to service areas.

**No hierarchy.** The relationship between address, city, state, country isn't captured—making it impossible to query "all customers in California" efficiently.

**Stale geocoding.** Addresses change. Buildings are demolished. Streets are renamed. One-time geocoding becomes inaccurate over time.

**Jurisdictional blindness.** Tax rates, regulations, and service availability vary by location. Systems that don't track jurisdiction can't apply the right rules.

## The Address Model

```python
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django_basemodels.models import SoftDeleteModel


class Country(models.Model):
    """Country reference data."""
    code = models.CharField(max_length=2, primary_key=True)  # ISO 3166-1 alpha-2
    code_alpha3 = models.CharField(max_length=3, unique=True)  # ISO 3166-1 alpha-3
    name = models.CharField(max_length=255)
    numeric_code = models.CharField(max_length=3)

    class Meta:
        verbose_name_plural = "countries"
        ordering = ['name']

    def __str__(self):
        return self.name


class Region(models.Model):
    """State, province, or administrative region."""
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='regions')
    code = models.CharField(max_length=10)  # State/province code
    name = models.CharField(max_length=255)
    region_type = models.CharField(max_length=50, blank=True)  # state, province, territory, etc.

    class Meta:
        unique_together = ['country', 'code']
        ordering = ['country', 'name']

    def __str__(self):
        return f"{self.name}, {self.country.code}"


class Address(SoftDeleteModel):
    """A physical address with geocoding support."""

    # Link to any model (customer, supplier, location, etc.)
    owner_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    owner_id = models.CharField(max_length=255, blank=True)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    # Address type
    ADDRESS_TYPES = [
        ('billing', 'Billing'),
        ('shipping', 'Shipping'),
        ('physical', 'Physical'),
        ('mailing', 'Mailing'),
        ('headquarters', 'Headquarters'),
        ('branch', 'Branch'),
    ]
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default='physical')

    # Structured address components
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    line3 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.ForeignKey(Country, on_delete=models.PROTECT)

    # Geocoding
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True
    )
    geocoded_at = models.DateTimeField(null=True, blank=True)
    geocode_accuracy = models.CharField(max_length=50, blank=True)  # rooftop, range, approximate

    # Validation
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_source = models.CharField(max_length=100, blank=True)

    # Temporal validity
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "addresses"
        indexes = [
            models.Index(fields=['postal_code']),
            models.Index(fields=['city', 'region']),
            models.Index(fields=['owner_content_type', 'owner_id']),
        ]

    @property
    def is_geocoded(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def coordinates(self):
        if self.is_geocoded:
            return (float(self.latitude), float(self.longitude))
        return None

    def formatted(self, include_country=True):
        """Return formatted address string."""
        lines = [self.line1]
        if self.line2:
            lines.append(self.line2)
        if self.line3:
            lines.append(self.line3)

        city_line = self.city
        if self.region:
            city_line += f", {self.region.code}"
        city_line += f" {self.postal_code}"
        lines.append(city_line)

        if include_country:
            lines.append(self.country.name)

        return "\n".join(lines)

    def __str__(self):
        return f"{self.line1}, {self.city}"
```

## Distance Calculations

```python
from math import radians, cos, sin, asin, sqrt
from decimal import Decimal


def haversine_distance(coord1, coord2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    Returns distance in kilometers.
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # Earth's radius in kilometers
    r = 6371

    return c * r


class AddressQuerySet(models.QuerySet):
    """QuerySet with geographic queries."""

    def within_radius(self, center_lat, center_lon, radius_km):
        """
        Find addresses within radius of a point.
        Note: For production, use PostGIS for efficient spatial queries.
        """
        addresses = []
        for addr in self.filter(latitude__isnull=False):
            dist = haversine_distance(
                (float(addr.latitude), float(addr.longitude)),
                (center_lat, center_lon)
            )
            if dist <= radius_km:
                addr._distance_km = dist
                addresses.append(addr)

        return sorted(addresses, key=lambda a: a._distance_km)

    def in_region(self, region):
        """Addresses in a specific region."""
        return self.filter(region=region)

    def in_country(self, country_code):
        """Addresses in a specific country."""
        return self.filter(country__code=country_code)

    def needs_geocoding(self):
        """Addresses that need geocoding."""
        return self.filter(latitude__isnull=True)

    def needs_verification(self):
        """Addresses that haven't been verified."""
        return self.filter(is_verified=False)
```

## Service Areas

Define geographic boundaries for service availability:

```python
class ServiceArea(SoftDeleteModel):
    """A geographic area where service is available."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Define by regions
    countries = models.ManyToManyField(Country, blank=True)
    regions = models.ManyToManyField(Region, blank=True)

    # Or define by postal code patterns
    postal_code_patterns = models.JSONField(default=list)  # ["902*", "903*", "904*"]

    # Or define by radius from a point
    center_latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True
    )
    center_longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True
    )
    radius_km = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )

    is_active = models.BooleanField(default=True)

    def contains_address(self, address):
        """Check if an address is within this service area."""
        # Check country
        if self.countries.exists():
            if address.country not in self.countries.all():
                return False

        # Check region
        if self.regions.exists():
            if address.region not in self.regions.all():
                return False

        # Check postal code patterns
        if self.postal_code_patterns:
            import fnmatch
            matches = any(
                fnmatch.fnmatch(address.postal_code, pattern)
                for pattern in self.postal_code_patterns
            )
            if not matches:
                return False

        # Check radius
        if self.center_latitude and address.is_geocoded:
            distance = haversine_distance(
                (float(self.center_latitude), float(self.center_longitude)),
                address.coordinates
            )
            if distance > float(self.radius_km):
                return False

        return True
```

## Tax Jurisdiction

Location determines taxation:

```python
class TaxJurisdiction(models.Model):
    """Tax rules for a geographic area."""

    name = models.CharField(max_length=255)
    jurisdiction_type = models.CharField(max_length=50)  # federal, state, county, city

    # Geographic scope
    country = models.ForeignKey(Country, on_delete=models.PROTECT)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True)
    postal_codes = models.JSONField(default=list)  # Specific postal codes

    # Tax rates
    sales_tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    use_tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    # Validity
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['country', 'region', 'name']

    @classmethod
    def for_address(cls, address, as_of_date=None):
        """Find applicable tax jurisdictions for an address."""
        from django.utils import timezone

        if as_of_date is None:
            as_of_date = timezone.now().date()

        jurisdictions = cls.objects.filter(
            country=address.country,
            effective_from__lte=as_of_date
        ).filter(
            models.Q(effective_to__isnull=True) |
            models.Q(effective_to__gte=as_of_date)
        )

        # Filter by region
        jurisdictions = jurisdictions.filter(
            models.Q(region__isnull=True) |
            models.Q(region=address.region)
        )

        # Filter by postal code
        matching = []
        for j in jurisdictions:
            if not j.postal_codes or address.postal_code in j.postal_codes:
                matching.append(j)

        return matching
```

## Geocoding Integration

```python
from django.utils import timezone
import requests


class GeocodingService:
    """Service for geocoding addresses."""

    def __init__(self, api_key=None):
        self.api_key = api_key

    def geocode(self, address):
        """
        Geocode an address and update its coordinates.
        Returns True if successful.
        """
        # Build query string
        query = f"{address.line1}, {address.city}"
        if address.region:
            query += f", {address.region.code}"
        query += f", {address.postal_code}, {address.country.code}"

        # Call geocoding API (example using Nominatim)
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                'q': query,
                'format': 'json',
                'limit': 1
            },
            headers={'User-Agent': 'YourApp/1.0'}
        )

        if response.status_code == 200:
            results = response.json()
            if results:
                address.latitude = results[0]['lat']
                address.longitude = results[0]['lon']
                address.geocoded_at = timezone.now()
                address.geocode_accuracy = results[0].get('type', 'unknown')
                address.save()
                return True

        return False

    def reverse_geocode(self, latitude, longitude):
        """Get address from coordinates."""
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                'lat': latitude,
                'lon': longitude,
                'format': 'json'
            },
            headers={'User-Agent': 'YourApp/1.0'}
        )

        if response.status_code == 200:
            return response.json()
        return None
```

## Why This Matters Later

The Geography primitive connects to:

- **Identity** (Chapter 6): Parties have addresses.
- **Agreements** (Chapter 8): Service areas define where agreements apply.
- **Ledger** (Chapter 10): Tax jurisdictions affect transaction amounts.
- **Catalog** (Chapter 9): Product availability varies by location.
- **Worklog** (Chapter 14): Service calls have locations.

Location seems simple until you need to:
- Calculate shipping costs across borders
- Apply the correct sales tax for a multi-jurisdiction order
- Determine if a service request is within your coverage area
- Comply with data residency requirements

The Geography primitive handles the complexity so your application doesn't have to reinvent it.

---

## How to Rebuild This Primitive

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-geo | `docs/prompts/django-geo.md` | ~40 tests |

### Using the Prompt

```bash
cat docs/prompts/django-geo.md | claude

# Request: "Implement Country and Region models with ISO codes,
# then Address with optional geocoding fields.
# Add ServiceArea with multiple boundary types."
```

### Key Constraints

- **ISO-3166 codes**: Country uses 2-letter, Region uses subdivision codes
- **Decimal coordinates**: Latitude/longitude as DecimalField (9,6), never Float
- **Haversine distance**: Pure math calculation, no external dependencies required
- **Optional geocoding**: Coordinates are nullable, geocoding is async

If Claude uses FloatField for coordinates or hardcodes country data, that's a constraint violation.

---

*Status: Draft*
