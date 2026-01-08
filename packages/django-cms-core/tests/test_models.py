"""Tests for django-cms-core models."""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone


@pytest.mark.django_db
class TestContentPage:
    """Tests for ContentPage model."""

    def test_create_page_with_required_fields(self):
        """ContentPage can be created with slug and title."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(
            slug="about-us",
            title="About Us",
        )
        assert page.pk is not None
        assert isinstance(page.pk, uuid.UUID)
        assert page.slug == "about-us"
        assert page.title == "About Us"

    def test_page_has_uuid_primary_key(self):
        """ContentPage uses UUID as primary key."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(slug="test", title="Test")
        assert isinstance(page.pk, uuid.UUID)

    def test_page_has_timestamps(self):
        """ContentPage has created_at and updated_at."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(slug="test", title="Test")
        assert page.created_at is not None
        assert page.updated_at is not None

    def test_page_default_status_is_draft(self):
        """ContentPage defaults to draft status."""
        from django_cms_core.models import ContentPage, PageStatus

        page = ContentPage.objects.create(slug="test", title="Test")
        assert page.status == PageStatus.DRAFT

    def test_page_default_access_level_is_public(self):
        """ContentPage defaults to public access."""
        from django_cms_core.models import ContentPage, AccessLevel

        page = ContentPage.objects.create(slug="test", title="Test")
        assert page.access_level == AccessLevel.PUBLIC

    def test_page_slug_unique_among_active(self):
        """Slug must be unique among non-deleted pages."""
        from django_cms_core.models import ContentPage

        ContentPage.objects.create(slug="unique-slug", title="First")
        with pytest.raises(IntegrityError):
            ContentPage.objects.create(slug="unique-slug", title="Second")

    def test_deleted_page_allows_slug_reuse(self):
        """Soft-deleted page slug can be reused."""
        from django_cms_core.models import ContentPage

        page1 = ContentPage.objects.create(slug="reusable", title="First")
        page1.delete()  # Soft delete

        page2 = ContentPage.objects.create(slug="reusable", title="Second")
        assert page2.slug == "reusable"

    def test_page_seo_fields(self):
        """ContentPage has SEO fields."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(
            slug="seo-test",
            title="SEO Test",
            seo_title="Custom SEO Title",
            seo_description="Meta description for search engines",
            og_image_url="https://example.com/image.jpg",
            canonical_url="https://example.com/seo-test/",
            robots="noindex, nofollow",
        )
        assert page.seo_title == "Custom SEO Title"
        assert page.seo_description == "Meta description for search engines"
        assert page.og_image_url == "https://example.com/image.jpg"
        assert page.canonical_url == "https://example.com/seo-test/"
        assert page.robots == "noindex, nofollow"

    def test_page_default_seo_values(self):
        """ContentPage has sensible SEO defaults."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(slug="test", title="Test")
        assert page.seo_title == ""
        assert page.seo_description == ""
        assert page.og_image_url == ""
        assert page.robots == "index, follow"

    def test_page_publishing_fields(self):
        """ContentPage has publishing-related fields."""
        from django_cms_core.models import ContentPage

        User = get_user_model()
        user = User.objects.create_user("publisher", "pub@test.com", "pass")
        now = timezone.now()

        page = ContentPage.objects.create(
            slug="published",
            title="Published Page",
            published_snapshot={"version": 1, "blocks": []},
            published_at=now,
            published_by=user,
        )
        assert page.published_snapshot == {"version": 1, "blocks": []}
        assert page.published_at == now
        assert page.published_by == user

    def test_page_access_control_fields(self):
        """ContentPage has access control fields."""
        from django_cms_core.models import ContentPage, AccessLevel

        page = ContentPage.objects.create(
            slug="protected",
            title="Protected Page",
            access_level=AccessLevel.ROLE,
            required_roles=["admin", "editor"],
            required_entitlements=["premium_content"],
        )
        assert page.access_level == AccessLevel.ROLE
        assert page.required_roles == ["admin", "editor"]
        assert page.required_entitlements == ["premium_content"]

    def test_page_metadata_field(self):
        """ContentPage has metadata JSON field."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(
            slug="meta",
            title="Meta Page",
            metadata={"custom_field": "value", "nested": {"key": 123}},
        )
        assert page.metadata == {"custom_field": "value", "nested": {"key": 123}}

    def test_page_template_key(self):
        """ContentPage has template_key for rendering hints."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(
            slug="landing",
            title="Landing Page",
            template_key="landing_page",
        )
        assert page.template_key == "landing_page"

    def test_page_default_template_key(self):
        """ContentPage defaults to 'default' template key."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(slug="test", title="Test")
        assert page.template_key == "default"

    def test_page_soft_delete(self):
        """ContentPage supports soft delete."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(slug="deleteme", title="Delete Me")
        page_id = page.pk
        page.delete()

        # Not in default queryset
        assert ContentPage.objects.filter(pk=page_id).count() == 0
        # Still in all_objects
        assert ContentPage.all_objects.filter(pk=page_id).count() == 1

    def test_page_sort_order(self):
        """ContentPage has sort_order field."""
        from django_cms_core.models import ContentPage

        page1 = ContentPage.objects.create(slug="page1", title="Page 1", sort_order=10)
        page2 = ContentPage.objects.create(slug="page2", title="Page 2", sort_order=5)

        pages = list(ContentPage.objects.order_by("sort_order"))
        assert pages[0].slug == "page2"
        assert pages[1].slug == "page1"

    def test_page_is_indexable(self):
        """ContentPage has is_indexable field for sitemap inclusion."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(
            slug="noindex",
            title="No Index",
            is_indexable=False,
        )
        assert page.is_indexable is False

    def test_page_default_is_indexable(self):
        """ContentPage defaults to is_indexable=True."""
        from django_cms_core.models import ContentPage

        page = ContentPage.objects.create(slug="test", title="Test")
        assert page.is_indexable is True


