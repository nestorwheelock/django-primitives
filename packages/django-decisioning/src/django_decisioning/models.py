"""Decision and IdempotencyKey models."""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


# PRIMITIVES: allow-plain-model
class IdempotencyKey(models.Model):
    """
    Prevents duplicate operations from retries.

    State machine: pending -> processing -> succeeded/failed

    From POSTGRES_GOTCHAS.md:
    - Use select_for_update() when acquiring the lock
    - result_id uses CharField for UUID support

    Usage:
        # In @idempotent decorator:
        with transaction.atomic():
            idem, created = IdempotencyKey.objects.select_for_update().get_or_create(
                scope=scope,
                key=key,
                defaults={'state': IdempotencyKey.State.PROCESSING, 'locked_at': timezone.now()}
            )
            if not created and idem.state == IdempotencyKey.State.SUCCEEDED:
                return idem.response_snapshot  # Replay cached result
    """

    class State(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    # Identity
    scope = models.CharField(
        max_length=100,
        help_text="Operation scope, e.g., 'basket_commit', 'payment'"
    )
    key = models.CharField(
        max_length=255,
        help_text="Client-provided or derived idempotency key"
    )
    request_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hash of request body for mismatch detection"
    )

    # Timestamps  # PRIMITIVES: allow-manual-timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this key can be cleaned up"
    )

    # State tracking
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.PENDING
    )
    locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing started (for stale lock detection)"
    )

    # Error handling
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    # Response caching for replay
    response_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Cached response for successful operations"
    )

    # Result reference (what was created)
    result_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="ContentType of the created object"
    )
    result_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID of created object (CharField for UUID support)"
    )

    class Meta:
        unique_together = ['scope', 'key']
        indexes = [
            models.Index(fields=['scope', 'key']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['state']),
        ]

    def __str__(self):
        return f"{self.scope}:{self.key} ({self.state})"


# PRIMITIVES: allow-plain-model
class Decision(models.Model):
    """
    Generic decision record for any decision surface.

    Records who made what decision, when, about what target,
    with immutable snapshot evidence.

    From CONTRACT.md:
    - Every decision surface must be auditable
    - Snapshots are required at the boundary

    From POSTGRES_GOTCHAS.md:
    - target_id uses CharField(max_length=255) for UUID support
    - Uses AUTH_USER_MODEL, not direct User import
    """

    # Time semantics (manual since we can't use multiple inheritance easily)
    from django.utils import timezone
    effective_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the decision was effective in the business world"
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the system recorded the decision"
    )

    # Authority - who made the decision
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='decisions_as_actor',
        help_text="User who made the decision"
    )
    # actor_party can be added if django-parties is installed
    on_behalf_of_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='decisions_on_behalf',
        help_text="User on whose behalf the decision was made (delegation)"
    )
    authority_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Role/org snapshot at decision time"
    )

    # Target - what was decided about (GenericFK with CharField for UUID)
    target_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        help_text="ContentType of the target object"
    )
    target_id = models.CharField(
        max_length=255,
        help_text="ID of target object (CharField for UUID support)"
    )
    target = GenericForeignKey('target_type', 'target_id')

    # Outcome
    action = models.CharField(
        max_length=50,
        help_text="Action taken: 'commit', 'approve', 'reverse', etc."
    )
    snapshot = models.JSONField(
        help_text="Immutable evidence of inputs at decision time"
    )
    outcome = models.JSONField(
        default=dict,
        blank=True,
        help_text="Result reference (e.g., created work item IDs)"
    )

    # Finality
    finalized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the decision became permanent"
    )

    class Meta:
        indexes = [
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['actor_user']),
            models.Index(fields=['action']),
            models.Index(fields=['effective_at']),
        ]

    def __str__(self):
        return f"{self.action} on {self.target_type}:{self.target_id}"

    @property
    def is_final(self):
        """Check if the decision is finalized (permanent)."""
        return self.finalized_at is not None

    def clean(self):
        """Validate decision record."""
        super().clean()

        # At least one actor must be present
        if not self.actor_user:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                "Decision must have at least one actor (actor_user required)"
            )
