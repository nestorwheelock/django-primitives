"""Web Push provider using pywebpush library."""

import json
import logging
from typing import TYPE_CHECKING

from django.utils import timezone
from pywebpush import webpush, WebPushException

from ..base import BaseProvider, SendResult

if TYPE_CHECKING:
    from ...models import CommunicationSettings, Message

logger = logging.getLogger(__name__)


class WebPushProvider(BaseProvider):
    """Web Push provider using pywebpush library.

    Sends push notifications via the Web Push protocol using VAPID
    authentication. The subscription endpoint and keys are stored
    in PushSubscription models.

    This provider:
    - Tracks successful pushes via last_successful_push
    - Increments failure_count on errors
    - Deactivates subscriptions after threshold failures
    - Immediately deactivates on 404/410 (subscription gone)
    """

    provider_name = "webpush"

    def __init__(self, settings: "CommunicationSettings"):
        """Initialize with communication settings.

        Args:
            settings: CommunicationSettings with VAPID keys configured
        """
        self.settings = settings

    def send(self, message: "Message") -> SendResult:
        """Send push notification.

        The message.to_address should be the push subscription endpoint.
        The actual subscription data (keys) is retrieved from the
        PushSubscription model matching that endpoint.

        Args:
            message: Message object with to_address set to endpoint

        Returns:
            SendResult with success/failure status
        """
        from ...models.push_subscription import PushSubscription

        # Find the subscription by endpoint
        try:
            subscription = PushSubscription.objects.get(
                endpoint=message.to_address,
                is_active=True,
            )
        except PushSubscription.DoesNotExist:
            logger.warning(f"Push subscription not found or inactive: {message.to_address[:50]}...")
            return SendResult.fail(
                self.provider_name,
                "Subscription not found or inactive",
            )

        # Build subscription info for pywebpush
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh_key,
                "auth": subscription.auth_key,
            },
        }

        # Build notification payload
        payload = json.dumps({
            "title": message.subject or "New Notification",
            "body": message.body_text[:200] if message.body_text else "",
            "url": "/portal/messages/",
            "timestamp": message.created_at.isoformat() if message.created_at else None,
        })

        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self.settings.vapid_private_key,
                vapid_claims={
                    "sub": f"mailto:{self.settings.vapid_contact_email}",
                },
            )

            # Update subscription success tracking
            subscription.last_successful_push = timezone.now()
            subscription.failure_count = 0
            subscription.save(
                update_fields=["last_successful_push", "failure_count", "updated_at"]
            )

            logger.info(f"Push notification sent to {subscription.endpoint[:50]}...")
            return SendResult.ok(self.provider_name, "push_sent")

        except WebPushException as e:
            logger.error(f"WebPush error: {e}")

            # Handle subscription expired (410 Gone or 404 Not Found)
            if e.response and e.response.status_code in (404, 410):
                subscription.is_active = False
                subscription.save(update_fields=["is_active", "updated_at"])
                logger.warning(f"Push subscription expired, deactivated: {subscription.endpoint[:50]}...")
                return SendResult.fail(self.provider_name, "Subscription expired")

            # Increment failure count
            subscription.failure_count += 1

            # Deactivate if reached threshold
            if subscription.failure_count >= self.settings.push_failure_threshold:
                subscription.is_active = False
                logger.warning(
                    f"Push subscription deactivated after {subscription.failure_count} failures: "
                    f"{subscription.endpoint[:50]}..."
                )

            subscription.save(
                update_fields=["failure_count", "is_active", "updated_at"]
            )

            return SendResult.fail(self.provider_name, str(e))

        except Exception as e:
            logger.exception(f"Unexpected error sending push: {e}")
            return SendResult.fail(self.provider_name, str(e))

    def validate_recipient(self, address: str) -> bool:
        """Validate that the address is a valid HTTPS endpoint.

        Push endpoints must be HTTPS for security.

        Args:
            address: Push subscription endpoint URL

        Returns:
            True if valid HTTPS URL, False otherwise
        """
        if not address:
            return False
        return address.startswith("https://")