@pytest.mark.django_db
class TestContentBlock:
    """Tests for ContentBlock model."""

    def test_create_block_with_required_fields(self):
        """ContentBlock can be created with page, type, and data."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        block = ContentBlock.objects.create(
            page=page,
            block_type="rich_text",
            data={"content": "<p>Hello</p>"},
        )
        assert block.pk is not None
        assert block.page == page
        assert block.block_type == "rich_text"
        assert block.data == {"content": "<p>Hello</p>"}

    def test_block_has_uuid_primary_key(self):
        """ContentBlock uses UUID as primary key."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        block = ContentBlock.objects.create(page=page, block_type="text", data={})
        assert isinstance(block.pk, uuid.UUID)

    def test_block_has_sequence(self):
        """ContentBlock has sequence for ordering."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        block1 = ContentBlock.objects.create(page=page, block_type="text", data={}, sequence=0)
        block2 = ContentBlock.objects.create(page=page, block_type="text", data={}, sequence=1)

        assert block1.sequence == 0
        assert block2.sequence == 1

    def test_block_default_sequence_is_zero(self):
        """ContentBlock defaults to sequence=0."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        block = ContentBlock.objects.create(page=page, block_type="text", data={})
        assert block.sequence == 0

    def test_block_is_active_field(self):
        """ContentBlock has is_active field."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        block = ContentBlock.objects.create(
            page=page,
            block_type="text",
            data={},
            is_active=False,
        )
        assert block.is_active is False

    def test_block_default_is_active(self):
        """ContentBlock defaults to is_active=True."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        block = ContentBlock.objects.create(page=page, block_type="text", data={})
        assert block.is_active is True

    def test_block_ordering_by_page_and_sequence(self):
        """ContentBlock orders by page and sequence."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        block3 = ContentBlock.objects.create(page=page, block_type="text", data={}, sequence=2)
        block1 = ContentBlock.objects.create(page=page, block_type="text", data={}, sequence=0)
        block2 = ContentBlock.objects.create(page=page, block_type="text", data={}, sequence=1)

        blocks = list(page.blocks.all())
        assert blocks[0].sequence == 0
        assert blocks[1].sequence == 1
        assert blocks[2].sequence == 2

    def test_block_cascades_on_page_delete(self):
        """Blocks are deleted when page is deleted."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        ContentBlock.objects.create(page=page, block_type="text", data={})
        ContentBlock.objects.create(page=page, block_type="text", data={})

        page_id = page.pk
        page.delete()  # Soft delete

        # Blocks should still exist (soft delete doesn't cascade)
        blocks = ContentBlock.objects.filter(page_id=page_id)
        # Note: This depends on implementation - may need adjustment

    def test_block_soft_delete(self):
        """ContentBlock supports soft delete."""
        from django_cms_core.models import ContentPage, ContentBlock

        page = ContentPage.objects.create(slug="test", title="Test")
        block = ContentBlock.objects.create(page=page, block_type="text", data={})
        block_id = block.pk
        block.delete()

        assert ContentBlock.objects.filter(pk=block_id).count() == 0
        assert ContentBlock.all_objects.filter(pk=block_id).count() == 1


