"""django-communication models.

Re-exports all models for convenient importing:
    from django_communication.models import Message, MessageTemplate, Conversation
"""

from .conversation import Conversation, ConversationStatus
from .message import Channel, Message, MessageDirection, MessageStatus
from .participant import ConversationParticipant, ParticipantRole
from .profile import EmailIdentity, MessageProfile, get_recipient_locale
from .settings import CommunicationSettings
from .template import MessageTemplate, MessageType

__all__ = [
    "Channel",
    "CommunicationSettings",
    "Conversation",
    "ConversationParticipant",
    "ConversationStatus",
    "EmailIdentity",
    "Message",
    "MessageDirection",
    "MessageProfile",
    "MessageStatus",
    "MessageTemplate",
    "MessageType",
    "ParticipantRole",
    "get_recipient_locale",
]
