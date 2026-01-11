"""Base provider interface for communication channels."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ..models import Message


@dataclass
class SendResult:
    """Result of a send operation."""

    success: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, provider: str, message_id: str = "") -> "SendResult":
        return cls(success=True, provider=provider, message_id=message_id)

    @classmethod
    def fail(cls, provider: str, error: str) -> "SendResult":
        return cls(success=False, provider=provider, error=error)


class BaseProvider(ABC):
    """Abstract base class for communication providers.

    All providers (email, SMS, etc.) must implement this interface.
    """

    provider_name: str = "base"

    @abstractmethod
    def send(self, message: Message) -> SendResult:
        """Send a message and return the result.

        Args:
            message: The Message object to send (already persisted)

        Returns:
            SendResult with success/failure status and provider details
        """
        raise NotImplementedError

    def validate_recipient(self, address: str) -> bool:
        """Validate that the recipient address is valid for this provider.

        Override in subclasses for channel-specific validation.
        """
        return bool(address)
