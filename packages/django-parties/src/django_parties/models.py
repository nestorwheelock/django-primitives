"""
Django Parties models - The Party Pattern.

This module provides:
- Party: Abstract base for entities that can own things and do business
- Person: A human being (separate from User account)
- Organization: Companies, clinics, suppliers, schools
- Group: Households, families, partnerships
- PartyRelationship: Links between parties (employee, vendor, member, etc.)
- Address: Physical/mailing addresses
- Phone: Phone numbers
- Email: Email addresses
- Demographics: Age, gender, date of birth, etc.
- PartyURL: Websites and social media profiles

All models inherit from django_basemodels.BaseModel providing:
- UUID primary keys
- created_at / updated_at timestamps
- Soft delete via deleted_at
- Default manager excludes soft-deleted rows

Key Design:
- Person is the real-world human identity (Party type)
- User (in your auth app) is a login account that links to a Person
- One Person can have multiple User accounts (different auth methods)
- A Person can exist without any User account (contacts, leads)
- A User can exist without a Person (API/service accounts)
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_basemodels import BaseModel


# =============================================================================
# Party Pattern - Core Models
# =============================================================================

# PRIMITIVES: allow-plain-model
class Party(models.Model):
    """Abstract base for any entity that can own things and do business.

    Subtypes: Person, Organization, Group

    Note: This is abstract and does NOT inherit from BaseModel.
    Concrete subclasses inherit from BaseModel directly.
    """

    class Meta:
        abstract = True

    # Primary contact info (convenience fields for quick entry)
    # Full contact info is stored in normalized Phone/Email/Address tables
    email = models.EmailField(_('email'), blank=True)
    phone = models.CharField(_('phone'), max_length=20, blank=True)
    address_line1 = models.CharField(_('address line 1'), max_length=255, blank=True)
    address_line2 = models.CharField(_('address line 2'), max_length=255, blank=True)
    city = models.CharField(_('city'), max_length=100, blank=True)
    state = models.CharField(_('state/province'), max_length=100, blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)
    country = models.CharField(_('country'), max_length=100, blank=True)


class Person(BaseModel, Party):
    """A human being - the real-world identity.

    Separate from User (login account). One Person can have multiple User
    accounts (different auth methods), or no accounts at all (just a contact).

    Examples:
    - Customer with email login AND Google OAuth = 1 Person, 2 Users
    - Business contact without login = 1 Person, 0 Users
    - API service account = 0 Person, 1 User

    To link User accounts to Person, add a ForeignKey in your User model:
        person = models.ForeignKey('django_parties.Person', ...)
    """

    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    middle_name = models.CharField(_('middle name'), max_length=150, blank=True)

    # Preferred name (what they want to be called)
    preferred_name = models.CharField(
        _('preferred name'),
        max_length=150,
        blank=True,
        help_text=_('What this person prefers to be called'),
    )

    # Display name for list views (auto-generated or manual)
    display_name = models.CharField(
        _('display name'),
        max_length=300,
        blank=True,
        help_text=_('Auto-generated from name or manually set'),
    )

    # Date fields for lifecycle tracking
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    date_of_death = models.DateField(_('date of death'), null=True, blank=True)

    # Status
    is_active = models.BooleanField(_('active'), default=True)

    # Person-specific phone metadata (phone number itself inherited from Party)
    phone_is_mobile = models.BooleanField(_('is mobile'), default=True)
    phone_has_whatsapp = models.BooleanField(_('has WhatsApp'), default=False)
    phone_can_receive_sms = models.BooleanField(_('can receive SMS'), default=True)

    # Person-specific address metadata (address fields inherited from Party)
    address_is_home = models.BooleanField(_('home address'), default=True)
    address_is_billing = models.BooleanField(_('billing address'), default=False)
    address_is_shipping = models.BooleanField(_('shipping address'), default=False)

    # Metadata
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('person')
        verbose_name_plural = _('people')
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.get_full_name()

    def get_full_name(self):
        """Returns the full name (first + last)."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts)

    def get_short_name(self):
        """Returns preferred name or first name."""
        return self.preferred_name or self.first_name

    def save(self, *args, **kwargs):
        # Auto-generate display_name if not set
        if not self.display_name:
            self.display_name = self.get_full_name()
        super().save(*args, **kwargs)

    @property
    def age(self):
        """Calculate age from date of birth."""
        if not self.date_of_birth:
            return None
        from datetime import date
        today = date.today()
        age = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            age -= 1
        return age


