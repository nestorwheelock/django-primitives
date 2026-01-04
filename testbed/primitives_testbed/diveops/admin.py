"""Django admin configuration for diveops models."""

from django.contrib import admin

from .models import (
    Booking,
    CertificationLevel,
    DiverCertification,
    DiverProfile,
    DiveSite,
    DiveTrip,
    TripRequirement,
    TripRoster,
)


@admin.register(CertificationLevel)
class CertificationLevelAdmin(admin.ModelAdmin):
    """Admin for CertificationLevel model."""

    list_display = ["code", "name", "rank", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["code", "name"]
    ordering = ["rank"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(DiverCertification)
class DiverCertificationAdmin(admin.ModelAdmin):
    """Admin for DiverCertification model."""

    list_display = [
        "diver",
        "level",
        "agency",
        "certification_number",
        "certified_on",
        "expires_on",
        "is_verified",
    ]
    list_filter = ["level", "is_verified", "agency"]
    search_fields = [
        "diver__person__first_name",
        "diver__person__last_name",
        "certification_number",
    ]
    raw_id_fields = ["diver", "agency", "verified_by"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "certified_on"


@admin.register(TripRequirement)
class TripRequirementAdmin(admin.ModelAdmin):
    """Admin for TripRequirement model."""

    list_display = [
        "trip",
        "requirement_type",
        "certification_level",
        "min_dives",
        "is_mandatory",
    ]
    list_filter = ["requirement_type", "is_mandatory"]
    search_fields = ["trip__dive_site__name", "description"]
    raw_id_fields = ["trip", "certification_level"]
    readonly_fields = ["id", "created_at", "updated_at"]


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
    search_fields = ["person__first_name", "person__last_name", "person__email"]
    raw_id_fields = ["person"]
    readonly_fields = ["id", "created_at", "updated_at"]


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


@admin.register(DiveTrip)
class DiveTripAdmin(admin.ModelAdmin):
    """Admin for DiveTrip model."""

    list_display = [
        "dive_site",
        "dive_shop",
        "departure_time",
        "status",
        "max_divers",
        "spots_available",
    ]
    list_filter = ["status", "dive_shop"]
    search_fields = ["dive_site__name", "dive_shop__name"]
    raw_id_fields = ["dive_shop", "dive_site", "encounter", "created_by"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "departure_time"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Admin for Booking model."""

    list_display = ["trip", "diver", "status", "created_at"]
    list_filter = ["status"]
    search_fields = [
        "diver__person__first_name",
        "diver__person__last_name",
        "trip__dive_site__name",
    ]
    raw_id_fields = ["trip", "diver", "basket", "invoice", "waiver_agreement", "booked_by"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(TripRoster)
class TripRosterAdmin(admin.ModelAdmin):
    """Admin for TripRoster model."""

    list_display = ["trip", "diver", "role", "checked_in_at", "dive_completed"]
    list_filter = ["role", "dive_completed"]
    search_fields = [
        "diver__person__first_name",
        "diver__person__last_name",
        "trip__dive_site__name",
    ]
    raw_id_fields = ["trip", "diver", "booking", "checked_in_by"]
    readonly_fields = ["id"]
