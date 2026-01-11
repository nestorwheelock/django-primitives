"""MessageOrchestrator - unified event-driven communication service.

The orchestrator is the single choke point for all outbound communications.
It handles:
- Event-to-template resolution
- Recipient address resolution
- Channel selection
- Template rendering with context providers
- Message creation and delivery
- Audit logging

Usage:
    from django_communication.services.orchestrator import orchestrate

    # Send notification for an event
    messages = orchestrate(
        event_type="class.signup.started",
        subject=customer_person,
        context={
            "class_name": "Open Water Diver",
            "class_date": "March 15, 2025",
        },
    )

    # With conversation attachment
    messages = orchestrate(
        event_type="conversation.new_message",
        actor=staff_person,
        subject=customer_person,
        context={"message_preview": "..."},
        conversation=conversation,
    )
"""

import logging
from typing import Any

from django.conf import settings
from django.template import Context, Template
from django.utils.module_loading import import_string

from ..models import (
    Channel,
    Conversation,
    Message,
    MessageDirection,
    MessageStatus,
    MessageTemplate,
)
from ..routing import get_channel_for_message, get_provider_for_channel
from .messaging import _get_from_address, ResolvedIdentity

logger = logging.getLogger(__name__)


def orchestrate(
    *,
    event_type: str,
    subject,
    actor=None,
    context: dict[str, Any] | None = None,
    conversation: Conversation | None = None,
) -> list[Message]:
    """Orchestrate communication for an event.

    This is the main entry point for event-driven messaging.
    Other apps should call this instead of sending messages directly.

    Args:
        event_type: Event identifier (e.g., 'class.signup.started')
        subject: Person who is the subject of the message (recipient)
        actor: Optional Person who triggered the event (staff/system)
        context: Template context variables
        conversation: Optional Conversation to attach message to

    Returns:
        List of Message instances created (may be empty if no template matches)

    Example:
        messages = orchestrate(
            event_type="booking.confirmed",
            subject=customer,
            context={"booking_ref": "BK-123", "date": "March 15"},
        )
    """
    context = context or {}
    messages = []

    # 1. Find template(s) for this event
    templates = MessageTemplate.objects.filter(
        event_type=event_type,
        is_active=True,
    )

    if not templates.exists():
        logger.debug("No active template found for event_type: %s", event_type)
        return []

    # 2. Get merged context from providers
    full_context = _get_merged_context(
        subject=subject,
        actor=actor,
        conversation=conversation,
        extra=context,
    )

    # 3. Process each matching template
    for template in templates:
        msg = _send_for_template(
            template=template,
            subject=subject,
            actor=actor,
            context=full_context,
            conversation=conversation,
        )
        if msg:
            messages.append(msg)

    return messages


def _get_merged_context(
    *,
    subject=None,
    actor=None,
    conversation=None,
    extra: dict | None = None,
) -> dict[str, Any]:
    """Build merged context from all providers.

    Calls configured COMMUNICATION_CONTEXT_PROVIDERS in order,
    merging results. Later providers override earlier ones.
    """
    context = {}

    # Get configured providers
    provider_paths = getattr(
        settings,
        "COMMUNICATION_CONTEXT_PROVIDERS",
        [],
    )

    for path in provider_paths:
        try:
            provider = import_string(path)
            provider_context = provider(
                subject=subject,
                actor=actor,
                conversation=conversation,
                extra=extra or {},
            )
            if provider_context:
                context.update(provider_context)
        except Exception as e:
            logger.warning("Error calling context provider %s: %s", path, e)

    # Add extra context last (highest priority)
    if extra:
        context.update(extra)

    return context


