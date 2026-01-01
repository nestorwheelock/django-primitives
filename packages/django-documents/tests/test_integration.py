"""Integration tests for django-documents."""
import pytest
import hashlib
from datetime import timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from django_documents.models import Document
from django_documents.services import attach_document, verify_document_integrity
from django_documents.exceptions import ChecksumMismatchError
from tests.models import Organization, Invoice


User = get_user_model()


@pytest.mark.django_db
class TestRealWorldUsage:
    """Integration tests simulating real-world usage patterns."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Acme Corp")

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    def test_invoice_document_workflow(self, org, user):
        """Test complete invoice document workflow."""
        # Create invoice
        invoice = Invoice.objects.create(number="INV-2026-001", org=org)

        # Attach PDF invoice
        pdf_content = b"%PDF-1.4 Invoice document content here..."
        pdf_file = SimpleUploadedFile("invoice.pdf", pdf_content, "application/pdf")

        doc = attach_document(
            target=invoice,
            file=pdf_file,
            document_type="invoice_pdf",
            uploaded_by=user,
            description="Original invoice PDF",
            retention_days=365 * 7,  # 7 year retention for tax purposes
            retention_policy="regulatory",
        )

        # Verify document was created correctly
        assert doc.target == invoice
        assert doc.document_type == "invoice_pdf"
        assert doc.retention_policy == "regulatory"
        assert doc.retention_days == 365 * 7

        # Verify checksum
        assert verify_document_integrity(doc) is True

        # Query documents for invoice
        invoice_docs = Document.objects.for_target(invoice)
        assert invoice_docs.count() == 1
        assert doc in invoice_docs

    def test_multi_document_attachment(self, org, user):
        """Test attaching multiple documents to same target."""
        invoice = Invoice.objects.create(number="INV-2026-002", org=org)

        # Attach invoice PDF
        pdf = SimpleUploadedFile("invoice.pdf", b"PDF content", "application/pdf")
        doc1 = attach_document(
            target=invoice,
            file=pdf,
            document_type="invoice_pdf",
            uploaded_by=user,
        )

        # Attach receipt image
        receipt = SimpleUploadedFile("receipt.jpg", b"JPEG content", "image/jpeg")
        doc2 = attach_document(
            target=invoice,
            file=receipt,
            document_type="receipt_image",
            uploaded_by=user,
        )

        # Attach supporting document
        support = SimpleUploadedFile("support.pdf", b"Support content", "application/pdf")
        doc3 = attach_document(
            target=invoice,
            file=support,
            document_type="supporting_doc",
            uploaded_by=user,
        )

        # Query all documents
        all_docs = Document.objects.for_target(invoice)
        assert all_docs.count() == 3

        # Filter by type
        pdfs = all_docs.filter(content_type="application/pdf")
        assert pdfs.count() == 2

        images = all_docs.filter(document_type="receipt_image")
        assert images.count() == 1

    def test_document_retention_lifecycle(self, org, user):
        """Test document retention policy lifecycle."""
        invoice = Invoice.objects.create(number="INV-2026-003", org=org)

        # Short retention document
        short_file = SimpleUploadedFile("temp.pdf", b"temporary", "application/pdf")
        short_doc = attach_document(
            target=invoice,
            file=short_file,
            document_type="temp_doc",
            uploaded_by=user,
            retention_days=30,
            retention_policy="temporary",
        )

        # Long retention document
        long_file = SimpleUploadedFile("archive.pdf", b"archive", "application/pdf")
        long_doc = attach_document(
            target=invoice,
            file=long_file,
            document_type="archive_doc",
            uploaded_by=user,
            retention_days=365 * 10,
            retention_policy="legal",
        )

        # Permanent document
        perm_file = SimpleUploadedFile("permanent.pdf", b"permanent", "application/pdf")
        perm_doc = attach_document(
            target=invoice,
            file=perm_file,
            document_type="permanent_doc",
            uploaded_by=user,
            retention_days=None,  # Keep forever
        )

        # All should be under retention initially
        assert short_doc.under_retention is True
        assert long_doc.under_retention is True
        assert perm_doc.under_retention is True

        # Check retention end dates
        assert short_doc.retention_ends_at is not None
        assert long_doc.retention_ends_at is not None
        assert perm_doc.retention_ends_at is None  # Permanent

    def test_document_expiration_management(self, org, user):
        """Test document expiration queries."""
        invoice = Invoice.objects.create(number="INV-2026-004", org=org)

        # Expired document
        expired_file = SimpleUploadedFile("expired.pdf", b"expired", "application/pdf")
        expired_doc = attach_document(
            target=invoice,
            file=expired_file,
            document_type="temp_doc",
            uploaded_by=user,
        )
        expired_doc.expires_at = timezone.now() - timedelta(days=1)
        expired_doc.save()

        # Future expiration document
        future_file = SimpleUploadedFile("future.pdf", b"future", "application/pdf")
        future_doc = attach_document(
            target=invoice,
            file=future_file,
            document_type="standard_doc",
            uploaded_by=user,
        )
        future_doc.expires_at = timezone.now() + timedelta(days=365)
        future_doc.save()

        # No expiration document
        no_exp_file = SimpleUploadedFile("noexp.pdf", b"noexp", "application/pdf")
        no_exp_doc = attach_document(
            target=invoice,
            file=no_exp_file,
            document_type="permanent_doc",
            uploaded_by=user,
        )

        # Query expired
        expired_docs = Document.objects.expired()
        assert expired_doc in expired_docs
        assert future_doc not in expired_docs
        assert no_exp_doc not in expired_docs

        # Query not expired
        valid_docs = Document.objects.not_expired()
        assert expired_doc not in valid_docs
        assert future_doc in valid_docs
        assert no_exp_doc in valid_docs


@pytest.mark.django_db
class TestIntegrityVerification:
    """Tests for document integrity verification."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    def test_verify_multiple_documents(self, org, user):
        """Test verifying integrity of multiple documents."""
        invoice = Invoice.objects.create(number="INV-001", org=org)

        # Create multiple documents
        docs = []
        for i in range(5):
            content = f"Document content {i}".encode()
            file = SimpleUploadedFile(f"doc{i}.pdf", content, "application/pdf")
            doc = attach_document(
                target=invoice,
                file=file,
                document_type="test_doc",
                uploaded_by=user,
            )
            docs.append(doc)

        # Verify all documents
        for doc in docs:
            assert verify_document_integrity(doc) is True

    def test_checksum_detects_tampering(self, org, user):
        """Test that checksum verification detects file tampering."""
        invoice = Invoice.objects.create(number="INV-001", org=org)

        content = b"Original sensitive content"
        file = SimpleUploadedFile("sensitive.pdf", content, "application/pdf")
        doc = attach_document(
            target=invoice,
            file=file,
            document_type="sensitive_doc",
            uploaded_by=user,
        )

        # Verify original is valid
        assert verify_document_integrity(doc) is True

        # Simulate tampering by changing checksum
        doc.checksum = "tampered_checksum_value"
        doc.save()

        # Verification should fail
        with pytest.raises(ChecksumMismatchError):
            verify_document_integrity(doc)

    def test_checksum_computation_consistency(self, org, user):
        """Test that checksum computation is consistent."""
        invoice = Invoice.objects.create(number="INV-001", org=org)

        # Same content should produce same checksum
        content = b"Test content for consistency check"
        expected = hashlib.sha256(content).hexdigest()

        file1 = SimpleUploadedFile("doc1.pdf", content, "application/pdf")
        doc1 = attach_document(
            target=invoice,
            file=file1,
            document_type="test_doc",
            uploaded_by=user,
        )

        file2 = SimpleUploadedFile("doc2.pdf", content, "application/pdf")
        doc2 = attach_document(
            target=invoice,
            file=file2,
            document_type="test_doc",
            uploaded_by=user,
        )

        assert doc1.checksum == expected
        assert doc2.checksum == expected
        assert doc1.checksum == doc2.checksum