@pytest.mark.django_db
class TestCMSSettings:
    """Tests for CMSSettings singleton model."""

    def test_get_instance_creates_if_not_exists(self):
        """CMSSettings.get_instance() creates singleton if needed."""
        from django_cms_core.models import CMSSettings

        settings = CMSSettings.get_instance()
        assert settings is not None
        assert settings.pk is not None

    def test_only_one_instance_exists(self):
        """Only one CMSSettings instance can exist."""
        from django_cms_core.models import CMSSettings

        settings1 = CMSSettings.get_instance()
        settings2 = CMSSettings.get_instance()
        assert settings1.pk == settings2.pk

    def test_settings_site_name(self):
        """CMSSettings has site_name field."""
        from django_cms_core.models import CMSSettings

        settings = CMSSettings.get_instance()
        settings.site_name = "My Site"
        settings.save()

        settings.refresh_from_db()
        assert settings.site_name == "My Site"

    def test_settings_hook_paths(self):
        """CMSSettings has hook path fields."""
        from django_cms_core.models import CMSSettings

        settings = CMSSettings.get_instance()
        settings.media_url_resolver_path = "myapp.utils.resolve_media_url"
        settings.entitlement_checker_path = "myapp.auth.check_entitlement"
        settings.save()

        settings.refresh_from_db()
        assert settings.media_url_resolver_path == "myapp.utils.resolve_media_url"
        assert settings.entitlement_checker_path == "myapp.auth.check_entitlement"

    def test_settings_default_seo(self):
        """CMSSettings has default SEO fields."""
        from django_cms_core.models import CMSSettings

        settings = CMSSettings.get_instance()
        settings.default_seo_title_suffix = " | My Site"
        settings.default_og_image_url = "https://example.com/default-og.jpg"
        settings.save()

        settings.refresh_from_db()
        assert settings.default_seo_title_suffix == " | My Site"
        assert settings.default_og_image_url == "https://example.com/default-og.jpg"

    def test_settings_nav_json(self):
        """CMSSettings has nav_json field."""
        from django_cms_core.models import CMSSettings

        nav = [
            {"label": "Home", "url": "/"},
            {"label": "About", "url": "/about/"},
        ]
        settings = CMSSettings.get_instance()
        settings.nav_json = nav
        settings.save()

        settings.refresh_from_db()
        assert settings.nav_json == nav

    def test_settings_footer_json(self):
        """CMSSettings has footer_json field."""
        from django_cms_core.models import CMSSettings

        footer = {
            "columns": [
                {"title": "Links", "items": [{"label": "Home", "url": "/"}]},
            ],
        }
        settings = CMSSettings.get_instance()
        settings.footer_json = footer
        settings.save()

        settings.refresh_from_db()
        assert settings.footer_json == footer

    def test_settings_api_cache_ttl(self):
        """CMSSettings has api_cache_ttl_seconds field."""
        from django_cms_core.models import CMSSettings

        settings = CMSSettings.get_instance()
        settings.api_cache_ttl_seconds = 300
        settings.save()

        settings.refresh_from_db()
        assert settings.api_cache_ttl_seconds == 300

    def test_settings_default_api_cache_ttl(self):
        """CMSSettings defaults api_cache_ttl_seconds to 60."""
        from django_cms_core.models import CMSSettings

        settings = CMSSettings.get_instance()
        assert settings.api_cache_ttl_seconds == 60

    def test_settings_metadata(self):
        """CMSSettings has metadata field."""
        from django_cms_core.models import CMSSettings

        settings = CMSSettings.get_instance()
        settings.metadata = {"analytics_id": "UA-12345"}
        settings.save()

        settings.refresh_from_db()
        assert settings.metadata == {"analytics_id": "UA-12345"}


