"""Tests for media_service.py - image/video processing and attachments."""
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.contenttypes.models import ContentType

from django_documents.models import (
    Document,
    MediaAsset,
    MediaRendition,
    Attachment,
    MediaKind,
    MediaProcessingStatus,
    RenditionRole,
    AttachmentPurpose,
)
from django_documents.media_service import (
    process_image_upload,
    generate_renditions,
    extract_dimensions,
    attach_media,
    get_attachments,
    reorder_attachments,
    set_primary_attachment,
)
from tests.models import Organization, Invoice


def create_test_image(width=100, height=100, format="PNG"):
    """Create a test image file."""
    img = Image.new("RGB", (width, height), color="red")
    buffer = BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer


@pytest.mark.django_db
class TestProcessImageUpload:
    """Test suite for process_image_upload function."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def image_document(self, org):
        """Create a document with an actual image file."""
        img_data = create_test_image(1920, 1080)
        uploaded = SimpleUploadedFile(
            name="photo.png",
            content=img_data.read(),
            content_type="image/png",
        )
        return Document.objects.create(
            target=org,
            file=uploaded,
            filename="photo.png",
            content_type="image/png",
            document_type="photo",
            category="image",
        )

    def test_process_image_creates_media_asset(self, image_document):
        """process_image_upload creates a MediaAsset for the document."""
        asset = process_image_upload(image_document)
        assert asset is not None
        assert asset.document == image_document
        assert asset.kind == MediaKind.IMAGE

    def test_process_image_extracts_dimensions(self, image_document):
        """process_image_upload extracts width and height."""
        asset = process_image_upload(image_document)
        assert asset.width == 1920
        assert asset.height == 1080

    def test_process_image_sets_status_completed(self, image_document):
        """process_image_upload sets status to COMPLETED on success."""
        asset = process_image_upload(image_document)
        assert asset.status == MediaProcessingStatus.COMPLETED

    def test_process_image_returns_existing_asset(self, image_document):
        """process_image_upload returns existing asset if already processed."""
        asset1 = process_image_upload(image_document)
        asset2 = process_image_upload(image_document)
        assert asset1.pk == asset2.pk

    def test_process_image_handles_invalid_file(self, org):
        """process_image_upload handles non-image files gracefully."""
        uploaded = SimpleUploadedFile(
            name="not_image.txt",
            content=b"not an image",
            content_type="text/plain",
        )
        doc = Document.objects.create(
            target=org,
            file=uploaded,
            filename="not_image.txt",
            content_type="text/plain",
            document_type="text",
        )
        asset = process_image_upload(doc)
        assert asset.status == MediaProcessingStatus.FAILED


@pytest.mark.django_db
class TestExtractDimensions:
    """Test suite for extract_dimensions function."""

    def test_extract_dimensions_from_png(self):
        """extract_dimensions returns width, height for PNG."""
        img_data = create_test_image(640, 480, "PNG")
        width, height = extract_dimensions(img_data)
        assert width == 640
        assert height == 480

    def test_extract_dimensions_from_jpeg(self):
        """extract_dimensions returns width, height for JPEG."""
        img_data = create_test_image(800, 600, "JPEG")
        width, height = extract_dimensions(img_data)
        assert width == 800
        assert height == 600

    def test_extract_dimensions_resets_file_position(self):
        """extract_dimensions resets file position after reading."""
        img_data = create_test_image(100, 100)
        extract_dimensions(img_data)
        assert img_data.tell() == 0

    def test_extract_dimensions_returns_none_for_invalid(self):
        """extract_dimensions returns None, None for invalid files."""
        invalid_data = BytesIO(b"not an image")
        width, height = extract_dimensions(invalid_data)
        assert width is None
        assert height is None


@pytest.mark.django_db
class TestGenerateRenditions:
    """Test suite for generate_renditions function."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def media_asset(self, org):
        """Create a media asset with a real image."""
        img_data = create_test_image(1920, 1080)
        uploaded = SimpleUploadedFile(
            name="photo.png",
            content=img_data.read(),
            content_type="image/png",
        )
        doc = Document.objects.create(
            target=org,
            file=uploaded,
            filename="photo.png",
            content_type="image/png",
            document_type="photo",
            category="image",
        )
        return MediaAsset.objects.create(
            document=doc,
            kind=MediaKind.IMAGE,
            width=1920,
            height=1080,
            status=MediaProcessingStatus.COMPLETED,
        )

    def test_generate_renditions_creates_thumb(self, media_asset):
        """generate_renditions creates a thumbnail rendition."""
        renditions = generate_renditions(media_asset, roles=[RenditionRole.THUMB])
        assert len(renditions) == 1
        assert renditions[0].role == RenditionRole.THUMB
        assert renditions[0].width <= 150

    def test_generate_renditions_creates_multiple(self, media_asset):
        """generate_renditions creates multiple renditions."""
        roles = [RenditionRole.THUMB, RenditionRole.SMALL, RenditionRole.MEDIUM]
        renditions = generate_renditions(media_asset, roles=roles)
        assert len(renditions) == 3
        created_roles = {r.role for r in renditions}
        assert created_roles == {RenditionRole.THUMB, RenditionRole.SMALL, RenditionRole.MEDIUM}

    def test_generate_renditions_default_roles(self, media_asset):
        """generate_renditions uses default roles if not specified."""
        renditions = generate_renditions(media_asset)
        assert len(renditions) >= 3  # thumb, small, medium

    def test_generate_renditions_maintains_aspect_ratio(self, media_asset):
        """generate_renditions maintains aspect ratio."""
        renditions = generate_renditions(media_asset, roles=[RenditionRole.THUMB])
        rendition = renditions[0]
        original_ratio = 1920 / 1080
        rendition_ratio = rendition.width / rendition.height
        assert abs(original_ratio - rendition_ratio) < 0.01

    def test_generate_renditions_skips_existing(self, media_asset):
        """generate_renditions skips already existing renditions."""
        # Create first
        renditions1 = generate_renditions(media_asset, roles=[RenditionRole.THUMB])
        # Try to create again
        renditions2 = generate_renditions(media_asset, roles=[RenditionRole.THUMB])
        assert len(renditions2) == 1
        assert renditions1[0].pk == renditions2[0].pk

    def test_generate_renditions_sets_file_size(self, media_asset):
        """generate_renditions sets file_size on each rendition."""
        renditions = generate_renditions(media_asset, roles=[RenditionRole.THUMB])
        assert renditions[0].file_size > 0

    def test_generate_renditions_skips_larger_than_original(self, org):
        """generate_renditions skips roles larger than original."""
        img_data = create_test_image(100, 100)
        uploaded = SimpleUploadedFile(
            name="small.png",
            content=img_data.read(),
            content_type="image/png",
        )
        doc = Document.objects.create(
            target=org,
            file=uploaded,
            filename="small.png",
            content_type="image/png",
            document_type="photo",
        )
        asset = MediaAsset.objects.create(
            document=doc,
            kind=MediaKind.IMAGE,
            width=100,
            height=100,
            status=MediaProcessingStatus.COMPLETED,
        )
        # LARGE role is 1280px, bigger than our 100px image
        renditions = generate_renditions(asset, roles=[RenditionRole.LARGE])
        assert len(renditions) == 0


