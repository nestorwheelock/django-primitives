"""Tests for channel routing logic."""

import pytest

from django_communication.models import Channel, MessageType
from django_communication.routing import (
    DEFAULT_ROUTING,
    get_channel_for_message,
    get_provider_for_channel,
)


class TestDefaultRouting:
    """Tests for default routing configuration."""

    def test_transactional_routes_to_email(self):
        """Transactional messages route to email by default."""
        assert DEFAULT_ROUTING[MessageType.TRANSACTIONAL] == Channel.EMAIL

    def test_reminder_routes_to_sms(self):
        """Reminder messages route to SMS by default."""
        assert DEFAULT_ROUTING[MessageType.REMINDER] == Channel.SMS

    def test_alert_routes_to_sms(self):
        """Alert messages route to SMS by default."""
        assert DEFAULT_ROUTING[MessageType.ALERT] == Channel.SMS

    def test_announcement_routes_to_email(self):
        """Announcement messages route to email by default."""
        assert DEFAULT_ROUTING[MessageType.ANNOUNCEMENT] == Channel.EMAIL


class TestGetChannelForMessage:
    """Tests for get_channel_for_message function."""

    def test_explicit_channel_takes_precedence(self):
        """Explicit channel parameter overrides everything."""
        result = get_channel_for_message(
            message_type=MessageType.TRANSACTIONAL.value,
            explicit_channel=Channel.SMS.value,
        )
        assert result == Channel.SMS.value

    def test_invalid_explicit_channel_raises(self):
        """Invalid explicit channel raises ValueError."""
        with pytest.raises(ValueError, match="Invalid channel"):
            get_channel_for_message(explicit_channel="invalid")

    def test_message_type_routing(self):
        """Message type determines channel when no explicit channel."""
        assert get_channel_for_message(
            message_type=MessageType.TRANSACTIONAL.value
        ) == Channel.EMAIL.value
        assert get_channel_for_message(
            message_type=MessageType.REMINDER.value
        ) == Channel.SMS.value

    def test_message_type_enum_routing(self):
        """Message type as enum works for routing."""
        assert get_channel_for_message(
            message_type=MessageType.TRANSACTIONAL
        ) == Channel.EMAIL.value

    @pytest.mark.django_db
    def test_settings_default_channel(self, settings_instance):
        """Settings default_channel used when no message_type."""
        settings_instance.default_channel = Channel.SMS.value
        settings_instance.save()

        result = get_channel_for_message(settings=settings_instance)
        assert result == Channel.SMS.value

    def test_ultimate_fallback_is_email(self):
        """Falls back to email when nothing else specified."""
        result = get_channel_for_message()
        assert result == Channel.EMAIL.value


@pytest.mark.django_db
class TestGetProviderForChannel:
    """Tests for get_provider_for_channel function."""

    def test_email_console_provider(self, settings_instance):
        """Console email provider is returned for console setting."""
        settings_instance.email_provider = "console"
        settings_instance.save()

        provider = get_provider_for_channel(Channel.EMAIL.value, settings_instance)
        assert provider.provider_name == "console"

    def test_email_ses_provider(self, settings_instance):
        """SES email provider is returned for ses setting."""
        settings_instance.email_provider = "ses"
        settings_instance.ses_region = "us-east-1"
        settings_instance.save()

        provider = get_provider_for_channel(Channel.EMAIL.value, settings_instance)
        assert provider.provider_name == "ses"

    def test_sms_console_provider(self, settings_instance):
        """Console SMS provider is returned for console setting."""
        settings_instance.sms_provider = "console"
        settings_instance.save()

        provider = get_provider_for_channel(Channel.SMS.value, settings_instance)
        assert provider.provider_name == "console_sms"

    def test_unknown_email_provider_raises(self, settings_instance):
        """Unknown email provider raises ValueError."""
        settings_instance.email_provider = "unknown"
        settings_instance.save()

        with pytest.raises(ValueError, match="Unknown email provider"):
            get_provider_for_channel(Channel.EMAIL.value, settings_instance)

    def test_unknown_sms_provider_raises(self, settings_instance):
        """Unknown SMS provider raises ValueError."""
        settings_instance.sms_provider = "unknown"
        settings_instance.save()

        with pytest.raises(ValueError, match="Unknown SMS provider"):
            get_provider_for_channel(Channel.SMS.value, settings_instance)

    def test_unknown_channel_raises(self, settings_instance):
        """Unknown channel raises ValueError."""
        with pytest.raises(ValueError, match="No provider configured"):
            get_provider_for_channel("voice", settings_instance)
