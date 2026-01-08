"""Medical Provider Service.

Service layer for querying medical providers associated with dive shops.
Used by PDF service to include recommended providers in medical questionnaire PDFs.
"""

from django.db.models import QuerySet

from primitives_testbed.diveops.models import (
    MedicalProviderProfile,
    MedicalProviderRelationship,
)


def get_recommended_providers(dive_shop) -> QuerySet[MedicalProviderRelationship]:
    """Get active medical providers for a dive shop, ordered by sort_order.

    Args:
        dive_shop: Organization instance representing the dive shop

    Returns:
        QuerySet of MedicalProviderRelationship objects with provider and
        locations prefetched for efficient access.
    """
    return (
        MedicalProviderRelationship.objects.filter(
            dive_shop=dive_shop,
            is_active=True,
            provider__is_active=True,
            provider__deleted_at__isnull=True,
        )
        .select_related(
            "provider",
            "provider__organization",
        )
        .prefetch_related(
            "provider__locations",
        )
        .order_by("sort_order", "provider__sort_order")
    )


def get_primary_provider(dive_shop) -> MedicalProviderProfile | None:
    """Get primary medical provider for a dive shop.

    Args:
        dive_shop: Organization instance representing the dive shop

    Returns:
        MedicalProviderProfile if a primary provider is configured, else None.
    """
    rel = (
        MedicalProviderRelationship.objects.filter(
            dive_shop=dive_shop,
            is_primary=True,
            is_active=True,
            provider__is_active=True,
            provider__deleted_at__isnull=True,
        )
        .select_related("provider__organization")
        .first()
    )
    return rel.provider if rel else None


def get_medical_instructions() -> dict:
    """Get medical clearance instructions for PDFs.

    Returns a dictionary containing the instructions to display
    when a diver requires physician clearance.

    Returns:
        dict with title, intro, and steps keys
    """
    return {
        "title": "Instructions for Obtaining Physician Clearance",
        "intro": (
            "Your medical questionnaire responses indicate that you require "
            "a physician evaluation before participating in scuba diving or "
            "freediving activities. Please follow these steps:"
        ),
        "steps": [
            (
                "Print this document and take it to one of the recommended "
                "medical providers listed below, or to your personal physician."
            ),
            (
                "The physician will review your flagged conditions and conduct "
                "an appropriate examination."
            ),
            (
                "The physician must complete and sign the Medical Clearance Form "
                "(last page of this document)."
            ),
            (
                "Return the signed clearance form to our dive shop before your "
                "scheduled activity."
            ),
            "Clearance is valid for one year from the date of physician signature.",
        ],
        "notes": [
            (
                "If you have a pre-existing relationship with a physician familiar "
                "with your medical history, you may use them instead of our "
                "recommended providers."
            ),
            (
                "For diving-specific medical questions, physicians can consult the "
                "Divers Alert Network (DAN) at dan.org or call the DAN Medical "
                "Information Line."
            ),
            (
                "Some conditions may require specialist evaluation. Your physician "
                "will advise if this is necessary."
            ),
        ],
    }
