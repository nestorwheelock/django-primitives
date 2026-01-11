"""Communication settings singleton model."""

from django.db import models

from django_singleton import SingletonModel


class CommunicationSettings(SingletonModel):
    """Global communication configuration.

    Singleton model storing all communication channel settings.
    Access via CommunicationSettings.get_instance().

    Email identity (from_address, reply_to) is now controlled via
    MessageProfile for multi-language support. The default_profile
    determines which profile to use when sending.
    """

    # === Default Message Profile ===
    default_profile = models.ForeignKey(
        "django_communication.MessageProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Default message profile for email identity (from address, reply-to)",
    )

    # === Email Settings ===
    email_enabled = models.BooleanField(
        default=False,
        help_text="Enable email sending",
    )
    email_provider = models.CharField(
        max_length=20,
        choices=[
            ("console", "Console (Development)"),
            ("ses_api", "Amazon SES (Production)"),
        ],
        default="console",
        help_text="Email delivery provider",
    )

    # === Legacy Email Fields (fallback if no profile) ===
    email_from_address = models.EmailField(
        blank=True,
        help_text="Fallback sender email (used if no profile set)",
    )
    email_from_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Fallback sender display name",
    )
    email_reply_to = models.EmailField(
        blank=True,
        help_text="Fallback reply-to address",
    )

    # === AWS SES Settings ===
    ses_region = models.CharField(
        max_length=20,
        blank=True,
        default="us-east-1",
        help_text="AWS region for SES",
    )
    ses_access_key_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="AWS access key ID",
    )
    ses_secret_access_key = models.CharField(
        max_length=100,
        blank=True,
        help_text="AWS secret access key",
    )
    ses_configuration_set = models.CharField(
        max_length=100,
        blank=True,
        help_text="SES configuration set for tracking (fallback, prefer profile)",
    )

    # === SMS Settings ===
    sms_enabled = models.BooleanField(
        default=False,
        help_text="Enable SMS sending",
    )
    sms_provider = models.CharField(
        max_length=20,
        choices=[
            ("console", "Console (Development)"),
        ],
        default="console",
        help_text="SMS delivery provider",
    )
    sms_from_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Default sender phone number (E.164 format)",
    )

    # === Routing ===
    default_channel = models.CharField(
        max_length=10,
        choices=[
            ("email", "Email"),
            ("sms", "SMS"),
        ],
        default="email",
        help_text="Default channel when not specified",
    )

    # === Sandbox Mode ===
    sandbox_mode = models.BooleanField(
        default=True,
        help_text="Log messages but don't actually send (for testing)",
    )

    # === Web Push Settings ===
    push_enabled = models.BooleanField(
        default=False,
        help_text="Enable Web Push notifications",
    )
    vapid_public_key = models.CharField(
        max_length=200,
        blank=True,
        help_text="VAPID public key for Web Push",
    )
    vapid_private_key = models.CharField(
        max_length=200,
        blank=True,
        help_text="VAPID private key for Web Push (keep secret!)",
    )
    vapid_contact_email = models.EmailField(
        blank=True,
        help_text="Contact email for VAPID claims",
    )

    # === Notification Fallback Settings ===
    notification_fallback_enabled = models.BooleanField(
        default=True,
        help_text="Enable fallback from push to email/SMS when push fails",
    )
    push_failure_threshold = models.PositiveIntegerField(
        default=3,
        help_text="Deactivate subscription after this many consecutive failures",
    )

    class Meta:
        verbose_name = "Communication Settings"
        verbose_name_plural = "Communication Settings"

    def __str__(self):
        channels = []
        if self.email_enabled:
            channels.append(f"email:{self.email_provider}")
        if self.sms_enabled:
            channels.append(f"sms:{self.sms_provider}")
        return f"CommunicationSettings ({', '.join(channels) or 'all disabled'})"

    def is_email_configured(self) -> bool:
        """Check if email is properly configured.

        Email is configured if:
        - email_enabled is True
        - Either a default_profile is set OR fallback email_from_address is set
        - For SES: AWS credentials are present
        """
        if not self.email_enabled:
            return False
        # Need either a profile or fallback from_address
        has_identity = bool(self.default_profile_id) or bool(self.email_from_address)
        if not has_identity:
            return False
        if self.email_provider == "ses_api":
            return bool(self.ses_access_key_id and self.ses_secret_access_key)
        return True

    def is_sms_configured(self) -> bool:
        """Check if SMS is properly configured."""
        if not self.sms_enabled:
            return False
        if not self.sms_from_number:
            return False
        return True

    def is_push_configured(self) -> bool:
        """Check if Web Push is properly configured.

        Push is configured when:
        - push_enabled is True
        - VAPID public key is set
        - VAPID private key is set
        - VAPID contact email is set
        """
        return bool(
            self.push_enabled
            and self.vapid_public_key
            and self.vapid_private_key
            and self.vapid_contact_email
        )
