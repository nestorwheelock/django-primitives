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
        data={"trip_id": str(trip.pk), "diver_id": str(diver.pk)},
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
    # Trip Actions
    # -------------------------------------------------------------------------
    TRIP_CREATED = "trip_created"
    TRIP_UPDATED = "trip_updated"
    TRIP_DELETED = "trip_deleted"
    TRIP_PUBLISHED = "trip_published"
    TRIP_CANCELLED = "trip_cancelled"
    TRIP_RESCHEDULED = "trip_rescheduled"
    TRIP_STARTED = "trip_started"
    TRIP_COMPLETED = "trip_completed"

    # -------------------------------------------------------------------------
    # Booking / Roster Actions
    # -------------------------------------------------------------------------
    BOOKING_CREATED = "booking_created"
    BOOKING_CANCELLED = "booking_cancelled"
    BOOKING_PAID = "booking_paid"
    BOOKING_REFUNDED = "booking_refunded"
    DIVER_CHECKED_IN = "diver_checked_in"
    DIVER_NO_SHOW = "diver_no_show"
    DIVER_COMPLETED_TRIP = "diver_completed_trip"
    DIVER_REMOVED_FROM_TRIP = "diver_removed_from_trip"

    # -------------------------------------------------------------------------
    # Eligibility / Override Actions
    # -------------------------------------------------------------------------
    ELIGIBILITY_CHECKED = "eligibility_checked"
    ELIGIBILITY_FAILED = "eligibility_failed"
    ELIGIBILITY_OVERRIDDEN = "eligibility_overridden"

    # -------------------------------------------------------------------------
    # Trip Requirement Actions
    # -------------------------------------------------------------------------
    TRIP_REQUIREMENT_ADDED = "trip_requirement_added"
    TRIP_REQUIREMENT_UPDATED = "trip_requirement_updated"
    TRIP_REQUIREMENT_REMOVED = "trip_requirement_removed"

    # -------------------------------------------------------------------------
    # Dive Site Actions
    # -------------------------------------------------------------------------
    DIVE_SITE_CREATED = "dive_site_created"
    DIVE_SITE_UPDATED = "dive_site_updated"
    DIVE_SITE_DELETED = "dive_site_deleted"


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
                "trip_id": str(trip.pk),
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


def log_trip_event(
    action: str,
    trip,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a trip operation.

    Args:
        action: One of Actions.TRIP_* constants
        trip: DiveTrip instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_trip_metadata(trip, data)

    return audit_log(
        action=action,
        obj=trip,
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
    trip,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for an eligibility check/override.

    Args:
        action: One of Actions.ELIGIBILITY_* constants
        diver: DiverProfile being checked
        trip: DiveTrip being checked against
        actor: Django User who performed the action
        data: Optional additional context (e.g., reasons, override justification)
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "diver_id": str(diver.pk),
        "diver_party_id": str(diver.person_id) if diver.person_id else None,
        "trip_id": str(trip.pk),
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


def log_trip_requirement_event(
    action: str,
    requirement,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a trip requirement operation.

    Args:
        action: One of Actions.TRIP_REQUIREMENT_* constants
        requirement: TripRequirement instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "trip_id": str(requirement.trip_id),
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


def _build_trip_metadata(trip, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for trip audit events."""
    metadata = {
        "trip_id": str(trip.pk),
    }

    if trip.dive_site_id:
        metadata["dive_site_id"] = str(trip.dive_site_id)
        if trip.dive_site:
            metadata["dive_site_name"] = trip.dive_site.name

    if trip.dive_shop_id:
        metadata["dive_shop_id"] = str(trip.dive_shop_id)
        if trip.dive_shop:
            metadata["dive_shop_name"] = trip.dive_shop.name

    if trip.departure_time:
        metadata["departure_time"] = trip.departure_time.isoformat()

    if trip.encounter_id:
        metadata["encounter_id"] = str(trip.encounter_id)

    if extra_data:
        metadata.update(extra_data)

    return metadata


def _build_booking_metadata(booking, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for booking audit events."""
    metadata = {
        "booking_id": str(booking.pk),
    }

    if booking.trip_id:
        metadata["trip_id"] = str(booking.trip_id)

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

    if roster.trip_id:
        metadata["trip_id"] = str(roster.trip_id)

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
