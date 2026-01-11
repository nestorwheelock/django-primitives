"""Console email provider for development."""

import logging
import uuid

from ..base import BaseProvider, SendResult
from ...models import Message

logger = logging.getLogger(__name__)


class ConsoleEmailProvider(BaseProvider):
    """Email provider that logs to console (for development).

    Does not actually send emails - just logs them for debugging.
    """

    provider_name = "console"

    def send(self, message: Message) -> SendResult:
        """Log email to console and return success."""
        fake_message_id = f"console-{uuid.uuid4().hex[:12]}"

        logger.info(
            "\n"
            "=" * 60 + "\n"
            "CONSOLE EMAIL (not actually sent)\n"
            "=" * 60 + "\n"
            f"To: {message.to_address}\n"
            f"From: {message.from_address}\n"
            f"Subject: {message.subject}\n"
            "-" * 60 + "\n"
            f"{message.body_text}\n"
            "=" * 60
        )

        if message.body_html:
            logger.debug(f"HTML body length: {len(message.body_html)} chars")

        return SendResult.ok(provider=self.provider_name, message_id=fake_message_id)

    def validate_recipient(self, address: str) -> bool:
        """Basic email validation."""
        return "@" in address and "." in address.split("@")[-1]
