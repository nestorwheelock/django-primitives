"""Django Audit Log - Generic audit logging for Django applications."""

__version__ = "0.1.0"


def log(*args, **kwargs):
    """Log an audit event for a model operation."""
    from .api import log as _log
    return _log(*args, **kwargs)


def log_event(*args, **kwargs):
    """Log a non-model event (login, permission denied, etc.)."""
    from .api import log_event as _log_event
    return _log_event(*args, **kwargs)


__all__ = ["log", "log_event"]
