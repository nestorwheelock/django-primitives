"""Models for invoicing module.

Provides Invoice and InvoiceLineItem for the basket-to-invoice flow.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from django_money import Money


class Invoice(models.Model):
    """Invoice generated from a priced basket.

    Represents a financial document with line items, linked to:
    - The source basket (for audit trail)
    - The encounter (for context)
    - The patient/party (who is billed)
    - The organization (who is billing)
    - The ledger transaction (double-entry record)
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("paid", "Paid"),
        ("voided", "Voided"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Source tracking
    basket = models.OneToOneField(
        "django_catalog.Basket",
        on_delete=models.PROTECT,
        related_name="invoice",
        help_text="The committed basket this invoice was generated from",
    )
    encounter = models.ForeignKey(
        "django_encounters.Encounter",
        on_delete=models.PROTECT,
        related_name="invoices",
        help_text="The encounter this invoice relates to",
    )

    # Party context (extracted from encounter)
    billed_to = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.PROTECT,
        related_name="invoices_received",
        help_text="The patient/party being billed",
    )
    issued_by = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="invoices_issued",
        help_text="The organization issuing the invoice",
    )

    # Optional agreement (for price context audit)
    agreement = models.ForeignKey(
        "django_agreements.Agreement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        help_text="Agreement used for pricing (if any)",
    )

    # Invoice metadata
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Human-readable invoice number",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    # Currency (single currency per invoice)
    currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="ISO currency code for all line items",
    )

    # Totals (denormalized for efficiency)
    subtotal_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        help_text="Sum of line item totals before tax",
    )
    tax_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=Decimal("0"),
        help_text="Total tax amount",
    )
    total_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        help_text="Final total (subtotal + tax)",
    )

    # Ledger integration
    ledger_transaction = models.OneToOneField(
        "django_ledger.Transaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoice",
        help_text="The double-entry transaction recording this invoice",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="invoices_created",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal_amount__gte=0),
                name="invoice_subtotal_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0),
                name="invoice_total_non_negative",
            ),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.total} ({self.status})"

    @property
    def subtotal(self) -> Money:
        """Return subtotal as Money."""
        return Money(self.subtotal_amount, self.currency)

    @property
    def tax(self) -> Money:
        """Return tax as Money."""
        return Money(self.tax_amount, self.currency)

    @property
    def total(self) -> Money:
        """Return total as Money."""
        return Money(self.total_amount, self.currency)


class InvoiceLineItem(models.Model):
    """Line item on an invoice, linked to a PricedBasketItem.

    Snapshots all billing data at invoice creation time for immutability.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="line_items",
    )

    # Source tracking (for audit trail)
    priced_basket_item = models.OneToOneField(
        "pricing.PricedBasketItem",
        on_delete=models.PROTECT,
        related_name="invoice_line",
        help_text="The priced basket item this line was generated from",
    )

    # Snapshotted data (immutable after creation)
    description = models.CharField(
        max_length=255,
        help_text="Display name at time of invoicing",
    )
    quantity = models.PositiveIntegerField()
    unit_price_amount = models.DecimalField(
        max_digits=10,
        decimal_places=4,
    )
    line_total_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        help_text="quantity * unit_price (calculated at creation)",
    )

    # Optional tax
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0"),
        help_text="Tax rate as decimal (0.08 = 8%)",
    )
    tax_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=Decimal("0"),
    )

    # Price rule audit
    price_scope_type = models.CharField(
        max_length=20,
        help_text="The scope type that determined the price (global/organization/party/agreement)",
    )
    price_rule_id = models.UUIDField(
        help_text="The Price record ID that was applied",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # Quantity must be positive (> 0, not >= 0)
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="invoicelineitem_quantity_positive",
            ),
            # Line total must equal quantity * unit_price (prevents drift)
            models.CheckConstraint(
                condition=Q(line_total_amount=models.F("quantity") * models.F("unit_price_amount")),
                name="invoicelineitem_total_equals_qty_times_price",
            ),
        ]

    def __str__(self):
        return f"{self.description} x{self.quantity} = {self.line_total}"

    @property
    def unit_price(self) -> Money:
        """Return unit price as Money."""
        return Money(self.unit_price_amount, self.invoice.currency)

    @property
    def line_total(self) -> Money:
        """Return line total as Money."""
        return Money(self.line_total_amount, self.invoice.currency)
