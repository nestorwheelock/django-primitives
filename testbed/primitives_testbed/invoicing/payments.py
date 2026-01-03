"""Payment recording for invoicing.

Records payments against invoices via the ledger.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from django_ledger.services import record_transaction

from .exceptions import InvoiceStateError
from .models import Invoice
from .services import get_or_create_account


@transaction.atomic
def record_payment(
    invoice: Invoice,
    amount: Decimal,
    payment_method: str,
    recorded_by,
    *,
    reference: str = "",
) -> Invoice:
    """Record a payment against an invoice.

    Creates a double-entry transaction:
    - Debit: Cash/Bank (asset)
    - Credit: Accounts Receivable (asset reduction)

    Args:
        invoice: The invoice being paid
        amount: Payment amount (must match invoice total for full payment)
        payment_method: How payment was received (cash, card, check, etc.)
        recorded_by: User recording the payment
        reference: Optional payment reference (check number, transaction ID, etc.)

    Returns:
        Updated invoice (status='paid' if fully paid)

    Raises:
        InvoiceStateError: If invoice is not in issued status
        InvoiceStateError: If amount exceeds remaining balance
    """
    if invoice.status not in ("issued",):
        raise InvoiceStateError(
            f"Cannot record payment for invoice in status={invoice.status}, must be 'issued'"
        )

    # Validate amount doesn't exceed total
    if amount > invoice.total_amount:
        raise InvoiceStateError(
            f"Payment amount {amount} exceeds invoice total {invoice.total_amount}"
        )

    # Get accounts
    cash_account = get_or_create_account(
        owner=invoice.issued_by,
        account_type="asset",
        currency=invoice.currency,
        name=f"Cash - {payment_method.title()}",
    )

    receivable_account = get_or_create_account(
        owner=invoice.issued_by,
        account_type="receivable",
        currency=invoice.currency,
        name="Accounts Receivable",
    )

    # Record payment transaction
    record_transaction(
        description=f"Payment for {invoice.invoice_number} via {payment_method}",
        entries=[
            {
                "account": cash_account,
                "amount": amount,
                "entry_type": "debit",
                "description": f"Payment received - {reference}"
                if reference
                else "Payment received",
            },
            {
                "account": receivable_account,
                "amount": amount,
                "entry_type": "credit",
                "description": f"Payment applied to {invoice.invoice_number}",
            },
        ],
        metadata={
            "invoice_id": str(invoice.pk),
            "invoice_number": invoice.invoice_number,
            "payment_method": payment_method,
            "reference": reference,
            "recorded_by": str(recorded_by.pk) if recorded_by else None,
        },
    )

    # If fully paid, update status
    if amount >= invoice.total_amount:
        invoice.status = "paid"
        invoice.paid_at = timezone.now()
        invoice.save()

    return invoice
