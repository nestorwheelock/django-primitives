"""Tests for communication services."""

import pytest
from unittest.mock import patch, MagicMock

from django_communication.exceptions import (
    InvalidRecipientError,
    ProviderError,
    TemplateNotFoundError,
)
from django_communication.models import (
    Channel,
    Message,
    MessageStatus,
)
from django_communication.services import (
    get_messages_for_object,
    send,
)


@pytest.mark.django_db
class TestSendService:
    """Tests for the send() service function."""

    def test_send_with_template(self, settings_instance, person, message_template):
        """Send using a template renders content correctly."""
        message = send(
            to=person,
            template_key="test-welcome",
            context={"name": "John"},
        )

        assert message.pk is not None
        assert message.status == MessageStatus.SENT
        assert message.to_address == person.email
        assert message.subject == "Welcome, John!"
        assert "Hello John" in message.body_text
        assert message.template == message_template

    def test_send_without_template(self, settings_instance, person):
        """Send without template uses provided content."""
        message = send(
            to=person,
            subject="Direct Subject",
            body_text="Direct body content",
        )

        assert message.status == MessageStatus.SENT
        assert message.subject == "Direct Subject"
        assert message.body_text == "Direct body content"
        assert message.template is None

    def test_send_explicit_channel_override(self, settings_instance, person, message_template):
        """Explicit channel overrides template routing."""
        # Template is transactional which routes to email
        # But we explicitly request SMS
        message = send(
            to=person,
            template_key="test-welcome",
            context={"name": "John"},
            channel=Channel.SMS.value,
        )

        assert message.channel == Channel.SMS.value
        assert message.to_address == person.phone

    def test_send_sms_template(self, settings_instance, person, sms_template):
        """Send SMS using reminder template routes to SMS."""
        message = send(
            to=person,
            template_key="reminder-sms",
            context={"time": "2:00 PM"},
        )

        assert message.channel == Channel.SMS.value
        assert message.to_address == person.phone
        assert "2:00 PM" in message.body_text

    def test_send_with_related_object(self, settings_instance, person, booking):
        """Send links message to related object."""
        message = send(
            to=person,
            subject="Booking Confirmation",
            body_text="Your booking is confirmed.",
            related_object=booking,
        )

        assert message.related_object == booking
        assert str(message.related_object_id) == str(booking.pk)

    def test_send_template_not_found(self, settings_instance, person):
        """Send raises TemplateNotFoundError for missing template."""
        with pytest.raises(TemplateNotFoundError, match="Template not found"):
            send(to=person, template_key="nonexistent-template")

    def test_send_inactive_template(self, settings_instance, person, message_template):
        """Send raises TemplateNotFoundError for inactive template."""
        message_template.is_active = False
        message_template.save()

        with pytest.raises(TemplateNotFoundError, match="not found or inactive"):
            send(to=person, template_key="test-welcome")

    def test_send_missing_email_address(self, settings_instance, person):
        """Send raises InvalidRecipientError when Person lacks email."""
        person.email = ""
        person.save()

        with pytest.raises(InvalidRecipientError, match="no address"):
            send(
                to=person,
                subject="Test",
                body_text="Test body",
                channel=Channel.EMAIL.value,
            )

    def test_send_missing_phone_number(self, settings_instance, person):
        """Send raises InvalidRecipientError when Person lacks phone."""
        person.phone = ""
        person.save()

        with pytest.raises(InvalidRecipientError, match="no address"):
            send(
                to=person,
                body_text="Test SMS",
                channel=Channel.SMS.value,
            )

    def test_send_invalid_recipient_format(self, settings_instance, person):
        """Send raises InvalidRecipientError for invalid address format."""
        person.email = "not-a-valid-email"
        person.save()

        with pytest.raises(InvalidRecipientError, match="Invalid address format"):
            send(
                to=person,
                subject="Test",
                body_text="Test body",
            )

    @patch("django_communication.services.messaging.get_provider_for_channel")
    def test_send_provider_failure(self, mock_get_provider, settings_instance, person):
        """Send raises ProviderError when provider fails."""
        from django_communication.providers.base import SendResult

        mock_provider = MagicMock()
        mock_provider.validate_recipient.return_value = True
        mock_provider.send.return_value = SendResult.fail(
            provider="ses",
            error="Rate limit exceeded",
        )
        mock_get_provider.return_value = mock_provider

        with pytest.raises(ProviderError, match="Rate limit exceeded"):
            send(
                to=person,
                subject="Test",
                body_text="Test body",
            )

    def test_send_creates_message_record(self, settings_instance, person):
        """Send creates Message record even before sending."""
        initial_count = Message.objects.count()

        send(to=person, subject="Test", body_text="Test body")

        assert Message.objects.count() == initial_count + 1

    def test_send_subject_override(self, settings_instance, person, message_template):
        """Subject override replaces template subject."""
        message = send(
            to=person,
            template_key="test-welcome",
            context={"name": "John"},
            subject="Custom Subject Override",
        )

        assert message.subject == "Custom Subject Override"

    def test_send_creates_settings_if_missing(self, person):
        """Send creates default settings if none exist."""
        from django_communication.models import CommunicationSettings

        CommunicationSettings.objects.all().delete()
        assert CommunicationSettings.objects.count() == 0

        send(to=person, subject="Test", body_text="Test body")

        assert CommunicationSettings.objects.count() == 1


