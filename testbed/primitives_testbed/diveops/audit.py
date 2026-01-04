"""Audit logging adapter for diveops.

This module provides a thin adapter to django_audit_log for domain-specific audit events.
DiveOps emits audit events but does NOT store audit data locally - the django_audit_log
primitive owns persistence.

All domain code must call this adapter, not django_audit_log directly.
This ensures stable action strings and consistent metadata across the domain.

Usage:
    from diveops.audit import log_certification_event, Actions

    log_certification_event(
        action=Actions.CERTIFICATION_ADDED,
        certification=cert,
        actor=request.user,
        data={"reason": "Initial setup"},
    )
"""

from django_audit_log import log as audit_log


# =============================================================================
# Stable Action Constants
# =============================================================================
# These strings are part of the DiveOps audit contract.
# Changing them requires migration of existing audit data.


class Actions:
    """Stable audit action constants for certification operations.

    These are domain-specific action strings that provide semantic meaning
    beyond generic CRUD operations. They are stable and reusable across
    the system.
    """

    # Certification lifecycle
    CERTIFICATION_ADDED = "certification_added"
    CERTIFICATION_UPDATED = "certification_updated"
    CERTIFICATION_REMOVED = "certification_removed"

    # Certification verification workflow
    CERTIFICATION_VERIFIED = "certification_verified"
    CERTIFICATION_UNVERIFIED = "certification_unverified"


# =============================================================================
# Audit Adapter
# =============================================================================


def log_certification_event(
    action: str,
    certification,
    actor=None,
    data: dict | None = None,
    changes: dict | None = None,
    request=None,
):
    """Log an audit event for a certification operation.

    This is the single entry point for all certification-related audit events.
    It wraps django_audit_log.log() with consistent metadata extraction.

    Args:
        action: One of the Actions.CERTIFICATION_* constants
        certification: DiverCertification instance (target of the action)
        actor: Django User who performed the action (required for non-system events)
        data: Optional additional context dict (merged into metadata)
        changes: Optional dict of field changes: {"field": {"old": x, "new": y}}
        request: Optional HTTP request for IP/user-agent extraction

    Returns:
        AuditLog instance

    Raises:
        Exceptions from django_audit_log are not caught - caller must handle.
        This is intentional: audit failures should be visible, not swallowed.

    Example:
        log_certification_event(
            action=Actions.CERTIFICATION_ADDED,
            certification=cert,
            actor=request.user,
            data={"card_number": "12345"},
        )
    """
    # Build consistent metadata for certification events
    metadata = _build_certification_metadata(certification, data)

    return audit_log(
        action=action,
        obj=certification,
        actor=actor,
        changes=changes or {},
        metadata=metadata,
        request=request,
    )


def _build_certification_metadata(certification, extra_data: dict | None = None) -> dict:
    """Build consistent metadata for certification audit events.

    Always includes:
    - agency_id: UUID of the certification agency
    - agency_name: Human-readable agency name
    - level_id: UUID of the certification level
    - level_name: Human-readable level name
    - diver_id: UUID of the diver profile

    Args:
        certification: DiverCertification instance
        extra_data: Optional additional data to merge

    Returns:
        Metadata dict for audit log
    """
    metadata = {}

    # Always include identifiers for data integrity
    if certification.level:
        metadata["level_id"] = str(certification.level_id)
        metadata["level_name"] = certification.level.name

        if certification.level.agency:
            metadata["agency_id"] = str(certification.level.agency_id)
            metadata["agency_name"] = certification.level.agency.name

    if certification.diver_id:
        metadata["diver_id"] = str(certification.diver_id)

    # Merge any extra data provided by caller
    if extra_data:
        metadata.update(extra_data)

    return metadata
