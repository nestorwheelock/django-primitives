"""Console SMS provider for development."""

import logging
import re
import uuid

from ..base import BaseProvider, SendResult
from ...models import Message

logger = logging.getLogger(__name__)


class ConsoleSMSProvider(BaseProvider):
    """SMS provider that logs to console (for development).

    Does not actually send SMS - just logs them for debugging.
    """

    provider_name = "console_sms"

    def send(self, message: Message) -> SendResult:
        """Log SMS to console and return success."""
        fake_message_id = f"sms-console-{uuid.uuid4().hex[:12]}"

        # Calculate SMS segments (160 chars per segment for GSM-7)
        segments = (len(message.body_text) + 159) // 160

        logger.info(
            "\n"
            "=" * 60 + "\n"
            "CONSOLE SMS (not actually sent)\n"
            "=" * 60 + "\n"
            f"To: {message.to_address}\n"
            f"From: {message.from_address}\n"
            f"Segments: {segments}\n"
            "-" * 60 + "\n"
            f"{message.body_text}\n"
            "=" * 60
        )

        return SendResult.ok(provider=self.provider_name, message_id=fake_message_id)

    def validate_recipient(self, address: str) -> bool:
        """Validate phone number format (E.164 preferred)."""
        if not address:
            return False
        # Accept E.164 format (+1234567890) or plain digits
        cleaned = re.sub(r"[\s\-\(\)]", "", address)
        if cleaned.startswith("+"):
            return len(cleaned) >= 10 and cleaned[1:].isdigit()
        return len(cleaned) >= 10 and cleaned.isdigit()
