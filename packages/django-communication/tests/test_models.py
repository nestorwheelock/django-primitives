"""Tests for django-communication models."""

import pytest
from django.db import IntegrityError

from django_communication.models import (
    Channel,
    CommunicationSettings,
    Message,
    MessageDirection,
    MessageStatus,
    MessageTemplate,
    MessageType,
)


@pytest.mark.django_db
class TestCommunicationSettings:
    """Tests for CommunicationSettings singleton model."""

    def test_singleton_creation(self):
        """Settings can be created."""
        settings = CommunicationSettings.objects.create(
            email_provider="console",
            email_from_address="test@example.com",
        )
        assert settings.pk is not None
        assert settings.email_provider == "console"

    def test_default_values(self):
        """Settings has sensible defaults."""
        settings = CommunicationSettings.objects.create()
        assert settings.email_provider == "console"
        assert settings.sms_provider == "console"
        assert settings.default_channel == "email"

    def test_ses_configuration_fields(self):
        """SES configuration fields are stored correctly."""
        settings = CommunicationSettings.objects.create(
            email_provider="ses",
            ses_access_key_id="AKIAXXXXXXXX",
            ses_secret_access_key="secret123",
            ses_region="us-west-2",
            ses_configuration_set="my-config-set",
        )
        assert settings.ses_access_key_id == "AKIAXXXXXXXX"
        assert settings.ses_region == "us-west-2"


@pytest.mark.django_db
class TestMessageTemplate:
    """Tests for MessageTemplate model."""

    def test_template_creation(self):
        """Template can be created with required fields."""
        template = MessageTemplate.objects.create(
            key="welcome-email",
            name="Welcome Email",
            message_type=MessageType.TRANSACTIONAL,
            email_subject="Welcome!",
            email_body_text="Welcome to our service.",
        )
        assert template.pk is not None
        assert template.key == "welcome-email"
        assert template.is_active is True

    def test_template_key_uniqueness(self):
        """Template key must be unique."""
        MessageTemplate.objects.create(
            key="unique-key",
            name="First Template",
            message_type=MessageType.TRANSACTIONAL,
        )
        with pytest.raises(IntegrityError):
            MessageTemplate.objects.create(
                key="unique-key",
                name="Second Template",
                message_type=MessageType.TRANSACTIONAL,
            )

    def test_message_type_choices(self):
        """MessageType enum has expected values."""
        assert MessageType.TRANSACTIONAL == "transactional"
        assert MessageType.REMINDER == "reminder"
        assert MessageType.ALERT == "alert"
        assert MessageType.ANNOUNCEMENT == "announcement"

    def test_template_str(self):
        """Template string representation includes key and name."""
        template = MessageTemplate.objects.create(
            key="test-template",
            name="Test Template",
            message_type=MessageType.TRANSACTIONAL,
        )
        assert str(template) == "test-template: Test Template"

    def test_multi_channel_template(self):
        """Template can have both email and SMS content."""
        template = MessageTemplate.objects.create(
            key="multi-channel",
            name="Multi-Channel Template",
            message_type=MessageType.REMINDER,
            email_subject="Reminder: {{ event }}",
            email_body_text="Your {{ event }} is coming up.",
            sms_body="Reminder: {{ event }} tomorrow!",
        )
        assert template.email_subject
        assert template.sms_body


@pytest.mark.django_db
class TestMessage:
    """Tests for Message model."""

    def test_message_creation(self, message_template):
        """Message can be created with required fields."""
        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body_text="Test body",
            template=message_template,
            status=MessageStatus.QUEUED,
        )
        assert message.pk is not None
        assert message.direction == MessageDirection.OUTBOUND
        assert message.channel == Channel.EMAIL

    def test_message_status_choices(self):
        """MessageStatus enum has expected values."""
        assert MessageStatus.QUEUED == "queued"
        assert MessageStatus.SENDING == "sending"
        assert MessageStatus.SENT == "sent"
        assert MessageStatus.DELIVERED == "delivered"
        assert MessageStatus.FAILED == "failed"
        assert MessageStatus.BOUNCED == "bounced"

    def test_channel_choices(self):
        """Channel enum has expected values."""
        assert Channel.EMAIL == "email"
        assert Channel.SMS == "sms"

    def test_message_direction_choices(self):
        """MessageDirection enum has expected values."""
        assert MessageDirection.OUTBOUND == "outbound"
        assert MessageDirection.INBOUND == "inbound"

    def test_message_without_template(self):
        """Message can be created without a template."""
        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Ad-hoc Subject",
            body_text="Ad-hoc body",
            status=MessageStatus.QUEUED,
        )
        assert message.template is None

    def test_message_with_html_body(self):
        """Message can have HTML body."""
        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="HTML Email",
            body_text="Plain text version",
            body_html="<h1>HTML version</h1>",
            status=MessageStatus.QUEUED,
        )
        assert message.body_html == "<h1>HTML version</h1>"

    def test_message_provider_fields(self):
        """Message stores provider information."""
        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            body_text="Test",
            status=MessageStatus.SENT,
            provider="ses",
            provider_message_id="abc123",
        )
        assert message.provider == "ses"
        assert message.provider_message_id == "abc123"

    def test_message_with_related_object(self, booking):
        """Message can be linked to a related object via GenericFK."""
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(booking)
        message = Message.objects.create(
            direction=MessageDirection.OUTBOUND,
            channel=Channel.EMAIL,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            body_text="Booking confirmation",
            status=MessageStatus.QUEUED,
            related_content_type=ct,
            related_object_id=str(booking.pk),
        )
        assert message.related_object == booking
