"""Selectors for dive operations.

Read-only queries optimized to avoid N+1 problems.
All selectors use select_related and prefetch_related.
"""

from datetime import datetime
from typing import Optional

from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from django_parties.models import Person

from .models import (
    Booking,
    CertificationLevel,
    Dive,
    DiverCertification,
    DiverProfile,
    DiveLog,
    DiveSite,
    Excursion,
    ExcursionRequirement,
    ExcursionRoster,
    SignableAgreement,
)

# Backwards compatibility aliases
DiveTrip = Excursion
TripRequirement = ExcursionRequirement
TripRoster = ExcursionRoster


def list_upcoming_excursions(
    dive_shop=None,
    dive_site=None,
    min_spots: int = 0,
    limit: int = 50,
) -> list[Excursion]:
    """List upcoming dive excursions with optional filters.

    Optimized query with related data prefetched.

    Args:
        dive_shop: Filter by dive shop (optional)
        dive_site: Filter by dive site (optional)
        min_spots: Minimum available spots (default 0 = all)
        limit: Maximum results

    Returns:
        List of Excursion objects with related data
    """
    qs = (
        Excursion.objects.filter(
            departure_time__gt=timezone.now(),
            status__in=["scheduled", "boarding"],
        )
        .select_related("dive_shop", "dive_site", "trip")
        .prefetch_related(
            Prefetch(
                "bookings",
                queryset=Booking.objects.filter(status__in=["confirmed", "checked_in"]),
            )
        )
        .annotate(
            confirmed_count=Count(
                "bookings",
                filter=Q(bookings__status__in=["confirmed", "checked_in"]),
            )
        )
        .order_by("departure_time")
    )

    if dive_shop:
        qs = qs.filter(dive_shop=dive_shop)

    if dive_site:
        qs = qs.filter(dive_site=dive_site)

    excursions = list(qs[:limit])

    if min_spots > 0:
        excursions = [e for e in excursions if e.spots_available >= min_spots]

    return excursions


# Backwards compatibility alias
list_upcoming_trips = list_upcoming_excursions


def get_excursion_with_roster(excursion_id) -> Optional[Excursion]:
    """Get an excursion with full roster data.

    Optimized query for excursion detail view.

    Args:
        excursion_id: Excursion UUID

    Returns:
        Excursion or None
    """
    return (
        Excursion.objects.filter(pk=excursion_id)
        .select_related("dive_shop", "dive_site", "trip", "encounter")
        .prefetch_related(
            Prefetch(
                "bookings",
                queryset=Booking.objects.select_related("diver__person"),
            ),
            Prefetch(
                "roster",
                queryset=ExcursionRoster.objects.select_related(
                    "diver__person", "checked_in_by"
                ),
            ),
            Prefetch(
                "dives",
                queryset=Dive.objects.select_related("dive_site").order_by("sequence"),
            ),
        )
        .first()
    )


# Backwards compatibility alias
get_trip_with_roster = get_excursion_with_roster


def list_diver_bookings(
    diver: DiverProfile,
    status: Optional[str] = None,
    include_past: bool = False,
    limit: int = 50,
) -> list[Booking]:
    """List bookings for a diver.

    Optimized query with excursion and site data.

    Args:
        diver: The diver profile
        status: Filter by status (optional)
        include_past: Include past excursions (default False)
        limit: Maximum results

    Returns:
        List of Booking objects
    """
    qs = (
        Booking.objects.filter(diver=diver)
        .select_related("excursion__dive_shop", "excursion__dive_site")
        .order_by("-excursion__departure_time")
    )

    if status:
        qs = qs.filter(status=status)

    if not include_past:
        qs = qs.filter(excursion__departure_time__gt=timezone.now())

    return list(qs[:limit])


def get_diver_profile(person) -> Optional[DiverProfile]:
    """Get diver profile for a person.

    Args:
        person: Person object or person ID

    Returns:
        DiverProfile or None
    """
    person_id = person.pk if hasattr(person, "pk") else person
    return (
        DiverProfile.objects.filter(person_id=person_id)
        .select_related("person")
        .first()
    )


