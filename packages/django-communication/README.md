# django-communication

Unified multi-channel communication primitive for Django. Send emails, SMS, and more through a single API with automatic channel routing, template support, and full audit logging.

## Installation

```bash
pip install django-communication
```

Add to INSTALLED_APPS:

```python
INSTALLED_APPS = [
    ...,
    "django_basemodels",
    "django_singleton",
    "django_communication",
]
```

Run migrations:

```bash
python manage.py migrate django_communication
```

## Quick Start

```python
from django_communication import send
from django_parties.models import Person

# Get recipient (from django-parties)
person = Person.objects.get(email="customer@example.com")

# Send using a template
message = send(
    to=person,
    template_key="booking_confirmation",
    context={"booking_ref": "BK-001", "date": "2024-03-15"},
)

# Or send ad-hoc
message = send(
    to=person,
    subject="Your booking is confirmed",
    body_text="Thank you for your booking!",
)
```

## Features

- **Multi-channel**: Email and SMS (voice/IVR planned)
- **Template system**: Reusable templates with Django template syntax
- **Automatic routing**: Message type determines channel (transactional -> email, reminder -> SMS)
- **Audit trail**: Every message is logged with status tracking
- **Provider abstraction**: Console (dev), AWS SES (production), extensible
- **Related objects**: Link messages to bookings, orders, etc. via GenericFK

## Models

### CommunicationSettings (Singleton)

Global configuration for communication providers.

```python
from django_communication.models import CommunicationSettings

settings = CommunicationSettings.objects.first()
settings.email_provider = "ses"
settings.email_from_address = "noreply@example.com"
settings.ses_region = "us-east-1"
settings.save()
```

### MessageTemplate

Reusable templates for multi-channel content.

```python
from django_communication.models import MessageTemplate, MessageType

template = MessageTemplate.objects.create(
    key="booking_confirmation",
    name="Booking Confirmation",
    message_type=MessageType.TRANSACTIONAL,
    email_subject="Your booking {{ booking_ref }} is confirmed",
    email_body_text="Dear {{ customer_name }},\n\nYour booking is confirmed.",
    email_body_html="<p>Dear {{ customer_name }},</p><p>Your booking is confirmed.</p>",
    sms_body="Booking {{ booking_ref }} confirmed for {{ date }}",
)
```

### Message

Audit log of all sent/received messages.

```python
from django_communication.models import Message, MessageStatus

# Get messages for a booking
messages = Message.objects.filter(
    related_content_type=ContentType.objects.get_for_model(Booking),
    related_object_id=str(booking.pk),
)

# Find failed messages
failed = Message.objects.filter(status=MessageStatus.FAILED)
```

## Channel Routing

Messages are routed to channels based on:

1. **Explicit channel** parameter (highest priority)
2. **Message type** routing (based on template)
3. **Default channel** from settings

Default routing:

| Message Type | Channel |
|--------------|---------|
| transactional | email |
| reminder | sms |
| alert | sms |
| announcement | email |

## Providers

### Console (Development)

Logs messages to console instead of sending. Default for development.

```python
settings.email_provider = "console"
settings.sms_provider = "console"
```

### AWS SES (Email - Production)

```python
settings.email_provider = "ses"
settings.ses_access_key_id = "AKIAXXXXXXXX"
settings.ses_secret_access_key = "secret"
settings.ses_region = "us-east-1"
settings.ses_configuration_set = "tracking"  # optional
```

## API Reference

### send()

```python
from django_communication import send

message = send(
    to=person,                      # Person instance (required)
    template_key="welcome",         # Template key (optional)
    context={"name": "John"},       # Template context (optional)
    channel="email",                # Explicit channel override (optional)
    subject="Override subject",     # Override template subject (optional)
    body_text="Override body",      # Override template body (optional)
    body_html="<p>HTML</p>",        # Override HTML body (optional)
    related_object=booking,         # Link to model instance (optional)
)
```

### get_messages_for_object()

```python
from django_communication import get_messages_for_object

messages = get_messages_for_object(booking)
```

## Exceptions

```python
from django_communication import (
    CommunicationError,      # Base exception
    TemplateNotFoundError,   # Template doesn't exist or inactive
    InvalidRecipientError,   # Missing/invalid address for channel
    ProviderError,           # Provider failed to send
)
```

## Dependencies

- Django >= 4.2
- django-basemodels
- django-singleton
- django-parties (for Person model)
- boto3 (for SES provider)

## License

MIT
