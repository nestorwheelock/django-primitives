"""Audit logging adapter for diveops.

This module provides a thin adapter to django_audit_log for domain-specific audit events.
DiveOps emits audit events but does NOT store audit data locally - the django_audit_log
primitive owns persistence.

All domain code must call this adapter, not django_audit_log directly.
This ensures stable action strings and consistent metadata across the domain.

=============================================================================
Django Audit Log API Reference (from ARCHITECTURE.md)
=============================================================================

Import path:
    from django_audit_log import log, log_event

log() parameters:
    - action: str (required) - what happened
    - obj: Model - Django model instance (extracts label/id/repr)
    - actor: User - who performed the action (AUTH_USER_MODEL)
    - request: HttpRequest - for IP/UA extraction
    - changes: dict - {"field": {"old": x, "new": y}}
    - metadata: dict - additional context
    - sensitivity: str - normal/high/critical
    - is_system: bool - True if system action

log_event() - for non-model events (login, permission denied, etc.)

Actor is ALWAYS a Django User, not Party. This is by design to keep
django_audit_log dependency-free from django_parties.

=============================================================================
Usage:
    from diveops.audit import log_event, Actions

    log_event(
        action=Actions.BOOKING_CREATED,
        target=booking,
        actor=request.user,
        data={"excursion_id": str(excursion.pk), "diver_id": str(diver.pk)},
    )
"""

from django_audit_log import log as audit_log


# =============================================================================
# Stable Action Constants - PUBLIC CONTRACT
# =============================================================================
# These strings are part of the DiveOps audit contract.
# DO NOT RENAME - changing them requires migration of existing audit data.
# Add new actions as needed, but never modify existing ones.


