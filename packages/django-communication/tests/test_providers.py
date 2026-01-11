"""Tests for communication providers."""

import pytest
from unittest.mock import MagicMock, patch

from django_communication.models import (
    Channel,
    Message,
    MessageDirection,
    MessageStatus,
)
from django_communication.providers.base import BaseProvider, SendResult
from django_communication.providers.email import ConsoleEmailProvider, SESEmailProvider
from django_communication.providers.sms import ConsoleSMSProvider


class TestSendResult:
    """Tests for SendResult dataclass."""

    def test_ok_result(self):
        """SendResult.ok creates successful result."""
        result = SendResult.ok(provider="console", message_id="abc123")
        assert result.success is True
        assert result.provider == "console"
        assert result.message_id == "abc123"
        assert result.error is None

    def test_fail_result(self):
        """SendResult.fail creates failed result."""
        result = SendResult.fail(provider="ses", error="Connection timeout")
        assert result.success is False
        assert result.provider == "ses"
        assert result.message_id is None
        assert result.error == "Connection timeout"


@pytest.mark.django_db
class TestConsoleEmailProvider:
    """Tests for ConsoleEmailProvider."""

    def test_provider_name(self):
        """Console provider has correct name."""
        provider = ConsoleEmailProvider()
        assert provider.provider_name == "console"

    def test_send_returns_success(self, message_template, caplog):
        """Send logs email and returns success."""
        import logging

        caplog.set_level(logging.INFO)
        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body_text="Test body content",
            template=message_template,
            status=MessageStatus.QUEUED,
        )

        provider = ConsoleEmailProvider()
        result = provider.send(message)

        assert result.success is True
        assert result.provider == "console"
        assert result.message_id.startswith("console-")
        assert "CONSOLE EMAIL" in caplog.text

    def test_validate_recipient_valid_email(self):
        """Valid email addresses pass validation."""
        provider = ConsoleEmailProvider()
        assert provider.validate_recipient("user@example.com") is True
        assert provider.validate_recipient("test.user@sub.domain.com") is True

    def test_validate_recipient_invalid_email(self):
        """Invalid email addresses fail validation."""
        provider = ConsoleEmailProvider()
        assert provider.validate_recipient("not-an-email") is False
        assert provider.validate_recipient("") is False


@pytest.mark.django_db
class TestSESEmailProvider:
    """Tests for SESEmailProvider."""

    def test_provider_name(self, settings_instance):
        """SES provider has correct name."""
        provider = SESEmailProvider(settings_instance)
        assert provider.provider_name == "ses"

    def test_send_success(self, settings_instance):
        """Send via SES returns success on successful API call."""
        settings_instance.ses_region = "us-east-1"
        settings_instance.save()

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body_text="Test body",
            status=MessageStatus.QUEUED,
        )

        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_client.send_email.return_value = {"MessageId": "ses-12345"}
            mock_boto3_client.return_value = mock_client

            provider = SESEmailProvider(settings_instance)
            result = provider.send(message)

            assert result.success is True
            assert result.provider == "ses"
            assert result.message_id == "ses-12345"
            mock_client.send_email.assert_called_once()

    def test_send_with_html_body(self, settings_instance):
        """Send includes HTML body when present."""
        settings_instance.ses_region = "us-east-1"
        settings_instance.save()

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body_text="Plain text",
            body_html="<p>HTML content</p>",
            status=MessageStatus.QUEUED,
        )

        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_client.send_email.return_value = {"MessageId": "ses-html"}
            mock_boto3_client.return_value = mock_client

            provider = SESEmailProvider(settings_instance)
            provider.send(message)

            call_args = mock_client.send_email.call_args
            body = call_args[1]["Message"]["Body"]
            assert "Html" in body
            assert body["Html"]["Data"] == "<p>HTML content</p>"

    def test_send_failure(self, settings_instance):
        """Send returns failure on API exception."""
        settings_instance.ses_region = "us-east-1"
        settings_instance.save()

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body_text="Test",
            status=MessageStatus.QUEUED,
        )

        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_client.send_email.side_effect = Exception("Connection refused")
            mock_boto3_client.return_value = mock_client

            provider = SESEmailProvider(settings_instance)
            result = provider.send(message)

            assert result.success is False
            assert "Connection refused" in result.error

    def test_validate_recipient_valid_email(self, settings_instance):
        """Valid email addresses pass validation."""
        provider = SESEmailProvider(settings_instance)
        assert provider.validate_recipient("user@example.com") is True

    def test_validate_recipient_invalid_email(self, settings_instance):
        """Invalid email addresses fail validation."""
        provider = SESEmailProvider(settings_instance)
        assert provider.validate_recipient("invalid") is False
        assert provider.validate_recipient("") is False


