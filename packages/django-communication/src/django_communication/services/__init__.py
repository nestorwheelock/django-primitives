"""django-communication services.

Re-exports all services for convenient importing.
"""

from .conversations import (
    accept_invite,
    add_participant,
    can_send_message,
    create_conversation,
    create_group_conversation,
    ensure_conversation_participant,
    find_or_create_for_email,
    get_active_participants,
    get_conversation_messages,
    get_customer_inbox,
    get_or_create_conversation_for_related,
    get_staff_inbox,
    invite_participant,
    leave_conversation,
    mark_conversation_read,
    remove_participant,
    send_in_conversation,
    send_system_message,
    set_conversation_title,
)
from .messaging import (
    ResolvedIdentity,
    get_messages_for_object,
    resolve_email_identity,
    send,
)
from .notifications import (
    get_notification_status,
    send_notification,
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
    # Group conversation services
    "accept_invite",
    "add_participant",
    "can_send_message",
    "create_group_conversation",
    "get_active_participants",
    "invite_participant",
    "leave_conversation",
    "remove_participant",
    "send_system_message",
    "set_conversation_title",
    # Messaging services
    "ResolvedIdentity",
    "get_messages_for_object",
    "resolve_email_identity",
    "send",
    # Notification services
    "get_notification_status",
    "send_notification",
]