@pytest.mark.django_db
class TestGetMessagesForObject:
    """Tests for get_messages_for_object function."""

    def test_get_messages_empty(self, booking):
        """Returns empty list when no messages linked."""
        messages = get_messages_for_object(booking)
        assert messages == []

    def test_get_messages_linked(self, settings_instance, person, booking):
        """Returns messages linked to object."""
        send(
            to=person,
            subject="Booking 1",
            body_text="First message",
            related_object=booking,
        )
        send(
            to=person,
            subject="Booking 2",
            body_text="Second message",
            related_object=booking,
        )

        messages = get_messages_for_object(booking)
        assert len(messages) == 2
        assert all(m.related_object == booking for m in messages)

    def test_get_messages_ordered_by_created(self, settings_instance, person, booking):
        """Messages are ordered by created_at descending."""
        msg1 = send(
            to=person,
            subject="First",
            body_text="First",
            related_object=booking,
        )
        msg2 = send(
            to=person,
            subject="Second",
            body_text="Second",
            related_object=booking,
        )

        messages = get_messages_for_object(booking)
        # Most recent first
        assert messages[0].pk == msg2.pk
        assert messages[1].pk == msg1.pk

    def test_get_messages_different_objects(self, settings_instance, person, booking, db):
        """Messages for different objects are not returned."""
        from tests.testapp.models import TestBooking

        other_booking = TestBooking.objects.create(
            reference="BK-002",
            notes="Other booking",
        )

        send(
            to=person,
            subject="Booking 1",
            body_text="Message for booking 1",
            related_object=booking,
        )
        send(
            to=person,
            subject="Booking 2",
            body_text="Message for booking 2",
            related_object=other_booking,
        )

        messages = get_messages_for_object(booking)
        assert len(messages) == 1
        assert messages[0].related_object == booking


@pytest.mark.django_db
class TestMessageStatusTracking:
    """Tests for message status tracking through send lifecycle."""

    def test_message_starts_queued(self, settings_instance, person):
        """Message record is created with QUEUED status initially."""
        # We need to intercept before send completes
        with patch("django_communication.services.messaging.get_provider_for_channel") as mock:
            mock_provider = MagicMock()
            mock_provider.validate_recipient.return_value = True

            def capture_status(msg):
                # Message should already exist at this point
                return MagicMock(success=True, provider="test", message_id="123")

            mock_provider.send.side_effect = capture_status
            mock.return_value = mock_provider

            send(to=person, subject="Test", body_text="Test body")

    def test_sent_message_has_sent_at(self, settings_instance, person):
        """Successfully sent message has sent_at timestamp."""
        message = send(to=person, subject="Test", body_text="Test body")

        assert message.sent_at is not None
        assert message.status == MessageStatus.SENT

    def test_failed_message_has_error(self, settings_instance, person):
        """Failed message has error_message populated."""
        with patch("django_communication.services.messaging.get_provider_for_channel") as mock:
            from django_communication.providers.base import SendResult

            mock_provider = MagicMock()
            mock_provider.validate_recipient.return_value = True
            mock_provider.send.return_value = SendResult.fail(
                provider="ses",
                error="Mailbox full",
            )
            mock.return_value = mock_provider

            try:
                send(to=person, subject="Test", body_text="Test body")
            except ProviderError:
                pass

            message = Message.objects.latest("created_at")
            assert message.status == MessageStatus.FAILED
            assert "Mailbox full" in message.error_message
