"""Custom exceptions for django-agreements."""


class AgreementError(Exception):
    """Base exception for agreement errors."""
    pass


class ImmutableVersionError(AgreementError):
    """Raised when attempting to modify an immutable version record."""

    def __init__(self, version_id):
        self.version_id = version_id
        super().__init__(
            f"Cannot modify version {version_id} - version records are immutable. "
            "Create an amendment instead."
        )
