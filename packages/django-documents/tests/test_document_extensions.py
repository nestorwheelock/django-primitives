"""Tests for Document model extensions (folder, category)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

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
def sample_file():
    """Create a sample uploaded file."""
    return SimpleUploadedFile(
        name="test_document.pdf",
        content=b"Test content for document extension tests.",
        content_type="application/pdf",
    )


@pytest.mark.django_db
class TestDocumentCategoryField:
    """Tests for Document.category field."""

    def test_document_has_category_field(self):
        """Document should have category field."""
        from django_documents.models import Document

        field_names = [f.name for f in Document._meta.get_fields()]
        assert "category" in field_names

    def test_document_category_choices_exist(self):
        """DocumentCategory choices should exist with correct values."""
        from django_documents.models import DocumentCategory

        assert DocumentCategory.DOCUMENT == "document"
        assert DocumentCategory.IMAGE == "image"
        assert DocumentCategory.VIDEO == "video"
        assert DocumentCategory.AUDIO == "audio"
        assert DocumentCategory.OTHER == "other"

    def test_document_category_defaults_to_document(self, invoice, sample_file):
        """Document.category should default to 'document'."""
        from django_documents.models import Document, DocumentCategory

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        assert doc.category == DocumentCategory.DOCUMENT

    def test_document_category_can_be_set(self, invoice, sample_file):
        """Document.category can be set to any valid category."""
        from django_documents.models import Document, DocumentCategory

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="photo.jpg",
            content_type="image/jpeg",
            document_type="photo",
            category=DocumentCategory.IMAGE,
        )

        assert doc.category == DocumentCategory.IMAGE


@pytest.mark.django_db
class TestDocumentFolderField:
    """Tests for Document.folder field."""

    def test_document_has_folder_field(self):
        """Document should have folder field."""
        from django_documents.models import Document

        field_names = [f.name for f in Document._meta.get_fields()]
        assert "folder" in field_names

    def test_document_folder_is_nullable(self, invoice, sample_file):
        """Document.folder should be nullable."""
        from django_documents.models import Document

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        assert doc.folder is None

    def test_document_can_be_in_folder(self, invoice, sample_file):
        """Document can be assigned to a folder."""
        from django_documents.models import Document
        from django_documents.services import create_folder

        folder = create_folder(name="Invoices", actor=None)

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            folder=folder,
        )

        assert doc.folder == folder


@pytest.mark.django_db
class TestDocumentDualMode:
    """Tests for Document dual mode (folder and/or target)."""

    def test_document_in_folder_only(self, sample_file):
        """Document can exist in folder without being attached to target."""
        from django_documents.models import Document
        from django_documents.services import create_folder

        folder = create_folder(name="General Documents", actor=None)

        # Create document with folder but no target
        doc = Document.objects.create(
            file=sample_file,
            filename="standalone.pdf",
            content_type="application/pdf",
            document_type="general",
            folder=folder,
            # No target
        )

        assert doc.folder == folder
        assert doc.target is None

    def test_document_attached_only(self, invoice, sample_file):
        """Document can be attached to target without being in a folder."""
        from django_documents.models import Document

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            # No folder
        )

        assert doc.target == invoice
        assert doc.folder is None

    def test_document_dual_mode(self, invoice, sample_file):
        """Document can be both in a folder AND attached to target."""
        from django_documents.models import Document
        from django_documents.services import create_folder

        folder = create_folder(name="Invoice Archives", actor=None)

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            folder=folder,
        )

        assert doc.target == invoice
        assert doc.folder == folder


@pytest.mark.django_db
class TestMoveDocument:
    """Tests for moving documents between folders."""

    def test_move_document_between_folders(self, invoice, sample_file):
        """Document can be moved between folders."""
        from django_documents.models import Document
        from django_documents.services import create_folder, move_document

        folder1 = create_folder(name="Folder1", actor=None)
        folder2 = create_folder(name="Folder2", actor=None)

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            folder=folder1,
        )

        moved = move_document(document=doc, destination=folder2, actor=None)

        assert moved.folder == folder2

    def test_move_document_to_root(self, invoice, sample_file):
        """Document can be moved to root (no folder)."""
        from django_documents.models import Document
        from django_documents.services import create_folder, move_document

        folder = create_folder(name="Folder1", actor=None)

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
            folder=folder,
        )

        moved = move_document(document=doc, destination=None, actor=None)

        assert moved.folder is None


@pytest.mark.django_db
class TestDocumentTargetOptional:
    """Tests for optional target fields."""

    def test_target_content_type_nullable(self):
        """target_content_type should be nullable."""
        from django_documents.models import Document

        field = Document._meta.get_field("target_content_type")
        assert field.null is True

    def test_target_id_allows_blank(self):
        """target_id should allow blank."""
        from django_documents.models import Document

        field = Document._meta.get_field("target_id")
        assert field.blank is True
