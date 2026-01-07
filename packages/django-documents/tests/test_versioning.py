"""Tests for DocumentVersion and content-addressed storage."""

import hashlib
import os
import tempfile

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from tests.models import Organization, Invoice


@pytest.fixture
def org():
    """Create a test organization."""
    return Organization.objects.create(name="Test Org")


@pytest.fixture
def invoice(org):
    """Create a test invoice."""
    return Invoice.objects.create(number="INV-001", org=org)


@pytest.fixture
def sample_content():
    """Sample file content for testing."""
    return b"This is test content for versioning tests."


@pytest.fixture
def sample_file(sample_content):
    """Create a sample uploaded file."""
    return SimpleUploadedFile(
        name="test_document.pdf",
        content=sample_content,
        content_type="application/pdf",
    )


@pytest.mark.django_db
class TestDocumentVersionModel:
    """Tests for DocumentVersion model."""

    def test_document_version_model_exists(self):
        """DocumentVersion model should exist."""
        from django_documents.models import DocumentVersion

        assert DocumentVersion is not None

    def test_document_version_has_required_fields(self):
        """DocumentVersion should have all required fields."""
        from django_documents.models import DocumentVersion

        # Check field names exist
        field_names = [f.name for f in DocumentVersion._meta.get_fields()]
        assert "document" in field_names
        assert "storage_backend" in field_names
        assert "blob_path" in field_names
        assert "sha256" in field_names
        assert "size_bytes" in field_names
        assert "mime_type" in field_names
        assert "original_filename" in field_names
        assert "metadata" in field_names
        assert "created_by" in field_names

    def test_document_version_immutable_after_creation(self, invoice, sample_file):
        """DocumentVersion should be immutable after creation."""
        from django_documents.models import Document, DocumentVersion

        # First create a document
        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        # Create a version
        version = DocumentVersion.objects.create(
            document=doc,
            storage_backend="filesystem",
            blob_path="documents/sha256/ab/cd/abcd1234/test.pdf",
            sha256="a" * 64,
            size_bytes=1024,
            mime_type="application/pdf",
            original_filename="test.pdf",
        )

        # Attempt to modify should raise
        version.size_bytes = 2048
        with pytest.raises(ValueError, match="immutable"):
            version.save()

    def test_document_version_storage_backend_defaults_filesystem(self, invoice, sample_file):
        """DocumentVersion.storage_backend should default to 'filesystem'."""
        from django_documents.models import Document, DocumentVersion

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        version = DocumentVersion.objects.create(
            document=doc,
            blob_path="documents/sha256/ab/cd/abcd1234/test.pdf",
            sha256="b" * 64,
            size_bytes=1024,
            mime_type="application/pdf",
            original_filename="test.pdf",
        )

        assert version.storage_backend == "filesystem"


@pytest.mark.django_db
class TestDocumentCurrentVersion:
    """Tests for Document.current_version FK."""

    def test_document_has_current_version_field(self):
        """Document should have current_version FK."""
        from django_documents.models import Document

        field_names = [f.name for f in Document._meta.get_fields()]
        assert "current_version" in field_names

    def test_document_current_version_nullable(self, invoice, sample_file):
        """Document.current_version should be nullable."""
        from django_documents.models import Document

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        # current_version can be null
        assert doc.current_version is None

    def test_document_current_version_can_be_set(self, invoice, sample_file):
        """Document.current_version can be set to a DocumentVersion."""
        from django_documents.models import Document, DocumentVersion

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        version = DocumentVersion.objects.create(
            document=doc,
            storage_backend="filesystem",
            blob_path="documents/sha256/ab/cd/abcd1234/test.pdf",
            sha256="c" * 64,
            size_bytes=1024,
            mime_type="application/pdf",
            original_filename="test.pdf",
        )

        doc.current_version = version
        doc.save()

        doc.refresh_from_db()
        assert doc.current_version == version