class Actions:
    """Stable audit action constants for DiveOps operations.

    These are domain-specific action strings that provide semantic meaning
    beyond generic CRUD operations. They are stable and constitute a
    public API contract.
    """

    # -------------------------------------------------------------------------
    # Diver Actions
    # -------------------------------------------------------------------------
    DIVER_CREATED = "diver_created"
    DIVER_UPDATED = "diver_updated"
    DIVER_DELETED = "diver_deleted"
    DIVER_ACTIVATED = "diver_activated"
    DIVER_DEACTIVATED = "diver_deactivated"

    # -------------------------------------------------------------------------
    # Certification Actions
    # -------------------------------------------------------------------------
    CERTIFICATION_ADDED = "certification_added"
    CERTIFICATION_UPDATED = "certification_updated"
    CERTIFICATION_REMOVED = "certification_removed"
    CERTIFICATION_VERIFIED = "certification_verified"
    CERTIFICATION_UNVERIFIED = "certification_unverified"
    CERTIFICATION_PROOF_UPLOADED = "certification_proof_uploaded"
    CERTIFICATION_PROOF_REMOVED = "certification_proof_removed"

    # -------------------------------------------------------------------------
    # Excursion Actions
    # -------------------------------------------------------------------------
    EXCURSION_CREATED = "excursion_created"
    EXCURSION_UPDATED = "excursion_updated"
    EXCURSION_DELETED = "excursion_deleted"
    EXCURSION_PUBLISHED = "excursion_published"
    EXCURSION_CANCELLED = "excursion_cancelled"
    EXCURSION_RESCHEDULED = "excursion_rescheduled"
    EXCURSION_STARTED = "excursion_started"
    EXCURSION_COMPLETED = "excursion_completed"

    # Backwards compatibility aliases (deprecated)
    TRIP_CREATED = EXCURSION_CREATED
    TRIP_UPDATED = EXCURSION_UPDATED
    TRIP_DELETED = EXCURSION_DELETED
    TRIP_PUBLISHED = EXCURSION_PUBLISHED
    TRIP_CANCELLED = EXCURSION_CANCELLED
    TRIP_RESCHEDULED = EXCURSION_RESCHEDULED
    TRIP_STARTED = EXCURSION_STARTED
    TRIP_COMPLETED = EXCURSION_COMPLETED

    # -------------------------------------------------------------------------
    # Booking / Roster Actions
    # -------------------------------------------------------------------------
    BOOKING_CREATED = "booking_created"
    BOOKING_CANCELLED = "booking_cancelled"
    BOOKING_CANCELLATION_BLOCKED = "booking_cancellation_blocked"
    BOOKING_PAID = "booking_paid"
    BOOKING_REFUNDED = "booking_refunded"
    DIVER_CHECKED_IN = "diver_checked_in"
    DIVER_NO_SHOW = "diver_no_show"
    DIVER_COMPLETED_EXCURSION = "diver_completed_excursion"
    DIVER_REMOVED_FROM_EXCURSION = "diver_removed_from_excursion"

    # Backwards compatibility aliases (deprecated)
    DIVER_COMPLETED_TRIP = DIVER_COMPLETED_EXCURSION
    DIVER_REMOVED_FROM_TRIP = DIVER_REMOVED_FROM_EXCURSION

    # -------------------------------------------------------------------------
    # Eligibility / Override Actions
    # -------------------------------------------------------------------------
    ELIGIBILITY_CHECKED = "eligibility_checked"
    ELIGIBILITY_FAILED = "eligibility_failed"
    ELIGIBILITY_OVERRIDDEN = "eligibility_overridden"
    BOOKING_ELIGIBILITY_OVERRIDDEN = "booking_eligibility_overridden"  # INV-1: booking-scoped

    # -------------------------------------------------------------------------
    # Excursion Requirement Actions
    # -------------------------------------------------------------------------
    EXCURSION_REQUIREMENT_ADDED = "excursion_requirement_added"
    EXCURSION_REQUIREMENT_UPDATED = "excursion_requirement_updated"
    EXCURSION_REQUIREMENT_REMOVED = "excursion_requirement_removed"

    # Backwards compatibility aliases (deprecated)
    TRIP_REQUIREMENT_ADDED = EXCURSION_REQUIREMENT_ADDED
    TRIP_REQUIREMENT_UPDATED = EXCURSION_REQUIREMENT_UPDATED
    TRIP_REQUIREMENT_REMOVED = EXCURSION_REQUIREMENT_REMOVED

    # -------------------------------------------------------------------------
    # Dive Actions (individual dives within an excursion)
    # -------------------------------------------------------------------------
    DIVE_CREATED = "dive_created"
    DIVE_UPDATED = "dive_updated"
    DIVE_DELETED = "dive_deleted"

    # -------------------------------------------------------------------------
    # Dive Template Actions (ExcursionTypeDive - product configuration)
    # -------------------------------------------------------------------------
    DIVE_TEMPLATE_CREATED = "dive_template_created"
    DIVE_TEMPLATE_UPDATED = "dive_template_updated"
    DIVE_TEMPLATE_DELETED = "dive_template_deleted"

    # -------------------------------------------------------------------------
    # Dive Site Actions
    # -------------------------------------------------------------------------
    DIVE_SITE_CREATED = "dive_site_created"
    DIVE_SITE_UPDATED = "dive_site_updated"
    DIVE_SITE_DELETED = "dive_site_deleted"

    # -------------------------------------------------------------------------
    # Excursion Type Actions
    # -------------------------------------------------------------------------
    EXCURSION_TYPE_CREATED = "excursion_type_created"
    EXCURSION_TYPE_UPDATED = "excursion_type_updated"
    EXCURSION_TYPE_DELETED = "excursion_type_deleted"
    EXCURSION_TYPE_ACTIVATED = "excursion_type_activated"
    EXCURSION_TYPE_DEACTIVATED = "excursion_type_deactivated"

    # -------------------------------------------------------------------------
    # Site Price Adjustment Actions
    # -------------------------------------------------------------------------
    SITE_PRICE_ADJUSTMENT_CREATED = "site_price_adjustment_created"
    SITE_PRICE_ADJUSTMENT_UPDATED = "site_price_adjustment_updated"
    SITE_PRICE_ADJUSTMENT_DELETED = "site_price_adjustment_deleted"
    SITE_PRICE_ADJUSTMENT_ACTIVATED = "site_price_adjustment_activated"
    SITE_PRICE_ADJUSTMENT_DEACTIVATED = "site_price_adjustment_deactivated"

    # -------------------------------------------------------------------------
    # Agreement Actions
    # -------------------------------------------------------------------------
    AGREEMENT_CREATED = "agreement_created"
    AGREEMENT_TERMINATED = "agreement_terminated"

    # -------------------------------------------------------------------------
    # Settlement Actions (INV-4)
    # -------------------------------------------------------------------------
    SETTLEMENT_POSTED = "settlement_posted"
    REFUND_SETTLEMENT_POSTED = "refund_settlement_posted"
    SETTLEMENT_RUN_COMPLETED = "settlement_run_completed"


# =============================================================================
# Audit Adapter - Single Entry Point
# =============================================================================


