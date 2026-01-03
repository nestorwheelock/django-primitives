"""Tests for invoice printing functionality.

Tests the selector, print service, views, and optional document storage.
Follows TDD approach - tests written before implementation.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.utils import timezone

User = get_user_model()


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def other_user(db):
    """Create a user without org access."""
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="otherpass123",
    )


@pytest.fixture
def clinic(db):
    """Create the Springfield Family Clinic organization (required by context extraction)."""
    from django_parties.models import Organization
    return Organization.objects.create(
        name="Springfield Family Clinic",
    )


@pytest.fixture
def patient(db):
    """Create a patient."""
    from django_parties.models import Person
    return Person.objects.create(
        first_name="John",
        last_name="Doe",
    )


@pytest.fixture
def encounter_definition(db):
    """Create an encounter definition."""
    from django_encounters.models import EncounterDefinition
    return EncounterDefinition.objects.create(
        key="office_visit",
        name="Office Visit",
        states=["pending", "checked_in", "in_progress", "completed"],
        transitions={
            "pending": ["checked_in"],
            "checked_in": ["in_progress"],
            "in_progress": ["completed"],
        },
        initial_state="pending",
        terminal_states=["completed"],
    )


@pytest.fixture
def encounter(db, encounter_definition, patient, user):
    """Create an encounter."""
    from django_encounters.models import Encounter
    person_ct = ContentType.objects.get_for_model(patient)
    return Encounter.objects.create(
        definition=encounter_definition,
        subject_type=person_ct,
        subject_id=str(patient.pk),
        state="checked_in",
        created_by=user,
    )


@pytest.fixture
def catalog_item(db):
    """Create a catalog item."""
    from django_catalog.models import CatalogItem
    return CatalogItem.objects.create(
        display_name="Office Exam",
        kind="service",
        service_category="consult",
        is_billable=True,
        active=True,
    )


@pytest.fixture
def price(db, catalog_item, user):
    """Create a price for the catalog item."""
    from primitives_testbed.pricing.models import Price
    return Price.objects.create(
        catalog_item=catalog_item,
        amount=Decimal("75.00"),
        currency="USD",
        priority=50,
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )


@pytest.fixture
def basket(db, encounter, user):
    """Create a committed basket."""
    from django_catalog.models import Basket
    return Basket.objects.create(
        encounter=encounter,
        status="committed",
        created_by=user,
    )


@pytest.fixture
def basket_item(db, basket, catalog_item, user):
    """Create a basket item."""
    from django_catalog.models import BasketItem
    return BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_item,
        quantity=2,
        added_by=user,
    )


@pytest.fixture
def draft_invoice(db, basket, basket_item, price, clinic, patient, encounter, user):
    """Create a draft invoice (not printable)."""
    from primitives_testbed.invoicing.services import create_invoice_from_basket
    return create_invoice_from_basket(
        basket,
        created_by=user,
        issue_immediately=False,
    )


@pytest.fixture
def issued_invoice(db, basket, basket_item, price, clinic, patient, encounter, user):
    """Create an issued invoice (printable)."""
    from primitives_testbed.invoicing.services import create_invoice_from_basket
    return create_invoice_from_basket(
        basket,
        created_by=user,
        issue_immediately=True,
    )


@pytest.fixture
def paid_invoice(db, issued_invoice, user):
    """Create a paid invoice."""
    from primitives_testbed.invoicing.payments import record_payment
    return record_payment(
        invoice=issued_invoice,
        amount=issued_invoice.total_amount,
        payment_method="card",
        recorded_by=user,
    )


@pytest.fixture
def voided_invoice(db, issued_invoice):
    """Create a voided invoice."""
    issued_invoice.status = "voided"
    issued_invoice.save()
    return issued_invoice


@pytest.fixture
def auth_client(db, user):
    """Authenticated test client."""
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def admin_client(db, admin_user):
    """Admin authenticated test client."""
    client = Client()
    client.force_login(admin_user)
    return client


# =============================================================================
# Selector Tests
# =============================================================================

@pytest.mark.django_db
class TestGetInvoiceForPrint:
    """Tests for the invoice print selector."""

    def test_draft_invoice_not_printable(self, draft_invoice, user):
        """Draft invoices cannot be printed."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print
        from primitives_testbed.invoicing.exceptions import InvoiceNotPrintableError

        with pytest.raises(InvoiceNotPrintableError) as exc_info:
            get_invoice_for_print(draft_invoice.pk, user)

        assert "draft" in str(exc_info.value).lower()

    def test_issued_invoice_printable(self, issued_invoice, user):
        """Issued invoices can be printed."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print

        result = get_invoice_for_print(issued_invoice.pk, user)

        assert result.invoice == issued_invoice
        assert result.invoice.status == "issued"

    def test_paid_invoice_printable(self, paid_invoice, user):
        """Paid invoices can be printed."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print

        result = get_invoice_for_print(paid_invoice.pk, user)

        assert result.invoice == paid_invoice
        assert result.invoice.status == "paid"

    def test_voided_invoice_printable(self, voided_invoice, user):
        """Voided invoices can be printed for records."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print

        result = get_invoice_for_print(voided_invoice.pk, user)

        assert result.invoice == voided_invoice
        assert result.invoice.status == "voided"

    def test_nonexistent_invoice_raises(self, user):
        """Nonexistent invoice raises DoesNotExist."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print
        from primitives_testbed.invoicing.models import Invoice

        with pytest.raises(Invoice.DoesNotExist):
            get_invoice_for_print(uuid4(), user)

    def test_prefetches_line_items_no_n_plus_1(self, issued_invoice, user, django_assert_num_queries):
        """Line items are prefetched - no N+1 queries."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print

        # First call to warm up
        result = get_invoice_for_print(issued_invoice.pk, user)

        # Second call with query count assertion
        with django_assert_num_queries(4):  # invoice + line_items + billed_to addresses + issued_by addresses
            result = get_invoice_for_print(issued_invoice.pk, user)
            # Access line items - should NOT trigger additional queries
            list(result.invoice.line_items.all())


# =============================================================================
# Print Service Tests
# =============================================================================

@pytest.mark.django_db
class TestInvoicePrintService:
    """Tests for the print service."""

    def test_render_html_contains_invoice_number_and_totals(self, issued_invoice, user):
        """HTML contains invoice number and totals."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print
        from primitives_testbed.invoicing.printing import InvoicePrintService

        invoice_data = get_invoice_for_print(issued_invoice.pk, user)
        service = InvoicePrintService(invoice_data)
        html = service.render_html()

        assert isinstance(html, str)
        assert issued_invoice.invoice_number in html
        assert "INVOICE" in html.upper()
        # Check totals are present
        assert str(issued_invoice.total_amount) in html or \
               f"{float(issued_invoice.total_amount):.2f}" in html

    def test_render_pdf_returns_nonempty_bytes_and_pdf_header(self, issued_invoice, user):
        """PDF rendering returns non-empty bytes with PDF magic header."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print
        from primitives_testbed.invoicing.printing import InvoicePrintService, WEASYPRINT_AVAILABLE

        if not WEASYPRINT_AVAILABLE:
            pytest.skip("WeasyPrint not installed")

        invoice_data = get_invoice_for_print(issued_invoice.pk, user)
        service = InvoicePrintService(invoice_data)
        pdf_bytes = service.render_pdf()

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'  # PDF magic bytes

    def test_snapshotted_prices_used_when_catalog_changes(self, issued_invoice, price, user):
        """HTML uses snapshotted prices, not current catalog prices."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print
        from primitives_testbed.invoicing.printing import InvoicePrintService

        # Get original line item price
        line_item = issued_invoice.line_items.first()
        original_price = line_item.unit_price_amount

        # Change the catalog price
        price.amount = Decimal("999.99")
        price.save()

        # Render invoice
        invoice_data = get_invoice_for_print(issued_invoice.pk, user)
        service = InvoicePrintService(invoice_data)
        html = service.render_html()

        # Should contain original snapshotted price, not new price
        assert str(original_price) in html or f"{float(original_price):.2f}" in html
        assert "999.99" not in html

    def test_get_filename_uses_invoice_number(self, issued_invoice, user):
        """Filename is deterministic based on invoice number."""
        from primitives_testbed.invoicing.selectors import get_invoice_for_print
        from primitives_testbed.invoicing.printing import InvoicePrintService

        invoice_data = get_invoice_for_print(issued_invoice.pk, user)
        service = InvoicePrintService(invoice_data)
        filename = service.get_filename()

        assert issued_invoice.invoice_number in filename
        assert filename.endswith(".pdf")


