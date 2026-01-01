"""Tests for document retention policy functionality."""
import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from django_documents.models import Document
from django_documents.exceptions import RetentionViolationError
from tests.models import Organization, Invoice


@pytest.mark.django_db
class TestRetentionPolicyFields:
    """Test suite for retention policy fields on Document model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        """Create a test invoice."""
        return Invoice.objects.create(number="INV-001", org=org)

    @pytest.fixture
    def sample_file(self):
        """Create a sample uploaded file."""
        return SimpleUploadedFile("test.pdf", b"content", "application/pdf")

    def test_document_has_retention_days_field(self, invoice, sample_file):
        """Document should have retention_days field."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            retention_days=365 * 7,  # 7 years
        )
        assert doc.retention_days == 365 * 7

    def test_document_retention_days_nullable(self, invoice, sample_file):
        """Document retention_days should be nullable (keep forever)."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            retention_days=None,
        )
        assert doc.retention_days is None

    def test_document_has_retention_policy_field(self, invoice, sample_file):
        """Document should have retention_policy classification."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            retention_policy="regulatory",
        )
        assert doc.retention_policy == "regulatory"

    def test_document_retention_policy_defaults_to_standard(self, invoice, sample_file):
        """Document retention_policy should default to 'standard'."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.retention_policy == "standard"

    def test_document_has_expires_at_field(self, invoice, sample_file):
        """Document should have expires_at datetime field."""
        expires = timezone.now() + timedelta(days=365)
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=expires,
        )
        assert doc.expires_at is not None
        # Allow small time difference due to test execution
        assert abs((doc.expires_at - expires).total_seconds()) < 1

    def test_document_expires_at_nullable(self, invoice, sample_file):
        """Document expires_at should be nullable (never expires)."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=None,
        )
        assert doc.expires_at is None


@pytest.mark.django_db
class TestRetentionProperties:
    """Test suite for retention-related properties and methods."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        """Create a test invoice."""
        return Invoice.objects.create(number="INV-001", org=org)

    @pytest.fixture
    def sample_file(self):
        """Create a sample uploaded file."""
        return SimpleUploadedFile("test.pdf", b"content", "application/pdf")

    def test_is_expired_returns_true_for_past_date(self, invoice, sample_file):
        """is_expired should return True when expires_at is in the past."""
        past_date = timezone.now() - timedelta(days=1)
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=past_date,
        )
        assert doc.is_expired is True

    def test_is_expired_returns_false_for_future_date(self, invoice, sample_file):
        """is_expired should return False when expires_at is in the future."""
        future_date = timezone.now() + timedelta(days=365)
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=future_date,
        )
        assert doc.is_expired is False

    def test_is_expired_returns_false_when_no_expiration(self, invoice, sample_file):
        """is_expired should return False when expires_at is None."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=None,
        )
        assert doc.is_expired is False

    def test_under_retention_returns_true_during_retention_period(self, invoice, sample_file):
        """under_retention should return True during the retention period."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            retention_days=365,  # 1 year retention
        )
        # Document was just created, so it's under retention
        assert doc.under_retention is True

    def test_under_retention_returns_false_after_retention_period(self, invoice, sample_file):
        """under_retention should return False after retention period ends."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            retention_days=0,  # No retention period
        )
        assert doc.under_retention is False

    def test_under_retention_returns_true_when_no_retention_set(self, invoice, sample_file):
        """under_retention should return True when retention_days is None (keep forever)."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            retention_days=None,  # Keep forever
        )
        assert doc.under_retention is True

    def test_retention_ends_at_property(self, invoice, sample_file):
        """retention_ends_at should return the date when retention ends."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            retention_days=365,
        )
        expected = doc.created_at + timedelta(days=365)
        # Allow small time difference
        assert abs((doc.retention_ends_at - expected).total_seconds()) < 1

    def test_retention_ends_at_returns_none_when_no_retention(self, invoice, sample_file):
        """retention_ends_at should return None when retention_days is None."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            retention_days=None,
        )
        assert doc.retention_ends_at is None


@pytest.mark.django_db
class TestRetentionQuerySet:
    """Test suite for retention-related queryset methods."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        """Create a test invoice."""
        return Invoice.objects.create(number="INV-001", org=org)

    def test_expired_returns_expired_documents(self, invoice):
        """expired() should return documents past their expiration date."""
        past_date = timezone.now() - timedelta(days=1)
        future_date = timezone.now() + timedelta(days=365)

        file1 = SimpleUploadedFile("expired.pdf", b"content1", "application/pdf")
        file2 = SimpleUploadedFile("valid.pdf", b"content2", "application/pdf")

        expired_doc = Document.objects.create(
            target=invoice,
            file=file1,
            filename="expired.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=past_date,
        )
        valid_doc = Document.objects.create(
            target=invoice,
            file=file2,
            filename="valid.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=future_date,
        )

        expired_docs = Document.objects.expired()
        assert expired_doc in expired_docs
        assert valid_doc not in expired_docs

    def test_expired_excludes_documents_without_expiration(self, invoice):
        """expired() should exclude documents with no expiration date."""
        file1 = SimpleUploadedFile("doc.pdf", b"content", "application/pdf")

        no_expiry_doc = Document.objects.create(
            target=invoice,
            file=file1,
            filename="doc.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=None,
        )

        expired_docs = Document.objects.expired()
        assert no_expiry_doc not in expired_docs

    def test_not_expired_returns_valid_documents(self, invoice):
        """not_expired() should return documents that are not expired."""
        past_date = timezone.now() - timedelta(days=1)
        future_date = timezone.now() + timedelta(days=365)

        file1 = SimpleUploadedFile("expired.pdf", b"content1", "application/pdf")
        file2 = SimpleUploadedFile("valid.pdf", b"content2", "application/pdf")
        file3 = SimpleUploadedFile("no_expiry.pdf", b"content3", "application/pdf")

        expired_doc = Document.objects.create(
            target=invoice,
            file=file1,
            filename="expired.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=past_date,
        )
        valid_doc = Document.objects.create(
            target=invoice,
            file=file2,
            filename="valid.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=future_date,
        )
        no_expiry_doc = Document.objects.create(
            target=invoice,
            file=file3,
            filename="no_expiry.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            expires_at=None,
        )

        not_expired_docs = Document.objects.not_expired()
        assert expired_doc not in not_expired_docs
        assert valid_doc in not_expired_docs
        assert no_expiry_doc in not_expired_docs
