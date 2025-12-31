"""Models for django-singleton."""

from django.db import IntegrityError, models, transaction

from .exceptions import SingletonDeletionError, SingletonViolationError


class SingletonModel(models.Model):
    """
    Abstract base for singleton settings models.

    Enforces pk=1, provides get_instance() for safe access.
    Raises on delete. Raises if multiple rows detected.

    Usage:
        class MySettings(SingletonModel):
            setting_field = models.CharField(max_length=100)

        # Access the singleton
        settings = MySettings.get_instance()
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Enforce pk=1
        self.pk = 1

        # Check for existing rows with wrong pk (corruption from bulk ops/fixtures)
        existing = self.__class__.objects.exclude(pk=1).exists()
        if existing:
            raise SingletonViolationError(
                f"Multiple rows exist for singleton {self.__class__.__name__}. "
                "Remove extra rows before saving."
            )

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise SingletonDeletionError(
            f"Cannot delete singleton {self.__class__.__name__}"
        )

    @classmethod
    def get_instance(cls):
        """
        Get or create the singleton instance.

        Handles race conditions via IntegrityError retry.

        Returns:
            The singleton instance (pk=1)
        """
        try:
            with transaction.atomic():
                obj, _ = cls.objects.get_or_create(pk=1)
                return obj
        except IntegrityError:
            # Race condition: another process created it
            return cls.objects.get(pk=1)
