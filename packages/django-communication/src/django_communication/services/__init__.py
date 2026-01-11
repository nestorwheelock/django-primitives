"""django-communication services.

Re-exports all services for convenient importing.
"""

from .conversations import (
    create_conversation,
    ensure_conversation_participant,
    find_or_create_for_email,
    get_conversation_messages,
    get_customer_inbox,
    get_or_create_conversation_for_related,
    get_staff_inbox,
    mark_conversation_read,
    send_in_conversation,
)
from .messaging import (
    ResolvedIdentity,
    get_messages_for_object,
    resolve_email_identity,
    send,
)

__all__ = [
    # Conversation services
    "create_conversation",
    "ensure_conversation_participant",
    "find_or_create_for_email",
    "get_conversation_messages",
    "get_customer_inbox",
    "get_or_create_conversation_for_related",
    "get_staff_inbox",
    "mark_conversation_read",
    "send_in_conversation",
    # Messaging services
    "ResolvedIdentity",
    "get_messages_for_object",
    "resolve_email_identity",
    "send",
]
