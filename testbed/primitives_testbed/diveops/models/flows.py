"""Flow models for agreement-triggered conversation workflows.

This module contains:
- FlowType: Named workflow types that can trigger conversations
- FlowThread: Links a customer's flow instance to a conversation

Flows provide a way to track customer onboarding processes, medical clearances,
and other multi-step workflows through dedicated conversations.
"""

from django.db import models
from django.db.models import Q

from django_basemodels import BaseModel


class FlowType(BaseModel):
    """Named workflow types that can trigger conversations.

    Flow types define categories of workflows like "Medical Onboarding" or
    "New Diver Setup". When an agreement associated with a flow type is sent,
    a conversation is automatically created for the customer.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class Category(models.TextChoices):
        ONBOARDING = "onboarding", "New Diver Onboarding"
        MEDICAL = "medical", "Medical Clearance"
        LIABILITY = "liability", "Liability Waiver"
        BOOKING = "booking", "Booking Confirmation"
        CERTIFICATION = "certification", "Certification Process"
        CUSTOM = "custom", "Custom Flow"

    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.CASCADE,
        related_name="flow_types",
        help_text="Dive shop that owns this flow type",
    )
    name = models.CharField(
        max_length=100,
        help_text="Display name (e.g., 'Medical Onboarding', 'New Diver Setup')",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.CUSTOM,
        help_text="Category of flow",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this flow accomplishes",
    )

    # Conversation settings
    auto_create_conversation = models.BooleanField(
        default=True,
        help_text="Create conversation automatically when flow starts",
    )
    conversation_subject_template = models.CharField(
        max_length=200,
        default="{flow_name} - {customer_name}",
        help_text="Template for conversation subject. Variables: {flow_name}, {customer_name}",
    )

    # Linked agreement templates (optional)
    agreement_templates = models.ManyToManyField(
        "diveops.AgreementTemplate",
        blank=True,
        related_name="flow_types",
        help_text="Agreement templates required for this flow",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this flow type is currently active",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Flow Type"
        verbose_name_plural = "Flow Types"
        constraints = [
            models.UniqueConstraint(
                fields=["dive_shop", "name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_flow_type_per_shop",
            ),
        ]
        indexes = [
            models.Index(fields=["dive_shop", "is_active"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.dive_shop.name})"


class FlowThread(BaseModel):
    """Links a customer's flow instance to a conversation.

    Represents a single customer's journey through a flow type.
    The conversation provides a communication channel for that flow.

    Key behaviors:
    - One active thread per customer per flow type
    - Conversation created when flow starts
    - System messages post updates (agreement sent, signed, etc.)
    - Completes when all required steps are done

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    flow_type = models.ForeignKey(
        FlowType,
        on_delete=models.PROTECT,
        related_name="threads",
        help_text="The type of flow this thread represents",
    )
    customer = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.CASCADE,
        related_name="flow_threads",
        help_text="The customer going through this flow",
    )
    conversation = models.OneToOneField(
        "django_communication.Conversation",
        on_delete=models.CASCADE,
        related_name="flow_thread",
        help_text="The conversation for this flow",
    )

    # Progress tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Current status of this flow",
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this flow was started",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this flow was completed",
    )

    # Optional: link to triggering agreement
    triggered_by_agreement = models.ForeignKey(
        "diveops.SignableAgreement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flow_threads",
        help_text="Agreement that triggered this flow (if any)",
    )

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Flow Thread"
        verbose_name_plural = "Flow Threads"
        constraints = [
            # One active thread per customer per flow type
            models.UniqueConstraint(
                fields=["flow_type", "customer"],
                condition=Q(status="active") & Q(deleted_at__isnull=True),
                name="unique_active_flow_per_customer",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["flow_type", "status"]),
            models.Index(fields=["status", "started_at"]),
        ]

    def __str__(self):
        return f"{self.flow_type.name} for {self.customer}"
