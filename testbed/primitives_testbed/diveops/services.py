"""Services for dive operations.

Business logic for booking, check-in, and trip completion.
All write operations are atomic transactions.
"""

from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from .cancellation_policy import RefundDecision


@dataclass
class CancellationResult:
    """Result of a booking cancellation.

    Bundles the cancelled booking with its refund decision.

    Attributes:
        booking: The cancelled Booking instance
        refund_decision: The computed RefundDecision (None if no agreement)
    """

    booking: "Booking"
    refund_decision: RefundDecision | None

from .audit import (
    Actions,
    log_booking_event,
    log_dive_assignment_event,
    log_dive_event,
    log_dive_log_event,
    log_dive_template_event,
    log_settlement_event,
    log_certification_event,
    log_diver_event,
    log_event,
    log_excursion_event,
    log_excursion_type_event,
    log_roster_event,
    log_site_event,
    log_site_price_adjustment_event,
)
from .decisioning import can_diver_join_trip
from .exceptions import (
    BookingError,
    CertificationError,
    CheckInError,
    DiverError,
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
from .models import (
    Booking,
    CertificationLevel,
    Dive,
    DiveAssignment,
    DiverCertification,
    DiverProfile,
    DiveLog,
    DiveSite,
    Excursion,
    ExcursionRoster,
    ExcursionType,
    ExcursionTypeDive,
    SitePriceAdjustment,
)

# Backwards compatibility aliases
DiveTrip = Excursion
TripRoster = ExcursionRoster


def _get_constraint_name(exc: IntegrityError) -> str | None:
    """Extract PostgreSQL constraint name from IntegrityError.

    Returns constraint name if available, None otherwise.
    """
    if exc.__cause__ and hasattr(exc.__cause__, "diag"):
        return exc.__cause__.diag.constraint_name
    return None


def _apply_tracked_update(obj, field: str, new_value, changes: dict) -> None:
    """Apply a field update and track the change if value differs.

    Args:
        obj: Model instance to update
        field: Field name to update
        new_value: New value (None means no change requested)
        changes: Dict to record changes for audit log
    """
    if new_value is None:
        return

    old_value = getattr(obj, field)
    if new_value == old_value:
        return

    # Format values for audit log (convert dates to strings)
    old_str = str(old_value) if old_value is not None else None
    new_str = str(new_value) if new_value is not None else None

    changes[field] = {"old": old_str, "new": new_str}
    setattr(obj, field, new_value)


def _get_or_create_excursion_catalog_item(excursion: Excursion) -> CatalogItem:
    """Get or create a CatalogItem for a dive excursion."""
    item, _ = CatalogItem.objects.get_or_create(
        display_name=f"Dive Excursion - {excursion.dive_site.name}",
        defaults={
            "kind": "service",
            "is_billable": True,
            "active": True,
        },
    )
    return item


# Backwards compatibility alias
_get_or_create_trip_catalog_item = _get_or_create_excursion_catalog_item


def get_compatible_sites(excursion_type: ExcursionType | None = None):
    """Get dive sites compatible with an excursion type.

    Filters sites based on:
    1. dive_mode: Site must match the excursion type's dive mode
    2. certification: Site's min_certification must not exceed what the
       excursion type allows (by certification rank)

    Args:
        excursion_type: The excursion type to filter for (None = all active sites)

    Returns:
        QuerySet of compatible DiveSite instances
    """
    sites = DiveSite.objects.filter(is_active=True)

    if excursion_type is None:
        return sites.order_by("name")

    # Filter by dive mode
    sites = sites.filter(dive_mode=excursion_type.dive_mode)

    # Filter by certification level compatibility
    # If excursion type has no cert requirement, only include sites with no requirement
    # If excursion type requires a cert, include sites that require same or lower rank
    if excursion_type.min_certification_level is None:
        # No cert excursion (like DSD) - only allow sites with no cert requirement
        sites = sites.filter(min_certification_level__isnull=True)
    else:
        # Include sites with no requirement OR requirement <= excursion's requirement
        excursion_rank = excursion_type.min_certification_level.rank
        sites = sites.filter(
            models.Q(min_certification_level__isnull=True)
            | models.Q(min_certification_level__rank__lte=excursion_rank)
        )

    return sites.select_related("min_certification_level", "place").order_by("name")


@transaction.atomic
def book_excursion(
    excursion: Excursion,
    diver: DiverProfile,
    booked_by,
    *,
    create_invoice: bool = False,
    skip_eligibility_check: bool = False,
    create_agreement: bool = False,
    cancellation_policy: dict | None = None,
) -> Booking:
    """Book a diver on an excursion.

    Creates a booking and optionally a basket/invoice using the pricing module.
    Can also create a waiver agreement with cancellation policy terms.

    Args:
        excursion: The excursion to book
        diver: The diver profile
        booked_by: User making the booking
        create_invoice: If True, create basket and invoice via billing adapter
        skip_eligibility_check: If True, skip eligibility validation
        create_agreement: If True, create waiver agreement with cancellation terms
        cancellation_policy: Custom cancellation policy (uses default if None)

    Returns:
        Created Booking

    Raises:
        DiverNotEligibleError: If diver fails eligibility checks
        TripCapacityError: If excursion is at capacity
        BookingError: For other booking issues
        ValueError: If cancellation_policy is invalid
    """
    # Lock the excursion to prevent race conditions
    excursion = Excursion.objects.select_for_update().get(pk=excursion.pk)

    # Check eligibility
    if not skip_eligibility_check:
        result = can_diver_join_trip(diver, excursion)
        if not result.allowed:
            # Determine error type
            if any("capacity" in r.lower() or "full" in r.lower() for r in result.reasons):
                raise TripCapacityError("; ".join(result.reasons))
            raise DiverNotEligibleError("; ".join(result.reasons))

    # INV-3: Price Immutability - snapshot price at booking creation
    # Price is ONLY captured if excursion has both excursion_type AND dive_site
    # This enables structured pricing breakdown in the snapshot
    price_snapshot = None
    price_amount = None
    price_currency = ""

    if excursion.excursion_type and excursion.dive_site:
        # Compute price from excursion type + site adjustments
        from .pricing_service import compute_excursion_price, create_price_snapshot

        computed = compute_excursion_price(excursion.excursion_type, excursion.dive_site)
        price_snapshot = create_price_snapshot(
            computed_price=computed,
            excursion_type_id=str(excursion.excursion_type.pk),
            dive_site_id=str(excursion.dive_site.pk),
        )
        price_amount = computed.total_price
        price_currency = computed.currency
    # Note: If excursion_type or dive_site is missing, price fields remain null
    # This is intentional per INV-3 - only structured pricing is snapshotted

    # Validate cancellation policy if provided
    if create_agreement and cancellation_policy is not None:
        from .cancellation_policy import validate_cancellation_policy

        validation = validate_cancellation_policy(cancellation_policy)
        if not validation.is_valid:
            raise ValueError(
                f"Invalid cancellation policy: {'; '.join(validation.errors)}"
            )

    # Create booking
    try:
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver,
            status="confirmed",
            booked_by=booked_by,
            price_snapshot=price_snapshot,
            price_amount=price_amount,
            price_currency=price_currency,
        )
    except IntegrityError as e:
        constraint = _get_constraint_name(e)
        if constraint == "diveops_booking_one_active_per_excursion":
            raise BookingError(
                f"Diver {diver} already has an active booking for this excursion"
            ) from e
        # Re-raise unknown IntegrityErrors
        raise

    # Create waiver agreement if requested
    if create_agreement:
        from django_agreements.services import create_agreement as create_agr
        from django.utils import timezone

        from .cancellation_policy import DEFAULT_CANCELLATION_POLICY

        # Use provided policy or default
        policy = cancellation_policy if cancellation_policy else DEFAULT_CANCELLATION_POLICY

        # Build agreement terms
        agreement_terms = {
            "booking_id": str(booking.pk),
            "excursion_id": str(excursion.pk),
            "cancellation_policy": policy,
            "agreed_at": timezone.now().isoformat(),
        }

        # Create agreement via django_agreements service
        agreement = create_agr(
            party_a=diver.person,
            party_b=excursion.dive_shop,
            scope_type="booking_waiver",
            terms=agreement_terms,
            agreed_by=booked_by,
            valid_from=timezone.now(),
            scope_ref=booking,
        )

        # Link agreement to booking
        booking.waiver_agreement = agreement
        booking.save(update_fields=["waiver_agreement"])

        # Emit agreement audit event
        log_event(
            action=Actions.AGREEMENT_CREATED,
            target=agreement,
            actor=booked_by,
            data={
                "booking_id": str(booking.pk),
                "diver_id": str(diver.pk),
                "excursion_id": str(excursion.pk),
                "scope_type": "booking_waiver",
            },
        )

    # Create basket and invoice via billing adapter
    if create_invoice:
        catalog_item = _get_or_create_excursion_catalog_item(excursion)

        # Create basket with excursion item
        basket = create_trip_basket(
            trip=excursion,
            diver=diver,
            catalog_item=catalog_item,
            created_by=booked_by,
        )
        booking.basket = basket

        # Price all basket items via pricing module
        for item in basket.items.all():
            price_basket_item(
                basket_item=item,
                trip=excursion,
                diver=diver,
            )

        # Create invoice from priced basket
        invoice = create_booking_invoice(
            basket=basket,
            trip=excursion,
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


# Backwards compatibility alias
book_trip = book_excursion


@transaction.atomic
def check_in(
    booking: Booking,
    checked_in_by,
    *,
    require_waiver: bool = False,
) -> ExcursionRoster:
    """Check in a diver for an excursion.

    Creates a roster entry and updates booking status.

    Args:
        booking: The booking to check in
        checked_in_by: User performing check-in
        require_waiver: If True, verify waiver is signed

    Returns:
        Created ExcursionRoster entry

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
    try:
        roster = ExcursionRoster.objects.create(
            excursion=booking.excursion,
            diver=booking.diver,
            booking=booking,
            checked_in_by=checked_in_by,
        )
    except IntegrityError as e:
        constraint = _get_constraint_name(e)
        if constraint == "diveops_roster_one_per_excursion":
            raise CheckInError(
                f"Diver {booking.diver} is already on the roster for this excursion"
            ) from e
        if constraint == "diveops_excursionroster_booking_id_key":
            raise CheckInError(
                "This booking already has a roster entry"
            ) from e
        # Re-raise unknown IntegrityErrors
        raise

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
def start_excursion(excursion: Excursion, started_by) -> Excursion:
    """Start an excursion (transition to in_progress).

    Creates an encounter if one doesn't exist.

    Args:
        excursion: The excursion to start
        started_by: User starting the excursion

    Returns:
        Updated excursion

    Raises:
        TripStateError: If excursion cannot be started
    """
    if excursion.status not in ["scheduled", "boarding"]:
        raise TripStateError(f"Cannot start excursion in status={excursion.status}")

    # Create encounter if needed
    if not excursion.encounter:
        from django_encounters.models import Encounter, EncounterDefinition

        definition = EncounterDefinition.objects.filter(key="dive_excursion").first()
        if not definition:
            # Fallback to legacy key
            definition = EncounterDefinition.objects.filter(key="dive_trip").first()
        if definition:
            excursion_ct = ContentType.objects.get_for_model(excursion)
            encounter = Encounter.objects.create(
                definition=definition,
                subject_type=excursion_ct,
                subject_id=str(excursion.pk),
                state="in_progress",
                created_by=started_by,
            )
            excursion.encounter = encounter

    excursion.status = "in_progress"
    excursion.save()

    # Emit audit event AFTER successful transaction
    log_excursion_event(
        action=Actions.EXCURSION_STARTED,
        excursion=excursion,
        actor=started_by,
    )

    return excursion


# Backwards compatibility alias
start_trip = start_excursion


@transaction.atomic
def complete_excursion(excursion: Excursion, completed_by) -> Excursion:
    """Complete an excursion.

    Updates excursion status and increments dive counts for all checked-in divers.
    Idempotent: returns existing completed excursion without error.

    Args:
        excursion: The excursion to complete
        completed_by: User completing the excursion

    Returns:
        Updated excursion (or existing if already completed)

    Raises:
        TripStateError: If excursion is cancelled
    """
    # Lock excursion to prevent concurrent completion
    excursion = Excursion.objects.select_for_update().get(pk=excursion.pk)

    # Idempotency: already completed is a no-op
    if excursion.status == "completed":
        return excursion

    if excursion.status == "cancelled":
        raise TripStateError("Cannot complete a cancelled excursion")

    # Lock and fetch roster entries that need completion
    # select_for_update prevents concurrent increment
    roster_entries = list(
        excursion.roster.select_for_update().filter(dive_completed=False)
    )

    # Track completed entries for audit logging
    completed_roster_entries = []

    for roster_entry in roster_entries:
        roster_entry.dive_completed = True
        roster_entry.save(update_fields=["dive_completed", "updated_at"])

        # Lock diver before increment to prevent race
        diver = DiverProfile.objects.select_for_update().get(pk=roster_entry.diver_id)
        diver.total_dives += 1
        diver.save(update_fields=["total_dives", "updated_at"])

        completed_roster_entries.append(roster_entry)

    # Update excursion status
    excursion.status = "completed"
    excursion.completed_at = timezone.now()
    excursion.save(update_fields=["status", "completed_at", "updated_at"])

    # Update encounter if exists
    if excursion.encounter:
        excursion.encounter.state = "completed"
        excursion.encounter.ended_at = timezone.now()
        excursion.encounter.save()

    # Emit audit events AFTER successful updates
    # First, emit DIVER_COMPLETED_TRIP for each roster entry
    for roster_entry in completed_roster_entries:
        log_roster_event(
            action=Actions.DIVER_COMPLETED_TRIP,
            roster=roster_entry,
            actor=completed_by,
        )

    # Then emit EXCURSION_COMPLETED for the excursion
    log_excursion_event(
        action=Actions.EXCURSION_COMPLETED,
        excursion=excursion,
        actor=completed_by,
    )

    return excursion


# Backwards compatibility alias
complete_trip = complete_excursion


def cancel_booking(
    booking: Booking,
    cancelled_by,
    *,
    force_with_refund: bool = False,
) -> CancellationResult:
    """Cancel a booking and compute refund decision.

    If the booking has a waiver agreement with cancellation terms,
    computes the refund decision based on the agreement's policy.

    T-004: This computes a DECISION, not a MOVEMENT of money.
    No settlement records or ledger entries are created (unless force_with_refund=True).

    T-011: Financial State Enforcement (INV-5)
    - If booking is settled (has revenue settlement), cancellation is blocked
    - Use force_with_refund=True to auto-create refund settlement and proceed

    Args:
        booking: The booking to cancel
        cancelled_by: User cancelling the booking
        force_with_refund: If True and booking is settled, auto-create refund settlement

    Returns:
        CancellationResult with booking and refund decision

    Raises:
        BookingError: If booking cannot be cancelled
    """
    # Pre-validation (outside atomic block to preserve audit log on failure)
    if booking.status == "cancelled":
        raise BookingError("Booking is already cancelled")

    if booking.status == "checked_in":
        raise BookingError("Cannot cancel a checked-in booking")

    # T-011: Financial state enforcement (INV-5)
    # Check before atomic block so audit log persists even if cancelled
    was_settled = booking.is_settled

    if was_settled and not force_with_refund:
        # Emit audit event for blocked action (outside atomic so it persists)
        log_event(
            action=Actions.BOOKING_CANCELLATION_BLOCKED,
            target=booking,
            actor=cancelled_by,
            data={
                "booking_id": str(booking.pk),
                "reason": "Booking is settled without refund",
                "financial_state": booking.get_financial_state(),
            },
        )
        raise BookingError(
            "Cannot cancel settled booking without refund. "
            "Use force_with_refund=True to auto-create refund settlement."
        )

    # All mutations happen in atomic block
    return _cancel_booking_atomic(booking, cancelled_by, was_settled, force_with_refund)


@transaction.atomic
def _cancel_booking_atomic(
    booking: Booking,
    cancelled_by,
    was_settled: bool,
    force_with_refund: bool,
) -> CancellationResult:
    """Internal atomic implementation of cancel_booking."""
    cancellation_time = timezone.now()
    refund_decision = None
    audit_data = {}

    # Compute refund decision if agreement exists with cancellation policy
    if booking.waiver_agreement is not None:
        agreement = booking.waiver_agreement
        terms = agreement.terms or {}
        cancellation_policy = terms.get("cancellation_policy")

        if cancellation_policy and booking.price_amount is not None:
            from .cancellation_policy import compute_refund_decision

            refund_decision = compute_refund_decision(
                original_amount=booking.price_amount,
                currency=booking.price_currency or "USD",
                departure_time=booking.excursion.departure_time,
                cancellation_time=cancellation_time,
                policy=cancellation_policy,
            )

            # Include refund decision in audit metadata
            audit_data = {
                "refund_percent": refund_decision.refund_percent,
                "refund_amount": str(refund_decision.refund_amount),
                "original_amount": str(refund_decision.original_amount),
                "hours_before_departure": refund_decision.hours_before_departure,
            }

        # Terminate the agreement
        from django_agreements.services import terminate_agreement

        terminate_agreement(
            agreement=agreement,
            terminated_by=cancelled_by,
            reason="Booking cancelled",
        )

        # Emit agreement termination audit event
        log_event(
            action=Actions.AGREEMENT_TERMINATED,
            target=agreement,
            actor=cancelled_by,
            data={
                "booking_id": str(booking.pk),
                "reason": "Booking cancelled",
            },
        )

    # Update booking status
    booking.status = "cancelled"
    booking.cancelled_at = cancellation_time
    booking.save()

    # Emit audit event with refund metadata
    log_booking_event(
        action=Actions.BOOKING_CANCELLED,
        booking=booking,
        actor=cancelled_by,
        data=audit_data if audit_data else None,
    )

    # T-011: Auto-create refund settlement if force_with_refund and booking was settled
    if force_with_refund and was_settled and refund_decision is not None:
        create_refund_settlement(
            booking=booking,
            refund_decision=refund_decision,
            processed_by=cancelled_by,
        )

    return CancellationResult(
        booking=booking,
        refund_decision=refund_decision,
    )


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

    changes = {}
    _apply_tracked_update(certification, "card_number", card_number, changes)
    _apply_tracked_update(certification, "issued_on", issued_on, changes)
    _apply_tracked_update(certification, "expires_on", expires_on, changes)

    # proof_document needs special handling for FK
    if proof_document is not None and proof_document != certification.proof_document:
        changes["proof_document"] = {
            "old": str(certification.proof_document_id) if certification.proof_document_id else None,
            "new": str(proof_document.pk),
        }
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


# =============================================================================
# Diver Services
# =============================================================================


@transaction.atomic
def create_diver(
    first_name: str,
    last_name: str,
    email: str,
    total_dives: int,
    created_by,
    *,
    medical_clearance_date=None,
    medical_clearance_valid_until=None,
) -> DiverProfile:
    """Create a new diver with Person and DiverProfile.

    Args:
        first_name: Diver's first name
        last_name: Diver's last name
        email: Diver's email address
        total_dives: Number of logged dives
        created_by: User creating the diver
        medical_clearance_date: Optional medical clearance date
        medical_clearance_valid_until: Optional medical clearance expiry

    Returns:
        Created DiverProfile

    Raises:
        DiverError: If diver creation fails
    """
    from django_parties.models import Person

    # Create Person record
    person = Person.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=email,
    )

    # Create DiverProfile
    diver = DiverProfile.objects.create(
        person=person,
        total_dives=total_dives,
        medical_clearance_date=medical_clearance_date,
        medical_clearance_valid_until=medical_clearance_valid_until,
    )

    # Emit audit event
    log_diver_event(
        action=Actions.DIVER_CREATED,
        diver=diver,
        actor=created_by,
    )

    return diver


@transaction.atomic
def update_diver(
    diver: DiverProfile,
    updated_by,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    total_dives: int | None = None,
    medical_clearance_date=None,
    medical_clearance_valid_until=None,
) -> DiverProfile:
    """Update an existing diver's Person and DiverProfile.

    Args:
        diver: DiverProfile to update
        updated_by: User making the update
        first_name: New first name (None = no change)
        last_name: New last name (None = no change)
        email: New email (None = no change)
        total_dives: New dive count (None = no change)
        medical_clearance_date: New clearance date (None = no change)
        medical_clearance_valid_until: New clearance expiry (None = no change)

    Returns:
        Updated DiverProfile

    Raises:
        DiverError: If diver is deleted or update fails
    """
    if diver.deleted_at is not None:
        raise DiverError("Cannot update a deleted diver")

    changes = {}
    person = diver.person

    # Update Person fields
    _apply_tracked_update(person, "first_name", first_name, changes)
    _apply_tracked_update(person, "last_name", last_name, changes)
    _apply_tracked_update(person, "email", email, changes)

    # Update DiverProfile fields
    _apply_tracked_update(diver, "total_dives", total_dives, changes)
    _apply_tracked_update(diver, "medical_clearance_date", medical_clearance_date, changes)
    _apply_tracked_update(diver, "medical_clearance_valid_until", medical_clearance_valid_until, changes)

    if changes:
        person.save()
        diver.save()

        log_diver_event(
            action=Actions.DIVER_UPDATED,
            diver=diver,
            actor=updated_by,
            changes=changes,
        )

    return diver


# =============================================================================
# Dive Site Services
# =============================================================================


@transaction.atomic
def create_dive_site(
    *,
    actor,
    name: str,
    latitude,
    longitude,
    max_depth_meters: int,
    difficulty: str,
    dive_mode: str = "boat",
    description: str = "",
    min_certification_level: CertificationLevel | None = None,
    rating: int | None = None,
    tags: list[str] | None = None,
) -> DiveSite:
    """Create a new dive site with an owned Place.

    Creates a Place from coordinates, then creates a DiveSite with that Place.
    The Place is owned by the DiveSite (no sharing/deduplication).

    Args:
        actor: User creating the site (required)
        name: Site name
        latitude: Decimal latitude
        longitude: Decimal longitude
        max_depth_meters: Maximum depth in meters
        difficulty: Difficulty level (beginner/intermediate/advanced/expert)
        dive_mode: Access mode (boat/shore/cenote/cavern)
        description: Optional site description
        min_certification_level: Optional minimum certification FK
        rating: Optional rating (1-5)
        tags: Optional list of tags

    Returns:
        Created DiveSite

    Raises:
        IntegrityError: If constraints are violated
    """
    from django_geo.models import Place

    # Create owned Place from coordinates
    place = Place.objects.create(
        name=name,
        latitude=latitude,
        longitude=longitude,
    )

    # Create DiveSite with the owned Place
    site = DiveSite.objects.create(
        name=name,
        description=description,
        place=place,
        max_depth_meters=max_depth_meters,
        min_certification_level=min_certification_level,
        difficulty=difficulty,
        dive_mode=dive_mode,
        rating=rating,
        tags=tags or [],
    )

    # Emit audit event
    log_site_event(
        action=Actions.DIVE_SITE_CREATED,
        site=site,
        actor=actor,
    )

    return site


@transaction.atomic
def update_dive_site(
    *,
    actor,
    site: DiveSite,
    name: str | None = None,
    latitude=None,
    longitude=None,
    max_depth_meters: int | None = None,
    difficulty: str | None = None,
    dive_mode: str | None = None,
    description: str | None = None,
    min_certification_level: CertificationLevel | None = None,
    rating: int | None = None,
    tags: list[str] | None = None,
) -> DiveSite:
    """Update an existing dive site.

    Updates both the DiveSite and its owned Place if coordinates change.

    Args:
        actor: User making the update (required)
        site: DiveSite to update
        name: New name (None = no change)
        latitude: New latitude (None = no change)
        longitude: New longitude (None = no change)
        max_depth_meters: New depth (None = no change)
        difficulty: New difficulty (None = no change)
        dive_mode: New access mode (None = no change)
        description: New description (None = no change)
        min_certification_level: New certification FK (None = no change)
        rating: New rating (None = no change)
        tags: New tags (None = no change)

    Returns:
        Updated DiveSite

    Raises:
        IntegrityError: If constraints are violated
    """
    changes = {}

    # Update DiveSite fields
    _apply_tracked_update(site, "name", name, changes)
    _apply_tracked_update(site, "description", description, changes)
    _apply_tracked_update(site, "max_depth_meters", max_depth_meters, changes)
    _apply_tracked_update(site, "difficulty", difficulty, changes)
    _apply_tracked_update(site, "dive_mode", dive_mode, changes)
    _apply_tracked_update(site, "rating", rating, changes)
    _apply_tracked_update(site, "tags", tags, changes)

    # Handle min_certification_level FK specially
    if min_certification_level is not None and min_certification_level != site.min_certification_level:
        changes["min_certification_level"] = {
            "old": str(site.min_certification_level_id) if site.min_certification_level_id else None,
            "new": str(min_certification_level.pk),
        }
        site.min_certification_level = min_certification_level

    # Update Place coordinates if changed
    place = site.place
    if latitude is not None and latitude != place.latitude:
        changes["latitude"] = {"old": str(place.latitude), "new": str(latitude)}
        place.latitude = latitude

    if longitude is not None and longitude != place.longitude:
        changes["longitude"] = {"old": str(place.longitude), "new": str(longitude)}
        place.longitude = longitude

    if changes:
        place.save()
        site.save()

        log_site_event(
            action=Actions.DIVE_SITE_UPDATED,
            site=site,
            actor=actor,
            changes=changes,
        )

    return site


@transaction.atomic
def delete_dive_site(
    *,
    actor,
    site: DiveSite,
) -> DiveSite:
    """Soft delete a dive site.

    Sets deleted_at timestamp instead of actually deleting.
    The site will be excluded from default queries.

    Args:
        actor: User deleting the site (required)
        site: DiveSite to delete

    Returns:
        Updated DiveSite with deleted_at set
    """
    site.deleted_at = timezone.now()
    site.save()

    log_site_event(
        action=Actions.DIVE_SITE_DELETED,
        site=site,
        actor=actor,
    )

    return site


# =============================================================================
# Excursion CRUD Services
# =============================================================================


@transaction.atomic
def create_excursion(
    *,
    actor,
    dive_site: DiveSite,
    dive_shop,
    departure_time,
    max_divers: int,
    return_time=None,
    price_per_diver=None,
    currency: str = "USD",
    trip=None,
    excursion_type: "ExcursionType | None" = None,
) -> Excursion:
    """Create a new dive excursion.

    Args:
        actor: User creating the excursion (required)
        dive_site: DiveSite for this excursion
        dive_shop: Organization running this excursion
        departure_time: Scheduled departure datetime
        max_divers: Maximum number of divers allowed
        return_time: Scheduled return datetime (defaults to 4 hours after departure)
        price_per_diver: Optional price per diver (Decimal). If not provided and
            excursion_type is set, computes price from type + site adjustments.
        currency: Currency code (default: USD)
        trip: Optional Trip package this excursion belongs to
        excursion_type: Optional product template for pricing and eligibility

    Returns:
        Created Excursion

    Raises:
        IntegrityError: If constraints are violated
    """
    from datetime import timedelta
    from decimal import Decimal

    # Default return_time to 4 hours after departure
    if return_time is None:
        return_time = departure_time + timedelta(hours=4)

    # If excursion_type is set and no explicit price, compute from pricing service
    if excursion_type is not None and price_per_diver is None:
        from .pricing_service import compute_excursion_price

        computed = compute_excursion_price(excursion_type, dive_site)
        price_per_diver = computed.total_price
        currency = computed.currency

    excursion = Excursion.objects.create(
        dive_site=dive_site,
        dive_shop=dive_shop,
        departure_time=departure_time,
        return_time=return_time,
        max_divers=max_divers,
        price_per_diver=price_per_diver or Decimal("0.00"),
        currency=currency,
        trip=trip,
        excursion_type=excursion_type,
        status="scheduled",
        created_by=actor,
    )

    # Auto-create dives from excursion type templates
    if excursion_type is not None:
        dive_templates = excursion_type.dive_templates.all().order_by("sequence")
        for template in dive_templates:
            # Calculate planned start time based on offset
            planned_start = departure_time + timedelta(minutes=template.offset_minutes)

            Dive.objects.create(
                excursion=excursion,
                dive_site=dive_site,  # Default to excursion's site
                sequence=template.sequence,
                planned_start=planned_start,
                planned_duration_minutes=template.planned_duration_minutes,
                notes=f"From template: {template.name}",
            )

    log_excursion_event(
        action=Actions.EXCURSION_CREATED,
        excursion=excursion,
        actor=actor,
    )

    return excursion


@transaction.atomic
def update_excursion(
    *,
    actor,
    excursion: Excursion,
    dive_site: DiveSite | None = None,
    departure_time=None,
    return_time=None,
    max_divers: int | None = None,
    price_per_diver=None,
    currency: str | None = None,
    excursion_type: "ExcursionType | None" = None,
) -> Excursion:
    """Update an existing excursion.

    Args:
        actor: User making the update (required)
        excursion: Excursion to update
        dive_site: New dive site (None = no change)
        departure_time: New departure time (None = no change)
        return_time: New return time (None = no change)
        max_divers: New max divers (None = no change)
        price_per_diver: New price (None = no change)
        currency: New currency (None = no change)
        excursion_type: New excursion type (None = no change)

    Returns:
        Updated Excursion

    Raises:
        TripStateError: If excursion is completed or cancelled
    """
    if excursion.status in ["completed", "cancelled"]:
        raise TripStateError(f"Cannot update excursion in status={excursion.status}")

    changes = {}

    # Update fields
    _apply_tracked_update(excursion, "departure_time", departure_time, changes)
    _apply_tracked_update(excursion, "return_time", return_time, changes)
    _apply_tracked_update(excursion, "max_divers", max_divers, changes)
    _apply_tracked_update(excursion, "price_per_diver", price_per_diver, changes)
    _apply_tracked_update(excursion, "currency", currency, changes)

    # Handle dive_site FK specially
    if dive_site is not None and dive_site != excursion.dive_site:
        changes["dive_site"] = {
            "old": str(excursion.dive_site_id),
            "new": str(dive_site.pk),
        }
        excursion.dive_site = dive_site

    # Handle excursion_type FK specially
    if excursion_type is not None and excursion_type != excursion.excursion_type:
        changes["excursion_type"] = {
            "old": str(excursion.excursion_type_id) if excursion.excursion_type else None,
            "new": str(excursion_type.pk),
        }
        excursion.excursion_type = excursion_type

    if changes:
        excursion.save()

        log_excursion_event(
            action=Actions.EXCURSION_UPDATED,
            excursion=excursion,
            actor=actor,
            changes=changes,
        )

    return excursion


@transaction.atomic
def cancel_excursion(
    *,
    excursion: Excursion,
    actor,
    reason: str = "",
) -> Excursion:
    """Cancel an excursion and all its active bookings.

    Args:
        excursion: Excursion to cancel
        actor: User cancelling the excursion
        reason: Optional cancellation reason

    Returns:
        Cancelled Excursion

    Raises:
        TripStateError: If excursion is already cancelled or completed
    """
    if excursion.status == "cancelled":
        raise TripStateError("Excursion is already cancelled")

    if excursion.status == "completed":
        raise TripStateError("Cannot cancel a completed excursion")

    # Cancel all active bookings
    active_bookings = excursion.bookings.filter(
        status__in=["pending", "confirmed"]
    )
    cancelled_at = timezone.now()

    for booking in active_bookings:
        booking.status = "cancelled"
        booking.cancelled_at = cancelled_at
        booking.save()

        log_booking_event(
            action=Actions.BOOKING_CANCELLED,
            booking=booking,
            actor=actor,
            data={"reason": "Excursion cancelled"},
        )

    # Cancel the excursion
    excursion.status = "cancelled"
    excursion.save()

    log_excursion_event(
        action=Actions.EXCURSION_CANCELLED,
        excursion=excursion,
        actor=actor,
        data={"reason": reason} if reason else None,
    )

    return excursion


# =============================================================================
# ExcursionType CRUD Services
# =============================================================================


@transaction.atomic
def create_excursion_type(
    *,
    actor,
    name: str,
    slug: str,
    dive_mode: str,
    time_of_day: str,
    max_depth_meters: int,
    base_price,
    currency: str = "USD",
    description: str = "",
    typical_duration_minutes: int = 60,
    dives_per_excursion: int = 2,
    min_certification_level: CertificationLevel | None = None,
    requires_cert: bool = True,
    is_training: bool = False,
    is_active: bool = True,
) -> ExcursionType:
    """Create a new excursion type.

    Args:
        actor: User creating the type (required for audit)
        name: Display name
        slug: URL-friendly unique identifier
        dive_mode: "boat" or "shore"
        time_of_day: "day", "night", "dawn", or "dusk"
        max_depth_meters: Maximum depth for this type
        base_price: Starting price (Decimal)
        currency: Currency code (default: USD)
        description: Optional description
        typical_duration_minutes: Expected duration (default: 60)
        dives_per_excursion: Number of dives included (default: 2)
        min_certification_level: Required certification FK (None = no requirement)
        requires_cert: If False, skip certification check (DSD)
        is_training: If True, this is a training dive
        is_active: If False, type is not bookable

    Returns:
        Created ExcursionType

    Raises:
        IntegrityError: If slug already exists
    """
    excursion_type = ExcursionType.objects.create(
        name=name,
        slug=slug,
        description=description,
        dive_mode=dive_mode,
        time_of_day=time_of_day,
        max_depth_meters=max_depth_meters,
        typical_duration_minutes=typical_duration_minutes,
        dives_per_excursion=dives_per_excursion,
        min_certification_level=min_certification_level,
        requires_cert=requires_cert,
        is_training=is_training,
        base_price=base_price,
        currency=currency,
        is_active=is_active,
    )

    log_excursion_type_event(
        action=Actions.EXCURSION_TYPE_CREATED,
        excursion_type=excursion_type,
        actor=actor,
    )

    return excursion_type


@transaction.atomic
def update_excursion_type(
    *,
    actor,
    excursion_type: ExcursionType,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    dive_mode: str | None = None,
    time_of_day: str | None = None,
    max_depth_meters: int | None = None,
    typical_duration_minutes: int | None = None,
    dives_per_excursion: int | None = None,
    min_certification_level: CertificationLevel | None = None,
    requires_cert: bool | None = None,
    is_training: bool | None = None,
    base_price=None,
    currency: str | None = None,
    is_active: bool | None = None,
) -> ExcursionType:
    """Update an existing excursion type.

    Only provided fields are updated. Pass explicit value to change.

    Args:
        actor: User making the update (required for audit)
        excursion_type: ExcursionType to update
        name: New name (None = no change)
        slug: New slug (None = no change)
        description: New description (None = no change)
        dive_mode: New dive mode (None = no change)
        time_of_day: New time of day (None = no change)
        max_depth_meters: New max depth (None = no change)
        typical_duration_minutes: New duration (None = no change)
        dives_per_excursion: New dive count (None = no change)
        min_certification_level: New certification FK (None = no change)
        requires_cert: New requires_cert flag (None = no change)
        is_training: New is_training flag (None = no change)
        base_price: New base price (None = no change)
        currency: New currency (None = no change)
        is_active: New active status (None = no change)

    Returns:
        Updated ExcursionType
    """
    changes = {}

    # Update simple fields
    _apply_tracked_update(excursion_type, "name", name, changes)
    _apply_tracked_update(excursion_type, "slug", slug, changes)
    _apply_tracked_update(excursion_type, "description", description, changes)
    _apply_tracked_update(excursion_type, "dive_mode", dive_mode, changes)
    _apply_tracked_update(excursion_type, "time_of_day", time_of_day, changes)
    _apply_tracked_update(excursion_type, "max_depth_meters", max_depth_meters, changes)
    _apply_tracked_update(excursion_type, "typical_duration_minutes", typical_duration_minutes, changes)
    _apply_tracked_update(excursion_type, "dives_per_excursion", dives_per_excursion, changes)
    _apply_tracked_update(excursion_type, "requires_cert", requires_cert, changes)
    _apply_tracked_update(excursion_type, "is_training", is_training, changes)
    _apply_tracked_update(excursion_type, "base_price", base_price, changes)
    _apply_tracked_update(excursion_type, "currency", currency, changes)
    _apply_tracked_update(excursion_type, "is_active", is_active, changes)

    # Handle min_certification_level FK specially (can be set to None explicitly)
    if min_certification_level is not None or "min_certification_level" in changes:
        old_id = excursion_type.min_certification_level_id
        new_id = min_certification_level.pk if min_certification_level else None
        if new_id != old_id:
            changes["min_certification_level"] = {
                "old": str(old_id) if old_id else None,
                "new": str(new_id) if new_id else None,
            }
            excursion_type.min_certification_level = min_certification_level

    if changes:
        excursion_type.save()

        log_excursion_type_event(
            action=Actions.EXCURSION_TYPE_UPDATED,
            excursion_type=excursion_type,
            actor=actor,
            changes=changes,
        )

    return excursion_type


@transaction.atomic
def delete_excursion_type(
    *,
    actor,
    excursion_type: ExcursionType,
) -> ExcursionType:
    """Soft delete an excursion type.

    Sets deleted_at timestamp instead of actually deleting.
    The type will be excluded from default queries.

    Args:
        actor: User deleting the type (required for audit)
        excursion_type: ExcursionType to delete

    Returns:
        Updated ExcursionType with deleted_at set
    """
    excursion_type.deleted_at = timezone.now()
    excursion_type.save()

    log_excursion_type_event(
        action=Actions.EXCURSION_TYPE_DELETED,
        excursion_type=excursion_type,
        actor=actor,
    )

    return excursion_type


# =============================================================================
# SitePriceAdjustment CRUD Services
# =============================================================================


@transaction.atomic
def create_site_price_adjustment(
    *,
    actor,
    dive_site: DiveSite,
    kind: str,
    amount,
    currency: str = "USD",
    applies_to_mode: str = "",
    is_per_diver: bool = True,
    is_active: bool = True,
) -> SitePriceAdjustment:
    """Create a new price adjustment for a dive site.

    Args:
        actor: User creating the adjustment (required for audit)
        dive_site: DiveSite this adjustment applies to
        kind: Adjustment type (distance, park_fee, night, boat)
        amount: Adjustment amount (Decimal)
        currency: Currency code (default: USD)
        applies_to_mode: Optional mode filter (boat/shore, empty = all)
        is_per_diver: If True, applied per diver; else per trip
        is_active: If False, adjustment is not applied

    Returns:
        Created SitePriceAdjustment

    Raises:
        IntegrityError: If constraints are violated
    """
    adjustment = SitePriceAdjustment.objects.create(
        dive_site=dive_site,
        kind=kind,
        amount=amount,
        currency=currency,
        applies_to_mode=applies_to_mode,
        is_per_diver=is_per_diver,
        is_active=is_active,
    )

    log_site_price_adjustment_event(
        action=Actions.SITE_PRICE_ADJUSTMENT_CREATED,
        adjustment=adjustment,
        actor=actor,
    )

    return adjustment


@transaction.atomic
def update_site_price_adjustment(
    *,
    actor,
    adjustment: SitePriceAdjustment,
    kind: str | None = None,
    amount=None,
    currency: str | None = None,
    applies_to_mode: str | None = None,
    is_per_diver: bool | None = None,
    is_active: bool | None = None,
) -> SitePriceAdjustment:
    """Update an existing price adjustment.

    Only provided fields are updated. Pass explicit value to change.

    Args:
        actor: User making the update (required for audit)
        adjustment: SitePriceAdjustment to update
        kind: New adjustment type (None = no change)
        amount: New amount (None = no change)
        currency: New currency (None = no change)
        applies_to_mode: New mode filter (None = no change)
        is_per_diver: New per-diver flag (None = no change)
        is_active: New active status (None = no change)

    Returns:
        Updated SitePriceAdjustment
    """
    changes = {}

    _apply_tracked_update(adjustment, "kind", kind, changes)
    _apply_tracked_update(adjustment, "amount", amount, changes)
    _apply_tracked_update(adjustment, "currency", currency, changes)
    _apply_tracked_update(adjustment, "applies_to_mode", applies_to_mode, changes)
    _apply_tracked_update(adjustment, "is_per_diver", is_per_diver, changes)
    _apply_tracked_update(adjustment, "is_active", is_active, changes)

    if changes:
        adjustment.save()

        log_site_price_adjustment_event(
            action=Actions.SITE_PRICE_ADJUSTMENT_UPDATED,
            adjustment=adjustment,
            actor=actor,
            changes=changes,
        )

    return adjustment


@transaction.atomic
def delete_site_price_adjustment(
    *,
    actor,
    adjustment: SitePriceAdjustment,
) -> SitePriceAdjustment:
    """Soft delete a price adjustment.

    Sets deleted_at timestamp instead of actually deleting.
    The adjustment will be excluded from default queries.

    Args:
        actor: User deleting the adjustment (required for audit)
        adjustment: SitePriceAdjustment to delete

    Returns:
        Updated SitePriceAdjustment with deleted_at set
    """
    adjustment.deleted_at = timezone.now()
    adjustment.save()

    log_site_price_adjustment_event(
        action=Actions.SITE_PRICE_ADJUSTMENT_DELETED,
        adjustment=adjustment,
        actor=actor,
    )

    return adjustment


# =============================================================================
# T-005: Revenue Settlement Services
# =============================================================================


@transaction.atomic
def create_revenue_settlement(
    booking: "Booking",
    *,
    processed_by,
    effective_at=None,
) -> "SettlementRecord":
    """Create revenue settlement for a booking (idempotent).

    Records revenue recognition for a booking by:
    1. Creating a SettlementRecord with deterministic idempotency key
    2. Creating balanced ledger transaction (DR: Receivable, CR: Revenue)
    3. Emitting audit event

    T-005: This is the first financial posting primitive. Revenue only.
    Refunds are out of scope (T-006).

    Idempotency: If called twice with same booking, returns existing record.
    The idempotency_key is deterministic: "{booking_id}:revenue:1"

    Args:
        booking: Booking to settle (must have price_amount)
        processed_by: User processing the settlement
        effective_at: When the settlement is effective (defaults to now)

    Returns:
        SettlementRecord (new or existing if idempotent)

    Raises:
        ValueError: If booking has no price_amount or is cancelled
    """
    from django_ledger.models import Account
    from django_ledger.services import record_transaction

    from .models import SettlementRecord

    # Validate booking has price snapshot
    if booking.price_amount is None:
        raise ValueError(
            "Cannot create revenue settlement: booking has no price_amount. "
            "Price snapshot is required for settlement."
        )

    # Validate booking status - cannot settle cancelled bookings
    if booking.status == "cancelled":
        raise ValueError(
            "Cannot create revenue settlement: booking is cancelled. "
            "Cancelled bookings cannot be settled for revenue."
        )

    # Build deterministic idempotency key
    idempotency_key = f"{booking.pk}:revenue:1"

    # Check for existing settlement (idempotent)
    existing = SettlementRecord.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    effective_at = effective_at or timezone.now()

    # Get or create accounts for the transaction
    # DR: Accounts Receivable (owned by diver's person)
    # CR: Revenue (owned by dive shop)
    diver_owner = booking.diver.person
    shop_owner = booking.excursion.dive_shop

    receivable_account, _ = Account.objects.get_or_create(
        owner_content_type=ContentType.objects.get_for_model(diver_owner),
        owner_id=str(diver_owner.pk),
        account_type="receivable",
        currency=booking.price_currency or "USD",
        defaults={"name": f"Receivable - {diver_owner}"},
    )

    revenue_account, _ = Account.objects.get_or_create(
        owner_content_type=ContentType.objects.get_for_model(shop_owner),
        owner_id=str(shop_owner.pk),
        account_type="revenue",
        currency=booking.price_currency or "USD",
        defaults={"name": f"Revenue - {shop_owner}"},
    )

    # Create balanced ledger transaction
    tx = record_transaction(
        description=f"Revenue for booking {booking.pk}",
        entries=[
            {
                "account": receivable_account,
                "amount": booking.price_amount,
                "entry_type": "debit",
                "description": "Customer receivable",
            },
            {
                "account": revenue_account,
                "amount": booking.price_amount,
                "entry_type": "credit",
                "description": "Booking revenue",
            },
        ],
        effective_at=effective_at,
        metadata={
            "booking_id": str(booking.pk),
            "idempotency_key": idempotency_key,
            "settlement_type": "revenue",
        },
    )

    # Create settlement record
    settlement = SettlementRecord.objects.create(
        booking=booking,
        settlement_type="revenue",
        idempotency_key=idempotency_key,
        amount=booking.price_amount,
        currency=booking.price_currency or "USD",
        transaction=tx,
        processed_by=processed_by,
        settled_at=effective_at,
    )

    # Emit audit event
    log_settlement_event(
        action=Actions.SETTLEMENT_POSTED,
        settlement=settlement,
        actor=processed_by,
    )

    return settlement


# =============================================================================
# T-006: Refund Settlement Services
# =============================================================================


@transaction.atomic
def create_refund_settlement(
    booking: "Booking",
    refund_decision: RefundDecision,
    *,
    processed_by,
    effective_at=None,
) -> "SettlementRecord | None":
    """Create refund settlement for a cancelled booking (idempotent).

    Records refund for a cancelled booking by:
    1. Creating a SettlementRecord with deterministic idempotency key
    2. Creating balanced ledger transaction (DR: Revenue, CR: Receivable)
    3. Emitting audit event

    T-006: This reverses revenue direction for refunds.
    Requires RefundDecision from cancel_booking().

    Idempotency: If called twice with same booking, returns existing record.
    The idempotency_key is deterministic: "{booking_id}:refund:1"

    Zero refund: If refund_decision.refund_amount is 0, returns None.
    No settlement or ledger entry is created for zero refunds.

    Args:
        booking: Cancelled booking to refund
        refund_decision: RefundDecision from cancel_booking()
        processed_by: User processing the settlement
        effective_at: When the settlement is effective (defaults to now)

    Returns:
        SettlementRecord (new or existing if idempotent), or None if zero refund

    Raises:
        ValueError: If refund_decision is None or booking is not cancelled
    """
    from django_ledger.models import Account
    from django_ledger.services import record_transaction

    from .models import SettlementRecord

    # Validate refund_decision is provided
    if refund_decision is None:
        raise ValueError(
            "Cannot create refund settlement: refund_decision is required. "
            "Use cancel_booking() to compute the refund decision first."
        )

    # Validate booking status - must be cancelled for refund
    if booking.status != "cancelled":
        raise ValueError(
            "Cannot create refund settlement: booking is not cancelled. "
            "Only cancelled bookings can be refunded."
        )

    # Zero refund - no settlement needed
    if refund_decision.refund_amount == 0:
        return None

    # Build deterministic idempotency key
    idempotency_key = f"{booking.pk}:refund:1"

    # Check for existing settlement (idempotent)
    existing = SettlementRecord.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    effective_at = effective_at or timezone.now()

    # Get or create accounts for the transaction
    # Refund REVERSES revenue direction:
    # DR: Revenue (reduce revenue)
    # CR: Accounts Receivable (reduce receivable)
    diver_owner = booking.diver.person
    shop_owner = booking.excursion.dive_shop

    receivable_account, _ = Account.objects.get_or_create(
        owner_content_type=ContentType.objects.get_for_model(diver_owner),
        owner_id=str(diver_owner.pk),
        account_type="receivable",
        currency=refund_decision.currency,
        defaults={"name": f"Receivable - {diver_owner}"},
    )

    revenue_account, _ = Account.objects.get_or_create(
        owner_content_type=ContentType.objects.get_for_model(shop_owner),
        owner_id=str(shop_owner.pk),
        account_type="revenue",
        currency=refund_decision.currency,
        defaults={"name": f"Revenue - {shop_owner}"},
    )

    # Create balanced ledger transaction - REVERSED from revenue
    tx = record_transaction(
        description=f"Refund for booking {booking.pk}",
        entries=[
            {
                "account": revenue_account,
                "amount": refund_decision.refund_amount,
                "entry_type": "debit",
                "description": "Revenue reversal (refund)",
            },
            {
                "account": receivable_account,
                "amount": refund_decision.refund_amount,
                "entry_type": "credit",
                "description": "Receivable reversal (refund)",
            },
        ],
        effective_at=effective_at,
        metadata={
            "booking_id": str(booking.pk),
            "idempotency_key": idempotency_key,
            "settlement_type": "refund",
            "refund_percent": refund_decision.refund_percent,
            "original_amount": str(refund_decision.original_amount),
        },
    )

    # Create settlement record
    settlement = SettlementRecord.objects.create(
        booking=booking,
        settlement_type="refund",
        idempotency_key=idempotency_key,
        amount=refund_decision.refund_amount,
        currency=refund_decision.currency,
        transaction=tx,
        processed_by=processed_by,
        settled_at=effective_at,
    )

    # Emit audit event
    log_settlement_event(
        action=Actions.REFUND_SETTLEMENT_POSTED,
        settlement=settlement,
        actor=processed_by,
        data={
            "refund_percent": refund_decision.refund_percent,
            "original_amount": str(refund_decision.original_amount),
        },
    )

    return settlement


# =============================================================================
# Dive CRUD Services
# =============================================================================


@transaction.atomic
def create_dive(
    *,
    actor,
    excursion: Excursion,
    dive_site: DiveSite,
    sequence: int,
    planned_start,
    planned_duration_minutes: int | None = None,
    max_depth_meters: int | None = None,
    notes: str = "",
) -> Dive:
    """Create a new dive within an excursion.

    Args:
        actor: User creating the dive (required for audit)
        excursion: Excursion this dive belongs to
        dive_site: DiveSite where the dive takes place
        sequence: Order of this dive in the excursion (1, 2, 3, etc.)
        planned_start: Planned start datetime
        planned_duration_minutes: Optional planned duration
        max_depth_meters: Optional max planned depth
        notes: Optional notes

    Returns:
        Created Dive

    Raises:
        IntegrityError: If constraints are violated
    """
    dive = Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=sequence,
        planned_start=planned_start,
        planned_duration_minutes=planned_duration_minutes,
        max_depth_meters=max_depth_meters,
        notes=notes,
    )

    log_dive_event(
        action=Actions.DIVE_CREATED,
        dive=dive,
        actor=actor,
    )

    return dive


@transaction.atomic
def update_dive(
    *,
    actor,
    dive: Dive,
    dive_site: DiveSite | None = None,
    sequence: int | None = None,
    planned_start=None,
    planned_duration_minutes: int | None = None,
    max_depth_meters: int | None = None,
    notes: str | None = None,
) -> Dive:
    """Update an existing dive.

    Args:
        actor: User making the update (required for audit)
        dive: Dive to update
        dive_site: New dive site (None = no change)
        sequence: New sequence (None = no change)
        planned_start: New planned start (None = no change)
        planned_duration_minutes: New duration (None = no change)
        max_depth_meters: New max depth (None = no change)
        notes: New notes (None = no change)

    Returns:
        Updated Dive
    """
    changes = {}

    _apply_tracked_update(dive, "sequence", sequence, changes)
    _apply_tracked_update(dive, "planned_start", planned_start, changes)
    _apply_tracked_update(dive, "planned_duration_minutes", planned_duration_minutes, changes)
    _apply_tracked_update(dive, "max_depth_meters", max_depth_meters, changes)
    _apply_tracked_update(dive, "notes", notes, changes)

    # Handle dive_site FK specially
    if dive_site is not None and dive_site != dive.dive_site:
        changes["dive_site"] = {
            "old": str(dive.dive_site_id),
            "new": str(dive_site.pk),
        }
        dive.dive_site = dive_site

    if changes:
        dive.save()

        log_dive_event(
            action=Actions.DIVE_UPDATED,
            dive=dive,
            actor=actor,
            changes=changes,
        )

    return dive


@transaction.atomic
def delete_dive(
    *,
    actor,
    dive: Dive,
) -> Dive:
    """Soft delete a dive.

    Sets deleted_at timestamp instead of actually deleting.
    The dive will be excluded from default queries.

    Args:
        actor: User deleting the dive (required for audit)
        dive: Dive to delete

    Returns:
        Updated Dive with deleted_at set
    """
    dive.deleted_at = timezone.now()
    dive.save()

    log_dive_event(
        action=Actions.DIVE_DELETED,
        dive=dive,
        actor=actor,
    )

    return dive


# =============================================================================
# ExcursionTypeDive (Dive Template) CRUD Services
# =============================================================================


@transaction.atomic
def create_dive_template(
    *,
    actor,
    excursion_type: ExcursionType,
    name: str,
    sequence: int,
    offset_minutes: int = 0,
    planned_duration_minutes: int | None = None,
    description: str = "",
    planned_depth_meters: int | None = None,
    min_certification_level: CertificationLevel | None = None,
) -> ExcursionTypeDive:
    """Create a new dive template for an excursion type.

    Args:
        actor: User creating the template (required for audit)
        excursion_type: ExcursionType this template belongs to
        name: Name of this dive (e.g., "First Dive", "Night Dive")
        sequence: Order of this dive (1, 2, 3, etc.)
        offset_minutes: Minutes after departure when this dive starts
        planned_duration_minutes: Optional planned duration
        description: Optional description
        planned_depth_meters: Optional planned depth
        min_certification_level: Optional certification level override

    Returns:
        Created ExcursionTypeDive

    Raises:
        IntegrityError: If constraints are violated
    """
    dive_template = ExcursionTypeDive.objects.create(
        excursion_type=excursion_type,
        name=name,
        sequence=sequence,
        offset_minutes=offset_minutes,
        planned_duration_minutes=planned_duration_minutes,
        description=description,
        planned_depth_meters=planned_depth_meters,
        min_certification_level=min_certification_level,
    )

    log_dive_template_event(
        action=Actions.DIVE_TEMPLATE_CREATED,
        dive_template=dive_template,
        actor=actor,
    )

    return dive_template


@transaction.atomic
def update_dive_template(
    *,
    actor,
    dive_template: ExcursionTypeDive,
    name: str | None = None,
    sequence: int | None = None,
    offset_minutes: int | None = None,
    planned_duration_minutes: int | None = None,
    description: str | None = None,
    planned_depth_meters: int | None = None,
    min_certification_level: CertificationLevel | None = None,
    clear_min_certification: bool = False,
) -> ExcursionTypeDive:
    """Update an existing dive template.

    Args:
        actor: User making the update (required for audit)
        dive_template: ExcursionTypeDive to update
        name: New name (None = no change)
        sequence: New sequence (None = no change)
        offset_minutes: New offset (None = no change)
        planned_duration_minutes: New duration (None = no change)
        description: New description (None = no change)
        planned_depth_meters: New planned depth (None = no change)
        min_certification_level: New certification level (None = no change)
        clear_min_certification: If True, clear min_certification_level

    Returns:
        Updated ExcursionTypeDive
    """
    changes = {}

    _apply_tracked_update(dive_template, "name", name, changes)
    _apply_tracked_update(dive_template, "sequence", sequence, changes)
    _apply_tracked_update(dive_template, "offset_minutes", offset_minutes, changes)
    _apply_tracked_update(dive_template, "planned_duration_minutes", planned_duration_minutes, changes)
    _apply_tracked_update(dive_template, "description", description, changes)
    _apply_tracked_update(dive_template, "planned_depth_meters", planned_depth_meters, changes)

    # Handle min_certification_level FK specially
    if clear_min_certification:
        if dive_template.min_certification_level_id is not None:
            changes["min_certification_level"] = {
                "old": str(dive_template.min_certification_level_id),
                "new": None,
            }
            dive_template.min_certification_level = None
    elif min_certification_level is not None and min_certification_level != dive_template.min_certification_level:
        changes["min_certification_level"] = {
            "old": str(dive_template.min_certification_level_id) if dive_template.min_certification_level_id else None,
            "new": str(min_certification_level.pk),
        }
        dive_template.min_certification_level = min_certification_level

    if changes:
        dive_template.save()

        log_dive_template_event(
            action=Actions.DIVE_TEMPLATE_UPDATED,
            dive_template=dive_template,
            actor=actor,
            changes=changes,
        )

    return dive_template


@transaction.atomic
def delete_dive_template(
    *,
    actor,
    dive_template: ExcursionTypeDive,
) -> None:
    """Delete a dive template (hard delete).

    Dive templates are configuration data, not transactional records,
    so hard delete is appropriate. The audit log preserves history.

    Args:
        actor: User deleting the template (required for audit)
        dive_template: ExcursionTypeDive to delete
    """
    # Capture metadata before deletion
    log_dive_template_event(
        action=Actions.DIVE_TEMPLATE_DELETED,
        dive_template=dive_template,
        actor=actor,
    )

    dive_template.delete()


# =============================================================================
# Dive Log Services
# =============================================================================


@transaction.atomic
def log_dive_results(
    *,
    actor,
    dive: Dive,
    actual_start,
    actual_end,
    max_depth_meters: int,
    bottom_time_minutes: int | None = None,
    visibility_meters: int | None = None,
    water_temp_celsius=None,
    surface_conditions: str = "",
    current: str = "",
) -> Dive:
    """Log actual results for a completed dive.

    Updates the Dive record with actual conditions and creates DiveLog
    entries for all participating divers (status in_water, surfaced, or on_boat).

    This operation is idempotent - calling twice will update the Dive
    but not duplicate DiveLog entries.

    Args:
        actor: Staff user logging the results
        dive: Dive instance to update
        actual_start: When dive actually started
        actual_end: When dive actually ended
        max_depth_meters: Maximum depth reached
        bottom_time_minutes: Total bottom time (optional)
        visibility_meters: Visibility in meters (optional)
        water_temp_celsius: Water temperature (optional)
        surface_conditions: Surface conditions (optional)
        current: Current strength (optional)

    Returns:
        Updated Dive instance
    """
    # Update dive with actual results
    dive.actual_start = actual_start
    dive.actual_end = actual_end
    dive.max_depth_meters = max_depth_meters

    if bottom_time_minutes is not None:
        dive.bottom_time_minutes = bottom_time_minutes

    if visibility_meters is not None:
        dive.visibility_meters = visibility_meters

    if water_temp_celsius is not None:
        dive.water_temp_celsius = water_temp_celsius

    if surface_conditions:
        dive.surface_conditions = surface_conditions

    if current:
        dive.current = current

    # Set audit fields
    dive.logged_by = actor
    dive.logged_at = timezone.now()

    dive.save()

    # Create DiveLog entries for participating divers
    # Participating statuses: in_water, surfaced, on_boat
    participating_statuses = [
        DiveAssignment.Status.IN_WATER,
        DiveAssignment.Status.SURFACED,
        DiveAssignment.Status.ON_BOAT,
    ]

    assignments = dive.assignments.filter(status__in=participating_statuses)

    for assignment in assignments:
        # Check if DiveLog already exists (idempotency)
        if not DiveLog.objects.filter(dive=dive, diver=assignment.diver).exists():
            # Calculate dive number for this diver
            existing_logs = DiveLog.objects.filter(diver=assignment.diver).count()
            dive_number = existing_logs + 1

            DiveLog.objects.create(
                dive=dive,
                diver=assignment.diver,
                assignment=assignment,
                dive_number=dive_number,
            )

    # Log audit event
    log_dive_event(
        action=Actions.DIVE_LOGGED,
        dive=dive,
        actor=actor,
    )

    return dive


@transaction.atomic
def update_diver_status(
    *,
    actor,
    assignment: DiveAssignment,
    new_status: str,
) -> DiveAssignment:
    """Update a diver's status during a dive.

    Tracks status changes and automatically sets timestamps for key transitions:
    - entered_water_at: Set on first transition to 'in_water'
    - surfaced_at: Set on first transition to 'surfaced'

    Args:
        actor: Staff user making the change
        assignment: DiveAssignment to update
        new_status: New status value

    Returns:
        Updated DiveAssignment instance
    """
    old_status = assignment.status
    now = timezone.now()

    # Update status
    assignment.status = new_status

    # Set timestamps on first transition only
    if new_status == DiveAssignment.Status.IN_WATER and assignment.entered_water_at is None:
        assignment.entered_water_at = now

    if new_status == DiveAssignment.Status.SURFACED and assignment.surfaced_at is None:
        assignment.surfaced_at = now

    assignment.save()

    # Log audit event with status change
    log_dive_assignment_event(
        action=Actions.DIVER_STATUS_CHANGED,
        assignment=assignment,
        actor=actor,
        changes={"status": {"old": old_status, "new": new_status}},
    )

    return assignment


@transaction.atomic
def verify_dive_log(
    *,
    actor,
    dive_log: DiveLog,
) -> DiveLog:
    """Verify a dive log entry.

    Sets verified_by and verified_at to record who verified the log and when.
    Can be called multiple times - subsequent calls update the verifier.

    Args:
        actor: Staff user verifying the log
        dive_log: DiveLog to verify

    Returns:
        Updated DiveLog instance
    """
    dive_log.verified_by = actor
    dive_log.verified_at = timezone.now()
    dive_log.save()

    log_dive_log_event(
        action=Actions.DIVE_LOG_VERIFIED,
        dive_log=dive_log,
        actor=actor,
    )

    return dive_log


@transaction.atomic
def update_dive_log(
    *,
    actor,
    dive_log: DiveLog,
    max_depth_meters=None,
    bottom_time_minutes: int | None = None,
    air_start_bar: int | None = None,
    air_end_bar: int | None = None,
    weight_kg=None,
    suit_type: str | None = None,
    tank_size_liters: int | None = None,
    nitrox_percentage: int | None = None,
    notes: str | None = None,
    buddy_name: str | None = None,
) -> DiveLog:
    """Update personal details on a dive log.

    Only updates fields that are explicitly provided (not None).
    Tracks changes for audit purposes. No audit event is logged if
    no values actually changed.

    Args:
        actor: User making the update
        dive_log: DiveLog to update
        max_depth_meters: Personal max depth (optional)
        bottom_time_minutes: Personal bottom time (optional)
        air_start_bar: Starting air pressure (optional)
        air_end_bar: Ending air pressure (optional)
        weight_kg: Weight used (optional)
        suit_type: Wetsuit/drysuit type (optional)
        tank_size_liters: Tank size (optional)
        nitrox_percentage: Nitrox percentage (optional)
        notes: Personal notes (optional)
        buddy_name: Buddy name (optional)

    Returns:
        Updated DiveLog instance
    """
    changes = {}

    # Track changes for all updatable fields
    field_updates = [
        ("max_depth_meters", max_depth_meters),
        ("bottom_time_minutes", bottom_time_minutes),
        ("air_start_bar", air_start_bar),
        ("air_end_bar", air_end_bar),
        ("weight_kg", weight_kg),
        ("suit_type", suit_type),
        ("tank_size_liters", tank_size_liters),
        ("nitrox_percentage", nitrox_percentage),
        ("notes", notes),
        ("buddy_name", buddy_name),
    ]

    for field_name, new_value in field_updates:
        if new_value is not None:
            old_value = getattr(dive_log, field_name)
            # Convert to comparable types
            old_comparable = str(old_value) if old_value is not None else None
            new_comparable = str(new_value)

            if old_comparable != new_comparable:
                # Convert Decimal to string for JSON serialization
                old_for_json = str(old_value) if old_value is not None else None
                new_for_json = str(new_value)
                changes[field_name] = {"old": old_for_json, "new": new_for_json}
                setattr(dive_log, field_name, new_value)

    if changes:
        dive_log.save()

        log_dive_log_event(
            action=Actions.DIVE_LOG_UPDATED,
            dive_log=dive_log,
            actor=actor,
            changes=changes,
        )

    return dive_log


# =============================================================================
# Dive Plan Lifecycle Services
# =============================================================================


@transaction.atomic
def publish_dive_template(
    *,
    actor,
    dive_template: "ExcursionTypeDive",
) -> "ExcursionTypeDive":
    """Publish a dive template for use in excursions.

    Changes template status from draft to published, making it available
    for use when locking dive plans.

    Args:
        actor: Staff user publishing the template
        dive_template: ExcursionTypeDive to publish

    Returns:
        Updated ExcursionTypeDive

    Raises:
        ValueError: If template is not in draft status
    """
    from .models import ExcursionTypeDive

    if dive_template.status != ExcursionTypeDive.PlanStatus.DRAFT:
        raise ValueError(
            f"Cannot publish template: not in draft status (current: {dive_template.status})"
        )

    dive_template.status = ExcursionTypeDive.PlanStatus.PUBLISHED
    dive_template.published_at = timezone.now()
    dive_template.published_by = actor
    dive_template.save()

    log_dive_template_event(
        action=Actions.DIVE_TEMPLATE_PUBLISHED,
        dive_template=dive_template,
        actor=actor,
    )

    return dive_template


@transaction.atomic
def retire_dive_template(
    *,
    actor,
    dive_template: "ExcursionTypeDive",
) -> "ExcursionTypeDive":
    """Retire a dive template.

    Changes template status from published to retired, making it unavailable
    for new excursions. Existing scheduled dives with locked snapshots are
    not affected.

    Args:
        actor: Staff user retiring the template
        dive_template: ExcursionTypeDive to retire

    Returns:
        Updated ExcursionTypeDive

    Raises:
        ValueError: If template is not in published status
    """
    from .models import ExcursionTypeDive

    if dive_template.status != ExcursionTypeDive.PlanStatus.PUBLISHED:
        raise ValueError(
            f"Cannot retire template: not in published status (current: {dive_template.status})"
        )

    dive_template.status = ExcursionTypeDive.PlanStatus.RETIRED
    dive_template.retired_at = timezone.now()
    dive_template.retired_by = actor
    dive_template.save()

    log_dive_template_event(
        action=Actions.DIVE_TEMPLATE_RETIRED,
        dive_template=dive_template,
        actor=actor,
    )

    return dive_template


# =============================================================================
# Dive Plan Snapshot Helpers
# =============================================================================


def build_plan_snapshot(*, template: "ExcursionTypeDive", dive: "Dive") -> dict:
    """Build the snapshot dictionary from template and dive.

    Creates a versioned JSON structure containing all relevant template
    and dive information to freeze at the time of locking.

    Args:
        template: ExcursionTypeDive template to snapshot
        dive: Dive instance being locked

    Returns:
        Dictionary suitable for storing in plan_snapshot field
    """
    return {
        "version": 1,
        "template": {
            "id": str(template.id),
            "name": template.name,
            "status": template.status,
            "published_at": (
                template.published_at.isoformat()
                if template.published_at
                else None
            ),
        },
        "planning": {
            "sequence": template.sequence,
            "planned_depth_meters": template.planned_depth_meters,
            "planned_duration_minutes": template.planned_duration_minutes,
            "offset_minutes": template.offset_minutes,
        },
        "briefing": {
            "gas": template.gas,
            "equipment_requirements": template.equipment_requirements,
            "skills": template.skills,
            "route": template.route,
            "hazards": template.hazards,
            "briefing_text": template.briefing_text,
        },
        "certification": {
            "min_level_id": (
                str(template.min_certification_level_id)
                if template.min_certification_level_id
                else None
            ),
            "min_level_name": (
                template.min_certification_level.name
                if template.min_certification_level
                else None
            ),
        },
        "metadata": {
            "locked_at": timezone.now().isoformat(),
        },
    }


# =============================================================================
# Dive Plan Locking Services
# =============================================================================


@transaction.atomic
def lock_dive_plan(
    *,
    actor,
    dive: "Dive",
    force: bool = False,
) -> "Dive":
    """Lock the dive plan by creating a snapshot.

    Snapshots the current state of the associated ExcursionTypeDive
    template. After locking, template changes don't affect this dive.

    This operation is idempotent - if already locked and force=False,
    returns the dive unchanged.

    Args:
        actor: Staff user locking the plan
        dive: Dive to lock
        force: If True, re-lock even if already locked (for resnapshot)

    Returns:
        Updated Dive with plan_snapshot populated

    Raises:
        ValidationError: If template is not published (unless force=True)
        ValueError: If no template available to snapshot
    """
    from django.core.exceptions import ValidationError

    from .models import ExcursionTypeDive

    # Idempotent: if already locked and not forcing, return unchanged
    if dive.plan_locked_at is not None and not force:
        return dive

    # Find matching template by sequence
    if not dive.excursion or not dive.excursion.excursion_type:
        raise ValueError("Cannot lock dive plan: no excursion type template available")

    try:
        template = ExcursionTypeDive.objects.get(
            excursion_type=dive.excursion.excursion_type,
            sequence=dive.sequence,
        )
    except ExcursionTypeDive.DoesNotExist:
        raise ValueError(
            f"Cannot lock dive plan: no template found for sequence {dive.sequence}"
        )

    # Validate template is published (unless force)
    if template.status != ExcursionTypeDive.PlanStatus.PUBLISHED and not force:
        raise ValidationError(
            f"Cannot lock dive plan: template not published (status: {template.status})"
        )

    # Build and save snapshot
    dive.plan_snapshot = build_plan_snapshot(template=template, dive=dive)
    dive.plan_locked_at = timezone.now()
    dive.plan_locked_by = actor
    dive.plan_template_id = template.id
    dive.plan_template_published_at = template.published_at
    dive.plan_snapshot_outdated = False
    dive.save()

    log_dive_event(
        action=Actions.DIVE_PLAN_LOCKED,
        dive=dive,
        actor=actor,
        data={
            "template_id": str(template.id),
            "template_name": template.name,
        },
    )

    return dive


@transaction.atomic
def resnapshot_dive_plan(
    *,
    actor,
    dive: "Dive",
    reason: str,
) -> "Dive":
    """Re-snapshot an already locked dive plan.

    This is a privileged operation for correcting briefings before
    the dive occurs. Requires explicit reason for audit trail.

    Args:
        actor: Staff user re-snapshotting
        dive: Already-locked Dive to update
        reason: Explanation for the resnapshot (required)

    Returns:
        Updated Dive with new plan_snapshot

    Raises:
        ValueError: If dive is not currently locked
        ValueError: If reason is empty
    """
    from .models import ExcursionTypeDive

    if dive.plan_locked_at is None:
        raise ValueError("Cannot resnapshot: dive is not locked")

    if not reason or not reason.strip():
        raise ValueError("Cannot resnapshot: reason is required")

    # Get fresh template
    try:
        template = ExcursionTypeDive.objects.get(
            excursion_type=dive.excursion.excursion_type,
            sequence=dive.sequence,
        )
    except ExcursionTypeDive.DoesNotExist:
        raise ValueError(
            f"Cannot resnapshot: no template found for sequence {dive.sequence}"
        )

    # Store old snapshot for audit
    old_snapshot = dive.plan_snapshot

    # Build and save new snapshot
    dive.plan_snapshot = build_plan_snapshot(template=template, dive=dive)
    dive.plan_locked_at = timezone.now()
    dive.plan_locked_by = actor
    dive.plan_template_id = template.id
    dive.plan_template_published_at = template.published_at
    dive.plan_snapshot_outdated = False
    dive.save()

    log_dive_event(
        action=Actions.DIVE_PLAN_RESNAPSHOTTED,
        dive=dive,
        actor=actor,
        changes={
            "reason": reason,
            "old_snapshot": old_snapshot,
            "new_snapshot": dive.plan_snapshot,
        },
        data={
            "template_id": str(template.id),
            "reason": reason,
        },
    )

    return dive


@transaction.atomic
def lock_excursion_plans(
    *,
    actor,
    excursion: "Excursion",
) -> list["Dive"]:
    """Lock plans for all dives in an excursion.

    Typically called when sending briefing to customers. Only locks
    dives that are not already locked.

    Args:
        actor: Staff user locking plans
        excursion: Excursion whose dives to lock

    Returns:
        List of locked Dive instances
    """
    from .models import Dive

    # Get all unlocked dives in this excursion
    unlocked_dives = excursion.dives.filter(plan_locked_at__isnull=True)

    locked_dives = []
    for dive in unlocked_dives:
        try:
            locked_dive = lock_dive_plan(actor=actor, dive=dive)
            locked_dives.append(locked_dive)
        except (ValueError, Exception):
            # Skip dives without templates or other issues
            pass

    if locked_dives:
        log_excursion_event(
            action=Actions.EXCURSION_PLANS_LOCKED,
            excursion=excursion,
            actor=actor,
            data={
                "dives_locked": len(locked_dives),
                "dive_ids": [str(d.id) for d in locked_dives],
            },
        )

    return locked_dives
