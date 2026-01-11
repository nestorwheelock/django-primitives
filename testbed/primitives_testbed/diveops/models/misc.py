"""Miscellaneous models for dive operations.

This module contains:
- SettlementRecord: Idempotent settlement record for booking payments
- CommissionRule: Effective-dated commission rule for revenue sharing
- SettlementRun: Batch settlement run record
- AISettings: AI service configuration (Singleton)
- MedicalProviderProfile: Dive-specific extension for medical provider organizations
- MedicalProviderLocation: Physical location for a medical provider
- MedicalProviderRelationship: Links a dive shop to its recommended medical providers
- Contact: Lightweight record for an unregistered friend/buddy
- BuddyIdentity: Abstraction for team member identity
- DiveTeam: Buddy pair or group
- DiveTeamMember: Membership in a dive team
- DiveBuddy: Simple buddy relationship for a diver
"""

from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q
from django.utils import timezone

from django_basemodels import BaseModel
from django_singleton import EnvFallbackMixin, SingletonModel


# =============================================================================
# Settlement Records - INV-4: Idempotent Financial Postings
# =============================================================================


class SettlementRecord(BaseModel):
    """INV-4: Idempotent settlement record for booking payments.

    Tracks financial settlements for bookings with ledger integration.
    The idempotency_key ensures duplicate settlements are rejected.

    Settlement types:
    - revenue: Initial revenue recognition for a booking
    - refund: Refund posting for cancelled bookings (T-006)

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class SettlementType(models.TextChoices):
        REVENUE = "revenue", "Revenue"
        REFUND = "refund", "Refund"

    # Core relationship
    booking = models.ForeignKey(
        "diveops.Booking",
        on_delete=models.PROTECT,
        related_name="settlements",
    )

    # Settlement type
    settlement_type = models.CharField(
        max_length=20,
        choices=SettlementType.choices,
        default=SettlementType.REVENUE,
    )

    # Idempotency - unique key prevents duplicate settlements
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Deterministic key: {booking_id}:{type}:{sequence}",
    )

    # Amount and currency (from booking price_snapshot)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Settlement amount",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
    )

    # Ledger integration - links to posted transaction
    transaction = models.ForeignKey(
        "django_ledger.Transaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="diveops_settlements",
        help_text="Linked ledger transaction (immutable after posting)",
    )

    # Link to settlement run (if part of a batch)
    settlement_run = models.ForeignKey(
        "diveops.SettlementRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settlements",
        help_text="Settlement run this record belongs to (if batch processed)",
    )

    # Audit
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_settlements",
    )
    settled_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the settlement was recorded",
    )
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            # Unique idempotency key is handled by unique=True on field
        ]
        indexes = [
            models.Index(fields=["booking", "settlement_type"]),
            models.Index(fields=["settled_at"]),
            models.Index(fields=["settlement_run"]),
        ]
        ordering = ["-settled_at"]

    def __str__(self):
        return f"Settlement {self.idempotency_key}: {self.amount} {self.currency}"


# =============================================================================
# T-009: Commission Rule Definition
# =============================================================================


class CommissionRule(BaseModel):
    """INV-3: Effective-dated commission rule for revenue sharing.

    Commission rules define how revenue is split for bookings:
    - Shop default commission rate (excursion_type=NULL)
    - ExcursionType-specific overrides (higher priority)
    - Rate can be percentage of booking price or fixed amount
    - Effective dating allows rate changes without losing history

    Rule priority (highest to lowest):
    1. ExcursionType-specific rule (matching excursion_type, latest effective_at)
    2. Shop default rule (excursion_type=NULL, latest effective_at)
    3. Zero commission (no matching rule)

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class RateType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed Amount"

    # Ownership - which shop this rule applies to
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="commission_rules",
    )

    # Optional scope - if NULL, applies as shop default
    excursion_type = models.ForeignKey(
        "diveops.ExcursionType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commission_rules",
        help_text="If set, rule only applies to this ExcursionType. NULL = shop default.",
    )

    # Rate configuration
    rate_type = models.CharField(
        max_length=20,
        choices=RateType.choices,
        default=RateType.PERCENTAGE,
    )
    rate_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Percentage (e.g., 15.00 = 15%) or fixed amount (e.g., 25.00)",
    )

    # Effective dating (INV-3)
    effective_at = models.DateTimeField(
        help_text="When this rule becomes effective. Latest effective_at <= as_of wins.",
    )

    # Optional description
    description = models.TextField(
        blank=True,
        help_text="Reason for this rate or notes about the rule",
    )

    class Meta:
        constraints = [
            # Rate value must be non-negative
            models.CheckConstraint(
                condition=Q(rate_value__gte=0),
                name="diveops_commission_rate_non_negative",
            ),
            # Percentage must be <= 100
            models.CheckConstraint(
                condition=~Q(rate_type="percentage") | Q(rate_value__lte=100),
                name="diveops_commission_percentage_max_100",
            ),
        ]
        indexes = [
            models.Index(fields=["dive_shop", "excursion_type", "effective_at"]),
            models.Index(fields=["effective_at"]),
        ]
        ordering = ["-effective_at"]

    def __str__(self):
        scope = self.excursion_type.name if self.excursion_type else "Shop Default"
        if self.rate_type == self.RateType.PERCENTAGE:
            return f"{scope}: {self.rate_value}%"
        return f"{scope}: ${self.rate_value} fixed"


