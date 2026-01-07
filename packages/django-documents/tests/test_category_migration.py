"""Tests for category data migration."""

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


@pytest.mark.django_db
class TestCategoryDetection:
    """Tests for category detection from content_type."""

    def test_image_content_type_sets_image_category(self, invoice):
        """Documents with image/* content type should have image category."""
        from django_documents.models import Document, DocumentCategory

        file = SimpleUploadedFile("photo.jpg", b"fake image", "image/jpeg")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="photo.jpg",
            content_type="image/jpeg",
            document_type="photo",
        )

        # Manually set category to document to simulate pre-migration state
        Document.objects.filter(pk=doc.pk).update(category="document")
        doc.refresh_from_db()
        assert doc.category == "document"

        # Now apply the category detection logic
        Document.objects.filter(content_type__startswith="image/").update(category="image")
        doc.refresh_from_db()
        assert doc.category == DocumentCategory.IMAGE

    def test_video_content_type_sets_video_category(self, invoice):
        """Documents with video/* content type should have video category."""
        from django_documents.models import Document, DocumentCategory

        file = SimpleUploadedFile("video.mp4", b"fake video", "video/mp4")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="video.mp4",
            content_type="video/mp4",
            document_type="video",
        )

        # Manually set category to document
        Document.objects.filter(pk=doc.pk).update(category="document")
        doc.refresh_from_db()

        # Apply detection
        Document.objects.filter(content_type__startswith="video/").update(category="video")
        doc.refresh_from_db()
        assert doc.category == DocumentCategory.VIDEO

    def test_audio_content_type_sets_audio_category(self, invoice):
        """Documents with audio/* content type should have audio category."""
        from django_documents.models import Document, DocumentCategory

        file = SimpleUploadedFile("audio.mp3", b"fake audio", "audio/mpeg")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="audio.mp3",
            content_type="audio/mpeg",
            document_type="audio",
        )

        # Manually set category to document
        Document.objects.filter(pk=doc.pk).update(category="document")
        doc.refresh_from_db()

        # Apply detection
        Document.objects.filter(content_type__startswith="audio/").update(category="audio")
        doc.refresh_from_db()
        assert doc.category == DocumentCategory.AUDIO

    def test_pdf_content_type_keeps_document_category(self, invoice):
        """Documents with application/pdf should keep document category."""
        from django_documents.models import Document, DocumentCategory

        file = SimpleUploadedFile("doc.pdf", b"fake pdf", "application/pdf")
        doc = Document.objects.create(
            target=invoice,
            file=file,
            filename="doc.pdf",
            content_type="application/pdf",
            document_type="document",
        )

        # Category should be document (default)
        assert doc.category == DocumentCategory.DOCUMENT

        # Run all detection updates - PDF shouldn't be affected
        Document.objects.filter(content_type__startswith="image/").update(category="image")
        Document.objects.filter(content_type__startswith="video/").update(category="video")
        Document.objects.filter(content_type__startswith="audio/").update(category="audio")

        doc.refresh_from_db()
        assert doc.category == DocumentCategory.DOCUMENT

    def test_various_image_types(self, invoice):
        """Various image content types should all be detected."""
        from django_documents.models import Document, DocumentCategory

        image_types = [
            ("image/jpeg", "photo.jpg"),
            ("image/png", "image.png"),
            ("image/gif", "animation.gif"),
            ("image/webp", "modern.webp"),
            ("image/svg+xml", "vector.svg"),
        ]

        for content_type, filename in image_types:
            file = SimpleUploadedFile(filename, b"fake", content_type)
            doc = Document.objects.create(
                target=invoice,
                file=file,
                filename=filename,
                content_type=content_type,
                document_type="image",
            )
            # Reset to document
            Document.objects.filter(pk=doc.pk).update(category="document")

        # Apply detection
        Document.objects.filter(content_type__startswith="image/").update(category="image")

        # All should be image category now
        for content_type, filename in image_types:
            doc = Document.objects.get(filename=filename)
            assert doc.category == DocumentCategory.IMAGE, f"Failed for {content_type}"
