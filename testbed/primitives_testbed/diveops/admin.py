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
    Excursion,
    ExcursionRoster,
    MarinePark,
    ParkFeeSchedule,
    ParkFeeTier,
    ParkGuideCredential,
    ParkRule,
    ParkZone,
    Trip,
    VesselPermit,
)

# Backwards compatibility aliases
DiveTrip = Excursion
TripRoster = ExcursionRoster


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


# Backwards compatibility alias
DiveTripAdmin = ExcursionAdmin


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


# Backwards compatibility alias
TripRosterAdmin = ExcursionRosterAdmin


# =============================================================================
# Marine Park Admin
# =============================================================================


@admin.register(MarinePark)
class MarineParkAdmin(admin.ModelAdmin):
    """Admin for MarinePark model."""

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


@admin.register(ParkZone)
class ParkZoneAdmin(admin.ModelAdmin):
    """Admin for ParkZone model."""

    list_display = [
        "name",
        "code",
        "marine_park",
        "zone_type",
        "diving_allowed",
        "requires_guide",
        "is_active",
    ]
    list_filter = ["zone_type", "diving_allowed", "requires_guide", "is_active", "marine_park"]
    list_select_related = ["marine_park"]
    search_fields = ["name", "code", "marine_park__name"]
    prepopulated_fields = {"code": ("name",)}
    raw_id_fields = ["marine_park"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(ParkRule)
class ParkRuleAdmin(admin.ModelAdmin):
    """Admin for ParkRule model."""

    list_display = [
        "subject",
        "marine_park",
        "zone",
        "rule_type",
        "activity",
        "enforcement_level",
        "effective_start",
        "is_active",
    ]
    list_filter = ["rule_type", "activity", "enforcement_level", "is_active", "marine_park"]
    list_select_related = ["marine_park", "zone"]
    search_fields = ["subject", "details", "marine_park__name"]
    raw_id_fields = ["marine_park", "zone", "source_document"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "effective_start"


@admin.register(ParkFeeSchedule)
class ParkFeeScheduleAdmin(admin.ModelAdmin):
    """Admin for ParkFeeSchedule model."""

    list_display = [
        "name",
        "marine_park",
        "fee_type",
        "applies_to",
        "currency",
        "effective_start",
        "is_active",
    ]
    list_filter = ["fee_type", "applies_to", "is_active", "marine_park"]
    list_select_related = ["marine_park", "zone"]
    search_fields = ["name", "marine_park__name"]
    raw_id_fields = ["marine_park", "zone", "catalog_item"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "effective_start"


@admin.register(ParkFeeTier)
class ParkFeeTierAdmin(admin.ModelAdmin):
    """Admin for ParkFeeTier model."""

    list_display = [
        "label",
        "tier_code",
        "schedule",
        "amount",
        "priority",
        "requires_proof",
    ]
    list_filter = ["tier_code", "requires_proof", "schedule__marine_park"]
    list_select_related = ["schedule__marine_park"]
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


@admin.register(ParkGuideCredential)
class ParkGuideCredentialAdmin(admin.ModelAdmin):
    """Admin for ParkGuideCredential model."""

    list_display = [
        "diver",
        "marine_park",
        "credential_number",
        "issued_at",
        "expires_at",
        "is_active",
        "is_refresher_due",
    ]
    list_filter = ["is_active", "is_owner", "marine_park"]
    list_select_related = ["diver__person", "marine_park"]
    search_fields = ["diver__person__first_name", "diver__person__last_name", "credential_number"]
    raw_id_fields = ["diver", "marine_park", "carta_eval_agreement", "carta_eval_signed_by"]
    filter_horizontal = ["authorized_zones"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "issued_at"


@admin.register(VesselPermit)
class VesselPermitAdmin(admin.ModelAdmin):
    """Admin for VesselPermit model."""

    list_display = [
        "vessel_name",
        "permit_number",
        "marine_park",
        "operator",
        "issued_at",
        "expires_at",
        "is_active",
    ]
    list_filter = ["is_active", "marine_park"]
    list_select_related = ["marine_park", "operator"]
    search_fields = ["vessel_name", "permit_number", "operator__name"]
    raw_id_fields = ["marine_park", "operator"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "issued_at"