class Organization(BaseModel, Party):
    """A formal business entity - company, clinic, school, supplier, etc."""

    ORGANIZATION_TYPES = [
        ('company', _('Company')),
        ('clinic', _('Clinic')),
        ('hospital', _('Hospital')),
        ('supplier', _('Supplier/Distributor')),
        ('school', _('School/Institution')),
        ('nonprofit', _('Non-profit')),
        ('government', _('Government Agency')),
        ('partner', _('Business Partner')),
        ('other', _('Other')),
    ]

    name = models.CharField(_('name'), max_length=200)
    org_type = models.CharField(
        _('organization type'),
        max_length=20,
        choices=ORGANIZATION_TYPES,
        default='company',
    )
    website = models.URLField(_('website'), blank=True)

    # Business info
    tax_id = models.CharField(
        _('tax ID'),
        max_length=30,
        blank=True,
        help_text=_('Tax identification number (EIN, RFC, VAT, etc.)'),
    )
    legal_name = models.CharField(_('legal name'), max_length=255, blank=True)

    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')
        ordering = ['name']

    def __str__(self):
        return self.name


class Group(BaseModel, Party):
    """An informal grouping of people - household, family, partnership.

    Use for: spouses sharing a pet, roommates, family units.
    """

    GROUP_TYPES = [
        ('household', _('Household')),
        ('family', _('Family')),
        ('partnership', _('Partnership')),
        ('team', _('Team')),
        ('department', _('Department')),
        ('other', _('Other')),
    ]

    name = models.CharField(_('name'), max_length=200)
    group_type = models.CharField(
        _('group type'),
        max_length=20,
        choices=GROUP_TYPES,
        default='household',
    )

    # Primary contact for the group
    primary_contact = models.ForeignKey(
        'Person',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='primary_for_groups',
        verbose_name=_('primary contact'),
    )

    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _('group')
        verbose_name_plural = _('groups')
        ordering = ['name']

    def __str__(self):
        return self.name