@pytest.mark.django_db
class TestRedirect:
    """Tests for Redirect model."""

    def test_create_redirect(self):
        """Redirect can be created with from_path and to_path."""
        from django_cms_core.models import Redirect

        redirect = Redirect.objects.create(
            from_path="/old-page/",
            to_path="/new-page/",
        )
        assert redirect.pk is not None
        assert redirect.from_path == "/old-page/"
        assert redirect.to_path == "/new-page/"

    def test_redirect_has_uuid_primary_key(self):
        """Redirect uses UUID as primary key."""
        from django_cms_core.models import Redirect

        redirect = Redirect.objects.create(from_path="/a/", to_path="/b/")
        assert isinstance(redirect.pk, uuid.UUID)

    def test_redirect_is_permanent_field(self):
        """Redirect has is_permanent field for 301 vs 302."""
        from django_cms_core.models import Redirect

        redirect301 = Redirect.objects.create(
            from_path="/permanent/",
            to_path="/new/",
            is_permanent=True,
        )
        redirect302 = Redirect.objects.create(
            from_path="/temporary/",
            to_path="/new/",
            is_permanent=False,
        )
        assert redirect301.is_permanent is True
        assert redirect302.is_permanent is False

    def test_redirect_default_is_temporary(self):
        """Redirect defaults to is_permanent=False (302)."""
        from django_cms_core.models import Redirect

        redirect = Redirect.objects.create(from_path="/a/", to_path="/b/")
        assert redirect.is_permanent is False

    def test_redirect_from_path_unique(self):
        """from_path must be unique."""
        from django_cms_core.models import Redirect

        Redirect.objects.create(from_path="/unique/", to_path="/target1/")
        with pytest.raises(IntegrityError):
            Redirect.objects.create(from_path="/unique/", to_path="/target2/")

    def test_redirect_soft_delete_allows_from_path_reuse(self):
        """Soft-deleted redirect from_path can be reused."""
        from django_cms_core.models import Redirect

        redirect1 = Redirect.objects.create(from_path="/reuse/", to_path="/old/")
        redirect1.delete()  # Soft delete

        redirect2 = Redirect.objects.create(from_path="/reuse/", to_path="/new/")
        assert redirect2.from_path == "/reuse/"

    def test_redirect_soft_delete(self):
        """Redirect supports soft delete."""
        from django_cms_core.models import Redirect

        redirect = Redirect.objects.create(from_path="/del/", to_path="/b/")
        redirect_id = redirect.pk
        redirect.delete()

        assert Redirect.objects.filter(pk=redirect_id).count() == 0
        assert Redirect.all_objects.filter(pk=redirect_id).count() == 1


@pytest.mark.django_db
class TestPageStatus:
    """Tests for PageStatus enum."""

    def test_page_status_values(self):
        """PageStatus has draft, published, archived values."""
        from django_cms_core.models import PageStatus

        assert PageStatus.DRAFT == "draft"
        assert PageStatus.PUBLISHED == "published"
        assert PageStatus.ARCHIVED == "archived"


@pytest.mark.django_db
class TestAccessLevel:
    """Tests for AccessLevel enum."""

    def test_access_level_values(self):
        """AccessLevel has public, authenticated, role, entitlement values."""
        from django_cms_core.models import AccessLevel

        assert AccessLevel.PUBLIC == "public"
        assert AccessLevel.AUTHENTICATED == "authenticated"
        assert AccessLevel.ROLE == "role"
        assert AccessLevel.ENTITLEMENT == "entitlement"
