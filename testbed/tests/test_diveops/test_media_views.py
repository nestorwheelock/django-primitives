"""Tests for Media Library staff views."""
import pytest
from io import BytesIO
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from django_documents.models import (
    Document,
    MediaAsset,
    MediaKind,
    MediaProcessingStatus,
)
from django_parties.models import Organization


User = get_user_model()


def create_test_image(width=100, height=100, format="PNG"):
    """Create a test image file."""
    img = Image.new("RGB", (width, height), color="blue")
    buffer = BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    """Create a regular (non-staff) user."""
    return User.objects.create_user(
        username="regular",
        email="regular@example.com",
        password="testpass123",
        is_staff=False,
    )


@pytest.fixture
def staff_client(staff_user):
    """Create a client logged in as staff."""
    client = Client()
    client.login(username="staff", password="testpass123")
    return client


@pytest.fixture
def regular_client(regular_user):
    """Create a client logged in as regular user."""
    client = Client()
    client.login(username="regular", password="testpass123")
    return client


@pytest.fixture
def anonymous_client():
    """Create an anonymous client."""
    return Client()


@pytest.fixture
def dive_shop(db):
    """Create a test dive shop organization."""
    return Organization.objects.create(
        name="Test Dive Shop",
        org_type="company",
    )


@pytest.fixture
def media_asset(dive_shop):
    """Create a media asset with document."""
    img_data = create_test_image(800, 600)
    uploaded = SimpleUploadedFile(
        name="test_photo.png",
        content=img_data.read(),
        content_type="image/png",
    )
    doc = Document.objects.create(
        target=dive_shop,
        file=uploaded,
        filename="test_photo.png",
        content_type="image/png",
        document_type="photo",
        category="image",
    )
    return MediaAsset.objects.create(
        document=doc,
        kind=MediaKind.IMAGE,
        width=800,
        height=600,
        status=MediaProcessingStatus.COMPLETED,
    )