class PartyRelationship(BaseModel):
    """Relationship between any two parties.

    Supports:
    - Person -> Organization (employee, contractor, contact)
    - Person -> Person (spouse, parent, emergency contact)
    - Organization -> Organization (contractor, vendor, partner)
    - Person -> Group (member, head of household)

    Note on CASCADE: We intentionally use CASCADE for party ForeignKeys because
    relationships are subordinate to parties. When a party is deleted (soft or hard),
    its relationships should be deleted too. This is NOT append-only audit history -
    it's mutable relationship state that tracks current connections between parties.
    """

    RELATIONSHIP_TYPES = [
        # Person -> Organization
        ('employee', _('Employee')),
        ('contractor_individual', _('Individual Contractor')),
        ('contact', _('Contact')),
        ('owner', _('Owner/Executive')),
        ('customer', _('Customer')),
        # Organization -> Organization
        ('contractor_org', _('Contractor Organization')),
        ('vendor', _('Vendor/Supplier')),
        ('partner', _('Business Partner')),
        ('client', _('Client')),
        ('subsidiary', _('Subsidiary')),
        ('parent_company', _('Parent Company')),
        # Person -> Group
        ('member', _('Member')),
        ('head', _('Head of Household')),
        ('spouse', _('Spouse/Partner')),
        ('dependent', _('Dependent')),
        # Person -> Person
        ('emergency_contact', _('Emergency Contact')),
        ('guardian', _('Guardian')),
        ('parent', _('Parent')),
        ('child', _('Child')),
        ('sibling', _('Sibling')),
        ('manager', _('Manager')),
        ('reports_to', _('Reports To')),
        ('friend', _('Friend')),
        ('relative', _('Relative/Family')),
        ('buddy', _('Activity Partner/Buddy')),
        ('travel_companion', _('Travel Companion')),
        ('instructor', _('Instructor/Trainer')),
        ('student', _('Student/Trainee')),
    ]

    # From party (can be Person or Org)
    from_person = models.ForeignKey(
        'Person',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='relationships_from',
        verbose_name=_('from person'),
    )
    from_organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='relationships_from',
        verbose_name=_('from organization'),
    )

    # To party (can be Person, Org, or Group)
    to_person = models.ForeignKey(
        'Person',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='relationships_to',
        verbose_name=_('to person'),
    )
    to_organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='relationships_to',
        verbose_name=_('to organization'),
    )
    to_group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='relationships_to',
        verbose_name=_('to group'),
    )

    relationship_type = models.CharField(
        _('relationship type'),
        max_length=30,
        choices=RELATIONSHIP_TYPES,
    )
    title = models.CharField(
        _('title'),
        max_length=100,
        blank=True,
        help_text=_('Job title or role description'),
    )

    # Contract details (for contractor/vendor relationships)
    contract_start = models.DateField(_('contract start'), null=True, blank=True)
    contract_end = models.DateField(_('contract end'), null=True, blank=True)
    contract_signed = models.BooleanField(_('contract signed'), default=False)

    is_active = models.BooleanField(_('active'), default=True)
    is_primary = models.BooleanField(
        _('primary'),
        default=False,
        help_text=_('Primary relationship of this type'),
    )

    class Meta:
        verbose_name = _('party relationship')
        verbose_name_plural = _('party relationships')
        ordering = ['-created_at']
        constraints = [
            # Exactly one "from" party must be set
            models.CheckConstraint(
                condition=(
                    (models.Q(from_person__isnull=False) & models.Q(from_organization__isnull=True)) |
                    (models.Q(from_person__isnull=True) & models.Q(from_organization__isnull=False))
                ),
                name="partyrelationship_exactly_one_from",
            ),
            # Exactly one "to" party must be set
            models.CheckConstraint(
                condition=(
                    (models.Q(to_person__isnull=False) & models.Q(to_organization__isnull=True) & models.Q(to_group__isnull=True)) |
                    (models.Q(to_person__isnull=True) & models.Q(to_organization__isnull=False) & models.Q(to_group__isnull=True)) |
                    (models.Q(to_person__isnull=True) & models.Q(to_organization__isnull=True) & models.Q(to_group__isnull=False))
                ),
                name="partyrelationship_exactly_one_to",
            ),
        ]

    def clean(self):
        """Validate relationship invariants (applies across all entry points)."""
        from django.core.exceptions import ValidationError

        super().clean()

        # Validate exactly one "from" party is set
        if not self.from_person and not self.from_organization:
            raise ValidationError(
                {'from_person': _('You must select either a from person or from organization.')}
            )
        if self.from_person and self.from_organization:
            raise ValidationError(
                {'from_person': _('Select only one from party (person or organization).')}
            )

        # Validate exactly one "to" party is set
        to_count = sum([bool(self.to_person), bool(self.to_organization), bool(self.to_group)])
        if to_count == 0:
            raise ValidationError(
                {'to_person': _('You must select a to party (person, organization, or group).')}
            )
        if to_count > 1:
            raise ValidationError(
                {'to_person': _('Select only one to party (person, organization, or group).')}
            )

    def __str__(self):
        from_party = self.from_person or self.from_organization
        to_party = self.to_person or self.to_organization or self.to_group
        return f'{from_party} -> {to_party} ({self.get_relationship_type_display()})'

    @property
    def from_party(self):
        """Returns whichever from party is set."""
        return self.from_person or self.from_organization

    @property
    def to_party(self):
        """Returns whichever to party is set."""
        return self.to_person or self.to_organization or self.to_group


# =============================================================================
# Address - Normalized address table
# =============================================================================

