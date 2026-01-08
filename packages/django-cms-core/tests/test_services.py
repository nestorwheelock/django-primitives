"""Tests for django-cms-core services."""

import hashlib
import json

import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
class TestCreatePage:
    """Tests for create_page service function."""

    def test_create_page_basic(self, user):
        """create_page creates a page with slug and title."""
        from django_cms_core.services import create_page

        page = create_page(
            slug="about-us",
            title="About Us",
            user=user,
        )
        assert page.slug == "about-us"
        assert page.title == "About Us"
        assert page.status == "draft"

    def test_create_page_with_seo(self, user):
        """create_page accepts SEO fields."""
        from django_cms_core.services import create_page

        page = create_page(
            slug="contact",
            title="Contact Us",
            user=user,
            seo_title="Get in Touch",
            seo_description="Contact our team",
            og_image_url="https://example.com/og.jpg",
        )
        assert page.seo_title == "Get in Touch"
        assert page.seo_description == "Contact our team"
        assert page.og_image_url == "https://example.com/og.jpg"

    def test_create_page_with_access_control(self, user):
        """create_page accepts access control fields."""
        from django_cms_core.models import AccessLevel
        from django_cms_core.services import create_page

        page = create_page(
            slug="premium",
            title="Premium Content",
            user=user,
            access_level=AccessLevel.ENTITLEMENT,
            required_entitlements=["premium_access"],
        )
        assert page.access_level == AccessLevel.ENTITLEMENT
        assert page.required_entitlements == ["premium_access"]

    def test_create_page_with_template_key(self, user):
        """create_page accepts template_key."""
        from django_cms_core.services import create_page

        page = create_page(
            slug="landing",
            title="Landing Page",
            user=user,
            template_key="landing_page",
        )
        assert page.template_key == "landing_page"


@pytest.mark.django_db
class TestAddBlock:
    """Tests for add_block service function."""

    def test_add_block_to_page(self, user):
        """add_block adds a block to a page."""
        from django_cms_core.services import create_page, add_block

        page = create_page(slug="test", title="Test", user=user)
        block = add_block(
            page=page,
            block_type="rich_text",
            data={"content": "<p>Hello</p>"},
        )
        assert block.page == page
        assert block.block_type == "rich_text"
        assert block.data == {"content": "<p>Hello</p>"}

    def test_add_block_auto_sequence(self, user):
        """add_block auto-assigns sequence if not provided."""
        from django_cms_core.services import create_page, add_block

        page = create_page(slug="test", title="Test", user=user)
        block1 = add_block(page=page, block_type="heading", data={"text": "Title"})
        block2 = add_block(page=page, block_type="rich_text", data={"content": "Body"})
        block3 = add_block(page=page, block_type="cta", data={"text": "Click", "url": "/"})

        assert block1.sequence == 0
        assert block2.sequence == 1
        assert block3.sequence == 2

    def test_add_block_explicit_sequence(self, user):
        """add_block uses explicit sequence if provided."""
        from django_cms_core.services import create_page, add_block

        page = create_page(slug="test", title="Test", user=user)
        block = add_block(
            page=page,
            block_type="rich_text",
            data={"content": "test"},
            sequence=5,
        )
        assert block.sequence == 5


@pytest.mark.django_db
class TestUpdateBlock:
    """Tests for update_block service function."""

    def test_update_block_data(self, user):
        """update_block can update block data."""
        from django_cms_core.services import create_page, add_block, update_block

        page = create_page(slug="test", title="Test", user=user)
        block = add_block(page=page, block_type="rich_text", data={"content": "old"})

        updated = update_block(block, data={"content": "new"})
        assert updated.data == {"content": "new"}

    def test_update_block_sequence(self, user):
        """update_block can update sequence."""
        from django_cms_core.services import create_page, add_block, update_block

        page = create_page(slug="test", title="Test", user=user)
        block = add_block(page=page, block_type="rich_text", data={}, sequence=0)

        updated = update_block(block, sequence=5)
        assert updated.sequence == 5

    def test_update_block_is_active(self, user):
        """update_block can update is_active."""
        from django_cms_core.services import create_page, add_block, update_block

        page = create_page(slug="test", title="Test", user=user)
        block = add_block(page=page, block_type="rich_text", data={})

        updated = update_block(block, is_active=False)
        assert updated.is_active is False


