"""Exceptions for django-communication."""


class CommunicationError(Exception):
    """Base exception for communication errors."""

    pass


class ProviderError(CommunicationError):
    """Error from a communication provider (SES, Twilio, etc.)."""

    def __init__(self, message: str, provider: str, original_error: Exception = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(f"[{provider}] {message}")


class TemplateNotFoundError(CommunicationError):
    """Requested template does not exist or is inactive."""

    def __init__(self, template_key: str):
        self.template_key = template_key
        super().__init__(f"Template '{template_key}' not found or inactive")


class TemplateRenderError(CommunicationError):
    """Error rendering template with provided context."""

    def __init__(self, template_key: str, error: str):
        self.template_key = template_key
        super().__init__(f"Failed to render template '{template_key}': {error}")


class ChannelDisabledError(CommunicationError):
    """Attempted to send via a disabled channel."""

    def __init__(self, channel: str):
        self.channel = channel
        super().__init__(f"Channel '{channel}' is disabled in settings")


class InvalidRecipientError(CommunicationError):
    """Recipient address is invalid or missing for the channel."""

    def __init__(self, channel: str, reason: str):
        self.channel = channel
        super().__init__(f"Invalid recipient for {channel}: {reason}")


class GroupConversationError(CommunicationError):
    """Base exception for group conversation errors."""

    pass


class NotParticipantError(GroupConversationError):
    """Person is not a participant in the conversation."""

    def __init__(self, message: str = "Not a participant in this conversation"):
        super().__init__(message)


class PermissionDeniedError(GroupConversationError):
    """Person lacks permission for the requested action."""

    def __init__(self, action: str, required_role: str = None):
        self.action = action
        self.required_role = required_role
        if required_role:
            super().__init__(f"Permission denied: {action} requires {required_role} role")
        else:
            super().__init__(f"Permission denied: {action}")


class OwnerCannotLeaveError(GroupConversationError):
    """Owner cannot leave the conversation without transferring ownership."""

    def __init__(self):
        super().__init__("Owner cannot leave the conversation. Transfer ownership first.")