class Address(BaseModel):
    """Physical or mailing address for any party."""

    ADDRESS_TYPES = [
        ('home', _('Home')),
        ('work', _('Work')),
        ('mailing', _('Mailing')),
        ('billing', _('Billing')),
        ('shipping', _('Shipping')),
        ('headquarters', _('Headquarters')),
        ('branch', _('Branch')),
        ('other', _('Other')),
    ]

    # Link to party (one must be set)
    person = models.ForeignKey(
        'Person',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='addresses',
        verbose_name=_('person'),
    )
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='addresses',
        verbose_name=_('organization'),
    )
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='addresses',
        verbose_name=_('group'),
    )

    address_type = models.CharField(
        _('address type'),
        max_length=20,
        choices=ADDRESS_TYPES,
        default='home',
    )
    is_primary = models.BooleanField(_('primary'), default=False)

    # Address fields
    line1 = models.CharField(_('address line 1'), max_length=255)
    line2 = models.CharField(_('address line 2'), max_length=255, blank=True)
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state/province'), max_length=100, blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)
    country = models.CharField(_('country'), max_length=100, blank=True)

    # Geolocation
    latitude = models.DecimalField(
        _('latitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        _('longitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # Metadata
    label = models.CharField(
        _('label'),
        max_length=100,
        blank=True,
        help_text=_('Custom label like "Mom\'s House" or "Downtown Office"'),
    )
    notes = models.TextField(_('notes'), blank=True)
    is_verified = models.BooleanField(_('verified'), default=False)

    class Meta:
        verbose_name = _('address')
        verbose_name_plural = _('addresses')
        ordering = ['-is_primary', '-created_at']
        constraints = [
            # Exactly one party FK must be set
            models.CheckConstraint(
                condition=(
                    (models.Q(person__isnull=False) & models.Q(organization__isnull=True) & models.Q(group__isnull=True)) |
                    (models.Q(person__isnull=True) & models.Q(organization__isnull=False) & models.Q(group__isnull=True)) |
                    (models.Q(person__isnull=True) & models.Q(organization__isnull=True) & models.Q(group__isnull=False))
                ),
                name="address_exactly_one_party",
            ),
        ]

    def __str__(self):
        return f'{self.line1}, {self.city}'

    @property
    def party(self):
        """Returns whichever party is set."""
        return self.person or self.organization or self.group

    @property
    def full_address(self):
        """Returns formatted full address."""
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        city_state = f'{self.city}, {self.state} {self.postal_code}'.strip()
        parts.append(city_state)
        if self.country:
            parts.append(self.country)
        return '\n'.join(parts)


# =============================================================================
# Phone - Normalized phone number table
# =============================================================================

class Phone(BaseModel):
    """Phone number for any party."""

    PHONE_TYPES = [
        ('mobile', _('Mobile')),
        ('home', _('Home')),
        ('work', _('Work')),
        ('fax', _('Fax')),
        ('whatsapp', _('WhatsApp')),
        ('main', _('Main')),
        ('toll_free', _('Toll Free')),
        ('other', _('Other')),
    ]

    # Link to party (one must be set)
    person = models.ForeignKey(
        'Person',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='phone_numbers',
        verbose_name=_('person'),
    )
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='phone_numbers',
        verbose_name=_('organization'),
    )
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='phone_numbers',
        verbose_name=_('group'),
    )

    phone_type = models.CharField(
        _('phone type'),
        max_length=20,
        choices=PHONE_TYPES,
        default='mobile',
    )
    is_primary = models.BooleanField(_('primary'), default=False)

    # Phone fields
    country_code = models.CharField(
        _('country code'),
        max_length=5,
        blank=True,
        help_text=_('e.g., +1 for US, +52 for Mexico'),
    )
    number = models.CharField(_('number'), max_length=20)
    extension = models.CharField(_('extension'), max_length=10, blank=True)

    # Metadata
    label = models.CharField(_('label'), max_length=100, blank=True)
    is_verified = models.BooleanField(_('verified'), default=False)
    can_receive_sms = models.BooleanField(_('can receive SMS'), default=True)
    can_receive_whatsapp = models.BooleanField(_('can receive WhatsApp'), default=False)

    class Meta:
        verbose_name = _('phone number')
        verbose_name_plural = _('phone numbers')
        ordering = ['-is_primary', '-created_at']
        constraints = [
            # Exactly one party FK must be set
            models.CheckConstraint(
                condition=(
                    (models.Q(person__isnull=False) & models.Q(organization__isnull=True) & models.Q(group__isnull=True)) |
                    (models.Q(person__isnull=True) & models.Q(organization__isnull=False) & models.Q(group__isnull=True)) |
                    (models.Q(person__isnull=True) & models.Q(organization__isnull=True) & models.Q(group__isnull=False))
                ),
                name="phone_exactly_one_party",
            ),
        ]

    def __str__(self):
        if self.country_code:
            return f'{self.country_code} {self.number}'
        return self.number

    @property
    def party(self):
        return self.person or self.organization or self.group

    @property
    def full_number(self):
        """Returns formatted phone number."""
        base = f'{self.country_code} {self.number}' if self.country_code else self.number
        if self.extension:
            return f'{base} ext. {self.extension}'
        return base


