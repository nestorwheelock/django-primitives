"""Tests for EmailSettings singleton and email service.

Tests the DB-first SES email configuration following the same patterns as AISettings.
"""

import pytest
import sys
from unittest.mock import MagicMock, patch

from django.core import mail


@pytest.mark.django_db
class TestEmailSettingsModel:
    """Tests for EmailSettings singleton model."""

    def test_email_settings_is_singleton(self):
        """EmailSettings should only have one instance."""
        from primitives_testbed.diveops.models import EmailSettings

        settings1 = EmailSettings.get_instance()
        settings2 = EmailSettings.get_instance()
        assert settings1.pk == settings2.pk

    def test_default_values(self):
        """EmailSettings should have sensible defaults."""
        from primitives_testbed.diveops.models import EmailSettings

        settings = EmailSettings.get_instance()
        assert settings.enabled is True
        assert settings.provider == "console"
        assert settings.sandbox_mode is False
        assert settings.aws_region == "us-east-1"

    def test_provider_choices(self):
        """Provider field should accept valid choices."""
        from primitives_testbed.diveops.models import EmailSettings

        settings = EmailSettings.get_instance()

        # Console provider
        settings.provider = "console"
        settings.save()
        settings.refresh_from_db()
        assert settings.provider == "console"

        # SES API provider
        settings.provider = "ses_api"
        settings.save()
        settings.refresh_from_db()
        assert settings.provider == "ses_api"

    def test_from_email_required(self):
        """default_from_email should be required for saving."""
        from primitives_testbed.diveops.models import EmailSettings

        settings = EmailSettings.get_instance()
        settings.default_from_email = "test@example.com"
        settings.save()
        assert settings.default_from_email == "test@example.com"

    def test_is_configured_false_when_no_credentials(self):
        """is_configured should return False without SES credentials."""
        from primitives_testbed.diveops.models import EmailSettings

        settings = EmailSettings.get_instance()
        settings.provider = "ses_api"
        settings.aws_access_key_id = ""
        settings.aws_secret_access_key = ""
        settings.save()
        assert settings.is_configured() is False

    def test_is_configured_true_with_credentials(self):
        """is_configured should return True with SES credentials."""
        from primitives_testbed.diveops.models import EmailSettings

        settings = EmailSettings.get_instance()
        settings.provider = "ses_api"
        settings.aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
        settings.aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        settings.default_from_email = "test@example.com"
        settings.save()
        assert settings.is_configured() is True

    def test_is_configured_true_for_console_provider(self):
        """is_configured should return True for console provider (no creds needed)."""
        from primitives_testbed.diveops.models import EmailSettings

        settings = EmailSettings.get_instance()
        settings.provider = "console"
        settings.default_from_email = "test@example.com"
        settings.save()
        assert settings.is_configured() is True

    def test_str_representation(self):
        """String representation should be descriptive."""
        from primitives_testbed.diveops.models import EmailSettings

        settings = EmailSettings.get_instance()
        assert str(settings) == "Email Settings"


