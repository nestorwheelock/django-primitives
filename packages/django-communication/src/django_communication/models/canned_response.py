"""CannedResponse model for reusable message snippets."""

from django.conf import settings
from django.db import models

from django_basemodels import BaseModel


class ResponseChannel(models.TextChoices):
    """Channels where canned responses can be used."""

    ANY = "any", "Any Channel"
    CHAT = "chat", "Chat/In-App"
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"


class Visibility(models.TextChoices):
    """Visibility scope for canned responses."""

    PRIVATE = "private", "Private (Creator Only)"
    ORG = "org", "Organization"
    PUBLIC = "public", "Public (All Users)"


class CannedResponseTag(BaseModel):
    """Tag for categorizing canned responses.

    Allows staff to quickly filter responses by topic
    (e.g., "Booking", "Payment", "FAQ", "Greeting").
    """

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Tag name (e.g., 'Booking', 'FAQ')",
    )

    class Meta:
        verbose_name = "Canned Response Tag"
        verbose_name_plural = "Canned Response Tags"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CannedResponse(BaseModel):
    """Reusable text snippet for conversations.

    Staff can insert canned responses into messages to save time.
    Supports variable substitution using {{ variable_name }} syntax.

    Scoping:
        - private: Only creator can use
        - org: Anyone in owner_party organization can use
        - public: Anyone in the system can use

    Variables:
        Body text can contain {{ variable_name }} placeholders.
        Variables are rendered using context providers configured
        in COMMUNICATION_CANNED_CONTEXT_PROVIDERS setting.

    Usage:
        from django_communication.services.canned_responses import (
            list_canned_responses,
            render_canned_response,
        )

        # Get available responses
        responses = list_canned_responses(actor=staff_person)

        # Render with context
        rendered = render_canned_response(
            response,
            {"first_name": "John", "trip_date": "March 15"},
        )
    """

    title = models.CharField(
        max_length=200,
        help_text="Short label shown in picker UI",
    )
    body = models.TextField(
        help_text="Message content with {{ variable }} placeholders",
    )
    channel = models.CharField(
        max_length=20,
        choices=ResponseChannel.choices,
        default=ResponseChannel.ANY,
        help_text="Which channel(s) this response is for",
    )
    language = models.CharField(
        max_length=10,
        blank=True,
        help_text="Language code (e.g., 'en', 'es'). Blank = all languages",
    )

    # === Scoping ===
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.ORG,
        help_text="Who can use this response",
    )
    owner_party = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="canned_responses",
        help_text="Organization that owns this response (for org visibility)",
    )
    created_by = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_canned_responses",
        help_text="Person who created this response",
    )

    # === Organization ===
    tags = models.ManyToManyField(
        CannedResponseTag,
        blank=True,
        related_name="canned_responses",
        help_text="Tags for filtering and organization",
    )

    # === Status ===
    is_active = models.BooleanField(
        default=True,
        help_text="Only active responses can be used",
    )

    class Meta:
        verbose_name = "Canned Response"
        verbose_name_plural = "Canned Responses"
        ordering = ["title"]
        indexes = [
            models.Index(fields=["visibility", "is_active"]),
            models.Index(fields=["owner_party", "is_active"]),
            models.Index(fields=["channel", "is_active"]),
            models.Index(fields=["created_by", "is_active"]),
        ]

    def __str__(self):
        return self.title
