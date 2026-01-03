"""Tests for invoicing module.

Tests the basket-to-invoice flow including:
- Context extraction from encounter
- Basket pricing
- Invoice creation with line items
- Ledger integration (double-entry transactions)
- Payment recording
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_agreements.models import Agreement
from django_catalog.models import Basket, BasketItem, CatalogItem
from django_encounters.models import Encounter, EncounterDefinition
from django_ledger.models import Account, Entry, Transaction
from django_ledger.services import get_balance
from django_parties.models import Organization, Person

from primitives_testbed.invoicing.context import (
    InvoiceContext,
    extract_invoice_context,
)
from primitives_testbed.invoicing.exceptions import (
    BasketNotCommittedError,
    ContextExtractionError,
    InvoiceStateError,
)
from primitives_testbed.invoicing.models import Invoice, InvoiceLineItem
from primitives_testbed.invoicing.payments import record_payment
from primitives_testbed.invoicing.pricing import PricedBasket, price_basket
from primitives_testbed.invoicing.services import (
    create_invoice_from_basket,
    issue_invoice,
)
from primitives_testbed.pricing.models import Price

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def clinic(db):
    """Create the Springfield Family Clinic organization."""
    return Organization.objects.create(name="Springfield Family Clinic")


@pytest.fixture
def patient(db):
    """Create a test patient."""
    return Person.objects.create(
        first_name="James",
        last_name="Wilson",
        date_of_birth="1980-05-15",
    )


@pytest.fixture
def encounter_definition(db):
    """Create an encounter definition."""
    return EncounterDefinition.objects.create(
        key="clinic_visit",
        name="Clinic Visit",
        initial_state="scheduled",
        states=["scheduled", "confirmed", "checked_in", "vitals", "provider", "checkout", "completed", "cancelled"],
        terminal_states=["completed", "cancelled"],
        transitions={
            "scheduled": ["confirmed", "cancelled"],
            "confirmed": ["checked_in", "cancelled"],
            "checked_in": ["vitals", "cancelled"],
            "vitals": ["provider", "cancelled"],
            "provider": ["checkout", "cancelled"],
            "checkout": ["completed", "cancelled"],
        },
    )


@pytest.fixture
def encounter(db, patient, encounter_definition, user):
    """Create an encounter for the patient."""
    person_ct = ContentType.objects.get_for_model(Person)
    return Encounter.objects.create(
        definition=encounter_definition,
        subject_type=person_ct,
        subject_id=str(patient.pk),
        state="checked_in",
        created_by=user,
    )


@pytest.fixture
def catalog_items(db):
    """Create catalog items for testing."""
    aspirin = CatalogItem.objects.create(
        display_name="Aspirin 100mg",
        kind="stock_item",
        default_stock_action="dispense",
        is_billable=True,
        active=True,
    )
    exam = CatalogItem.objects.create(
        display_name="General Examination",
        kind="service",
        service_category="consult",
        is_billable=True,
        active=True,
    )
    return {"aspirin": aspirin, "exam": exam}


@pytest.fixture
def prices(db, catalog_items, user):
    """Create prices for catalog items."""
    now = timezone.now()
    aspirin_price = Price.objects.create(
        catalog_item=catalog_items["aspirin"],
        amount=Decimal("12.50"),
        currency="USD",
        priority=50,
        valid_from=now,
        created_by=user,
        reason="Standard retail price",
    )
    exam_price = Price.objects.create(
        catalog_item=catalog_items["exam"],
        amount=Decimal("75.00"),
        currency="USD",
        priority=50,
        valid_from=now,
        created_by=user,
        reason="Standard consultation fee",
    )
    return {"aspirin": aspirin_price, "exam": exam_price}


@pytest.fixture
def committed_basket(db, encounter, catalog_items, user):
    """Create a committed basket with items."""
    basket = Basket.objects.create(
        encounter=encounter,
        status="committed",
        created_by=user,
    )
    BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_items["aspirin"],
        quantity=2,
        added_by=user,
    )
    BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_items["exam"],
        quantity=1,
        added_by=user,
    )
    return basket


@pytest.fixture
def draft_basket(db, encounter, catalog_items, user):
    """Create a draft basket with items."""
    # Create a new encounter to avoid the unique constraint on committed basket
    person_ct = ContentType.objects.get_for_model(Person)
    new_encounter = Encounter.objects.create(
        definition=encounter.definition,
        subject_type=person_ct,
        subject_id=encounter.subject_id,
        state="scheduled",
        created_by=user,
    )
    basket = Basket.objects.create(
        encounter=new_encounter,
        status="draft",
        created_by=user,
    )
    BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_items["aspirin"],
        quantity=1,
        added_by=user,
    )
    return basket


# =============================================================================
# Context Extraction Tests
# =============================================================================


@pytest.mark.django_db
class TestContextExtraction:
    """Tests for extract_invoice_context()."""

    def test_extracts_patient_from_encounter(self, committed_basket, patient, clinic):
        """Context extraction gets patient from encounter subject."""
        context = extract_invoice_context(committed_basket)

        assert context.patient == patient
        assert isinstance(context, InvoiceContext)

    def test_extracts_organization(self, committed_basket, clinic):
        """Context extraction gets clinic organization."""
        context = extract_invoice_context(committed_basket)

        assert context.organization == clinic

    def test_raises_on_uncommitted_basket(self, draft_basket):
        """Cannot extract context from uncommitted basket."""
        with pytest.raises(BasketNotCommittedError) as exc_info:
            extract_invoice_context(draft_basket)

        assert "must be committed" in str(exc_info.value)

    def test_includes_encounter_and_basket(self, committed_basket, clinic):
        """Context includes the encounter and basket."""
        context = extract_invoice_context(committed_basket)

        assert context.encounter == committed_basket.encounter
        assert context.basket == committed_basket


# =============================================================================
# Basket Pricing Tests
# =============================================================================


@pytest.mark.django_db
class TestBasketPricing:
    """Tests for price_basket()."""

    def test_prices_all_items(self, committed_basket, prices, clinic, patient):
        """All basket items are priced."""
        priced = price_basket(
            committed_basket,
            organization=clinic,
            party=patient,
        )

        assert isinstance(priced, PricedBasket)
        assert len(priced.lines) == 2

    def test_calculates_line_totals(self, committed_basket, prices, clinic, patient):
        """Line totals are unit_price * quantity."""
        priced = price_basket(
            committed_basket,
            organization=clinic,
            party=patient,
        )

        # Aspirin: $12.50 * 2 = $25.00
        aspirin_line = next(
            l for l in priced.lines
            if l.basket_item.catalog_item.display_name == "Aspirin 100mg"
        )
        assert aspirin_line.line_total.amount == Decimal("25.00")

        # Exam: $75.00 * 1 = $75.00
        exam_line = next(
            l for l in priced.lines
            if l.basket_item.catalog_item.display_name == "General Examination"
        )
        assert exam_line.line_total.amount == Decimal("75.00")

    def test_calculates_subtotal(self, committed_basket, prices, clinic, patient):
        """Subtotal is sum of all line totals."""
        priced = price_basket(
            committed_basket,
            organization=clinic,
            party=patient,
        )

        # $25.00 + $75.00 = $100.00
        assert priced.subtotal.amount == Decimal("100.00")
        assert priced.currency == "USD"


# =============================================================================
# Invoice Creation Tests
# =============================================================================


@pytest.mark.django_db
class TestInvoiceCreation:
    """Tests for create_invoice_from_basket()."""

    def test_creates_invoice_with_line_items(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Invoice is created with correct line items."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        assert isinstance(invoice, Invoice)
        assert invoice.line_items.count() == 2
        assert invoice.status == "draft"

    def test_applies_tax_rate(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Tax is calculated correctly."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            tax_rate=Decimal("0.08"),  # 8% tax
            issue_immediately=False,
        )

        # Subtotal: $100.00, Tax: $8.00, Total: $108.00
        assert invoice.subtotal_amount == Decimal("100.0000")
        assert invoice.tax_amount == Decimal("8.0000")
        assert invoice.total_amount == Decimal("108.0000")

    def test_snapshots_prices(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Line items snapshot the price at invoice time."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        aspirin_line = invoice.line_items.get(description="Aspirin 100mg")
        assert aspirin_line.unit_price_amount == Decimal("12.5000")
        assert aspirin_line.quantity == 2
        assert aspirin_line.line_total_amount == Decimal("25.0000")
        assert aspirin_line.price_scope_type == "global"

    def test_links_to_basket_and_encounter(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Invoice links to source basket and encounter."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        assert invoice.basket == committed_basket
        assert invoice.encounter == committed_basket.encounter
        assert invoice.billed_to == patient
        assert invoice.issued_by == clinic


# =============================================================================
# Ledger Integration Tests
# =============================================================================


@pytest.mark.django_db
class TestLedgerIntegration:
    """Tests for ledger integration."""

    def test_issue_creates_balanced_transaction(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Issuing creates a balanced ledger transaction."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=True,
        )

        assert invoice.status == "issued"
        assert invoice.ledger_transaction is not None

        # Transaction should have 2 entries (debit + credit)
        entries = Entry.objects.filter(transaction=invoice.ledger_transaction)
        assert entries.count() == 2

    def test_receivable_debited_revenue_credited(
        self, committed_basket, prices, clinic, patient, user
    ):
        """AR is debited, Revenue is credited."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=True,
        )

        entries = Entry.objects.filter(transaction=invoice.ledger_transaction)

        debit_entry = entries.get(entry_type="debit")
        credit_entry = entries.get(entry_type="credit")

        assert debit_entry.account.account_type == "receivable"
        assert credit_entry.account.account_type == "revenue"
        assert debit_entry.amount == invoice.total_amount
        assert credit_entry.amount == invoice.total_amount

    def test_payment_debits_cash_credits_receivable(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Payment creates debit Cash, credit Receivable."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=True,
        )

        # Record payment
        invoice = record_payment(
            invoice=invoice,
            amount=invoice.total_amount,
            payment_method="card",
            recorded_by=user,
        )

        assert invoice.status == "paid"
        assert invoice.paid_at is not None

        # Find payment transaction (not the invoice transaction)
        payment_tx = Transaction.objects.filter(
            description__icontains="Payment for"
        ).first()
        assert payment_tx is not None

        payment_entries = Entry.objects.filter(transaction=payment_tx)
        debit = payment_entries.get(entry_type="debit")
        credit = payment_entries.get(entry_type="credit")

        assert debit.account.account_type == "asset"  # Cash
        assert credit.account.account_type == "receivable"  # AR reduction

    def test_transaction_metadata_includes_invoice_id(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Ledger transaction metadata includes invoice reference."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=True,
        )

        tx = invoice.ledger_transaction
        assert tx.metadata["invoice_id"] == str(invoice.pk)
        assert tx.metadata["invoice_number"] == invoice.invoice_number


