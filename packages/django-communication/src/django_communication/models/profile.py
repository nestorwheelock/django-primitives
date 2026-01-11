"""Message Profile model for language-specific email identities.

Uses django-parties Demographics.preferred_language for recipient locale.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import models

from django_basemodels import BaseModel

if TYPE_CHECKING:
    from django_parties.models import Person


@dataclass(frozen=True)
class EmailIdentity:
    """Value object representing a resolved email identity.

    Immutable data container returned by MessageProfile.get_identity_for_locale().
    """

    from_name: str
    from_address: str
    reply_to: str | None
    ses_configuration_set: str | None
    locale: str
    profile_slug: str

    @property
    def formatted_from(self) -> str:
        """Return formatted 'Name <email>' string."""
        if self.from_name:
            return f"{self.from_name} <{self.from_address}>"
        return self.from_address


class MessageProfile(BaseModel):
    """A messaging identity profile for multi-language brand support.

    Each profile defines email identities for different languages,
    allowing a single communication pipeline to send with the
    appropriate brand/domain based on recipient locale.

    The recipient's preferred language comes from:
        Person.demographics.preferred_language (django-parties)

    Example:
        - transactional profile:
          - English: info@happydiving.mx
          - Spanish: hola@buceofeliz.com

    Usage:
        profile = MessageProfile.objects.get(slug="transactional")
        identity = profile.get_identity_for_locale("es")
        # identity.from_address = "hola@buceofeliz.com"
    """

    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Unique identifier (e.g., transactional, marketing)",
    )
    name = models.CharField(
        max_length=100,
        help_text="Display name for this profile",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of when this profile is used",
    )

    # === Sender Display Name ===
    from_name = models.CharField(
        max_length=100,
        help_text="Sender display name (e.g., 'Happy Diving')",
    )

    # === English Identity ===
    from_address_en = models.EmailField(
        help_text="Sender email for English messages",
    )
    reply_to_en = models.EmailField(
        blank=True,
        help_text="Reply-to address for English messages (optional)",
    )
    ses_configuration_set_en = models.CharField(
        max_length=100,
        blank=True,
        help_text="SES configuration set for English (optional)",
    )

    # === Spanish Identity ===
    from_address_es = models.EmailField(
        help_text="Sender email for Spanish messages",
    )
    reply_to_es = models.EmailField(
        blank=True,
        help_text="Reply-to address for Spanish messages (optional)",
    )
    ses_configuration_set_es = models.CharField(
        max_length=100,
        blank=True,
        help_text="SES configuration set for Spanish (optional)",
    )

    # === Status ===
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this profile can be used for sending",
    )

    class Meta:
        verbose_name = "Message Profile"
        verbose_name_plural = "Message Profiles"
        ordering = ["slug"]

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def get_identity_for_locale(self, locale: str | None) -> EmailIdentity:
        """Get the email identity for a specific locale.

        Args:
            locale: Language code ('en', 'es', 'en-US', etc). Defaults to 'en' if None/unknown.

        Returns:
            EmailIdentity with from_address, reply_to, and ses_configuration_set
        """
        # Normalize locale to just language code
        lang = locale.lower().split("-")[0] if locale else "en"

        if lang == "es":
            return EmailIdentity(
                from_name=self.from_name,
                from_address=self.from_address_es,
                reply_to=self.reply_to_es or None,
                ses_configuration_set=self.ses_configuration_set_es or None,
                locale="es",
                profile_slug=self.slug,
            )
        else:
            # Default to English for any non-Spanish locale
            return EmailIdentity(
                from_name=self.from_name,
                from_address=self.from_address_en,
                reply_to=self.reply_to_en or None,
                ses_configuration_set=self.ses_configuration_set_en or None,
                locale="en",
                profile_slug=self.slug,
            )


def get_recipient_locale(person: "Person") -> str:
    """Get recipient's preferred locale from django-parties Demographics.

    Args:
        person: A django_parties.Person instance

    Returns:
        Language code (e.g., 'en', 'es') or 'en' as default
    """
    try:
        if hasattr(person, "demographics") and person.demographics:
            lang = person.demographics.preferred_language
            if lang:
                return lang.lower().split("-")[0]
    except Exception:
        pass
    return "en"
