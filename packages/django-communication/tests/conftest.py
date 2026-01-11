"""Pytest configuration for django-communication tests."""

import pytest


@pytest.fixture
def settings_instance(db):
    """Create a CommunicationSettings instance."""
    from django_communication.models import CommunicationSettings

    settings, _ = CommunicationSettings.objects.get_or_create(
        defaults={
            "email_provider": "console",
            "email_from_address": "test@example.com",
            "email_from_name": "Test Sender",
            "sms_provider": "console",
            "default_channel": "email",
        }
    )
    return settings


@pytest.fixture
def person(db):
    """Create a test Person."""
    from django_parties.models import Person

    return Person.objects.create(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+15551234567",
    )


@pytest.fixture
def message_template(db):
    """Create a test MessageTemplate."""
    from django_communication.models import MessageTemplate

    return MessageTemplate.objects.create(
        key="test-welcome",
        name="Welcome Email",
        message_type="transactional",
        email_subject="Welcome, {{ name }}!",
        email_body_text="Hello {{ name }}, welcome to our service.",
        email_body_html="<p>Hello <strong>{{ name }}</strong>, welcome!</p>",
        sms_body="Welcome {{ name }}! Thanks for joining.",
        is_active=True,
    )


@pytest.fixture
def sms_template(db):
    """Create a test SMS template."""
    from django_communication.models import MessageTemplate

    return MessageTemplate.objects.create(
        key="reminder-sms",
        name="Appointment Reminder",
        message_type="reminder",
        sms_body="Reminder: Your appointment is tomorrow at {{ time }}.",
        is_active=True,
    )


@pytest.fixture
def booking(db):
    """Create a test booking for GenericFK testing."""
    from tests.testapp.models import TestBooking

    return TestBooking.objects.create(
        reference="BK-001",
        notes="Test booking",
    )
