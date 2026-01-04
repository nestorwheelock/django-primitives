"""Services for dive operations.

Business logic for booking, check-in, and trip completion.
All write operations are atomic transactions.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .decisioning import can_diver_join_trip
from .exceptions import (
    BookingError,
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
from .models import Booking, DiverProfile, DiveTrip, TripRoster


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

    # Update all roster entries and increment dive counts
    for roster_entry in trip.roster.all():
        if not roster_entry.dive_completed:
            roster_entry.dive_completed = True
            roster_entry.save()

            # Increment diver's total dives
            diver = roster_entry.diver
            diver.total_dives += 1
            diver.save()

    # Update trip status
    trip.status = "completed"
    trip.completed_at = timezone.now()
    trip.save()

    # Update encounter if exists
    if trip.encounter:
        trip.encounter.state = "completed"
        trip.encounter.ended_at = timezone.now()
        trip.encounter.save()

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

    return booking