def log_event(
    *,
    action: str,
    target,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
    sensitivity: str = "normal",
    is_system: bool = False,
):
    """Log an audit event for a DiveOps operation.

    This is the SINGLE entry point for all DiveOps audit events.
    It wraps django_audit_log.log() with consistent metadata extraction.

    IMPORTANT: This adapter is the ONLY place that imports django_audit_log.
    All domain code must use this function, never import django_audit_log directly.

    Args:
        action: One of the Actions.* constants (required)
        target: Model instance that is the target of the action (required)
        actor: Django User who performed the action (None for system events)
        data: Additional context dict (merged into metadata)
        changes: Dict of field changes: {"field": {"old": x, "new": y}}
        request: Optional HTTP request for IP/user-agent extraction
        sensitivity: normal/high/critical (default: normal)
        is_system: True if system action, not user-initiated (default: False)

    Returns:
        AuditLog instance

    Raises:
        Exceptions from django_audit_log are not caught - caller must handle.
        This is intentional: audit failures should be visible, not swallowed.

    Example:
        log_event(
            action=Actions.BOOKING_CREATED,
            target=booking,
            actor=request.user,
            data={
                "excursion_id": str(excursion.pk),
                "diver_id": str(diver.pk),
                "price": "100.00",
            },
        )
    """
    # Build metadata from data dict
    metadata = data or {}

    return audit_log(
        action=action,
        obj=target,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
        sensitivity=sensitivity,
        is_system=is_system,
    )


# =============================================================================
# Specialized Logging Functions
# =============================================================================
# These provide convenience and ensure consistent metadata for each domain.


