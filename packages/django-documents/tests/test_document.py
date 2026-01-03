"""Tests for Document model."""
import pytest
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from django_documents.models import Document
from tests.models import Organization, Invoice


@pytest.mark.django_db
class TestDocumentModel:
    """Test suite for Document model."""

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
        content = b"This is test file content for document testing."
        return SimpleUploadedFile(
            name="test_document.pdf",
            content=content,
            content_type="application/pdf",
        )

    def test_document_has_target_generic_fk(self, invoice, sample_file):
        """Document should have target via GenericFK."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.target == invoice

    def test_document_target_uses_charfield_for_id(self, invoice, sample_file):
        """Document target_id should be CharField (UUID support)."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        # target_id should be string
        assert isinstance(doc.target_id, str)
        assert doc.target_id == str(invoice.pk)

    def test_document_has_file_field(self, invoice, sample_file):
        """Document should have a file field."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.file is not None

    def test_document_has_filename(self, invoice, sample_file):
        """Document should store original filename."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="my_invoice.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.filename == "my_invoice.pdf"

    def test_document_has_content_type(self, invoice, sample_file):
        """Document should store MIME content type."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.content_type == "application/pdf"

    def test_document_has_document_type(self, invoice, sample_file):
        """Document should have a document_type classification."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.document_type == "invoice_pdf"

    def test_document_has_file_size(self, invoice, sample_file):
        """Document should track file size in bytes."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            file_size=len(sample_file.read()),
        )
        assert doc.file_size > 0

    def test_document_has_checksum(self, invoice, sample_file):
        """Document should have SHA-256 checksum field."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            checksum="abc123",  # Will be computed properly in service
        )
        assert doc.checksum == "abc123"

    def test_document_has_timestamps(self, invoice, sample_file):
        """Document should have created_at and updated_at."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.created_at is not None
        assert doc.updated_at is not None

    def test_document_can_have_description(self, invoice, sample_file):
        """Document can have optional description."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            description="Invoice PDF for order #123",
        )
        assert doc.description == "Invoice PDF for order #123"

    def test_document_description_is_optional(self, invoice, sample_file):
        """Document description should be optional."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.description == ""

    def test_document_has_metadata_json_field(self, invoice, sample_file):
        """Document should have metadata JSONField."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            metadata={"page_count": 5, "author": "Test User"},
        )
        assert doc.metadata["page_count"] == 5
        assert doc.metadata["author"] == "Test User"

    def test_document_metadata_defaults_to_empty_dict(self, invoice, sample_file):
        """Document metadata should default to empty dict."""
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        assert doc.metadata == {}


@pytest.mark.django_db
class TestDocumentQuerySet:
    """Test suite for Document queryset methods."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        """Create a test invoice."""
        return Invoice.objects.create(number="INV-001", org=org)

    @pytest.fixture
    def second_invoice(self, org):
        """Create another test invoice."""
        return Invoice.objects.create(number="INV-002", org=org)

    def test_for_target_returns_documents_for_object(self, invoice, second_invoice):
        """for_target() should return documents attached to specific object."""
        file1 = SimpleUploadedFile("doc1.pdf", b"content1", "application/pdf")
        file2 = SimpleUploadedFile("doc2.pdf", b"content2", "application/pdf")
        file3 = SimpleUploadedFile("doc3.pdf", b"content3", "application/pdf")

        doc1 = Document.objects.create(
            target=invoice,
            file=file1,
            filename="doc1.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        doc2 = Document.objects.create(
            target=invoice,
            file=file2,
            filename="doc2.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        doc3 = Document.objects.create(
            target=second_invoice,
            file=file3,
            filename="doc3.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        invoice_docs = Document.objects.for_target(invoice)
        assert invoice_docs.count() == 2
        assert doc1 in invoice_docs
        assert doc2 in invoice_docs
        assert doc3 not in invoice_docs

    def test_for_target_with_document_type_filter(self, invoice):
        """for_target() can be chained with document_type filter."""
        file1 = SimpleUploadedFile("doc1.pdf", b"content1", "application/pdf")
        file2 = SimpleUploadedFile("doc2.jpg", b"content2", "image/jpeg")

        Document.objects.create(
            target=invoice,
            file=file1,
            filename="doc1.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        Document.objects.create(
            target=invoice,
            file=file2,
            filename="doc2.jpg",
            content_type="image/jpeg",
            document_type="receipt_image",
        )

        pdf_docs = Document.objects.for_target(invoice).filter(document_type="invoice_pdf")
        assert pdf_docs.count() == 1


@pytest.mark.django_db
class TestDocumentChecksum:
    """Test suite for document checksum functionality."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        """Create a test invoice."""
        return Invoice.objects.create(number="INV-001", org=org)

    def test_compute_checksum_returns_sha256(self, invoice):
        """compute_checksum() should return SHA-256 hash."""
        import hashlib

        content = b"This is test content for checksum verification."
        expected_checksum = hashlib.sha256(content).hexdigest()

        file = SimpleUploadedFile("test.pdf", content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            checksum=expected_checksum,
        )

        assert doc.compute_checksum() == expected_checksum

    def test_verify_checksum_returns_true_for_valid(self, invoice):
        """verify_checksum() should return True when checksum matches."""
        import hashlib

        content = b"This is test content for checksum verification."
        checksum = hashlib.sha256(content).hexdigest()

        file = SimpleUploadedFile("test.pdf", content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            checksum=checksum,
        )

        assert doc.verify_checksum() is True

    def test_verify_checksum_returns_false_for_invalid(self, invoice):
        """verify_checksum() should return False when checksum doesn't match."""
        content = b"This is test content."
        file = SimpleUploadedFile("test.pdf", content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            checksum="invalid_checksum_value",
        )

        assert doc.verify_checksum() is False

    def test_checksum_is_immutable_after_set(self, invoice):
        """Once checksum is set, it cannot be changed."""
        from django_documents.exceptions import ImmutableChecksumError

        content = b"This is test content."
        file = SimpleUploadedFile("test.pdf", content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            checksum="original_checksum_value",
        )

        # Attempt to modify checksum should raise
        doc.checksum = "new_checksum_value"
        with pytest.raises(ImmutableChecksumError) as exc_info:
            doc.save()

        assert str(doc.pk) in str(exc_info.value)

    def test_checksum_error_includes_document_id(self, invoice):
        """ImmutableChecksumError should include document ID."""
        from django_documents.exceptions import ImmutableChecksumError

        content = b"This is test content."
        file = SimpleUploadedFile("test.pdf", content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            checksum="original_checksum",
        )

        with pytest.raises(ImmutableChecksumError) as exc_info:
            doc.checksum = "modified_checksum"
            doc.save()

        assert exc_info.value.document_id == doc.pk

    def test_can_update_document_without_changing_checksum(self, invoice):
        """Other fields can be updated as long as checksum stays the same."""
        content = b"This is test content."
        file = SimpleUploadedFile("test.pdf", content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            checksum="valid_checksum",
        )

        # Update description (should work)
        doc.description = "Updated description"
        doc.save()  # Should not raise

        doc.refresh_from_db()
        assert doc.description == "Updated description"
        assert doc.checksum == "valid_checksum"

    def test_can_set_checksum_on_document_without_checksum(self, invoice):
        """Can set checksum if it was originally empty."""
        content = b"This is test content."
        file = SimpleUploadedFile("test.pdf", content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            # No checksum set
        )

        # Setting checksum for first time should work
        doc.checksum = "new_checksum_value"
        doc.save()  # Should not raise

        doc.refresh_from_db()
        assert doc.checksum == "new_checksum_value"
