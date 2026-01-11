"""Tests for MessageOrchestrator - unified event-driven communication."""

import pytest
from django.utils import timezone


@pytest.fixture
def customer(db):
    """Create a test customer person."""
    from django_parties.models import Person

    return Person.objects.create(
        first_name="Alice",
        last_name="Customer",
        email="alice@example.com",
        phone="+15551234567",
    )


@pytest.fixture
def staff(db):
    """Create a test staff person."""
    from django_parties.models import Person

    return Person.objects.create(
        first_name="Bob",
        last_name="Staff",
        email="bob@diveshop.com",
    )


@pytest.fixture
def comm_settings(db):
    """Create communication settings."""
    from django_communication.models import CommunicationSettings

    return CommunicationSettings.objects.create(
        email_enabled=True,
        email_provider="console",
        email_from_address="noreply@diveshop.com",
        sandbox_mode=True,
    )


@pytest.fixture
def event_template(db):
    """Create a template keyed by event_type."""
    from django_communication.models import MessageTemplate, MessageType

    return MessageTemplate.objects.create(
        key="class_signup_started",
        name="Class Signup Started",
        message_type=MessageType.TRANSACTIONAL,
        event_type="class.signup.started",
        email_subject="Welcome to {{ class_name }}!",
        email_body_text="Hi {{ first_name }},\n\nYou're signed up for {{ class_name }} on {{ class_date }}.",
        email_body_html="<p>Hi {{ first_name }},</p><p>You're signed up for <strong>{{ class_name }}</strong> on {{ class_date }}.</p>",
    )


@pytest.mark.django_db
class TestMessageTemplateEventType:
    """Tests for event_type field on MessageTemplate."""

    def test_template_with_event_type(self, db):
        """MessageTemplate can have an event_type."""
        from django_communication.models import MessageTemplate, MessageType

        template = MessageTemplate.objects.create(
            key="booking_confirmation",
            name="Booking Confirmation",
            message_type=MessageType.TRANSACTIONAL,
            event_type="booking.confirmed",
            email_subject="Booking Confirmed",
            email_body_text="Your booking is confirmed.",
        )
        assert template.event_type == "booking.confirmed"

    def test_template_without_event_type(self, db):
        """MessageTemplate can work without event_type (manual use)."""
        from django_communication.models import MessageTemplate, MessageType

        template = MessageTemplate.objects.create(
            key="manual_template",
            name="Manual Template",
            message_type=MessageType.TRANSACTIONAL,
            email_subject="Hello",
            email_body_text="Hello world.",
        )
        assert template.event_type == ""

    def test_find_template_by_event_type(self, event_template):
        """Can find templates by event_type."""
        from django_communication.models import MessageTemplate

        found = MessageTemplate.objects.filter(
            event_type="class.signup.started",
            is_active=True,
        ).first()
        assert found is not None
        assert found.key == "class_signup_started"


@pytest.mark.django_db
class TestOrchestrate:
    """Tests for the orchestrate() service function."""

    def test_orchestrate_sends_message(self, customer, comm_settings, event_template):
        """orchestrate() creates and sends a message for an event."""
        from django_communication.services.orchestrator import orchestrate

        messages = orchestrate(
            event_type="class.signup.started",
            subject=customer,
            context={
                "first_name": "Alice",
                "class_name": "Open Water Diver",
                "class_date": "March 15, 2025",
            },
        )

        assert len(messages) == 1
        msg = messages[0]
        assert msg.to_address == "alice@example.com"
        assert "Open Water Diver" in msg.body_text
        assert msg.template == event_template

    def test_orchestrate_no_template_returns_empty(self, customer, comm_settings):
        """orchestrate() returns empty list when no template matches event."""
        from django_communication.services.orchestrator import orchestrate

        messages = orchestrate(
            event_type="nonexistent.event",
            subject=customer,
            context={},
        )

        assert messages == []

    def test_orchestrate_uses_context_providers(self, customer, comm_settings, event_template, settings):
        """orchestrate() merges context from configured providers."""
        from django_communication.services.orchestrator import orchestrate

        # Configure a test context provider
        settings.COMMUNICATION_CONTEXT_PROVIDERS = [
            "tests.test_orchestrator.test_context_provider",
        ]

        messages = orchestrate(
            event_type="class.signup.started",
            subject=customer,
            context={
                "class_name": "Advanced Diver",
                "class_date": "April 1, 2025",
            },
        )

        assert len(messages) == 1
        # first_name should come from provider
        assert "Alice" in messages[0].body_text

    def test_orchestrate_with_conversation(self, customer, staff, comm_settings, event_template):
        """orchestrate() can post message to a conversation."""
        from django_communication.models import Conversation
        from django_communication.services.orchestrator import orchestrate

        conv = Conversation.objects.create(subject="Class Enrollment")

        messages = orchestrate(
            event_type="class.signup.started",
            subject=customer,
            context={
                "first_name": "Alice",
                "class_name": "Open Water",
                "class_date": "March 15",
            },
            conversation=conv,
        )

        assert len(messages) == 1
        assert messages[0].conversation == conv

    def test_orchestrate_with_actor(self, customer, staff, comm_settings, event_template):
        """orchestrate() records the actor (staff who triggered the event)."""
        from django_communication.services.orchestrator import orchestrate

        messages = orchestrate(
            event_type="class.signup.started",
            actor=staff,
            subject=customer,
            context={
                "first_name": "Alice",
                "class_name": "Rescue Diver",
                "class_date": "May 1",
            },
        )

        assert len(messages) == 1
        # Message should record who initiated it (via sender or metadata)

    def test_orchestrate_respects_channel_preference(self, customer, comm_settings, event_template):
        """orchestrate() can use channel from context."""
        from django_communication.services.orchestrator import orchestrate

        messages = orchestrate(
            event_type="class.signup.started",
            subject=customer,
            context={
                "first_name": "Alice",
                "class_name": "Night Diver",
                "class_date": "June 1",
                "channel_preference": "email",
            },
        )

        assert len(messages) == 1
        assert messages[0].channel == "email"


