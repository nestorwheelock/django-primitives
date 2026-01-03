# Capítulo 15: Geografía

> "¿Dónde en el mundo está esto?"

---

Los negocios ocurren en lugares. Los clientes tienen direcciones. Las entregas tienen destinos. Las áreas de servicio tienen límites. Las tasas de impuestos dependen de la jurisdicción. Los costos de envío dependen de la distancia.

La primitiva de Geografía captura datos de ubicación con la precisión que la logística, el cumplimiento normativo y el servicio al cliente requieren.

## El Problema que Resuelve la Geografía

Los datos de ubicación fallan de maneras predecibles:

**Direcciones no estructuradas.** "Calle Principal 123" almacenado en un único campo de texto no puede ser buscado, validado o geocodificado de manera confiable.

**Coordenadas faltantes.** Las direcciones sin latitud/longitud no pueden ser trazadas en mapas, usadas para cálculos de distancia, o emparejadas con áreas de servicio.

**Sin jerarquía.** La relación entre dirección, ciudad, estado, país no está capturada—haciendo imposible consultar "todos los clientes en California" de manera eficiente.

**Geocodificación obsoleta.** Las direcciones cambian. Los edificios son demolidos. Las calles son renombradas. La geocodificación única se vuelve inexacta con el tiempo.

**Ceguera jurisdiccional.** Las tasas de impuestos, regulaciones y disponibilidad de servicios varían por ubicación. Los sistemas que no rastrean jurisdicción no pueden aplicar las reglas correctas.

## El Modelo Address

```python
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django_basemodels.models import SoftDeleteModel


class Country(models.Model):
    """Datos de referencia de país."""
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
    """Estado, provincia o región administrativa."""
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='regions')
    code = models.CharField(max_length=10)  # Código de estado/provincia
    name = models.CharField(max_length=255)
    region_type = models.CharField(max_length=50, blank=True)  # estado, provincia, territorio, etc.

    class Meta:
        unique_together = ['country', 'code']
        ordering = ['country', 'name']

    def __str__(self):
        return f"{self.name}, {self.country.code}"


class Address(SoftDeleteModel):
    """Una dirección física con soporte de geocodificación."""

    # Enlace a cualquier modelo (cliente, proveedor, ubicación, etc.)
    owner_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    owner_id = models.CharField(max_length=255, blank=True)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    # Tipo de dirección
    ADDRESS_TYPES = [
        ('billing', 'Facturación'),
        ('shipping', 'Envío'),
        ('physical', 'Física'),
        ('mailing', 'Correspondencia'),
        ('headquarters', 'Sede Principal'),
        ('branch', 'Sucursal'),
    ]
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default='physical')

    # Componentes estructurados de dirección
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    line3 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.ForeignKey(Country, on_delete=models.PROTECT)

    # Geocodificación
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

    # Validación
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_source = models.CharField(max_length=100, blank=True)

    # Validez temporal
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
        """Retorna cadena de dirección formateada."""
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

## Cálculos de Distancia

```python
from math import radians, cos, sin, asin, sqrt
from decimal import Decimal


def haversine_distance(coord1, coord2):
    """
    Calcula la distancia del gran círculo entre dos puntos
    en la tierra (especificados en grados decimales).
    Retorna distancia en kilómetros.
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # Convertir a radianes
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Fórmula de Haversine
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # Radio de la Tierra en kilómetros
    r = 6371

    return c * r


class AddressQuerySet(models.QuerySet):
    """QuerySet con consultas geográficas."""

    def within_radius(self, center_lat, center_lon, radius_km):
        """
        Encuentra direcciones dentro del radio de un punto.
        Nota: Para producción, use PostGIS para consultas espaciales eficientes.
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
        """Direcciones en una región específica."""
        return self.filter(region=region)

    def in_country(self, country_code):
        """Direcciones en un país específico."""
        return self.filter(country__code=country_code)

    def needs_geocoding(self):
        """Direcciones que necesitan geocodificación."""
        return self.filter(latitude__isnull=True)

    def needs_verification(self):
        """Direcciones que no han sido verificadas."""
        return self.filter(is_verified=False)