def get_current_diver(user) -> Optional[DiverProfile]:
    """Get DiverProfile for a logged-in user.

    Links User -> Person -> DiverProfile via email matching.
    This is the primary selector for portal views.

    Args:
        user: Django User object (from request.user)

    Returns:
        DiverProfile or None if no matching person/diver exists
    """
    if not user or not user.is_authenticated:
        return None

    # Find Person by matching email
    person = (
        Person.objects.filter(email__iexact=user.email, deleted_at__isnull=True)
        .first()
    )

    if not person:
        return None

    # Get DiverProfile for that Person
    return (
        DiverProfile.objects.filter(person=person, deleted_at__isnull=True)
        .select_related("person")
        .first()
    )


def list_dive_sites(
    is_active: bool = True,
    max_certification_rank: Optional[int] = None,
    limit: int = 50,
) -> list[DiveSite]:
    """List dive sites with optional filters.

    Args:
        is_active: Filter by active status
        max_certification_rank: Maximum certification rank required (filter sites requiring this rank or lower)
        limit: Maximum results

    Returns:
        List of DiveSite objects
    """
    qs = DiveSite.objects.select_related("place", "min_certification_level").filter(
        is_active=is_active
    ).order_by("name")

    if max_certification_rank is not None:
        # Get sites that require this level or lower (by rank), or no requirement
        qs = qs.filter(
            Q(min_certification_level__isnull=True)
            | Q(min_certification_level__rank__lte=max_certification_rank)
        )

    return list(qs[:limit])


def list_shop_excursions(
    dive_shop,
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 50,
) -> list[Excursion]:
    """List excursions for a dive shop.

    Optimized for shop management views.

    Args:
        dive_shop: The organization
        status: Filter by status
        from_date: Filter excursions departing on or after
        to_date: Filter excursions departing before
        limit: Maximum results

    Returns:
        List of Excursion objects
    """
    qs = (
        Excursion.objects.filter(dive_shop=dive_shop)
        .select_related("dive_site", "trip")
        .prefetch_related(
            Prefetch(
                "bookings",
                queryset=Booking.objects.select_related("diver__person").filter(
                    status__in=["confirmed", "checked_in"]
                ),
            )
        )
        .annotate(
            booking_count=Count(
                "bookings",
                filter=Q(bookings__status__in=["confirmed", "checked_in"]),
            )
        )
        .order_by("-departure_time")
    )

    if status:
        qs = qs.filter(status=status)

    if from_date:
        qs = qs.filter(departure_time__gte=from_date)

    if to_date:
        qs = qs.filter(departure_time__lt=to_date)

    return list(qs[:limit])


# Backwards compatibility alias
list_shop_trips = list_shop_excursions


def get_booking(booking_id) -> Optional[Booking]:
    """Get a booking with related data.

    Args:
        booking_id: Booking UUID

    Returns:
        Booking or None
    """
    return (
        Booking.objects.filter(pk=booking_id)
        .select_related(
            "excursion__dive_shop",
            "excursion__dive_site",
            "excursion__trip",
            "diver__person",
            "booked_by",
        )
        .first()
    )


# Certification-related selectors

def get_diver_with_certifications(diver_id) -> Optional[DiverProfile]:
    """Get a diver with all certifications prefetched.

    Optimized query to avoid N+1 when accessing certifications.

    Args:
        diver_id: Diver UUID

    Returns:
        DiverProfile with certifications or None
    """
    return (
        DiverProfile.objects.filter(pk=diver_id)
        .select_related("person", "profile_photo", "photo_id")
        .prefetch_related(
            Prefetch(
                "certifications",
                queryset=DiverCertification.objects.filter(
                    deleted_at__isnull=True
                ).select_related(
                    "level", "level__agency", "proof_document"
                ).order_by("-level__rank", "-issued_on"),
            )
        )
        .first()
    )


