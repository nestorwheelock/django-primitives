"""Clinic-specific exceptions."""


class ClinicError(Exception):
    """Base exception for clinic errors."""

    pass


class ConsentRequiredError(ClinicError):
    """Raised when patient has not signed required consent forms."""

    def __init__(self, missing_consents: list[str]):
        self.missing_consents = missing_consents
        consent_names = ", ".join(missing_consents)
        super().__init__(f"Missing required consents: {consent_names}")
