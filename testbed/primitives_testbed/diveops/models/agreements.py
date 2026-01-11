"""Agreement-related models for diveops.

This module contains models for agreement templates, signable agreements,
agreement revisions, and document retention/legal hold policies.
"""

import hashlib
import secrets

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone

from django_basemodels import BaseModel

from .base import DIVEOPS_WAIVER_VALIDITY_DAYS  # noqa: F401 - exported for convenience


# =============================================================================
# Agreement Template Models
# =============================================================================


class AgreementTemplate(BaseModel):
    """Template for agreement paperwork (waivers, releases, questionnaires).

    Agreement templates define the reusable content for standard forms that
    divers sign. When a diver needs to sign paperwork, an Agreement is created
    from this template using django_agreements.

    Template types:
    - waiver: Liability waivers/releases
    - medical: Medical questionnaires (RSTC form)
    - briefing: Briefing acknowledgment forms
    - code_of_conduct: Diver code of conduct agreements
    - rental: Equipment rental agreements
    - training: Training/certification agreements

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class TemplateType(models.TextChoices):
        WAIVER = "waiver", "Liability Waiver"
        MEDICAL = "medical", "Medical Questionnaire"
        BRIEFING = "briefing", "Briefing Acknowledgment"
        CODE_OF_CONDUCT = "code_of_conduct", "Diver Code of Conduct"
        RENTAL = "rental", "Equipment Rental Agreement"
        TRAINING = "training", "Training Agreement"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class TargetPartyType(models.TextChoices):
        DIVER = "diver", "Diver"
        EMPLOYEE = "employee", "Employee"
        VENDOR = "vendor", "Vendor"
        ANY = "any", "Any Party"

    class DiverCategory(models.TextChoices):
        """Which category of diver needs this waiver/agreement."""
        ALL = "all", "All Divers"
        CERTIFIED = "certified", "Certified Divers Only"
        STUDENT = "student", "Students in Training"
        DSD = "dsd", "Discover Scuba (DSD/Try Dive)"

    # Ownership
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="agreement_templates",
    )

    # Identity
    name = models.CharField(
        max_length=100,
        help_text="Template name (e.g., 'Standard Liability Release')",
    )
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        help_text="Type of agreement this template is for",
    )
    target_party_type = models.CharField(
        max_length=20,
        choices=TargetPartyType.choices,
        default=TargetPartyType.DIVER,
        help_text="Type of party who should sign this template (diver, employee, vendor)",
    )
    diver_category = models.CharField(
        max_length=20,
        choices=DiverCategory.choices,
        default=DiverCategory.ALL,
        help_text="Which diver category needs this agreement (for waivers)",
    )
    description = models.TextField(
        blank=True,
        help_text="Internal description or notes about this template",
    )

    # Content
    content = models.TextField(
        help_text="The agreement text/content (supports HTML)",
    )

    # Requirements
    requires_signature = models.BooleanField(
        default=True,
        help_text="Does this form require a signature?",
    )
    requires_initials = models.BooleanField(
        default=False,
        help_text="Does this form require initials on each page/section?",
    )
    is_required_for_booking = models.BooleanField(
        default=False,
        help_text="Must this form be signed before diving?",
    )

    # Validity
    validity_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="How many days this agreement is valid (null = never expires)",
    )

    # Versioning
    version = models.CharField(
        max_length=20,
        default="1.0",
        help_text="Version number of this template",
    )

    # Lifecycle
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        constraints = [
            # Only one published template of each type+category per shop
            models.UniqueConstraint(
                fields=["dive_shop", "template_type", "diver_category"],
                condition=Q(status="published") & Q(deleted_at__isnull=True),
                name="diveops_unique_published_template_per_type_category",
            ),
        ]
        indexes = [
            models.Index(fields=["dive_shop", "template_type"]),
            models.Index(fields=["dive_shop", "target_party_type"]),
            models.Index(fields=["dive_shop", "diver_category"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["dive_shop", "template_type", "-version"]

    def __str__(self):
        return f"{self.name} (v{self.version})"

    def publish(self, user):
        """Publish this template, archiving any previous published version."""
        # Archive the currently published template of this type
        AgreementTemplate.objects.filter(
            dive_shop=self.dive_shop,
            template_type=self.template_type,
            status=self.Status.PUBLISHED,
        ).exclude(pk=self.pk).update(status=self.Status.ARCHIVED)

        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.published_by = user
        self.save(update_fields=["status", "published_at", "published_by", "updated_at"])


# =============================================================================
# Signable Agreement Models (Workflow)
# =============================================================================


class SignableAgreement(BaseModel):
    """Agreement instance with workflow: draft -> sent -> signed -> void.

    This model manages the workflow state for agreements that need to be signed.
    The django-agreements primitive is an immutable fact store (append-only ledger)
    with no workflow states. This model provides the workflow layer on top.

    When signed, a ledger_agreement is created in django_agreements.Agreement
    as the immutable record.

    Security:
    - access_token is stored as SHA-256 hash, never raw
    - Token is consumed after signing (cannot be reused)
    - expires_at is enforced at signing time

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        SIGNED = "signed", "Signed"
        VOID = "void", "Void"
        EXPIRED = "expired", "Expired"

    # Source template
    template = models.ForeignKey(
        "AgreementTemplate",
        on_delete=models.PROTECT,
        related_name="signable_agreements",
    )
    template_version = models.CharField(
        max_length=20,
        help_text="Snapshot of template.version at creation time",
    )

    # Party A (the signer) - GenericFK since Party is abstract
    party_a_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    party_a_object_id = models.CharField(max_length=255)
    party_a = GenericForeignKey("party_a_content_type", "party_a_object_id")

    # Party B (optional counter-party) - GenericFK
    party_b_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    party_b_object_id = models.CharField(max_length=255, blank=True)
    party_b = GenericForeignKey("party_b_content_type", "party_b_object_id")

    # Related object (booking, enrollment, etc.) - GenericFK
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    related_object_id = models.CharField(max_length=255, blank=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    # Content
    content_snapshot = models.TextField(
        help_text="Rendered content at send time (editable until signed)",
    )
    content_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of content_snapshot",
    )

    # Workflow state
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    # Delivery tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    delivery_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="How agreement was delivered: email, link, in_person",
    )

    # Token for signing URL
    access_token = models.CharField(
        max_length=64,
        blank=True,
        help_text="Raw token for signing URL (displayed to staff)",
    )
    access_token_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="SHA-256 hash of access token for verification",
    )
    token_consumed = models.BooleanField(
        default=False,
        help_text="Token invalidated after signing (cannot be reused)",
    )

    # Signature tracking (metadata only - image stored as Document)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by_name = models.CharField(max_length=255, blank=True)
    signed_ip = models.GenericIPAddressField(null=True, blank=True)
    signed_user_agent = models.TextField(blank=True)

    # Enhanced digital fingerprint for legal validity
    signed_screen_resolution = models.CharField(max_length=20, blank=True, help_text="e.g., 1920x1080")
    signed_timezone = models.CharField(max_length=100, blank=True, help_text="e.g., America/New_York")
    signed_timezone_offset = models.SmallIntegerField(null=True, blank=True, help_text="UTC offset in minutes")
    signed_language = models.CharField(max_length=50, blank=True, help_text="Browser language preference")
    signed_platform = models.CharField(max_length=100, blank=True, help_text="OS/Platform")
    signed_device_memory = models.CharField(max_length=20, blank=True, help_text="Device memory in GB")
    signed_hardware_concurrency = models.PositiveSmallIntegerField(null=True, blank=True, help_text="CPU cores")
    signed_touch_support = models.BooleanField(null=True, blank=True, help_text="Touch screen device")
    signed_canvas_fingerprint = models.CharField(max_length=64, blank=True, help_text="SHA-256 of canvas fingerprint")
    signed_geolocation = models.JSONField(null=True, blank=True, help_text="Lat/long if permitted")

    # E-Sign consent tracking (for legal compliance)
    agreed_to_terms = models.BooleanField(
        default=False,
        help_text="Signer checked 'I agree to be bound by its terms'",
    )
    agreed_to_esign = models.BooleanField(
        default=False,
        help_text="Signer checked 'I consent to sign electronically'",
    )

    # Signature image stored as Document (role=signature)
    signature_document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signature_for_agreements",
    )

    # Signed PDF document
    signed_document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signed_agreements",
    )

    # Linked immutable record (django-agreements primitive)
    ledger_agreement = models.ForeignKey(
        "django_agreements.Agreement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signable_agreements",
    )

    # Expiration - MUST be enforced at signing time
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this agreement expires (enforced at signing)",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["party_a_content_type", "party_a_object_id"]),
            models.Index(fields=["related_content_type", "related_object_id"]),
            models.Index(fields=["access_token_hash"]),
            models.Index(fields=["expires_at"]),
        ]
        constraints = [
            # WORKFLOW INTEGRITY: status='signed' requires signed_at
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(signed_at__isnull=False),
                name="signable_signed_requires_signed_at",
            ),
            # WORKFLOW INTEGRITY: status='sent' requires sent_at
            models.CheckConstraint(
                condition=~Q(status="sent") | Q(sent_at__isnull=False),
                name="signable_sent_requires_sent_at",
            ),
            # WORKFLOW INTEGRITY: status in (sent, signed) requires token hash
            models.CheckConstraint(
                condition=~Q(status__in=["sent", "signed"]) | ~Q(access_token_hash=""),
                name="signable_sent_signed_requires_token",
            ),
            # WORKFLOW INTEGRITY: status='signed' requires ledger_agreement
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(ledger_agreement__isnull=False),
                name="signable_signed_requires_ledger",
            ),
            # Content hash must be valid SHA-256 (64 hex chars)
            models.CheckConstraint(
                condition=Q(content_hash__regex=r"^[a-f0-9]{64}$"),
                name="signable_valid_content_hash",
            ),
            # LEGAL COMPLIANCE: status='signed' requires agreed_to_terms=True
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(agreed_to_terms=True),
                name="signable_signed_requires_terms_consent",
            ),
            # LEGAL COMPLIANCE: status='signed' requires agreed_to_esign=True
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(agreed_to_esign=True),
                name="signable_signed_requires_esign_consent",
            ),
            # DIGITAL PROOF: status='signed' requires IP address
            models.CheckConstraint(
                condition=~Q(status="signed") | Q(signed_ip__isnull=False),
                name="signable_signed_requires_ip",
            ),
            # DIGITAL PROOF: status='signed' requires user agent fingerprint
            models.CheckConstraint(
                condition=~Q(status="signed") | ~Q(signed_user_agent=""),
                name="signable_signed_requires_user_agent",
            ),
            # DIGITAL PROOF: status='signed' requires signer name
            models.CheckConstraint(
                condition=~Q(status="signed") | ~Q(signed_by_name=""),
                name="signable_signed_requires_signer_name",
            ),
            # DEDUPING: Only one pending agreement per template+party+related_object
            # Partial unique constraint for status in (draft, sent)
            # nulls_distinct=False ensures NULL values are treated as equal for deduping
            models.UniqueConstraint(
                fields=[
                    "template",
                    "party_a_content_type",
                    "party_a_object_id",
                    "related_content_type",
                    "related_object_id",
                ],
                condition=Q(status__in=["draft", "sent"]),
                name="signable_unique_pending_per_party_object",
                nulls_distinct=False,
            ),
        ]

    def __str__(self):
        return f"{self.template.name} for {self.get_party_a_cached()} ({self.status})"

    def get_party_a_cached(self):
        """Get party_a using prefetched data if available (avoids N+1)."""
        if hasattr(self, "_prefetched_party_a"):
            return self._prefetched_party_a
        return self.party_a

    @staticmethod
    def generate_token() -> tuple[str, str]:
        """Generate cryptographically random token and its hash.

        Returns:
            tuple: (raw_token, token_hash)
            - raw_token: URL-safe token to send to signer (returned ONCE)
            - token_hash: SHA-256 hash to store in database
        """
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token, token_hash

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for comparison."""
        return hashlib.sha256(token.encode()).hexdigest()

    def verify_token(self, token: str) -> bool:
        """Verify token matches stored hash and is not consumed.

        Args:
            token: Raw token from signing URL

        Returns:
            bool: True if token is valid and not consumed
        """
        if self.token_consumed:
            return False
        return secrets.compare_digest(
            self.access_token_hash,
            self.hash_token(token),
        )


class SignableAgreementRevision(BaseModel):
    """Immutable record of content changes for auditability.

    Every edit to a SignableAgreement's content creates a revision record.
    This provides a complete audit trail of all changes made before signing.

    Stores the content_before to enable diff viewing between revisions.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    agreement = models.ForeignKey(
        SignableAgreement,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    previous_content_hash = models.CharField(max_length=64)
    new_content_hash = models.CharField(max_length=64)
    content_before = models.TextField(
        blank=True,
        help_text="Content snapshot before this revision (for diff viewing)",
    )
    change_note = models.TextField(
        help_text="Required explanation of why the change was made",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )

    class Meta:
        ordering = ["revision_number"]
        unique_together = [["agreement", "revision_number"]]
        constraints = [
            # Change note is required (non-empty)
            models.CheckConstraint(
                condition=~Q(change_note=""),
                name="revision_requires_change_note",
            ),
        ]

    def __str__(self):
        return f"Revision {self.revision_number} of {self.agreement}"


# =============================================================================
# Document Retention Policy Models (overlay on django-documents)
# =============================================================================


class DocumentRetentionPolicy(BaseModel):
    """Defines retention rules for documents by type.

    Overlay model that extends django-documents with retention policies.
    Used for compliance with regulations like GDPR, HIPAA, IRS requirements.

    Default behavior: 30 days in Trash before permanent deletion.
    Policies can override this per document type.
    """

    document_type = models.CharField(
        max_length=100,
        unique=True,
        help_text="Document type this policy applies to (e.g., 'agreement', 'certification')",
    )
    retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days to retain after creation (null = keep forever)",
    )
    trash_retention_days = models.PositiveIntegerField(
        default=30,
        help_text="Days to keep in Trash before auto-delete (default 30)",
    )
    legal_basis = models.CharField(
        max_length=200,
        blank=True,
        help_text="Regulation/standard requiring this retention (e.g., 'IRS 7-year rule', 'PADI records')",
    )
    description = models.TextField(
        blank=True,
        help_text="Explanation of why this retention period is required",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this policy is currently enforced",
    )

    class Meta:
        verbose_name = "Document Retention Policy"
        verbose_name_plural = "Document Retention Policies"
        ordering = ["document_type"]

    def __str__(self):
        if self.retention_days:
            return f"{self.document_type}: {self.retention_days} days"
        return f"{self.document_type}: keep forever"


