"""Selectors for diver profile data.

Provides optimized queries for the staff diver detail view, returning
bundled data from Person (django-parties) and domain models.

Architecture Note:
- Person owns identity data (name, DOB, contact info)
- DiverProfile extends Person with dive-specific data
- Relationships live in PartyRelationship (django-parties)
- DiverRelationshipMeta extends PartyRelationship with dive-specific metadata
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone

from django_parties.models import PartyRelationship, Person

from ..models import (
    Booking,
    DiverCertification,
    DiverProfile,
    EmergencyContact,
    DiverRelationship,
    ExcursionRoster,
)


def calculate_age(date_of_birth: Optional[date]) -> Optional[int]:
    """Calculate age from date of birth.

    Args:
        date_of_birth: Person's DOB or None

    Returns:
        Age in years or None if DOB not provided
    """
    if not date_of_birth:
        return None
    today = date.today()
    age = today.year - date_of_birth.year
    # Adjust if birthday hasn't occurred this year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


@dataclass
class PersonDetails:
    """Bundle of Person identity fields for display."""

    date_of_birth: Optional[date]
    age: Optional[int]
    preferred_name: str
    phone_is_mobile: bool
    phone_has_whatsapp: bool
    phone_can_receive_sms: bool
    address_line1: str
    address_line2: str
    city: str
    state: str
    postal_code: str
    country: str
    has_address: bool
    notes: str


@dataclass
class NormalizedContacts:
    """Bundle of normalized contact records from django-parties."""

    addresses: QuerySet
    phones: QuerySet
    emails: QuerySet
    has_any: bool


@dataclass
class MedicalDetails:
    """Bundle of medical clearance information."""

    clearance_date: Optional[date]
    valid_until: Optional[date]
    is_expired: bool
    days_remaining: Optional[int]
    clearance_notes: str
    questionnaire_instance: Optional[object]


def get_diver_person_details(person: Person) -> PersonDetails:
    """Get Person identity details for display.

    Args:
        person: Person instance

    Returns:
        PersonDetails dataclass with all identity fields
    """
    return PersonDetails(
        date_of_birth=person.date_of_birth,
        age=calculate_age(person.date_of_birth),
        preferred_name=person.preferred_name or "",
        phone_is_mobile=person.phone_is_mobile,
        phone_has_whatsapp=person.phone_has_whatsapp,
        phone_can_receive_sms=person.phone_can_receive_sms,
        address_line1=person.address_line1 or "",
        address_line2=person.address_line2 or "",
        city=person.city or "",
        state=person.state or "",
        postal_code=person.postal_code or "",
        country=person.country or "",
        has_address=bool(person.address_line1),
        notes=person.notes or "",
    )


def get_diver_normalized_contacts(person: Person) -> NormalizedContacts:
    """Get normalized contact records from django-parties.

    These are separate Address/Phone/Email models that allow
    multiple entries per person (vs denormalized fields on Person).

    Args:
        person: Person instance

    Returns:
        NormalizedContacts dataclass with querysets
    """
    # Evaluate querysets once to avoid duplicate queries
    addresses = list(person.addresses.filter(deleted_at__isnull=True).order_by("-is_primary", "address_type"))
    phones = list(person.phone_numbers.filter(deleted_at__isnull=True).order_by("-is_primary", "phone_type"))
    emails = list(person.email_addresses.filter(deleted_at__isnull=True).order_by("-is_primary", "email_type"))

    return NormalizedContacts(
        addresses=addresses,
        phones=phones,
        emails=emails,
        has_any=bool(addresses or phones or emails),
    )


def get_diver_emergency_contacts(diver: DiverProfile) -> list:
    """Get emergency contacts for a diver.

    Implements "dual-read, single-write" transition pattern:
    - First tries PartyRelationship (new canonical model)
    - Falls back to EmergencyContact (legacy) if none found
    - Writes always go to PartyRelationship (see services.py)

    Args:
        diver: DiverProfile instance

    Returns:
        List of emergency contact dicts with 'source' field indicating origin
    """
    # Try PartyRelationship first
    pr_contacts = _get_emergency_contacts_from_party_relationship(diver)
    if pr_contacts:
        return pr_contacts

    # Fallback to legacy EmergencyContact
    return _get_emergency_contacts_from_legacy(diver)


def _get_emergency_contacts_from_party_relationship(diver: DiverProfile) -> list:
    """Query PartyRelationship for emergency contacts.

    Args:
        diver: DiverProfile instance

    Returns:
        List of emergency contact dicts from PartyRelationship, or empty list
    """
    from ..models import DiverRelationshipMeta

    # Evaluate once - don't use .exists() then iterate (causes 2 queries)
    contacts = list(
        PartyRelationship.objects.filter(
            from_person=diver.person,
            relationship_type="emergency_contact",
            is_active=True,
            deleted_at__isnull=True,
        )
        .select_related("to_person")
        .prefetch_related("diver_meta")
        .order_by("created_at")
    )

    if not contacts:
        return []

    result = []
    for contact in contacts:
        meta = getattr(contact, "diver_meta", None)
        result.append({
            "contact_person": contact.to_person,
            "relationship": contact.title or "",
            "priority": meta.priority if meta else (1 if contact.is_primary else 99),
            "notes": meta.notes if meta else "",
            "is_also_diver": _is_person_a_diver(contact.to_person),
            "party_relationship": contact,
            "source": "party_relationship",
        })
    return sorted(result, key=lambda x: x["priority"])


def _get_emergency_contacts_from_legacy(diver: DiverProfile) -> list:
    """Query legacy EmergencyContact model.

    Args:
        diver: DiverProfile instance

    Returns:
        List of emergency contact dicts from EmergencyContact
    """
    legacy_contacts = EmergencyContact.objects.filter(
        diver=diver,
        deleted_at__isnull=True,
    ).select_related("contact_person").order_by("priority")

    return [
        {
            "contact_person": ec.contact_person,
            "relationship": ec.relationship,
            "priority": ec.priority,
            "notes": ec.notes,
            "is_also_diver": ec.is_also_diver,
            "legacy_model": ec,
            "source": "legacy",
        }
        for ec in legacy_contacts
    ]


def _is_person_a_diver(person: Person) -> bool:
    """Check if person has an active DiverProfile.

    Args:
        person: Person instance

    Returns:
        True if person has an active diver profile
    """
    return (
        hasattr(person, "diver_profile")
        and person.diver_profile is not None
        and person.diver_profile.deleted_at is None
    )


def get_diver_relationships(diver: DiverProfile) -> list:
    """Get buddy/family relationships for a diver.

    Implements "dual-read, single-write" transition pattern:
    - First tries PartyRelationship (new canonical model)
    - Falls back to DiverRelationship (legacy) if none found
    - Writes always go to PartyRelationship (see services.py)

    Args:
        diver: DiverProfile instance

    Returns:
        List of relationship dicts with 'source' field indicating origin
    """
    # Try PartyRelationship first
    pr_relationships = _get_relationships_from_party_relationship(diver)
    if pr_relationships:
        return pr_relationships

    # Fallback to legacy DiverRelationship
    return _get_relationships_from_legacy(diver)


def _get_relationships_from_party_relationship(diver: DiverProfile) -> list:
    """Query PartyRelationship for diver relationships.

    Args:
        diver: DiverProfile instance

    Returns:
        List of relationship dicts from PartyRelationship, or empty list
    """
    # Relationship types relevant to divers (exclude emergency_contact)
    DIVE_RELATIONSHIP_TYPES = [
        "spouse",
        "buddy",
        "friend",
        "relative",
        "travel_companion",
        "instructor",
        "student",
    ]

    # Evaluate once - don't use .exists() then iterate (causes 2 queries)
    relationships = list(
        PartyRelationship.objects.filter(
            Q(from_person=diver.person) | Q(to_person=diver.person),
            relationship_type__in=DIVE_RELATIONSHIP_TYPES,
            is_active=True,
            deleted_at__isnull=True,
        )
        .select_related("from_person", "to_person")
        .prefetch_related("diver_meta")
    )

    if not relationships:
        return []

    result = []
    for rel in relationships:
        # Get the "other" person in the relationship
        other_person = rel.to_person if rel.from_person == diver.person else rel.from_person
        meta = getattr(rel, "diver_meta", None)
        result.append({
            "other_person": other_person,
            "relationship_type": rel.relationship_type,
            "is_preferred_buddy": meta.is_preferred_buddy if meta else False,
            "notes": meta.notes if meta else "",
            "is_also_diver": _is_person_a_diver(other_person),
            "party_relationship": rel,
            "source": "party_relationship",
        })
    return result


def _get_relationships_from_legacy(diver: DiverProfile) -> list:
    """Query legacy DiverRelationship model.

    Args:
        diver: DiverProfile instance

    Returns:
        List of relationship dicts from DiverRelationship
    """
    relationships = DiverRelationship.objects.filter(
        Q(from_diver=diver) | Q(to_diver=diver),
        deleted_at__isnull=True,
    ).select_related(
        "from_diver__person",
        "to_diver__person",
    )

    result = []
    for rel in relationships:
        other_diver = rel.to_diver if rel.from_diver == diver else rel.from_diver
        result.append({
            "other_person": other_diver.person,
            "other_diver": other_diver,
            "relationship_type": rel.relationship_type,
            "is_preferred_buddy": rel.is_preferred_buddy,
            "notes": rel.notes,
            "is_also_diver": True,  # Legacy model always links divers
            "legacy_model": rel,
            "source": "legacy",
        })
    return result


def get_diver_booking_history(
    diver: DiverProfile,
    limit: int = 10,
    include_cancelled: bool = False,
) -> QuerySet:
    """Get booking history for a diver.

    Args:
        diver: DiverProfile instance
        limit: Maximum number of bookings to return
        include_cancelled: Whether to include cancelled bookings

    Returns:
        QuerySet of Booking objects ordered by departure time (newest first)
    """
    qs = Booking.objects.filter(
        diver=diver,
        deleted_at__isnull=True,
    ).select_related(
        "excursion",
        "excursion__dive_site",
        "excursion__dive_shop",
        "excursion__excursion_type",
    )

    if not include_cancelled:
        qs = qs.exclude(status="cancelled")

    return qs.order_by("-excursion__departure_time")[:limit]


def get_diver_dive_history(
    diver: DiverProfile,
    limit: int = 10,
    completed_only: bool = True,
) -> QuerySet:
    """Get dive/check-in history for a diver.

    Args:
        diver: DiverProfile instance
        limit: Maximum number of roster entries to return
        completed_only: Whether to only show completed dives

    Returns:
        QuerySet of ExcursionRoster objects ordered by check-in time (newest first)
    """
    qs = ExcursionRoster.objects.filter(
        diver=diver,
        deleted_at__isnull=True,
    ).select_related(
        "excursion",
        "excursion__dive_site",
        "excursion__dive_shop",
        "checked_in_by",
    )

    if completed_only:
        qs = qs.filter(dive_completed=True)

    return qs.order_by("-checked_in_at")[:limit]


def get_diver_medical_details(
    diver: DiverProfile,
    questionnaire_instance: Optional[object] = None,
) -> MedicalDetails:
    """Get full medical clearance details for a diver.

    Args:
        diver: DiverProfile instance
        questionnaire_instance: Optional pre-fetched instance to avoid extra query

    Returns:
        MedicalDetails dataclass with clearance information
    """
    today = date.today()
    clearance_notes = ""

    # Use provided instance or fetch if not provided
    if questionnaire_instance is None:
        try:
            from ..medical.services import get_diver_medical_instance
            questionnaire_instance = get_diver_medical_instance(diver)
        except ImportError:
            pass

    if questionnaire_instance:
        clearance_notes = getattr(questionnaire_instance, "clearance_notes", "") or ""

    # Calculate validity
    clearance_date = diver.medical_clearance_date
    valid_until = diver.medical_clearance_valid_until

    # If valid_until not set but clearance_date exists, default to 1 year
    if clearance_date and not valid_until:
        valid_until = clearance_date + timedelta(days=365)

    is_expired = valid_until < today if valid_until else False

    days_remaining = None
    if valid_until and not is_expired:
        days_remaining = (valid_until - today).days

    return MedicalDetails(
        clearance_date=clearance_date,
        valid_until=valid_until,
        is_expired=is_expired,
        days_remaining=days_remaining,
        clearance_notes=clearance_notes,
        questionnaire_instance=questionnaire_instance,
    )


def get_diver_with_full_context(diver_id: UUID) -> Optional[dict]:
    """Get diver with all context data for staff detail view.

    This is the main selector for DiverDetailView. It fetches
    the diver and all related data in optimized queries.

    Args:
        diver_id: UUID of the DiverProfile

    Returns:
        Dict with diver and all context bundles, or None if not found
    """
    # Main diver query with prefetches
    diver = (
        DiverProfile.objects.filter(pk=diver_id, deleted_at__isnull=True)
        .select_related(
            "person",
            "profile_photo",
            "photo_id",
            "certification_agency",
        )
        .prefetch_related(
            Prefetch(
                "certifications",
                queryset=DiverCertification.objects.filter(deleted_at__isnull=True)
                .select_related("level", "level__agency", "proof_document")
                .order_by("-level__rank", "-issued_on"),
            ),
            Prefetch(
                "emergency_contact_entries",
                queryset=EmergencyContact.objects.filter(deleted_at__isnull=True)
                .select_related("contact_person")
                .order_by("priority"),
            ),
        )
        .first()
    )

    if not diver:
        return None

    person = diver.person

    # Get medical context in a single query (status + instance)
    try:
        from ..medical.services import get_diver_medical_context
        medical_ctx = get_diver_medical_context(diver)
        medical_status = medical_ctx["status"].value
        medical_instance = medical_ctx["instance"]
    except ImportError:
        medical_status = None
        medical_instance = None

    return {
        "diver": diver,
        "person": person,
        "person_details": get_diver_person_details(person),
        "normalized_contacts": get_diver_normalized_contacts(person),
        "emergency_contacts": get_diver_emergency_contacts(diver),
        "relationships": get_diver_relationships(diver),
        "booking_history": get_diver_booking_history(diver),
        "dive_history": get_diver_dive_history(diver),
        "medical_details": get_diver_medical_details(diver, questionnaire_instance=medical_instance),
        "medical_status": medical_status,
        "medical_instance": medical_instance,
        "demographics": getattr(person, "demographics", None),
    }


def get_staff_person(user) -> Optional[Person]:
    """Get the Person associated with a staff user.

    Staff users may have an associated Person record for messaging.
    If not found, returns None.

    Args:
        user: Django User instance

    Returns:
        Person instance or None
    """
    if not user or not user.is_authenticated:
        return None

    # Try to find Person by user's email
    if user.email:
        person = Person.objects.filter(email=user.email, deleted_at__isnull=True).first()
        if person:
            return person

    # Try to find by username as a fallback
    person = Person.objects.filter(
        Q(email=user.username) | Q(first_name=user.first_name, last_name=user.last_name),
        deleted_at__isnull=True,
    ).first()

    return person


def get_diver_for_person(person: Person) -> Optional[DiverProfile]:
    """Get DiverProfile for a Person if one exists.

    Args:
        person: Person instance

    Returns:
        DiverProfile instance or None
    """
    if not person:
        return None

    return DiverProfile.objects.filter(
        person=person,
        deleted_at__isnull=True,
    ).select_related("person").first()