@pytest.mark.django_db
class TestMultiChannelTemplates:
    """Tests for templates with multiple channel content."""

    def test_template_with_email_and_sms(self, customer, comm_settings, db):
        """Template can have both email and SMS content."""
        from django_communication.models import MessageTemplate, MessageType
        from django_communication.services.orchestrator import orchestrate

        MessageTemplate.objects.create(
            key="appointment_reminder",
            name="Appointment Reminder",
            message_type=MessageType.REMINDER,
            event_type="appointment.reminder",
            email_subject="Reminder: {{ appointment_type }} tomorrow",
            email_body_text="Hi {{ first_name }}, reminder about your {{ appointment_type }}.",
            sms_body="Reminder: {{ appointment_type }} tomorrow at {{ time }}. Reply STOP to unsubscribe.",
        )

        # Enable SMS
        comm_settings.sms_enabled = True
        comm_settings.sms_provider = "console"
        comm_settings.sms_from_number = "+15559999999"
        comm_settings.save()

        messages = orchestrate(
            event_type="appointment.reminder",
            subject=customer,
            context={
                "first_name": "Alice",
                "appointment_type": "dive lesson",
                "time": "2:00 PM",
            },
        )

        # Should send via SMS for reminders (default routing)
        assert len(messages) >= 1


@pytest.mark.django_db
class TestOrchestratorFallback:
    """Tests for notification fallback ladder."""

    def test_uses_email_for_transactional_messages(self, customer, comm_settings, db):
        """Transactional messages route to email by default."""
        from django_communication.models import MessageTemplate, MessageType
        from django_communication.services.orchestrator import orchestrate

        MessageTemplate.objects.create(
            key="new_message_notification",
            name="New Message",
            message_type=MessageType.TRANSACTIONAL,
            event_type="conversation.new_message",
            email_subject="New message from {{ sender_name }}",
            email_body_text="You have a new message from {{ sender_name }}.",
        )

        messages = orchestrate(
            event_type="conversation.new_message",
            subject=customer,
            context={"sender_name": "Dive Shop"},
        )

        # Transactional routes to email by default
        assert len(messages) == 1
        assert messages[0].channel == "email"


@pytest.mark.django_db
class TestOrchestratorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_orchestrate_missing_required_context(self, customer, comm_settings, event_template):
        """orchestrate() handles missing template variables gracefully."""
        from django_communication.services.orchestrator import orchestrate

        # Don't provide first_name - should render as blank
        messages = orchestrate(
            event_type="class.signup.started",
            subject=customer,
            context={
                "class_name": "Open Water",
                "class_date": "March 15",
            },
        )

        assert len(messages) == 1
        # Should still send, with blank for missing variable

    def test_orchestrate_inactive_template_ignored(self, customer, comm_settings, db):
        """orchestrate() ignores inactive templates."""
        from django_communication.models import MessageTemplate, MessageType
        from django_communication.services.orchestrator import orchestrate

        MessageTemplate.objects.create(
            key="disabled_event",
            name="Disabled Event",
            message_type=MessageType.TRANSACTIONAL,
            event_type="disabled.event",
            email_subject="This is disabled",
            email_body_text="Should not be sent.",
            is_active=False,
        )

        messages = orchestrate(
            event_type="disabled.event",
            subject=customer,
            context={},
        )

        assert messages == []

    def test_orchestrate_no_valid_recipient_address(self, comm_settings, db):
        """orchestrate() returns empty when recipient has no valid address."""
        from django_parties.models import Person
        from django_communication.models import MessageTemplate, MessageType
        from django_communication.services.orchestrator import orchestrate

        # Person without email
        person_no_email = Person.objects.create(
            first_name="NoEmail",
            last_name="Person",
        )

        MessageTemplate.objects.create(
            key="email_only_event",
            name="Email Only",
            message_type=MessageType.TRANSACTIONAL,
            event_type="email.only.event",
            email_subject="Test",
            email_body_text="Test body",
        )

        messages = orchestrate(
            event_type="email.only.event",
            subject=person_no_email,
            context={},
        )

        # Should return empty or log warning - can't send email without address
        assert messages == []


# Test context provider for test_orchestrate_uses_context_providers
def test_context_provider(*, subject=None, actor=None, conversation=None, extra=None):
    """Test context provider that adds person info."""
    context = {}
    if subject:
        context["first_name"] = getattr(subject, "first_name", "")
        context["last_name"] = getattr(subject, "last_name", "")
        context["email"] = getattr(subject, "email", "")
    return context
