"""Time semantics mixins for Django models."""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimeSemanticsMixin(models.Model):
    """
    Abstract mixin providing dual timestamps for business facts.

    Every fact in the system has two timestamps:
    - effective_at: When the fact is true in the business world (can be backdated)
    - recorded_at: When the system learned the fact (auto_now_add, immutable)

    From TIME_SEMANTICS.md:
    - effective_at defaults to timezone.now(), can be overridden for backdating
    - recorded_at is sacred: always auto_now_add=True, never allow override
    """

    effective_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the fact is true in the business world"
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the system learned the fact"
    )

    class Meta:
        abstract = True


class EffectiveDatedMixin(TimeSemanticsMixin):
    """
    Abstract mixin for records with validity periods.

    Provides valid_from/valid_to for temporal records that have a
    window of validity. Inherits effective_at/recorded_at from TimeSemanticsMixin.

    Rules from TIME_SEMANTICS.md:
    - valid_from is required: When does this record become effective?
    - valid_to is nullable: Null means "until further notice"
    - No overlaps: Enforce via database constraint or application logic
    - Close old before opening new: When updating, set old record's valid_to
      before creating new
    """

    valid_from = models.DateTimeField(
        db_index=True,
        help_text="When this record becomes effective"
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When this record expires (null = until further notice)"
    )

    class Meta:
        abstract = True

    def clean(self):
        """Validate that valid_to > valid_from when both are set."""
        super().clean()
        if self.valid_to is not None and self.valid_from is not None:
            if self.valid_to <= self.valid_from:
                raise ValidationError({
                    'valid_to': 'valid_to must be greater than valid_from'
                })
