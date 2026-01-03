"""Context extraction for invoicing.

Extracts billing context (patient, organization, agreement) from a basket's encounter.
"""

from dataclasses import dataclass
from typing import Optional

from django_agreements.models import Agreement
from django_catalog.models import Basket
from django_encounters.models import Encounter
from django_parties.models import Organization, Person

from .exceptions import BasketNotCommittedError, ContextExtractionError


@dataclass(frozen=True)
class InvoiceContext:
    """Extracted context for invoice creation.

    Immutable value object containing all parties involved in the invoice.
    """

    patient: Person
    organization: Organization
    encounter: Encounter
    basket: Basket
    agreement: Optional[Agreement] = None


def extract_invoice_context(basket: Basket) -> InvoiceContext:
    """Extract billing context from a basket's encounter.

    Args:
        basket: A committed basket with an encounter

    Returns:
        InvoiceContext with all parties extracted

    Raises:
        BasketNotCommittedError: If basket is not committed
        ContextExtractionError: If encounter subject is not a Person
        ContextExtractionError: If clinic organization not found
    """
    from primitives_testbed.clinic.services import (
        get_clinic_organization,
        get_patient_from_encounter,
    )

    if basket.status != "committed":
        raise BasketNotCommittedError(
            f"Basket must be committed before invoicing, got status={basket.status}"
        )

    encounter = basket.encounter

    patient = get_patient_from_encounter(encounter)
    if not patient:
        raise ContextExtractionError(
            f"Encounter subject must be a Person, got {encounter.subject_type}"
        )

    organization = get_clinic_organization()
    if not organization:
        raise ContextExtractionError("Clinic organization not found")

    # Optionally find applicable agreement for this patient/org pair
    agreement = _find_billing_agreement(patient, organization)

    return InvoiceContext(
        patient=patient,
        organization=organization,
        encounter=encounter,
        basket=basket,
        agreement=agreement,
    )


def _find_billing_agreement(
    patient: Person,
    organization: Organization,
) -> Optional[Agreement]:
    """Find an active billing agreement between patient and organization."""
    return (
        Agreement.objects.for_party(patient)
        .current()
        .filter(scope_type__in=["contract", "billing", "insurance"])
        .first()
    )
