"""Read-optimized selectors for terminal UI.

These selectors provide efficient queries with proper prefetching
to prevent N+1 query issues.
"""

from typing import Any
from uuid import UUID


def list_parties(limit: int = 50, party_type: str | None = None) -> list:
    """List parties (Person and/or Organization).

    Args:
        limit: Maximum number of records to return
        party_type: Filter by type ('person' or 'org'), None for both

    Returns:
        List of Person and/or Organization objects
    """
    from django_parties.models import Organization, Person

    parties = []

    if party_type is None or party_type == "person":
        persons = Person.objects.order_by("-created_at")[:limit]
        parties.extend(list(persons))

    if party_type is None or party_type == "org":
        orgs = Organization.objects.order_by("-created_at")[:limit]
        parties.extend(list(orgs))

    return parties[:limit]


def list_encounters(limit: int = 50, state: str | None = None) -> list:
    """List encounters with related data.

    Args:
        limit: Maximum number of records to return
        state: Filter by state

    Returns:
        List of Encounter objects
    """
    from django_encounters.models import Encounter

    qs = Encounter.objects.select_related(
        "definition", "subject_type"
    ).order_by("-created_at")

    if state:
        qs = qs.filter(state=state)

    return list(qs[:limit])


def list_baskets(limit: int = 50, status: str | None = None) -> list:
    """List baskets with item counts.

    Args:
        limit: Maximum number of records to return
        status: Filter by status

    Returns:
        List of Basket objects
    """
    from django_catalog.models import Basket

    qs = Basket.objects.select_related("created_by").prefetch_related("items")

    if status:
        qs = qs.filter(status=status)

    return list(qs.order_by("-created_at")[:limit])


def list_invoices(limit: int = 50, status: str | None = None) -> list:
    """List invoices with party info.

    Args:
        limit: Maximum number of records to return
        status: Filter by status

    Returns:
        List of Invoice objects
    """
    from primitives_testbed.invoicing.models import Invoice

    qs = Invoice.objects.select_related(
        "billed_to", "issued_by", "basket", "encounter"
    ).order_by("-created_at")

    if status:
        qs = qs.filter(status=status)

    return list(qs[:limit])


def list_ledger_transactions(limit: int = 50) -> list:
    """List ledger transactions with entries.

    Args:
        limit: Maximum number of records to return

    Returns:
        List of Transaction objects
    """
    from django_ledger.models import Transaction

    return list(
        Transaction.objects.prefetch_related("entries", "entries__account")
        .order_by("-posted_at")[:limit]
    )


def list_agreements(limit: int = 50, scope_type: str | None = None) -> list:
    """List agreements with party info.

    Args:
        limit: Maximum number of records to return
        scope_type: Filter by scope_type

    Returns:
        List of Agreement objects
    """
    from django_agreements.models import Agreement

    qs = Agreement.objects.select_related(
        "party_a_content_type", "party_b_content_type"
    ).order_by("-created_at")

    if scope_type:
        qs = qs.filter(scope_type=scope_type)

    return list(qs[:limit])


def get_party(party_id: UUID) -> Any | None:
    """Get a party (Person or Organization) by ID.

    Args:
        party_id: UUID of the party

    Returns:
        Person or Organization object, or None if not found
    """
    from django_parties.models import Organization, Person

    try:
        return Person.objects.get(pk=party_id)
    except Person.DoesNotExist:
        pass

    try:
        return Organization.objects.get(pk=party_id)
    except Organization.DoesNotExist:
        pass

    return None


def get_encounter(encounter_id: UUID) -> Any | None:
    """Get an encounter by ID with related data.

    Args:
        encounter_id: UUID of the encounter

    Returns:
        Encounter object or None if not found
    """
    from django_encounters.models import Encounter

    try:
        return Encounter.objects.select_related(
            "definition", "subject_type"
        ).get(pk=encounter_id)
    except Encounter.DoesNotExist:
        return None


def get_basket(basket_id: UUID) -> Any | None:
    """Get a basket by ID with related data.

    Args:
        basket_id: UUID of the basket

    Returns:
        Basket object or None if not found
    """
    from django_catalog.models import Basket

    try:
        return Basket.objects.select_related(
            "created_by"
        ).prefetch_related("items").get(pk=basket_id)
    except Basket.DoesNotExist:
        return None


def get_invoice(invoice_id: UUID) -> Any | None:
    """Get an invoice by ID with related data.

    Args:
        invoice_id: UUID of the invoice

    Returns:
        Invoice object or None if not found
    """
    from primitives_testbed.invoicing.models import Invoice

    try:
        return Invoice.objects.select_related(
            "billed_to", "issued_by", "basket", "encounter"
        ).prefetch_related("line_items").get(pk=invoice_id)
    except Invoice.DoesNotExist:
        return None


def get_agreement(agreement_id: UUID) -> Any | None:
    """Get an agreement by ID with related data.

    Args:
        agreement_id: UUID of the agreement

    Returns:
        Agreement object or None if not found
    """
    from django_agreements.models import Agreement

    try:
        return Agreement.objects.select_related(
            "party_a_content_type", "party_b_content_type"
        ).get(pk=agreement_id)
    except Agreement.DoesNotExist:
        return None
