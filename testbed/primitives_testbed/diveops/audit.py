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
    DIVE_LOGGED = "dive_logged"

    # -------------------------------------------------------------------------
    # Dive Assignment Actions (diver status during dive)
    # -------------------------------------------------------------------------
    DIVER_STATUS_CHANGED = "diver_status_changed"

    # -------------------------------------------------------------------------
    # Dive Log Actions (personal dive records)
    # -------------------------------------------------------------------------
    DIVE_LOG_VERIFIED = "dive_log_verified"
    DIVE_LOG_UPDATED = "dive_log_updated"

    # -------------------------------------------------------------------------
    # Dive Template Actions (ExcursionTypeDive - product configuration)
    # -------------------------------------------------------------------------
    DIVE_TEMPLATE_CREATED = "dive_template_created"
    DIVE_TEMPLATE_UPDATED = "dive_template_updated"
    DIVE_TEMPLATE_DELETED = "dive_template_deleted"

    # -------------------------------------------------------------------------
    # Dive Template Lifecycle Actions (publish/retire)
    # -------------------------------------------------------------------------
    DIVE_TEMPLATE_PUBLISHED = "dive_template_published"
    DIVE_TEMPLATE_RETIRED = "dive_template_retired"

    # -------------------------------------------------------------------------
    # Dive Plan Locking Actions
    # -------------------------------------------------------------------------
    DIVE_PLAN_LOCKED = "dive_plan_locked"
    DIVE_PLAN_RESNAPSHOTTED = "dive_plan_resnapshotted"
    EXCURSION_PLANS_LOCKED = "excursion_plans_locked"

    # -------------------------------------------------------------------------
    # Dive Plan Decompression Validation Actions
    # -------------------------------------------------------------------------
    DIVE_PLAN_VALIDATED = "dive_plan_validated"
    DIVE_PLAN_VALIDATION_FAILED = "dive_plan_validation_failed"

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
    # Agreement Actions (SignableAgreement workflow)
    # -------------------------------------------------------------------------
    AGREEMENT_CREATED = "agreement_created"
    AGREEMENT_EDITED = "agreement_edited"
    AGREEMENT_SENT = "agreement_sent"
    AGREEMENT_SIGNED = "agreement_signed"
    AGREEMENT_VOIDED = "agreement_voided"
    AGREEMENT_EXPIRED = "agreement_expired"
    # Legacy - for django-agreements ledger
    AGREEMENT_AMENDED = "agreement_amended"
    AGREEMENT_TERMINATED = "agreement_terminated"

    # -------------------------------------------------------------------------
    # Agreement Template Actions (Paperwork)
    # -------------------------------------------------------------------------
    AGREEMENT_TEMPLATE_CREATED = "agreement_template_created"
    AGREEMENT_TEMPLATE_UPDATED = "agreement_template_updated"
    AGREEMENT_TEMPLATE_PUBLISHED = "agreement_template_published"
    AGREEMENT_TEMPLATE_ARCHIVED = "agreement_template_archived"
    AGREEMENT_TEMPLATE_DELETED = "agreement_template_deleted"

    # -------------------------------------------------------------------------
    # Settlement Actions (INV-4)
    # -------------------------------------------------------------------------
    SETTLEMENT_POSTED = "settlement_posted"
    REFUND_SETTLEMENT_POSTED = "refund_settlement_posted"
    SETTLEMENT_RUN_COMPLETED = "settlement_run_completed"

    # -------------------------------------------------------------------------
    # Pricing Actions
    # -------------------------------------------------------------------------
    EXCURSION_QUOTE_GENERATED = "excursion_quote_generated"
    BOOKING_PRICING_SNAPSHOTTED = "booking_pricing_snapshotted"
    DIVER_EQUIPMENT_RENTED = "diver_equipment_rented"
    PRICING_VALIDATION_FAILED = "pricing_validation_failed"

    # -------------------------------------------------------------------------
    # Catalog Item Actions
    # -------------------------------------------------------------------------
    CATALOG_ITEM_CREATED = "catalog_item_created"
    CATALOG_ITEM_UPDATED = "catalog_item_updated"
    CATALOG_ITEM_DELETED = "catalog_item_deleted"

    # -------------------------------------------------------------------------
    # Catalog Component Actions (Assembly/BOM)
    # -------------------------------------------------------------------------
    CATALOG_COMPONENT_ADDED = "catalog_component_added"
    CATALOG_COMPONENT_UPDATED = "catalog_component_updated"
    CATALOG_COMPONENT_REMOVED = "catalog_component_removed"

    # -------------------------------------------------------------------------
    # Price Rule Actions
    # -------------------------------------------------------------------------
    PRICE_RULE_CREATED = "price_rule_created"
    PRICE_RULE_UPDATED = "price_rule_updated"
    PRICE_RULE_DELETED = "price_rule_deleted"

    # -------------------------------------------------------------------------
    # Payables Actions
    # -------------------------------------------------------------------------
    VENDOR_INVOICE_RECORDED = "vendor_invoice_recorded"
    VENDOR_PAYMENT_RECORDED = "vendor_payment_recorded"

    # -------------------------------------------------------------------------
    # Account Actions
    # Note: Accounts cannot be deleted, only deactivated (accounting standard)
    # -------------------------------------------------------------------------
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_UPDATED = "account_updated"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    ACCOUNT_REACTIVATED = "account_reactivated"
    ACCOUNTS_SEEDED = "accounts_seeded"

    # -------------------------------------------------------------------------
    # Marine Park Actions
    # -------------------------------------------------------------------------
    PARK_CREATED = "park_created"
    PARK_UPDATED = "park_updated"
    PARK_DELETED = "park_deleted"

    # -------------------------------------------------------------------------
    # Park Zone Actions
    # -------------------------------------------------------------------------
    PARK_ZONE_CREATED = "park_zone_created"
    PARK_ZONE_UPDATED = "park_zone_updated"
    PARK_ZONE_DELETED = "park_zone_deleted"

    # -------------------------------------------------------------------------
    # Park Rule Actions
    # -------------------------------------------------------------------------
    PARK_RULE_CREATED = "park_rule_created"
    PARK_RULE_UPDATED = "park_rule_updated"
    PARK_RULE_DELETED = "park_rule_deleted"

    # -------------------------------------------------------------------------
    # Park Fee Actions
    # -------------------------------------------------------------------------
    PARK_FEE_SCHEDULE_CREATED = "park_fee_schedule_created"
    PARK_FEE_SCHEDULE_UPDATED = "park_fee_schedule_updated"
    PARK_FEE_SCHEDULE_DELETED = "park_fee_schedule_deleted"
    PARK_FEE_TIER_CREATED = "park_fee_tier_created"
    PARK_FEE_TIER_UPDATED = "park_fee_tier_updated"
    PARK_FEE_TIER_DELETED = "park_fee_tier_deleted"

    # -------------------------------------------------------------------------
    # Park Guide Credential Actions
    # -------------------------------------------------------------------------
    PARK_GUIDE_CREDENTIAL_ISSUED = "park_guide_credential_issued"
    PARK_GUIDE_CREDENTIAL_UPDATED = "park_guide_credential_updated"
    PARK_GUIDE_CREDENTIAL_SUSPENDED = "park_guide_credential_suspended"
    PARK_GUIDE_CREDENTIAL_REVOKED = "park_guide_credential_revoked"
    PARK_GUIDE_REFRESHER_COMPLETED = "park_guide_refresher_completed"

    # -------------------------------------------------------------------------
    # Vessel Permit Actions
    # -------------------------------------------------------------------------
    VESSEL_PERMIT_ISSUED = "vessel_permit_issued"
    VESSEL_PERMIT_UPDATED = "vessel_permit_updated"
    VESSEL_PERMIT_REVOKED = "vessel_permit_revoked"
    VESSEL_PERMIT_EXPIRED = "vessel_permit_expired"

    # -------------------------------------------------------------------------
    # Diver Eligibility Proof Actions
    # -------------------------------------------------------------------------
    DIVER_PROOF_SUBMITTED = "diver_proof_submitted"
    DIVER_PROOF_VERIFIED = "diver_proof_verified"
    DIVER_PROOF_REJECTED = "diver_proof_rejected"

    # -------------------------------------------------------------------------
    # Photo Tag Actions
    # -------------------------------------------------------------------------
    PHOTO_DIVER_TAGGED = "photo_diver_tagged"
    PHOTO_DIVER_UNTAGGED = "photo_diver_untagged"

    # -------------------------------------------------------------------------
    # Media Link Actions
    # -------------------------------------------------------------------------
    MEDIA_LINKED_TO_EXCURSION = "media_linked_to_excursion"
    MEDIA_UNLINKED_FROM_EXCURSION = "media_unlinked_from_excursion"
    MEDIA_LINKED_DIRECT = "media_linked_direct"
    MEDIA_UNLINKED_DIRECT = "media_unlinked_direct"

    # -------------------------------------------------------------------------
    # Diver Staff Note Actions
    # -------------------------------------------------------------------------
    DIVER_NOTE_ADDED = "diver_note_added"
    DIVER_NOTE_DELETED = "diver_note_deleted"

    # -------------------------------------------------------------------------
    # Diver Document Actions
    # -------------------------------------------------------------------------
    DIVER_DOCUMENT_UPLOADED = "diver_document_uploaded"
    DIVER_DOCUMENT_DELETED = "diver_document_deleted"

    # -------------------------------------------------------------------------
    # Medical Questionnaire Actions
    # -------------------------------------------------------------------------
    MEDICAL_QUESTIONNAIRE_SENT = "medical_questionnaire_sent"
    MEDICAL_QUESTIONNAIRE_COMPLETED = "medical_questionnaire_completed"
    MEDICAL_QUESTIONNAIRE_FLAGGED = "medical_questionnaire_flagged"
    MEDICAL_QUESTIONNAIRE_CLEARED = "medical_questionnaire_cleared"
    MEDICAL_QUESTIONNAIRE_EXPIRED = "medical_questionnaire_expired"


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
        roster: ExcursionRoster instance
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


