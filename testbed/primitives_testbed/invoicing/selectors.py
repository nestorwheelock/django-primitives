"""Invoice selectors for read-only queries.

Provides optimized query functions for invoice printing and display.
Uses select_related/prefetch_related to avoid N+1 queries.
"""

from typing import NamedTuple, Optional
from uuid import UUID

from django.db.models import Prefetch

from .exceptions import InvoiceAccessDeniedError, InvoiceNotPrintableError
from .models import Invoice, InvoiceLineItem


PRINTABLE_STATUSES = frozenset({"issued", "paid", "voided"})


class InvoicePrintData(NamedTuple):
    """Data structure for invoice printing."""

    invoice: Invoice
    billed_to_address: Optional[str]
    issued_by_address: Optional[str]


def get_invoice_for_print(
    invoice_id: UUID,
    user,
    *,
    check_org_access: bool = True,
) -> InvoicePrintData:
    """Fetch an invoice with all data needed for printing.

    Uses select_related and prefetch_related to avoid N+1 queries.

    Args:
        invoice_id: UUID of the invoice
        user: The requesting user (for access control)
        check_org_access: Whether to verify user has org access

    Returns:
        InvoicePrintData with invoice and formatted addresses

    Raises:
        Invoice.DoesNotExist: If invoice not found
        InvoiceNotPrintableError: If invoice status is draft
        InvoiceAccessDeniedError: If user lacks access to invoice org
    """
    # Single query with all related data
    invoice = (
        Invoice.objects.select_related(
            "billed_to",
            "issued_by",
            "encounter",
            "agreement",
        )
        .prefetch_related(
            Prefetch(
                "line_items", queryset=InvoiceLineItem.objects.order_by("created_at")
            ),
            "billed_to__addresses",
            "issued_by__addresses",
        )
        .get(pk=invoice_id)
    )

    # Status check
    if invoice.status not in PRINTABLE_STATUSES:
        raise InvoiceNotPrintableError(
            f"Cannot print invoice in status '{invoice.status}'. "
            f"Only {sorted(PRINTABLE_STATUSES)} invoices can be printed."
        )

    # Access control
    if check_org_access:
        if not _user_has_org_access(user, invoice.issued_by):
            raise InvoiceAccessDeniedError(
                f"User does not have access to organization {invoice.issued_by.pk}"
            )

    # Format addresses
    billed_to_address = _get_primary_address_formatted(invoice.billed_to)
    issued_by_address = _get_primary_address_formatted(invoice.issued_by)

    return InvoicePrintData(
        invoice=invoice,
        billed_to_address=billed_to_address,
        issued_by_address=issued_by_address,
    )


def _user_has_org_access(user, organization) -> bool:
    """Check if user has access to the organization.

    Simple implementation:
    - Superusers can access all orgs
    - Otherwise, always allow (can be enhanced with RBAC)
    """
    if user.is_superuser:
        return True

    # For now, allow authenticated users
    # This can be enhanced with PartyRelationship checks or RBAC
    return user.is_authenticated


def _get_primary_address_formatted(party) -> Optional[str]:
    """Get formatted primary address for a party.

    Uses prefetched addresses to avoid additional queries.
    """
    if not hasattr(party, "addresses"):
        return None

    addresses = list(party.addresses.all())
    if not addresses:
        return None

    # Find primary or use first
    primary = next((a for a in addresses if getattr(a, "is_primary", False)), None)
    if primary is None:
        primary = addresses[0]

    # Format address
    parts = []
    if getattr(primary, "address_line1", None):
        parts.append(primary.address_line1)
    if getattr(primary, "address_line2", None):
        parts.append(primary.address_line2)

    city_state_zip = []
    if getattr(primary, "city", None):
        city_state_zip.append(primary.city)
    if getattr(primary, "state", None):
        city_state_zip.append(primary.state)
    if getattr(primary, "postal_code", None):
        city_state_zip.append(primary.postal_code)

    if city_state_zip:
        parts.append(", ".join(city_state_zip))

    if getattr(primary, "country", None):
        parts.append(primary.country)

    return "\n".join(parts) if parts else None