```

## Áreas de Servicio

Define límites geográficos para disponibilidad de servicios:

```python
class ServiceArea(SoftDeleteModel):
    """Un área geográfica donde el servicio está disponible."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Definir por regiones
    countries = models.ManyToManyField(Country, blank=True)
    regions = models.ManyToManyField(Region, blank=True)

    # O definir por patrones de código postal
    postal_code_patterns = models.JSONField(default=list)  # ["902*", "903*", "904*"]

    # O definir por radio desde un punto
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
        """Verifica si una dirección está dentro de esta área de servicio."""
        # Verificar país
        if self.countries.exists():
            if address.country not in self.countries.all():
                return False

        # Verificar región
        if self.regions.exists():
            if address.region not in self.regions.all():
                return False

        # Verificar patrones de código postal
        if self.postal_code_patterns:
            import fnmatch
            matches = any(
                fnmatch.fnmatch(address.postal_code, pattern)
                for pattern in self.postal_code_patterns
            )
            if not matches:
                return False

        # Verificar radio
        if self.center_latitude and address.is_geocoded:
            distance = haversine_distance(
                (float(self.center_latitude), float(self.center_longitude)),
                address.coordinates
            )
            if distance > float(self.radius_km):
                return False

        return True
```

## Jurisdicción Fiscal

La ubicación determina la tributación:

```python
class TaxJurisdiction(models.Model):
    """Reglas fiscales para un área geográfica."""

    name = models.CharField(max_length=255)
    jurisdiction_type = models.CharField(max_length=50)  # federal, estatal, condado, ciudad

    # Alcance geográfico
    country = models.ForeignKey(Country, on_delete=models.PROTECT)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True)
    postal_codes = models.JSONField(default=list)  # Códigos postales específicos

    # Tasas de impuestos
    sales_tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    use_tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    # Validez
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['country', 'region', 'name']

    @classmethod
    def for_address(cls, address, as_of_date=None):
        """Encuentra jurisdicciones fiscales aplicables para una dirección."""
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

        # Filtrar por región
        jurisdictions = jurisdictions.filter(
            models.Q(region__isnull=True) |
            models.Q(region=address.region)
        )

        # Filtrar por código postal
        matching = []
        for j in jurisdictions:
            if not j.postal_codes or address.postal_code in j.postal_codes:
                matching.append(j)

        return matching
```

## Integración de Geocodificación

```python
from django.utils import timezone
import requests


class GeocodingService:
    """Servicio para geocodificar direcciones."""

    def __init__(self, api_key=None):
        self.api_key = api_key

    def geocode(self, address):
        """
        Geocodifica una dirección y actualiza sus coordenadas.
        Retorna True si tiene éxito.
        """
        # Construir cadena de consulta
        query = f"{address.line1}, {address.city}"
        if address.region:
            query += f", {address.region.code}"
        query += f", {address.postal_code}, {address.country.code}"

        # Llamar API de geocodificación (ejemplo usando Nominatim)
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
        """Obtiene dirección desde coordenadas."""
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

## Por Qué Esto Importa Después

La primitiva de Geografía se conecta con:

- **Identidad** (Capítulo 6): Las partes tienen direcciones.
- **Acuerdos** (Capítulo 8): Las áreas de servicio definen dónde aplican los acuerdos.
- **Libro Mayor** (Capítulo 10): Las jurisdicciones fiscales afectan los montos de las transacciones.
- **Catálogo** (Capítulo 9): La disponibilidad de productos varía por ubicación.
- **Registro de Trabajo** (Capítulo 14): Las llamadas de servicio tienen ubicaciones.

La ubicación parece simple hasta que necesitas:
- Calcular costos de envío a través de fronteras
- Aplicar el impuesto de ventas correcto para un pedido multi-jurisdiccional
- Determinar si una solicitud de servicio está dentro de tu área de cobertura
- Cumplir con requisitos de residencia de datos

La primitiva de Geografía maneja la complejidad para que tu aplicación no tenga que reinventarla.

---

## Cómo Reconstruir Esta Primitiva

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-geo | `docs/prompts/django-geo.md` | ~40 tests |

### Usando el Prompt

```bash
cat docs/prompts/django-geo.md | claude

# Solicitud: "Implementar modelos Country y Region con códigos ISO,
# luego Address con campos opcionales de geocodificación.
# Agregar ServiceArea con múltiples tipos de límites."
```

### Restricciones Clave

- **Códigos ISO-3166**: Country usa 2 letras, Region usa códigos de subdivisión
- **Coordenadas decimales**: Latitud/longitud como DecimalField (9,6), nunca Float
- **Distancia Haversine**: Cálculo matemático puro, no requiere dependencias externas
- **Geocodificación opcional**: Las coordenadas son anulables, la geocodificación es asíncrona

Si Claude usa FloatField para coordenadas o codifica datos de países de manera fija, eso es una violación de restricción.

---

*Estado: Borrador*
