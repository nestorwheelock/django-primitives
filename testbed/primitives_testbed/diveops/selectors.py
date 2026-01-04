"""Selectors for dive operations.

Read-only queries optimized to avoid N+1 problems.
All selectors use select_related and prefetch_related.
"""

from datetime import datetime
from typing import Optional

from django.db.models import Count, Prefetch, Q
from django.utils import timezone

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


def list_upcoming_trips(
    dive_shop=None,
    dive_site=None,
    min_spots: int = 0,
    limit: int = 50,
) -> list[DiveTrip]:
    """List upcoming dive trips with optional filters.

    Optimized query with related data prefetched.

    Args:
        dive_shop: Filter by dive shop (optional)
        dive_site: Filter by dive site (optional)
        min_spots: Minimum available spots (default 0 = all)
        limit: Maximum results

    Returns:
        List of DiveTrip objects with related data
    """
    qs = (
        DiveTrip.objects.filter(
            departure_time__gt=timezone.now(),
            status__in=["scheduled", "boarding"],
        )
        .select_related("dive_shop", "dive_site")
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

    trips = list(qs[:limit])

    if min_spots > 0:
        trips = [t for t in trips if t.spots_available >= min_spots]

    return trips


def get_trip_with_roster(trip_id) -> Optional[DiveTrip]:
    """Get a trip with full roster data.

    Optimized query for trip detail view.

    Args:
        trip_id: Trip UUID

    Returns:
        DiveTrip or None
    """
    return (
        DiveTrip.objects.filter(pk=trip_id)
        .select_related("dive_shop", "dive_site", "encounter")
        .prefetch_related(
            Prefetch(
                "bookings",
                queryset=Booking.objects.select_related("diver__person"),
            ),
            Prefetch(
                "roster",
                queryset=TripRoster.objects.select_related(
                    "diver__person", "checked_in_by"
                ),
            ),
        )
        .first()
    )


def list_diver_bookings(
    diver: DiverProfile,
    status: Optional[str] = None,
    include_past: bool = False,
    limit: int = 50,
) -> list[Booking]:
    """List bookings for a diver.

    Optimized query with trip and site data.

    Args:
        diver: The diver profile
        status: Filter by status (optional)
        include_past: Include past trips (default False)
        limit: Maximum results

    Returns:
        List of Booking objects
    """
    qs = (
        Booking.objects.filter(diver=diver)
        .select_related("trip__dive_shop", "trip__dive_site")
        .order_by("-trip__departure_time")
    )

    if status:
        qs = qs.filter(status=status)

    if not include_past:
        qs = qs.filter(trip__departure_time__gt=timezone.now())

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


def list_shop_trips(
    dive_shop,
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 50,
) -> list[DiveTrip]:
    """List trips for a dive shop.

    Optimized for shop management views.

    Args:
        dive_shop: The organization
        status: Filter by status
        from_date: Filter trips departing on or after
        to_date: Filter trips departing before
        limit: Maximum results

    Returns:
        List of DiveTrip objects
    """
    qs = (
        DiveTrip.objects.filter(dive_shop=dive_shop)
        .select_related("dive_site")
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
            "trip__dive_shop",
            "trip__dive_site",
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
        .select_related("person")
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


def get_trip_with_requirements(trip_id) -> Optional[DiveTrip]:
    """Get a trip with all requirements prefetched.

    Optimized query to avoid N+1 when checking requirements.

    Args:
        trip_id: Trip UUID

    Returns:
        DiveTrip with requirements or None
    """
    return (
        DiveTrip.objects.filter(pk=trip_id)
        .select_related("dive_shop", "dive_site")
        .prefetch_related(
            Prefetch(
                "requirements",
                queryset=TripRequirement.objects.select_related(
                    "certification_level"
                ).order_by("requirement_type"),
            )
        )
        .first()
    )


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


def trip_audit_feed(trip: DiveTrip, limit: int = 100) -> list:
    """Get all audit events related to a trip.

    Returns audit events where trip_id appears in metadata.
    Events are ordered newest first.

    Args:
        trip: DiveTrip
        limit: Maximum number of events to return (default 100)

    Returns:
        List of AuditLog entries related to this trip
    """
    from django_audit_log.models import AuditLog

    trip_id_str = str(trip.pk)

    # Query by metadata JSON contains trip_id
    return list(
        AuditLog.objects.filter(
            metadata__trip_id=trip_id_str
        ).order_by("-created_at")[:limit]
    )
