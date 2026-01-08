"""Tests for Media models (MediaAsset, MediaRendition, Attachment)."""
import pytest
from io import BytesIO
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
from tests.models import Organization, Invoice


@pytest.mark.django_db
class TestMediaAssetModel:
    """Test suite for MediaAsset model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def sample_image(self):
        """Create a sample image file."""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Minimal PNG header
        return SimpleUploadedFile(
            name="test_image.png",
            content=content,
            content_type="image/png",
        )

    @pytest.fixture
    def document(self, org, sample_image):
        """Create a test document."""
        return Document.objects.create(
            target=org,
            file=sample_image,
            filename="test_image.png",
            content_type="image/png",
            document_type="photo",
            category="image",
        )

    def test_media_asset_creation(self, document):
        """MediaAsset can be created with a document."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            width=1920,
            height=1080,
        )
        assert asset.pk is not None
        assert asset.document == document

    def test_media_asset_is_one_to_one(self, document):
        """MediaAsset has 1:1 relationship with Document."""
        MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
        )
        # Second MediaAsset for same document should fail
        with pytest.raises(Exception):  # IntegrityError
            MediaAsset.objects.create(
                document=document,
                kind=MediaKind.IMAGE,
            )

    def test_media_asset_has_kind(self, document):
        """MediaAsset should have kind field (image/video)."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.VIDEO,
        )
        assert asset.kind == MediaKind.VIDEO

    def test_media_asset_has_dimensions(self, document):
        """MediaAsset should store width and height."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            width=1920,
            height=1080,
        )
        assert asset.width == 1920
        assert asset.height == 1080

    def test_media_asset_aspect_ratio(self, document):
        """MediaAsset should calculate aspect ratio."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            width=1920,
            height=1080,
        )
        assert asset.aspect_ratio == pytest.approx(1.777, rel=0.01)

    def test_media_asset_is_landscape(self, document):
        """MediaAsset should detect landscape orientation."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            width=1920,
            height=1080,
        )
        assert asset.is_landscape is True
        assert asset.is_portrait is False

    def test_media_asset_is_portrait(self, document):
        """MediaAsset should detect portrait orientation."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            width=1080,
            height=1920,
        )
        assert asset.is_portrait is True
        assert asset.is_landscape is False

    def test_media_asset_has_processing_status(self, document):
        """MediaAsset should have processing status."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            status=MediaProcessingStatus.PENDING,
        )
        assert asset.status == MediaProcessingStatus.PENDING

    def test_media_asset_has_exif_fields(self, document):
        """MediaAsset should store EXIF metadata."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            camera_make="Canon",
            camera_model="EOS R5",
        )
        assert asset.camera_make == "Canon"
        assert asset.camera_model == "EOS R5"

    def test_media_asset_has_gps_fields(self, document):
        """MediaAsset should store GPS coordinates."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            gps_latitude=20.5,
            gps_longitude=-87.4,
        )
        assert asset.gps_latitude == 20.5
        assert asset.gps_longitude == -87.4

    def test_media_asset_video_has_duration(self, document):
        """Video MediaAsset should have duration."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.VIDEO,
            duration_seconds=125.5,
        )
        assert asset.duration_seconds == 125.5

    def test_media_asset_has_alt_text(self, document):
        """MediaAsset should have alt_text for accessibility."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            alt_text="A diver exploring a coral reef",
        )
        assert asset.alt_text == "A diver exploring a coral reef"