def log_dive_assignment_event(
    action: str,
    assignment,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a dive assignment operation.

    Args:
        action: One of Actions.DIVER_STATUS_* constants
        assignment: DiveAssignment instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "assignment_id": str(assignment.pk),
        "dive_id": str(assignment.dive_id),
        "diver_id": str(assignment.diver_id),
        "status": assignment.status,
        "role": assignment.role,
    }

    if assignment.diver and assignment.diver.person:
        metadata["diver_name"] = assignment.diver.person.get_full_name()

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=assignment,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_dive_log_event(
    action: str,
    dive_log,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a dive log operation.

    Args:
        action: One of Actions.DIVE_LOG_* constants
        dive_log: DiveLog instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "dive_log_id": str(dive_log.pk),
        "dive_id": str(dive_log.dive_id),
        "diver_id": str(dive_log.diver_id),
    }

    if dive_log.dive_number:
        metadata["dive_number"] = dive_log.dive_number

    if dive_log.diver and dive_log.diver.person:
        metadata["diver_name"] = dive_log.diver.person.get_full_name()

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=dive_log,
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

    # Record linked excursion types (M2M relationship)
    excursion_types = list(dive_template.excursion_types.values_list("pk", "name"))
    if excursion_types:
        metadata["excursion_type_ids"] = [str(pk) for pk, _ in excursion_types]
        metadata["excursion_type_names"] = [name for _, name in excursion_types]

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


