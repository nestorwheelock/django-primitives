"""Profile models for user preferences and settings."""

import uuid

from django.conf import settings
from django.db import models


class UserPreferences(models.Model):
    """User preferences and settings.

    Stores per-user configuration that applies across all contexts
    (customer portal, staff portal, admin).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
    )

    # Profile photo (stored in django-documents)
    profile_photo = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    # Timezone preference
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="User's preferred timezone",
    )

    # Notification preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications",
    )
    marketing_emails = models.BooleanField(
        default=False,
        help_text="Receive marketing and promotional emails",
    )

    # UI preferences
    dark_mode = models.BooleanField(
        default=False,
        help_text="Use dark mode interface",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "user preferences"
        verbose_name_plural = "user preferences"

    def __str__(self):
        return f"Preferences for {self.user.email}"


def get_user_preferences(user):
    """Get or create preferences for a user."""
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    return prefs