# =============================================================================
# T-010: Settlement Run (Batch Posting)
# =============================================================================


class SettlementRun(BaseModel):
    """Batch settlement run record.

    Tracks a batch of settlements processed together:
    - Period (date range) of bookings included
    - Success/failure counts
    - Total amount settled
    - Audit trail

    Individual SettlementRecords link to their SettlementRun.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # Shop this run is for
    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        related_name="settlement_runs",
    )

    # Period covered by this run
    period_start = models.DateTimeField(
        help_text="Start of period for eligible bookings",
    )
    period_end = models.DateTimeField(
        help_text="End of period for eligible bookings",
    )

    # Run status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Counts
    total_bookings = models.IntegerField(
        default=0,
        help_text="Total eligible bookings found",
    )
    settled_count = models.IntegerField(
        default=0,
        help_text="Number of bookings successfully settled",
    )
    failed_count = models.IntegerField(
        default=0,
        help_text="Number of bookings that failed to settle",
    )

    # Total amount
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total amount settled in this run",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
    )

    # Audit
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="settlement_runs_processed",
    )
    run_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the run was executed",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the run finished",
    )
    notes = models.TextField(blank=True)
    error_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Details of any failures during the run",
    )

    class Meta:
        indexes = [
            models.Index(fields=["dive_shop", "run_at"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-run_at"]

    def __str__(self):
        return f"SettlementRun {self.pk}: {self.dive_shop.name} ({self.settled_count}/{self.total_bookings})"


# =============================================================================
# AI Settings (Singleton Configuration)
# =============================================================================


class AISettings(EnvFallbackMixin, SingletonModel):
    """AI service configuration for the dive shop.

    Stores API keys and settings for AI services used in:
    - Document text extraction (OCR enhancement)
    - Agreement template processing
    - Other AI-powered features

    Uses EnvFallbackMixin: Database values take precedence,
    with fallback to environment variables if DB is blank.

    Usage:
        settings = AISettings.get_instance()
        key = settings.get_with_fallback('openrouter_api_key')
        if settings.has_value('openrouter_api_key'):
            # AI features are available
    """

    # API Keys
    openrouter_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="OpenRouter API key (falls back to OPENROUTER_API_KEY env var)",
    )
    openai_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="OpenAI API key (falls back to OPENAI_API_KEY env var)",
    )

    # Model Configuration
    default_model = models.CharField(
        max_length=100,
        default="anthropic/claude-3-haiku",
        help_text="Default AI model to use for processing",
    )

    # Feature Flags
    ocr_enhancement_enabled = models.BooleanField(
        default=True,
        help_text="Enable AI-powered OCR enhancement for scanned documents",
    )
    auto_extract_enabled = models.BooleanField(
        default=False,
        help_text="Automatically extract text from uploaded documents",
    )

    ENV_FALLBACKS = {
        "openrouter_api_key": "OPENROUTER_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
    }

    class Meta:
        verbose_name = "AI Settings"
        verbose_name_plural = "AI Settings"

    def __str__(self):
        return "AI Settings"

    def is_configured(self):
        """Check if at least one AI service is configured."""
        return self.has_value("openrouter_api_key") or self.has_value("openai_api_key")


# =============================================================================
# Email Settings (Singleton Configuration)
# =============================================================================


class EmailSettings(SingletonModel):
    """Email service configuration for the dive shop.

    DB-first configuration for email sending via Amazon SES or Django console.
    Credentials are stored in the database and editable via Django admin.

    Supported providers:
    - console: Uses Django's console email backend (development)
    - ses_api: Uses boto3 SES API with credentials from this model

    Setup steps:
    1. Go to Django Admin > Diveops > Email Settings
    2. Set provider to 'ses_api' for production
    3. Enter AWS region, access key, and secret key
    4. Set default_from_email (must be verified in SES)
    5. Run: python manage.py send_test_email --to your@email.com
    6. For production, ensure SES is out of sandbox mode

    Usage:
        settings = EmailSettings.get_instance()
        if settings.is_configured():
            from primitives_testbed.diveops.email_service import send_email
            send_email(to="user@example.com", subject="Hello", body_text="Hi!")
    """

    PROVIDER_CHOICES = [
        ("console", "Console (Development)"),
        ("ses_api", "Amazon SES API"),
        ("ses_smtp", "Amazon SES SMTP"),
    ]

    # General settings
    enabled = models.BooleanField(
        default=True,
        help_text="Master switch to enable/disable email sending",
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default="console",
        help_text="Email provider to use",
    )
    sandbox_mode = models.BooleanField(
        default=False,
        help_text="Safety toggle - when enabled, emails are logged but not sent",
    )

    # Sender identity
    default_from_email = models.EmailField(
        help_text="Default sender email address (must be verified in SES)",
    )
    default_from_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Display name for sender (e.g., 'Dive Shop Name')",
    )
    reply_to_email = models.EmailField(
        blank=True,
        help_text="Default reply-to address (optional)",
    )

    # AWS SES configuration
    aws_region = models.CharField(
        max_length=50,
        default="us-east-1",
        help_text="AWS region for SES (e.g., us-east-1, eu-west-1)",
    )
    configuration_set = models.CharField(
        max_length=100,
        blank=True,
        help_text="SES Configuration Set name for tracking (optional)",
    )
    aws_access_key_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="AWS Access Key ID for SES",
    )
    aws_secret_access_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="AWS Secret Access Key for SES",
    )

    # Optional SMTP fields (for future ses_smtp provider)
    smtp_host = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP host (for SMTP provider)",
    )
    smtp_port = models.PositiveIntegerField(
        default=587,
        help_text="SMTP port (typically 587 for TLS)",
    )
    smtp_username = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP username",
    )
    smtp_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP password",
    )

    class Meta:
        verbose_name = "Email Settings"
        verbose_name_plural = "Email Settings"

    def __str__(self):
        return "Email Settings"

    def is_configured(self):
        """Check if email is properly configured for the selected provider."""
        if not self.default_from_email:
            return False

        if self.provider == "console":
            return True
        elif self.provider == "ses_api":
            return bool(self.aws_access_key_id and self.aws_secret_access_key)
        elif self.provider == "ses_smtp":
            return bool(self.smtp_host and self.smtp_username and self.smtp_password)

        return False

    def get_from_address(self):
        """Get formatted From address with name if provided."""
        if self.default_from_name:
            return f"{self.default_from_name} <{self.default_from_email}>"
        return self.default_from_email


class EmailTemplate(BaseModel):
    """DB-stored email template with subject, text, and HTML body.

    Templates are identified by a unique key (e.g., "verify_email", "welcome").
    Template content uses Django template syntax for variable substitution.

    Usage:
        template = EmailTemplate.objects.get(key="verify_email", is_active=True)
        # Use with render_email_template() from email_service.py
    """

    key = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for the template (e.g., 'verify_email', 'welcome')",
    )
    name = models.CharField(
        max_length=200,
        help_text="Human-readable name for the template",
    )
    subject_template = models.TextField(
        help_text="Email subject line (supports Django template syntax)",
    )
    body_text_template = models.TextField(
        help_text="Plain text email body (supports Django template syntax)",
    )
    body_html_template = models.TextField(
        blank=True,
        help_text="HTML email body (optional, supports Django template syntax)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template can be used for sending emails",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_email_templates",
        help_text="User who last updated this template",
    )

    class Meta:
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"
        ordering = ["key"]

    def __str__(self):
        return f"{self.key}: {self.name}"


# =============================================================================
# Medical Provider Models
# =============================================================================


class MedicalProviderProfile(BaseModel):
    """Dive-specific extension for medical provider organizations.

    Links to django_parties.Organization (1:1) and stores dive-specific
    attributes like hyperbaric chamber availability, languages spoken,
    and certifications.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    PROVIDER_TYPE_CHOICES = [
        ("clinic", "Clinic"),
        ("hospital", "Hospital"),
        ("urgent_care", "Urgent Care"),
        ("chamber", "Hyperbaric Chamber Facility"),
        ("physician", "Individual Physician"),
    ]

    organization = models.OneToOneField(
        "django_parties.Organization",
        on_delete=models.CASCADE,
        related_name="medical_provider_profile",
        help_text="Base organization record",
    )
    provider_type = models.CharField(
        max_length=20,
        choices=PROVIDER_TYPE_CHOICES,
        help_text="Type of medical provider",
    )

    # Capabilities
    has_hyperbaric_chamber = models.BooleanField(
        default=False,
        help_text="Whether facility has a hyperbaric chamber",
    )
    hyperbaric_details = models.TextField(
        blank=True,
        help_text="Details about hyperbaric chamber (type, depth rating, etc.)",
    )
    accepts_divers = models.BooleanField(
        default=True,
        help_text="Whether provider accepts diving-related cases",
    )
    accepts_emergencies = models.BooleanField(
        default=False,
        help_text="Whether provider accepts emergency cases",
    )
    is_dan_affiliated = models.BooleanField(
        default=False,
        help_text="Whether provider is affiliated with Divers Alert Network",
    )

    # Languages and certifications (stored as arrays for simplicity)
    languages = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Languages spoken by staff",
    )
    certifications = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Relevant medical certifications (DAN, UHMS, etc.)",
    )

    # Contact
    after_hours_phone = models.CharField(
        max_length=30,
        blank=True,
        help_text="After-hours emergency contact number",
    )
    notes = models.TextField(
        blank=True,
        help_text="Special instructions or notes about this provider",
    )

    # Display ordering
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order for display (lower = first)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this provider is currently active",
    )

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name = "Medical Provider Profile"
        verbose_name_plural = "Medical Provider Profiles"

    def __str__(self):
        return f"{self.organization.name} ({self.get_provider_type_display()})"