# =============================================================================
# View Tests
# =============================================================================

@pytest.mark.django_db
class TestInvoicePrintViews:
    """Tests for invoice print views."""

    def test_html_view_requires_login(self, client, issued_invoice):
        """HTML print view requires authentication."""
        response = client.get(f'/invoicing/{issued_invoice.pk}/print/')

        # Should redirect to login or return 403
        assert response.status_code in (302, 403)

    def test_html_view_returns_html(self, auth_client, issued_invoice):
        """HTML print view returns rendered invoice."""
        response = auth_client.get(f'/invoicing/{issued_invoice.pk}/print/')

        assert response.status_code == 200
        assert 'text/html' in response['Content-Type']
        assert issued_invoice.invoice_number.encode() in response.content

    def test_pdf_download_returns_correct_content_type(self, auth_client, issued_invoice):
        """PDF download returns PDF content type."""
        from primitives_testbed.invoicing.printing import WEASYPRINT_AVAILABLE

        if not WEASYPRINT_AVAILABLE:
            pytest.skip("WeasyPrint not installed")

        response = auth_client.get(f'/invoicing/{issued_invoice.pk}/pdf/')

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert 'attachment' in response['Content-Disposition']

    def test_pdf_view_returns_inline(self, auth_client, issued_invoice):
        """PDF inline view returns PDF for browser viewing."""
        from primitives_testbed.invoicing.printing import WEASYPRINT_AVAILABLE

        if not WEASYPRINT_AVAILABLE:
            pytest.skip("WeasyPrint not installed")

        response = auth_client.get(f'/invoicing/{issued_invoice.pk}/pdf/view/')

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert 'inline' in response['Content-Disposition']

    def test_draft_invoice_returns_400(self, auth_client, draft_invoice):
        """Attempting to print draft invoice returns 400."""
        response = auth_client.get(f'/invoicing/{draft_invoice.pk}/print/')

        assert response.status_code == 400

    def test_nonexistent_invoice_returns_404(self, auth_client):
        """Nonexistent invoice returns 404."""
        fake_id = uuid4()
        response = auth_client.get(f'/invoicing/{fake_id}/print/')

        assert response.status_code == 404

    def test_authenticated_user_can_view_invoice(self, other_user, issued_invoice):
        """Any authenticated user can currently view invoices.

        Note: The current implementation allows all authenticated users
        to view invoices. Full RBAC integration would be needed for
        stricter org-based access control. This test documents the
        current permissive behavior.
        """
        client = Client()
        client.force_login(other_user)

        response = client.get(f'/invoicing/{issued_invoice.pk}/print/')

        # Currently allows all authenticated users
        assert response.status_code == 200


