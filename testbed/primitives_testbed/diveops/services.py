"""Services for dive operations.

Business logic for booking, check-in, and trip completion.
All write operations are atomic transactions.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .audit import (
    Actions,
    log_booking_event,
    log_certification_event,
    log_roster_event,
    log_trip_event,
)
from .decisioning import can_diver_join_trip
from .exceptions import (
    BookingError,
    CertificationError,
    CheckInError,
    DiverNotEligibleError,
    TripCapacityError,
    TripStateError,
)
from .integrations import (
    CatalogItem,
    create_booking_invoice,
    create_trip_basket,
    price_basket_item,
)
from .models import Booking, CertificationLevel, DiverCertification, DiverProfile, DiveTrip, TripRoster


def _get_or_create_trip_catalog_item(trip: DiveTrip) -> CatalogItem:
    """Get or create a CatalogItem for a dive trip."""
    item, _ = CatalogItem.objects.get_or_create(
        display_name=f"Dive Trip - {trip.dive_site.name}",
        defaults={
            "kind": "service",
            "is_billable": True,
            "active": True,
        },
    )
    return item


@transaction.atomic
def book_trip(
    trip: DiveTrip,
    diver: DiverProfile,
    booked_by,
    *,
    create_invoice: bool = False,
    skip_eligibility_check: bool = False,
) -> Booking:
    """Book a diver on a trip.

    Creates a booking and optionally a basket/invoice using the pricing module.

    Args:
        trip: The trip to book
        diver: The diver profile
        booked_by: User making the booking
        create_invoice: If True, create basket and invoice via billing adapter
        skip_eligibility_check: If True, skip eligibility validation

    Returns:
        Created Booking

    Raises:
        DiverNotEligibleError: If diver fails eligibility checks
        TripCapacityError: If trip is at capacity
        BookingError: For other booking issues
    """
    # Lock the trip to prevent race conditions
    trip = DiveTrip.objects.select_for_update().get(pk=trip.pk)

    # Check eligibility
    if not skip_eligibility_check:
        result = can_diver_join_trip(diver, trip)
        if not result.allowed:
            # Determine error type
            if any("capacity" in r.lower() or "full" in r.lower() for r in result.reasons):
                raise TripCapacityError("; ".join(result.reasons))
            raise DiverNotEligibleError("; ".join(result.reasons))

    # Create booking
    booking = Booking.objects.create(
        trip=trip,
        diver=diver,
        status="confirmed",
        booked_by=booked_by,
    )

    # Create basket and invoice via billing adapter
    if create_invoice:
        catalog_item = _get_or_create_trip_catalog_item(trip)

        # Create basket with trip item
        basket = create_trip_basket(
            trip=trip,
            diver=diver,
            catalog_item=catalog_item,
            created_by=booked_by,
        )
        booking.basket = basket

        # Price all basket items via pricing module
        for item in basket.items.all():
            price_basket_item(
                basket_item=item,
                trip=trip,
                diver=diver,
            )

        # Create invoice from priced basket
        invoice = create_booking_invoice(
            basket=basket,
            trip=trip,
            diver=diver,
            created_by=booked_by,
        )
        booking.invoice = invoice
        booking.save()

    # Emit audit event AFTER successful transaction
    log_booking_event(
        action=Actions.BOOKING_CREATED,
        booking=booking,
        actor=booked_by,
    )

    return booking


@transaction.atomic
def check_in(
    booking: Booking,
    checked_in_by,
    *,
    require_waiver: bool = False,
) -> TripRoster:
    """Check in a diver for a trip.

    Creates a roster entry and updates booking status.

    Args:
        booking: The booking to check in
        checked_in_by: User performing check-in
        require_waiver: If True, verify waiver is signed

    Returns:
        Created TripRoster entry

    Raises:
        CheckInError: If check-in requirements not met
    """
    # Validate booking status
    if booking.status == "cancelled":
        raise CheckInError("Cannot check in a cancelled booking")

    if booking.status == "checked_in":
        raise CheckInError("Booking is already checked in")

    # Validate waiver if required
    if require_waiver and not booking.waiver_agreement:
        raise CheckInError("Waiver agreement must be signed before check-in")

    # Create roster entry
    roster = TripRoster.objects.create(
        trip=booking.trip,
        diver=booking.diver,
        booking=booking,
        checked_in_by=checked_in_by,
    )

    # Update booking status
    booking.status = "checked_in"
    booking.save()

    # Emit audit event AFTER successful transaction
    log_roster_event(
        action=Actions.DIVER_CHECKED_IN,
        roster=roster,
        actor=checked_in_by,
    )

    return roster


@transaction.atomic
def start_trip(trip: DiveTrip, started_by) -> DiveTrip:
    """Start a trip (transition to in_progress).

    Creates an encounter if one doesn't exist.

    Args:
        trip: The trip to start
        started_by: User starting the trip

    Returns:
        Updated trip

    Raises:
        TripStateError: If trip cannot be started
    """
    if trip.status not in ["scheduled", "boarding"]:
        raise TripStateError(f"Cannot start trip in status={trip.status}")

    # Create encounter if needed
    if not trip.encounter:
        from django_encounters.models import Encounter, EncounterDefinition

        definition = EncounterDefinition.objects.filter(key="dive_trip").first()
        if definition:
            trip_ct = ContentType.objects.get_for_model(trip)
            encounter = Encounter.objects.create(
                definition=definition,
                subject_type=trip_ct,
                subject_id=str(trip.pk),
                state="in_progress",
                created_by=started_by,
            )
            trip.encounter = encounter

    trip.status = "in_progress"
    trip.save()

    # Emit audit event AFTER successful transaction
    log_trip_event(
        action=Actions.TRIP_STARTED,
        trip=trip,
        actor=started_by,
    )

    return trip


@transaction.atomic
def complete_trip(trip: DiveTrip, completed_by) -> DiveTrip:
    """Complete a trip.

    Updates trip status and increments dive counts for all checked-in divers.

    Args:
        trip: The trip to complete
        completed_by: User completing the trip

    Returns:
        Updated trip

    Raises:
        TripStateError: If trip cannot be completed
    """
    if trip.status in ["completed", "cancelled"]:
        raise TripStateError(f"Cannot complete trip in status={trip.status}")

    # Track roster entries that were completed
    completed_roster_entries = []

    # Update all roster entries and increment dive counts
    for roster_entry in trip.roster.all():
        if not roster_entry.dive_completed:
            roster_entry.dive_completed = True
            roster_entry.save()

            # Increment diver's total dives
            diver = roster_entry.diver
            diver.total_dives += 1
            diver.save()

            completed_roster_entries.append(roster_entry)

    # Update trip status
    trip.status = "completed"
    trip.completed_at = timezone.now()
    trip.save()

    # Update encounter if exists
    if trip.encounter:
        trip.encounter.state = "completed"
        trip.encounter.ended_at = timezone.now()
        trip.encounter.save()

    # Emit audit events AFTER successful transaction
    # First, emit DIVER_COMPLETED_TRIP for each roster entry
    for roster_entry in completed_roster_entries:
        log_roster_event(
            action=Actions.DIVER_COMPLETED_TRIP,
            roster=roster_entry,
            actor=completed_by,
        )

    # Then emit TRIP_COMPLETED for the trip
    log_trip_event(
        action=Actions.TRIP_COMPLETED,
        trip=trip,
        actor=completed_by,
    )

    return trip


@transaction.atomic
def cancel_booking(booking: Booking, cancelled_by) -> Booking:
    """Cancel a booking.

    Args:
        booking: The booking to cancel
        cancelled_by: User cancelling the booking

    Returns:
        Updated booking

    Raises:
        BookingError: If booking cannot be cancelled
    """
    if booking.status == "cancelled":
        raise BookingError("Booking is already cancelled")

    if booking.status == "checked_in":
        raise BookingError("Cannot cancel a checked-in booking")

    booking.status = "cancelled"
    booking.cancelled_at = timezone.now()
    booking.save()

    # Emit audit event AFTER successful transaction
    log_booking_event(
        action=Actions.BOOKING_CANCELLED,
        booking=booking,
        actor=cancelled_by,
    )

    return booking


# =============================================================================
# Certification Services
# =============================================================================


@transaction.atomic
def add_certification(
    diver: DiverProfile,
    level: CertificationLevel,
    added_by,
    *,
    card_number: str | None = None,
    issued_on=None,
    expires_on=None,
    proof_document=None,
) -> DiverCertification:
    """Add a new certification to a diver.

    Args:
        diver: The diver profile
        level: The certification level to add
        added_by: User adding the certification
        card_number: Optional card number
        issued_on: Optional issue date
        expires_on: Optional expiration date
        proof_document: Optional proof document (django_documents.Document)

    Returns:
        Created DiverCertification

    Raises:
        CertificationError: If certification already exists or is invalid
    """
    # Check for duplicate certification (same diver + level, not deleted)
    existing = DiverCertification.objects.filter(
        diver=diver,
        level=level,
    ).exists()

    if existing:
        raise CertificationError(
            f"Diver already has {level.name} certification from {level.agency.name}"
        )

    certification = DiverCertification.objects.create(
        diver=diver,
        level=level,
        card_number=card_number or "",
        issued_on=issued_on,
        expires_on=expires_on,
        proof_document=proof_document,
    )

    log_certification_event(
        action=Actions.CERTIFICATION_ADDED,
        certification=certification,
        actor=added_by,
    )

    return certification


@transaction.atomic
def update_certification(
    certification: DiverCertification,
    updated_by,
    *,
    card_number: str | None = None,
    issued_on=None,
    expires_on=None,
    proof_document=None,
) -> DiverCertification:
    """Update an existing certification.

    Args:
        certification: The certification to update
        updated_by: User making the update
        card_number: New card number (None = no change)
        issued_on: New issue date (None = no change)
        expires_on: New expiration date (None = no change)
        proof_document: New proof document (None = no change)

    Returns:
        Updated DiverCertification

    Raises:
        CertificationError: If certification is deleted
    """
    if certification.deleted_at is not None:
        raise CertificationError("Cannot update a deleted certification")

    # Track changes for audit log
    changes = {}

    if card_number is not None and card_number != certification.card_number:
        changes["card_number"] = {"old": certification.card_number, "new": card_number}
        certification.card_number = card_number

    if issued_on is not None and issued_on != certification.issued_on:
        changes["issued_on"] = {
            "old": str(certification.issued_on) if certification.issued_on else None,
            "new": str(issued_on) if issued_on else None,
        }
        certification.issued_on = issued_on

    if expires_on is not None and expires_on != certification.expires_on:
        changes["expires_on"] = {
            "old": str(certification.expires_on) if certification.expires_on else None,
            "new": str(expires_on) if expires_on else None,
        }
        certification.expires_on = expires_on

    if proof_document is not None and proof_document != certification.proof_document:
        changes["proof_document"] = {"old": str(certification.proof_document_id), "new": str(proof_document.pk)}
        certification.proof_document = proof_document

    if changes:
        certification.save()

        log_certification_event(
            action=Actions.CERTIFICATION_UPDATED,
            certification=certification,
            actor=updated_by,
            changes=changes,
        )

    return certification


@transaction.atomic
def remove_certification(
    certification: DiverCertification,
    removed_by,
) -> DiverCertification:
    """Soft delete a certification.

    Sets deleted_at timestamp instead of actually deleting.

    Args:
        certification: The certification to remove
        removed_by: User removing the certification

    Returns:
        Updated DiverCertification with deleted_at set

    Raises:
        CertificationError: If certification is already deleted
    """
    if certification.deleted_at is not None:
        raise CertificationError("Certification is already removed")

    certification.deleted_at = timezone.now()
    certification.save()

    log_certification_event(
        action=Actions.CERTIFICATION_REMOVED,
        certification=certification,
        actor=removed_by,
    )

    return certification


@transaction.atomic
def verify_certification(
    certification: DiverCertification,
    verified_by,
) -> DiverCertification:
    """Mark a certification as verified by staff.

    Args:
        certification: The certification to verify
        verified_by: User verifying the certification

    Returns:
        Updated DiverCertification with is_verified=True

    Raises:
        CertificationError: If certification is deleted or already verified
    """
    if certification.deleted_at is not None:
        raise CertificationError("Cannot verify a deleted certification")

    if certification.is_verified:
        raise CertificationError("Certification is already verified")

    certification.is_verified = True
    certification.save()

    log_certification_event(
        action=Actions.CERTIFICATION_VERIFIED,
        certification=certification,
        actor=verified_by,
    )

    return certification


@transaction.atomic
def unverify_certification(
    certification: DiverCertification,
    unverified_by,
) -> DiverCertification:
    """Remove verification from a certification.

    Args:
        certification: The certification to unverify
        unverified_by: User removing verification

    Returns:
        Updated DiverCertification with is_verified=False

    Raises:
        CertificationError: If certification is deleted or not verified
    """
    if certification.deleted_at is not None:
        raise CertificationError("Cannot unverify a deleted certification")

    if not certification.is_verified:
        raise CertificationError("Certification is not verified")

    certification.is_verified = False
    certification.save()

    log_certification_event(
        action=Actions.CERTIFICATION_UNVERIFIED,
        certification=certification,
        actor=unverified_by,
    )

    return certification