def get_excursion_with_requirements(excursion_id) -> Optional[Excursion]:
    """Get an excursion with all requirements prefetched.

    Optimized query to avoid N+1 when checking requirements.

    Args:
        excursion_id: Excursion UUID

    Returns:
        Excursion with requirements or None
    """
    return (
        Excursion.objects.filter(pk=excursion_id)
        .select_related("dive_shop", "dive_site", "trip")
        .prefetch_related(
            Prefetch(
                "requirements",
                queryset=ExcursionRequirement.objects.select_related(
                    "certification_level"
                ).order_by("requirement_type"),
            )
        )
        .first()
    )


# Backwards compatibility alias
get_trip_with_requirements = get_excursion_with_requirements


def list_certification_levels(active_only: bool = True) -> list[CertificationLevel]:
    """List all certification levels ordered by rank.

    Args:
        active_only: Only return active levels (default True)

    Returns:
        List of CertificationLevel objects
    """
    qs = CertificationLevel.objects.order_by("rank")
    if active_only:
        qs = qs.filter(is_active=True)
    return list(qs)


def get_diver_highest_certification(diver: DiverProfile) -> Optional[DiverCertification]:
    """Get the diver's highest current (non-expired) certification.

    Args:
        diver: DiverProfile

    Returns:
        DiverCertification with highest rank or None
    """
    from datetime import date

    return (
        diver.certifications
        .filter(Q(expires_on__isnull=True) | Q(expires_on__gt=date.today()))
        .select_related("level", "level__agency")
        .order_by("-level__rank")
        .first()
    )


# =============================================================================
# Audit Selectors (read-only)
# =============================================================================


def diver_audit_feed(diver: DiverProfile, limit: int = 100) -> list:
    """Get all audit events related to a diver.

    Returns audit events where diver_id appears in metadata.
    Events are ordered newest first.

    Args:
        diver: DiverProfile
        limit: Maximum number of events to return (default 100)

    Returns:
        List of AuditLog entries related to this diver
    """
    from django_audit_log.models import AuditLog

    diver_id_str = str(diver.pk)

    # Query by metadata JSON contains diver_id
    return list(
        AuditLog.objects.filter(
            metadata__diver_id=diver_id_str
        ).order_by("-created_at")[:limit]
    )


def excursion_audit_feed(excursion: Excursion, limit: int = 100) -> list:
    """Get all audit events related to an excursion.

    Returns audit events where excursion_id or trip_id appears in metadata.
    Events are ordered newest first.

    Args:
        excursion: Excursion
        limit: Maximum number of events to return (default 100)

    Returns:
        List of AuditLog entries related to this excursion
    """
    from django_audit_log.models import AuditLog

    excursion_id_str = str(excursion.pk)

    # Query by metadata JSON contains excursion_id or trip_id (backwards compat)
    return list(
        AuditLog.objects.filter(
            Q(metadata__excursion_id=excursion_id_str) |
            Q(metadata__trip_id=excursion_id_str)
        ).order_by("-created_at")[:limit]
    )


# Backwards compatibility alias
trip_audit_feed = excursion_audit_feed


# =============================================================================
# Medical Clearance Selectors
# =============================================================================


def get_diver_medical_status(diver: DiverProfile) -> dict:
    """Get diver's medical clearance status.

    Args:
        diver: DiverProfile

    Returns:
        Dict with medical clearance status:
        - has_clearance: bool
        - clearance_date: date or None
        - valid_until: date or None
        - is_expired: bool
        - days_until_expiry: int or None
    """
    from datetime import date

    today = date.today()

    if not diver.medical_clearance_date:
        return {
            "has_clearance": False,
            "clearance_date": None,
            "valid_until": None,
            "is_expired": False,
            "days_until_expiry": None,
        }

    valid_until = diver.medical_clearance_valid_until
    is_expired = valid_until and valid_until < today

    days_until_expiry = None
    if valid_until and not is_expired:
        days_until_expiry = (valid_until - today).days

    return {
        "has_clearance": True,
        "clearance_date": diver.medical_clearance_date,
        "valid_until": valid_until,
        "is_expired": is_expired,
        "days_until_expiry": days_until_expiry,
    }


