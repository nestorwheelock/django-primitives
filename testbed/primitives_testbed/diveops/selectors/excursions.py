"""Selectors for dive operations.

Read-only queries optimized to avoid N+1 problems.
All selectors use select_related and prefetch_related.
"""

from datetime import datetime
from typing import Optional

from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from django_parties.models import Person

from ..models import (
    AgreementTemplate,
    Booking,
    CertificationLevel,
    Dive,
    DiveAssignment,
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

    Checks both DiverProfile fields and QuestionnaireInstance records.

    Args:
        diver: DiverProfile

    Returns:
        Dict with medical clearance status:
        - has_clearance: bool
        - clearance_date: date or None
        - valid_until: date or None
        - is_expired: bool
        - days_until_expiry: int or None
        - questionnaire: QuestionnaireInstance or None (the cleared questionnaire)
    """
    from datetime import date, timedelta
    from django.contrib.contenttypes.models import ContentType
    from django_questionnaires.models import QuestionnaireInstance

    today = date.today()

    # First check QuestionnaireInstance for cleared medical questionnaires
    diver_ct = ContentType.objects.get_for_model(DiverProfile)
    cleared_questionnaire = QuestionnaireInstance.objects.filter(
        respondent_content_type=diver_ct,
        respondent_object_id=str(diver.pk),
        status="cleared",
        deleted_at__isnull=True,
    ).order_by("-cleared_at").first()

    if cleared_questionnaire:
        clearance_date = cleared_questionnaire.cleared_at.date() if cleared_questionnaire.cleared_at else None
        # Medical clearance typically valid for 1 year
        valid_until = clearance_date + timedelta(days=365) if clearance_date else None
        is_expired = valid_until and valid_until < today

        days_until_expiry = None
        if valid_until and not is_expired:
            days_until_expiry = (valid_until - today).days

        return {
            "has_clearance": True,
            "clearance_date": clearance_date,
            "valid_until": valid_until,
            "is_expired": is_expired,
            "days_until_expiry": days_until_expiry,
            "questionnaire": cleared_questionnaire,
        }

    # Fall back to DiverProfile fields
    if not diver.medical_clearance_date:
        return {
            "has_clearance": False,
            "clearance_date": None,
            "valid_until": None,
            "is_expired": False,
            "days_until_expiry": None,
            "questionnaire": None,
        }

    # Use explicit valid_until if set, otherwise calculate 1 year from clearance date
    valid_until = diver.medical_clearance_valid_until
    if not valid_until and diver.medical_clearance_date:
        valid_until = diver.medical_clearance_date + timedelta(days=365)
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
        "questionnaire": None,
    }


def list_diver_documents(diver: DiverProfile, limit: int = 50) -> list:
    """Get documents attached to a diver's profile.

    Includes medical questionnaire PDFs, photo ID, physician clearances, etc.

    Args:
        diver: DiverProfile
        limit: Maximum results

    Returns:
        List of Document objects ordered by creation date (newest first)
    """
    from django.contrib.contenttypes.models import ContentType
    from django_documents.models import Document

    diver_ct = ContentType.objects.get_for_model(DiverProfile)

    return list(
        Document.objects.filter(
            target_content_type=diver_ct,
            target_id=str(diver.pk),
            deleted_at__isnull=True,
        )
        .order_by("-created_at")[:limit]
    )


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
    from django_parties.models import Person

    # Agreements are linked to Person, not DiverProfile
    person_ct = ContentType.objects.get_for_model(Person)

    qs = (
        SignableAgreement.objects.filter(
            party_a_content_type=person_ct,
            party_a_object_id=str(diver.person_id),
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
    from django_parties.models import Person

    # Agreements are linked to Person, not DiverProfile
    person_ct = ContentType.objects.get_for_model(Person)

    return list(
        SignableAgreement.objects.filter(
            party_a_content_type=person_ct,
            party_a_object_id=str(diver.person_id),
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
        - total_dives: int (actual logged dives at this shop)
        - self_reported_dives: int (lifetime dives from profile)
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
        "total_dives": stats["total_logged_dives"] or 0,
        "self_reported_dives": diver.total_dives or 0,
        "deepest_depth": stats["deepest_depth"],
        "longest_dive": stats["longest_dive"],
    }


# =============================================================================
# Diver Category and Required Agreements
# =============================================================================


def get_diver_category(diver: DiverProfile) -> str:
    """Determine the diver's category for agreement purposes.

    Categories (in order of precedence):
    - 'dsd': Has an upcoming DSD/try dive booking (no cert required)
    - 'student': Currently enrolled in training or has student assignments
    - 'certified': Has valid certification(s)
    - 'all': Fallback - no specific category

    Args:
        diver: DiverProfile

    Returns:
        Category string: 'dsd', 'student', 'certified', or 'all'
    """
    now = timezone.now()

    # Check for upcoming DSD bookings (is_training=True on excursion_type)
    dsd_bookings = Booking.objects.filter(
        diver=diver,
        status__in=["confirmed", "checked_in"],
        excursion__departure_time__gt=now,
        excursion__excursion_type__is_training=True,
    ).exists()

    if dsd_bookings:
        return "dsd"

    # Check for student assignments in upcoming dives
    student_assignments = DiveAssignment.objects.filter(
        diver=diver,
        role=DiveAssignment.Role.STUDENT,
        dive__excursion__departure_time__gt=now,
        status__in=["assigned", "checked_in"],
    ).exists()

    if student_assignments:
        return "student"

    # Check for valid certifications
    from datetime import date
    has_cert = diver.certifications.filter(
        Q(expires_on__isnull=True) | Q(expires_on__gt=date.today())
    ).exists()

    if has_cert:
        return "certified"

    return "all"


def get_required_agreements_for_diver(
    diver: DiverProfile,
    dive_shop=None,
) -> list[dict]:
    """Get agreements the diver needs but hasn't signed.

    Checks:
    1. Medical questionnaire if no valid medical clearance
    2. Liability waiver matching their diver category
    3. Any other required-for-booking templates

    Args:
        diver: DiverProfile
        dive_shop: Optional Organization to filter templates

    Returns:
        List of dicts with template info and reason
    """
    from django.contrib.contenttypes.models import ContentType
    from django_parties.models import Person
    from datetime import date

    required = []
    # Agreements are linked to Person, not DiverProfile
    person_ct = ContentType.objects.get_for_model(Person)
    category = get_diver_category(diver)

    # Get the dive shop(s) the diver is associated with
    if dive_shop:
        shops = [dive_shop]
    else:
        # Get shops from diver's bookings
        shop_ids = Booking.objects.filter(
            diver=diver,
        ).values_list("excursion__dive_shop_id", flat=True).distinct()
        from django_parties.models import Organization
        shops = list(Organization.objects.filter(pk__in=shop_ids))

        # Fall back to shops with published agreement templates
        if not shops:
            template_shop_ids = AgreementTemplate.objects.filter(
                status=AgreementTemplate.Status.PUBLISHED,
                deleted_at__isnull=True,
            ).values_list("dive_shop_id", flat=True).distinct()
            shops = list(Organization.objects.filter(pk__in=template_shop_ids))

    if not shops:
        return []

    for shop in shops:
        # 1. Check medical questionnaire
        medical_status = get_diver_medical_status(diver)
        if not medical_status["has_clearance"] or medical_status["is_expired"]:
            medical_template = AgreementTemplate.objects.filter(
                dive_shop=shop,
                template_type=AgreementTemplate.TemplateType.MEDICAL,
                status=AgreementTemplate.Status.PUBLISHED,
            ).first()

            if medical_template:
                # Check if already signed and still valid
                signed = SignableAgreement.objects.filter(
                    party_a_content_type=person_ct,
                    party_a_object_id=str(diver.person_id),
                    template=medical_template,
                    status=SignableAgreement.Status.SIGNED,
                ).first()

                if not signed:
                    required.append({
                        "template": medical_template,
                        "reason": "Medical questionnaire required",
                        "priority": "high",
                    })

        # 2. Check liability waiver for their category
        # Try specific category first, fall back to 'all'
        categories_to_check = [category, "all"] if category != "all" else ["all"]

        for cat in categories_to_check:
            waiver_template = AgreementTemplate.objects.filter(
                dive_shop=shop,
                template_type=AgreementTemplate.TemplateType.WAIVER,
                diver_category=cat,
                status=AgreementTemplate.Status.PUBLISHED,
            ).first()

            if waiver_template:
                # Check if signed and still valid
                signed = SignableAgreement.objects.filter(
                    party_a_content_type=person_ct,
                    party_a_object_id=str(diver.person_id),
                    template=waiver_template,
                    status=SignableAgreement.Status.SIGNED,
                )

                # Check validity period
                if waiver_template.validity_days:
                    cutoff = timezone.now() - timezone.timedelta(days=waiver_template.validity_days)
                    signed = signed.filter(signed_at__gte=cutoff)

                if not signed.exists():
                    category_labels = {
                        "certified": "Certified Diver",
                        "student": "Student",
                        "dsd": "Discover Scuba",
                        "all": "",
                    }
                    label = category_labels.get(cat, "")
                    required.append({
                        "template": waiver_template,
                        "reason": f"{label} Liability Release required".strip(),
                        "priority": "high",
                    })
                break  # Only need one waiver

    return required


def get_diver_agreement_status(diver: DiverProfile, dive_shop=None) -> dict:
    """Get complete agreement status for a diver.

    Returns:
        Dict with:
        - category: diver's category (certified, student, dsd, all)
        - required: list of required but unsigned agreements
        - signed_count: number of signed agreements
        - has_valid_medical: bool
        - has_valid_waiver: bool
    """
    category = get_diver_category(diver)
    required = get_required_agreements_for_diver(diver, dive_shop)
    signed = list_diver_signed_agreements(diver, limit=100)
    medical_status = get_diver_medical_status(diver)

    has_valid_waiver = not any(
        r["template"].template_type == AgreementTemplate.TemplateType.WAIVER
        for r in required
    )

    return {
        "category": category,
        "category_display": dict(AgreementTemplate.DiverCategory.choices).get(category, category),
        "required": required,
        "signed_count": len(signed),
        "has_valid_medical": medical_status["has_clearance"] and not medical_status["is_expired"],
        "has_valid_waiver": has_valid_waiver,
    }
