"""Tests for DocumentAccessLog model and access logging operations."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from tests.models import Organization, Invoice


User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass")


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
        content=b"Test content for access log tests.",
        content_type="application/pdf",
    )


@pytest.mark.django_db
class TestDocumentAccessLogModel:
    """Tests for DocumentAccessLog model."""

    def test_document_access_log_model_exists(self):
        """DocumentAccessLog model should exist."""
        from django_documents.models import DocumentAccessLog

        assert DocumentAccessLog is not None

    def test_document_access_log_has_required_fields(self):
        """DocumentAccessLog should have all required fields."""
        from django_documents.models import DocumentAccessLog

        field_names = [f.name for f in DocumentAccessLog._meta.get_fields()]
        assert "document" in field_names
        assert "version" in field_names
        assert "document_filename" in field_names
        assert "action" in field_names
        assert "actor" in field_names
        assert "ip_address" in field_names
        assert "user_agent" in field_names
        assert "accessed_at" in field_names

    def test_access_action_choices_exist(self):
        """AccessAction choices should exist with correct values."""
        from django_documents.models import AccessAction

        assert AccessAction.VIEW == "view"
        assert AccessAction.DOWNLOAD == "download"
        assert AccessAction.PREVIEW == "preview"
        assert AccessAction.UPLOAD == "upload"
        assert AccessAction.EDIT == "edit"
        assert AccessAction.MOVE == "move"
        assert AccessAction.DELETE == "delete"


@pytest.mark.django_db
class TestLogAccess:
    """Tests for log_access service."""

    def test_log_access_creates_record(self, invoice, sample_file, user):
        """log_access should create a DocumentAccessLog record."""
        from django_documents.models import Document, DocumentAccessLog, AccessAction
        from django_documents.services import log_access

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        log = log_access(
            document=doc,
            action=AccessAction.VIEW,
            actor=user,
        )

        assert log.pk is not None
        assert log.document == doc
        assert log.action == AccessAction.VIEW
        assert log.actor == user
        assert log.document_filename == "test.pdf"

    def test_log_access_captures_filename_snapshot(self, invoice, sample_file, user):
        """log_access should capture filename at time of logging."""
        from django_documents.models import Document, AccessAction
        from django_documents.services import log_access

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="original_name.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        log = log_access(
            document=doc,
            action=AccessAction.VIEW,
            actor=user,
        )

        # Change the document filename
        doc.filename = "new_name.pdf"
        doc.save()

        # Log should still have original filename
        log.refresh_from_db()
        assert log.document_filename == "original_name.pdf"

    def test_log_access_with_version(self, invoice, sample_file, user):
        """log_access should record version when provided."""
        from django_documents.models import Document, DocumentVersion, AccessAction
        from django_documents.services import log_access

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
            blob_path="documents/sha256/ab/cd/test/test.pdf",
            sha256="a" * 64,
            size_bytes=1024,
            mime_type="application/pdf",
            original_filename="test.pdf",
        )

        log = log_access(
            document=doc,
            action=AccessAction.DOWNLOAD,
            actor=user,
            version=version,
        )

        assert log.version == version

    def test_log_access_with_ip_and_user_agent(self, invoice, sample_file, user):
        """log_access should record IP and user agent when provided."""
        from django_documents.models import Document, AccessAction
        from django_documents.services import log_access

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        log = log_access(
            document=doc,
            action=AccessAction.VIEW,
            actor=user,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Test Browser",
        )

        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "Mozilla/5.0 Test Browser"

    def test_log_access_without_actor(self, invoice, sample_file):
        """log_access should work without an actor (anonymous access)."""
        from django_documents.models import Document, AccessAction
        from django_documents.services import log_access

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        log = log_access(
            document=doc,
            action=AccessAction.PREVIEW,
            actor=None,
        )

        assert log.pk is not None
        assert log.actor is None


@pytest.mark.django_db
class TestAccessLogImmutability:
    """Tests for DocumentAccessLog immutability."""

    def test_access_log_immutable_after_creation(self, invoice, sample_file, user):
        """DocumentAccessLog should be immutable after creation."""
        from django_documents.models import Document, AccessAction
        from django_documents.services import log_access

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        log = log_access(
            document=doc,
            action=AccessAction.VIEW,
            actor=user,
        )

        # Attempt to modify should raise
        log.action = AccessAction.DOWNLOAD
        with pytest.raises(ValueError, match="immutable"):
            log.save()


@pytest.mark.django_db
class TestAccessLogAfterDocumentDelete:
    """Tests for access log behavior after document deletion."""

    def test_log_preserved_after_document_hard_delete(self, invoice, sample_file, user):
        """Access log should be preserved after document is hard deleted."""
        from django_documents.models import Document, DocumentAccessLog, AccessAction
        from django_documents.services import log_access

        doc = Document.objects.create(
            target=invoice,
            file=sample_file,
            filename="test.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )
        doc_id = doc.pk

        log = log_access(
            document=doc,
            action=AccessAction.VIEW,
            actor=user,
        )
        log_id = log.pk

        # Hard delete the document (actually removes from DB)
        doc.hard_delete()

        # Log should still exist with filename snapshot
        log = DocumentAccessLog.objects.get(pk=log_id)
        assert log.document is None  # FK set to null
        assert log.document_filename == "test.pdf"  # Snapshot preserved