@pytest.mark.django_db
class TestConsoleSMSProvider:
    """Tests for ConsoleSMSProvider."""

    def test_provider_name(self):
        """Console SMS provider has correct name."""
        provider = ConsoleSMSProvider()
        assert provider.provider_name == "console_sms"

    def test_send_returns_success(self, caplog):
        """Send logs SMS and returns success."""
        import logging

        caplog.set_level(logging.INFO)
        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.SMS,
            from_address="+15550001111",
            to_address="+15559998888",
            body_text="Test SMS message",
            status=MessageStatus.QUEUED,
        )

        provider = ConsoleSMSProvider()
        result = provider.send(message)

        assert result.success is True
        assert result.provider == "console_sms"
        assert result.message_id.startswith("sms-console-")
        assert "CONSOLE SMS" in caplog.text

    def test_validate_recipient_e164_format(self):
        """E.164 format phone numbers pass validation."""
        provider = ConsoleSMSProvider()
        assert provider.validate_recipient("+15551234567") is True
        assert provider.validate_recipient("+447911123456") is True

    def test_validate_recipient_plain_digits(self):
        """Plain digit phone numbers pass validation."""
        provider = ConsoleSMSProvider()
        assert provider.validate_recipient("5551234567") is True
        assert provider.validate_recipient("15551234567") is True

    def test_validate_recipient_with_formatting(self):
        """Phone numbers with formatting characters pass validation."""
        provider = ConsoleSMSProvider()
        assert provider.validate_recipient("+1 (555) 123-4567") is True
        assert provider.validate_recipient("555-123-4567") is True

    def test_validate_recipient_invalid(self):
        """Invalid phone numbers fail validation."""
        provider = ConsoleSMSProvider()
        assert provider.validate_recipient("") is False
        assert provider.validate_recipient("12345") is False  # Too short
        assert provider.validate_recipient("abc") is False

    def test_sms_segments_calculation(self, caplog):
        """SMS segment count is logged correctly."""
        import logging

        caplog.set_level(logging.INFO)
        short_message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.SMS,
            from_address="+15550001111",
            to_address="+15559998888",
            body_text="Short message",
            status=MessageStatus.QUEUED,
        )
        long_message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.SMS,
            from_address="+15550001111",
            to_address="+15559998888",
            body_text="A" * 200,  # More than 160 chars
            status=MessageStatus.QUEUED,
        )

        provider = ConsoleSMSProvider()

        provider.send(short_message)
        assert "Segments: 1" in caplog.text

        caplog.clear()
        caplog.set_level(logging.INFO)
        provider.send(long_message)
        assert "Segments: 2" in caplog.text


