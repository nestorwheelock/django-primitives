"""Agreement service layer.

All write operations go through these functions.
Direct model manipulation bypasses invariants and is unsupported.

Functions:
- create_agreement(): Create agreement with initial version
- amend_agreement(): Amend terms, create new version
- terminate_agreement(): End agreement by setting valid_to
- get_terms_as_of(): Get terms effective at a timestamp
"""

from django.db import transaction
from django.utils import timezone

from .models import Agreement, AgreementVersion


class AgreementError(Exception):
    """Base exception for agreement operations."""
    pass


class InvalidTerminationError(AgreementError):
    """Raised when termination would violate constraints."""
    pass


def create_agreement(
    party_a,
    party_b,
    scope_type: str,
    terms: dict,
    agreed_by,
    valid_from,
    agreed_at=None,
    valid_to=None,
    scope_ref=None,
) -> Agreement:
    """
    Create an agreement with initial version.

    Args:
        party_a: First party to the agreement (any model instance)
        party_b: Second party to the agreement (any model instance)
        scope_type: Type of agreement (e.g., 'service_contract', 'consent')
        terms: Agreement terms as dict
        agreed_by: User who made the agreement
        valid_from: When the agreement becomes effective (REQUIRED)
        agreed_at: When the agreement was made (defaults to now)
        valid_to: When the agreement expires (None = indefinite)
        scope_ref: Optional reference to what the agreement is about

    Returns:
        The created Agreement instance

    Raises:
        ValueError: If valid_to <= valid_from
    """
    agreed_at = agreed_at or timezone.now()

    # Validate dates before hitting DB constraint
    if valid_to is not None and valid_to <= valid_from:
        raise ValueError("valid_to must be after valid_from")

    with transaction.atomic():
        agreement = Agreement(
            party_a=party_a,
            party_b=party_b,
            scope_type=scope_type,
            terms=terms,
            agreed_at=agreed_at,
            agreed_by=agreed_by,
            valid_from=valid_from,
            valid_to=valid_to,
            current_version=1,
        )
        if scope_ref is not None:
            agreement.scope_ref = scope_ref
        agreement.save()

        AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms=terms,
            created_by=agreed_by,
            reason="Initial agreement",
        )

        return agreement


def amend_agreement(
    agreement: Agreement,
    new_terms: dict,
    reason: str,
    amended_by,
) -> Agreement:
    """
    Amend an agreement, creating a new version.

    This updates Agreement.terms (the projection) and creates an
    immutable AgreementVersion record (the ledger).

    Args:
        agreement: The agreement to amend
        new_terms: The new terms
        reason: Why the amendment was made
        amended_by: User making the amendment

    Returns:
        The updated Agreement instance
    """
    with transaction.atomic():
        # Lock the row to prevent concurrent amendments
        agreement = Agreement.objects.select_for_update().get(pk=agreement.pk)

        new_version = agreement.current_version + 1

        # Create immutable version record (ledger)
        AgreementVersion.objects.create(
            agreement=agreement,
            version=new_version,
            terms=new_terms,
            created_by=amended_by,
            reason=reason,
        )

        # Update projection
        agreement.terms = new_terms
        agreement.current_version = new_version
        agreement.save()

        return agreement


def terminate_agreement(
    agreement: Agreement,
    terminated_by,
    valid_to=None,
    reason: str = "Terminated",
) -> Agreement:
    """
    Terminate an agreement by setting valid_to.

    Creates a version record even though terms don't change,
    because termination is a legal fact worth recording.

    Args:
        agreement: The agreement to terminate
        terminated_by: User terminating the agreement
        valid_to: When the agreement ends (defaults to now)
        reason: Why the agreement was terminated

    Returns:
        The updated Agreement instance

    Raises:
        InvalidTerminationError: If valid_to <= valid_from
    """
    valid_to = valid_to or timezone.now()

    with transaction.atomic():
        # Lock the row
        agreement = Agreement.objects.select_for_update().get(pk=agreement.pk)

        # Validate before hitting DB constraint
        if valid_to <= agreement.valid_from:
            raise InvalidTerminationError(
                f"Cannot terminate agreement: valid_to ({valid_to}) must be after "
                f"valid_from ({agreement.valid_from})"
            )

        new_version = agreement.current_version + 1

        # Record termination as a version (terms unchanged, but fact recorded)
        AgreementVersion.objects.create(
            agreement=agreement,
            version=new_version,
            terms=agreement.terms,
            created_by=terminated_by,
            reason=reason,
        )

        agreement.valid_to = valid_to
        agreement.current_version = new_version
        agreement.save()

        return agreement


def get_terms_as_of(agreement: Agreement, timestamp) -> dict | None:
    """
    Get the terms that were recorded by a given timestamp.

    Note: This returns terms by created_at (when recorded), not by
    effective_at (when they became true). If you need true temporal
    term applicability, add effective_at to AgreementVersion.

    Args:
        agreement: The agreement to query
        timestamp: The point in time to query

    Returns:
        The terms dict, or None if no version existed by that timestamp
    """
    version = agreement.versions.filter(
        created_at__lte=timestamp
    ).order_by('-version').first()

    return version.terms if version else None