@pytest.mark.django_db
class TestEmailService:
    """Tests for email sending service."""

    def test_send_email_disabled_returns_early(self):
        """send_email should no-op when disabled."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        settings = EmailSettings.get_instance()
        settings.enabled = False
        settings.save()

        result = send_email(
            to="recipient@example.com",
            subject="Test",
            body_text="Test body",
        )

        assert result.sent is False
        assert result.reason == "disabled"

    def test_send_email_console_provider(self):
        """send_email with console provider should use Django mail."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "console"
        settings.default_from_email = "sender@example.com"
        settings.save()

        result = send_email(
            to="recipient@example.com",
            subject="Test Subject",
            body_text="Test body text",
        )

        assert result.sent is True
        assert result.provider == "console"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Test Subject"
        assert mail.outbox[0].to == ["recipient@example.com"]

    def test_send_email_with_from_name(self):
        """send_email should format From with name when provided."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "console"
        settings.default_from_email = "sender@example.com"
        settings.default_from_name = "Test Sender"
        settings.save()

        result = send_email(
            to="recipient@example.com",
            subject="Test",
            body_text="Test body",
        )

        assert result.sent is True
        assert mail.outbox[0].from_email == "Test Sender <sender@example.com>"

    def test_send_email_with_reply_to(self):
        """send_email should set reply-to header when provided."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "console"
        settings.default_from_email = "sender@example.com"
        settings.reply_to_email = "reply@example.com"
        settings.save()

        result = send_email(
            to="recipient@example.com",
            subject="Test",
            body_text="Test body",
        )

        assert result.sent is True
        assert mail.outbox[0].reply_to == ["reply@example.com"]

    def test_send_email_with_html_body(self):
        """send_email should support HTML body."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "console"
        settings.default_from_email = "sender@example.com"
        settings.save()

        result = send_email(
            to="recipient@example.com",
            subject="Test",
            body_text="Plain text",
            body_html="<html><body>HTML body</body></html>",
        )

        assert result.sent is True
        assert len(mail.outbox[0].alternatives) == 1
        assert mail.outbox[0].alternatives[0][1] == "text/html"

    def test_send_email_override_reply_to(self):
        """send_email should allow overriding reply-to per call."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "console"
        settings.default_from_email = "sender@example.com"
        settings.reply_to_email = "default-reply@example.com"
        settings.save()

        result = send_email(
            to="recipient@example.com",
            subject="Test",
            body_text="Test body",
            reply_to="override-reply@example.com",
        )

        assert result.sent is True
        assert mail.outbox[0].reply_to == ["override-reply@example.com"]

    def test_send_email_ses_api_provider(self):
        """send_email with ses_api provider should use boto3 SES."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        # Setup mock
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "test-message-id-123"}
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "ses_api"
        settings.default_from_email = "sender@example.com"
        settings.aws_region = "us-west-2"
        settings.aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
        settings.aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        settings.save()

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            result = send_email(
                to="recipient@example.com",
                subject="Test Subject",
                body_text="Test body text",
            )

        assert result.sent is True
        assert result.provider == "ses_api"
        assert result.message_id == "test-message-id-123"

        # Verify boto3 was called correctly
        mock_boto3.client.assert_called_once_with(
            "ses",
            region_name="us-west-2",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )

    def test_send_email_ses_with_configuration_set(self):
        """send_email should use configuration_set when provided."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "test-123"}
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "ses_api"
        settings.default_from_email = "sender@example.com"
        settings.aws_region = "us-east-1"
        settings.aws_access_key_id = "AKIAEXAMPLE"
        settings.aws_secret_access_key = "secretkey"
        settings.configuration_set = "my-config-set"
        settings.save()

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            send_email(
                to="recipient@example.com",
                subject="Test",
                body_text="Test body",
            )

        # Verify configuration set was included
        call_kwargs = mock_client.send_email.call_args[1]
        assert call_kwargs.get("ConfigurationSetName") == "my-config-set"

    def test_send_email_not_configured_returns_error(self):
        """send_email should return error when SES not configured."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "ses_api"
        settings.default_from_email = "sender@example.com"
        settings.aws_access_key_id = ""
        settings.aws_secret_access_key = ""
        settings.save()

        result = send_email(
            to="recipient@example.com",
            subject="Test",
            body_text="Test body",
        )

        assert result.sent is False
        assert result.reason == "not_configured"


@pytest.mark.django_db
class TestEmailResultObject:
    """Tests for EmailResult dataclass."""

    def test_email_result_attributes(self):
        """EmailResult should have expected attributes."""
        from primitives_testbed.diveops.email_service import EmailResult

        result = EmailResult(
            sent=True,
            provider="ses_api",
            message_id="msg-123",
        )

        assert result.sent is True
        assert result.provider == "ses_api"
        assert result.message_id == "msg-123"
        assert result.reason is None

    def test_email_result_failure(self):
        """EmailResult should represent failures."""
        from primitives_testbed.diveops.email_service import EmailResult

        result = EmailResult(
            sent=False,
            provider="ses_api",
            reason="not_configured",
        )

        assert result.sent is False
        assert result.reason == "not_configured"
