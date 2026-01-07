"""Tests for verify_documents management command."""

import hashlib
import os
import json

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from io import StringIO

from tests.models import Organization, Invoice


@pytest.fixture
def org(db):
    """Create a test organization."""
    return Organization.objects.create(name="Test Org")


@pytest.fixture
def invoice(org):
    """Create a test invoice."""
    return Invoice.objects.create(number="INV-001", org=org)


@pytest.fixture
def sample_content():
    """Sample file content for testing."""
    return b"This is test content for verify command tests."


@pytest.fixture
def sample_file(sample_content):
    """Create a sample uploaded file."""
    return SimpleUploadedFile(
        name="test_document.pdf",
        content=sample_content,
        content_type="application/pdf",
    )


def create_version_with_blob(doc, content, filename="test.pdf"):
    """Helper to create a DocumentVersion with actual blob on disk."""
    from django_documents.models import DocumentVersion

    sha256 = hashlib.sha256(content).hexdigest()
    blob_path = f"documents/sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}/{filename}"
    full_path = os.path.join(settings.MEDIA_ROOT, blob_path)

    # Create directory and write file
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(content)

    # Create version record
    version = DocumentVersion.objects.create(
        document=doc,
        storage_backend="filesystem",
        blob_path=blob_path,
        sha256=sha256,
        size_bytes=len(content),
        mime_type="application/pdf",
        original_filename=filename,
    )

    return version


@pytest.mark.django_db
class TestVerifyDocumentsCommand:
    """Tests for verify_documents management command."""

    def test_command_exists(self):
        """verify_documents command should exist."""
        from django.core.management import get_commands

        assert "verify_documents" in get_commands()

    def test_verify_documents_ok_count(self, invoice, sample_content):
        """Command should report OK count for healthy files."""
        from django_documents.models import Document

        # Create document with version
        file = SimpleUploadedFile("test.pdf", sample_content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        create_version_with_blob(doc, sample_content, "test.pdf")

        # Run command
        out = StringIO()
        call_command("verify_documents", stdout=out)
        output = out.getvalue()

        assert "OK: 1" in output or "ok: 1" in output.lower()

    def test_verify_documents_missing_count(self, invoice, sample_content):
        """Command should report MISSING count for missing blobs."""
        from django_documents.models import Document, DocumentVersion

        # Create document with version pointing to non-existent file
        file = SimpleUploadedFile("test.pdf", sample_content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        DocumentVersion.objects.create(
            document=doc,
            storage_backend="filesystem",
            blob_path="documents/sha256/xx/yy/nonexistent/missing.pdf",
            sha256="a" * 64,
            size_bytes=1024,
            mime_type="application/pdf",
            original_filename="missing.pdf",
        )

        # Run command
        out = StringIO()
        call_command("verify_documents", stdout=out)
        output = out.getvalue()

        assert "MISSING: 1" in output or "missing: 1" in output.lower()

    def test_verify_documents_corrupt_count(self, invoice, sample_content):
        """Command should report CORRUPT count for hash mismatches."""
        from django_documents.models import Document, DocumentVersion

        # Create document with version
        file = SimpleUploadedFile("test.pdf", sample_content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        # Create version with wrong hash
        sha256 = hashlib.sha256(sample_content).hexdigest()
        blob_path = f"documents/sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}/corrupt.pdf"
        full_path = os.path.join(settings.MEDIA_ROOT, blob_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(sample_content)

        # Create version with WRONG hash
        DocumentVersion.objects.create(
            document=doc,
            storage_backend="filesystem",
            blob_path=blob_path,
            sha256="b" * 64,  # Wrong hash!
            size_bytes=len(sample_content),
            mime_type="application/pdf",
            original_filename="corrupt.pdf",
        )

        # Run command
        out = StringIO()
        call_command("verify_documents", stdout=out)
        output = out.getvalue()

        assert "CORRUPT: 1" in output or "corrupt: 1" in output.lower()

    def test_verify_documents_sample_flag(self, invoice, sample_content):
        """Command should limit scan with --sample flag."""
        from django_documents.models import Document

        # Create multiple documents
        for i in range(5):
            content = f"Content {i}".encode()
            file = SimpleUploadedFile(f"test{i}.pdf", content, "application/pdf")
            doc = Document.objects.create(
                target=invoice,
                file=file,
                filename=f"test{i}.pdf",
                content_type="application/pdf",
                document_type="invoice_pdf",
            )
            create_version_with_blob(doc, content, f"test{i}.pdf")

        # Run command with sample=2
        out = StringIO()
        call_command("verify_documents", "--sample=2", stdout=out)
        output = out.getvalue()

        # Should show total scanned is 2
        assert "scanned: 2" in output.lower() or "Scanned: 2" in output

    def test_verify_documents_json_output(self, invoice, sample_content):
        """Command should support JSON output format."""
        from django_documents.models import Document

        # Create document with version
        file = SimpleUploadedFile("test.pdf", sample_content, "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        create_version_with_blob(doc, sample_content, "test.pdf")

        # Run command with JSON output
        out = StringIO()
        call_command("verify_documents", "--format=json", stdout=out)
        output = out.getvalue()

        # Should be valid JSON
        data = json.loads(output)
        assert "ok" in data
        assert "missing" in data
        assert "corrupt" in data
        assert data["ok"] == 1

    def test_verify_documents_no_versions(self, invoice, sample_content):
        """Command should handle documents without versions gracefully."""
        from django_documents.models import Document

        # Create document WITHOUT version
        file = SimpleUploadedFile("test.pdf", sample_content, "application/pdf")
        Document.objects.create(
            target=invoice,
            file=file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        # Run command - should not error
        out = StringIO()
        call_command("verify_documents", stdout=out)
        output = out.getvalue()

        # Should complete without error
        assert "OK:" in output or "ok:" in output.lower() or "Scanned:" in output