@pytest.mark.django_db
class TestReorderBlocks:
    """Tests for reorder_blocks service function."""

    def test_reorder_blocks(self, user):
        """reorder_blocks updates sequence based on ID order."""
        from django_cms_core.services import create_page, add_block, reorder_blocks

        page = create_page(slug="test", title="Test", user=user)
        b1 = add_block(page=page, block_type="heading", data={"text": "1"})
        b2 = add_block(page=page, block_type="heading", data={"text": "2"})
        b3 = add_block(page=page, block_type="heading", data={"text": "3"})

        # Reverse order
        reorder_blocks(page, [str(b3.id), str(b2.id), str(b1.id)])

        b1.refresh_from_db()
        b2.refresh_from_db()
        b3.refresh_from_db()

        assert b3.sequence == 0
        assert b2.sequence == 1
        assert b1.sequence == 2


@pytest.mark.django_db
class TestDeleteBlock:
    """Tests for delete_block service function."""

    def test_delete_block_soft_deletes(self, user):
        """delete_block soft-deletes the block."""
        from django_cms_core.models import ContentBlock
        from django_cms_core.services import create_page, add_block, delete_block

        page = create_page(slug="test", title="Test", user=user)
        block = add_block(page=page, block_type="rich_text", data={})
        block_id = block.id

        delete_block(block)

        # Should not be in default queryset
        assert ContentBlock.objects.filter(id=block_id).count() == 0
        # Should be in all_objects
        assert ContentBlock.all_objects.filter(id=block_id).count() == 1


@pytest.mark.django_db
class TestPublishPage:
    """Tests for publish_page service function."""

    def test_publish_page_basic(self, user):
        """publish_page sets status to published and creates snapshot."""
        from django_cms_core.models import PageStatus
        from django_cms_core.services import create_page, add_block, publish_page

        page = create_page(slug="test", title="Test Page", user=user)
        add_block(page=page, block_type="rich_text", data={"content": "Hello"})

        published = publish_page(page, user)

        assert published.status == PageStatus.PUBLISHED
        assert published.published_at is not None
        assert published.published_by == user
        assert published.published_snapshot is not None

    def test_publish_page_snapshot_structure(self, user):
        """publish_page creates properly structured snapshot."""
        from django_cms_core.services import create_page, add_block, publish_page

        page = create_page(
            slug="about",
            title="About Us",
            user=user,
            seo_title="About | Site",
            seo_description="Learn about us",
        )
        add_block(page=page, block_type="heading", data={"text": "Welcome", "level": 1})
        add_block(page=page, block_type="rich_text", data={"content": "<p>Content</p>"})

        published = publish_page(page, user)
        snapshot = published.published_snapshot

        assert snapshot["version"] == 1
        assert "published_at" in snapshot
        assert snapshot["published_by_id"] == str(user.id)
        assert snapshot["meta"]["title"] == "About Us"
        assert snapshot["meta"]["slug"] == "about"
        assert snapshot["meta"]["seo_title"] == "About | Site"
        assert len(snapshot["blocks"]) == 2
        assert "checksum" in snapshot

    def test_publish_page_only_active_blocks(self, user):
        """publish_page only includes active blocks in snapshot."""
        from django_cms_core.services import create_page, add_block, update_block, publish_page

        page = create_page(slug="test", title="Test", user=user)
        b1 = add_block(page=page, block_type="heading", data={"text": "Visible"})
        b2 = add_block(page=page, block_type="heading", data={"text": "Hidden"})
        update_block(b2, is_active=False)

        published = publish_page(page, user)
        snapshot = published.published_snapshot

        assert len(snapshot["blocks"]) == 1
        assert snapshot["blocks"][0]["data"]["text"] == "Visible"

    def test_publish_page_access_control_in_snapshot(self, user):
        """publish_page includes access control in snapshot."""
        from django_cms_core.models import AccessLevel
        from django_cms_core.services import create_page, publish_page

        page = create_page(
            slug="premium",
            title="Premium",
            user=user,
            access_level=AccessLevel.ROLE,
            required_roles=["subscriber"],
        )

        published = publish_page(page, user)
        snapshot = published.published_snapshot

        assert snapshot["access_control"]["level"] == "role"
        assert snapshot["access_control"]["required_roles"] == ["subscriber"]

    def test_publish_page_already_published_updates(self, user):
        """publish_page updates an already published page."""
        from django_cms_core.services import create_page, add_block, publish_page

        page = create_page(slug="test", title="V1", user=user)
        add_block(page=page, block_type="heading", data={"text": "V1"})
        published = publish_page(page, user)
        first_published_at = published.published_at

        # Update and republish
        page.title = "V2"
        page.save()
        republished = publish_page(page, user)

        assert republished.published_snapshot["meta"]["title"] == "V2"
        assert republished.published_at > first_published_at


