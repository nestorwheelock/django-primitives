"""Notification service with fallback ladder.

Provides send_notification() that tries channels in order:
1. Push (free)
2. Email (fallback)
3. SMS (fallback)

Also provides get_notification_status() for staff visibility.
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from django.db import transaction

from ..models import (
    Channel,
    CommunicationSettings,
    Message,
    MessageDirection,
    MessageStatus,
    PushSubscription,
)
from ..routing import get_provider_for_channel

if TYPE_CHECKING:
    from django_parties.models import Person
    from ..models import Conversation

logger = logging.getLogger(__name__)


def send_notification(
    person: "Person",
    subject: str,
    body_text: str,
    body_html: str = "",
    conversation: Optional["Conversation"] = None,
    related_object: Any = None,
) -> tuple[Optional[Message], str]:
    """Send notification using fallback ladder: Push → Email → SMS.

    Args:
        person: The Person to notify
        subject: Notification subject/title
        body_text: Plain text body
        body_html: Optional HTML body (for email)
        conversation: Optional Conversation to link message to
        related_object: Optional object to link via GenericFK

    Returns:
        (message, channel_used) - The sent message and which channel succeeded
        (None, "none") - If all channels failed or person has no contact methods
    """
    settings = _get_settings()

    # 1. Try Push first (free)
    if settings.is_push_configured():
        result = _try_push(person, subject, body_text, conversation, related_object, settings)
        if result[0] is not None:
            return result

    # 2. Fallback to Email (if enabled and configured)
    if settings.notification_fallback_enabled:
        if person.email:
            result = _try_email(
                person, subject, body_text, body_html, conversation, related_object, settings
            )
            if result[0] is not None:
                return result

        # 3. Fallback to SMS
        if person.phone:
            result = _try_sms(person, body_text, conversation, related_object, settings)
            if result[0] is not None:
                return result

    return None, "none"


def get_notification_status(person: "Person") -> dict:
    """Get notification capability status for a person.

    Returns dict with channel availability for staff visibility.
    """
    settings = _get_settings()

    active_subs = PushSubscription.objects.filter(
        person=person,
        is_active=True,
    ).count()

    push_configured = settings.is_push_configured() if settings else False
    email_configured = _is_email_configured(settings)
    sms_configured = _is_sms_configured(settings)

    return {
        "push_enabled": bool(push_configured and active_subs > 0),
        "push_subscription_count": active_subs,
        "email_available": bool(person.email and email_configured),
        "sms_available": bool(person.phone and sms_configured),
        "primary_channel": _get_primary_channel(person, settings),
    }


def _get_settings() -> CommunicationSettings:
    """Get or create communication settings."""
    settings = CommunicationSettings.objects.first()
    if not settings:
        settings = CommunicationSettings.objects.create()
    return settings


def _is_email_configured(settings: Optional[CommunicationSettings]) -> bool:
    """Check if email sending is configured."""
    if not settings:
        return False
    return bool(settings.email_provider)


def _is_sms_configured(settings: Optional[CommunicationSettings]) -> bool:
    """Check if SMS sending is configured."""
    if not settings:
        return False
    return bool(settings.sms_provider)


def _get_primary_channel(person: "Person", settings: Optional[CommunicationSettings]) -> str:
    """Determine the primary notification channel for a person."""
    if settings and settings.is_push_configured():
        if PushSubscription.objects.filter(person=person, is_active=True).exists():
            return "push"
    if person.email and _is_email_configured(settings):
        return "email"
    if person.phone and _is_sms_configured(settings):
        return "sms"
    return "none"


def _try_push(
    person: "Person",
    subject: str,
    body_text: str,
    conversation: Optional["Conversation"],
    related_object: Any,
    settings: CommunicationSettings,
) -> tuple[Optional[Message], str]:
    """Try to send push notification to all active subscriptions."""
    subscriptions = PushSubscription.objects.filter(
        person=person,
        is_active=True,
    )

    for sub in subscriptions:
        try:
            message = _send_via_push(
                person=person,
                subscription=sub,
                subject=subject,
                body_text=body_text,
                conversation=conversation,
                related_object=related_object,
                settings=settings,
            )
            if message and message.status == MessageStatus.SENT:
                return message, "push"
        except Exception as e:
            logger.warning(f"Push to {sub.endpoint[:50]} failed: {e}")
            continue  # Try next subscription

    return None, "none"


def _send_via_push(
    person: "Person",
    subscription: PushSubscription,
    subject: str,
    body_text: str,
    conversation: Optional["Conversation"],
    related_object: Any,
    settings: CommunicationSettings,
) -> Optional[Message]:
    """Send push notification via specific subscription."""
    from django.contrib.contenttypes.models import ContentType

    with transaction.atomic():
        # Create message record
        message_kwargs = {
            "direction": MessageDirection.OUTBOUND,
            "channel": Channel.PUSH,
            "from_address": "system",
            "to_address": subscription.endpoint,
            "subject": subject,
            "body_text": body_text[:200],  # Truncate for push
            "status": MessageStatus.QUEUED,
        }

        if conversation:
            message_kwargs["conversation"] = conversation

        if related_object:
            message_kwargs["related_object_content_type"] = ContentType.objects.get_for_model(
                related_object
            )
            message_kwargs["related_object_id"] = str(related_object.pk)

        message = Message.objects.create(**message_kwargs)

        # Send via provider
        try:
            provider = get_provider_for_channel(Channel.PUSH.value, settings)
            result = provider.send(message)

            if result.success:
                message.status = MessageStatus.SENT
                message.provider_message_id = result.message_id
                message.save(update_fields=["status", "provider_message_id", "updated_at"])
                return message
            else:
                message.status = MessageStatus.FAILED
                message.error_message = result.error
                message.save(update_fields=["status", "error_message", "updated_at"])
                return None
        except Exception as e:
            message.status = MessageStatus.FAILED
            message.error_message = str(e)
            message.save(update_fields=["status", "error_message", "updated_at"])
            raise


def _try_email(
    person: "Person",
    subject: str,
    body_text: str,
    body_html: str,
    conversation: Optional["Conversation"],
    related_object: Any,
    settings: CommunicationSettings,
) -> tuple[Optional[Message], str]:
    """Try to send email notification."""
    from django.contrib.contenttypes.models import ContentType

    try:
        with transaction.atomic():
            message_kwargs = {
                "direction": MessageDirection.OUTBOUND,
                "channel": Channel.EMAIL,
                "from_address": settings.email_from_address or "noreply@example.com",
                "to_address": person.email,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "status": MessageStatus.QUEUED,
            }

            if conversation:
                message_kwargs["conversation"] = conversation

            if related_object:
                message_kwargs["related_object_content_type"] = ContentType.objects.get_for_model(
                    related_object
                )
                message_kwargs["related_object_id"] = str(related_object.pk)

            message = Message.objects.create(**message_kwargs)

            # Send via provider
            provider = get_provider_for_channel(Channel.EMAIL.value, settings)
            result = provider.send(message)

            if result.success:
                message.status = MessageStatus.SENT
                message.provider_message_id = result.message_id
                message.save(update_fields=["status", "provider_message_id", "updated_at"])
                return message, "email"
            else:
                message.status = MessageStatus.FAILED
                message.error_message = result.error
                message.save(update_fields=["status", "error_message", "updated_at"])
                return None, "none"
    except Exception as e:
        logger.warning(f"Email notification failed: {e}")
        return None, "none"


def _try_sms(
    person: "Person",
    body_text: str,
    conversation: Optional["Conversation"],
    related_object: Any,
    settings: CommunicationSettings,
) -> tuple[Optional[Message], str]:
    """Try to send SMS notification."""
    from django.contrib.contenttypes.models import ContentType

    try:
        with transaction.atomic():
            message_kwargs = {
                "direction": MessageDirection.OUTBOUND,
                "channel": Channel.SMS,
                "from_address": settings.sms_from_number or "+15550000000",
                "to_address": person.phone,
                "body_text": body_text[:160],  # SMS limit
                "status": MessageStatus.QUEUED,
            }

            if conversation:
                message_kwargs["conversation"] = conversation

            if related_object:
                message_kwargs["related_object_content_type"] = ContentType.objects.get_for_model(
                    related_object
                )
                message_kwargs["related_object_id"] = str(related_object.pk)

            message = Message.objects.create(**message_kwargs)

            # Send via provider
            provider = get_provider_for_channel(Channel.SMS.value, settings)
            result = provider.send(message)

            if result.success:
                message.status = MessageStatus.SENT
                message.provider_message_id = result.message_id
                message.save(update_fields=["status", "provider_message_id", "updated_at"])
                return message, "sms"
            else:
                message.status = MessageStatus.FAILED
                message.error_message = result.error
                message.save(update_fields=["status", "error_message", "updated_at"])
                return None, "none"
    except Exception as e:
        logger.warning(f"SMS notification failed: {e}")
        return None, "none"
