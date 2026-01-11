"""Tests for blog post and category staff views."""

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user for testing."""
    return User.objects.create_user(
        username="staffuser",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    """Create a regular (non-staff) user for testing."""
    return User.objects.create_user(
        username="regularuser",
        email="regular@example.com",
        password="testpass123",
        is_staff=False,
    )


@pytest.fixture
def staff_client(staff_user):
    """Create a client logged in as staff user."""
    client = Client()
    client.login(username="staffuser", password="testpass123")
    return client


@pytest.fixture
def regular_client(regular_user):
    """Create a client logged in as regular user."""
    client = Client()
    client.login(username="regularuser", password="testpass123")
    return client


@pytest.fixture
def blog_category(db):
    """Create a blog category for testing."""
    from django_cms_core.models import BlogCategory

    return BlogCategory.objects.create(
        name="Tech",
        slug="tech",
        description="Technology posts",
        color="#3b82f6",
        sort_order=0,
    )


@pytest.fixture
def blog_post(db, blog_category):
    """Create a blog post for testing."""
    from django_cms_core.models import ContentPage

    return ContentPage.objects.create(
        page_type="post",
        title="Test Blog Post",
        slug="test-blog-post",
        status="draft",
        category=blog_category,
        excerpt="Test excerpt",
        tags=["test", "blog"],
    )


@pytest.fixture
def published_post(db, blog_category):
    """Create a published blog post for testing."""
    from django.utils import timezone
    from django_cms_core.models import ContentPage

    return ContentPage.objects.create(
        page_type="post",
        title="Published Blog Post",
        slug="published-blog-post",
        status="published",
        category=blog_category,
        published_at=timezone.now(),
    )


# ============================================================================
# Blog Post List View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogPostListView:
    """Tests for BlogPostListView."""

    def test_post_list_requires_authentication(self, client):
        """Non-authenticated users are redirected to login."""
        url = reverse("diveops:blog-post-list")
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_post_list_requires_staff(self, regular_client):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-post-list")
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_post_list_accessible_by_staff(self, staff_client):
        """Staff users can access the post list."""
        url = reverse("diveops:blog-post-list")
        response = staff_client.get(url)
        assert response.status_code == 200
        assert "Posts" in response.content.decode()

    def test_post_list_shows_posts(self, staff_client, blog_post):
        """Post list shows blog posts."""
        url = reverse("diveops:blog-post-list")
        response = staff_client.get(url)
        assert response.status_code == 200
        assert blog_post.title in response.content.decode()

    def test_post_list_filters_by_status(self, staff_client, blog_post, published_post):
        """Post list can filter by status."""
        url = reverse("diveops:blog-post-list") + "?status=draft"
        response = staff_client.get(url)
        content = response.content.decode()
        assert blog_post.title in content
        assert published_post.title not in content

    def test_post_list_filters_by_category(self, staff_client, blog_post, blog_category):
        """Post list can filter by category."""
        url = reverse("diveops:blog-post-list") + f"?category={blog_category.slug}"
        response = staff_client.get(url)
        assert response.status_code == 200
        assert blog_post.title in response.content.decode()

    def test_post_list_search(self, staff_client, blog_post):
        """Post list can search posts."""
        url = reverse("diveops:blog-post-list") + "?q=Test"
        response = staff_client.get(url)
        assert response.status_code == 200
        assert blog_post.title in response.content.decode()

    def test_post_list_shows_status_counts(self, staff_client, blog_post, published_post):
        """Post list shows status counts."""
        url = reverse("diveops:blog-post-list")
        response = staff_client.get(url)
        content = response.content.decode()
        # Check for counts in the response
        assert "Draft" in content
        assert "Published" in content


# ============================================================================
# Blog Post Create View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogPostCreateView:
    """Tests for BlogPostCreateView."""

    def test_create_post_requires_staff(self, regular_client):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-post-create")
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_create_post_accessible_by_staff(self, staff_client):
        """Staff users can access the create form."""
        url = reverse("diveops:blog-post-create")
        response = staff_client.get(url)
        assert response.status_code == 200
        assert "Create Post" in response.content.decode()

    def test_create_post_creates_post(self, staff_client, blog_category):
        """Creating a post works correctly."""
        from django_cms_core.models import ContentPage

        url = reverse("diveops:blog-post-create")
        response = staff_client.post(url, {
            "title": "New Blog Post",
            "slug": "new-blog-post",
            "status": "draft",
            "access_level": "public",
            "category": blog_category.pk,
            "excerpt": "Post excerpt",
            "tags": "tag1, tag2",
        })

        assert response.status_code == 302
        post = ContentPage.objects.get(slug="new-blog-post")
        assert post.title == "New Blog Post"
        assert post.page_type == "post"
        assert post.category == blog_category
        assert post.tags == ["tag1", "tag2"]

    def test_create_post_requires_title_and_slug(self, staff_client):
        """Creating a post requires title and slug."""
        url = reverse("diveops:blog-post-create")
        response = staff_client.post(url, {
            "title": "",
            "slug": "",
            "status": "draft",
        })
        assert response.status_code == 200
        assert "required" in response.content.decode().lower()

    def test_create_post_rejects_duplicate_slug(self, staff_client, blog_post):
        """Creating a post with duplicate slug fails."""
        url = reverse("diveops:blog-post-create")
        response = staff_client.post(url, {
            "title": "Another Post",
            "slug": blog_post.slug,  # Duplicate slug
            "status": "draft",
        })
        assert response.status_code == 200
        assert "already exists" in response.content.decode().lower()


# ============================================================================
# Blog Post Detail View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogPostDetailView:
    """Tests for BlogPostDetailView."""

    def test_post_detail_requires_staff(self, regular_client, blog_post):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-post-detail", kwargs={"pk": blog_post.pk})
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_post_detail_accessible_by_staff(self, staff_client, blog_post):
        """Staff users can access post detail."""
        url = reverse("diveops:blog-post-detail", kwargs={"pk": blog_post.pk})
        response = staff_client.get(url)
        assert response.status_code == 200
        assert blog_post.title in response.content.decode()

    def test_post_detail_shows_category(self, staff_client, blog_post):
        """Post detail shows category."""
        url = reverse("diveops:blog-post-detail", kwargs={"pk": blog_post.pk})
        response = staff_client.get(url)
        assert response.status_code == 200
        assert blog_post.category.name in response.content.decode()

    def test_post_detail_404_for_invalid_pk(self, staff_client):
        """Post detail returns 404 for invalid pk."""
        url = reverse("diveops:blog-post-detail", kwargs={"pk": uuid.uuid4()})
        response = staff_client.get(url)
        assert response.status_code == 404


# ============================================================================
# Blog Post Update View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogPostUpdateView:
    """Tests for BlogPostUpdateView."""

    def test_update_post_requires_staff(self, regular_client, blog_post):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-post-update", kwargs={"pk": blog_post.pk})
        response = regular_client.post(url, {"title": "Updated"})
        assert response.status_code == 403

    def test_update_post_updates_title(self, staff_client, blog_post):
        """Updating post title works."""
        url = reverse("diveops:blog-post-update", kwargs={"pk": blog_post.pk})
        response = staff_client.post(url, {
            "title": "Updated Title",
            "slug": blog_post.slug,
            "access_level": "public",
        })
        assert response.status_code == 302
        blog_post.refresh_from_db()
        assert blog_post.title == "Updated Title"

    def test_update_post_updates_category(self, staff_client, blog_post, db):
        """Updating post category works."""
        from django_cms_core.models import BlogCategory

        new_category = BlogCategory.objects.create(
            name="News",
            slug="news",
        )
        url = reverse("diveops:blog-post-update", kwargs={"pk": blog_post.pk})
        response = staff_client.post(url, {
            "title": blog_post.title,
            "slug": blog_post.slug,
            "access_level": "public",
            "category": new_category.pk,
        })
        assert response.status_code == 302
        blog_post.refresh_from_db()
        assert blog_post.category == new_category


# ============================================================================
# Blog Post Publish View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogPostPublishView:
    """Tests for BlogPostPublishView."""

    def test_publish_requires_staff(self, regular_client, blog_post):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-post-publish", kwargs={"pk": blog_post.pk})
        response = regular_client.post(url)
        assert response.status_code == 403

    def test_publish_requires_post(self, staff_client, blog_post):
        """Publish requires POST method."""
        url = reverse("diveops:blog-post-publish", kwargs={"pk": blog_post.pk})
        response = staff_client.get(url)
        assert response.status_code == 405

    def test_publish_publishes_draft_post(self, staff_client, blog_post):
        """Publishing a draft post works."""
        import django_cms_core.blocks  # noqa: F401 - Register block types

        url = reverse("diveops:blog-post-publish", kwargs={"pk": blog_post.pk})
        response = staff_client.post(url)
        assert response.status_code == 302
        blog_post.refresh_from_db()
        assert blog_post.status == "published"
        assert blog_post.published_at is not None


# ============================================================================
# Blog Post Unpublish View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogPostUnpublishView:
    """Tests for BlogPostUnpublishView."""

    def test_unpublish_requires_staff(self, regular_client, published_post):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-post-unpublish", kwargs={"pk": published_post.pk})
        response = regular_client.post(url)
        assert response.status_code == 403

    def test_unpublish_requires_post(self, staff_client, published_post):
        """Unpublish requires POST method."""
        url = reverse("diveops:blog-post-unpublish", kwargs={"pk": published_post.pk})
        response = staff_client.get(url)
        assert response.status_code == 405

    def test_unpublish_unpublishes_post(self, staff_client, published_post):
        """Unpublishing a published post works."""
        url = reverse("diveops:blog-post-unpublish", kwargs={"pk": published_post.pk})
        response = staff_client.post(url)
        assert response.status_code == 302
        published_post.refresh_from_db()
        assert published_post.status == "draft"


# ============================================================================
# Blog Post Delete View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogPostDeleteView:
    """Tests for BlogPostDeleteView."""

    def test_delete_requires_staff(self, regular_client, blog_post):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-post-delete", kwargs={"pk": blog_post.pk})
        response = regular_client.post(url)
        assert response.status_code == 403

    def test_delete_soft_deletes_post(self, staff_client, blog_post):
        """Deleting a post soft deletes it."""
        from django_cms_core.models import ContentPage

        url = reverse("diveops:blog-post-delete", kwargs={"pk": blog_post.pk})
        response = staff_client.post(url)
        assert response.status_code == 302

        # Post should still exist but be soft-deleted
        blog_post.refresh_from_db()
        assert blog_post.deleted_at is not None

        # Should not appear in normal queries
        assert not ContentPage.objects.filter(
            pk=blog_post.pk,
            deleted_at__isnull=True
        ).exists()


# ============================================================================
# Blog Category List View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogCategoryListView:
    """Tests for BlogCategoryListView."""

    def test_category_list_requires_authentication(self, client):
        """Non-authenticated users are redirected to login."""
        url = reverse("diveops:blog-category-list")
        response = client.get(url)
        assert response.status_code == 302

    def test_category_list_requires_staff(self, regular_client):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-category-list")
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_category_list_accessible_by_staff(self, staff_client):
        """Staff users can access the category list."""
        url = reverse("diveops:blog-category-list")
        response = staff_client.get(url)
        assert response.status_code == 200
        assert "Categories" in response.content.decode()

    def test_category_list_shows_categories(self, staff_client, blog_category):
        """Category list shows categories."""
        url = reverse("diveops:blog-category-list")
        response = staff_client.get(url)
        assert response.status_code == 200
        assert blog_category.name in response.content.decode()

    def test_category_list_shows_post_count(self, staff_client, blog_post):
        """Category list shows post count."""
        url = reverse("diveops:blog-category-list")
        response = staff_client.get(url)
        assert response.status_code == 200
        # Should show "1 post" for the category
        assert "1 post" in response.content.decode()


# ============================================================================
# Blog Category Create View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogCategoryCreateView:
    """Tests for BlogCategoryCreateView."""

    def test_create_category_requires_staff(self, regular_client):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-category-create")
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_create_category_accessible_by_staff(self, staff_client):
        """Staff users can access the create form."""
        url = reverse("diveops:blog-category-create")
        response = staff_client.get(url)
        assert response.status_code == 200
        assert "Create Category" in response.content.decode()

    def test_create_category_creates_category(self, staff_client):
        """Creating a category works correctly."""
        from django_cms_core.models import BlogCategory

        url = reverse("diveops:blog-category-create")
        response = staff_client.post(url, {
            "name": "News",
            "slug": "news",
            "description": "News posts",
            "color": "#ef4444",
            "sort_order": "1",
        })

        assert response.status_code == 302
        category = BlogCategory.objects.get(slug="news")
        assert category.name == "News"
        assert category.color == "#ef4444"

    def test_create_category_requires_name_and_slug(self, staff_client):
        """Creating a category requires name and slug."""
        url = reverse("diveops:blog-category-create")
        response = staff_client.post(url, {
            "name": "",
            "slug": "",
        })
        assert response.status_code == 200
        assert "required" in response.content.decode().lower()

    def test_create_category_rejects_duplicate_slug(self, staff_client, blog_category):
        """Creating a category with duplicate slug fails."""
        url = reverse("diveops:blog-category-create")
        response = staff_client.post(url, {
            "name": "Another Category",
            "slug": blog_category.slug,  # Duplicate slug
        })
        assert response.status_code == 200
        assert "already exists" in response.content.decode().lower()


# ============================================================================
# Blog Category Update View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogCategoryUpdateView:
    """Tests for BlogCategoryUpdateView."""

    def test_update_category_requires_staff(self, regular_client, blog_category):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-category-edit", kwargs={"pk": blog_category.pk})
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_update_category_accessible_by_staff(self, staff_client, blog_category):
        """Staff users can access the edit form."""
        url = reverse("diveops:blog-category-edit", kwargs={"pk": blog_category.pk})
        response = staff_client.get(url)
        assert response.status_code == 200
        assert blog_category.name in response.content.decode()

    def test_update_category_updates_name(self, staff_client, blog_category):
        """Updating category name works."""
        url = reverse("diveops:blog-category-edit", kwargs={"pk": blog_category.pk})
        response = staff_client.post(url, {
            "name": "Updated Tech",
            "slug": blog_category.slug,
            "description": blog_category.description,
            "color": blog_category.color,
            "sort_order": "0",
        })
        assert response.status_code == 302
        blog_category.refresh_from_db()
        assert blog_category.name == "Updated Tech"


# ============================================================================
# Blog Category Delete View Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogCategoryDeleteView:
    """Tests for BlogCategoryDeleteView."""

    def test_delete_category_requires_staff(self, regular_client, blog_category):
        """Non-staff users are forbidden."""
        url = reverse("diveops:blog-category-delete", kwargs={"pk": blog_category.pk})
        response = regular_client.post(url)
        assert response.status_code == 403

    def test_delete_category_soft_deletes(self, staff_client, blog_category):
        """Deleting a category soft deletes it."""
        from django_cms_core.models import BlogCategory

        url = reverse("diveops:blog-category-delete", kwargs={"pk": blog_category.pk})
        response = staff_client.post(url)
        assert response.status_code == 302

        # Category should still exist but be soft-deleted
        blog_category.refresh_from_db()
        assert blog_category.deleted_at is not None

        # Should not appear in normal queries
        assert not BlogCategory.objects.filter(
            pk=blog_category.pk,
            deleted_at__isnull=True
        ).exists()


# ============================================================================
# URL Pattern Tests
# ============================================================================


@pytest.mark.django_db
class TestBlogURLPatterns:
    """Tests that blog URL patterns resolve correctly."""

    def test_blog_post_list_url_resolves(self):
        """Blog post list URL resolves."""
        url = reverse("diveops:blog-post-list")
        assert url == "/staff/diveops/cms/posts/"

    def test_blog_post_create_url_resolves(self):
        """Blog post create URL resolves."""
        url = reverse("diveops:blog-post-create")
        assert url == "/staff/diveops/cms/posts/add/"

    def test_blog_post_detail_url_resolves(self, blog_post):
        """Blog post detail URL resolves."""
        url = reverse("diveops:blog-post-detail", kwargs={"pk": blog_post.pk})
        assert f"/staff/diveops/cms/posts/{blog_post.pk}/" == url

    def test_blog_category_list_url_resolves(self):
        """Blog category list URL resolves."""
        url = reverse("diveops:blog-category-list")
        assert url == "/staff/diveops/cms/categories/"

    def test_blog_category_create_url_resolves(self):
        """Blog category create URL resolves."""
        url = reverse("diveops:blog-category-create")
        assert url == "/staff/diveops/cms/categories/add/"
