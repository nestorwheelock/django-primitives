"""Django admin configuration for django-cms-core."""

from django.contrib import admin

from .models import ContentPage, ContentBlock, CMSSettings, Redirect


class ContentBlockInline(admin.TabularInline):
    """Inline admin for content blocks."""

    model = ContentBlock
    extra = 1
    fields = ["block_type", "data", "sequence", "is_active"]
    ordering = ["sequence"]

    def get_queryset(self, request):
        """Exclude soft-deleted blocks."""
        return super().get_queryset(request).filter(deleted_at__isnull=True)


@admin.register(ContentPage)
class ContentPageAdmin(admin.ModelAdmin):
    """Admin for ContentPage model."""

    list_display = [
        "title",
        "slug",
        "status",
        "access_level",
        "published_at",
        "created_at",
    ]
    list_filter = ["status", "access_level", "is_indexable"]
    search_fields = ["title", "slug", "seo_title", "seo_description"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "published_at",
        "published_by",
        "published_snapshot",
    ]
    inlines = [ContentBlockInline]

    fieldsets = [
        (None, {
            "fields": ["title", "slug", "status", "template_key"],
        }),
        ("Access Control", {
            "fields": ["access_level", "required_roles", "required_entitlements"],
            "classes": ["collapse"],
        }),
        ("SEO", {
            "fields": [
                "seo_title",
                "seo_description",
                "og_image_url",
                "canonical_url",
                "robots",
                "is_indexable",
            ],
            "classes": ["collapse"],
        }),
        ("Display", {
            "fields": ["sort_order", "metadata"],
            "classes": ["collapse"],
        }),
        ("Publishing", {
            "fields": ["published_at", "published_by", "published_snapshot"],
            "classes": ["collapse"],
        }),
        ("System", {
            "fields": ["id", "created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_queryset(self, request):
        """Exclude soft-deleted pages."""
        return super().get_queryset(request).filter(deleted_at__isnull=True)


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    """Admin for ContentBlock model."""

    list_display = ["block_type", "page", "sequence", "is_active", "created_at"]
    list_filter = ["block_type", "is_active"]
    search_fields = ["page__title", "page__slug"]
    readonly_fields = ["id", "created_at", "updated_at"]

    def get_queryset(self, request):
        """Exclude soft-deleted blocks."""
        return super().get_queryset(request).filter(deleted_at__isnull=True)


@admin.register(CMSSettings)
class CMSSettingsAdmin(admin.ModelAdmin):
    """Admin for CMSSettings singleton."""

    list_display = ["site_name", "api_cache_ttl_seconds"]

    fieldsets = [
        ("Site", {
            "fields": ["site_name"],
        }),
        ("Hooks", {
            "fields": ["media_url_resolver_path", "entitlement_checker_path"],
        }),
        ("Default SEO", {
            "fields": ["default_seo_title_suffix", "default_og_image_url"],
        }),
        ("Navigation", {
            "fields": ["nav_json", "footer_json"],
            "classes": ["collapse"],
        }),
        ("API", {
            "fields": ["api_cache_ttl_seconds"],
        }),
        ("Other", {
            "fields": ["metadata"],
            "classes": ["collapse"],
        }),
    ]

    def has_add_permission(self, request):
        """Prevent adding more than one settings instance."""
        return not CMSSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting the settings instance."""
        return False


@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    """Admin for Redirect model."""

    list_display = ["from_path", "to_path", "is_permanent", "created_at"]
    list_filter = ["is_permanent"]
    search_fields = ["from_path", "to_path"]
    readonly_fields = ["id", "created_at", "updated_at"]

    def get_queryset(self, request):
        """Exclude soft-deleted redirects."""
        return super().get_queryset(request).filter(deleted_at__isnull=True)