@pytest.mark.django_db
class TestMediaLibraryView:
    """Tests for MediaLibraryView."""

    def test_media_library_requires_authentication(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:media-library")
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_media_library_requires_staff(self, regular_client):
        """Non-staff users are denied access."""
        url = reverse("diveops:media-library")
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_media_library_accessible_by_staff(self, staff_client, media_asset):
        """Staff users can access media library."""
        url = reverse("diveops:media-library")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "media_assets" in response.context

    def test_media_library_lists_media_assets(self, staff_client, dive_shop):
        """Media library shows all media assets."""
        # Create multiple media assets
        for i in range(3):
            img_data = create_test_image(100, 100)
            uploaded = SimpleUploadedFile(
                name=f"photo{i}.png",
                content=img_data.read(),
                content_type="image/png",
            )
            doc = Document.objects.create(
                target=dive_shop,
                file=uploaded,
                filename=f"photo{i}.png",
                content_type="image/png",
                document_type="photo",
            )
            MediaAsset.objects.create(
                document=doc,
                kind=MediaKind.IMAGE,
                width=100,
                height=100,
            )

        url = reverse("diveops:media-library")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert len(response.context["media_assets"]) == 3

    def test_media_library_filters_by_kind(self, staff_client, dive_shop):
        """Media library can filter by kind (image/video)."""
        # Create an image
        img_data = create_test_image(100, 100)
        doc1 = Document.objects.create(
            target=dive_shop,
            file=SimpleUploadedFile("photo.png", img_data.read(), "image/png"),
            filename="photo.png",
            content_type="image/png",
            document_type="photo",
        )
        MediaAsset.objects.create(
            document=doc1,
            kind=MediaKind.IMAGE,
            width=100,
            height=100,
        )

        # Create a video (simulated)
        doc2 = Document.objects.create(
            target=dive_shop,
            file=SimpleUploadedFile("video.mp4", b"fake video", "video/mp4"),
            filename="video.mp4",
            content_type="video/mp4",
            document_type="video",
        )
        MediaAsset.objects.create(
            document=doc2,
            kind=MediaKind.VIDEO,
            width=1920,
            height=1080,
        )

        url = reverse("diveops:media-library")

        # Filter by image
        response = staff_client.get(url, {"kind": "image"})
        assert response.status_code == 200
        assert len(response.context["media_assets"]) == 1

        # Filter by video
        response = staff_client.get(url, {"kind": "video"})
        assert len(response.context["media_assets"]) == 1

    def test_media_library_uses_correct_template(self, staff_client, media_asset):
        """Media library uses the correct template."""
        url = reverse("diveops:media-library")
        response = staff_client.get(url)

        assert "diveops/staff/media_library.html" in [t.name for t in response.templates]


@pytest.mark.django_db
class TestMediaDetailView:
    """Tests for MediaDetailView."""

    def test_media_detail_requires_authentication(self, anonymous_client, media_asset):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:media-detail", kwargs={"pk": media_asset.pk})
        response = anonymous_client.get(url)

        assert response.status_code == 302

    def test_media_detail_requires_staff(self, regular_client, media_asset):
        """Non-staff users are denied access."""
        url = reverse("diveops:media-detail", kwargs={"pk": media_asset.pk})
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_media_detail_accessible_by_staff(self, staff_client, media_asset):
        """Staff users can access media detail."""
        url = reverse("diveops:media-detail", kwargs={"pk": media_asset.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "media_asset" in response.context
        assert response.context["media_asset"].pk == media_asset.pk

    def test_media_detail_shows_dimensions(self, staff_client, media_asset):
        """Media detail shows width and height."""
        url = reverse("diveops:media-detail", kwargs={"pk": media_asset.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "800" in content  # width
        assert "600" in content  # height

    def test_media_detail_uses_correct_template(self, staff_client, media_asset):
        """Media detail uses the correct template."""
        url = reverse("diveops:media-detail", kwargs={"pk": media_asset.pk})
        response = staff_client.get(url)

        assert "diveops/staff/media_detail.html" in [t.name for t in response.templates]


@pytest.mark.django_db
class TestMediaUploadView:
    """Tests for media upload functionality."""

    def test_media_upload_requires_authentication(self, anonymous_client):
        """Anonymous users cannot upload media."""
        url = reverse("diveops:media-upload")
        img_data = create_test_image(100, 100)
        response = anonymous_client.post(url, {
            "file": SimpleUploadedFile("test.png", img_data.read(), "image/png"),
        })

        assert response.status_code == 302

    def test_media_upload_requires_staff(self, regular_client):
        """Non-staff users cannot upload media."""
        url = reverse("diveops:media-upload")
        img_data = create_test_image(100, 100)
        response = regular_client.post(url, {
            "file": SimpleUploadedFile("test.png", img_data.read(), "image/png"),
        })

        assert response.status_code in [302, 403]

    def test_media_upload_creates_document_and_asset(self, staff_client, dive_shop):
        """Uploading creates Document and MediaAsset."""
        url = reverse("diveops:media-upload")
        img_data = create_test_image(640, 480)

        response = staff_client.post(url, {
            "file": SimpleUploadedFile("upload.png", img_data.read(), "image/png"),
        })

        # Should redirect on success
        assert response.status_code in [200, 302]

        # Check document and asset were created
        assert Document.objects.filter(filename="upload.png").exists()
        assert MediaAsset.objects.filter(document__filename="upload.png").exists()

    def test_media_upload_extracts_dimensions(self, staff_client, dive_shop):
        """Upload extracts width and height from image."""
        url = reverse("diveops:media-upload")
        img_data = create_test_image(1280, 720)

        staff_client.post(url, {
            "file": SimpleUploadedFile("dimensions.png", img_data.read(), "image/png"),
        })

        asset = MediaAsset.objects.get(document__filename="dimensions.png")
        assert asset.width == 1280
        assert asset.height == 720
