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
