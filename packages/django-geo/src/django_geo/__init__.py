"""Django Geo - Geographic primitives for Django applications."""

__version__ = '0.1.0'


def __getattr__(name):
    """Lazy import to avoid AppRegistryNotReady errors."""
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


__all__ = ['GeoPoint', 'Place', 'ServiceArea']
