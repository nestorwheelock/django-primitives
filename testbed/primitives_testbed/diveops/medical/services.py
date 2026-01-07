"""DiveOps Medical Services.

Policy layer on top of django-questionnaires primitive.
Enforces diving-specific medical requirements.
"""

from datetime import date
from typing import Any

from django.db import models

from django_questionnaires.services import (
    get_current_instance,
    is_instance_valid,
    clear_instance as questionnaire_clear_instance,
    create_instance as questionnaire_create_instance,
)
from django_questionnaires.models import InstanceStatus

from ..audit import Actions, log_medical_questionnaire_event


class MedicalStatus(models.TextChoices):
    """Medical clearance status for divers."""

    CLEARED = "cleared", "Cleared"
    PENDING = "pending", "Pending Questionnaire"
    REQUIRES_CLEARANCE = "requires_clearance", "Requires Physician Clearance"
    EXPIRED = "expired", "Expired"
    NOT_STARTED = "not_started", "Not Started"


RSTC_MEDICAL_SLUG = "rstc-medical"


def get_diver_medical_status(diver: Any, as_of_date: date | None = None) -> MedicalStatus:
    """Check diver's medical questionnaire status.

    Args:
        diver: DiverProfile or similar model instance
        as_of_date: Date to check status for (defaults to today)

    Returns:
        MedicalStatus indicating current clearance status
    """
    instance = get_current_instance(respondent=diver, definition_slug=RSTC_MEDICAL_SLUG)

    if not instance:
        return MedicalStatus.NOT_STARTED

    # Check if expired
    if instance.is_expired:
        return MedicalStatus.EXPIRED

    # Check status
    if instance.status == InstanceStatus.PENDING:
        return MedicalStatus.PENDING

    if instance.status == InstanceStatus.FLAGGED:
        return MedicalStatus.REQUIRES_CLEARANCE

    if instance.status in [InstanceStatus.COMPLETED, InstanceStatus.CLEARED]:
        # Double-check validity
        if is_instance_valid(instance):
            return MedicalStatus.CLEARED
        return MedicalStatus.EXPIRED

    return MedicalStatus.PENDING


def can_diver_dive(diver: Any, excursion_date: date | None = None) -> tuple[bool, str]:
    """Check if diver can participate on excursion date.

    Args:
        diver: DiverProfile or similar model instance
        excursion_date: Date of the excursion (defaults to today)

    Returns:
        Tuple of (can_dive: bool, reason: str)
    """
    status = get_diver_medical_status(diver, excursion_date)

    if status == MedicalStatus.CLEARED:
        return True, ""

    reasons = {
        MedicalStatus.NOT_STARTED: "Medical questionnaire not completed",
        MedicalStatus.PENDING: "Medical questionnaire not submitted",
        MedicalStatus.REQUIRES_CLEARANCE: "Requires physician clearance",
        MedicalStatus.EXPIRED: "Medical clearance has expired",
    }

    return False, reasons.get(status, f"Medical status: {status.label}")


def send_medical_questionnaire(
    diver: Any,
    expires_in_days: int = 30,
    actor: Any = None,
):
    """Send a medical questionnaire to a diver.

    Creates a new questionnaire instance for the diver to fill out.

    Args:
        diver: DiverProfile or similar model instance
        expires_in_days: Days until questionnaire expires
        actor: User initiating the action

    Returns:
        QuestionnaireInstance
    """
    instance = questionnaire_create_instance(
        definition_slug=RSTC_MEDICAL_SLUG,
        respondent=diver,
        expires_in_days=expires_in_days,
        actor=actor,
    )

    # Log to audit trail
    log_medical_questionnaire_event(
        action=Actions.MEDICAL_QUESTIONNAIRE_SENT,
        instance=instance,
        actor=actor,
        data={"expires_in_days": expires_in_days},
    )

    return instance


def upload_physician_clearance(
    instance: Any,
    document: Any,
    cleared_by: Any,
    notes: str = "",
):
    """Attach physician clearance document and clear flagged instance.

    Args:
        instance: The flagged QuestionnaireInstance
        document: Document model instance (from django-documents)
        cleared_by: User performing the clearance
        notes: Optional clearance notes

    Returns:
        The cleared QuestionnaireInstance
    """
    cleared_instance = questionnaire_clear_instance(
        instance=instance,
        cleared_by=cleared_by,
        notes=notes,
        clearance_document=document,
    )

    # Log to audit trail
    log_medical_questionnaire_event(
        action=Actions.MEDICAL_QUESTIONNAIRE_CLEARED,
        instance=cleared_instance,
        actor=cleared_by,
        data={
            "clearance_notes": notes,
            "document_id": str(document.pk) if document else None,
        },
    )

    return cleared_instance


def get_diver_medical_instance(diver: Any):
    """Get the current medical questionnaire instance for a diver.

    Args:
        diver: DiverProfile or similar model instance

    Returns:
        QuestionnaireInstance or None
    """
    return get_current_instance(respondent=diver, definition_slug=RSTC_MEDICAL_SLUG)


def is_medical_valid(diver: Any, as_of_date: date | None = None) -> bool:
    """Check if diver has valid medical clearance.

    Convenience function that returns a simple boolean.

    Args:
        diver: DiverProfile or similar model instance
        as_of_date: Date to check (defaults to today)

    Returns:
        True if diver is cleared to dive, False otherwise
    """
    status = get_diver_medical_status(diver, as_of_date)
    return status == MedicalStatus.CLEARED