# =============================================================================
# Payment Tests
# =============================================================================


@pytest.mark.django_db
class TestPayment:
    """Tests for record_payment()."""

    def test_cannot_pay_draft_invoice(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Cannot record payment on draft invoice."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        with pytest.raises(InvoiceStateError) as exc_info:
            record_payment(
                invoice=invoice,
                amount=invoice.total_amount,
                payment_method="cash",
                recorded_by=user,
            )

        assert "must be 'issued'" in str(exc_info.value)

    def test_cannot_overpay_invoice(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Cannot pay more than invoice total."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=True,
        )

        with pytest.raises(InvoiceStateError) as exc_info:
            record_payment(
                invoice=invoice,
                amount=invoice.total_amount + Decimal("100"),
                payment_method="cash",
                recorded_by=user,
            )

        assert "exceeds invoice total" in str(exc_info.value)


# =============================================================================
# P0 Constraint Tests (Data Integrity)
# =============================================================================


@pytest.mark.django_db(transaction=True)
class TestInvoiceLineItemConstraints:
    """Tests for P0 data integrity constraints on InvoiceLineItem."""

    def test_zero_quantity_rejected_by_db(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Line item with quantity=0 is rejected by DB constraint."""
        from django.db import IntegrityError, transaction as db_transaction

        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        # Try to create a line item with quantity=0
        with pytest.raises(IntegrityError) as exc_info:
            with db_transaction.atomic():
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    priced_basket_item=invoice.line_items.first().priced_basket_item,
                    description="Zero quantity test",
                    quantity=0,
                    unit_price_amount=Decimal("10.00"),
                    line_total_amount=Decimal("0.00"),
                    price_scope_type="global",
                    price_rule_id=prices["aspirin"].pk,
                )

        assert "invoicelineitem_quantity_positive" in str(exc_info.value).lower()

    def test_inconsistent_line_total_rejected_by_db(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Line total that doesn't match qty * unit_price is rejected."""
        from django.db import IntegrityError, transaction as db_transaction

        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        # Try to create a line item where total != qty * price
        # quantity=2, unit_price=10.00, but line_total=50.00 (should be 20.00)
        with pytest.raises(IntegrityError) as exc_info:
            with db_transaction.atomic():
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    priced_basket_item=invoice.line_items.first().priced_basket_item,
                    description="Inconsistent total test",
                    quantity=2,
                    unit_price_amount=Decimal("10.0000"),
                    line_total_amount=Decimal("50.0000"),  # Wrong! Should be 20.00
                    price_scope_type="global",
                    price_rule_id=prices["aspirin"].pk,
                )

        assert "invoicelineitem_total_equals_qty_times_price" in str(exc_info.value).lower()

    def test_consistent_line_item_accepted(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Line item with correct qty * unit_price = total is accepted."""
        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        # Get an existing priced basket item to link to
        from primitives_testbed.pricing.models import PricedBasketItem

        # Create a new basket item for this test
        new_basket_item = BasketItem.objects.create(
            basket=committed_basket,
            catalog_item=invoice.line_items.first().priced_basket_item.basket_item.catalog_item,
            quantity=3,
            added_by=user,
        )

        priced_item = PricedBasketItem.objects.create(
            basket_item=new_basket_item,
            unit_price_amount=Decimal("15.0000"),
            unit_price_currency="USD",
            price_rule=prices["aspirin"],
        )

        # This should succeed: 3 * 15.00 = 45.00
        line = InvoiceLineItem.objects.create(
            invoice=invoice,
            priced_basket_item=priced_item,
            description="Consistent total test",
            quantity=3,
            unit_price_amount=Decimal("15.0000"),
            line_total_amount=Decimal("45.0000"),  # Correct: 3 * 15 = 45
            price_scope_type="global",
            price_rule_id=prices["aspirin"].pk,
        )

        assert line.pk is not None


@pytest.mark.django_db(transaction=True)
class TestInvoiceNumberGeneration:
    """Tests for atomic invoice number generation."""

    def test_invoice_numbers_are_unique(
        self, committed_basket, prices, clinic, patient, user, encounter_definition
    ):
        """Each invoice gets a unique number."""
        # Create first invoice
        invoice1 = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        # Create another encounter and basket for second invoice
        person_ct = ContentType.objects.get_for_model(Person)
        encounter2 = Encounter.objects.create(
            definition=encounter_definition,
            subject_type=person_ct,
            subject_id=str(patient.pk),
            state="checked_in",
            created_by=user,
        )
        basket2 = Basket.objects.create(
            encounter=encounter2,
            status="committed",
            created_by=user,
        )
        BasketItem.objects.create(
            basket=basket2,
            catalog_item=prices["aspirin"].catalog_item,
            quantity=1,
            added_by=user,
        )

        invoice2 = create_invoice_from_basket(
            basket2,
            created_by=user,
            issue_immediately=False,
        )

        assert invoice1.invoice_number != invoice2.invoice_number

    def test_invoice_number_format(
        self, committed_basket, prices, clinic, patient, user
    ):
        """Invoice number follows INV-YYYY-NNNN format."""
        import re

        invoice = create_invoice_from_basket(
            committed_basket,
            created_by=user,
            issue_immediately=False,
        )

        # Should match INV-YYYY-NNNN pattern
        pattern = r"^INV-\d{4}-\d{4}$"
        assert re.match(pattern, invoice.invoice_number), \
            f"Invoice number {invoice.invoice_number} doesn't match expected pattern"
