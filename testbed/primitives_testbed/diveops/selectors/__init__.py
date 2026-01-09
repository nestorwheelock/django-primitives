"""Selectors for DiveOps.

Provides optimized, read-only queries for various DiveOps entities.
All selectors use select_related/prefetch_related to avoid N+1 problems.
"""

from .divers import (
    get_diver_with_full_context,
    get_diver_person_details,
    get_diver_normalized_contacts,
    get_diver_emergency_contacts,
    get_diver_relationships,
    get_diver_booking_history,
    get_diver_dive_history,
    get_diver_medical_details,
    calculate_age,
)

from .excursions import (
    list_upcoming_excursions,
    get_excursion_with_roster,
    list_diver_bookings,
    get_diver_profile,
    get_current_diver,
    list_dive_sites,
    list_shop_excursions,
    get_booking,
    get_diver_with_certifications,
    get_excursion_with_requirements,
    list_certification_levels,
    get_diver_highest_certification,
    diver_audit_feed,
    excursion_audit_feed,
    get_diver_medical_status,
    list_diver_documents,
    list_diver_signed_agreements,
    list_diver_briefings,
    list_diver_waivers,
    list_diver_pending_agreements,
    list_diver_dive_logs,
    get_diver_dive_stats,
    get_diver_category,
    get_required_agreements_for_diver,
    get_diver_agreement_status,
)

__all__ = [
    # Diver profile selectors
    "get_diver_with_full_context",
    "get_diver_person_details",
    "get_diver_normalized_contacts",
    "get_diver_emergency_contacts",
    "get_diver_relationships",
    "get_diver_booking_history",
    "get_diver_dive_history",
    "get_diver_medical_details",
    "calculate_age",
    # Excursion and booking selectors
    "list_upcoming_excursions",
    "get_excursion_with_roster",
    "list_diver_bookings",
    "get_diver_profile",
    "get_current_diver",
    "list_dive_sites",
    "list_shop_excursions",
    "get_booking",
    "get_diver_with_certifications",
    "get_excursion_with_requirements",
    "list_certification_levels",
    "get_diver_highest_certification",
    "diver_audit_feed",
    "excursion_audit_feed",
    "get_diver_medical_status",
    "list_diver_documents",
    "list_diver_signed_agreements",
    "list_diver_briefings",
    "list_diver_waivers",
    "list_diver_pending_agreements",
    "list_diver_dive_logs",
    "get_diver_dive_stats",
    "get_diver_category",
    "get_required_agreements_for_diver",
    "get_diver_agreement_status",
]
