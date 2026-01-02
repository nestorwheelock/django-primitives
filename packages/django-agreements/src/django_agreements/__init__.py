"""Django Agreements - Temporal agreement primitives.

Models:
    Agreement: Contract between two parties with effective dating
    AgreementVersion: Immutable amendment history

Services (the only supported write path):
    create_agreement: Create agreement with initial version
    amend_agreement: Amend terms, create new version
    terminate_agreement: End agreement by setting valid_to
    get_terms_as_of: Get terms recorded by a timestamp
"""

__version__ = "0.2.0"

__all__ = [
    # Models
    "Agreement",
    "AgreementVersion",
    # Services
    "create_agreement",
    "amend_agreement",
    "terminate_agreement",
    "get_terms_as_of",
    # Exceptions
    "AgreementError",
    "InvalidTerminationError",
]


def __getattr__(name):
    """Lazy import to avoid AppRegistryNotReady errors."""
    if name in ("Agreement", "AgreementVersion"):
        from .models import Agreement, AgreementVersion
        if name == "Agreement":
            return Agreement
        return AgreementVersion

    if name in ("create_agreement", "amend_agreement", "terminate_agreement", "get_terms_as_of"):
        from . import services
        return getattr(services, name)

    if name in ("AgreementError", "InvalidTerminationError"):
        from .services import AgreementError, InvalidTerminationError
        if name == "AgreementError":
            return AgreementError
        return InvalidTerminationError

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