@pytest.mark.django_db
class TestMediaRenditionModel:
    """Test suite for MediaRendition model."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def sample_image(self):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        return SimpleUploadedFile(
            name="test_image.png",
            content=content,
            content_type="image/png",
        )

    @pytest.fixture
    def document(self, org, sample_image):
        return Document.objects.create(
            target=org,
            file=sample_image,
            filename="test_image.png",
            content_type="image/png",
            document_type="photo",
        )

    @pytest.fixture
    def media_asset(self, document):
        return MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
            width=1920,
            height=1080,
        )

    @pytest.fixture
    def thumb_file(self):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        return SimpleUploadedFile(
            name="thumb.png",
            content=content,
            content_type="image/png",
        )

    def test_rendition_creation(self, media_asset, thumb_file):
        """MediaRendition can be created for a MediaAsset."""
        rendition = MediaRendition.objects.create(
            media_asset=media_asset,
            role=RenditionRole.THUMB,
            file=thumb_file,
            width=150,
            height=84,
            file_size=50,
        )
        assert rendition.pk is not None
        assert rendition.media_asset == media_asset

    def test_rendition_has_role(self, media_asset, thumb_file):
        """MediaRendition should have role (thumb, small, medium, etc)."""
        rendition = MediaRendition.objects.create(
            media_asset=media_asset,
            role=RenditionRole.MEDIUM,
            file=thumb_file,
            width=640,
            height=360,
            file_size=100,
        )
        assert rendition.role == RenditionRole.MEDIUM

    def test_rendition_unique_per_role(self, media_asset, thumb_file):
        """Only one rendition per role per MediaAsset."""
        MediaRendition.objects.create(
            media_asset=media_asset,
            role=RenditionRole.THUMB,
            file=thumb_file,
            width=150,
            height=84,
            file_size=50,
        )
        # Second thumb should fail
        with pytest.raises(Exception):  # IntegrityError
            thumb_file2 = SimpleUploadedFile("thumb2.png", b"\x89PNG" + b"\x00" * 50, "image/png")
            MediaRendition.objects.create(
                media_asset=media_asset,
                role=RenditionRole.THUMB,
                file=thumb_file2,
                width=150,
                height=84,
                file_size=50,
            )

    def test_rendition_has_dimensions(self, media_asset, thumb_file):
        """MediaRendition should store dimensions."""
        rendition = MediaRendition.objects.create(
            media_asset=media_asset,
            role=RenditionRole.SMALL,
            file=thumb_file,
            width=320,
            height=180,
            file_size=75,
        )
        assert rendition.width == 320
        assert rendition.height == 180

    def test_rendition_has_file_size(self, media_asset, thumb_file):
        """MediaRendition should track file size."""
        rendition = MediaRendition.objects.create(
            media_asset=media_asset,
            role=RenditionRole.THUMB,
            file=thumb_file,
            width=150,
            height=84,
            file_size=12345,
        )
        assert rendition.file_size == 12345

    def test_rendition_has_format(self, media_asset, thumb_file):
        """MediaRendition should store output format."""
        rendition = MediaRendition.objects.create(
            media_asset=media_asset,
            role=RenditionRole.THUMB,
            file=thumb_file,
            width=150,
            height=84,
            file_size=50,
            format="webp",
        )
        assert rendition.format == "webp"

    def test_media_asset_has_renditions(self, media_asset, thumb_file):
        """MediaAsset should have related renditions."""
        MediaRendition.objects.create(
            media_asset=media_asset,
            role=RenditionRole.THUMB,
            file=thumb_file,
            width=150,
            height=84,
            file_size=50,
        )
        small_file = SimpleUploadedFile("small.png", b"\x89PNG" + b"\x00" * 75, "image/png")
        MediaRendition.objects.create(
            media_asset=media_asset,
            role=RenditionRole.SMALL,
            file=small_file,
            width=320,
            height=180,
            file_size=75,
        )
        assert media_asset.renditions.count() == 2


@pytest.mark.django_db
class TestAttachmentModel:
    """Test suite for Attachment model."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def invoice(self, org):
        return Invoice.objects.create(number="INV-001", org=org)

    @pytest.fixture
    def sample_image(self):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        return SimpleUploadedFile(
            name="photo.png",
            content=content,
            content_type="image/png",
        )

    @pytest.fixture
    def document(self, org, sample_image):
        return Document.objects.create(
            target=org,
            file=sample_image,
            filename="photo.png",
            content_type="image/png",
            document_type="photo",
        )

    def test_attachment_creation(self, document, invoice):
        """Attachment can link a Document to any entity."""
        ct = ContentType.objects.get_for_model(Invoice)
        attachment = Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY,
        )
        assert attachment.pk is not None
        assert attachment.document == document
        assert attachment.content_object == invoice

    def test_attachment_has_purpose(self, document, invoice):
        """Attachment should have purpose field."""
        ct = ContentType.objects.get_for_model(Invoice)
        attachment = Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.COVER,
        )
        assert attachment.purpose == AttachmentPurpose.COVER

    def test_attachment_has_sort_order(self, document, invoice):
        """Attachment should have sort_order for galleries."""
        ct = ContentType.objects.get_for_model(Invoice)
        attachment = Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY,
            sort_order=5,
        )
        assert attachment.sort_order == 5

    def test_attachment_has_is_primary(self, document, invoice):
        """Attachment can be marked as primary."""
        ct = ContentType.objects.get_for_model(Invoice)
        attachment = Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY,
            is_primary=True,
        )
        assert attachment.is_primary is True

    def test_attachment_has_caption(self, document, invoice):
        """Attachment should have caption field."""
        ct = ContentType.objects.get_for_model(Invoice)
        attachment = Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY,
            caption="A beautiful dive photo",
        )
        assert attachment.caption == "A beautiful dive photo"

    def test_attachment_has_alt_text(self, document, invoice):
        """Attachment should have alt_text for accessibility."""
        ct = ContentType.objects.get_for_model(Invoice)
        attachment = Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY,
            alt_text="Diver with sea turtle",
        )
        assert attachment.alt_text == "Diver with sea turtle"

    def test_attachment_unique_constraint(self, document, invoice):
        """Same document cannot be attached twice with same purpose."""
        ct = ContentType.objects.get_for_model(Invoice)
        Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY,
        )
        # Second attachment with same purpose should fail
        with pytest.raises(Exception):  # IntegrityError
            Attachment.objects.create(
                document=document,
                content_type=ct,
                object_id=str(invoice.pk),
                purpose=AttachmentPurpose.GALLERY,
            )

    def test_attachment_different_purposes_allowed(self, document, invoice):
        """Same document can be attached with different purposes."""
        ct = ContentType.objects.get_for_model(Invoice)
        Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY,
        )
        # Different purpose should succeed
        attachment2 = Attachment.objects.create(
            document=document,
            content_type=ct,
            object_id=str(invoice.pk),
            purpose=AttachmentPurpose.COVER,
        )
        assert attachment2.pk is not None

    def test_attachment_ordering(self, org, invoice):
        """Attachments should be ordered by purpose, sort_order, created_at."""
        ct = ContentType.objects.get_for_model(Invoice)

        # Create documents
        file1 = SimpleUploadedFile("1.png", b"\x89PNG" + b"\x00" * 50, "image/png")
        doc1 = Document.objects.create(
            target=org, file=file1, filename="1.png",
            content_type="image/png", document_type="photo",
        )
        file2 = SimpleUploadedFile("2.png", b"\x89PNG" + b"\x00" * 50, "image/png")
        doc2 = Document.objects.create(
            target=org, file=file2, filename="2.png",
            content_type="image/png", document_type="photo",
        )

        # Create attachments with different sort orders
        a2 = Attachment.objects.create(
            document=doc2, content_type=ct, object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY, sort_order=2,
        )
        a1 = Attachment.objects.create(
            document=doc1, content_type=ct, object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY, sort_order=1,
        )

        attachments = list(Attachment.objects.filter(
            content_type=ct, object_id=str(invoice.pk)
        ))
        assert attachments[0] == a1
        assert attachments[1] == a2

    def test_document_has_attachments(self, document, invoice, org):
        """Document should have reverse relation to attachments."""
        ct_inv = ContentType.objects.get_for_model(Invoice)
        ct_org = ContentType.objects.get_for_model(Organization)

        Attachment.objects.create(
            document=document, content_type=ct_inv, object_id=str(invoice.pk),
            purpose=AttachmentPurpose.GALLERY,
        )
        Attachment.objects.create(
            document=document, content_type=ct_org, object_id=str(org.pk),
            purpose=AttachmentPurpose.AVATAR,
        )

        assert document.attachments.count() == 2
