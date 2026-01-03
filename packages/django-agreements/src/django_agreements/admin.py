"""Django admin configuration for agreements."""

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from .models import Agreement, AgreementVersion


class AgreementVersionInline(admin.TabularInline):
    """Inline for viewing agreement versions."""

    model = AgreementVersion
    extra = 0
    readonly_fields = ['version', 'terms', 'created_by', 'reason', 'created_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Agreement)
class AgreementAdmin(admin.ModelAdmin):
    """Admin for Agreement model."""

    list_display = [
        'id',
        'get_party_a',
        'get_party_b',
        'scope_type',
        'current_version',
        'valid_from',
        'valid_to',
        'is_active',
    ]
    list_filter = ['scope_type', 'valid_from']
    search_fields = ['party_a_id', 'party_b_id', 'scope_type']
    readonly_fields = [
        'id',
        'party_a_content_type',
        'party_a_id',
        'get_party_a',
        'party_b_content_type',
        'party_b_id',
        'get_party_b',
        'scope_ref_content_type',
        'scope_ref_id',
        'current_version',
        'agreed_at',
        'agreed_by',
        'created_at',
        'updated_at',
    ]
    fieldsets = [
        ('Agreement Info', {
            'fields': ['id', 'scope_type', 'current_version']
        }),
        ('Parties', {
            'fields': ['get_party_a', 'get_party_b']
        }),
        ('Terms', {
            'fields': ['terms']
        }),
        ('Validity', {
            'fields': ['valid_from', 'valid_to', 'agreed_at', 'agreed_by']
        }),
        ('Scope Reference', {
            'fields': ['scope_ref_content_type', 'scope_ref_id'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    inlines = [AgreementVersionInline]

    def get_party_a(self, obj):
        """Display party A."""
        return str(obj.party_a) if obj.party_a else '-'
    get_party_a.short_description = 'Party A'

    def get_party_b(self, obj):
        """Display party B."""
        return str(obj.party_b) if obj.party_b else '-'
    get_party_b.short_description = 'Party B'

    def is_active(self, obj):
        """Display active status."""
        return obj.is_active
    is_active.boolean = True
    is_active.short_description = 'Active'


@admin.register(AgreementVersion)
class AgreementVersionAdmin(admin.ModelAdmin):
    """Admin for AgreementVersion model (read-only)."""

    list_display = ['agreement', 'version', 'created_by', 'created_at']
    list_filter = ['created_at']
    readonly_fields = [
        'id',
        'agreement',
        'version',
        'terms',
        'created_by',
        'reason',
        'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
