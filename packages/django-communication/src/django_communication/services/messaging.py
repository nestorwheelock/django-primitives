"""Communication services for sending messages via email/SMS."""

import logging
from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.template import Context, Template
from django.utils import timezone

from ..exceptions import (
    CommunicationError,
    InvalidRecipientError,
    ProviderError,
    TemplateNotFoundError,
)
from ..models.message import Channel, Message, MessageDirection, MessageStatus
from ..models.profile import EmailIdentity, MessageProfile, get_recipient_locale
from ..models.settings import CommunicationSettings
from ..models.template import MessageTemplate
from ..routing import get_channel_for_message, get_provider_for_channel

if TYPE_CHECKING:
    from django_parties.models import Person

logger = logging.getLogger(__name__)


@dataclass
class ResolvedIdentity:
    """Resolved sender identity for a message."""

    from_address: str
    from_name: str
    reply_to: str | None
    ses_configuration_set: str | None
    locale: str
    profile: MessageProfile | None


def send(
    to: "Person",
    template_key: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
    channel: Optional[str] = None,
    subject: Optional[str] = None,
    body_text: Optional[str] = None,
    body_html: Optional[str] = None,
    related_object: Optional[Any] = None,
) -> Message:
    """Send a message to a recipient.

    This is the main entry point for sending communications. It:
    1. Resolves the recipient's address (email or phone from Person)
    2. Determines the channel (explicit, template routing, or default)
    3. Renders the template (if using template)
    4. Creates a Message record for audit
    5. Sends via the appropriate provider
    6. Updates the Message with the result

    Args:
        to: Person instance (from django-parties) - recipient
        template_key: Key of MessageTemplate to use (optional if providing body)
        context: Dict of variables for template rendering
        channel: Explicit channel override (email, sms)
        subject: Override template subject (email only)
        body_text: Override template body (required if no template)
        body_html: Override template HTML body (email only)
        related_object: Optional model instance to link message to

    Returns:
        Message instance with send status

    Raises:
        TemplateNotFoundError: Template key doesn't exist or inactive
        InvalidRecipientError: Person missing required address for channel
        ProviderError: Provider failed to send
        CommunicationError: Other communication errors
    """
    context = context or {}

    # Get settings
    settings = CommunicationSettings.objects.first()
    if not settings:
        settings = CommunicationSettings.objects.create()

    # Load template if specified
    template = None
    message_type = None
    if template_key:
        try:
            template = MessageTemplate.objects.get(key=template_key, is_active=True)
            message_type = template.message_type
        except MessageTemplate.DoesNotExist:
            raise TemplateNotFoundError(f"Template not found or inactive: {template_key}")

    # Determine channel
    resolved_channel = get_channel_for_message(
        message_type=message_type,
        explicit_channel=channel,
        settings=settings,
    )

    # Resolve recipient address
    to_address = _get_recipient_address(to, resolved_channel)
    if not to_address:
        raise InvalidRecipientError(
            channel=resolved_channel,
            reason=f"Person {to.pk} has no address",
        )

    # Resolve sender identity (profile-based for email)
    identity = _get_from_address(resolved_channel, settings, recipient=to)

    # Extract from_address depending on channel
    if isinstance(identity, ResolvedIdentity):
        from_address = identity.from_address
        reply_to = identity.reply_to
        recipient_locale = identity.locale
        profile = identity.profile
    else:
        from_address = identity
        reply_to = None
        recipient_locale = ""
        profile = None

    # Render content
    final_subject, final_body_text, final_body_html = _render_content(
        template=template,
        context=context,
        channel=resolved_channel,
        subject_override=subject,
        body_text_override=body_text,
        body_html_override=body_html,
    )

    # Create message record with identity info
    message = _create_message_record(
        channel=resolved_channel,
        from_address=from_address,
        to_address=to_address,
        reply_to=reply_to or "",
        recipient_locale=recipient_locale,
        profile=profile,
        subject=final_subject,
        body_text=final_body_text,
        body_html=final_body_html,
        template=template,
        related_object=related_object,
    )

    # Validate recipient with provider
    provider = get_provider_for_channel(resolved_channel, settings)
    if not provider.validate_recipient(to_address):
        message.status = MessageStatus.FAILED
        message.error_message = f"Invalid recipient address: {to_address}"
        message.save(update_fields=["status", "error_message", "updated_at"])
        raise InvalidRecipientError(
            channel=resolved_channel,
            reason=f"Invalid address format: {to_address}",
        )

    # Send!
    try:
        message.status = MessageStatus.SENDING
        message.save(update_fields=["status", "updated_at"])

        result = provider.send(message)

        if result.success:
            message.status = MessageStatus.SENT
            message.provider = result.provider
            message.provider_message_id = result.message_id or ""
            message.sent_at = timezone.now()
            message.save(
                update_fields=[
                    "status",
                    "provider",
                    "provider_message_id",
                    "sent_at",
                    "updated_at",
                ]
            )
            logger.info(
                f"Message {message.pk} sent via {result.provider}: {result.message_id}"
            )
        else:
            message.status = MessageStatus.FAILED
            message.provider = result.provider
            message.error_message = result.error or "Unknown error"
            message.save(
                update_fields=["status", "provider", "error_message", "updated_at"]
            )
            logger.error(f"Message {message.pk} failed: {result.error}")
            raise ProviderError(
                message=result.error or "Unknown error",
                provider=result.provider,
            )

    except ProviderError:
        raise
    except Exception as e:
        message.status = MessageStatus.FAILED
        message.error_message = str(e)
        message.save(update_fields=["status", "error_message", "updated_at"])
        logger.exception(f"Message {message.pk} failed with exception")
        raise CommunicationError(str(e)) from e

    return message


