"""Tests for CMS staff views."""

import json
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()


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
    """Create a non-staff user."""
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
def cms_page(db):
    """Create a CMS content page."""
    from django_cms_core.models import ContentPage

    return ContentPage.objects.create(
        title="Test Page",
        slug="test-page",
        status="draft",
        access_level="public",
        template_key="default",
    )


@pytest.fixture
def published_page(db):
    """Create a published CMS content page."""
    from django_cms_core.models import ContentPage
    from django.utils import timezone

    return ContentPage.objects.create(
        title="Published Page",
        slug="published-page",
        status="published",
        published_at=timezone.now(),
        access_level="public",
        template_key="default",
    )


@pytest.fixture
def content_block(db, cms_page):
    """Create a content block for a page."""
    from django_cms_core.models import ContentBlock

    return ContentBlock.objects.create(
        page=cms_page,
        block_type="rich_text",
        data={"content": "Test content"},
        sequence=1,
        is_active=True,
    )


@pytest.fixture
def redirect(db):
    """Create a CMS redirect."""
    from django_cms_core.models import Redirect

    return Redirect.objects.create(
        from_path="old-page",
        to_path="new-page",
        is_permanent=True,
    )


@pytest.mark.django_db
class TestCMSPageListView:
    """Tests for CMS page list view."""

    def test_page_list_requires_authentication(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-page-list")
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_page_list_requires_staff(self, regular_client):
        """Non-staff users are denied access."""
        url = reverse("diveops:cms-page-list")
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_page_list_accessible_by_staff(self, staff_client, cms_page):
        """Staff users can access page list."""
        url = reverse("diveops:cms-page-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "pages" in response.context

    def test_page_list_shows_pages(self, staff_client, cms_page):
        """Page list shows existing pages."""
        url = reverse("diveops:cms-page-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert cms_page.title.encode() in response.content

    def test_page_list_filters_by_status(self, staff_client, cms_page, published_page):
        """Page list can filter by status."""
        url = reverse("diveops:cms-page-list") + "?status=draft"
        response = staff_client.get(url)

        assert response.status_code == 200
        assert cms_page.title.encode() in response.content
        assert published_page.title.encode() not in response.content

    def test_page_list_search(self, staff_client, cms_page):
        """Page list can search by title."""
        url = reverse("diveops:cms-page-list") + "?q=Test"
        response = staff_client.get(url)

        assert response.status_code == 200
        assert cms_page.title.encode() in response.content

    def test_page_list_shows_status_counts(self, staff_client, cms_page, published_page):
        """Page list shows status counts."""
        url = reverse("diveops:cms-page-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "total_pages" in response.context
        assert "draft_pages" in response.context
        assert "published_pages" in response.context


@pytest.mark.django_db
class TestCMSPageCreateView:
    """Tests for CMS page create view."""

    def test_create_page_requires_staff(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-page-create")
        response = anonymous_client.get(url)

        assert response.status_code == 302

    def test_create_page_accessible_by_staff(self, staff_client):
        """Staff users can access create page form."""
        url = reverse("diveops:cms-page-create")
        response = staff_client.get(url)

        assert response.status_code == 200

    def test_create_page_creates_page(self, staff_client):
        """POST creates a new page."""
        from django_cms_core.models import ContentPage

        url = reverse("diveops:cms-page-create")
        response = staff_client.post(url, {
            "title": "New Page",
            "slug": "new-page",
            "status": "draft",
            "access_level": "public",
            "template_key": "default",
        })

        assert response.status_code == 302
        assert ContentPage.objects.filter(slug="new-page").exists()

    def test_create_page_redirects_to_detail(self, staff_client):
        """Successful creation redirects to page detail."""
        url = reverse("diveops:cms-page-create")
        response = staff_client.post(url, {
            "title": "Redirect Test",
            "slug": "redirect-test",
            "status": "draft",
            "access_level": "public",
            "template_key": "default",
        })

        assert response.status_code == 302
        assert "cms/pages/" in response.url


@pytest.mark.django_db
class TestCMSPageDetailView:
    """Tests for CMS page detail view."""

    def test_page_detail_requires_staff(self, anonymous_client, cms_page):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-page-detail", kwargs={"pk": cms_page.pk})
        response = anonymous_client.get(url)

        assert response.status_code == 302

    def test_page_detail_accessible_by_staff(self, staff_client, cms_page):
        """Staff users can access page detail."""
        url = reverse("diveops:cms-page-detail", kwargs={"pk": cms_page.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "page" in response.context

    def test_page_detail_shows_page_info(self, staff_client, cms_page):
        """Page detail shows page information."""
        url = reverse("diveops:cms-page-detail", kwargs={"pk": cms_page.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert cms_page.title.encode() in response.content

    def test_page_detail_shows_blocks(self, staff_client, cms_page, content_block):
        """Page detail shows content blocks."""
        url = reverse("diveops:cms-page-detail", kwargs={"pk": cms_page.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "blocks" in response.context
        assert len(response.context["blocks"]) == 1

    def test_page_detail_has_preview_link(self, staff_client, cms_page):
        """Page detail has preview link."""
        url = reverse("diveops:cms-page-detail", kwargs={"pk": cms_page.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert b"Preview" in response.content

    def test_page_detail_404_for_invalid_pk(self, staff_client):
        """Page detail returns 404 for non-existent page."""
        import uuid
        url = reverse("diveops:cms-page-detail", kwargs={"pk": uuid.uuid4()})
        response = staff_client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestCMSPageUpdateView:
    """Tests for CMS page update view."""

    def test_update_page_requires_staff(self, anonymous_client, cms_page):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-page-update", kwargs={"pk": cms_page.pk})
        response = anonymous_client.post(url, {})

        assert response.status_code == 302

    def test_update_page_updates_title(self, staff_client, cms_page):
        """POST updates page title."""
        url = reverse("diveops:cms-page-update", kwargs={"pk": cms_page.pk})
        response = staff_client.post(url, {
            "title": "Updated Title",
            "slug": cms_page.slug,
            "access_level": cms_page.access_level,
            "template_key": cms_page.template_key,
        })

        assert response.status_code == 302
        cms_page.refresh_from_db()
        assert cms_page.title == "Updated Title"


@pytest.mark.django_db
class TestCMSPagePublishView:
    """Tests for CMS page publish view."""

    def test_publish_requires_staff(self, anonymous_client, cms_page):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-page-publish", kwargs={"pk": cms_page.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302

    def test_publish_requires_post(self, staff_client, cms_page):
        """GET is not allowed."""
        url = reverse("diveops:cms-page-publish", kwargs={"pk": cms_page.pk})
        response = staff_client.get(url)

        assert response.status_code == 405

    def test_publish_publishes_draft_page(self, staff_client, cms_page, content_block):
        """POST publishes a draft page with blocks."""
        # Import blocks module to register block types
        import django_cms_core.blocks  # noqa: F401

        assert cms_page.status == "draft"

        url = reverse("diveops:cms-page-publish", kwargs={"pk": cms_page.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        cms_page.refresh_from_db()
        assert cms_page.status == "published"
        assert cms_page.published_at is not None


@pytest.mark.django_db
class TestCMSPageUnpublishView:
    """Tests for CMS page unpublish view."""

    def test_unpublish_requires_staff(self, anonymous_client, published_page):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-page-unpublish", kwargs={"pk": published_page.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302

    def test_unpublish_requires_post(self, staff_client, published_page):
        """GET is not allowed."""
        url = reverse("diveops:cms-page-unpublish", kwargs={"pk": published_page.pk})
        response = staff_client.get(url)

        assert response.status_code == 405

    def test_unpublish_unpublishes_page(self, staff_client, published_page):
        """POST unpublishes a published page."""
        assert published_page.status == "published"

        url = reverse("diveops:cms-page-unpublish", kwargs={"pk": published_page.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        published_page.refresh_from_db()
        assert published_page.status == "draft"


@pytest.mark.django_db
class TestCMSPageArchiveView:
    """Tests for CMS page archive view."""

    def test_archive_requires_staff(self, anonymous_client, cms_page):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-page-archive", kwargs={"pk": cms_page.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302

    def test_archive_archives_page(self, staff_client, cms_page):
        """POST archives a page."""
        url = reverse("diveops:cms-page-archive", kwargs={"pk": cms_page.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        cms_page.refresh_from_db()
        assert cms_page.status == "archived"


@pytest.mark.django_db
class TestCMSPageDeleteView:
    """Tests for CMS page delete view."""

    def test_delete_requires_staff(self, anonymous_client, cms_page):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-page-delete", kwargs={"pk": cms_page.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302

    def test_delete_soft_deletes_page(self, staff_client, cms_page):
        """POST soft-deletes the page."""
        url = reverse("diveops:cms-page-delete", kwargs={"pk": cms_page.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        cms_page.refresh_from_db()
        assert cms_page.deleted_at is not None


@pytest.mark.django_db
class TestCMSBlockAddView:
    """Tests for adding content blocks."""

    def test_add_block_requires_staff(self, anonymous_client, cms_page):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-block-add", kwargs={"pk": cms_page.pk})
        response = anonymous_client.post(url, {})

        assert response.status_code == 302

    def test_add_block_creates_block(self, staff_client, cms_page):
        """POST creates a new block."""
        from django_cms_core.models import ContentBlock

        url = reverse("diveops:cms-block-add", kwargs={"pk": cms_page.pk})
        response = staff_client.post(url, {
            "block_type": "rich_text",
            "data": '{"content": "New content"}',
        })

        assert response.status_code == 302
        assert ContentBlock.objects.filter(page=cms_page, block_type="rich_text").exists()


@pytest.mark.django_db
class TestCMSBlockUpdateView:
    """Tests for updating content blocks."""

    def test_update_block_requires_staff(self, anonymous_client, cms_page, content_block):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-block-update", kwargs={
            "page_pk": cms_page.pk,
            "block_pk": content_block.pk,
        })
        response = anonymous_client.post(url, {})

        assert response.status_code == 302

    def test_update_block_updates_data(self, staff_client, cms_page, content_block):
        """POST updates block data."""
        url = reverse("diveops:cms-block-update", kwargs={
            "page_pk": cms_page.pk,
            "block_pk": content_block.pk,
        })
        response = staff_client.post(url, {
            "data": '{"content": "Updated content"}',
            "is_active": True,
        })

        assert response.status_code == 302
        content_block.refresh_from_db()
        assert content_block.data["content"] == "Updated content"


@pytest.mark.django_db
class TestCMSBlockDeleteView:
    """Tests for deleting content blocks."""

    def test_delete_block_requires_staff(self, anonymous_client, cms_page, content_block):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-block-delete", kwargs={
            "page_pk": cms_page.pk,
            "block_pk": content_block.pk,
        })
        response = anonymous_client.post(url)

        assert response.status_code == 302

    def test_delete_block_deletes_block(self, staff_client, cms_page, content_block):
        """POST deletes the block."""
        from django_cms_core.models import ContentBlock

        url = reverse("diveops:cms-block-delete", kwargs={
            "page_pk": cms_page.pk,
            "block_pk": content_block.pk,
        })
        response = staff_client.post(url)

        assert response.status_code == 302
        assert not ContentBlock.objects.filter(pk=content_block.pk).exists()


@pytest.mark.django_db
class TestCMSRedirectListView:
    """Tests for redirect list view."""

    def test_redirect_list_requires_staff(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-redirect-list")
        response = anonymous_client.get(url)

        assert response.status_code == 302

    def test_redirect_list_accessible_by_staff(self, staff_client, redirect):
        """Staff users can access redirect list."""
        url = reverse("diveops:cms-redirect-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "redirects" in response.context

    def test_redirect_list_shows_redirects(self, staff_client, redirect):
        """Redirect list shows existing redirects."""
        url = reverse("diveops:cms-redirect-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert redirect.from_path.encode() in response.content


@pytest.mark.django_db
class TestCMSRedirectCreateView:
    """Tests for redirect create view."""

    def test_create_redirect_requires_staff(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-redirect-create")
        response = anonymous_client.get(url)

        assert response.status_code == 302

    def test_create_redirect_accessible_by_staff(self, staff_client):
        """Staff users can access create redirect form."""
        url = reverse("diveops:cms-redirect-create")
        response = staff_client.get(url)

        assert response.status_code == 200

    def test_create_redirect_creates_redirect(self, staff_client):
        """POST creates a new redirect."""
        from django_cms_core.models import Redirect

        url = reverse("diveops:cms-redirect-create")
        response = staff_client.post(url, {
            "from_path": "old-url",
            "to_path": "new-url",
            "is_permanent": True,
        })

        assert response.status_code == 302
        assert Redirect.objects.filter(from_path="old-url").exists()


@pytest.mark.django_db
class TestCMSRedirectDeleteView:
    """Tests for redirect delete view."""

    def test_delete_redirect_requires_staff(self, anonymous_client, redirect):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-redirect-delete", kwargs={"pk": redirect.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302

    def test_delete_redirect_deletes_redirect(self, staff_client, redirect):
        """POST deletes the redirect."""
        from django_cms_core.models import Redirect

        url = reverse("diveops:cms-redirect-delete", kwargs={"pk": redirect.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        assert not Redirect.objects.filter(pk=redirect.pk).exists()


@pytest.mark.django_db
class TestCMSSettingsView:
    """Tests for CMS settings view."""

    def test_settings_requires_staff(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:cms-settings")
        response = anonymous_client.get(url)

        assert response.status_code == 302

    def test_settings_accessible_by_staff(self, staff_client):
        """Staff users can access settings."""
        url = reverse("diveops:cms-settings")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "settings" in response.context

    def test_settings_update_saves(self, staff_client):
        """POST updates settings."""
        from django_cms_core.models import CMSSettings

        url = reverse("diveops:cms-settings")
        response = staff_client.post(url, {
            "site_name": "Updated Site Name",
            "default_seo_title_suffix": " | My Site",
            "default_og_image_url": "https://example.com/image.jpg",
            "api_cache_ttl_seconds": 120,
        })

        assert response.status_code == 302
        settings = CMSSettings.get_instance()
        assert settings.site_name == "Updated Site Name"


@pytest.mark.django_db
class TestCMSURLPatterns:
    """Tests for CMS URL patterns."""

    def test_cms_page_list_url_resolves(self):
        """CMS page list URL can be reversed."""
        url = reverse("diveops:cms-page-list")
        assert "/cms/pages/" in url

    def test_cms_page_create_url_resolves(self):
        """CMS page create URL can be reversed."""
        url = reverse("diveops:cms-page-create")
        assert "/cms/pages/add/" in url

    def test_cms_page_detail_url_resolves(self, cms_page):
        """CMS page detail URL can be reversed."""
        url = reverse("diveops:cms-page-detail", kwargs={"pk": cms_page.pk})
        assert str(cms_page.pk) in url

    def test_cms_redirect_list_url_resolves(self):
        """CMS redirect list URL can be reversed."""
        url = reverse("diveops:cms-redirect-list")
        assert "/cms/redirects/" in url

    def test_cms_settings_url_resolves(self):
        """CMS settings URL can be reversed."""
        url = reverse("diveops:cms-settings")
        assert "/cms/settings/" in url
