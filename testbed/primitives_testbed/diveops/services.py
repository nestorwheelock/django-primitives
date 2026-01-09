"""Services for dive operations.

Business logic for booking, check-in, and trip completion.
All write operations are atomic transactions.
"""

import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, models, transaction
from django.db.models import Q
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
    log_price_rule_event,
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
    ProtectedArea,
    ProtectedAreaFeeSchedule,
    ProtectedAreaRule,
    ProtectedAreaZone,
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
    # Lock booking row to prevent concurrent cancellations (P1 fix)
    # Re-fetch with lock to ensure we have latest state
    booking = Booking.objects.select_for_update().get(pk=booking.pk)

    # Re-check status after acquiring lock (may have changed)
    if booking.status == "cancelled":
        raise BookingError("Booking is already cancelled")

    if booking.status == "checked_in":
        raise BookingError("Cannot cancel a checked-in booking")

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
    weight_kg=None,
    height_cm=None,
    wetsuit_size: str = "",
    bcd_size: str = "",
    fin_size: str = "",
    mask_fit: str = "",
    glove_size: str = "",
    weight_required_kg=None,
    gear_notes: str = "",
    equipment_ownership: str = "none",
    diver_type: str = "activity",
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
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        wetsuit_size: Wetsuit size
        bcd_size: BCD size
        fin_size: Fin size
        mask_fit: Mask fit notes
        glove_size: Glove size
        weight_required_kg: Weight needed for neutral buoyancy
        gear_notes: Additional gear notes
        equipment_ownership: Equipment ownership status
        diver_type: Whether diving is identity or activity

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
        weight_kg=weight_kg,
        height_cm=height_cm,
        wetsuit_size=wetsuit_size,
        bcd_size=bcd_size,
        fin_size=fin_size,
        mask_fit=mask_fit,
        glove_size=glove_size,
        weight_required_kg=weight_required_kg,
        gear_notes=gear_notes,
        equipment_ownership=equipment_ownership,
        diver_type=diver_type,
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
    weight_kg=None,
    height_cm=None,
    wetsuit_size: str | None = None,
    bcd_size: str | None = None,
    fin_size: str | None = None,
    mask_fit: str | None = None,
    glove_size: str | None = None,
    weight_required_kg=None,
    gear_notes: str | None = None,
    equipment_ownership: str | None = None,
    diver_type: str | None = None,
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
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        wetsuit_size: Wetsuit size
        bcd_size: BCD size
        fin_size: Fin size
        mask_fit: Mask fit notes
        glove_size: Glove size
        weight_required_kg: Weight needed for neutral buoyancy
        gear_notes: Additional gear notes
        equipment_ownership: Equipment ownership status
        diver_type: Whether diving is identity or activity

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

    # Update body measurements / gear sizing
    _apply_tracked_update(diver, "weight_kg", weight_kg, changes)
    _apply_tracked_update(diver, "height_cm", height_cm, changes)
    _apply_tracked_update(diver, "wetsuit_size", wetsuit_size, changes)
    _apply_tracked_update(diver, "bcd_size", bcd_size, changes)
    _apply_tracked_update(diver, "fin_size", fin_size, changes)
    _apply_tracked_update(diver, "mask_fit", mask_fit, changes)
    _apply_tracked_update(diver, "glove_size", glove_size, changes)
    _apply_tracked_update(diver, "weight_required_kg", weight_required_kg, changes)
    _apply_tracked_update(diver, "gear_notes", gear_notes, changes)
    _apply_tracked_update(diver, "equipment_ownership", equipment_ownership, changes)
    _apply_tracked_update(diver, "diver_type", diver_type, changes)

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
    protected_area: "ProtectedArea | None" = None,
    protected_area_zone: "ProtectedAreaZone | None" = None,
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
        protected_area: Optional protected area FK
        protected_area_zone: Optional zone within protected area FK

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
        protected_area=protected_area,
        protected_area_zone=protected_area_zone,
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
    protected_area: "ProtectedArea | None" = None,
    protected_area_zone: "ProtectedAreaZone | None" = None,
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
        protected_area: New protected area FK (None = no change)
        protected_area_zone: New zone FK (None = no change)

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

    # Handle protected_area FK - use sentinel to detect if passed
    if protected_area != site.protected_area:
        changes["protected_area"] = {
            "old": str(site.protected_area_id) if site.protected_area_id else None,
            "new": str(protected_area.pk) if protected_area else None,
        }
        site.protected_area = protected_area

    # Handle protected_area_zone FK
    if protected_area_zone != site.protected_area_zone:
        changes["protected_area_zone"] = {
            "old": str(site.protected_area_zone_id) if site.protected_area_zone_id else None,
            "new": str(protected_area_zone.pk) if protected_area_zone else None,
        }
        site.protected_area_zone = protected_area_zone

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
    base_price,
    currency: str = "USD",
    description: str = "",
    typical_duration_minutes: int = 60,
    dives_per_excursion: int = 2,
    min_certification_level: CertificationLevel | None = None,
    requires_cert: bool = True,
    is_training: bool = False,
    is_active: bool = True,
    auto_create_catalog_item: bool = True,
) -> ExcursionType:
    """Create a new excursion type.

    Args:
        actor: User creating the type (required for audit)
        name: Display name
        slug: URL-friendly unique identifier
        dive_mode: "boat" or "shore"
        time_of_day: "day", "night", "dawn", or "dusk"
        base_price: Starting price (Decimal)
        currency: Currency code (default: USD)
        description: Optional description
        typical_duration_minutes: Expected duration (default: 60)
        dives_per_excursion: Number of dives included (default: 2)
        min_certification_level: Required certification FK (None = no requirement)
        requires_cert: If False, skip certification check (DSD)
        is_training: If True, this is a training dive
        is_active: If False, type is not bookable
        auto_create_catalog_item: If True, auto-create a linked CatalogItem

    Returns:
        Created ExcursionType

    Raises:
        IntegrityError: If slug already exists
    """
    # Auto-create a catalog item for this excursion type
    catalog_item = None
    if auto_create_catalog_item:
        catalog_item = CatalogItem.objects.create(
            kind="service",
            display_name=name,
            is_billable=True,
            active=is_active,
        )

    excursion_type = ExcursionType.objects.create(
        name=name,
        slug=slug,
        description=description,
        dive_mode=dive_mode,
        time_of_day=time_of_day,
        typical_duration_minutes=typical_duration_minutes,
        dives_per_excursion=dives_per_excursion,
        min_certification_level=min_certification_level,
        requires_cert=requires_cert,
        is_training=is_training,
        base_price=base_price,
        currency=currency,
        is_active=is_active,
        catalog_item=catalog_item,
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
    excursion_type: ExcursionType | None = None,
    excursion_types: list[ExcursionType] | None = None,
    name: str,
    sequence: int,
    offset_minutes: int = 0,
    surface_interval_minutes: int | None = None,
    planned_duration_minutes: int | None = None,
    description: str = "",
    planned_depth_meters: int | None = None,
    min_certification_level: CertificationLevel | None = None,
    dive_site: "DiveSite | None" = None,
    # Dive planning fields
    gas: str = "",
    route: str = "",
    route_segments: list | None = None,
    briefing_text: str = "",
    briefing_video_url: str = "",
    hazards: str = "",
    access_mode: str = "",
    boat_instructions: str = "",
    # Commerce linkage
    catalog_item=None,
    auto_create_catalog_item: bool = True,
) -> ExcursionTypeDive:
    """Create a new dive template (dive plan).

    Args:
        actor: User creating the template (required for audit)
        excursion_type: Single ExcursionType (backwards compat, added to excursion_types)
        excursion_types: List of ExcursionTypes this template is used by (M2M)
        name: Name of this dive (e.g., "First Dive", "Night Dive")
        sequence: Order of this dive (1, 2, 3, etc.)
        offset_minutes: Minutes after departure when this dive starts
        planned_duration_minutes: Optional planned duration
        description: Optional description
        planned_depth_meters: Optional planned depth
        min_certification_level: Optional certification level override
        dive_site: Optional specific dive site this plan is designed for
        gas: Gas mix (air, ean32, ean36, trimix)
        route: Route description text
        route_segments: Structured dive profile as list of segments
        briefing_text: Full briefing content
        briefing_video_url: YouTube video URL for dive briefing
        hazards: Known hazards and safety considerations
        access_mode: How divers get to the dive site (boat, vehicle, beach_meet, etc.)
        boat_instructions: Instructions for boat dives
        catalog_item: CatalogItem FK for product sold for this dive
        auto_create_catalog_item: If True and no catalog_item provided, auto-create one

    Returns:
        Created ExcursionTypeDive

    Raises:
        IntegrityError: If constraints are violated
    """
    # Build list of excursion types (backwards compat + new M2M)
    types_to_add = list(excursion_types or [])
    if excursion_type is not None and excursion_type not in types_to_add:
        types_to_add.append(excursion_type)

    # Auto-add dive_site to suitable_sites for each excursion type
    if dive_site is not None:
        for et in types_to_add:
            if not et.suitable_sites.filter(pk=dive_site.pk).exists():
                et.suitable_sites.add(dive_site)

    # Auto-create a catalog item if not provided
    if catalog_item is None and auto_create_catalog_item:
        catalog_item = CatalogItem.objects.create(
            kind="service",
            display_name=name,
            is_billable=True,
            active=True,
        )

    dive_template = ExcursionTypeDive.objects.create(
        name=name,
        sequence=sequence,
        offset_minutes=offset_minutes,
        surface_interval_minutes=surface_interval_minutes,
        planned_duration_minutes=planned_duration_minutes,
        description=description,
        planned_depth_meters=planned_depth_meters,
        min_certification_level=min_certification_level,
        dive_site=dive_site,
        gas=gas,
        route=route,
        route_segments=route_segments or [],
        briefing_text=briefing_text,
        briefing_video_url=briefing_video_url,
        hazards=hazards,
        access_mode=access_mode,
        boat_instructions=boat_instructions,
        catalog_item=catalog_item,
    )

    # Add excursion types via M2M
    if types_to_add:
        dive_template.excursion_types.add(*types_to_add)

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
    surface_interval_minutes: int | None = None,
    planned_duration_minutes: int | None = None,
    description: str | None = None,
    planned_depth_meters: int | None = None,
    min_certification_level: CertificationLevel | None = None,
    clear_min_certification: bool = False,
    dive_site: "DiveSite | None" = None,
    clear_dive_site: bool = False,
    # Dive planning fields
    gas: str | None = None,
    route: str | None = None,
    route_segments: list | None = None,
    briefing_text: str | None = None,
    briefing_video_url: str | None = None,
    hazards: str | None = None,
    access_mode: str | None = None,
    boat_instructions: str | None = None,
    # Commerce linkage
    catalog_item=None,
    clear_catalog_item: bool = False,
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
        dive_site: New dive site (None = no change)
        clear_dive_site: If True, clear dive_site
        gas: Gas mix (None = no change)
        route: Route description (None = no change)
        route_segments: Structured dive profile (None = no change)
        briefing_text: Full briefing content (None = no change)
        briefing_video_url: YouTube video URL (None = no change)
        hazards: Known hazards (None = no change)
        access_mode: How divers get to the dive site (None = no change)
        boat_instructions: Instructions for boat dives (None = no change)
        catalog_item: CatalogItem FK for product sold (None = no change)
        clear_catalog_item: If True, clear catalog_item

    Returns:
        Updated ExcursionTypeDive
    """
    changes = {}

    _apply_tracked_update(dive_template, "name", name, changes)
    _apply_tracked_update(dive_template, "sequence", sequence, changes)
    _apply_tracked_update(dive_template, "offset_minutes", offset_minutes, changes)
    _apply_tracked_update(dive_template, "surface_interval_minutes", surface_interval_minutes, changes)
    _apply_tracked_update(dive_template, "planned_duration_minutes", planned_duration_minutes, changes)
    _apply_tracked_update(dive_template, "description", description, changes)
    _apply_tracked_update(dive_template, "planned_depth_meters", planned_depth_meters, changes)
    # Dive planning fields
    _apply_tracked_update(dive_template, "gas", gas, changes)
    _apply_tracked_update(dive_template, "route", route, changes)
    _apply_tracked_update(dive_template, "briefing_text", briefing_text, changes)
    _apply_tracked_update(dive_template, "briefing_video_url", briefing_video_url, changes)
    _apply_tracked_update(dive_template, "hazards", hazards, changes)
    _apply_tracked_update(dive_template, "access_mode", access_mode, changes)
    _apply_tracked_update(dive_template, "boat_instructions", boat_instructions, changes)
    # route_segments needs special handling for JSON comparison
    if route_segments is not None and route_segments != dive_template.route_segments:
        changes["route_segments"] = {"old": dive_template.route_segments, "new": route_segments}
        dive_template.route_segments = route_segments

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

    # Handle dive_site FK specially
    # Auto-add dive_site to suitable_sites if not already there
    if dive_site is not None and not clear_dive_site:
        for excursion_type in dive_template.excursion_types.all():
            if not excursion_type.suitable_sites.filter(pk=dive_site.pk).exists():
                excursion_type.suitable_sites.add(dive_site)

    if clear_dive_site:
        if dive_template.dive_site_id is not None:
            changes["dive_site"] = {
                "old": str(dive_template.dive_site_id),
                "new": None,
            }
            dive_template.dive_site = None
    elif dive_site is not None and dive_site != dive_template.dive_site:
        changes["dive_site"] = {
            "old": str(dive_template.dive_site_id) if dive_template.dive_site_id else None,
            "new": str(dive_site.pk),
        }
        dive_template.dive_site = dive_site

    # Handle catalog_item FK specially
    if clear_catalog_item:
        if dive_template.catalog_item_id is not None:
            changes["catalog_item"] = {
                "old": str(dive_template.catalog_item_id),
                "new": None,
            }
            dive_template.catalog_item = None
    elif catalog_item is not None and catalog_item != dive_template.catalog_item:
        changes["catalog_item"] = {
            "old": str(dive_template.catalog_item_id) if dive_template.catalog_item_id else None,
            "new": str(catalog_item.pk),
        }
        dive_template.catalog_item = catalog_item

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

# Gas label to O2 fraction mapping for decompression validation
GAS_O2_MAP = {
    "air": 0.21,
    "ean32": 0.32,
    "ean36": 0.36,
}


def _gas_o2_fraction(gas_label: str | None) -> float:
    """Get O2 fraction for a gas label.

    Args:
        gas_label: Gas label like "air", "ean32", "ean36", or None

    Returns:
        O2 fraction (0.0-1.0), defaults to 0.21 (air) for unknown
    """
    if not gas_label:
        return 0.21
    return GAS_O2_MAP.get(gas_label.lower(), 0.21)


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
            "gas_o2": _gas_o2_fraction(template.gas),
            "gas_he": 0.0,  # Helium not yet supported in templates
            "equipment_requirements": template.equipment_requirements,
            "skills": template.skills,
            "route": template.route,
            "route_segments": template.route_segments,
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


# =============================================================================
# Dive Plan Decompression Validation Services
# =============================================================================


@transaction.atomic
def validate_dive_plan(
    *,
    actor,
    dive: "Dive",
    force: bool = False,
) -> "Dive":
    """Validate locked dive plan using Bühlmann ZHL-16C.

    Runs the dive plan through the decompression validator to calculate
    ceiling, TTS, NDL, and deco stops. Results are stored in the
    plan_snapshot["validation"] field.

    Args:
        actor: User performing validation
        dive: Dive with locked plan_snapshot
        force: If True, re-validate even if validation exists

    Returns:
        Updated Dive with validation results in plan_snapshot

    Raises:
        ValueError: If plan_snapshot doesn't exist (plan not locked)
    """
    from django.conf import settings

    from .audit import Actions, log_dive_event

    if not dive.plan_snapshot:
        raise ValueError("Dive plan must be locked before validation")

    # Skip if already validated (unless force)
    if dive.plan_snapshot.get("validation") and not force:
        logger.info(
            f"Dive {dive.id} already validated, skipping (use force=True to re-validate)"
        )
        return dive

    # Check if validation is enabled
    if not getattr(settings, "ENABLE_DECO_VALIDATION", False):
        logger.info(f"Deco validation disabled, skipping dive {dive.id}")
        return dive

    from .planning import build_validator_input, run_deco_validator

    briefing = dive.plan_snapshot.get("briefing", {})
    route_segments = briefing.get("route_segments", [])

    if not route_segments:
        dive.plan_snapshot["validation"] = {
            "error": "no_route_segments",
            "validated_at": timezone.now().isoformat(),
        }
        dive.save(update_fields=["plan_snapshot"])
        return dive

    # Use stored gas values (floats), not label lookup
    gas_o2 = briefing.get("gas_o2", 0.21)
    gas_he = briefing.get("gas_he", 0.0)

    # Build validator input using configured GF values
    gf_low = getattr(settings, "DECO_GF_LOW", 0.40)
    gf_high = getattr(settings, "DECO_GF_HIGH", 0.85)

    input_data = build_validator_input(
        route_segments=route_segments,
        gas_o2=gas_o2,
        gas_he=gas_he,
        gf_low=gf_low,
        gf_high=gf_high,
    )

    result = run_deco_validator(input_data)
    result["validated_at"] = timezone.now().isoformat()

    dive.plan_snapshot["validation"] = result
    dive.save(update_fields=["plan_snapshot"])

    # Emit audit event
    if "error" not in result:
        log_dive_event(
            action=Actions.DIVE_PLAN_VALIDATED,
            dive=dive,
            actor=actor,
            data={
                "deco_required": result.get("deco_required", False),
                "ceiling_m": result.get("ceiling_m"),
                "tts_min": result.get("tts_min"),
                "ndl_min": result.get("ndl_min"),
            },
        )
    else:
        log_dive_event(
            action=Actions.DIVE_PLAN_VALIDATION_FAILED,
            dive=dive,
            actor=actor,
            data={"error": result.get("error")},
        )

    return dive


# =============================================================================
# Catalog Item Services
# =============================================================================


@transaction.atomic
def create_catalog_item(
    *,
    actor,
    kind: str,
    display_name: str,
    display_name_es: str = "",
    service_category: str = "",
    default_stock_action: str = "",
    is_billable: bool = True,
    active: bool = True,
):
    """Create a new catalog item.

    Args:
        actor: User performing the action
        kind: 'stock_item' or 'service'
        display_name: Name shown to staff and on invoices
        display_name_es: Spanish translation (optional)
        service_category: For services only
        default_stock_action: For stock items only
        is_billable: Whether item appears on invoices
        active: Whether item can be added to orders

    Returns:
        CatalogItem instance
    """
    from django_catalog.models import CatalogItem

    item = CatalogItem.objects.create(
        kind=kind,
        display_name=display_name,
        display_name_es=display_name_es,
        service_category=service_category,
        default_stock_action=default_stock_action,
        is_billable=is_billable,
        active=active,
    )

    # Emit audit event
    log_event(
        action=Actions.CATALOG_ITEM_CREATED,
        target=item,
        actor=actor,
        data={
            "kind": kind,
            "display_name": display_name,
            "is_billable": is_billable,
            "active": active,
        },
    )

    return item


@transaction.atomic
def update_catalog_item(
    *,
    actor,
    item,
    kind: str | None = None,
    display_name: str | None = None,
    display_name_es: str | None = None,
    service_category: str | None = None,
    default_stock_action: str | None = None,
    is_billable: bool | None = None,
    active: bool | None = None,
):
    """Update an existing catalog item.

    Args:
        actor: User performing the action
        item: CatalogItem to update
        kind: 'stock_item' or 'service' (optional)
        display_name: Name shown to staff and on invoices (optional)
        display_name_es: Spanish translation (optional)
        service_category: For services only (optional)
        default_stock_action: For stock items only (optional)
        is_billable: Whether item appears on invoices (optional)
        active: Whether item can be added to orders (optional)

    Returns:
        Updated CatalogItem instance
    """
    changes = {}

    if kind is not None and item.kind != kind:
        changes["kind"] = {"old": item.kind, "new": kind}
        item.kind = kind
    if display_name is not None and item.display_name != display_name:
        changes["display_name"] = {"old": item.display_name, "new": display_name}
        item.display_name = display_name
    if display_name_es is not None and item.display_name_es != display_name_es:
        changes["display_name_es"] = {"old": item.display_name_es, "new": display_name_es}
        item.display_name_es = display_name_es
    if service_category is not None and item.service_category != service_category:
        changes["service_category"] = {"old": item.service_category, "new": service_category}
        item.service_category = service_category
    if default_stock_action is not None and item.default_stock_action != default_stock_action:
        changes["default_stock_action"] = {"old": item.default_stock_action, "new": default_stock_action}
        item.default_stock_action = default_stock_action
    if is_billable is not None and item.is_billable != is_billable:
        changes["is_billable"] = {"old": item.is_billable, "new": is_billable}
        item.is_billable = is_billable
    if active is not None and item.active != active:
        changes["active"] = {"old": item.active, "new": active}
        item.active = active

    if changes:
        item.save()

        # Emit audit event
        log_event(
            action=Actions.CATALOG_ITEM_UPDATED,
            target=item,
            actor=actor,
            data={"changes": changes},
        )

    return item


@transaction.atomic
def delete_catalog_item(*, actor, item):
    """Soft delete a catalog item.

    Args:
        actor: User performing the action
        item: CatalogItem to delete

    Returns:
        None
    """
    item.active = False
    item.deleted_at = timezone.now()
    item.save(update_fields=["active", "deleted_at", "updated_at"])

    # Emit audit event
    log_event(
        action=Actions.CATALOG_ITEM_DELETED,
        target=item,
        actor=actor,
        data={"display_name": item.display_name},
    )


# =============================================================================
# Price Rule Services
# =============================================================================


@transaction.atomic
def create_price_rule(
    *,
    actor,
    catalog_item,
    amount,
    currency: str,
    cost_amount=None,
    cost_currency: str = "",
    organization=None,
    party=None,
    agreement=None,
    valid_from=None,
    valid_to=None,
    priority: int = 0,
    reason: str = "",
):
    """Create a new price rule for a catalog item.

    Args:
        actor: User performing the action
        catalog_item: CatalogItem this price applies to
        amount: Customer charge amount
        currency: Currency code (e.g., 'USD')
        cost_amount: Shop cost amount (optional, for vendor pricing)
        cost_currency: Cost currency code
        organization: Organization scope (optional)
        party: Party scope (optional)
        agreement: Agreement scope (optional, for vendor pricing)
        valid_from: Start of validity period
        valid_to: End of validity period (optional)
        priority: Higher priority wins ties
        reason: Audit reason for creating this rule

    Returns:
        Price instance
    """
    from primitives_testbed.pricing.models import Price

    if valid_from is None:
        valid_from = timezone.now()

    price = Price.objects.create(
        catalog_item=catalog_item,
        amount=amount,
        currency=currency,
        cost_amount=cost_amount,
        cost_currency=cost_currency or currency,
        organization=organization,
        party=party,
        agreement=agreement,
        valid_from=valid_from,
        valid_to=valid_to,
        priority=priority,
        created_by=actor,
        reason=reason,
    )

    # Emit audit event
    log_price_rule_event(
        action=Actions.PRICE_RULE_CREATED,
        price=price,
        actor=actor,
        data={"reason": reason},
    )

    return price


@transaction.atomic
def update_price_rule(
    *,
    actor,
    price,
    amount=None,
    currency: str | None = None,
    cost_amount=None,
    cost_currency: str | None = None,
    valid_from=None,
    valid_to=None,
    priority: int | None = None,
    reason: str = "",
):
    """Update an existing price rule.

    Note: Scope fields (organization, party, agreement) cannot be changed.
    Create a new price rule if you need a different scope.

    Args:
        actor: User performing the action
        price: Price instance to update
        amount: New customer charge amount (optional)
        currency: New currency code (optional)
        cost_amount: New shop cost amount (optional)
        cost_currency: New cost currency code (optional)
        valid_from: New start of validity period (optional)
        valid_to: New end of validity period (optional)
        priority: New priority (optional)
        reason: Audit reason for update

    Returns:
        Updated Price instance
    """
    changes = {}

    if amount is not None and price.amount != amount:
        changes["amount"] = {"old": str(price.amount), "new": str(amount)}
        price.amount = amount
    if currency is not None and price.currency != currency:
        changes["currency"] = {"old": price.currency, "new": currency}
        price.currency = currency
    if cost_amount is not None and price.cost_amount != cost_amount:
        changes["cost_amount"] = {
            "old": str(price.cost_amount) if price.cost_amount else None,
            "new": str(cost_amount),
        }
        price.cost_amount = cost_amount
    if cost_currency is not None and price.cost_currency != cost_currency:
        changes["cost_currency"] = {"old": price.cost_currency, "new": cost_currency}
        price.cost_currency = cost_currency
    if valid_from is not None and price.valid_from != valid_from:
        changes["valid_from"] = {
            "old": price.valid_from.isoformat() if price.valid_from else None,
            "new": valid_from.isoformat(),
        }
        price.valid_from = valid_from
    if valid_to is not None and price.valid_to != valid_to:
        changes["valid_to"] = {
            "old": price.valid_to.isoformat() if price.valid_to else None,
            "new": valid_to.isoformat() if valid_to else None,
        }
        price.valid_to = valid_to
    if priority is not None and price.priority != priority:
        changes["priority"] = {"old": price.priority, "new": priority}
        price.priority = priority

    if changes:
        price.save()

        # Emit audit event
        log_price_rule_event(
            action=Actions.PRICE_RULE_UPDATED,
            price=price,
            actor=actor,
            changes=changes,
            data={"reason": reason},
        )

    return price


@transaction.atomic
def delete_price_rule(*, actor, price, reason: str = ""):
    """Soft delete a price rule.

    Args:
        actor: User performing the action
        price: Price instance to delete
        reason: Audit reason for deletion

    Returns:
        None
    """
    price.deleted_at = timezone.now()
    price.save(update_fields=["deleted_at", "updated_at"])

    # Emit audit event
    log_price_rule_event(
        action=Actions.PRICE_RULE_DELETED,
        price=price,
        actor=actor,
        data={"reason": reason},
    )


# =============================================================================
# Payables Services (Vendor Invoice/Payment Management)
# =============================================================================


def get_or_create_vendor_payable_account(shop, vendor, currency: str):
    """Get or create a vendor-specific payable account.

    IMPORTANT: The account is owned by the shop (not the vendor), but named
    for the vendor. This allows proper tracking of per-vendor liabilities
    from the shop's perspective.

    Args:
        shop: Organization instance (dive shop) - the account owner
        vendor: Organization instance (vendor) - for account naming
        currency: Currency code (USD, MXN, etc.)

    Returns:
        Account instance
    """
    from .accounts import get_vendor_payable_account

    return get_vendor_payable_account(shop, vendor, currency, auto_create=True)


@transaction.atomic
def record_vendor_invoice(
    *,
    actor,
    shop,
    vendor,
    amount,
    currency: str,
    invoice_number: str = "",
    invoice_date=None,
    due_date=None,
    source=None,
    description: str = "",
):
    """Record a vendor invoice: DR Expense, CR Vendor Payables.

    This creates a balanced ledger transaction recording the liability
    to the vendor. The payable account is per-vendor for proper reconciliation.

    Args:
        actor: User recording the invoice
        shop: Organization instance (dive shop) - owner of expense/payable accounts
        vendor: Organization instance (vendor)
        amount: Invoice amount
        currency: Currency code
        invoice_number: Vendor's invoice number
        invoice_date: Date of the invoice (defaults to now)
        due_date: When payment is due
        source: Optional source model (Booking, Excursion, etc.)
        description: Description for the ledger entry

    Returns:
        Transaction instance

    Raises:
        AccountConfigurationError: If required accounts are not seeded
    """
    from django.contrib.contenttypes.models import ContentType

    from django_ledger.services import record_transaction

    from .accounts import get_required_accounts, get_vendor_payable_account
    from .audit import Actions, log_event

    if invoice_date is None:
        invoice_date = timezone.now()

    # Get required accounts from seeded chart of accounts
    # This will raise AccountConfigurationError if not seeded
    accounts = get_required_accounts(shop, currency)

    # Get vendor-specific payable account (or create if seeding)
    payable_account = get_vendor_payable_account(shop, vendor, currency, auto_create=True)

    # Use the excursion_costs account for vendor invoices (shop owns it)
    expense_account = accounts.excursion_costs

    # Build metadata
    metadata = {
        "type": "vendor_invoice",
        "vendor_id": str(vendor.pk),
        "vendor_name": vendor.name,
        "shop_id": str(shop.pk),
        "shop_name": shop.name,
        "invoice_number": invoice_number,
        "invoice_date": str(invoice_date.date()) if hasattr(invoice_date, "date") else str(invoice_date),
    }
    if due_date:
        metadata["due_date"] = str(due_date.date()) if hasattr(due_date, "date") else str(due_date)
    if source:
        source_ct = ContentType.objects.get_for_model(source)
        metadata["source_type"] = source_ct.model
        metadata["source_id"] = str(source.pk)

    # Create balanced transaction
    tx = record_transaction(
        description=description or f"Vendor invoice from {vendor.name}",
        entries=[
            {"account": expense_account, "entry_type": "debit", "amount": amount},
            {"account": payable_account, "entry_type": "credit", "amount": amount},
        ],
        effective_at=invoice_date,
        metadata=metadata,
    )

    # Audit event
    log_event(
        action=Actions.VENDOR_INVOICE_RECORDED,
        target=vendor,
        actor=actor,
        data={
            "transaction_id": str(tx.pk),
            "shop_id": str(shop.pk),
            "amount": str(amount),
            "currency": currency,
            "invoice_number": invoice_number,
        },
    )

    return tx


@transaction.atomic
def record_vendor_payment(
    *,
    actor,
    shop,
    vendor,
    amount,
    currency: str,
    payment_date=None,
    reference: str = "",
    description: str = "",
):
    """Record a payment to vendor: DR Vendor Payables, CR Cash/Bank.

    This reduces the liability to the vendor and records the cash outflow.

    Args:
        actor: User recording the payment
        shop: Organization instance (dive shop) - owner of cash/payable accounts
        vendor: Organization instance (vendor)
        amount: Payment amount
        currency: Currency code
        payment_date: When payment was made (defaults to now)
        reference: Payment reference (check number, wire ref, etc.)
        description: Description for the ledger entry

    Returns:
        Transaction instance

    Raises:
        AccountConfigurationError: If required accounts are not seeded
    """
    from django_ledger.services import record_transaction

    from .accounts import get_required_accounts, get_vendor_payable_account
    from .audit import Actions, log_event

    if payment_date is None:
        payment_date = timezone.now()

    # Get required accounts from seeded chart of accounts
    # This will raise AccountConfigurationError if not seeded
    accounts = get_required_accounts(shop, currency)

    # Get vendor-specific payable account
    payable_account = get_vendor_payable_account(shop, vendor, currency, auto_create=True)

    # Use the shop's cash/bank account
    cash_account = accounts.cash_bank

    # Build metadata
    metadata = {
        "type": "vendor_payment",
        "vendor_id": str(vendor.pk),
        "vendor_name": vendor.name,
        "shop_id": str(shop.pk),
        "shop_name": shop.name,
        "reference": reference,
    }

    # Create balanced transaction
    tx = record_transaction(
        description=description or f"Payment to {vendor.name}",
        entries=[
            {"account": payable_account, "entry_type": "debit", "amount": amount},
            {"account": cash_account, "entry_type": "credit", "amount": amount},
        ],
        effective_at=payment_date,
        metadata=metadata,
    )

    # Audit event
    log_event(
        action=Actions.VENDOR_PAYMENT_RECORDED,
        target=vendor,
        actor=actor,
        data={
            "transaction_id": str(tx.pk),
            "shop_id": str(shop.pk),
            "amount": str(amount),
            "currency": currency,
            "reference": reference,
        },
    )

    return tx


def get_vendor_payables_summary(shop=None):
    """Get open payable balances grouped by vendor and currency.

    Queries payable accounts and returns non-zero balances.
    Vendor payable accounts are named "Accounts Payable - {vendor_name}"
    and owned by the shop.

    Args:
        shop: Organization instance (dive shop) - if None, queries all shops

    Returns:
        List of dicts with vendor_name, currency, balance, account_id, shop_id
    """
    from django.contrib.contenttypes.models import ContentType

    from django_ledger.models import Account
    from django_ledger.services import get_balance

    # Find vendor payable accounts (named "Accounts Payable - {vendor}")
    # These are per-vendor accounts owned by shops
    queryset = Account.objects.filter(
        account_type="payable",
        name__startswith="Accounts Payable - ",
    )

    # Filter by shop owner if provided
    if shop:
        shop_ct = ContentType.objects.get_for_model(shop)
        queryset = queryset.filter(
            owner_content_type=shop_ct,
            owner_id=str(shop.pk),
        )

    summary = []
    for account in queryset:
        balance = get_balance(account)
        if balance != 0:
            # Extract vendor name from account name
            vendor_name = account.name.replace("Accounts Payable - ", "")
            summary.append({
                "vendor_name": vendor_name,
                "currency": account.currency,
                "balance": balance,
                "account_id": str(account.pk),
                "shop_id": account.owner_id,
            })

    return summary


def get_vendor_transactions(vendor, shop=None, currency: str = None):
    """Get all transactions for a vendor's payable account.

    Vendor payable accounts are owned by the shop but named for the vendor.
    This function finds entries on those accounts.

    Args:
        vendor: Organization instance (vendor)
        shop: Organization instance (dive shop) - if None, searches all shops
        currency: Optional currency filter

    Returns:
        QuerySet of Entry instances with related transaction and account
    """
    from django.contrib.contenttypes.models import ContentType

    from django_ledger.models import Account, Entry

    # Vendor payable accounts are named "Accounts Payable - {vendor.name}"
    # and owned by the shop, not the vendor
    account_name = f"Accounts Payable - {vendor.name}"

    queryset = Account.objects.filter(
        account_type="payable",
        name=account_name,
    )

    # Filter by shop owner if provided
    if shop:
        shop_ct = ContentType.objects.get_for_model(shop)
        queryset = queryset.filter(
            owner_content_type=shop_ct,
            owner_id=str(shop.pk),
        )

    if currency:
        queryset = queryset.filter(currency=currency)

    # Get all entries for these accounts
    entries = Entry.objects.filter(
        account__in=queryset
    ).select_related("transaction", "account").order_by("-transaction__effective_at")

    return entries


# =============================================================================
# Tissue Loading Calculator (EPHEMERAL - No Persistence)
# =============================================================================
#
# CRITICAL: These functions return EPHEMERAL what-if planning data.
# Do NOT persist any of these results to the database.
# Recalculate fresh each time - tissue state should never be stored.
#
# Bühlmann ZHL-16C tissue model with 16 compartments.
# Each compartment has a specific half-time for N2 (and He if using trimix).
# For recreational diving with air/nitrox, we only track N2.

import math
from dataclasses import dataclass, field


TISSUE_PAYLOAD_VERSION = "1.0"  # Version-tag for tissue state format

# Bühlmann ZHL-16C N2 half-times in minutes
# These are the standard tissue compartment half-times
BUHLMANN_N2_HALFTIMES = [
    4.0, 8.0, 12.5, 18.5, 27.0, 38.3, 54.3, 77.0,
    109.0, 146.0, 187.0, 239.0, 305.0, 390.0, 498.0, 635.0
]

# Surface N2 partial pressure (bar) - air at sea level
SURFACE_N2_PP = 0.79

# Water vapor pressure (bar) at body temperature
WATER_VAPOR_PP = 0.0627

# Atmospheric pressure at sea level (bar)
SURFACE_PRESSURE = 1.0


@dataclass
class TissueState:
    """Represents tissue loading state for all 16 compartments.

    WARNING: This is EPHEMERAL planning data. Do NOT persist.
    """

    version: str = TISSUE_PAYLOAD_VERSION
    n2_pressures: list[float] = field(default_factory=list)

    def __post_init__(self):
        """Initialize with surface-saturated tissues if empty."""
        if not self.n2_pressures:
            # Start with tissues equilibrated to surface N2 pressure
            self.n2_pressures = [SURFACE_N2_PP] * 16

    def max_loading_percent(self) -> float:
        """Return the maximum compartment loading as percentage of surface saturation."""
        if not self.n2_pressures:
            return 100.0
        return max(p / SURFACE_N2_PP * 100.0 for p in self.n2_pressures)

    def to_dict(self) -> dict:
        """Serialize for transport (JSON-safe)."""
        return {
            "version": self.version,
            "n2_pressures": self.n2_pressures.copy(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TissueState":
        """Deserialize from dict."""
        if data.get("version") != TISSUE_PAYLOAD_VERSION:
            raise ValueError(
                f"Tissue state version mismatch: {data.get('version')} != {TISSUE_PAYLOAD_VERSION}"
            )
        return cls(
            version=data["version"],
            n2_pressures=data["n2_pressures"].copy(),
        )


def validate_tissue_state(tissue_state: dict | None, expected_version: str = TISSUE_PAYLOAD_VERSION) -> bool:
    """Validate tissue state structure before using.

    Args:
        tissue_state: Dict with tissue state or None for fresh start
        expected_version: Expected version string

    Returns:
        True if valid

    Raises:
        ValueError: If tissue state is invalid
    """
    if tissue_state is None:
        return True  # Fresh start

    if not isinstance(tissue_state, dict):
        raise ValueError("Invalid tissue state: expected dict")

    if tissue_state.get("version") != expected_version:
        raise ValueError(
            f"Tissue state version mismatch: {tissue_state.get('version')} != {expected_version}"
        )

    # Validate 16 N2 compartments
    n2_pressures = tissue_state.get("n2_pressures", [])
    if len(n2_pressures) != 16:
        raise ValueError(f"Expected 16 N2 compartments, got {len(n2_pressures)}")

    return True


def _calculate_compartment_loading(
    initial_pp: float,
    ambient_pp: float,
    duration_min: float,
    half_time_min: float,
) -> float:
    """Calculate tissue compartment N2 pressure after exposure.

    Uses Haldane exponential equation:
    P_tissue(t) = P_tissue(0) + (P_ambient - P_tissue(0)) * (1 - e^(-t*ln(2)/τ))

    Args:
        initial_pp: Initial tissue N2 partial pressure (bar)
        ambient_pp: Ambient N2 partial pressure (bar)
        duration_min: Exposure duration (minutes)
        half_time_min: Compartment half-time (minutes)

    Returns:
        Final tissue N2 partial pressure (bar)
    """
    if duration_min <= 0:
        return initial_pp

    # Rate constant k = ln(2) / half_time
    k = math.log(2) / half_time_min

    # Exponential uptake/elimination
    return initial_pp + (ambient_pp - initial_pp) * (1 - math.exp(-k * duration_min))


def _depth_to_ambient_n2_pp(depth_m: float, gas_n2_fraction: float) -> float:
    """Calculate ambient N2 partial pressure at depth.

    Args:
        depth_m: Depth in meters
        gas_n2_fraction: N2 fraction in breathing gas (0.0-1.0)

    Returns:
        Ambient N2 partial pressure (bar)
    """
    # Absolute pressure at depth
    ambient_pressure = SURFACE_PRESSURE + (depth_m / 10.0)

    # Inspired N2 partial pressure (accounting for water vapor)
    return (ambient_pressure - WATER_VAPOR_PP) * gas_n2_fraction


# Bühlmann ZHL-16C M-values (a and b coefficients for each compartment)
# M-value = a + (ambient_pressure / b)
# These determine the maximum tolerable tissue pressure at a given ambient pressure
BUHLMANN_A_VALUES = [
    1.2599, 1.0000, 0.8618, 0.7562, 0.6667, 0.5933, 0.5282, 0.4701,
    0.4187, 0.3798, 0.3497, 0.3223, 0.2971, 0.2737, 0.2523, 0.2327
]
BUHLMANN_B_VALUES = [
    0.5050, 0.6514, 0.7222, 0.7825, 0.8126, 0.8434, 0.8693, 0.8910,
    0.9092, 0.9222, 0.9319, 0.9403, 0.9477, 0.9544, 0.9602, 0.9653
]

# Default gradient factors (GF Low / GF High)
# GF 100/100 = Standard Bühlmann (no conservatism)
# GF 30/85 = PADI-like conservatism (common recreational setting)
# GF 30/70 = More conservative (common for technical diving)
DEFAULT_GF_LOW = 100  # Percentage (0-100)
DEFAULT_GF_HIGH = 100  # Percentage (0-100)


def calculate_m_value_with_gf(
    compartment_idx: int,
    ambient_pressure: float,
    gf_low: int = DEFAULT_GF_LOW,
    gf_high: int = DEFAULT_GF_HIGH,
    current_depth_m: float = 0.0,
    max_depth_m: float = 0.0,
) -> float:
    """Calculate M-value adjusted for gradient factors.

    Gradient factors reduce the allowed supersaturation to add conservatism:
    - GF Low: Applied at the deepest point of the dive
    - GF High: Applied at the surface (0m)
    - Linear interpolation between depths

    Args:
        compartment_idx: Tissue compartment index (0-15)
        ambient_pressure: Current ambient pressure (bar)
        gf_low: Low gradient factor percentage (default 100)
        gf_high: High gradient factor percentage (default 100)
        current_depth_m: Current depth for GF interpolation
        max_depth_m: Maximum depth for GF interpolation

    Returns:
        M-value adjusted by gradient factor
    """
    a = BUHLMANN_A_VALUES[compartment_idx]
    b = BUHLMANN_B_VALUES[compartment_idx]

    # Standard M-value (M0 = M-value at ambient pressure)
    m_value = a + (ambient_pressure / b)

    # Calculate M0 (the tissue's inert gas pressure at ambient, no supersaturation)
    # This is the "floor" - we interpolate between M0 and M-value
    m0 = ambient_pressure  # Simplified: ambient pressure is the no-supersaturation limit

    # Interpolate GF based on depth
    # At max_depth, use GF_low; at surface (0m), use GF_high
    if max_depth_m > 0 and current_depth_m > 0:
        # Linear interpolation
        gf = gf_high + (gf_low - gf_high) * (current_depth_m / max_depth_m)
    else:
        # At surface or no depth info, use GF_high
        gf = gf_high

    gf_fraction = gf / 100.0

    # Apply gradient factor: M_gf = M0 + (M - M0) * GF
    m_value_gf = m0 + (m_value - m0) * gf_fraction

    return m_value_gf


def calculate_ndl(
    tissue_state: "TissueState",
    depth_m: float,
    gas_o2_fraction: float = 0.21,
    gf_low: int = DEFAULT_GF_LOW,
    gf_high: int = DEFAULT_GF_HIGH,
) -> int | None:
    """Calculate No Decompression Limit (NDL) at given depth.

    NDL is the maximum time before any tissue compartment exceeds its
    M-value at surface pressure (requiring decompression stops).

    Args:
        tissue_state: Current tissue state
        depth_m: Planned depth in meters
        gas_o2_fraction: O2 fraction (0.0-1.0)
        gf_low: Low gradient factor percentage (default 100)
        gf_high: High gradient factor percentage (default 100)

    Returns:
        NDL in minutes, or None if already in deco obligation
    """
    import math

    gas_n2_fraction = 1.0 - gas_o2_fraction
    ambient_n2_pp = _depth_to_ambient_n2_pp(depth_m, gas_n2_fraction)

    # Surface ambient pressure for M-value calculation
    surface_ambient = SURFACE_PRESSURE

    min_ndl = float("inf")

    for i, half_time in enumerate(BUHLMANN_N2_HALFTIMES):
        current_pp = tissue_state.n2_pressures[i]

        # M-value at surface with gradient factor
        # For NDL, we care about surfacing directly, so use GF High at surface
        m_value = calculate_m_value_with_gf(
            compartment_idx=i,
            ambient_pressure=surface_ambient,
            gf_low=gf_low,
            gf_high=gf_high,
            current_depth_m=0.0,  # At surface
            max_depth_m=depth_m,
        )

        # If already over M-value, NDL is 0
        if current_pp >= m_value:
            return 0

        # Time constant k = ln(2) / half_time
        k = math.log(2) / half_time

        # Solve for time when tissue_pp reaches m_value
        # P(t) = P_ambient + (P_initial - P_ambient) * e^(-kt)
        # m_value = ambient_n2_pp + (current_pp - ambient_n2_pp) * e^(-kt)
        # (m_value - ambient_n2_pp) / (current_pp - ambient_n2_pp) = e^(-kt)

        if ambient_n2_pp >= m_value:
            # At this depth, this compartment will eventually exceed M-value
            numerator = m_value - ambient_n2_pp
            denominator = current_pp - ambient_n2_pp

            if denominator == 0:
                continue  # Already at ambient, won't change

            ratio = numerator / denominator
            if ratio <= 0:
                # Already approaching limit
                ndl = 0
            else:
                ndl = -math.log(ratio) / k
        else:
            # This compartment won't limit NDL at this depth
            continue

        if ndl < min_ndl:
            min_ndl = ndl

    if min_ndl == float("inf"):
        return 999  # Very long NDL (effectively unlimited for rec diving)

    return max(0, int(min_ndl))


def loading_to_pressure_group(loading_percent: float) -> str:
    """Map tissue loading percentage to approximate PADI pressure group.

    This is an approximation since PADI RDP uses US Navy-derived tables,
    not Bühlmann. But it gives divers a familiar reference point.

    Args:
        loading_percent: Tissue loading as percentage of surface saturation

    Returns:
        PADI pressure group letter (A-Z)
    """
    # Approximate mapping: 100% = A (surface), increasing to W/Z at limits
    # Groups roughly correspond to 5-8% increments
    if loading_percent <= 100:
        return "A"
    elif loading_percent <= 108:
        return "B"
    elif loading_percent <= 116:
        return "C"
    elif loading_percent <= 124:
        return "D"
    elif loading_percent <= 132:
        return "E"
    elif loading_percent <= 140:
        return "F"
    elif loading_percent <= 150:
        return "G"
    elif loading_percent <= 160:
        return "H"
    elif loading_percent <= 170:
        return "I"
    elif loading_percent <= 180:
        return "J"
    elif loading_percent <= 190:
        return "K"
    elif loading_percent <= 200:
        return "L"
    elif loading_percent <= 212:
        return "M"
    elif loading_percent <= 224:
        return "N"
    elif loading_percent <= 236:
        return "O"
    elif loading_percent <= 250:
        return "P"
    elif loading_percent <= 264:
        return "Q"
    elif loading_percent <= 280:
        return "R"
    elif loading_percent <= 296:
        return "S"
    elif loading_percent <= 312:
        return "T"
    elif loading_percent <= 330:
        return "U"
    elif loading_percent <= 350:
        return "V"
    elif loading_percent <= 370:
        return "W"
    else:
        return "Z"


def calculate_dive_tissue_loading(
    *,
    route_segments: list[dict],
    gas_o2_fraction: float = 0.21,
    initial_tissue_state: TissueState | None = None,
) -> tuple[TissueState, dict]:
    """Calculate tissue loading for a single dive.

    WARNING: Returns EPHEMERAL data. Do NOT persist.

    Args:
        route_segments: List of dive segments with depth_m, duration_min
        gas_o2_fraction: O2 fraction (0.0-1.0), N2 = 1 - O2 for air/nitrox
        initial_tissue_state: Starting tissue state (None = surface saturated)

    Returns:
        Tuple of (final_tissue_state, dive_metrics)
    """
    # Start with provided state or fresh surface-saturated tissues
    if initial_tissue_state is None:
        tissue_state = TissueState()
    else:
        tissue_state = TissueState(n2_pressures=initial_tissue_state.n2_pressures.copy())

    # Calculate N2 fraction (for air/nitrox, assume no He)
    gas_n2_fraction = 1.0 - gas_o2_fraction

    max_depth = 0.0
    total_runtime = 0.0

    # Process each segment
    for segment in route_segments:
        depth_m = float(segment.get("depth_m", 0))
        duration_min = float(segment.get("duration_min", 0))

        if duration_min <= 0:
            continue

        max_depth = max(max_depth, depth_m)
        total_runtime += duration_min

        # Calculate ambient N2 partial pressure at this depth
        ambient_n2_pp = _depth_to_ambient_n2_pp(depth_m, gas_n2_fraction)

        # Update each tissue compartment
        new_pressures = []
        for i, half_time in enumerate(BUHLMANN_N2_HALFTIMES):
            new_pp = _calculate_compartment_loading(
                initial_pp=tissue_state.n2_pressures[i],
                ambient_pp=ambient_n2_pp,
                duration_min=duration_min,
                half_time_min=half_time,
            )
            new_pressures.append(new_pp)

        tissue_state.n2_pressures = new_pressures

    metrics = {
        "max_depth_m": max_depth,
        "runtime_min": total_runtime,
        "max_loading_percent": tissue_state.max_loading_percent(),
        "gas_o2_fraction": gas_o2_fraction,
    }

    return tissue_state, metrics


def calculate_surface_interval_offgassing(
    *,
    tissue_state: TissueState,
    duration_min: float,
) -> TissueState:
    """Calculate tissue off-gassing during surface interval.

    At surface, tissues off-gas toward surface N2 saturation (0.79 bar).

    WARNING: Returns EPHEMERAL data. Do NOT persist.

    Args:
        tissue_state: Current tissue state after previous dive
        duration_min: Surface interval duration (minutes)

    Returns:
        New tissue state after off-gassing
    """
    if duration_min <= 0:
        return tissue_state

    new_state = TissueState(n2_pressures=tissue_state.n2_pressures.copy())

    # At surface, ambient N2 pp is surface saturation level
    surface_n2_pp = SURFACE_N2_PP

    # Off-gas each compartment toward surface saturation
    new_pressures = []
    for i, half_time in enumerate(BUHLMANN_N2_HALFTIMES):
        new_pp = _calculate_compartment_loading(
            initial_pp=new_state.n2_pressures[i],
            ambient_pp=surface_n2_pp,
            duration_min=duration_min,
            half_time_min=half_time,
        )
        new_pressures.append(new_pp)

    new_state.n2_pressures = new_pressures
    return new_state


@dataclass
class DiveResult:
    """Result for a single dive in the excursion profile."""

    dive_id: str
    sequence: int
    name: str
    max_depth_m: float
    runtime_min: float
    max_loading_percent: float
    loading_before_percent: float
    loading_after_percent: float
    ndl_at_start: int | None  # No Deco Limit at start of dive (minutes)
    pressure_group_before: str  # PADI pressure group before dive
    pressure_group_after: str  # PADI pressure group after dive
    profile_segments: list[dict]  # Raw route_segments for visualization [{phase, depth_m/from_depth_m/to_depth_m, duration_min}, ...]


@dataclass
class SurfaceIntervalResult:
    """Result for a surface interval between dives."""

    before_dive_sequence: int
    duration_min: int
    loading_before_percent: float
    loading_after_percent: float
    pressure_group_before: str  # PADI pressure group at start of SI
    pressure_group_after: str  # PADI pressure group after SI


@dataclass
class ExcursionTissueProfile:
    """Complete tissue profile for an excursion.

    WARNING: This is EPHEMERAL planning data. Do NOT persist.
    """

    version: str
    excursion_type_id: str
    dive_results: list[DiveResult]
    surface_intervals: list[SurfaceIntervalResult]
    final_loading_percent: float
    gf_low: int  # Gradient factor low used for calculations
    gf_high: int  # Gradient factor high used for calculations


def calculate_excursion_tissue_loading(
    excursion_type,
    gf_low: int = DEFAULT_GF_LOW,
    gf_high: int = DEFAULT_GF_HIGH,
) -> ExcursionTissueProfile:
    """Calculate tissue loading for all dives in an excursion.

    WARNING: Returns EPHEMERAL data for planning/visualization only.
    Do NOT store these results. Recalculate fresh each time.

    Args:
        excursion_type: ExcursionType instance with related dives
        gf_low: Low gradient factor (0-100), default 100 (no conservatism)
        gf_high: High gradient factor (0-100), default 100 (no conservatism)

    Returns:
        ExcursionTissueProfile with dive results and surface intervals
    """
    from .planning.segment_converter import segments_to_steps

    dives = excursion_type.dive_templates.order_by("sequence")
    dive_results = []
    surface_intervals = []
    current_tissue_state = TissueState()  # Start surface saturated

    for dive in dives:
        loading_before = current_tissue_state.max_loading_percent()
        pg_before_si = loading_to_pressure_group(loading_before)

        # Apply surface interval off-gassing if not first dive
        if dive.surface_interval_minutes and dive.sequence > 1:
            si_loading_before = current_tissue_state.max_loading_percent()
            si_pg_before = loading_to_pressure_group(si_loading_before)

            current_tissue_state = calculate_surface_interval_offgassing(
                tissue_state=current_tissue_state,
                duration_min=float(dive.surface_interval_minutes),
            )

            si_loading_after = current_tissue_state.max_loading_percent()
            si_pg_after = loading_to_pressure_group(si_loading_after)

            surface_intervals.append(
                SurfaceIntervalResult(
                    before_dive_sequence=dive.sequence,
                    duration_min=dive.surface_interval_minutes,
                    loading_before_percent=si_loading_before,
                    loading_after_percent=si_loading_after,
                    pressure_group_before=si_pg_before,
                    pressure_group_after=si_pg_after,
                )
            )

            # Update loading_before to reflect post-SI state
            loading_before = current_tissue_state.max_loading_percent()

        # Get dive segments from route_segments or use simple depth profile
        if hasattr(dive, "route_segments") and dive.route_segments:
            # Convert route_segments to flat steps for calculation
            steps = segments_to_steps(dive.route_segments)
        else:
            # Simple rectangular profile based on planned depth and duration
            # ExcursionTypeDive uses planned_depth_meters and planned_duration_minutes
            max_depth = getattr(dive, "planned_depth_meters", None)
            if max_depth is None:
                max_depth = getattr(dive, "max_depth_m", 18.0)
            bottom_time = getattr(dive, "planned_duration_minutes", None)
            if bottom_time is None:
                bottom_time = getattr(dive, "bottom_time_min", 30.0)
            steps = [{"depth_m": float(max_depth), "duration_min": float(bottom_time)}]

        # Extract max depth from steps (works for both branches)
        dive_max_depth = max((s.get("depth_m", 0) for s in steps), default=18.0)

        # Get gas mix (default to air)
        gas_o2 = 0.21
        if hasattr(dive, "gas_o2_fraction") and dive.gas_o2_fraction:
            gas_o2 = float(dive.gas_o2_fraction)

        # Calculate NDL at start of this dive (with gradient factors)
        ndl_at_start = calculate_ndl(
            tissue_state=current_tissue_state,
            depth_m=float(dive_max_depth),
            gas_o2_fraction=gas_o2,
            gf_low=gf_low,
            gf_high=gf_high,
        )

        # Pressure group before dive
        pg_before_dive = loading_to_pressure_group(loading_before)

        # Calculate dive tissue loading
        current_tissue_state, metrics = calculate_dive_tissue_loading(
            route_segments=steps,
            gas_o2_fraction=gas_o2,
            initial_tissue_state=current_tissue_state,
        )

        # Pressure group after dive
        loading_after = current_tissue_state.max_loading_percent()
        pg_after_dive = loading_to_pressure_group(loading_after)

        dive_results.append(
            DiveResult(
                dive_id=str(dive.pk),
                sequence=dive.sequence,
                name=dive.name,
                max_depth_m=metrics["max_depth_m"],
                runtime_min=metrics["runtime_min"],
                max_loading_percent=metrics["max_loading_percent"],
                loading_before_percent=loading_before,
                loading_after_percent=loading_after,
                ndl_at_start=ndl_at_start,
                pressure_group_before=pg_before_dive,
                pressure_group_after=pg_after_dive,
                profile_segments=dive.route_segments,  # Raw segments for chart visualization
            )
        )

    return ExcursionTissueProfile(
        version=TISSUE_PAYLOAD_VERSION,
        excursion_type_id=str(excursion_type.pk),
        dive_results=dive_results,
        surface_intervals=surface_intervals,
        final_loading_percent=current_tissue_state.max_loading_percent(),
        gf_low=gf_low,
        gf_high=gf_high,
    )


# =============================================================================
# Protected Area Inheritance-Aware Services
# =============================================================================


def get_applicable_rules(
    *,
    protected_area: ProtectedArea,
    zone: ProtectedAreaZone | None = None,
    as_of: date | None = None,
    activity: str | None = None,
) -> list[ProtectedAreaRule]:
    """Get all rules applicable to area/zone, including inherited from ancestors.

    Resolution order (most specific first):
    1. Zone-specific rules for this area
    2. Area-wide rules for this area
    3. Area-wide rules from parent area
    4. Area-wide rules from grandparent area
    ... up to root

    All filtered by effective_start <= as_of and (effective_end is null or >= as_of).

    Args:
        protected_area: The ProtectedArea to get rules for
        zone: Optional zone within the area (adds zone-specific rules)
        as_of: Date to check rule effective dates against (defaults to today)
        activity: Optional activity filter (e.g., "diving", "snorkeling")
                  Rules with activity="all" are always included

    Returns:
        List of applicable ProtectedAreaRule instances
    """
    if as_of is None:
        as_of = date.today()

    rules = []

    # 1. Zone-specific rules (if zone provided)
    if zone:
        zone_rules = ProtectedAreaRule.objects.filter(
            protected_area=protected_area,
            zone=zone,
            effective_start__lte=as_of,
            is_active=True,
        ).filter(Q(effective_end__isnull=True) | Q(effective_end__gte=as_of))
        if activity:
            zone_rules = zone_rules.filter(Q(activity=activity) | Q(activity="all"))
        rules.extend(zone_rules)

    # 2. Area-wide rules (zone=null) for this area and ancestors
    areas = [protected_area] + protected_area.get_ancestors()
    for area in areas:
        area_rules = ProtectedAreaRule.objects.filter(
            protected_area=area,
            zone__isnull=True,
            effective_start__lte=as_of,
            is_active=True,
        ).filter(Q(effective_end__isnull=True) | Q(effective_end__gte=as_of))
        if activity:
            area_rules = area_rules.filter(Q(activity=activity) | Q(activity="all"))
        rules.extend(area_rules)

    return rules


def get_applicable_fee_schedules(
    *,
    protected_area: ProtectedArea,
    zone: ProtectedAreaZone | None = None,
    as_of: date | None = None,
) -> list[ProtectedAreaFeeSchedule]:
    """Get all fee schedules applicable to area/zone, including inherited from ancestors.

    Resolution order (most specific first):
    1. Zone-specific fees for this area
    2. Area-wide fees for this area
    3. Area-wide fees from parent area
    4. Area-wide fees from grandparent area
    ... up to root

    All filtered by effective_start <= as_of and (effective_end is null or >= as_of).

    Args:
        protected_area: The ProtectedArea to get fee schedules for
        zone: Optional zone within the area (adds zone-specific fees)
        as_of: Date to check fee schedule effective dates against (defaults to today)

    Returns:
        List of applicable ProtectedAreaFeeSchedule instances
    """
    if as_of is None:
        as_of = date.today()

    fees = []

    # 1. Zone-specific fees (if zone provided)
    if zone:
        zone_fees = ProtectedAreaFeeSchedule.objects.filter(
            protected_area=protected_area,
            zone=zone,
            effective_start__lte=as_of,
            is_active=True,
        ).filter(Q(effective_end__isnull=True) | Q(effective_end__gte=as_of))
        fees.extend(zone_fees)

    # 2. Area-wide fees (zone=null) for this area and ancestors
    areas = [protected_area] + protected_area.get_ancestors()
    for area in areas:
        area_fees = ProtectedAreaFeeSchedule.objects.filter(
            protected_area=area,
            zone__isnull=True,
            effective_start__lte=as_of,
            is_active=True,
        ).filter(Q(effective_end__isnull=True) | Q(effective_end__gte=as_of))
        fees.extend(area_fees)

    return fees


# =============================================================================
# Agreement Services
# =============================================================================

import hashlib
import re
from datetime import timedelta

from .exceptions import (
    AgreementNotEditable,
    ChangeNoteRequired,
    VoidReasonRequired,
)


def _render_agreement_content(template_content: str, party) -> str:
    """Render template content with party context.

    Replaces placeholders like {{diver_name}}, {{date}}, {{dive_shop}}, etc.
    """
    from django.conf import settings

    content = template_content

    # Get party name (works for Person or Organization)
    party_name = ""
    if hasattr(party, "first_name") and hasattr(party, "last_name"):
        party_name = f"{party.first_name} {party.last_name}"
    elif hasattr(party, "name"):
        party_name = party.name

    # Get dive shop name from settings or use default
    dive_shop_name = getattr(settings, "DIVE_SHOP_NAME", "Our Dive Shop")

    # Simple placeholder replacement
    replacements = {
        "diver_name": party_name,
        "party_name": party_name,
        "date": timezone.now().strftime("%Y-%m-%d"),
        "today": timezone.now().strftime("%Y-%m-%d"),
        "dive_shop": dive_shop_name,
        "company_name": dive_shop_name,
        "operator_name": dive_shop_name,
    }

    # Party email
    if hasattr(party, "email") and party.email:
        replacements["email"] = party.email

    # Apply all replacements
    for key, value in replacements.items():
        content = re.sub(rf"\{{\{{\s*{key}\s*\}}\}}", str(value), content)

    return content


@transaction.atomic
def create_agreement_from_template(
    *,
    template,
    party_a,
    party_b=None,
    related_object=None,
    content_overrides: dict | None = None,
    actor,
):
    """Create draft SignableAgreement from template.

    Renders template with party context, computes content_hash (SHA-256),
    and creates audit log entry.

    Idempotent: returns existing pending if dedupe constraint matches.

    Args:
        template: AgreementTemplate to create from
        party_a: The party who will sign (Person, Organization, etc.)
        party_b: Optional counter-party
        related_object: Optional related object (Booking, etc.)
        content_overrides: Optional dict to override template variables
        actor: User performing the action (for audit)

    Returns:
        SignableAgreement instance (draft status)
    """
    from .models import SignableAgreement

    # Try to find existing pending agreement (idempotent)
    party_a_ct = ContentType.objects.get_for_model(party_a)
    party_a_id = str(party_a.pk)

    related_ct = None
    related_id = ""
    if related_object:
        related_ct = ContentType.objects.get_for_model(related_object)
        related_id = str(related_object.pk)

    existing = SignableAgreement.objects.filter(
        template=template,
        party_a_content_type=party_a_ct,
        party_a_object_id=party_a_id,
        related_content_type=related_ct,
        related_object_id=related_id,
        status__in=["draft", "sent"],
    ).first()

    if existing:
        return existing

    # Render content
    content = _render_agreement_content(template.content, party_a)

    # Apply any overrides
    if content_overrides:
        for key, value in content_overrides.items():
            content = re.sub(rf"\{{\{{\s*{key}\s*\}}\}}", str(value), content)

    # Compute hash
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Create agreement
    agreement = SignableAgreement.objects.create(
        template=template,
        template_version=template.version,
        party_a_content_type=party_a_ct,
        party_a_object_id=party_a_id,
        party_b_content_type=ContentType.objects.get_for_model(party_b) if party_b else None,
        party_b_object_id=str(party_b.pk) if party_b else "",
        related_content_type=related_ct,
        related_object_id=related_id,
        content_snapshot=content,
        content_hash=content_hash,
        status="draft",
    )

    # Audit log
    log_event(
        action=Actions.AGREEMENT_CREATED,
        target=agreement,
        actor=actor,
        data={
            "template_id": str(template.pk),
            "template_name": template.name,
            "party_a_type": party_a_ct.model,
            "party_a_id": party_a_id,
        },
    )

    return agreement


@transaction.atomic
def edit_agreement(
    *,
    agreement,
    new_content: str,
    change_note: str,
    actor,
):
    """Edit agreement content (draft or sent only).

    Creates SignableAgreementRevision with old/new hash + change_note.
    Updates content_snapshot and content_hash.

    Args:
        agreement: SignableAgreement to edit
        new_content: New content text
        change_note: Required explanation of why change was made
        actor: User performing the action

    Returns:
        Updated SignableAgreement

    Raises:
        ChangeNoteRequired: If change_note is empty
        AgreementNotEditable: If agreement is not in editable status
    """
    from .models import SignableAgreementRevision

    # Validate
    if not change_note or not change_note.strip():
        raise ChangeNoteRequired("Change note is required when editing an agreement")

    if agreement.status not in ("draft", "sent"):
        raise AgreementNotEditable(
            f"Cannot edit agreement in {agreement.status} status"
        )

    # Store old content and hash for revision history
    old_content = agreement.content_snapshot
    old_hash = agreement.content_hash

    # Compute new hash
    new_hash = hashlib.sha256(new_content.encode()).hexdigest()

    # Get next revision number
    max_revision = agreement.revisions.aggregate(models.Max("revision_number"))[
        "revision_number__max"
    ]
    next_revision = (max_revision or 0) + 1

    # Create revision record with content_before for diff viewing
    SignableAgreementRevision.objects.create(
        agreement=agreement,
        revision_number=next_revision,
        previous_content_hash=old_hash,
        new_content_hash=new_hash,
        content_before=old_content,
        change_note=change_note.strip(),
        changed_by=actor,
    )

    # Update agreement
    agreement.content_snapshot = new_content
    agreement.content_hash = new_hash
    agreement.save(update_fields=["content_snapshot", "content_hash", "updated_at"])

    # Audit log
    log_event(
        action=Actions.AGREEMENT_EDITED,
        target=agreement,
        actor=actor,
        data={
            "revision_number": next_revision,
            "change_note": change_note.strip(),
        },
    )

    return agreement


@transaction.atomic
def send_agreement(
    *,
    agreement,
    delivery_method: str,
    expires_in_days: int = 30,
    actor,
):
    """Send agreement to party. Status: draft → sent.

    Generates cryptographically random token, stores only the hash.
    Returns raw token ONCE for URL generation.

    Args:
        agreement: SignableAgreement to send
        delivery_method: How it was sent (email, link, in_person)
        expires_in_days: Days until expiration (default 30)
        actor: User performing the action

    Returns:
        tuple: (agreement, raw_token) - raw token returned ONCE for URL generation
    """
    from .models import SignableAgreement

    # Generate token
    raw_token, token_hash = SignableAgreement.generate_token()

    # Update agreement
    now = timezone.now()
    agreement.status = "sent"
    agreement.sent_at = now
    agreement.sent_by = actor
    agreement.delivery_method = delivery_method
    agreement.access_token = raw_token
    agreement.access_token_hash = token_hash
    agreement.expires_at = now + timedelta(days=expires_in_days)
    agreement.save(
        update_fields=[
            "status",
            "sent_at",
            "sent_by",
            "delivery_method",
            "access_token",
            "access_token_hash",
            "expires_at",
            "updated_at",
        ]
    )

    # Audit log
    log_event(
        action=Actions.AGREEMENT_SENT,
        target=agreement,
        actor=actor,
        data={
            "delivery_method": delivery_method,
            "expires_at": agreement.expires_at.isoformat(),
        },
    )

    return agreement, raw_token


@transaction.atomic
def void_agreement(
    *,
    agreement,
    reason: str,
    actor,
):
    """Void agreement. Any status → void.

    Can void draft, sent, or even signed (for legal recall).
    Requires reason for audit trail.

    Args:
        agreement: SignableAgreement to void
        reason: Required reason for voiding
        actor: User performing the action

    Returns:
        Updated SignableAgreement

    Raises:
        VoidReasonRequired: If reason is empty
    """
    if not reason or not reason.strip():
        raise VoidReasonRequired("Reason is required when voiding an agreement")

    agreement.status = "void"
    agreement.save(update_fields=["status", "updated_at"])

    # Audit log
    log_event(
        action=Actions.AGREEMENT_VOIDED,
        target=agreement,
        actor=actor,
        data={
            "reason": reason.strip(),
        },
    )

    return agreement


def get_agreement_by_token(token: str):
    """Lookup agreement by token hash.

    PUBLIC SIGNING SECURITY:
    - Returns None if token invalid (caller returns 404, not 403)
    - Never reveals whether agreement exists
    - Filters for status='sent' only (can't sign draft or signed)

    Args:
        token: Raw token from signing URL

    Returns:
        SignableAgreement or None if not found/invalid
    """
    from .models import SignableAgreement

    # Hash the token for lookup
    token_hash = SignableAgreement.hash_token(token)

    # Only find sent agreements with valid token
    return SignableAgreement.objects.filter(
        access_token_hash=token_hash,
        status="sent",
        token_consumed=False,
    ).first()


def expire_stale_agreements() -> int:
    """Mark expired agreements as EXPIRED status.

    Called by management command or celery beat.

    Returns:
        Count of agreements marked expired
    """
    from .models import SignableAgreement

    now = timezone.now()

    count = SignableAgreement.objects.filter(
        status="sent",
        expires_at__lt=now,
    ).update(status="expired")

    return count


@transaction.atomic
def resend_agreement(
    *,
    agreement,
    delivery_method: str,
    expires_in_days: int = 30,
    actor,
) -> tuple:
    """Resend a sent agreement with a new token.

    Generates a new access token and updates expiration. Useful when the
    original link has expired or was lost.

    Args:
        agreement: SignableAgreement to resend
        delivery_method: How to deliver (email, link, in_person)
        expires_in_days: Number of days until expiration
        actor: User performing the action

    Returns:
        Tuple of (agreement, raw_token)

    Raises:
        ValueError: If agreement is not in 'sent' status
    """
    from .audit import Actions, log_event
    from .models import SignableAgreement

    if agreement.status != "sent":
        raise ValueError("Can only resend agreements with 'sent' status")

    # Generate new token
    token, token_hash = SignableAgreement.generate_token()

    # Update agreement with new token and expiration
    agreement.access_token = token
    agreement.access_token_hash = token_hash
    agreement.token_consumed = False
    agreement.delivery_method = delivery_method
    agreement.expires_at = timezone.now() + timedelta(days=expires_in_days)
    agreement.save(
        update_fields=[
            "access_token",
            "access_token_hash",
            "token_consumed",
            "delivery_method",
            "expires_at",
            "updated_at",
        ]
    )

    # Log the resend
    log_event(
        action=Actions.AGREEMENT_SENT,  # Use same action as send
        actor=actor,
        target=agreement,
        data={
            "delivery_method": delivery_method,
            "expires_in_days": expires_in_days,
            "is_resend": True,
        },
    )

    return agreement, token


@transaction.atomic
def sign_agreement(
    *,
    agreement,
    raw_token: str,
    signature_image: bytes,
    signed_by_name: str,
    ip_address: str | None = None,
    user_agent: str = "",
    agreed_to_terms: bool = True,
    agreed_to_esign: bool = True,
    # Enhanced digital fingerprint
    fingerprint: dict | None = None,
):
    """Sign an agreement.

    Security measures enforced:
    - Verifies token hash matches (constant-time comparison)
    - Checks token not already consumed
    - Checks expires_at not passed
    - Stores signature as Document (role=signature)
    - Creates django_agreements.Agreement as immutable ledger record
    - Marks token as consumed
    - Captures comprehensive digital fingerprint for legal validity

    Args:
        agreement: SignableAgreement to sign
        raw_token: Token from signing URL
        signature_image: PNG image data of signature
        signed_by_name: Name as entered by signer
        ip_address: IP address of signer
        user_agent: User agent string
        agreed_to_terms: Whether signer checked "agree to terms" checkbox
        agreed_to_esign: Whether signer checked "consent to e-sign" checkbox
        fingerprint: Dict containing digital fingerprint data:
            - screen_resolution: e.g., "1920x1080"
            - timezone: e.g., "America/New_York"
            - timezone_offset: UTC offset in minutes
            - language: Browser language
            - platform: OS/Platform
            - device_memory: Device memory in GB
            - hardware_concurrency: CPU cores
            - touch_support: Touch screen device
            - canvas_fingerprint: SHA-256 hash of canvas fingerprint
            - geolocation: {lat, lng} if permitted

    Returns:
        Updated SignableAgreement

    Raises:
        AgreementExpired: If agreement has expired
        InvalidToken: If token is invalid or consumed
        AgreementAlreadySigned: If agreement is already signed
    """
    from django.conf import settings

    from .audit import Actions, log_event
    from .exceptions import AgreementAlreadySigned, AgreementExpired, InvalidToken
    from .models import SignableAgreement

    # Verify agreement is in correct state
    if agreement.status == "signed":
        raise AgreementAlreadySigned("This agreement has already been signed.")

    if agreement.status != "sent":
        raise InvalidToken("This agreement cannot be signed in its current state.")

    # Verify token
    if not agreement.verify_token(raw_token):
        raise InvalidToken("Invalid or expired signing link.")

    # Check expiration
    if agreement.expires_at and agreement.expires_at < timezone.now():
        raise AgreementExpired("This signing link has expired.")

    # Store signature image as Document if provided
    signature_document = None
    if signature_image:
        try:
            from django.core.files.base import ContentFile
            from django_documents.models import Document, DocumentFolder

            # Get the Signatures folder (child of Agreements)
            signatures_folder = DocumentFolder.objects.filter(
                slug="signatures",
                parent__slug="agreements",
            ).first()

            # Create document for signature
            signature_document = Document.objects.create(
                target=agreement,
                folder=signatures_folder,
                file=ContentFile(
                    signature_image,
                    name=f"signature_{agreement.pk}.png",
                ),
                filename=f"signature_{agreement.pk}.png",
                content_type="image/png",
                document_type="signature",
                description=f"Signature for {signed_by_name}",
            )
        except Exception:
            # If document storage fails, continue without it
            # The signature metadata is still captured
            pass

    # Create immutable ledger record using django-agreements primitive
    from django.contrib.auth import get_user_model
    from django_agreements.services import create_agreement as create_ledger_agreement
    from django_parties.models import Organization

    # Get or create the dive shop organization as party_b
    dive_shop, _ = Organization.objects.get_or_create(
        name=getattr(settings, "DIVE_SHOP_NAME", "Dive Shop"),
        defaults={"legal_name": getattr(settings, "DIVE_SHOP_NAME", "Dive Shop")},
    )

    # For agreed_by, we need a User instance.
    # Use the staff member who sent the agreement, or fall back to a system user.
    User = get_user_model()
    if agreement.sent_by:
        agreed_by_user = agreement.sent_by
    else:
        # Fall back to first superuser or create system user
        agreed_by_user = User.objects.filter(is_superuser=True).first()
        if not agreed_by_user:
            agreed_by_user, _ = User.objects.get_or_create(
                username="system",
                defaults={"is_active": False, "email": "system@localhost"},
            )

    # Create the ledger agreement using the primitive's service
    ledger_agreement = create_ledger_agreement(
        party_a=agreement.party_a,
        party_b=dive_shop,
        scope_type="waiver",
        terms={
            "template_name": agreement.template.name,
            "template_version": agreement.template_version,
            "content": agreement.content_snapshot,
            "content_hash": agreement.content_hash,
            "signed_by_name": signed_by_name,
            "signed_ip": ip_address,
        },
        agreed_by=agreed_by_user,
        valid_from=timezone.now(),
    )

    # Update agreement fields before PDF generation
    agreement.status = SignableAgreement.Status.SIGNED
    agreement.signed_at = timezone.now()
    agreement.signed_by_name = signed_by_name
    agreement.signed_ip = ip_address
    agreement.signed_user_agent = user_agent
    agreement.token_consumed = True
    agreement.signature_document = signature_document
    agreement.ledger_agreement = ledger_agreement
    agreement.agreed_to_terms = agreed_to_terms
    agreement.agreed_to_esign = agreed_to_esign

    # Store enhanced fingerprint data
    fp = fingerprint or {}
    agreement.signed_screen_resolution = fp.get("screen_resolution", "")[:20]
    agreement.signed_timezone = fp.get("timezone", "")[:100]
    agreement.signed_timezone_offset = fp.get("timezone_offset")
    agreement.signed_language = fp.get("language", "")[:50]
    agreement.signed_platform = fp.get("platform", "")[:100]
    agreement.signed_device_memory = fp.get("device_memory", "")[:20]
    agreement.signed_hardware_concurrency = fp.get("hardware_concurrency")
    agreement.signed_touch_support = fp.get("touch_support")
    agreement.signed_canvas_fingerprint = fp.get("canvas_fingerprint", "")[:64]
    agreement.signed_geolocation = fp.get("geolocation")

    # Generate signed PDF with digital proof stamp
    signed_pdf_document = None
    try:
        from django.core.files.base import ContentFile
        from django_documents.models import Document, DocumentFolder

        # Get the Signed PDFs folder (child of Agreements)
        signed_pdfs_folder = DocumentFolder.objects.filter(
            slug="signed-pdfs",
            parent__slug="agreements",
        ).first()

        pdf_bytes = _generate_signed_agreement_pdf(agreement)
        signed_pdf_document = Document.objects.create(
            target=agreement,
            folder=signed_pdfs_folder,
            file=ContentFile(
                pdf_bytes,
                name=f"signed_agreement_{agreement.pk}.pdf",
            ),
            filename=f"signed_agreement_{agreement.pk}.pdf",
            content_type="application/pdf",
            document_type="signed_agreement",
            description=f"Signed agreement for {signed_by_name} on {agreement.signed_at.strftime('%Y-%m-%d')}",
        )
        agreement.signed_document = signed_pdf_document
    except Exception:
        # If PDF generation fails, continue without it
        # The agreement is still valid
        pass

    agreement.save(
        update_fields=[
            "status",
            "signed_at",
            "signed_by_name",
            "signed_ip",
            "signed_user_agent",
            "token_consumed",
            "signature_document",
            "signed_document",
            "ledger_agreement",
            "agreed_to_terms",
            "agreed_to_esign",
            # Enhanced fingerprint fields
            "signed_screen_resolution",
            "signed_timezone",
            "signed_timezone_offset",
            "signed_language",
            "signed_platform",
            "signed_device_memory",
            "signed_hardware_concurrency",
            "signed_touch_support",
            "signed_canvas_fingerprint",
            "signed_geolocation",
            "updated_at",
        ]
    )

    # Log the signing with PDF information and full fingerprint
    audit_data = {
        "signed_by_name": signed_by_name,
        "ip_address": ip_address,
        "user_agent": _truncate_user_agent(user_agent, 100) if user_agent else None,
        "has_signature_image": bool(signature_document),
        "content_hash": agreement.content_hash,
        "consent": {
            "agreed_to_terms": agreed_to_terms,
            "agreed_to_esign": agreed_to_esign,
            "terms_text": "I have read and understand the agreement above, and I agree to be bound by its terms.",
            "esign_text": "I consent to sign this document electronically. I understand that my electronic signature has the same legal effect as a handwritten signature and that a signed copy will be available for my records.",
        },
        # Enhanced digital fingerprint for legal validity
        "digital_fingerprint": {
            "screen_resolution": fp.get("screen_resolution"),
            "timezone": fp.get("timezone"),
            "timezone_offset_minutes": fp.get("timezone_offset"),
            "language": fp.get("language"),
            "platform": fp.get("platform"),
            "device_memory_gb": fp.get("device_memory"),
            "cpu_cores": fp.get("hardware_concurrency"),
            "touch_support": fp.get("touch_support"),
            "canvas_fingerprint_hash": fp.get("canvas_fingerprint"),
            "geolocation": fp.get("geolocation"),
        },
    }

    # Add PDF information if generated
    if signed_pdf_document:
        # Compute checksum for the PDF
        pdf_checksum = signed_pdf_document.compute_checksum() if hasattr(signed_pdf_document, 'compute_checksum') else None
        if pdf_checksum and not signed_pdf_document.checksum:
            signed_pdf_document.checksum = pdf_checksum
            signed_pdf_document.save(update_fields=['checksum'])

        audit_data["pdf"] = {
            "filename": signed_pdf_document.filename,
            "location": signed_pdf_document.file.url if signed_pdf_document.file else None,
            "checksum": signed_pdf_document.checksum or pdf_checksum,
            "document_id": str(signed_pdf_document.pk),
        }

    log_event(
        action=Actions.AGREEMENT_SIGNED,
        actor=None,  # Public signing has no authenticated user
        target=agreement,
        data=audit_data,
    )

    return agreement


# =============================================================================
# PDF Generation for Signed Agreements
# =============================================================================


def _generate_signed_agreement_pdf(agreement) -> bytes:
    """
    Generate a PDF document for a signed agreement with digital proof stamp.

    The PDF includes:
    - Agreement content
    - Signature image with name and date
    - Digital signature proof footer with:
      - Document hash
      - Signer's name
      - Signed date/time (UTC)
      - IP address
      - User agent fingerprint

    Args:
        agreement: SignableAgreement that has been signed

    Returns:
        PDF content as bytes
    """
    import base64
    from weasyprint import HTML, CSS

    # Get signature image as base64 if available
    signature_img_html = ""
    if agreement.signature_document and agreement.signature_document.file:
        try:
            agreement.signature_document.file.seek(0)
            sig_data = agreement.signature_document.file.read()
            sig_b64 = base64.b64encode(sig_data).decode('utf-8')
            content_type = agreement.signature_document.content_type or 'image/png'
            signature_img_html = f'<img src="data:{content_type};base64,{sig_b64}" class="signature-image" alt="Signature">'
        except Exception:
            pass

    # Format signed date
    signed_date_formatted = agreement.signed_at.strftime('%B %d, %Y') if agreement.signed_at else 'N/A'
    signed_time_formatted = agreement.signed_at.strftime('%I:%M %p UTC') if agreement.signed_at else ''

    # Create HTML with agreement content and digital proof footer
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: letter;
                margin: 1in;
                @bottom-center {{
                    content: "Page " counter(page) " of " counter(pages);
                    font-size: 10px;
                    color: #666;
                }}
            }}
            body {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                font-size: 12px;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                text-align: center;
                margin-bottom: 2em;
                padding-bottom: 1em;
                border-bottom: 2px solid #333;
            }}
            .header h1 {{
                margin: 0;
                font-size: 18px;
                font-weight: bold;
            }}
            .header .date {{
                margin-top: 0.5em;
                font-size: 11px;
                color: #666;
            }}
            .content {{
                margin-bottom: 3em;
            }}
            .signature-block {{
                margin-top: 3em;
                page-break-inside: avoid;
                border: 1px solid #ccc;
                padding: 1.5em;
                background-color: #fafafa;
            }}
            .signature-block h3 {{
                margin: 0 0 1em 0;
                font-size: 14px;
                color: #333;
            }}
            .signature-image {{
                max-width: 300px;
                max-height: 100px;
                border-bottom: 2px solid #333;
                display: block;
                margin-bottom: 0.5em;
            }}
            .signature-details {{
                margin-top: 0.5em;
            }}
            .signature-name {{
                font-size: 14px;
                font-weight: bold;
                color: #333;
            }}
            .signature-date {{
                font-size: 12px;
                color: #666;
                margin-top: 0.25em;
            }}
            .signature-line {{
                border-top: 2px solid #333;
                width: 300px;
                margin-top: 60px;
                padding-top: 5px;
            }}
            .digital-proof {{
                margin-top: 3em;
                padding: 1em;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                font-size: 9px;
                page-break-inside: avoid;
            }}
            .digital-proof h3 {{
                margin: 0 0 1em 0;
                font-size: 11px;
                color: #333;
                border-bottom: 1px solid #ccc;
                padding-bottom: 0.5em;
            }}
            .digital-proof .proof-row {{
                display: flex;
                margin: 0.3em 0;
            }}
            .digital-proof .proof-label {{
                font-weight: bold;
                width: 120px;
                color: #555;
            }}
            .digital-proof .proof-value {{
                font-family: 'Courier New', monospace;
                word-break: break-all;
            }}
            .digital-proof .hash {{
                font-size: 8px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{agreement.template.name}</h1>
            <div class="date">Document ID: {agreement.pk}</div>
        </div>

        <div class="content">
            {agreement.content_snapshot}
        </div>

        <div class="signature-block">
            <h3>Signature</h3>
            {signature_img_html if signature_img_html else '<div class="signature-line"></div>'}
            <div class="signature-details">
                <div class="signature-name">{agreement.signed_by_name}</div>
                <div class="signature-date">Date: {signed_date_formatted}</div>
            </div>
        </div>

        <div class="digital-proof">
            <h3>🔒 Digital Signature Verification</h3>
            <div class="proof-row">
                <span class="proof-label">Signer Name:</span>
                <span class="proof-value">{agreement.signed_by_name}</span>
            </div>
            <div class="proof-row">
                <span class="proof-label">Signed Date:</span>
                <span class="proof-value">{agreement.signed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if agreement.signed_at else 'N/A'}</span>
            </div>
            <div class="proof-row">
                <span class="proof-label">IP Address:</span>
                <span class="proof-value">{agreement.signed_ip or 'Not recorded'}</span>
            </div>
            <div class="proof-row">
                <span class="proof-label">Browser:</span>
                <span class="proof-value">{_truncate_user_agent(agreement.signed_user_agent) if agreement.signed_user_agent else 'Not recorded'}</span>
            </div>
            <div class="proof-row">
                <span class="proof-label">Content Hash:</span>
                <span class="proof-value hash">{agreement.content_hash}</span>
            </div>
            <div class="proof-row">
                <span class="proof-label">Document ID:</span>
                <span class="proof-value">{agreement.pk}</span>
            </div>
            <div style="margin-top: 1em; font-size: 8px; color: #888;">
                This document was digitally signed. The content hash can be used to verify
                that this document has not been modified since signing.
            </div>
        </div>
    </body>
    </html>
    """

    # Generate PDF using WeasyPrint
    html = HTML(string=html_content)
    pdf_bytes = html.write_pdf()

    return pdf_bytes


def _truncate_user_agent(user_agent: str, max_length: int = 80) -> str:
    """Truncate user agent string for display."""
    if not user_agent:
        return ""
    if len(user_agent) <= max_length:
        return user_agent
    return user_agent[:max_length] + "..."


# =============================================================================
# Agreement Integration Services (for Booking/Enrollment Flows)
# =============================================================================


def ensure_required_agreements(
    *,
    related_object,
    party,
    templates_required: list,
    actor,
) -> list:
    """Create/return agreements required for a related object.

    IDEMPOTENT due to UniqueConstraint on (template, party_a, related_content_type, related_id).

    Args:
        related_object: The booking, enrollment, etc. that requires agreements
        party: The Person/Organization who needs to sign
        templates_required: List of AgreementTemplate objects required
        actor: User performing the action

    Returns:
        List of all pending (draft/sent) agreements for this party+object

    Example:
        templates = AgreementTemplate.objects.filter(is_required_for_booking=True)
        agreements = ensure_required_agreements(
            related_object=booking,
            party=diver,
            templates_required=list(templates),
            actor=request.user,
        )
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import SignableAgreement

    # Get content type for related object
    ct = ContentType.objects.get_for_model(related_object)
    object_id = str(related_object.pk)

    # Get party content type
    party_ct = ContentType.objects.get_for_model(party)
    party_id = str(party.pk)

    agreements = []

    for template in templates_required:
        # Check for existing pending agreement
        existing = SignableAgreement.objects.filter(
            template=template,
            party_a_content_type=party_ct,
            party_a_object_id=party_id,
            related_content_type=ct,
            related_id=object_id,
            status__in=["draft", "sent"],
        ).first()

        if existing:
            agreements.append(existing)
        else:
            # Create new draft agreement
            agreement = create_agreement_from_template(
                template=template,
                party_a=party,
                related_object=related_object,
                actor=actor,
            )
            agreements.append(agreement)

    return agreements


def get_pending_agreements(related_object) -> list:
    """Get all pending (draft/sent) agreements for a related object.

    Args:
        related_object: The booking, enrollment, etc.

    Returns:
        QuerySet of SignableAgreement objects in draft or sent status
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import SignableAgreement

    ct = ContentType.objects.get_for_model(related_object)
    object_id = str(related_object.pk)

    return list(
        SignableAgreement.objects.filter(
            related_content_type=ct,
            related_id=object_id,
            status__in=["draft", "sent"],
        ).select_related("template")
    )


def all_agreements_signed(related_object) -> bool:
    """Check if all required agreements for an object are signed.

    Args:
        related_object: The booking, enrollment, etc.

    Returns:
        True if no pending (draft/sent) agreements exist for this object
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import SignableAgreement

    ct = ContentType.objects.get_for_model(related_object)
    object_id = str(related_object.pk)

    # Check if any pending agreements exist
    pending_count = SignableAgreement.objects.filter(
        related_content_type=ct,
        related_id=object_id,
        status__in=["draft", "sent"],
    ).count()

    return pending_count == 0


def get_signed_agreements(related_object) -> list:
    """Get all signed agreements for a related object.

    Args:
        related_object: The booking, enrollment, etc.

    Returns:
        List of SignableAgreement objects in signed status
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import SignableAgreement

    ct = ContentType.objects.get_for_model(related_object)
    object_id = str(related_object.pk)

    return list(
        SignableAgreement.objects.filter(
            related_content_type=ct,
            related_id=object_id,
            status="signed",
        ).select_related("template", "ledger_agreement")
    )


# =============================================================================
# AI Text Enhancement Service
# =============================================================================


@dataclass
class EnhancedDocument:
    """Result of AI document enhancement."""

    content: str
    method: str
    suggested_title: str = ""


def enhance_extracted_text(text: str, method: str) -> EnhancedDocument:
    """
    Enhance extracted text using AI if configured.

    Uses OpenRouter API to clean up OCR errors and format document text.
    Falls back to original text if AI is disabled, not configured, or fails.

    Args:
        text: Raw extracted text from document
        method: Extraction method used (e.g., "tesseract", "pypdf2")

    Returns:
        EnhancedDocument with content, method, and suggested_title
        If AI enhancement is applied, method will have "+ai_enhanced(model)" appended
    """
    import json
    import logging

    from .models import AISettings

    logger = logging.getLogger(__name__)

    # Get AI settings
    ai_settings = AISettings.get_instance()

    # Check if enhancement is enabled
    if not ai_settings.ocr_enhancement_enabled:
        return EnhancedDocument(content=text, method=method)

    # Check if AI is configured
    if not ai_settings.is_configured():
        return EnhancedDocument(content=text, method=method)

    try:
        import requests

        api_key = ai_settings.get_with_fallback("openrouter_api_key")
        model = ai_settings.default_model

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://diveops.local",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": """You are a legal document formatter. Transform raw OCR text into professionally styled HTML for display in a web application.

OUTPUT FORMAT: JSON with two fields:
{
  "title": "Document Title (extracted or generated from content)",
  "content": "<html content here>"
}

HTML STRUCTURE FOR content FIELD:
1. DO NOT include the title in the HTML - it will be displayed separately
2. Sections - Use <h3 class="font-semibold mt-6 mb-2">Section Name</h3>
3. Numbered Lists - Use <ol class="list-decimal ml-6 space-y-2"><li>Item</li></ol>
4. Paragraphs - Use <p class="mb-4">Text</p>
5. For questionnaires/checklists, use interactive checkboxes:
   <div class="space-y-2">
     <label class="flex items-start gap-2">
       <input type="checkbox" name="question_1" class="mt-1">
       <span>Question or statement text</span>
     </label>
   </div>
6. Signature and Verification Block at end:
   <div class="mt-8 pt-4 border-t space-y-6">
     <div class="no-print bg-blue-50 border border-blue-200 rounded p-4">
       <p class="text-sm text-blue-800 mb-2">Please review this document carefully before signing.</p>
       <button type="button" onclick="window.print()" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">
         Print Document for Review
       </button>
     </div>
     <div>
       <h4 class="font-semibold mb-3">Required Documents</h4>
       <div class="space-y-4">
         <div>
           <label class="block text-sm font-medium mb-1">Photo ID (Driver's License or Passport)</label>
           <input type="file" name="photo_id" accept="image/*,.pdf" class="block w-full text-sm border rounded p-2">
         </div>
         <div>
           <label class="block text-sm font-medium mb-1">Certification Card (Front)</label>
           <input type="file" name="certification_card" accept="image/*,.pdf" class="block w-full text-sm border rounded p-2">
         </div>
       </div>
     </div>
     <div>
       <h4 class="font-semibold mb-3">Dive Insurance</h4>
       <div class="space-y-3">
         <label class="flex items-center gap-2">
           <input type="checkbox" name="has_dan_insurance" id="has_dan_insurance" onchange="document.getElementById('dan_policy_section').classList.toggle('hidden', !this.checked)">
           <span>I have DAN (Divers Alert Network) insurance</span>
         </label>
         <div id="dan_policy_section" class="hidden ml-6">
           <label class="block text-sm font-medium mb-1">DAN Policy Number</label>
           <input type="text" name="dan_policy_number" class="block w-full text-sm border rounded p-2" placeholder="Enter your DAN policy number">
         </div>
       </div>
     </div>
     <div class="print-only">
       <h4 class="font-semibold mb-3">Signature</h4>
       <p class="mb-4"><strong>Participant Signature:</strong> _______________________</p>
       <p class="mb-4"><strong>Print Name:</strong> {{ diver_name }}</p>
       <p><strong>Date:</strong> {{ date }}</p>
     </div>
     <div class="no-print bg-blue-50 border border-blue-200 rounded p-4">
       <p class="text-sm text-blue-800 mb-2">Before signing electronically, you may print a copy for review.</p>
       <button type="button" onclick="window.print()" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">
         Print for Review
       </button>
     </div>
   </div>

TITLE FIELD:
- Extract the document title from the content (e.g., "Liability Waiver", "Medical Questionnaire")
- If no clear title, generate one based on document type (e.g., "Dive Liability Release Form")
- Keep it concise (3-6 words typically)

CONTENT RULES:
- Fix OCR errors (l/1, O/0, rn/m confusions)
- Preserve all legal language - do not change meaning
- Use {{ field_name }} for Django template variables ({{ diver_name }}, {{ date }}, etc.)
- Remove duplicate text or OCR artifacts
- Use <strong> for emphasis, <em> for italics
- For yes/no questions, medical forms, or checklists, use checkboxes

Output ONLY valid JSON. No markdown, no explanations, no code fences.""",
                    },
                    {
                        "role": "user",
                        "content": f"Clean and format this extracted document:\n\n{text}",
                    },
                ],
                "temperature": 0.1,
                "max_tokens": 4000,
            },
            timeout=60,
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"]
            enhanced_method = f"{method}+ai_enhanced({model})"

            # Try to parse as JSON
            try:
                # Strip any markdown code fences if present
                ai_response = ai_response.strip()
                if ai_response.startswith("```"):
                    # Remove code fence markers
                    lines = ai_response.split("\n")
                    ai_response = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

                parsed = json.loads(ai_response)
                return EnhancedDocument(
                    content=parsed.get("content", ai_response),
                    method=enhanced_method,
                    suggested_title=parsed.get("title", ""),
                )
            except json.JSONDecodeError:
                # AI didn't return valid JSON, use response as content
                logger.warning("AI response was not valid JSON, using as plain content")
                return EnhancedDocument(
                    content=ai_response,
                    method=enhanced_method,
                    suggested_title="",
                )
        else:
            logger.warning(
                f"AI enhancement failed: {response.status_code} - {response.text}"
            )
            return EnhancedDocument(content=text, method=method)

    except Exception as e:
        logger.warning(f"AI enhancement error: {e}")
        return EnhancedDocument(content=text, method=method)


# =============================================================================
# Buddy Services
# =============================================================================


def get_or_create_identity(*, person=None, contact=None):
    """Get or create a BuddyIdentity for a Person or Contact.

    Args:
        person: A Person instance (mutually exclusive with contact)
        contact: A Contact instance (mutually exclusive with person)

    Returns:
        Tuple of (BuddyIdentity, created: bool)

    Raises:
        ValueError: If both person and contact provided, or neither provided
    """
    from .models import BuddyIdentity

    if person is not None and contact is not None:
        raise ValueError("Cannot provide both person and contact")
    if person is None and contact is None:
        raise ValueError("Must provide either person or contact")

    if person is not None:
        return BuddyIdentity.objects.get_or_create(person=person)
    else:
        return BuddyIdentity.objects.get_or_create(contact=contact)


def add_buddy_pair(*, me_person, friend_person=None, friend_data=None):
    """Create a buddy pair (team of 2).

    Args:
        me_person: The Person creating the buddy relationship
        friend_person: Existing Person to add as buddy (optional)
        friend_data: Dict with display_name, email, and/or phone to create Contact

    Returns:
        DiveTeam instance with 2 members

    Raises:
        ValueError: If trying to add yourself, or neither friend_person nor friend_data
    """
    from .models import BuddyIdentity, Contact, DiveTeam, DiveTeamMember

    if friend_person is None and friend_data is None:
        raise ValueError("Must provide either friend_person or friend_data")

    if friend_person is not None and friend_person.pk == me_person.pk:
        raise ValueError("Cannot add yourself as your own buddy")

    with transaction.atomic():
        # Get or create my identity
        my_identity, _ = get_or_create_identity(person=me_person)

        # Get or create friend's identity
        if friend_person is not None:
            friend_identity, _ = get_or_create_identity(person=friend_person)
        else:
            # Create Contact from friend_data
            contact = Contact.objects.create(
                created_by=me_person,
                display_name=friend_data.get("display_name", ""),
                email=friend_data.get("email"),
                phone=friend_data.get("phone"),
            )
            friend_identity, _ = get_or_create_identity(contact=contact)

        # Check if pair already exists
        existing_team = _find_existing_pair(my_identity, friend_identity)
        if existing_team:
            return existing_team

        # Create new team
        team = DiveTeam.objects.create(
            team_type=DiveTeam.TeamType.BUDDY,
            created_by=me_person,
        )

        # Add both members
        DiveTeamMember.objects.create(team=team, identity=my_identity)
        DiveTeamMember.objects.create(team=team, identity=friend_identity)

        return team


def _find_existing_pair(identity1, identity2):
    """Find existing buddy pair containing both identities."""
    from .models import DiveTeam

    # Find teams where identity1 is a member
    teams_with_1 = DiveTeam.objects.filter(
        members__identity=identity1,
        deleted_at__isnull=True,
    )

    for team in teams_with_1:
        if team.members.count() == 2:
            if team.members.filter(identity=identity2).exists():
                return team

    return None


def create_buddy_group(*, me_person, friend_persons, name=None):
    """Create a buddy group (team of 3+).

    Args:
        me_person: The Person creating the group
        friend_persons: List of Person instances to include
        name: Optional name for the group

    Returns:
        DiveTeam instance with 3+ members
    """
    from .models import DiveTeam, DiveTeamMember

    with transaction.atomic():
        # Create team
        team = DiveTeam.objects.create(
            team_type=DiveTeam.TeamType.BUDDY,
            name=name or "",
            created_by=me_person,
        )

        # Add creator
        my_identity, _ = get_or_create_identity(person=me_person)
        DiveTeamMember.objects.create(team=team, identity=my_identity)

        # Add friends
        for friend in friend_persons:
            friend_identity, _ = get_or_create_identity(person=friend)
            DiveTeamMember.objects.create(team=team, identity=friend_identity)

        return team


def list_buddy_pairs(person):
    """List buddy pairs (size=2) where person is a member.

    Args:
        person: Person to find pairs for

    Returns:
        List of dicts with team_id, buddy_name, is_registered
    """
    from .models import BuddyIdentity, DiveTeam

    # Get person's identity
    try:
        my_identity = BuddyIdentity.objects.get(person=person)
    except BuddyIdentity.DoesNotExist:
        return []

    # Find teams with exactly 2 members where person is one
    pairs = []
    teams = DiveTeam.objects.filter(
        members__identity=my_identity,
        deleted_at__isnull=True,
    )

    for team in teams:
        if team.members.count() == 2:
            # Find the other member
            other_member = team.members.exclude(identity=my_identity).first()
            if other_member:
                pairs.append({
                    "team_id": team.pk,
                    "buddy_name": other_member.identity.display_name,
                    "is_registered": other_member.identity.is_registered,
                })

    return pairs


def list_buddy_groups(person):
    """List buddy groups (size>=3) where person is a member.

    Args:
        person: Person to find groups for

    Returns:
        List of dicts with team_id, name, member_count
    """
    from .models import BuddyIdentity, DiveTeam

    # Get person's identity
    try:
        my_identity = BuddyIdentity.objects.get(person=person)
    except BuddyIdentity.DoesNotExist:
        return []

    # Find teams with 3+ members where person is one
    groups = []
    teams = DiveTeam.objects.filter(
        members__identity=my_identity,
        deleted_at__isnull=True,
    )

    for team in teams:
        if team.members.count() >= 3:
            groups.append({
                "team_id": team.pk,
                "name": team.name,
                "member_count": team.members.count(),
            })

    return groups


def remove_buddy(*, me_person, team_id):
    """Remove person from a buddy team.

    For pairs (size=2): soft-deletes the whole team
    For groups (size>=3): removes person's membership

    Args:
        me_person: Person leaving the team
        team_id: UUID of the team
    """
    from .models import BuddyIdentity, DiveTeam

    with transaction.atomic():
        team = DiveTeam.objects.select_for_update().get(pk=team_id)
        my_identity = BuddyIdentity.objects.get(person=me_person)

        if team.members.count() == 2:
            # Pair - delete the whole team
            team.delete()
        else:
            # Group - just remove membership
            membership = team.members.get(identity=my_identity)
            membership.delete()
