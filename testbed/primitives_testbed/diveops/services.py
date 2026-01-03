"""Services for dive operations.

Business logic for booking, check-in, and trip completion.
All write operations are atomic transactions.
"""

from typing import Optional

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
from .models import Booking, DiverProfile, DiveTrip, TripRoster


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

    Creates a booking and optionally a basket/invoice.

    Args:
        trip: The trip to book
        diver: The diver profile
        booked_by: User making the booking
        create_invoice: If True, create basket and invoice
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

    # Create basket if requested
    if create_invoice:
        basket = _create_booking_basket(booking, booked_by)
        booking.basket = basket

        # Create invoice
        invoice = _create_booking_invoice(booking, basket, booked_by)
        booking.invoice = invoice
        booking.save()

    return booking


def _create_booking_basket(booking: Booking, created_by) -> "Basket":
    """Create a basket for a booking.

    Internal helper - creates a basket with the trip as an item.
    """
    from django_catalog.models import Basket, BasketItem, CatalogItem

    # Get or create a catalog item for dive trips
    trip_item, _ = CatalogItem.objects.get_or_create(
        display_name=f"Dive Trip - {booking.trip.dive_site.name}",
        defaults={
            "kind": "service",
            "is_billable": True,
            "active": True,
        },
    )

    # Create an encounter for the basket (if needed)
    from django_encounters.models import Encounter, EncounterDefinition

    # Get or create dive trip encounter definition
    definition, _ = EncounterDefinition.objects.get_or_create(
        key="dive_booking",
        defaults={
            "name": "Dive Booking",
            "states": ["draft", "confirmed", "completed", "cancelled"],
            "transitions": {
                "draft": ["confirmed", "cancelled"],
                "confirmed": ["completed", "cancelled"],
                "completed": [],
                "cancelled": [],
            },
            "initial_state": "draft",
            "terminal_states": ["completed", "cancelled"],
        },
    )

    # Create encounter for the booking
    diver_ct = ContentType.objects.get_for_model(booking.diver)
    encounter = Encounter.objects.create(
        definition=definition,
        subject_type=diver_ct,
        subject_id=str(booking.diver.pk),
        state="draft",
    )

    # Create basket
    basket = Basket.objects.create(
        encounter=encounter,
        status="draft",
        created_by=created_by,
    )

    # Add trip as basket item
    BasketItem.objects.create(
        basket=basket,
        catalog_item=trip_item,
        quantity=1,
        added_by=created_by,
    )

    return basket


def _create_booking_invoice(booking: Booking, basket, created_by) -> "Invoice":
    """Create an invoice for a booking.

    Internal helper - prices basket and creates invoice.
    """
    from decimal import Decimal

    from primitives_testbed.invoicing.models import Invoice, InvoiceLineItem
    from django_sequence.services import next_sequence

    trip = booking.trip

    # Commit the basket first
    basket.status = "committed"
    basket.committed_by = created_by
    basket.committed_at = timezone.now()
    basket.save()

    # Generate invoice number
    invoice_number = next_sequence(
        scope="invoice",
        org=trip.dive_shop,
        prefix="INV-",
        pad_width=4,
        include_year=True,
    )

    # Create invoice
    invoice = Invoice.objects.create(
        basket=basket,
        encounter=basket.encounter,
        billed_to=booking.diver.person,
        issued_by=trip.dive_shop,
        invoice_number=invoice_number,
        status="issued",
        currency=trip.currency,
        subtotal_amount=trip.price_per_diver,
        tax_amount=Decimal("0"),
        total_amount=trip.price_per_diver,
        created_by=created_by,
        issued_at=timezone.now(),
    )

    # We can't create line items without PricedBasketItem in this simplified flow
    # In a real implementation, we'd use the pricing module

    return invoice


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
