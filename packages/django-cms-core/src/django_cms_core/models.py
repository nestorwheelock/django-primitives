"""Models for django-cms-core.

Domain-agnostic CMS models for managing content pages, blocks, and settings.
"""

from django.conf import settings
from django.db import models

from django_basemodels import BaseModel
from django_singleton import SingletonModel


class PageStatus(models.TextChoices):
    """Status choices for content pages."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class AccessLevel(models.TextChoices):
    """Access level choices for content pages."""

    PUBLIC = "public", "Public"
    AUTHENTICATED = "authenticated", "Authenticated Users"
    ROLE = "role", "Role-based"
    ENTITLEMENT = "entitlement", "Entitlement-based"


class ContentPage(BaseModel):
    """Content page with publishing workflow and access control.

    Represents a single page of content that can be drafted, published,
    and archived. Supports block-based content, SEO fields, and
    configurable access control.

    Attributes:
        slug: URL-safe identifier, unique among non-deleted pages
        title: Display title for the page
        status: Current page status (draft, published, archived)
        access_level: Who can access this page
        required_roles: List of role slugs required for role-based access
        required_entitlements: List of entitlement codes for entitlement access
        seo_title: Custom title for search engines (max 70 chars)
        seo_description: Meta description (max 160 chars)
        og_image_url: Open Graph image URL
        canonical_url: Canonical URL for SEO
        robots: robots meta tag value
        published_snapshot: Immutable JSON snapshot at publish time
        published_at: When the page was last published
        published_by: Who published the page
        sort_order: For manual ordering in listings
        is_indexable: Whether to include in sitemaps
        template_key: Hint for template selection
        metadata: Arbitrary JSON for custom data
    """

    # Identity
    slug = models.SlugField(max_length=200, db_index=True)
    title = models.CharField(max_length=255)

    # Status
    status = models.CharField(
        max_length=20,
        choices=PageStatus.choices,
        default=PageStatus.DRAFT,
    )

    # Access Control
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC,
    )
    required_roles = models.JSONField(default=list, blank=True)
    required_entitlements = models.JSONField(default=list, blank=True)

    # SEO
    seo_title = models.CharField(max_length=70, blank=True, default="")
    seo_description = models.CharField(max_length=160, blank=True, default="")
    og_image_url = models.CharField(max_length=500, blank=True, default="")
    canonical_url = models.CharField(max_length=500, blank=True, default="")
    robots = models.CharField(max_length=50, default="index, follow")

    # Publishing
    published_snapshot = models.JSONField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_pages",
    )

    # Display
    sort_order = models.IntegerField(default=0)
    is_indexable = models.BooleanField(default=True)

    # Template hint
    template_key = models.CharField(max_length=100, default="default")

    # Extensibility
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_page_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["slug", "status"]),
            models.Index(fields=["status", "published_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.slug})"


class ContentBlock(BaseModel):
    """Block of content within a page.

    Represents a single content block with a type and data payload.
    Blocks are ordered by sequence within their parent page.

    Attributes:
        page: Parent content page
        block_type: Registry key identifying the block type
        data: JSON payload for block content
        sequence: Order within the page (lower = earlier)
        is_active: Whether block is included in renders
    """

    page = models.ForeignKey(
        ContentPage,
        on_delete=models.CASCADE,
        related_name="blocks",
    )
    block_type = models.CharField(max_length=50, db_index=True)
    data = models.JSONField(default=dict)
    sequence = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["page", "sequence"]
        indexes = [
            models.Index(fields=["page", "sequence"]),
        ]

    def __str__(self):
        return f"{self.block_type} (seq {self.sequence})"


class CMSSettings(SingletonModel):
    """Global CMS configuration singleton.

    Stores site-wide settings including hook paths, default SEO values,
    navigation structure, and API configuration.

    Attributes:
        site_name: Display name for the site
        media_url_resolver_path: Dotted path to media URL resolver function
        entitlement_checker_path: Dotted path to entitlement check function
        default_seo_title_suffix: Appended to page titles for SEO
        default_og_image_url: Default Open Graph image
        nav_json: Navigation structure for renderers
        footer_json: Footer structure for renderers
        api_cache_ttl_seconds: Cache TTL for API responses
        metadata: Arbitrary JSON for custom settings
    """

    # Site identity
    site_name = models.CharField(max_length=255, blank=True, default="")

    # Hook paths (dotted Python paths)
    media_url_resolver_path = models.CharField(max_length=255, blank=True, default="")
    entitlement_checker_path = models.CharField(max_length=255, blank=True, default="")

    # Default SEO
    default_seo_title_suffix = models.CharField(max_length=100, blank=True, default="")
    default_og_image_url = models.CharField(max_length=500, blank=True, default="")

    # Navigation (for renderers)
    nav_json = models.JSONField(default=list, blank=True)
    footer_json = models.JSONField(default=dict, blank=True)

    # API settings
    api_cache_ttl_seconds = models.PositiveIntegerField(default=60)

    # Extensibility
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "CMS Settings"
        verbose_name_plural = "CMS Settings"

    def __str__(self):
        return f"CMS Settings ({self.site_name or 'Unnamed Site'})"


class Redirect(BaseModel):
    """URL redirect rule.

    Stores redirect mappings from old paths to new paths.
    Supports both permanent (301) and temporary (302) redirects.

    Attributes:
        from_path: Source path to redirect from
        to_path: Destination path to redirect to
        is_permanent: True for 301, False for 302
    """

    from_path = models.CharField(max_length=500)
    to_path = models.CharField(max_length=500)
    is_permanent = models.BooleanField(default=False)

    class Meta:
        ordering = ["from_path"]
        constraints = [
            models.UniqueConstraint(
                fields=["from_path"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_redirect_from_path",
            ),
        ]

    def __str__(self):
        redirect_type = "301" if self.is_permanent else "302"
        return f"{self.from_path} -> {self.to_path} ({redirect_type})"