@pytest.mark.django_db
class TestAttachMedia:
    """Test suite for attach_media function."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        return Invoice.objects.create(number="INV-001", org=org)

    @pytest.fixture
    def document(self, org):
        img_data = create_test_image(100, 100)
        uploaded = SimpleUploadedFile(
            name="photo.png",
            content=img_data.read(),
            content_type="image/png",
        )
        return Document.objects.create(
            target=org,
            file=uploaded,
            filename="photo.png",
            content_type="image/png",
            document_type="photo",
        )

    def test_attach_media_creates_attachment(self, document, invoice):
        """attach_media creates an Attachment linking document to target."""
        attachment = attach_media(
            document=document,
            target=invoice,
            purpose=AttachmentPurpose.GALLERY,
        )
        assert attachment is not None
        assert attachment.document == document
        assert attachment.content_object == invoice
        assert attachment.purpose == AttachmentPurpose.GALLERY

    def test_attach_media_with_caption(self, document, invoice):
        """attach_media sets caption."""
        attachment = attach_media(
            document=document,
            target=invoice,
            purpose=AttachmentPurpose.GALLERY,
            caption="Test caption",
        )
        assert attachment.caption == "Test caption"

    def test_attach_media_with_sort_order(self, document, invoice):
        """attach_media sets sort_order."""
        attachment = attach_media(
            document=document,
            target=invoice,
            purpose=AttachmentPurpose.GALLERY,
            sort_order=5,
        )
        assert attachment.sort_order == 5

    def test_attach_media_with_alt_text(self, document, invoice):
        """attach_media sets alt_text."""
        attachment = attach_media(
            document=document,
            target=invoice,
            purpose=AttachmentPurpose.GALLERY,
            alt_text="Alt text here",
        )
        assert attachment.alt_text == "Alt text here"

    def test_attach_media_returns_existing(self, document, invoice):
        """attach_media returns existing attachment if already exists."""
        a1 = attach_media(document, invoice, AttachmentPurpose.GALLERY)
        a2 = attach_media(document, invoice, AttachmentPurpose.GALLERY)
        assert a1.pk == a2.pk


@pytest.mark.django_db
class TestGetAttachments:
    """Test suite for get_attachments function."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        return Invoice.objects.create(number="INV-001", org=org)

    def test_get_attachments_returns_all_for_target(self, org, invoice):
        """get_attachments returns all attachments for a target."""
        # Create documents
        docs = []
        for i in range(3):
            img_data = create_test_image(100, 100)
            uploaded = SimpleUploadedFile(
                name=f"photo{i}.png",
                content=img_data.read(),
                content_type="image/png",
            )
            doc = Document.objects.create(
                target=org,
                file=uploaded,
                filename=f"photo{i}.png",
                content_type="image/png",
                document_type="photo",
            )
            docs.append(doc)

        # Attach to invoice
        for i, doc in enumerate(docs):
            attach_media(doc, invoice, AttachmentPurpose.GALLERY, sort_order=i)

        attachments = get_attachments(invoice)
        assert attachments.count() == 3

    def test_get_attachments_filters_by_purpose(self, org, invoice):
        """get_attachments can filter by purpose."""
        img_data = create_test_image(100, 100)
        doc1 = Document.objects.create(
            target=org,
            file=SimpleUploadedFile("1.png", img_data.read(), "image/png"),
            filename="1.png",
            content_type="image/png",
            document_type="photo",
        )
        img_data2 = create_test_image(100, 100)
        doc2 = Document.objects.create(
            target=org,
            file=SimpleUploadedFile("2.png", img_data2.read(), "image/png"),
            filename="2.png",
            content_type="image/png",
            document_type="photo",
        )

        attach_media(doc1, invoice, AttachmentPurpose.GALLERY)
        attach_media(doc2, invoice, AttachmentPurpose.COVER)

        gallery = get_attachments(invoice, purpose=AttachmentPurpose.GALLERY)
        assert gallery.count() == 1

    def test_get_attachments_ordered_by_sort_order(self, org, invoice):
        """get_attachments returns attachments ordered by sort_order."""
        docs = []
        for i in range(3):
            img_data = create_test_image(100, 100)
            doc = Document.objects.create(
                target=org,
                file=SimpleUploadedFile(f"{i}.png", img_data.read(), "image/png"),
                filename=f"{i}.png",
                content_type="image/png",
                document_type="photo",
            )
            docs.append(doc)

        # Attach in reverse order
        attach_media(docs[0], invoice, AttachmentPurpose.GALLERY, sort_order=2)
        attach_media(docs[1], invoice, AttachmentPurpose.GALLERY, sort_order=0)
        attach_media(docs[2], invoice, AttachmentPurpose.GALLERY, sort_order=1)

        attachments = list(get_attachments(invoice))
        assert attachments[0].sort_order == 0
        assert attachments[1].sort_order == 1
        assert attachments[2].sort_order == 2


