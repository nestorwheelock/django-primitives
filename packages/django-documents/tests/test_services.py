"""Tests for document services."""
import pytest
import hashlib
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from django_documents.models import Document
from django_documents.services import attach_document, verify_document_integrity
from django_documents.exceptions import ChecksumMismatchError, DocumentNotFoundError
from tests.models import Organization, Invoice


User = get_user_model()


@pytest.mark.django_db
class TestAttachDocument:
    """Test suite for attach_document service."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        """Create a test invoice."""
        return Invoice.objects.create(number="INV-001", org=org)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def sample_content(self):
        """Sample file content."""
        return b"This is test file content for document attachment."

    @pytest.fixture
    def sample_file(self, sample_content):
        """Create a sample uploaded file."""
        return SimpleUploadedFile(
            name="test_document.pdf",
            content=sample_content,
            content_type="application/pdf",
        )

    def test_attach_document_creates_document(self, invoice, sample_file, user):
        """attach_document should create a Document record."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )
        assert doc is not None
        assert doc.pk is not None

    def test_attach_document_sets_target(self, invoice, sample_file, user):
        """attach_document should set the target correctly."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )
        assert doc.target == invoice

    def test_attach_document_stores_file(self, invoice, sample_file, user):
        """attach_document should store the file."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )
        assert doc.file is not None
        assert doc.file.size > 0

    def test_attach_document_sets_filename(self, invoice, sample_file, user):
        """attach_document should set filename from uploaded file."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )
        assert doc.filename == "test_document.pdf"

    def test_attach_document_sets_content_type(self, invoice, sample_file, user):
        """attach_document should set content_type from uploaded file."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )
        assert doc.content_type == "application/pdf"

    def test_attach_document_sets_file_size(self, invoice, sample_file, sample_content, user):
        """attach_document should calculate and set file size."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )
        assert doc.file_size == len(sample_content)

    def test_attach_document_computes_checksum(self, invoice, sample_content, user):
        """attach_document should compute and store SHA-256 checksum."""
        expected_checksum = hashlib.sha256(sample_content).hexdigest()
        sample_file = SimpleUploadedFile("test.pdf", sample_content, "application/pdf")

        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )
        assert doc.checksum == expected_checksum

    def test_attach_document_sets_document_type(self, invoice, sample_file, user):
        """attach_document should set document_type."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="receipt_image",
            uploaded_by=user,
        )
        assert doc.document_type == "receipt_image"

    def test_attach_document_with_description(self, invoice, sample_file, user):
        """attach_document should accept optional description."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
            description="Main invoice PDF",
        )
        assert doc.description == "Main invoice PDF"

    def test_attach_document_with_retention_days(self, invoice, sample_file, user):
        """attach_document should accept retention_days."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
            retention_days=365 * 7,
        )
        assert doc.retention_days == 365 * 7

    def test_attach_document_with_retention_policy(self, invoice, sample_file, user):
        """attach_document should accept retention_policy."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
            retention_policy="regulatory",
        )
        assert doc.retention_policy == "regulatory"

    def test_attach_document_with_metadata(self, invoice, sample_file, user):
        """attach_document should accept metadata."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
            metadata={"page_count": 3, "generated_by": "system"},
        )
        assert doc.metadata["page_count"] == 3
        assert doc.metadata["generated_by"] == "system"

    def test_attach_document_stores_uploader_in_metadata(self, invoice, sample_file, user):
        """attach_document should store uploaded_by user in metadata."""
        doc = attach_document(
            target=invoice,
            file=sample_file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )
        assert doc.metadata.get("uploaded_by_id") == user.pk


@pytest.mark.django_db
class TestVerifyDocumentIntegrity:
    """Test suite for verify_document_integrity service."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        """Create a test invoice."""
        return Invoice.objects.create(number="INV-001", org=org)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    def test_verify_integrity_returns_true_for_valid(self, invoice, user):
        """verify_document_integrity should return True for valid document."""
        content = b"Test content for integrity check."
        file = SimpleUploadedFile("test.pdf", content, "application/pdf")

        doc = attach_document(
            target=invoice,
            file=file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )

        assert verify_document_integrity(doc) is True

    def test_verify_integrity_raises_for_invalid(self, invoice, user):
        """verify_document_integrity should raise ChecksumMismatchError for tampered document."""
        from django_documents.models import Document

        content = b"Test content."
        file = SimpleUploadedFile("test.pdf", content, "application/pdf")

        doc = attach_document(
            target=invoice,
            file=file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )

        # Simulate tampering by changing checksum directly in database
        # (bypasses model save() to simulate database-level corruption)
        Document.objects.filter(pk=doc.pk).update(checksum="invalid_checksum")
        doc.refresh_from_db()

        with pytest.raises(ChecksumMismatchError):
            verify_document_integrity(doc)

    def test_verify_integrity_by_document_id(self, invoice, user):
        """verify_document_integrity should accept document ID."""
        content = b"Test content."
        file = SimpleUploadedFile("test.pdf", content, "application/pdf")

        doc = attach_document(
            target=invoice,
            file=file,
            document_type="invoice_pdf",
            uploaded_by=user,
        )

        assert verify_document_integrity(doc.pk) is True

    def test_verify_integrity_raises_for_missing_document(self):
        """verify_document_integrity should raise DocumentNotFoundError for missing document."""
        with pytest.raises(DocumentNotFoundError):
            verify_document_integrity(99999)