# =============================================================================
# Agreement Selectors
# =============================================================================


def list_diver_signed_agreements(
    diver: DiverProfile,
    template_type: Optional[str] = None,
    limit: int = 50,
) -> list[SignableAgreement]:
    """Get signed agreements for a diver.

    Args:
        diver: DiverProfile
        template_type: Filter by template type (waiver, medical, briefing, etc.)
        limit: Maximum results

    Returns:
        List of SignableAgreement objects that are signed
    """
    from django.contrib.contenttypes.models import ContentType

    diver_ct = ContentType.objects.get_for_model(DiverProfile)

    qs = (
        SignableAgreement.objects.filter(
            party_a_content_type=diver_ct,
            party_a_object_id=str(diver.pk),
            status=SignableAgreement.Status.SIGNED,
        )
        .select_related("template", "signed_document")
        .order_by("-signed_at")
    )

    if template_type:
        qs = qs.filter(template__template_type=template_type)

    return list(qs[:limit])


def list_diver_briefings(diver: DiverProfile, limit: int = 10) -> list[SignableAgreement]:
    """Get signed briefing acknowledgments for a diver.

    Args:
        diver: DiverProfile
        limit: Maximum results

    Returns:
        List of SignableAgreement objects of type briefing
    """
    return list_diver_signed_agreements(diver, template_type="briefing", limit=limit)


def list_diver_waivers(diver: DiverProfile, limit: int = 10) -> list[SignableAgreement]:
    """Get signed waivers for a diver.

    Args:
        diver: DiverProfile
        limit: Maximum results

    Returns:
        List of SignableAgreement objects of type waiver
    """
    return list_diver_signed_agreements(diver, template_type="waiver", limit=limit)


def list_diver_pending_agreements(
    diver: DiverProfile,
    limit: int = 20,
) -> list[SignableAgreement]:
    """Get pending (unsigned) agreements for a diver.

    Args:
        diver: DiverProfile
        limit: Maximum results

    Returns:
        List of SignableAgreement objects that need signing
    """
    from django.contrib.contenttypes.models import ContentType

    diver_ct = ContentType.objects.get_for_model(DiverProfile)

    return list(
        SignableAgreement.objects.filter(
            party_a_content_type=diver_ct,
            party_a_object_id=str(diver.pk),
            status__in=[SignableAgreement.Status.DRAFT, SignableAgreement.Status.SENT],
        )
        .select_related("template")
        .order_by("-created_at")[:limit]
    )


# =============================================================================
# Dive Log Selectors
# =============================================================================


def list_diver_dive_logs(
    diver: DiverProfile,
    limit: int = 50,
) -> list[DiveLog]:
    """Get dive logs for a diver.

    Args:
        diver: DiverProfile
        limit: Maximum results

    Returns:
        List of DiveLog objects ordered by dive date (newest first)
    """
    return list(
        DiveLog.objects.filter(diver=diver)
        .select_related(
            "dive__dive_site",
            "dive__excursion",
            "assignment",
        )
        .order_by("-dive__actual_start", "-dive__sequence")[:limit]
    )


def get_diver_dive_stats(diver: DiverProfile) -> dict:
    """Get dive statistics for a diver.

    Args:
        diver: DiverProfile

    Returns:
        Dict with dive statistics:
        - total_dives: int
        - total_logged_dives: int
        - deepest_depth: Decimal or None
        - longest_dive: int (minutes) or None
    """
    from django.db.models import Max, Count

    logs = DiveLog.objects.filter(diver=diver)

    stats = logs.aggregate(
        total_logged_dives=Count("id"),
        deepest_depth=Max("max_depth_meters"),
        longest_dive=Max("bottom_time_minutes"),
    )

    return {
        "total_dives": diver.total_dives or stats["total_logged_dives"] or 0,
        "total_logged_dives": stats["total_logged_dives"] or 0,
        "deepest_depth": stats["deepest_depth"],
        "longest_dive": stats["longest_dive"],
    }