class MedicalProviderLocation(BaseModel):
    """Physical location for a medical provider.

    Supports multi-location providers with different addresses and hours.
    Stores coordinates for map links in PDFs.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    profile = models.ForeignKey(
        MedicalProviderProfile,
        on_delete=models.CASCADE,
        related_name="locations",
        help_text="Parent medical provider profile",
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Location name (e.g., 'Main Office', 'Chamber Facility')",
    )

    # Address fields (inline for simplicity)
    address_line1 = models.CharField(
        max_length=255,
        help_text="Street address line 1",
    )
    address_line2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Street address line 2",
    )
    city = models.CharField(
        max_length=100,
        help_text="City",
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        help_text="State or province",
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal/ZIP code",
    )
    country = models.CharField(
        max_length=100,
        default="Mexico",
        help_text="Country",
    )

    # Coordinates for map links (9 digits, 6 decimal places per django_geo pattern)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate",
    )

    # Operating hours
    hours_text = models.CharField(
        max_length=255,
        help_text="Hours of operation (e.g., 'Mon-Fri 9:00 AM - 5:00 PM')",
    )
    is_24_7 = models.BooleanField(
        default=False,
        help_text="Whether location is open 24/7",
    )

    # Contact overrides (if different from main org)
    phone = models.CharField(
        max_length=30,
        blank=True,
        help_text="Phone number for this location",
    )
    email = models.EmailField(
        blank=True,
        help_text="Email address for this location",
    )

    # Flags
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary/main location",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order for display (lower = first)",
    )

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name = "Medical Provider Location"
        verbose_name_plural = "Medical Provider Locations"

    def __str__(self):
        if self.name:
            return f"{self.profile.organization.name} - {self.name}"
        return f"{self.profile.organization.name} - {self.city}"

    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        city_state_zip = f"{self.city}"
        if self.state:
            city_state_zip += f", {self.state}"
        if self.postal_code:
            city_state_zip += f" {self.postal_code}"
        parts.append(city_state_zip)
        if self.country:
            parts.append(self.country)
        return "\n".join(parts)

    @property
    def google_maps_url(self):
        """Return Google Maps URL if coordinates are available."""
        if self.latitude and self.longitude:
            return f"https://maps.google.com/?q={self.latitude},{self.longitude}"
        return None


class MedicalProviderRelationship(BaseModel):
    """Links a dive shop to its recommended medical providers.

    Allows dive operators to configure their preferred medical providers
    for customer referrals. Supports ordering and marking a primary provider.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    dive_shop = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.CASCADE,
        related_name="medical_provider_relationships",
        help_text="The dive shop/operator",
    )
    provider = models.ForeignKey(
        MedicalProviderProfile,
        on_delete=models.CASCADE,
        related_name="dive_shop_relationships",
        help_text="The medical provider",
    )

    # Relationship attributes
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary/preferred provider",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order for display (lower = first)",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about this provider relationship (e.g., 'Preferred for complex cases')",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this relationship is currently active",
    )

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name = "Medical Provider Relationship"
        verbose_name_plural = "Medical Provider Relationships"
        constraints = [
            # Only one relationship per dive_shop + provider (among active records)
            models.UniqueConstraint(
                fields=["dive_shop", "provider"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_shop_provider_relationship",
            ),
        ]

    def __str__(self):
        return f"{self.dive_shop.name} -> {self.provider.organization.name}"


# =============================================================================
# Buddy System Models
# =============================================================================


class Contact(BaseModel):
    """Lightweight record for an unregistered friend/buddy.

    Used when a diver wants to add a buddy who isn't on the platform yet.
    Supports invite workflows: create contact -> invite -> they register -> link.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        INVITED = "invited", "Invited"
        ACCEPTED = "accepted", "Accepted"
        BOUNCED = "bounced", "Bounced"
        OPTED_OUT = "opted_out", "Opted Out"

    created_by = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.CASCADE,
        related_name="created_contacts",
        help_text="Person who created this contact",
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Display name for the contact",
    )
    email = models.EmailField(
        null=True,
        blank=True,
        help_text="Contact email address",
    )
    phone = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Contact phone number",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        help_text="Contact status in invite workflow",
    )
    linked_person = models.ForeignKey(
        "django_parties.Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contact_links",
        help_text="Linked Person after they register",
    )

    class Meta:
        ordering = ["display_name"]
        constraints = [
            # Must have at least email or phone
            models.CheckConstraint(
                condition=Q(email__isnull=False) | Q(phone__isnull=False),
                name="contact_requires_email_or_phone",
            ),
        ]
        indexes = [
            models.Index(fields=["created_by"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.display_name


class BuddyIdentity(BaseModel):
    """Abstraction for team member identity: Person OR Contact.

    Allows DiveTeamMember to reference either a registered Person
    or an unregistered Contact, enabling invite-ready buddy system.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    person = models.OneToOneField(
        "django_parties.Person",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="buddy_identity",
        help_text="Reference to a registered Person",
    )
    contact = models.OneToOneField(
        Contact,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="buddy_identity",
        help_text="Reference to an unregistered Contact",
    )

    class Meta:
        verbose_name = "Buddy Identity"
        verbose_name_plural = "Buddy Identities"
        constraints = [
            # Must have exactly one of person or contact
            models.CheckConstraint(
                condition=(
                    Q(person__isnull=False, contact__isnull=True) |
                    Q(person__isnull=True, contact__isnull=False)
                ),
                name="identity_exactly_one_of_person_or_contact",
            ),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self) -> str:
        """Get display name from Person or Contact."""
        if self.person:
            return f"{self.person.first_name} {self.person.last_name}"
        if self.contact:
            return self.contact.display_name
        return "Unknown"

    @property
    def is_registered(self) -> bool:
        """Check if this identity represents a registered user.

        True if:
        - Identity references a Person directly, OR
        - Identity references a Contact that has been linked to a Person
        """
        if self.person is not None:
            return True
        if self.contact and self.contact.linked_person is not None:
            return True
        return False


class DiveTeam(BaseModel):
    """Buddy pair or group.

    Represents 2+ divers who typically dive together.
    Size 2 = buddy pair, size 3+ = buddy group with optional name.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    class TeamType(models.TextChoices):
        BUDDY = "buddy", "Buddy Group"

    team_type = models.CharField(
        max_length=20,
        choices=TeamType.choices,
        default=TeamType.BUDDY,
        help_text="Type of team",
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional name for groups (blank for pairs)",
    )
    created_by = models.ForeignKey(
        "django_parties.Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_dive_teams",
        help_text="Person who created this team",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this team is currently active",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        if self.name:
            return self.name
        return f"Buddy Team {self.pk}"


class DiveTeamMember(BaseModel):
    """Membership in a dive team.

    Join table linking BuddyIdentity to DiveTeam.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    team = models.ForeignKey(
        DiveTeam,
        on_delete=models.CASCADE,
        related_name="members",
        help_text="The dive team",
    )
    identity = models.ForeignKey(
        BuddyIdentity,
        on_delete=models.CASCADE,
        related_name="team_memberships",
        help_text="The team member identity",
    )
    role = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optional role in the team",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about this team member",
    )

    class Meta:
        ordering = ["team", "created_at"]
        constraints = [
            # Can't add same identity to team twice
            models.UniqueConstraint(
                fields=["team", "identity"],
                name="unique_team_member",
            ),
        ]
        indexes = [
            models.Index(fields=["team", "identity"]),
        ]

    def __str__(self):
        return f"{self.identity.display_name} in {self.team}"