# =============================================================================
# Email - Normalized email table
# =============================================================================

class Email(BaseModel):
    """Email address for any party."""

    EMAIL_TYPES = [
        ('personal', _('Personal')),
        ('work', _('Work')),
        ('billing', _('Billing')),
        ('support', _('Support')),
        ('newsletter', _('Newsletter')),
        ('info', _('Info')),
        ('other', _('Other')),
    ]

    # Link to party (one must be set)
    person = models.ForeignKey(
        'Person',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='email_addresses',
        verbose_name=_('person'),
    )
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='email_addresses',
        verbose_name=_('organization'),
    )
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='email_addresses',
        verbose_name=_('group'),
    )

    email_type = models.CharField(
        _('email type'),
        max_length=20,
        choices=EMAIL_TYPES,
        default='personal',
    )
    is_primary = models.BooleanField(_('primary'), default=False)

    # Email fields
    email = models.EmailField(_('email address'))

    # Metadata
    label = models.CharField(_('label'), max_length=100, blank=True)
    is_verified = models.BooleanField(_('verified'), default=False)
    receives_marketing = models.BooleanField(_('receives marketing'), default=False)
    receives_transactional = models.BooleanField(_('receives transactional'), default=True)

    class Meta:
        verbose_name = _('email address')
        verbose_name_plural = _('email addresses')
        ordering = ['-is_primary', '-created_at']
        constraints = [
            # Exactly one party FK must be set
            models.CheckConstraint(
                condition=(
                    (models.Q(person__isnull=False) & models.Q(organization__isnull=True) & models.Q(group__isnull=True)) |
                    (models.Q(person__isnull=True) & models.Q(organization__isnull=False) & models.Q(group__isnull=True)) |
                    (models.Q(person__isnull=True) & models.Q(organization__isnull=True) & models.Q(group__isnull=False))
                ),
                name="email_exactly_one_party",
            ),
        ]

    def __str__(self):
        return self.email

    @property
    def party(self):
        return self.person or self.organization or self.group


# =============================================================================
# Demographics - Person demographics
# =============================================================================