@pytest.mark.django_db
class TestContentAddressedStorage:
    """Tests for content-addressed storage helpers."""

    def test_compute_sha256_returns_hex_digest(self, sample_content):
        """compute_sha256() should return hex digest of file content."""
        from django_documents.services import compute_sha256
        from io import BytesIO

        file_obj = BytesIO(sample_content)
        result = compute_sha256(file_obj)

        expected = hashlib.sha256(sample_content).hexdigest()
        assert result == expected
        assert len(result) == 64  # SHA-256 is 64 hex chars

    def test_compute_sha256_resets_file_position(self, sample_content):
        """compute_sha256() should reset file position after reading."""
        from django_documents.services import compute_sha256
        from io import BytesIO

        file_obj = BytesIO(sample_content)
        compute_sha256(file_obj)

        # File position should be reset to start
        assert file_obj.tell() == 0

    def test_content_addressed_path_uses_hash_layout(self):
        """content_addressed_path() should return path with hash-based layout."""
        from django_documents.services import content_addressed_path

        sha256 = "abcdef1234567890" + "0" * 48  # 64 chars
        filename = "test_document.pdf"

        result = content_addressed_path(sha256, filename)

        # Should follow: documents/sha256/<aa>/<bb>/<fullhash>/<filename>
        assert "documents/sha256/ab/cd" in result
        assert sha256 in result
        assert filename in result

    def test_content_addressed_path_is_relative(self):
        """content_addressed_path() should return relative path (no leading /)."""
        from django_documents.services import content_addressed_path

        sha256 = "1234567890abcdef" + "0" * 48
        filename = "file.pdf"

        result = content_addressed_path(sha256, filename)

        assert not result.startswith("/")


@pytest.mark.django_db
class TestVerifyBlob:
    """Tests for verify_blob() function."""

    def test_verify_blob_ok_when_file_exists_and_hash_matches(self, invoice, sample_file, sample_content):
        """verify_blob() should return 'ok' when file exists and hash matches."""
        from django_documents.models import Document, DocumentVersion
        from django_documents.services import verify_blob

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        # Create a version pointing to actual file
        sha256 = hashlib.sha256(sample_content).hexdigest()

        # Write file to temp location
        blob_path = f"documents/sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}/test.pdf"
        full_path = os.path.join(settings.MEDIA_ROOT, blob_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(sample_content)

        version = DocumentVersion.objects.create(
            document=doc,
            storage_backend="filesystem",
            blob_path=blob_path,
            sha256=sha256,
            size_bytes=len(sample_content),
            mime_type="application/pdf",
            original_filename="test.pdf",
        )

        result = verify_blob(version)
        assert result == "ok"

    def test_verify_blob_missing_when_file_not_found(self, invoice, sample_file):
        """verify_blob() should return 'missing' when file doesn't exist."""
        from django_documents.models import Document, DocumentVersion
        from django_documents.services import verify_blob

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        # Create version pointing to non-existent file
        version = DocumentVersion.objects.create(
            document=doc,
            storage_backend="filesystem",
            blob_path="documents/sha256/xx/yy/nonexistent/file.pdf",
            sha256="d" * 64,
            size_bytes=1024,
            mime_type="application/pdf",
            original_filename="file.pdf",
        )

        result = verify_blob(version)
        assert result == "missing"

    def test_verify_blob_corrupt_when_hash_mismatch(self, invoice, sample_file, sample_content):
        """verify_blob() should return 'corrupt' when file exists but hash doesn't match."""
        from django_documents.models import Document, DocumentVersion
        from django_documents.services import verify_blob

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        # Write file with one content
        blob_path = "documents/sha256/ee/ff/corrupt_test/test.pdf"
        full_path = os.path.join(settings.MEDIA_ROOT, blob_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(sample_content)

        # But record different hash
        wrong_hash = "e" * 64

        version = DocumentVersion.objects.create(
            document=doc,
            storage_backend="filesystem",
            blob_path=blob_path,
            sha256=wrong_hash,
            size_bytes=len(sample_content),
            mime_type="application/pdf",
            original_filename="test.pdf",
        )

        result = verify_blob(version)
        assert result == "corrupt"
