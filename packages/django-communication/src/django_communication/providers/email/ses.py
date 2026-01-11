"""AWS SES email provider."""

import logging
from typing import TYPE_CHECKING

from ..base import BaseProvider, SendResult
from ...models import Message

if TYPE_CHECKING:
    from ...models import CommunicationSettings

logger = logging.getLogger(__name__)


class SESEmailProvider(BaseProvider):
    """Email provider using AWS Simple Email Service (SES).

    Sends emails via the SES API using boto3.
    """

    provider_name = "ses"

    def __init__(self, settings: "CommunicationSettings"):
        """Initialize with settings.

        Args:
            settings: CommunicationSettings instance with SES credentials
        """
        self.settings = settings

    def _get_client(self):
        """Create boto3 SES client."""
        import boto3

        return boto3.client(
            "ses",
            region_name=self.settings.ses_region or "us-east-1",
            aws_access_key_id=self.settings.ses_access_key_id,
            aws_secret_access_key=self.settings.ses_secret_access_key,
        )

    def send(self, message: Message) -> SendResult:
        """Send email via SES API."""
        try:
            client = self._get_client()

            # Build destination
            destination = {"ToAddresses": [message.to_address]}

            # Build message body
            body = {"Text": {"Data": message.body_text, "Charset": "UTF-8"}}
            if message.body_html:
                body["Html"] = {"Data": message.body_html, "Charset": "UTF-8"}

            # Build email message
            email_message = {
                "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                "Body": body,
            }

            # Build source (from address with optional display name)
            if self.settings.email_from_name:
                source = f"{self.settings.email_from_name} <{message.from_address}>"
            else:
                source = message.from_address

            # Send params
            send_params = {
                "Source": source,
                "Destination": destination,
                "Message": email_message,
            }

            # Add reply-to if configured
            if self.settings.email_reply_to:
                send_params["ReplyToAddresses"] = [self.settings.email_reply_to]

            # Add configuration set if configured
            if self.settings.ses_configuration_set:
                send_params["ConfigurationSetName"] = self.settings.ses_configuration_set

            # Send!
            response = client.send_email(**send_params)
            message_id = response.get("MessageId", "")

            logger.info(f"SES email sent: {message_id} to {message.to_address}")
            return SendResult.ok(provider=self.provider_name, message_id=message_id)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"SES send failed: {error_msg}")
            return SendResult.fail(provider=self.provider_name, error=error_msg)

    def validate_recipient(self, address: str) -> bool:
        """Validate email address format."""
        if not address or "@" not in address:
            return False
        local, domain = address.rsplit("@", 1)
        return bool(local and domain and "." in domain)