def log_pricing_event(
    action: str,
    target,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for a pricing operation.

    Args:
        action: One of Actions.EXCURSION_QUOTE_GENERATED, BOOKING_PRICING_SNAPSHOTTED,
                DIVER_EQUIPMENT_RENTED, or PRICING_VALIDATION_FAILED
        target: Model instance (Excursion, Booking, or DiverEquipmentRental)
        actor: Django User who performed the action
        data: Optional additional context (pricing details, amounts, etc.)
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = data or {}

    return audit_log(
        action=action,
        obj=target,
        actor=actor,
        metadata=metadata,
        request=request,
    )


def log_price_rule_event(
    action: str,
    price,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a price rule operation.

    Args:
        action: One of Actions.PRICE_RULE_* constants
        price: Price instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_price_rule_metadata(price, data)

    return audit_log(
        action=action,
        obj=price,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def _build_price_rule_metadata(price, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for price rule audit events."""
    metadata = {
        "price_id": str(price.pk),
        "amount": str(price.amount),
        "currency": price.currency,
    }

    if price.catalog_item_id:
        metadata["catalog_item_id"] = str(price.catalog_item_id)
        if price.catalog_item:
            metadata["catalog_item_name"] = price.catalog_item.display_name

    if price.cost_amount is not None:
        metadata["cost_amount"] = str(price.cost_amount)
        metadata["cost_currency"] = price.cost_currency

    # Scope information
    if price.organization_id:
        metadata["scope_type"] = "organization"
        metadata["organization_id"] = str(price.organization_id)
        if price.organization:
            metadata["organization_name"] = price.organization.name
    elif price.party_id:
        metadata["scope_type"] = "party"
        metadata["party_id"] = str(price.party_id)
    elif price.agreement_id:
        metadata["scope_type"] = "agreement"
        metadata["agreement_id"] = str(price.agreement_id)
    else:
        metadata["scope_type"] = "global"

    if price.valid_from:
        metadata["valid_from"] = price.valid_from.isoformat()

    if price.valid_to:
        metadata["valid_to"] = price.valid_to.isoformat()

    metadata["priority"] = price.priority

    if extra_data:
        metadata.update(extra_data)

    return metadata


def log_agreement_event(
    action: str,
    agreement,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for an agreement operation.

    Args:
        action: One of Actions.AGREEMENT_* constants
        agreement: Agreement instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = _build_agreement_metadata(agreement, data)

    return audit_log(
        action=action,
        obj=agreement,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def _build_agreement_metadata(agreement, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for agreement audit events."""
    metadata = {
        "agreement_id": str(agreement.pk),
        "scope_type": agreement.scope_type,
        "current_version": agreement.current_version,
        "is_active": agreement.is_active,
    }

    if agreement.party_a_id:
        metadata["party_a_id"] = str(agreement.party_a_id)
        metadata["party_a_type"] = agreement.party_a_content_type.model if agreement.party_a_content_type else None

    if agreement.party_b_id:
        metadata["party_b_id"] = str(agreement.party_b_id)
        metadata["party_b_type"] = agreement.party_b_content_type.model if agreement.party_b_content_type else None

    if agreement.valid_from:
        metadata["valid_from"] = agreement.valid_from.isoformat()

    if agreement.valid_to:
        metadata["valid_to"] = agreement.valid_to.isoformat()

    if agreement.agreed_at:
        metadata["agreed_at"] = agreement.agreed_at.isoformat()

    if extra_data:
        metadata.update(extra_data)

    return metadata


# =============================================================================
# Protected Area Logging Functions
# =============================================================================


def log_protected_area_event(
    action: str,
    protected_area,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a protected area operation.

    Args:
        action: One of Actions.PARK_* constants
        protected_area: ProtectedArea instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "protected_area_id": str(protected_area.pk),
        "protected_area_name": protected_area.name,
        "protected_area_code": protected_area.code,
        "designation_type": protected_area.designation_type,
        "is_active": protected_area.is_active,
    }

    if protected_area.parent_id:
        metadata["parent_id"] = str(protected_area.parent_id)

    if protected_area.governing_authority:
        metadata["governing_authority"] = protected_area.governing_authority

    if protected_area.place_id:
        metadata["place_id"] = str(protected_area.place_id)

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=protected_area,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


# Backwards compatibility alias
log_marine_park_event = log_protected_area_event


def log_protected_area_zone_event(
    action: str,
    zone,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a protected area zone operation.

    Args:
        action: One of Actions.PARK_ZONE_* constants
        zone: ProtectedAreaZone instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "zone_id": str(zone.pk),
        "zone_name": zone.name,
        "zone_code": zone.code,
        "zone_type": zone.zone_type,
        "protected_area_id": str(zone.protected_area_id),
        "is_active": zone.is_active,
    }

    if zone.protected_area:
        metadata["protected_area_name"] = zone.protected_area.name

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=zone,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


# Backwards compatibility alias
log_park_zone_event = log_protected_area_zone_event


def log_protected_area_rule_event(
    action: str,
    rule,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a protected area rule operation.

    Args:
        action: One of Actions.PARK_RULE_* constants
        rule: ProtectedAreaRule instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "rule_id": str(rule.pk),
        "rule_type": rule.rule_type,
        "subject": rule.subject,
        "activity": rule.activity,
        "enforcement_level": rule.enforcement_level,
        "protected_area_id": str(rule.protected_area_id),
        "effective_start": rule.effective_start.isoformat() if rule.effective_start else None,
    }

    if rule.zone_id:
        metadata["zone_id"] = str(rule.zone_id)

    if rule.effective_end:
        metadata["effective_end"] = rule.effective_end.isoformat()

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=rule,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


# Backwards compatibility alias
log_park_rule_event = log_protected_area_rule_event


def log_protected_area_guide_credential_event(
    action: str,
    credential,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a guide permit/credential operation.

    Args:
        action: One of Actions.PARK_GUIDE_CREDENTIAL_* constants
        credential: ProtectedAreaPermit (type=GUIDE) or legacy credential object
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "credential_id": str(credential.pk),
        "diver_id": str(credential.diver_id),
        "protected_area_id": str(credential.protected_area_id),
        "is_active": credential.is_active,
        "issued_at": credential.issued_at.isoformat() if credential.issued_at else None,
    }

    if credential.protected_area:
        metadata["protected_area_name"] = credential.protected_area.name

    if credential.credential_number:
        metadata["credential_number"] = credential.credential_number

    if credential.expires_at:
        metadata["expires_at"] = credential.expires_at.isoformat()

    if credential.diver and credential.diver.person:
        metadata["diver_name"] = credential.diver.person.get_full_name()

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=credential,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


# Backwards compatibility alias
log_guide_credential_event = log_protected_area_guide_credential_event


def log_vessel_permit_event(
    action: str,
    permit,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a vessel permit operation.

    Args:
        action: One of Actions.VESSEL_PERMIT_* constants
        permit: ProtectedAreaPermit (type=VESSEL) or legacy VesselPermit object
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "permit_id": str(permit.pk),
        "vessel_name": permit.vessel_name,
        "permit_number": permit.permit_number,
        "protected_area_id": str(permit.protected_area_id),
        "operator_id": str(permit.operator_id),
        "is_active": permit.is_active,
        "issued_at": permit.issued_at.isoformat() if permit.issued_at else None,
        "expires_at": permit.expires_at.isoformat() if permit.expires_at else None,
    }

    if permit.protected_area:
        metadata["protected_area_name"] = permit.protected_area.name

    if permit.operator:
        metadata["operator_name"] = permit.operator.name

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=permit,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_eligibility_proof_event(
    action: str,
    proof,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a diver eligibility proof operation.

    Args:
        action: One of Actions.DIVER_PROOF_* constants
        proof: DiverEligibilityProof instance
        actor: Django User who performed the action
        data: Optional additional context
        changes: Optional field changes
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "proof_id": str(proof.pk),
        "diver_id": str(proof.diver_id),
        "proof_type": proof.proof_type,
        "status": proof.status,
    }

    if proof.diver and proof.diver.person:
        metadata["diver_name"] = proof.diver.person.get_full_name()

    if proof.verified_by_id:
        metadata["verified_by_id"] = str(proof.verified_by_id)

    if proof.verified_at:
        metadata["verified_at"] = proof.verified_at.isoformat()

    if proof.expires_at:
        metadata["expires_at"] = proof.expires_at.isoformat()

    if proof.rejection_reason:
        metadata["rejection_reason"] = proof.rejection_reason

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=proof,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def log_photo_tag_event(
    action: str,
    photo_tag,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for a photo tag operation.

    Args:
        action: One of Actions.PHOTO_DIVER_TAGGED or PHOTO_DIVER_UNTAGGED
        photo_tag: PhotoTag instance
        actor: Django User who performed the action
        data: Optional additional context
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "photo_tag_id": str(photo_tag.pk),
        "document_id": str(photo_tag.document_id),
        "diver_id": str(photo_tag.diver_id),
    }

    if photo_tag.document:
        metadata["document_filename"] = photo_tag.document.filename

    if photo_tag.diver and photo_tag.diver.person:
        metadata["diver_name"] = photo_tag.diver.person.get_full_name()

    if photo_tag.tagged_by_id:
        metadata["tagged_by_id"] = str(photo_tag.tagged_by_id)

    if data:
        metadata.update(data)

    # Log against the document (primary subject of photo tagging)
    return audit_log(
        action=action,
        obj=photo_tag.document,
        actor=actor,
        changes={},
        metadata=metadata,
        request=request,
    )


def log_medical_questionnaire_event(
    action: str,
    instance,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for a medical questionnaire operation.

    Args:
        action: One of Actions.MEDICAL_QUESTIONNAIRE_* constants
        instance: QuestionnaireInstance from django_questionnaires
        actor: Django User who performed the action (None for public submissions)
        data: Optional additional context
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "questionnaire_instance_id": str(instance.pk),
        "definition_slug": instance.definition.slug if instance.definition else None,
        "definition_name": instance.definition.name if instance.definition else None,
        "status": instance.status,
    }

    # Get respondent info (DiverProfile)
    respondent = instance.respondent
    if respondent:
        metadata["diver_id"] = str(respondent.pk)
        if hasattr(respondent, "person") and respondent.person:
            metadata["diver_name"] = f"{respondent.person.first_name} {respondent.person.last_name}"

    if instance.completed_at:
        metadata["completed_at"] = instance.completed_at.isoformat()

    if instance.flagged_at:
        metadata["flagged_at"] = instance.flagged_at.isoformat()

    if instance.cleared_at:
        metadata["cleared_at"] = instance.cleared_at.isoformat()

    if instance.cleared_by_id:
        metadata["cleared_by_id"] = str(instance.cleared_by_id)

    if instance.expires_at:
        metadata["expires_at"] = instance.expires_at.isoformat()

    if data:
        metadata.update(data)

    # Log against the respondent (diver) if available, otherwise the instance
    target = respondent if respondent else instance

    return audit_log(
        action=action,
        obj=target,
        actor=actor,
        metadata=metadata,
        request=request,
    )


def log_diver_note_event(
    action: str,
    note,
    diver,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for a diver staff note operation.

    Args:
        action: One of Actions.DIVER_NOTE_ADDED or DIVER_NOTE_DELETED
        note: Note instance from django_notes
        diver: DiverProfile instance
        actor: Django User who performed the action
        data: Optional additional context
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "note_id": str(note.pk),
        "diver_id": str(diver.pk),
        "visibility": note.visibility,
    }

    if hasattr(diver, "person") and diver.person:
        metadata["diver_name"] = f"{diver.person.first_name} {diver.person.last_name}"

    if note.author_id:
        metadata["author_id"] = str(note.author_id)

    # Include content preview (first 100 chars)
    if note.content:
        metadata["content_preview"] = note.content[:100]

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=diver,
        actor=actor,
        metadata=metadata,
        request=request,
    )


def log_diver_document_event(
    action: str,
    document,
    diver,
    actor=None,
    data: dict | None = None,
    request=None,
):
    """Log an audit event for a diver document operation.

    Args:
        action: One of Actions.DIVER_DOCUMENT_UPLOADED or DIVER_DOCUMENT_DELETED
        document: Document instance from django_documents
        diver: DiverProfile instance
        actor: Django User who performed the action
        data: Optional additional context
        request: Optional HTTP request

    Returns:
        AuditLog instance
    """
    metadata = {
        "document_id": str(document.pk),
        "diver_id": str(diver.pk),
        "filename": document.filename,
        "document_type": document.document_type,
        "content_type": document.content_type,
        "file_size": document.file_size,
    }

    if hasattr(diver, "person") and diver.person:
        metadata["diver_name"] = f"{diver.person.first_name} {diver.person.last_name}"

    if document.description:
        metadata["description"] = document.description

    if data:
        metadata.update(data)

    return audit_log(
        action=action,
        obj=diver,
        actor=actor,
        metadata=metadata,
        request=request,
    )