@pytest.mark.django_db
class TestCrossObjectDocuments:
    """Tests for documents attached to different object types."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    def test_documents_attached_to_different_targets(self, user):
        """Test documents can be attached to different model types."""
        org1 = Organization.objects.create(name="Org 1")
        org2 = Organization.objects.create(name="Org 2")

        invoice1 = Invoice.objects.create(number="INV-001", org=org1)
        invoice2 = Invoice.objects.create(number="INV-002", org=org2)

        # Attach documents to different targets
        file1 = SimpleUploadedFile("doc1.pdf", b"content1", "application/pdf")
        doc1 = attach_document(
            target=org1,
            file=file1,
            document_type="company_doc",
            uploaded_by=user,
        )

        file2 = SimpleUploadedFile("doc2.pdf", b"content2", "application/pdf")
        doc2 = attach_document(
            target=invoice1,
            file=file2,
            document_type="invoice_doc",
            uploaded_by=user,
        )

        file3 = SimpleUploadedFile("doc3.pdf", b"content3", "application/pdf")
        doc3 = attach_document(
            target=invoice2,
            file=file3,
            document_type="invoice_doc",
            uploaded_by=user,
        )

        # Query documents per target
        org_docs = Document.objects.for_target(org1)
        assert org_docs.count() == 1
        assert doc1 in org_docs

        inv1_docs = Document.objects.for_target(invoice1)
        assert inv1_docs.count() == 1
        assert doc2 in inv1_docs

        inv2_docs = Document.objects.for_target(invoice2)
        assert inv2_docs.count() == 1
        assert doc3 in inv2_docs

    def test_total_documents_count(self, user):
        """Test total document count across all targets."""
        org = Organization.objects.create(name="Test Org")
        invoice = Invoice.objects.create(number="INV-001", org=org)

        # Create multiple documents
        for i in range(3):
            file = SimpleUploadedFile(f"org{i}.pdf", f"org{i}".encode(), "application/pdf")
            attach_document(target=org, file=file, document_type="org_doc", uploaded_by=user)

        for i in range(5):
            file = SimpleUploadedFile(f"inv{i}.pdf", f"inv{i}".encode(), "application/pdf")
            attach_document(target=invoice, file=file, document_type="inv_doc", uploaded_by=user)

        # Total count
        assert Document.objects.count() == 8
        assert Document.objects.for_target(org).count() == 3
        assert Document.objects.for_target(invoice).count() == 5