def _send_for_template(
    *,
    template: MessageTemplate,
    subject,
    actor=None,
    context: dict[str, Any],
    conversation: Conversation | None = None,
) -> Message | None:
    """Send a message using a specific template.

    Returns Message if successful, None if skipped (e.g., no valid address).
    """
    from ..models import CommunicationSettings

    # Get settings
    try:
        comm_settings = CommunicationSettings.objects.first()
    except Exception:
        comm_settings = None

    if not comm_settings:
        logger.warning("No CommunicationSettings found, cannot send")
        return None

    # Determine channel
    channel_preference = context.get("channel_preference")
    if channel_preference:
        channel = channel_preference
    else:
        channel = get_channel_for_message(
            message_type=template.message_type,
            settings=comm_settings,
        )

    # Check if template has content for this channel
    if channel == "email" and not template.has_email_content():
        logger.debug("Template %s has no email content", template.key)
        return None
    if channel == "sms" and not template.has_sms_content():
        logger.debug("Template %s has no SMS content", template.key)
        return None

    # Get recipient address
    to_address = _get_recipient_address(subject, channel)
    if not to_address:
        logger.warning(
            "Subject %s has no valid address for channel %s",
            subject.pk if subject else "None",
            channel,
        )
        return None

    # Render content
    rendered = _render_template_content(template, context, channel)

    # Resolve sender identity
    identity = _get_from_address(channel, comm_settings, recipient=subject)
    if isinstance(identity, ResolvedIdentity):
        from_address = identity.from_address
        reply_to = identity.reply_to
        profile = identity.profile
    else:
        from_address = identity
        reply_to = None
        profile = None

    # Create message
    message = Message.objects.create(
        conversation=conversation,
        sender_person=actor,
        direction=MessageDirection.OUTBOUND,
        channel=channel,
        message_type=template.message_type,
        from_address=from_address,
        to_address=to_address,
        reply_to=reply_to or "",
        subject=rendered.get("subject", ""),
        body_text=rendered.get("body_text", ""),
        body_html=rendered.get("body_html", ""),
        template=template,
        profile=profile,
        status=MessageStatus.QUEUED,
    )

    # Send via provider
    try:
        provider = get_provider_for_channel(channel, comm_settings)
        result = provider.send(message)

        if result.success:
            message.mark_sent(result.provider, result.message_id)
        else:
            message.mark_failed(result.error, result.provider)
    except Exception as e:
        logger.exception("Error sending message %s: %s", message.pk, e)
        message.mark_failed(str(e))

    return message


def _get_recipient_address(subject, channel: str) -> str | None:
    """Get the appropriate address for a recipient and channel.

    Args:
        subject: Person receiving the message
        channel: Communication channel (email, sms, etc.)

    Returns:
        Address string or None if not available
    """
    if not subject:
        return None

    if channel == "email":
        return getattr(subject, "email", None) or None
    elif channel == "sms":
        return getattr(subject, "phone", None) or None
    elif channel == "push":
        # For push, we'd need to look up PushSubscription
        # Return None for now - push has its own handling
        return None
    elif channel == "in_app":
        # In-app doesn't need an external address
        return getattr(subject, "email", None) or "in_app"

    return None


def _render_template_content(
    template: MessageTemplate,
    context: dict[str, Any],
    channel: str,
) -> dict[str, str]:
    """Render template content for a specific channel.

    Returns dict with subject, body_text, body_html as appropriate.
    """
    result = {}

    try:
        if channel == "email":
            if template.email_subject:
                result["subject"] = Template(template.email_subject).render(Context(context))
            if template.email_body_text:
                result["body_text"] = Template(template.email_body_text).render(Context(context))
            if template.email_body_html:
                result["body_html"] = Template(template.email_body_html).render(Context(context))
        elif channel == "sms":
            if template.sms_body:
                result["body_text"] = Template(template.sms_body).render(Context(context))
        else:
            # Default: use email text if available
            if template.email_body_text:
                result["body_text"] = Template(template.email_body_text).render(Context(context))
            if template.email_subject:
                result["subject"] = Template(template.email_subject).render(Context(context))
    except Exception as e:
        logger.warning("Error rendering template %s: %s", template.key, e)
        # Return raw content as fallback
        result["body_text"] = template.email_body_text or template.sms_body or ""

    return result


def get_notification_channels_for_person(person) -> list[str]:
    """Get available notification channels for a person.

    Checks what channels are configured and what addresses the person has.

    Args:
        person: Person to check

    Returns:
        List of available channel names
    """
    from ..models import CommunicationSettings, PushSubscription

    channels = []
    settings = CommunicationSettings.objects.first()

    if not settings:
        return []

    # Check push
    if settings.is_push_configured():
        if PushSubscription.objects.filter(person=person, is_active=True).exists():
            channels.append("push")

    # Check email
    if settings.is_email_configured() and getattr(person, "email", None):
        channels.append("email")

    # Check SMS
    if settings.is_sms_configured() and getattr(person, "phone", None):
        channels.append("sms")

    return channels
