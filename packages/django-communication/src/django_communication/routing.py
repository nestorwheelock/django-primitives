"""Channel routing logic for django-communication."""

from typing import TYPE_CHECKING, Optional

from .models.message import Channel
from .models.template import MessageType

if TYPE_CHECKING:
    from .models import CommunicationSettings


# Default routing rules: message_type -> preferred channel
DEFAULT_ROUTING = {
    MessageType.TRANSACTIONAL: Channel.EMAIL,
    MessageType.REMINDER: Channel.SMS,
    MessageType.ALERT: Channel.SMS,
    MessageType.ANNOUNCEMENT: Channel.EMAIL,
}


def get_channel_for_message(
    message_type: Optional[str] = None,
    explicit_channel: Optional[str] = None,
    settings: Optional["CommunicationSettings"] = None,
) -> str:
    """Determine the channel to use for a message.

    Resolution order:
    1. Explicit channel parameter (if provided)
    2. Message type routing (based on DEFAULT_ROUTING)
    3. Default channel from settings
    4. Fallback to email

    Args:
        message_type: The MessageType value (transactional, reminder, etc.)
        explicit_channel: Explicitly requested channel (overrides routing)
        settings: CommunicationSettings instance for default_channel

    Returns:
        Channel value (email, sms)
    """
    # 1. Explicit channel takes precedence
    if explicit_channel:
        if explicit_channel in [c.value for c in Channel]:
            return explicit_channel
        raise ValueError(f"Invalid channel: {explicit_channel}")

    # 2. Route based on message type
    if message_type:
        if message_type in DEFAULT_ROUTING:
            return DEFAULT_ROUTING[message_type].value
        # Handle string values
        for msg_type, channel in DEFAULT_ROUTING.items():
            if msg_type.value == message_type:
                return channel.value

    # 3. Use default channel from settings
    if settings and settings.default_channel:
        return settings.default_channel

    # 4. Ultimate fallback
    return Channel.EMAIL.value


def get_provider_for_channel(
    channel: str,
    settings: "CommunicationSettings",
):
    """Get the appropriate provider instance for a channel.

    Args:
        channel: The channel (email, sms, push)
        settings: CommunicationSettings with provider config

    Returns:
        Provider instance ready to send messages

    Raises:
        ValueError: If no provider configured for channel
    """
    if channel == Channel.EMAIL.value:
        return _get_email_provider(settings)
    elif channel == Channel.SMS.value:
        return _get_sms_provider(settings)
    elif channel == Channel.PUSH.value:
        return _get_push_provider(settings)
    else:
        raise ValueError(f"No provider configured for channel: {channel}")


def _get_email_provider(settings: "CommunicationSettings"):
    """Get email provider based on settings."""
    provider_name = settings.email_provider or "console"

    if provider_name == "console":
        from .providers.email import ConsoleEmailProvider

        return ConsoleEmailProvider()
    elif provider_name == "ses":
        from .providers.email import SESEmailProvider

        return SESEmailProvider(settings)
    else:
        raise ValueError(f"Unknown email provider: {provider_name}")


def _get_sms_provider(settings: "CommunicationSettings"):
    """Get SMS provider based on settings."""
    provider_name = settings.sms_provider or "console"

    if provider_name == "console":
        from .providers.sms import ConsoleSMSProvider

        return ConsoleSMSProvider()
    # Future: add twilio, etc.
    else:
        raise ValueError(f"Unknown SMS provider: {provider_name}")


def _get_push_provider(settings: "CommunicationSettings"):
    """Get push provider based on settings.

    Args:
        settings: CommunicationSettings with VAPID keys configured

    Returns:
        WebPushProvider instance

    Raises:
        ValueError: If push is not properly configured
    """
    if not settings.is_push_configured():
        raise ValueError(
            "Push notifications not configured. "
            "Set push_enabled=True and provide VAPID keys."
        )

    from .providers.push import WebPushProvider

    return WebPushProvider(settings)
