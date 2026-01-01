"""GeoPoint value object for geographic coordinates."""
from dataclasses import dataclass
from decimal import Decimal
import math
from typing import Union


# Earth's radius in kilometers
EARTH_RADIUS_KM = Decimal('6371.0')


@dataclass(frozen=True)
class GeoPoint:
    """Immutable geographic coordinate point.

    Represents a latitude/longitude coordinate pair with
    Haversine distance calculation.
    """

    latitude: Decimal
    longitude: Decimal

    def __post_init__(self) -> None:
        """Convert floats to Decimal if needed."""
        # Use object.__setattr__ since dataclass is frozen
        if not isinstance(self.latitude, Decimal):
            object.__setattr__(self, 'latitude', Decimal(str(self.latitude)))
        if not isinstance(self.longitude, Decimal):
            object.__setattr__(self, 'longitude', Decimal(str(self.longitude)))

    def distance_to(self, other: 'GeoPoint') -> Decimal:
        """Calculate Haversine distance to another point in kilometers.

        Uses the Haversine formula to calculate great-circle distance
        between two points on Earth's surface.

        Args:
            other: The target GeoPoint to measure distance to.

        Returns:
            Distance in kilometers as a Decimal.
        """
        # Convert to radians
        lat1 = math.radians(float(self.latitude))
        lon1 = math.radians(float(self.longitude))
        lat2 = math.radians(float(other.latitude))
        lon2 = math.radians(float(other.longitude))

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        # Calculate distance
        distance = float(EARTH_RADIUS_KM) * c

        return Decimal(str(round(distance, 6)))

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"({self.latitude}, {self.longitude})"

    def __repr__(self) -> str:
        """Return debuggable representation."""
        return f"GeoPoint(latitude={self.latitude!r}, longitude={self.longitude!r})"
