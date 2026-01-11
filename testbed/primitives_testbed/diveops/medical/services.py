"""DiveOps Medical Services.

Policy layer on top of django-questionnaires primitive.
Enforces diving-specific medical requirements.
"""

from datetime import date
from typing import Any

from django.db import models

from django.contrib.contenttypes.models import ContentType

from django_questionnaires.services import (
    get_current_instance,
    is_instance_valid,
    clear_instance as questionnaire_clear_instance,
    create_instance as questionnaire_create_instance,
    void_instance as questionnaire_void_instance,
)
from django_questionnaires.models import InstanceStatus, QuestionnaireInstance

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
    canned_response: Any = None,
    custom_message: str | None = None,
):
    """Send a medical questionnaire to a diver.

    Creates a new questionnaire instance for the diver to fill out.
    Any existing pending (not yet submitted) instances are voided.
    Optionally includes a canned response or custom message in the conversation.

    Args:
        diver: DiverProfile or similar model instance
        expires_in_days: Days until questionnaire expires
        actor: User initiating the action
        canned_response: Optional CannedResponse to include
        custom_message: Optional custom message text

    Returns:
        QuestionnaireInstance
    """
    # Void any existing pending instances for this diver
    _void_pending_medical_instances(diver, actor)

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

    # Send message to customer conversation if provided
    if canned_response or custom_message:
        _send_medical_message_to_conversation(
            diver=diver,
            actor=actor,
            canned_response=canned_response,
            custom_message=custom_message,
        )

    return instance


def _send_medical_message_to_conversation(
    diver: Any,
    actor: Any,
    canned_response: Any = None,
    custom_message: str | None = None,
):
    """Send a message to the diver's conversation about medical questionnaire.

    Uses the flow thread system to find or create a conversation for the diver.
    """
    from ..services import _get_customer_active_conversation
    from ..selectors import get_staff_person

    if not diver.person:
        return

    # Try to find an existing conversation for this customer
    conversation = _get_customer_active_conversation(diver.person)

    if not conversation:
        # No existing conversation - we could create one here if needed
        # For now, skip if no conversation exists
        return

    # Build message text
    message_text = None
    if canned_response:
        from django_communication.services.canned_responses import (
            render_canned_response,
            get_context_for_conversation,
        )

        context = get_context_for_conversation(
            conversation=conversation,
            actor=actor,
            recipient=diver.person,
            extra={},
        )
        context.update({
            "customer_name": f"{diver.person.first_name} {diver.person.last_name}",
            "customer_first_name": diver.person.first_name,
        })
        message_text = render_canned_response(canned_response, context)
    elif custom_message:
        message_text = custom_message

    if message_text:
        from django_communication.services import send_in_conversation, send_system_message

        # Send system message about the questionnaire
        send_system_message(
            conversation=conversation,
            body_text="Medical questionnaire sent",
            event_type="medical_questionnaire_sent",
        )

        # Send the cover message from staff
        staff_person = get_staff_person(actor)
        if staff_person:
            send_in_conversation(
                conversation=conversation,
                sender_person=staff_person,
                body_text=message_text,
                direction="outbound",
            )


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


def get_diver_medical_context(diver: Any) -> dict:
    """Get medical instance and status in a single query.

    Optimized for views that need both - avoids duplicate queries.

    Args:
        diver: DiverProfile or similar model instance

    Returns:
        dict with 'instance' and 'status' keys
    """
    instance = get_current_instance(respondent=diver, definition_slug=RSTC_MEDICAL_SLUG)

    if not instance:
        return {"instance": None, "status": MedicalStatus.NOT_STARTED}

    if instance.is_expired:
        return {"instance": instance, "status": MedicalStatus.EXPIRED}

    if instance.status == InstanceStatus.PENDING:
        return {"instance": instance, "status": MedicalStatus.PENDING}

    if instance.status == InstanceStatus.FLAGGED:
        return {"instance": instance, "status": MedicalStatus.REQUIRES_CLEARANCE}

    if instance.status in [InstanceStatus.COMPLETED, InstanceStatus.CLEARED]:
        if is_instance_valid(instance):
            return {"instance": instance, "status": MedicalStatus.CLEARED}
        return {"instance": instance, "status": MedicalStatus.EXPIRED}

    return {"instance": instance, "status": MedicalStatus.PENDING}


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


def _void_pending_medical_instances(diver: Any, actor: Any = None) -> int:
    """Void all pending medical questionnaire instances for a diver.

    When sending a new questionnaire, any existing pending (not yet submitted)
    instances should be voided so they don't clutter the diver's queue.

    Uses select_for_update() to prevent race conditions when multiple
    requests try to void/create questionnaires concurrently.

    Args:
        diver: DiverProfile or similar model instance
        actor: User performing the action (for audit)

    Returns:
        Number of instances voided
    """
    from django.db import transaction

    content_type = ContentType.objects.get_for_model(diver)

    voided_count = 0

    with transaction.atomic():
        # Lock rows to prevent race condition on concurrent sends
        pending_instances = list(
            QuestionnaireInstance.objects.select_for_update().filter(
                definition__slug=RSTC_MEDICAL_SLUG,
                respondent_content_type=content_type,
                respondent_object_id=str(diver.pk),
                status=InstanceStatus.PENDING,
                deleted_at__isnull=True,
            )
        )

        for instance in pending_instances:
            questionnaire_void_instance(
                instance=instance,
                voided_by=actor,
                reason="Superseded by new questionnaire",
            )
            voided_count += 1

            # Log to audit trail
            log_medical_questionnaire_event(
                action=Actions.MEDICAL_QUESTIONNAIRE_VOIDED,
                instance=instance,
                actor=actor,
                data={"reason": "Superseded by new questionnaire"},
            )

    return voided_count