class Demographics(BaseModel):
    """Extended demographics for a Person.

    Note: Basic demographics (date_of_birth) are on Person model.
    This model holds additional demographic data.
    """

    GENDER_CHOICES = [
        ('male', _('Male')),
        ('female', _('Female')),
        ('non_binary', _('Non-binary')),
        ('prefer_not_say', _('Prefer not to say')),
        ('other', _('Other')),
    ]

    MARITAL_STATUS_CHOICES = [
        ('single', _('Single')),
        ('married', _('Married')),
        ('divorced', _('Divorced')),
        ('widowed', _('Widowed')),
        ('separated', _('Separated')),
        ('domestic_partner', _('Domestic Partnership')),
        ('prefer_not_say', _('Prefer not to say')),
    ]

    person = models.OneToOneField(
        'Person',
        on_delete=models.CASCADE,
        related_name='demographics',
        verbose_name=_('person'),
    )

    # Gender and family status
    gender = models.CharField(
        _('gender'),
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
    )
    marital_status = models.CharField(
        _('marital status'),
        max_length=20,
        choices=MARITAL_STATUS_CHOICES,
        blank=True,
    )

    # Nationality/Origin
    nationality = models.CharField(_('nationality'), max_length=100, blank=True)
    country_of_birth = models.CharField(_('country of birth'), max_length=100, blank=True)
    ethnicity = models.CharField(_('ethnicity'), max_length=100, blank=True)

    # Language
    preferred_language = models.CharField(
        _('preferred language'),
        max_length=10,
        blank=True,
        help_text=_('ISO 639-1 code (e.g., en, es, fr)'),
    )
    additional_languages = models.JSONField(
        _('additional languages'),
        default=list,
        blank=True,
        help_text=_('List of ISO 639-1 codes'),
    )

    # Education/Occupation
    education_level = models.CharField(_('education level'), max_length=100, blank=True)
    occupation = models.CharField(_('occupation'), max_length=200, blank=True)

    # Household
    household_size = models.PositiveIntegerField(
        _('household size'),
        null=True,
        blank=True,
        help_text=_('Number of people in household'),
    )
    has_children = models.BooleanField(_('has children'), null=True, blank=True)
    number_of_children = models.PositiveIntegerField(
        _('number of children'),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _('demographics')
        verbose_name_plural = _('demographics')

    def __str__(self):
        return f'Demographics for {self.person}'


# =============================================================================
# URL / Social Media - Party web presence
# =============================================================================

class PartyURL(BaseModel):
    """Website or social media URL for any party."""

    URL_TYPES = [
        ('website', _('Website')),
        ('facebook', _('Facebook')),
        ('instagram', _('Instagram')),
        ('twitter', _('Twitter/X')),
        ('linkedin', _('LinkedIn')),
        ('youtube', _('YouTube')),
        ('tiktok', _('TikTok')),
        ('whatsapp', _('WhatsApp Business')),
        ('google_maps', _('Google Maps')),
        ('yelp', _('Yelp')),
        ('github', _('GitHub')),
        ('portfolio', _('Portfolio')),
        ('blog', _('Blog')),
        ('other', _('Other')),
    ]

    # Link to party (one must be set)
    person = models.ForeignKey(
        'Person',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='urls',
        verbose_name=_('person'),
    )
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='urls',
        verbose_name=_('organization'),
    )
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='urls',
        verbose_name=_('group'),
    )

    url_type = models.CharField(
        _('URL type'),
        max_length=20,
        choices=URL_TYPES,
        default='website',
    )
    is_primary = models.BooleanField(_('primary'), default=False)

    # URL fields
    url = models.URLField(_('URL'), max_length=500)
    username = models.CharField(
        _('username/handle'),
        max_length=100,
        blank=True,
        help_text=_('Social media handle without @ symbol'),
    )

    # Metadata
    label = models.CharField(
        _('label'),
        max_length=100,
        blank=True,
        help_text=_('Custom label like "Personal Blog" or "Company LinkedIn"'),
    )
    is_verified = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_('Verified ownership of this URL'),
    )
    is_public = models.BooleanField(
        _('public'),
        default=True,
        help_text=_('Show on public profiles'),
    )

    class Meta:
        verbose_name = _('URL')
        verbose_name_plural = _('URLs')
        ordering = ['-is_primary', 'url_type', '-created_at']
        constraints = [
            # Exactly one party FK must be set
            models.CheckConstraint(
                condition=(
                    (models.Q(person__isnull=False) & models.Q(organization__isnull=True) & models.Q(group__isnull=True)) |
                    (models.Q(person__isnull=True) & models.Q(organization__isnull=False) & models.Q(group__isnull=True)) |
                    (models.Q(person__isnull=True) & models.Q(organization__isnull=True) & models.Q(group__isnull=False))
                ),
                name="partyurl_exactly_one_party",
            ),
        ]

    def __str__(self):
        return f'{self.get_url_type_display()}: {self.url}'

    @property
    def party(self):
        return self.person or self.organization or self.group

    @property
    def icon(self):
        """Returns icon name for the URL type."""
        icons = {
            'website': 'globe',
            'facebook': 'facebook',
            'instagram': 'instagram',
            'twitter': 'twitter',
            'linkedin': 'linkedin',
            'youtube': 'youtube',
            'tiktok': 'music',
            'whatsapp': 'message-circle',
            'google_maps': 'map-pin',
            'yelp': 'star',
            'github': 'github',
            'portfolio': 'briefcase',
            'blog': 'edit-3',
            'other': 'link',
        }
        return icons.get(self.url_type, 'link')
