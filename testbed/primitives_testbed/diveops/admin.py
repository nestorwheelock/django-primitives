"""Django admin configuration for diveops models."""

from django.contrib import admin

from .models import (
    Booking,
    CertificationLevel,
    Dive,
    DiverCertification,
    DiverEligibilityProof,
    DiverProfile,
    DiveSegmentType,
    DiveSite,
    EmailSettings,
    EmailTemplate,
    Excursion,
    ExcursionRoster,
    ProtectedArea,
    ProtectedAreaFeeSchedule,
    ProtectedAreaFeeTier,
    ProtectedAreaRule,
    ProtectedAreaZone,
    Trip,
)




@admin.register(CertificationLevel)
class CertificationLevelAdmin(admin.ModelAdmin):
    """Admin for CertificationLevel model."""

    list_display = ["code", "name", "agency", "rank", "max_depth_m", "is_active", "created_at"]
    list_filter = ["is_active", "agency"]
    list_select_related = ["agency"]
    search_fields = ["code", "name", "agency__name"]
    ordering = ["agency", "rank"]
    autocomplete_fields = ["agency"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(DiverCertification)
class DiverCertificationAdmin(admin.ModelAdmin):
    """Admin for DiverCertification model."""

    list_display = [
        "diver",
        "level",
        "get_agency",
        "card_number",
        "issued_on",
        "expires_on",
        "is_verified",
        "has_proof",
    ]
    list_filter = ["level__agency", "is_verified"]
    list_select_related = ["diver__person", "level__agency"]
    search_fields = [
        "diver__person__first_name",
        "diver__person__last_name",
        "card_number",
        "level__agency__name",
    ]
    raw_id_fields = ["diver", "verified_by", "proof_document"]
    autocomplete_fields = ["level"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "issued_on"

    @admin.display(description="Agency")
    def get_agency(self, obj):
        return obj.level.agency.name if obj.level else "-"

    @admin.display(boolean=True, description="Proof")
    def has_proof(self, obj):
        return obj.proof_document is not None


@admin.register(DiverProfile)
class DiverProfileAdmin(admin.ModelAdmin):
    """Admin for DiverProfile model."""

    list_display = [
        "person",
        "certification_level",
        "certification_agency",
        "total_dives",
        "is_medical_current",
    ]
    list_filter = ["certification_level", "certification_agency"]
    list_select_related = ["person", "certification_agency"]
    search_fields = ["person__first_name", "person__last_name", "person__email"]
    raw_id_fields = ["person"]
    autocomplete_fields = ["certification_agency"]  # Search for certification agencies
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(DiveSegmentType)
class DiveSegmentTypeAdmin(admin.ModelAdmin):
    """Admin for DiveSegmentType model (dive profile segment types)."""

    list_display = [
        "name",
        "display_name",
        "is_depth_transition",
        "color",
        "sort_order",
        "is_active",
    ]
    list_filter = ["is_active", "is_depth_transition"]
    search_fields = ["name", "display_name", "description"]
    ordering = ["sort_order", "display_name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    list_editable = ["sort_order", "is_active"]

    fieldsets = (
        (None, {
            "fields": ("name", "display_name", "description")
        }),
        ("Display", {
            "fields": ("color", "sort_order", "is_active")
        }),
        ("Behavior", {
            "fields": ("is_depth_transition",),
            "description": "Depth transition segments (descent/ascent) have from/to depth fields instead of a single depth."
        }),
        ("System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(DiveSite)
class DiveSiteAdmin(admin.ModelAdmin):
    """Admin for DiveSite model."""

    list_display = [
        "name",
        "max_depth_meters",
        "min_certification_level",
        "difficulty",
        "is_active",
    ]
    list_filter = ["min_certification_level", "difficulty", "is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    """Admin for Trip model (commercial package)."""

    list_display = [
        "name",
        "dive_shop",
        "start_date",
        "end_date",
        "status",
        "excursion_count",
    ]
    list_filter = ["status", "dive_shop"]
    list_select_related = ["dive_shop", "catalog_item"]
    search_fields = ["name", "dive_shop__name"]
    raw_id_fields = ["dive_shop", "catalog_item", "created_by"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "start_date"

    @admin.display(description="Excursions")
    def excursion_count(self, obj):
        return obj.excursions.count()


@admin.register(Excursion)
class ExcursionAdmin(admin.ModelAdmin):
    """Admin for Excursion model (operational outing)."""

    list_display = [
        "dive_site",
        "dive_shop",
        "trip",
        "departure_time",
        "status",
        "max_divers",
        "spots_available",
    ]
    list_filter = ["status", "dive_shop"]
    list_select_related = ["dive_site", "dive_shop", "trip"]
    search_fields = ["dive_site__name", "dive_shop__name", "trip__name"]
    raw_id_fields = ["dive_shop", "dive_site", "trip", "encounter", "created_by"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "departure_time"




@admin.register(Dive)
class DiveAdmin(admin.ModelAdmin):
    """Admin for Dive model (atomic loggable unit)."""

    list_display = [
        "excursion",
        "dive_site",
        "sequence",
        "planned_start",
        "actual_start",
        "max_depth_meters",
        "bottom_time_minutes",
    ]
    list_filter = ["excursion__dive_shop"]
    list_select_related = ["excursion", "dive_site"]
    search_fields = ["dive_site__name", "excursion__dive_site__name"]
    raw_id_fields = ["excursion", "dive_site"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Admin for Booking model."""

    list_display = ["excursion", "diver", "status", "created_at"]
    list_filter = ["status"]
    list_select_related = ["excursion__dive_site", "diver__person"]
    search_fields = [
        "diver__person__first_name",
        "diver__person__last_name",
        "excursion__dive_site__name",
    ]
    raw_id_fields = ["excursion", "diver", "basket", "invoice", "waiver_agreement", "booked_by"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(ExcursionRoster)
class ExcursionRosterAdmin(admin.ModelAdmin):
    """Admin for ExcursionRoster model."""

    list_display = ["excursion", "diver", "role", "checked_in_at", "dive_completed"]
    list_filter = ["role", "dive_completed"]
    list_select_related = ["excursion__dive_site", "diver__person"]
    search_fields = [
        "diver__person__first_name",
        "diver__person__last_name",
        "excursion__dive_site__name",
    ]
    raw_id_fields = ["excursion", "diver", "booking", "checked_in_by"]
    readonly_fields = ["id"]




# =============================================================================
# Marine Park Admin
# =============================================================================


@admin.register(ProtectedArea)
class ProtectedAreaAdmin(admin.ModelAdmin):
    """Admin for ProtectedArea model."""

    list_display = [
        "name",
        "code",
        "designation_type",
        "governing_authority",
        "is_active",
        "zone_count",
    ]
    list_filter = ["designation_type", "is_active"]
    search_fields = ["name", "code", "governing_authority"]
    prepopulated_fields = {"code": ("name",)}
    raw_id_fields = ["place"]
    readonly_fields = ["id", "created_at", "updated_at"]

    @admin.display(description="Zones")
    def zone_count(self, obj):
        return obj.zones.count()


@admin.register(ProtectedAreaZone)
class ProtectedAreaZoneAdmin(admin.ModelAdmin):
    """Admin for ProtectedAreaZone model."""

    list_display = [
        "name",
        "code",
        "protected_area",
        "zone_type",
        "diving_allowed",
        "requires_guide",
        "is_active",
    ]
    list_filter = ["zone_type", "diving_allowed", "requires_guide", "is_active", "protected_area"]
    list_select_related = ["protected_area"]
    search_fields = ["name", "code", "protected_area__name"]
    prepopulated_fields = {"code": ("name",)}
    raw_id_fields = ["protected_area"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(ProtectedAreaRule)
class ProtectedAreaRuleAdmin(admin.ModelAdmin):
    """Admin for ProtectedAreaRule model."""

    list_display = [
        "subject",
        "protected_area",
        "zone",
        "rule_type",
        "activity",
        "enforcement_level",
        "effective_start",
        "is_active",
    ]
    list_filter = ["rule_type", "activity", "enforcement_level", "is_active", "protected_area"]
    list_select_related = ["protected_area", "zone"]
    search_fields = ["subject", "details", "protected_area__name"]
    raw_id_fields = ["protected_area", "zone", "source_document"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "effective_start"


@admin.register(ProtectedAreaFeeSchedule)
class ProtectedAreaFeeScheduleAdmin(admin.ModelAdmin):
    """Admin for ProtectedAreaFeeSchedule model."""

    list_display = [
        "name",
        "protected_area",
        "fee_type",
        "applies_to",
        "currency",
        "effective_start",
        "is_active",
    ]
    list_filter = ["fee_type", "applies_to", "is_active", "protected_area"]
    list_select_related = ["protected_area", "zone"]
    search_fields = ["name", "protected_area__name"]
    raw_id_fields = ["protected_area", "zone", "catalog_item"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "effective_start"


@admin.register(ProtectedAreaFeeTier)
class ProtectedAreaFeeTierAdmin(admin.ModelAdmin):
    """Admin for ProtectedAreaFeeTier model."""

    list_display = [
        "label",
        "tier_code",
        "schedule",
        "amount",
        "priority",
        "requires_proof",
    ]
    list_filter = ["tier_code", "requires_proof", "schedule__protected_area"]
    list_select_related = ["schedule__protected_area"]
    search_fields = ["label", "schedule__name"]
    raw_id_fields = ["schedule"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(DiverEligibilityProof)
class DiverEligibilityProofAdmin(admin.ModelAdmin):
    """Admin for DiverEligibilityProof model."""

    list_display = [
        "diver",
        "proof_type",
        "status",
        "verified_by",
        "verified_at",
        "expires_at",
    ]
    list_filter = ["proof_type", "status"]
    list_select_related = ["diver__person", "verified_by"]
    search_fields = ["diver__person__first_name", "diver__person__last_name"]
    raw_id_fields = ["diver", "document", "verified_by"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "verified_at"


# =============================================================================
# Email Settings Admin
# =============================================================================


@admin.register(EmailSettings)
class EmailSettingsAdmin(admin.ModelAdmin):
    """Admin for EmailSettings singleton model.

    Provides DB-first configuration for email sending via Amazon SES.
    Only superusers can edit sensitive credential fields.
    """

    fieldsets = (
        ("General", {
            "fields": ("enabled", "provider", "sandbox_mode"),
            "description": "Master controls for email sending."
        }),
        ("Sender Identity", {
            "fields": ("default_from_email", "default_from_name", "reply_to_email"),
            "description": "Sender address must be verified in SES."
        }),
        ("AWS SES Configuration", {
            "fields": ("aws_region", "configuration_set"),
        }),
        ("AWS Credentials", {
            "fields": ("aws_access_key_id", "aws_secret_access_key"),
            "description": "Only superusers can edit these fields.",
            "classes": ("collapse",),
        }),
        ("SMTP Configuration (Future)", {
            "fields": ("smtp_host", "smtp_port", "smtp_username", "smtp_password"),
            "description": "For future SMTP provider support.",
            "classes": ("collapse",),
        }),
    )

    def has_add_permission(self, request):
        """Prevent adding additional instances (singleton)."""
        return not EmailSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting the singleton instance."""
        return False

    def get_readonly_fields(self, request, obj=None):
        """Make credential fields readonly for non-superusers."""
        readonly = []
        if not request.user.is_superuser:
            readonly.extend([
                "aws_access_key_id",
                "aws_secret_access_key",
                "smtp_password",
            ])
        return readonly

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """Add configuration status to the change form."""
        extra_context = extra_context or {}
        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                extra_context["is_configured"] = obj.is_configured()
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Admin for EmailTemplate model.

    Provides editing of email templates with preview capability.
    """

    list_display = [
        "key",
        "name",
        "is_active",
        "updated_at",
        "updated_by",
    ]
    list_filter = ["is_active"]
    search_fields = ["key", "name", "subject_template"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["updated_by"]
    prepopulated_fields = {"key": ("name",)}
    ordering = ["key"]

    fieldsets = (
        (None, {
            "fields": ("key", "name", "is_active"),
        }),
        ("Subject", {
            "fields": ("subject_template",),
            "description": "Email subject line. Supports Django template syntax: {{ variable }}",
        }),
        ("Plain Text Body", {
            "fields": ("body_text_template",),
            "description": "Required. Plain text version of the email.",
        }),
        ("HTML Body", {
            "fields": ("body_html_template",),
            "description": "Optional. HTML version of the email.",
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("updated_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    actions = ["preview_template"]

    @admin.action(description="Preview template with sample context")
    def preview_template(self, request, queryset):
        """Preview selected templates with sample context."""
        from django.contrib import messages
        from django.template import Context, Template

        # Sample context for preview
        sample_context = {
            "user_name": "John Doe",
            "verify_url": "https://example.com/verify?token=abc123",
            "dashboard_url": "https://example.com/dashboard",
            "reset_url": "https://example.com/reset?token=xyz789",
            "site_name": "DiveOps",
        }

        for template in queryset:
            try:
                django_context = Context(sample_context)
                subject = Template(template.subject_template).render(django_context).strip()
                text = Template(template.body_text_template).render(django_context)[:200]

                messages.info(
                    request,
                    f"Template '{template.key}': Subject='{subject}' | Text preview: {text}..."
                )
            except Exception as e:
                messages.error(request, f"Template '{template.key}' error: {e}")

    def save_model(self, request, obj, form, change):
        """Automatically set updated_by to current user."""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