@pytest.mark.django_db
class TestWebPushProvider:
    """Tests for WebPushProvider."""

    @pytest.fixture
    def push_settings(self, db):
        """Create settings with push configured."""
        from django_communication.models import CommunicationSettings

        settings, _ = CommunicationSettings.objects.get_or_create(
            defaults={
                "push_enabled": True,
                "vapid_public_key": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
                "vapid_private_key": "xYmPh0VhN7cN3K4fUqDr-5cJjA5FPhMJTKKLR3pHqYE",
                "vapid_contact_email": "admin@example.com",
                "push_failure_threshold": 3,
            }
        )
        return settings

    @pytest.fixture
    def push_subscription(self, person, db):
        """Create a push subscription for testing."""
        from django_communication.models import PushSubscription

        return PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/test123",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
            is_active=True,
        )

    def test_provider_name(self, push_settings):
        """WebPush provider has correct name."""
        from django_communication.providers.push import WebPushProvider

        provider = WebPushProvider(push_settings)
        assert provider.provider_name == "webpush"

    def test_validate_recipient_https(self, push_settings):
        """HTTPS endpoints pass validation."""
        from django_communication.providers.push import WebPushProvider

        provider = WebPushProvider(push_settings)
        assert provider.validate_recipient("https://fcm.googleapis.com/fcm/send/abc123") is True
        assert provider.validate_recipient("https://updates.push.services.mozilla.com/xyz") is True

    def test_validate_recipient_http_fails(self, push_settings):
        """HTTP endpoints fail validation."""
        from django_communication.providers.push import WebPushProvider

        provider = WebPushProvider(push_settings)
        assert provider.validate_recipient("http://insecure.example.com/push") is False
        assert provider.validate_recipient("not-a-url") is False
        assert provider.validate_recipient("") is False

    def test_send_success(self, push_settings, push_subscription):
        """Send push notification successfully."""
        from django_communication.providers.push import WebPushProvider
        from django.utils import timezone

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.PUSH,
            from_address="system",
            to_address=push_subscription.endpoint,
            subject="New Message",
            body_text="You have a new message",
            status=MessageStatus.QUEUED,
        )

        with patch("django_communication.providers.push.webpush.webpush") as mock_webpush:
            mock_webpush.return_value = MagicMock()

            provider = WebPushProvider(push_settings)
            result = provider.send(message)

            assert result.success is True
            assert result.provider == "webpush"
            mock_webpush.assert_called_once()

            # Verify subscription updated
            push_subscription.refresh_from_db()
            assert push_subscription.failure_count == 0
            assert push_subscription.last_successful_push is not None

    def test_send_subscription_not_found(self, push_settings):
        """Send fails when subscription not found."""
        from django_communication.providers.push import WebPushProvider

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.PUSH,
            from_address="system",
            to_address="https://nonexistent.endpoint/push",
            subject="Test",
            body_text="Test message",
            status=MessageStatus.QUEUED,
        )

        provider = WebPushProvider(push_settings)
        result = provider.send(message)

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_send_subscription_inactive(self, push_settings, push_subscription):
        """Send fails when subscription is inactive."""
        from django_communication.providers.push import WebPushProvider

        push_subscription.is_active = False
        push_subscription.save()

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.PUSH,
            from_address="system",
            to_address=push_subscription.endpoint,
            subject="Test",
            body_text="Test message",
            status=MessageStatus.QUEUED,
        )

        provider = WebPushProvider(push_settings)
        result = provider.send(message)

        assert result.success is False

    def test_send_increments_failure_count(self, push_settings, push_subscription):
        """Send failure increments failure count."""
        from django_communication.providers.push import WebPushProvider
        from pywebpush import WebPushException

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.PUSH,
            from_address="system",
            to_address=push_subscription.endpoint,
            subject="Test",
            body_text="Test message",
            status=MessageStatus.QUEUED,
        )

        with patch("django_communication.providers.push.webpush.webpush") as mock_webpush:
            error_response = MagicMock()
            error_response.status_code = 500
            mock_webpush.side_effect = WebPushException("Server error", response=error_response)

            provider = WebPushProvider(push_settings)
            result = provider.send(message)

            assert result.success is False
            push_subscription.refresh_from_db()
            assert push_subscription.failure_count == 1
            assert push_subscription.is_active is True  # Still active after 1 failure

    def test_send_deactivates_on_threshold(self, push_settings, push_subscription):
        """Subscription deactivated after reaching failure threshold."""
        from django_communication.providers.push import WebPushProvider
        from pywebpush import WebPushException

        push_subscription.failure_count = 2  # One away from threshold
        push_subscription.save()

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.PUSH,
            from_address="system",
            to_address=push_subscription.endpoint,
            subject="Test",
            body_text="Test message",
            status=MessageStatus.QUEUED,
        )

        with patch("django_communication.providers.push.webpush.webpush") as mock_webpush:
            error_response = MagicMock()
            error_response.status_code = 500
            mock_webpush.side_effect = WebPushException("Server error", response=error_response)

            provider = WebPushProvider(push_settings)
            provider.send(message)

            push_subscription.refresh_from_db()
            assert push_subscription.failure_count == 3
            assert push_subscription.is_active is False  # Deactivated at threshold

    def test_send_deactivates_on_410_gone(self, push_settings, push_subscription):
        """Subscription deactivated immediately on 410 Gone response."""
        from django_communication.providers.push import WebPushProvider
        from pywebpush import WebPushException

        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.PUSH,
            from_address="system",
            to_address=push_subscription.endpoint,
            subject="Test",
            body_text="Test message",
            status=MessageStatus.QUEUED,
        )

        with patch("django_communication.providers.push.webpush.webpush") as mock_webpush:
            error_response = MagicMock()
            error_response.status_code = 410  # Gone - subscription expired
            mock_webpush.side_effect = WebPushException("Subscription gone", response=error_response)

            provider = WebPushProvider(push_settings)
            result = provider.send(message)

            assert result.success is False
            assert "expired" in result.error.lower()
            push_subscription.refresh_from_db()
            assert push_subscription.is_active is False