class DiveBuddy(BaseModel):
    """Simple buddy relationship for a diver.

    Links a diver to their buddies. Buddy can be:
    - Another DiverProfile (buddy field), or
    - Just a Person who isn't a diver yet (buddy_person field)

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse/Partner"),
        ("friend", "Friend"),
        ("dive_club", "Dive Club Member"),
        ("instructor", "Instructor"),
        ("family", "Family Member"),
        ("coworker", "Coworker"),
        ("other", "Other"),
    ]

    diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.CASCADE,
        related_name="dive_buddies",
        help_text="The diver who owns this buddy relationship",
    )
    buddy = models.ForeignKey(
        "diveops.DiverProfile",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="buddy_of",
        help_text="The buddy (if they are a diver)",
    )
    buddy_person = models.ForeignKey(
        "django_parties.Person",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="buddy_person_for",
        help_text="The buddy (if they are just a person, not a diver)",
    )
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        help_text="Type of relationship",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about this buddy",
    )

    class Meta:
        ordering = ["diver", "relationship"]
        verbose_name = "Dive Buddy"
        verbose_name_plural = "Dive Buddies"
        indexes = [
            models.Index(fields=["diver"]),
        ]

    def __str__(self):
        return f"{self.diver.person} -> {self.buddy_name} ({self.get_relationship_display()})"

    @property
    def buddy_name(self) -> str:
        """Get the buddy's display name."""
        if self.buddy:
            person = self.buddy.person
            return f"{person.first_name} {person.last_name}"
        if self.buddy_person:
            return f"{self.buddy_person.first_name} {self.buddy_person.last_name}"
        return "Unknown"


class DiveBuddyGroup(BaseModel):
    """Links a DiveTeam to a group Conversation.

    Provides DiveOps-specific context for buddy group chats:
    - Connects the primitive Conversation to the domain DiveTeam
    - Enables chat features for buddy groups
    - Maintains dive-specific group semantics

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    dive_team = models.OneToOneField(
        DiveTeam,
        on_delete=models.CASCADE,
        related_name="group_chat",
        help_text="The dive team this chat belongs to",
    )
    conversation = models.OneToOneField(
        "django_communication.Conversation",
        on_delete=models.CASCADE,
        related_name="buddy_group",
        help_text="The underlying group conversation",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Dive Buddy Group"
        verbose_name_plural = "Dive Buddy Groups"

    def __str__(self):
        return f"Chat for {self.dive_team}"