class DocumentLegalHold(BaseModel):
    """Prevents deletion of a specific document.

    Legal holds override retention policies and prevent any deletion
    (including from Trash) until the hold is released.

    Use cases:
    - Litigation hold
    - Regulatory investigation
    - Audit preservation
    - Insurance claim
    """

    document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.CASCADE,
        related_name="legal_holds",
        help_text="Document under legal hold",
    )
    reason = models.CharField(
        max_length=200,
        help_text="Reason for the hold (e.g., 'Litigation: Smith v. DiveShop')",
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Case/ticket/reference number",
    )
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_holds_placed",
        help_text="User who placed the hold",
    )
    placed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the hold was placed",
    )
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_holds_released",
        help_text="User who released the hold",
    )
    released_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the hold was released (null = still active)",
    )
    release_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reason for releasing the hold",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this hold",
    )

    class Meta:
        verbose_name = "Document Legal Hold"
        verbose_name_plural = "Document Legal Holds"
        ordering = ["-placed_at"]
        indexes = [
            models.Index(fields=["document", "released_at"]),
        ]

    def __str__(self):
        status = "ACTIVE" if self.is_active else "Released"
        return f"{self.document.filename}: {self.reason} [{status}]"

    @property
    def is_active(self):
        """Check if hold is still active."""
        return self.released_at is None

    def release(self, user, reason=""):
        """Release the hold."""
        if self.released_at:
            raise ValueError("Hold already released")
        self.released_by = user
        self.released_at = timezone.now()
        self.release_reason = reason
        self.save(update_fields=["released_by", "released_at", "release_reason", "updated_at"])

    @classmethod
    def document_has_active_hold(cls, document):
        """Check if a document has any active legal holds."""
        return cls.objects.filter(
            document=document,
            released_at__isnull=True,
            deleted_at__isnull=True,
        ).exists()
