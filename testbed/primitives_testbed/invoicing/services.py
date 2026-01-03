"""Invoice creation and management services.

Main entry points for the basket-to-invoice flow.
"""

from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from django_ledger.models import Account
from django_ledger.services import record_transaction
from django_money import Money
from django_sequence.services import next_sequence

from .context import InvoiceContext, extract_invoice_context
from .exceptions import InvoiceStateError, LedgerIntegrationError
from .models import Invoice, InvoiceLineItem
from .pricing import price_basket


def generate_invoice_number(organization) -> str:
    """Generate a unique invoice number atomically.

    Uses django-sequence with select_for_update() to prevent race conditions
    when multiple requests try to generate invoice numbers simultaneously.

    Format: INV-YYYY-NNNN where NNNN is sequential per organization per year.

    Args:
        organization: The organization issuing the invoice (for scoping)

    Returns:
        Unique invoice number like "INV-2026-0001"
    """
    return next_sequence(
        scope='invoice',
        org=organization,
        prefix='INV-',
        pad_width=4,
        include_year=True,
    )


@transaction.atomic
def create_invoice_from_basket(
    basket,
    created_by,
    *,
    tax_rate: Decimal = Decimal("0"),
    notes: str = "",
    issue_immediately: bool = True,
) -> Invoice:
    """Create an invoice from a committed basket.

    This is the main entry point for the basket-to-invoice flow.

    Args:
        basket: A committed basket
        created_by: User creating the invoice
        tax_rate: Optional tax rate as decimal (0.08 = 8%)
        notes: Optional invoice notes
        issue_immediately: If True, also record ledger entry and set status to 'issued'

    Returns:
        Created Invoice with line items

    Raises:
        BasketNotCommittedError: If basket is not committed
        ContextExtractionError: If context extraction fails
        PricingError: If some items cannot be priced
    """
    # 1. Extract context from basket
    context = extract_invoice_context(basket)

    # 2. Price the basket
    priced_basket = price_basket(
        basket,
        organization=context.organization,
        party=context.patient,
        agreement=context.agreement,
    )

    # 3. Calculate totals
    subtotal = priced_basket.subtotal.quantized()
    tax_amount = (subtotal * tax_rate).quantized()
    total = (subtotal + tax_amount).quantized()

    # 4. Create invoice
    invoice = Invoice.objects.create(
        basket=basket,
        encounter=context.encounter,
        billed_to=context.patient,
        issued_by=context.organization,
        agreement=context.agreement,
        invoice_number=generate_invoice_number(context.organization),
        status="draft",
        currency=priced_basket.currency,
        subtotal_amount=subtotal.amount,
        tax_amount=tax_amount.amount,
        total_amount=total.amount,
        created_by=created_by,
        notes=notes,
    )

    # 5. Create line items
    for line in priced_basket.lines:
        line_tax = (line.line_total * tax_rate).quantized()

        InvoiceLineItem.objects.create(
            invoice=invoice,
            priced_basket_item=line.priced_item,
            description=line.basket_item.catalog_item.display_name,
            quantity=line.quantity,
            unit_price_amount=line.unit_price.amount,
            line_total_amount=line.line_total.amount,
            tax_rate=tax_rate,
            tax_amount=line_tax.amount,
            price_scope_type=line.scope_type,
            price_rule_id=line.price_id,
        )

    # 6. Optionally issue (record ledger entry)
    if issue_immediately:
        invoice = issue_invoice(invoice, issued_by=created_by)

    return invoice


@transaction.atomic
def issue_invoice(invoice: Invoice, issued_by) -> Invoice:
    """Issue a draft invoice, recording the ledger entry.

    Creates a double-entry transaction:
    - Debit: Accounts Receivable (asset)
    - Credit: Revenue (income)

    Args:
        invoice: A draft invoice
        issued_by: User issuing the invoice

    Returns:
        Updated invoice with status='issued' and ledger_transaction set

    Raises:
        InvoiceStateError: If invoice is not in draft status
        LedgerIntegrationError: If ledger transaction fails
    """
    if invoice.status != "draft":
        raise InvoiceStateError(
            f"Cannot issue invoice in status={invoice.status}, must be 'draft'"
        )

    # Get or create accounts for the organization
    receivable_account = get_or_create_account(
        owner=invoice.issued_by,
        account_type="receivable",
        currency=invoice.currency,
        name="Accounts Receivable",
    )

    revenue_account = get_or_create_account(
        owner=invoice.issued_by,
        account_type="revenue",
        currency=invoice.currency,
        name="Service Revenue",
    )

    try:
        # Record the double-entry transaction
        transaction_obj = record_transaction(
            description=f"Invoice {invoice.invoice_number} - {invoice.billed_to.first_name} {invoice.billed_to.last_name}",
            entries=[
                {
                    "account": receivable_account,
                    "amount": invoice.total_amount,
                    "entry_type": "debit",
                    "description": f"Invoice {invoice.invoice_number}",
                },
                {
                    "account": revenue_account,
                    "amount": invoice.total_amount,
                    "entry_type": "credit",
                    "description": f"Revenue from {invoice.invoice_number}",
                },
            ],
            metadata={
                "invoice_id": str(invoice.pk),
                "invoice_number": invoice.invoice_number,
                "patient_id": str(invoice.billed_to.pk),
                "encounter_id": str(invoice.encounter.pk),
            },
        )
    except Exception as e:
        raise LedgerIntegrationError(f"Failed to record ledger transaction: {e}") from e

    # Update invoice
    invoice.ledger_transaction = transaction_obj
    invoice.status = "issued"
    invoice.issued_at = timezone.now()
    invoice.save()

    return invoice


def get_or_create_account(
    owner, account_type: str, currency: str, name: str
) -> Account:
    """Get or create a ledger account for an organization.

    Args:
        owner: The organization that owns the account
        account_type: Type of account (receivable, revenue, etc.)
        currency: ISO currency code
        name: Human-readable account name

    Returns:
        Account instance
    """
    owner_ct = ContentType.objects.get_for_model(owner)

    account, _ = Account.objects.get_or_create(
        owner_content_type=owner_ct,
        owner_id=str(owner.pk),
        account_type=account_type,
        currency=currency,
        defaults={"name": name},
    )

    return account