def log_diver_event(
    action: str,
    diver,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a diver operation.

    Args:
        action: One of Actions.DIVER_* constants
        diver: DiverProfile instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_diver_metadata(diver, data)

    return audit_log(
        action=action,
        obj=diver,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_certification_event(
    action: str,
    certification,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a certification operation.

    Args:
        action: One of Actions.CERTIFICATION_* constants
        certification: DiverCertification instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_certification_metadata(certification, data)

    return audit_log(
        action=action,
        obj=certification,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_excursion_event(
    action: str,
    excursion,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for an excursion operation.

    Args:
        action: One of Actions.EXCURSION_* constants
        excursion: Excursion instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_excursion_metadata(excursion, data)

    return audit_log(
        action=action,
        obj=excursion,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_booking_event(
    action: str,
    booking,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a booking operation.

    Args:
        action: One of Actions.BOOKING_* or DIVER_* (roster) constants
        booking: Booking instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_booking_metadata(booking, data)

    return audit_log(
        action=action,
        obj=booking,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_roster_event(
    action: str,
    roster,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for a roster operation.

    Args:
        action: One of Actions.DIVER_CHECKED_IN, DIVER_NO_SHOW, etc.
        roster: TripRoster instance
        actor: Django User who performed the action
        data: Optional additional context
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_roster_metadata(roster, data)

    return audit_log(
        action=action,
        obj=roster,
        actor=actor,
        metadata=metadata,
        request=request,
    )


def log_eligibility_event(
    action: str,
    diver,
    excursion,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for an eligibility check/override.

    Args:
        action: One of Actions.ELIGIBILITY_* constants
        diver: DiverProfile being checked
        excursion: Excursion being checked against
        actor: Django User who performed the action
        data: Optional additional context (e.g., reasons, override justification)
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "diver_id": str(diver.pk),
        "diver_party_id": str(diver.person_id) if diver.person_id else None,
        "excursion_id": str(excursion.pk),
    }

    if data:
        metadata.update(data)

    # Log against the diver (primary subject of eligibility)
    return audit_log(
        action=action,
        obj=diver,
        actor=actor,
        metadata=metadata,
        request=request,
    )


def log_booking_override_event(
    override,
    actor=None,
    request=None,
):
    """Log an audit event for a booking eligibility override (INV-1).

    Args:
        override: EligibilityOverride instance
        actor: Django User who approved the override
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "booking_id": str(override.booking_id),
        "diver_id": str(override.diver_id),
        "requirement_type": override.requirement_type,
        "original_requirement": override.original_requirement,
        "reason": override.reason,
        "approved_by_id": str(override.approved_by_id),
    }

    return audit_log(
        action=Actions.BOOKING_ELIGIBILITY_OVERRIDDEN,
        obj=override.booking,
        actor=actor or override.approved_by,
        metadata=metadata,
        request=request,
    )


def log_trip_requirement_event(
    action: str,
    requirement,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for an excursion requirement operation.

    Args:
        action: One of Actions.EXCURSION_REQUIREMENT_* constants
        requirement: ExcursionRequirement instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "excursion_id": str(requirement.excursion_id),
        "requirement_type": requirement.requirement_type,
    }

    if requirement.certification_level_id:
        metadata["certification_level_id"] = str(requirement.certification_level_id)

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=requirement,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_dive_event(
    action: str,
    dive,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a dive operation.

    Args:
        action: One of Actions.DIVE_* constants
        dive: Dive instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_dive_metadata(dive, data)

    return audit_log(
        action=action,
        obj=dive,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_dive_template_event(
    action: str,
    dive_template,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for an excursion type dive template operation.

    Args:
        action: One of Actions.DIVE_TEMPLATE_* constants
        dive_template: ExcursionTypeDive instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_dive_template_metadata(dive_template, data)

    return audit_log(
        action=action,
        obj=dive_template,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_site_event(
    action: str,
    site,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a dive site operation.

    Args:
        action: One of Actions.DIVE_SITE_* constants
        site: DiveSite instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_site_metadata(site, data)

    return audit_log(
        action=action,
        obj=site,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_excursion_type_event(
    action: str,
    excursion_type,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for an excursion type operation.

    Args:
        action: One of Actions.EXCURSION_TYPE_* constants
        excursion_type: ExcursionType instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_excursion_type_metadata(excursion_type, data)

    return audit_log(
        action=action,
        obj=excursion_type,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_site_price_adjustment_event(
    action: str,
    adjustment,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a site price adjustment operation.

    Args:
        action: One of Actions.SITE_PRICE_ADJUSTMENT_* constants
        adjustment: SitePriceAdjustment instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_site_price_adjustment_metadata(adjustment, data)

    return audit_log(
        action=action,
        obj=adjustment,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


# =============================================================================
# Metadata Builders
# =============================================================================
# These ensure consistent metadata structure across all events.


def _build_diver_metadata(diver, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for diver audit events."""
    metadata = {
        "diver_id": str(diver.pk),
    }

    if diver.person_id:
        metadata["diver_party_id"] = str(diver.person_id)
        if diver.person:
            metadata["diver_name"] = f"{diver.person.first_name} {diver.person.last_name}"
            metadata["diver_email"] = diver.person.email

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_certification_metadata(certification, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for certification audit events."""
    metadata = {}

    if certification.diver_id:
        metadata["diver_id"] = str(certification.diver_id)

    if certification.level:
        metadata["level_id"] = str(certification.level_id)
        metadata["level_name"] = certification.level.name

        if certification.level.agency:
            metadata["agency_id"] = str(certification.level.agency_id)
            metadata["agency_name"] = certification.level.agency.name

    if certification.proof_document_id:
        metadata["document_id"] = str(certification.proof_document_id)

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_excursion_metadata(excursion, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for excursion audit events."""
    metadata = {
        "excursion_id": str(excursion.pk),
    }

    if excursion.dive_site_id:
        metadata["dive_site_id"] = str(excursion.dive_site_id)
        if excursion.dive_site:
            metadata["dive_site_name"] = excursion.dive_site.name

    if excursion.dive_shop_id:
        metadata["dive_shop_id"] = str(excursion.dive_shop_id)
        if excursion.dive_shop:
            metadata["dive_shop_name"] = excursion.dive_shop.name

    if excursion.departure_time:
        metadata["departure_time"] = excursion.departure_time.isoformat()

    if excursion.encounter_id:
        metadata["encounter_id"] = str(excursion.encounter_id)

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_booking_metadata(booking, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for booking audit events."""
    metadata = {
        "booking_id": str(booking.pk),
    }

    if booking.excursion_id:
        metadata["excursion_id"] = str(booking.excursion_id)

    if booking.diver_id:
        metadata["diver_id"] = str(booking.diver_id)
        if booking.diver and booking.diver.person:
            metadata["diver_party_id"] = str(booking.diver.person_id)

    if booking.invoice_id:
        metadata["invoice_id"] = str(booking.invoice_id)

    if booking.basket_id:
        metadata["basket_id"] = str(booking.basket_id)

    metadata["status"] = booking.status

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_roster_metadata(roster, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for roster audit events."""
    metadata = {
        "roster_id": str(roster.pk),
    }

    if roster.excursion_id:
        metadata["excursion_id"] = str(roster.excursion_id)

    if roster.diver_id:
        metadata["diver_id"] = str(roster.diver_id)
        if roster.diver and roster.diver.person:
            metadata["diver_party_id"] = str(roster.diver.person_id)

    if roster.booking_id:
        metadata["booking_id"] = str(roster.booking_id)

    if roster.role:
        metadata["role"] = roster.role

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_dive_metadata(dive, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for dive audit events."""
    metadata = {
        "dive_id": str(dive.pk),
        "sequence": dive.sequence,
    }

    if dive.excursion_id:
        metadata["excursion_id"] = str(dive.excursion_id)

    if dive.dive_site_id:
        metadata["dive_site_id"] = str(dive.dive_site_id)
        if dive.dive_site:
            metadata["dive_site_name"] = dive.dive_site.name

    if dive.planned_start:
        metadata["planned_start"] = dive.planned_start.isoformat()

    if dive.planned_duration_minutes:
        metadata["planned_duration_minutes"] = dive.planned_duration_minutes

    if dive.max_depth_meters:
        metadata["max_depth_meters"] = dive.max_depth_meters

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_dive_template_metadata(dive_template, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for excursion type dive template audit events."""
    metadata = {
        "dive_template_id": str(dive_template.pk),
        "sequence": dive_template.sequence,
        "name": dive_template.name,
    }

    if dive_template.excursion_type_id:
        metadata["excursion_type_id"] = str(dive_template.excursion_type_id)
        if dive_template.excursion_type:
            metadata["excursion_type_name"] = dive_template.excursion_type.name

    if dive_template.offset_minutes is not None:
        metadata["offset_minutes"] = dive_template.offset_minutes

    if dive_template.planned_duration_minutes:
        metadata["planned_duration_minutes"] = dive_template.planned_duration_minutes

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_site_metadata(site, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for dive site audit events."""
    metadata = {
        "site_id": str(site.pk),
        "site_name": site.name,
    }

    if site.place_id:
        metadata["place_id"] = str(site.place_id)
        if site.place:
            metadata["latitude"] = str(site.place.latitude)
            metadata["longitude"] = str(site.place.longitude)

    if site.min_certification_level_id:
        metadata["min_certification_level_id"] = str(site.min_certification_level_id)
        if site.min_certification_level:
            metadata["min_certification_level_name"] = site.min_certification_level.name

    if site.difficulty:
        metadata["difficulty"] = site.difficulty

    if site.max_depth_meters:
        metadata["max_depth_meters"] = site.max_depth_meters

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_excursion_type_metadata(excursion_type, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for excursion type audit events."""
    metadata = {
        "excursion_type_id": str(excursion_type.pk),
        "excursion_type_name": excursion_type.name,
        "dive_mode": excursion_type.dive_mode,
        "time_of_day": excursion_type.time_of_day,
        "is_active": excursion_type.is_active,
    }

    if excursion_type.base_price is not None:
        metadata["base_price"] = str(excursion_type.base_price)
        metadata["currency"] = excursion_type.currency

    if excursion_type.min_certification_level_id:
        metadata["min_certification_level_id"] = str(excursion_type.min_certification_level_id)
        if excursion_type.min_certification_level:
            metadata["min_certification_level_name"] = excursion_type.min_certification_level.name

    metadata["requires_cert"] = excursion_type.requires_cert
    metadata["is_training"] = excursion_type.is_training

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_site_price_adjustment_metadata(adjustment, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for site price adjustment audit events."""
    metadata = {
        "adjustment_id": str(adjustment.pk),
        "kind": adjustment.kind,
        "amount": str(adjustment.amount),
        "is_active": adjustment.is_active,
    }

    if adjustment.dive_site_id:
        metadata["dive_site_id"] = str(adjustment.dive_site_id)
        if adjustment.dive_site:
            metadata["dive_site_name"] = adjustment.dive_site.name

    if adjustment.applies_to_mode:
        metadata["applies_to_mode"] = adjustment.applies_to_mode

    if extra_data:
        metadata.update(extra_data)

    return metadata


def log_settlement_event(
    action: str,
    settlement,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for a settlement operation.

    Args:
        action: One of Actions.SETTLEMENT_* constants
        settlement: SettlementRecord instance
        actor: Django User who performed the action
        data: Optional additional context
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "settlement_id": str(settlement.pk),
        "booking_id": str(settlement.booking_id),
        "idempotency_key": settlement.idempotency_key,
        "settlement_type": settlement.settlement_type,
        "amount": str(settlement.amount),
        "currency": settlement.currency,
    }

    if settlement.transaction_id:
        metadata["transaction_id"] = str(settlement.transaction_id)

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=settlement,
        actor=actor,
        metadata=metadata,
        request=request,
    )