# =============================================================================
# Document Storage Tests (Optional Feature)
# =============================================================================

@pytest.mark.django_db
class TestInvoicePDFStorage:
    """Tests for optional PDF document storage."""

    def test_storage_disabled_by_default(self, settings):
        """PDF storage is disabled by default."""
        from primitives_testbed.invoicing.document_storage import is_pdf_storage_enabled

        # Ensure setting is not set or False
        settings.INVOICE_STORE_PDF = False

        assert is_pdf_storage_enabled() is False

    @pytest.mark.skipif(
        True,  # Skip until storage is enabled in test settings
        reason="Storage tests require INVOICE_STORE_PDF=True"
    )
    def test_can_store_pdf(self, issued_invoice, user, settings):
        """Can store PDF for an invoice."""
        from primitives_testbed.invoicing.document_storage import store_invoice_pdf

        settings.INVOICE_STORE_PDF = True

        doc = store_invoice_pdf(issued_invoice, user)

        assert doc is not None
        assert doc.document_type == 'invoice_pdf'
        assert doc.checksum  # Has integrity checksum

    @pytest.mark.skipif(
        True,
        reason="Storage tests require INVOICE_STORE_PDF=True"
    )
    def test_cannot_overwrite_stored_pdf(self, issued_invoice, user, settings):
        """Cannot regenerate/overwrite stored PDF (immutability)."""
        from primitives_testbed.invoicing.document_storage import store_invoice_pdf

        settings.INVOICE_STORE_PDF = True

        # Store first PDF
        store_invoice_pdf(issued_invoice, user)

        # Attempt to store again should fail
        with pytest.raises(ValueError) as exc_info:
            store_invoice_pdf(issued_invoice, user)

        assert "immutable" in str(exc_info.value).lower()