def _get_recipient_address(person: "Person", channel: str) -> Optional[str]:
    """Get the appropriate address from Person for the channel."""
    if channel == Channel.EMAIL.value:
        return getattr(person, "email", None)
    elif channel == Channel.SMS.value:
        return getattr(person, "phone", None)
    return None


def resolve_email_identity(
    recipient: "Person",
    settings: CommunicationSettings,
    profile_override: MessageProfile | None = None,
    locale_override: str | None = None,
) -> ResolvedIdentity:
    """Resolve the email sender identity based on recipient's locale.

    Resolution order:
    1. Use explicit profile_override if provided
    2. Use settings.default_profile if set
    3. Fall back to legacy settings fields

    Locale resolution:
    1. Use explicit locale_override if provided
    2. Get from recipient's Demographics.preferred_language (django-parties)
    3. Default to 'en'

    Args:
        recipient: Person instance (from django-parties)
        settings: CommunicationSettings singleton
        profile_override: Explicit profile to use (optional)
        locale_override: Explicit locale to use (optional)

    Returns:
        ResolvedIdentity with from_address, reply_to, locale, profile
    """
    # Resolve locale
    if locale_override:
        locale = locale_override.lower().split("-")[0]
    else:
        locale = get_recipient_locale(recipient)

    # Get profile
    profile = profile_override or settings.default_profile

    if profile and profile.is_active:
        # Use profile-based identity
        identity = profile.get_identity_for_locale(locale)
        return ResolvedIdentity(
            from_address=identity.from_address,
            from_name=identity.from_name,
            reply_to=identity.reply_to,
            ses_configuration_set=identity.ses_configuration_set,
            locale=identity.locale,
            profile=profile,
        )
    else:
        # Fall back to legacy settings
        return ResolvedIdentity(
            from_address=settings.email_from_address or "noreply@example.com",
            from_name=settings.email_from_name or "",
            reply_to=settings.email_reply_to or None,
            ses_configuration_set=settings.ses_configuration_set or None,
            locale=locale,
            profile=None,
        )


def _get_from_address(
    channel: str,
    settings: CommunicationSettings,
    recipient: Optional["Person"] = None,
) -> ResolvedIdentity | str:
    """Get the from address/identity for a channel.

    For email: Returns ResolvedIdentity with profile-based identity
    For SMS: Returns simple string (phone number)
    """
    if channel == Channel.EMAIL.value:
        if recipient:
            return resolve_email_identity(recipient, settings)
        else:
            # No recipient - use fallback
            return ResolvedIdentity(
                from_address=settings.email_from_address or "noreply@example.com",
                from_name=settings.email_from_name or "",
                reply_to=settings.email_reply_to or None,
                ses_configuration_set=settings.ses_configuration_set or None,
                locale="en",
                profile=None,
            )
    elif channel == Channel.SMS.value:
        return settings.sms_from_number or ""
    return ""


def _render_content(
    template: Optional[MessageTemplate],
    context: dict[str, Any],
    channel: str,
    subject_override: Optional[str],
    body_text_override: Optional[str],
    body_html_override: Optional[str],
) -> tuple[str, str, str]:
    """Render message content from template or overrides.

    Returns:
        (subject, body_text, body_html)
    """
    subject = ""
    body_text = ""
    body_html = ""

    if template:
        django_context = Context(context)

        if channel == Channel.EMAIL.value:
            if template.email_subject:
                subject = Template(template.email_subject).render(django_context)
            if template.email_body_text:
                body_text = Template(template.email_body_text).render(django_context)
            if template.email_body_html:
                body_html = Template(template.email_body_html).render(django_context)
        elif channel == Channel.SMS.value:
            if template.sms_body:
                body_text = Template(template.sms_body).render(django_context)

    # Apply overrides
    if subject_override:
        subject = subject_override
    if body_text_override:
        body_text = body_text_override
    if body_html_override:
        body_html = body_html_override

    return subject, body_text, body_html


@transaction.atomic
def _create_message_record(
    channel: str,
    from_address: str,
    to_address: str,
    reply_to: str,
    recipient_locale: str,
    profile: Optional[MessageProfile],
    subject: str,
    body_text: str,
    body_html: str,
    template: Optional[MessageTemplate],
    related_object: Optional[Any],
) -> Message:
    """Create a Message record for audit trail.

    Includes resolved identity info (from_address, reply_to, locale, profile)
    for full auditability of what identity was used.
    """
    message = Message(
        direction=MessageDirection.OUTBOUND,
        channel=channel,
        from_address=from_address,
        to_address=to_address,
        reply_to=reply_to,
        recipient_locale=recipient_locale,
        profile=profile,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        template=template,
        status=MessageStatus.QUEUED,
    )

    # Link to related object if provided
    if related_object:
        message.related_content_type = ContentType.objects.get_for_model(related_object)
        message.related_object_id = str(related_object.pk)

    message.save()
    return message


def get_messages_for_object(obj: Any) -> list[Message]:
    """Get all messages linked to a specific object.

    Args:
        obj: Any model instance with a pk

    Returns:
        List of Message instances related to the object
    """
    content_type = ContentType.objects.get_for_model(obj)
    return list(
        Message.objects.filter(
            related_content_type=content_type,
            related_object_id=str(obj.pk),
        ).order_by("-created_at")
    )