@pytest.mark.django_db
class TestReorderAttachments:
    """Test suite for reorder_attachments function."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        return Invoice.objects.create(number="INV-001", org=org)

    def test_reorder_attachments_updates_sort_order(self, org, invoice):
        """reorder_attachments updates sort_order based on list order."""
        docs = []
        attachments = []
        for i in range(3):
            img_data = create_test_image(100, 100)
            doc = Document.objects.create(
                target=org,
                file=SimpleUploadedFile(f"{i}.png", img_data.read(), "image/png"),
                filename=f"{i}.png",
                content_type="image/png",
                document_type="photo",
            )
            docs.append(doc)
            a = attach_media(doc, invoice, AttachmentPurpose.GALLERY, sort_order=i)
            attachments.append(a)

        # Reorder: move last to first
        new_order = [attachments[2].pk, attachments[0].pk, attachments[1].pk]
        reorder_attachments(invoice, AttachmentPurpose.GALLERY, new_order)

        # Refresh and check
        attachments[0].refresh_from_db()
        attachments[1].refresh_from_db()
        attachments[2].refresh_from_db()

        assert attachments[2].sort_order == 0
        assert attachments[0].sort_order == 1
        assert attachments[1].sort_order == 2


@pytest.mark.django_db
class TestSetPrimaryAttachment:
    """Test suite for set_primary_attachment function."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        return Invoice.objects.create(number="INV-001", org=org)

    def test_set_primary_attachment_marks_as_primary(self, org, invoice):
        """set_primary_attachment sets is_primary=True."""
        img_data = create_test_image(100, 100)
        doc = Document.objects.create(
            target=org,
            file=SimpleUploadedFile("1.png", img_data.read(), "image/png"),
            filename="1.png",
            content_type="image/png",
            document_type="photo",
        )
        attachment = attach_media(doc, invoice, AttachmentPurpose.GALLERY)

        set_primary_attachment(attachment)

        attachment.refresh_from_db()
        assert attachment.is_primary is True

    def test_set_primary_attachment_clears_other_primaries(self, org, invoice):
        """set_primary_attachment clears is_primary on other attachments."""
        docs = []
        attachments = []
        for i in range(2):
            img_data = create_test_image(100, 100)
            doc = Document.objects.create(
                target=org,
                file=SimpleUploadedFile(f"{i}.png", img_data.read(), "image/png"),
                filename=f"{i}.png",
                content_type="image/png",
                document_type="photo",
            )
            docs.append(doc)
            a = attach_media(doc, invoice, AttachmentPurpose.GALLERY)
            attachments.append(a)

        # Set first as primary
        set_primary_attachment(attachments[0])
        # Set second as primary
        set_primary_attachment(attachments[1])

        attachments[0].refresh_from_db()
        attachments[1].refresh_from_db()

        assert attachments[0].is_primary is False
        assert attachments[1].is_primary is True

    def test_set_primary_only_affects_same_purpose(self, org, invoice):
        """set_primary_attachment only clears primaries with same purpose."""
        img_data1 = create_test_image(100, 100)
        doc1 = Document.objects.create(
            target=org,
            file=SimpleUploadedFile("1.png", img_data1.read(), "image/png"),
            filename="1.png",
            content_type="image/png",
            document_type="photo",
        )
        img_data2 = create_test_image(100, 100)
        doc2 = Document.objects.create(
            target=org,
            file=SimpleUploadedFile("2.png", img_data2.read(), "image/png"),
            filename="2.png",
            content_type="image/png",
            document_type="photo",
        )

        gallery = attach_media(doc1, invoice, AttachmentPurpose.GALLERY)
        cover = attach_media(doc2, invoice, AttachmentPurpose.COVER)

        set_primary_attachment(gallery)
        set_primary_attachment(cover)

        gallery.refresh_from_db()
        cover.refresh_from_db()

        # Both should still be primary (different purposes)
        assert gallery.is_primary is True
        assert cover.is_primary is True
