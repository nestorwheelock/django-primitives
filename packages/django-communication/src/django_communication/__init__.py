"""Django Communication - Multi-channel messaging primitive."""

__version__ = "0.1.0"

__all__ = [
    # Models
    "CommunicationSettings",
    "Conversation",
    "ConversationParticipant",
    "Message",
    "MessageTemplate",
    # Enums
    "Channel",
    "ConversationStatus",
    "MessageDirection",
    "MessageStatus",
    "MessageType",
    "ParticipantRole",
    # Services
    "send",
    "get_messages_for_object",
    # Exceptions
    "CommunicationError",
    "TemplateNotFoundError",
    "InvalidRecipientError",
    "ProviderError",
]


def __getattr__(name: str):
    """Lazy import to avoid AppRegistryNotReady errors."""
    if name == "CommunicationSettings":
        from .models import CommunicationSettings

        return CommunicationSettings
    if name == "Conversation":
        from .models import Conversation

        return Conversation
    if name == "ConversationParticipant":
        from .models import ConversationParticipant

        return ConversationParticipant
    if name == "MessageTemplate":
        from .models import MessageTemplate

        return MessageTemplate
    if name == "Message":
        from .models import Message

        return Message
    if name == "Channel":
        from .models.message import Channel

        return Channel
    if name == "ConversationStatus":
        from .models.conversation import ConversationStatus

        return ConversationStatus
    if name == "MessageDirection":
        from .models.message import MessageDirection

        return MessageDirection
    if name == "MessageStatus":
        from .models.message import MessageStatus

        return MessageStatus
    if name == "MessageType":
        from .models.template import MessageType

        return MessageType
    if name == "ParticipantRole":
        from .models.participant import ParticipantRole

        return ParticipantRole
    if name == "send":
        from .services import send

        return send
    if name == "get_messages_for_object":
        from .services import get_messages_for_object

        return get_messages_for_object
    if name in (
        "CommunicationError",
        "TemplateNotFoundError",
        "InvalidRecipientError",
        "ProviderError",
    ):
        from . import exceptions

        return getattr(exceptions, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