@pytest.mark.django_db
class TestUnpublishPage:
    """Tests for unpublish_page service function."""

    def test_unpublish_page(self, user):
        """unpublish_page sets status to draft and clears snapshot."""
        from django_cms_core.models import PageStatus
        from django_cms_core.services import create_page, publish_page, unpublish_page

        page = create_page(slug="test", title="Test", user=user)
        publish_page(page, user)

        unpublished = unpublish_page(page)

        assert unpublished.status == PageStatus.DRAFT
        assert unpublished.published_snapshot is None
        assert unpublished.published_at is None


@pytest.mark.django_db
class TestArchivePage:
    """Tests for archive_page service function."""

    def test_archive_page(self, user):
        """archive_page sets status to archived."""
        from django_cms_core.models import PageStatus
        from django_cms_core.services import create_page, archive_page

        page = create_page(slug="test", title="Test", user=user)

        archived = archive_page(page)

        assert archived.status == PageStatus.ARCHIVED


@pytest.mark.django_db
class TestValidatePageBlocks:
    """Tests for validate_page_blocks service function."""

    def test_validate_page_blocks_valid(self, user):
        """validate_page_blocks returns empty list for valid blocks."""
        from django_cms_core import blocks  # noqa: F401 - register blocks
        from django_cms_core.services import create_page, add_block, validate_page_blocks

        page = create_page(slug="test", title="Test", user=user)
        add_block(page=page, block_type="rich_text", data={"content": "hello"})
        add_block(page=page, block_type="heading", data={"text": "Title", "level": 2})

        errors = validate_page_blocks(page)
        assert errors == []

    def test_validate_page_blocks_unknown_type(self, user):
        """validate_page_blocks returns error for unknown block type."""
        from django_cms_core.models import ContentBlock
        from django_cms_core.services import create_page, validate_page_blocks

        page = create_page(slug="test", title="Test", user=user)
        # Create block directly to bypass validation
        ContentBlock.objects.create(
            page=page,
            block_type="nonexistent_type",
            data={"foo": "bar"},
        )

        errors = validate_page_blocks(page)
        assert len(errors) > 0
        assert "nonexistent_type" in errors[0].lower()


@pytest.mark.django_db
class TestGetPublishedPage:
    """Tests for get_published_page service function."""

    def test_get_published_page(self, user):
        """get_published_page returns snapshot for published page."""
        from django_cms_core.services import create_page, add_block, publish_page, get_published_page

        page = create_page(slug="test", title="Test", user=user)
        add_block(page=page, block_type="rich_text", data={"content": "Hello"})
        publish_page(page, user)

        result = get_published_page("test")
        assert result is not None
        assert result["meta"]["title"] == "Test"

    def test_get_published_page_not_found(self):
        """get_published_page returns None for nonexistent page."""
        from django_cms_core.services import get_published_page

        result = get_published_page("nonexistent")
        assert result is None

    def test_get_published_page_draft_not_returned(self, user):
        """get_published_page returns None for draft page."""
        from django_cms_core.services import create_page, get_published_page

        create_page(slug="draft", title="Draft", user=user)

        result = get_published_page("draft")
        assert result is None


@pytest.mark.django_db
class TestListPublishedPages:
    """Tests for list_published_pages service function."""

    def test_list_published_pages(self, user):
        """list_published_pages returns all published pages."""
        from django_cms_core.services import create_page, publish_page, list_published_pages

        p1 = create_page(slug="page1", title="Page 1", user=user)
        p2 = create_page(slug="page2", title="Page 2", user=user)
        create_page(slug="draft", title="Draft", user=user)  # Not published

        publish_page(p1, user)
        publish_page(p2, user)

        pages = list_published_pages()
        assert len(pages) == 2
        slugs = [p["meta"]["slug"] for p in pages]
        assert "page1" in slugs
        assert "page2" in slugs
        assert "draft" not in slugs

    def test_list_published_pages_empty(self):
        """list_published_pages returns empty list if no published pages."""
        from django_cms_core.services import list_published_pages

        pages = list_published_pages()
        assert pages == []
