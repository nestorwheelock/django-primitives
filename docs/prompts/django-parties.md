# Prompt: Rebuild django-parties

## Instruction

Create a Django package called `django-parties` that provides the Party pattern with Person, Organization, and Group abstractions.

## Package Purpose

Implement the Party pattern for unified contact management:
- `Person` - Individual human contacts
- `Organization` - Companies, institutions, entities
- `Group` - Collections of parties
- `PartyRelationship` - Typed relationships between parties
- Contact info: `Address`, `Phone`, `Email`, `PartyURL`
- `Demographics` - Optional demographic data for persons

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel, BaseModel, soft delete)

## File Structure

```
packages/django-parties/
├── pyproject.toml
├── README.md
├── src/django_parties/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── mixins.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_person.py
    ├── test_organization.py
    ├── test_group.py
    ├── test_relationship.py
    └── test_contact_info.py
```

## Mixins Specification

### mixins.py

```python
from django.db import models

class PartyBaseMixin(models.Model):
    """Shared fields for all party types."""
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.name
        super().save(*args, **kwargs)


class AddressMixin(models.Model):
    """Denormalized address fields for models that need inline address."""
    address_line1 = models.CharField(max_length=255, blank=True, default='')
    address_line2 = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=100, default='US')

    class Meta:
        abstract = True

    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        city_state_zip = ', '.join(filter(None, [
            self.city,
            ' '.join(filter(None, [self.state, self.postal_code]))
        ]))
        if city_state_zip:
            parts.append(city_state_zip)
        if self.country and self.country != 'US':
            parts.append(self.country)
        return '\n'.join(parts)
```

## Models Specification

### Person Model

```python
from django.db import models
from django_basemodels.models import UUIDModel, BaseModel
from .mixins import PartyBaseMixin

class Person(UUIDModel, BaseModel, PartyBaseMixin):
    """Individual human contact."""
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, default='')
    prefix = models.CharField(max_length=20, blank=True, default='')  # Mr., Dr., etc.
    suffix = models.CharField(max_length=20, blank=True, default='')  # Jr., III, etc.

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'person'
        verbose_name_plural = 'people'
        ordering = ['last_name', 'first_name']

    def save(self, *args, **kwargs):
        # Build name from components if not set
        if not self.name:
            self.name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.name
```

### Organization Model

```python
class OrganizationType(models.TextChoices):
    COMPANY = 'company', 'Company'
    NONPROFIT = 'nonprofit', 'Non-Profit'
    GOVERNMENT = 'government', 'Government'
    EDUCATIONAL = 'educational', 'Educational'
    HEALTHCARE = 'healthcare', 'Healthcare'
    OTHER = 'other', 'Other'


class Organization(UUIDModel, BaseModel, PartyBaseMixin):
    """Company, institution, or other organizational entity."""
    legal_name = models.CharField(max_length=255, blank=True, default='')
    org_type = models.CharField(
        max_length=20,
        choices=OrganizationType.choices,
        default=OrganizationType.COMPANY
    )
    tax_id = models.CharField(max_length=50, blank=True, default='')
    website = models.URLField(blank=True, default='')

    # Parent organization for hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subsidiaries'
    )

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'organization'
        verbose_name_plural = 'organizations'
        ordering = ['name']

    def __str__(self):
        return self.display_name or self.name
```

### Group Model

```python
class Group(UUIDModel, BaseModel, PartyBaseMixin):
    """Collection of parties (persons and/or organizations)."""
    group_type = models.CharField(max_length=50, blank=True, default='')
    description = models.TextField(blank=True, default='')

    # Members via M2M through model
    members = models.ManyToManyField(
        'Person',
        through='GroupMembership',
        related_name='groups'
    )
    org_members = models.ManyToManyField(
        'Organization',
        through='GroupOrgMembership',
        related_name='groups'
    )

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'group'
        verbose_name_plural = 'groups'
        ordering = ['name']

    def __str__(self):
        return self.display_name or self.name


class GroupMembership(UUIDModel, BaseModel):
    """Person membership in a group."""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='person_memberships')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=100, blank=True, default='')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'django_parties'
        unique_together = ['group', 'person']

    def __str__(self):
        return f"{self.person} in {self.group}"


class GroupOrgMembership(UUIDModel, BaseModel):
    """Organization membership in a group."""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='org_memberships')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=100, blank=True, default='')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'django_parties'
        unique_together = ['group', 'organization']

    def __str__(self):
        return f"{self.organization} in {self.group}"
```

### PartyRelationship Model

```python
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class RelationshipType(models.TextChoices):
    EMPLOYEE = 'employee', 'Employee Of'
    MEMBER = 'member', 'Member Of'
    OWNER = 'owner', 'Owner Of'
    CONTACT = 'contact', 'Contact For'
    REPORTS_TO = 'reports_to', 'Reports To'
    PARTNER = 'partner', 'Partner With'
    VENDOR = 'vendor', 'Vendor For'
    CLIENT = 'client', 'Client Of'
    OTHER = 'other', 'Other'


class PartyRelationship(UUIDModel, BaseModel):
    """Typed relationship between any two parties."""
    # From party (GenericFK)
    from_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    from_id = models.CharField(max_length=255)
    from_party = GenericForeignKey('from_content_type', 'from_id')

    # To party (GenericFK)
    to_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    to_id = models.CharField(max_length=255)
    to_party = GenericForeignKey('to_content_type', 'to_id')

    relationship_type = models.CharField(
        max_length=20,
        choices=RelationshipType.choices,
        default=RelationshipType.OTHER
    )
    description = models.TextField(blank=True, default='')

    # Validity period
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'party relationship'
        verbose_name_plural = 'party relationships'

    def save(self, *args, **kwargs):
        self.from_id = str(self.from_id)
        self.to_id = str(self.to_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.from_party} {self.relationship_type} {self.to_party}"
```

### Contact Info Models

```python
class AddressType(models.TextChoices):
    HOME = 'home', 'Home'
    WORK = 'work', 'Work'
    BILLING = 'billing', 'Billing'
    SHIPPING = 'shipping', 'Shipping'
    OTHER = 'other', 'Other'


class Address(UUIDModel, BaseModel):
    """Postal address linked to a party."""
    # Owner (GenericFK)
    owner_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    owner_id = models.CharField(max_length=255)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    address_type = models.CharField(
        max_length=20,
        choices=AddressType.choices,
        default=AddressType.HOME
    )
    is_primary = models.BooleanField(default=False)

    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='US')

    # Optional coordinates
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'address'
        verbose_name_plural = 'addresses'

    def save(self, *args, **kwargs):
        self.owner_id = str(self.owner_id)
        super().save(*args, **kwargs)

    @property
    def full_address(self) -> str:
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        if self.country != 'US':
            parts.append(self.country)
        return '\n'.join(parts)

    def __str__(self):
        return f"{self.address_type}: {self.city}, {self.state}"


class PhoneType(models.TextChoices):
    MOBILE = 'mobile', 'Mobile'
    HOME = 'home', 'Home'
    WORK = 'work', 'Work'
    FAX = 'fax', 'Fax'
    OTHER = 'other', 'Other'


class Phone(UUIDModel, BaseModel):
    """Phone number linked to a party."""
    owner_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    owner_id = models.CharField(max_length=255)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    phone_type = models.CharField(
        max_length=20,
        choices=PhoneType.choices,
        default=PhoneType.MOBILE
    )
    is_primary = models.BooleanField(default=False)
    number = models.CharField(max_length=30)
    extension = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'phone'
        verbose_name_plural = 'phones'

    def save(self, *args, **kwargs):
        self.owner_id = str(self.owner_id)
        super().save(*args, **kwargs)

    def __str__(self):
        ext = f" x{self.extension}" if self.extension else ""
        return f"{self.phone_type}: {self.number}{ext}"


class EmailType(models.TextChoices):
    PERSONAL = 'personal', 'Personal'
    WORK = 'work', 'Work'
    OTHER = 'other', 'Other'


class Email(UUIDModel, BaseModel):
    """Email address linked to a party."""
    owner_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    owner_id = models.CharField(max_length=255)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    email_type = models.CharField(
        max_length=20,
        choices=EmailType.choices,
        default=EmailType.PERSONAL
    )
    is_primary = models.BooleanField(default=False)
    address = models.EmailField()

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'email'
        verbose_name_plural = 'emails'

    def save(self, *args, **kwargs):
        self.owner_id = str(self.owner_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email_type}: {self.address}"


class PartyURL(UUIDModel, BaseModel):
    """URL/link associated with a party (social, website, etc)."""
    owner_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    owner_id = models.CharField(max_length=255)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    url_type = models.CharField(max_length=50)  # website, linkedin, twitter, etc.
    url = models.URLField()

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'party URL'
        verbose_name_plural = 'party URLs'

    def save(self, *args, **kwargs):
        self.owner_id = str(self.owner_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.url_type}: {self.url}"
```

### Demographics Model

```python
class Demographics(UUIDModel, BaseModel):
    """Optional demographic data for a person."""
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        related_name='demographics'
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=50, blank=True, default='')
    nationality = models.CharField(max_length=100, blank=True, default='')
    preferred_language = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        app_label = 'django_parties'
        verbose_name = 'demographics'
        verbose_name_plural = 'demographics'

    def __str__(self):
        return f"Demographics for {self.person}"
```

## Test Cases (44 tests)

### Person Tests (10 tests)
1. `test_person_creation` - Create with required fields
2. `test_person_has_uuid_pk` - UUID primary key
3. `test_person_has_timestamps` - created_at, updated_at
4. `test_person_name_built_from_components` - Auto-builds name
5. `test_person_display_name_defaults_to_name` - Default display name
6. `test_person_soft_delete` - Soft delete sets deleted_at
7. `test_person_str_representation` - String returns display_name
8. `test_person_ordering` - Ordered by last_name, first_name
9. `test_person_prefix_suffix_optional` - Optional fields work
10. `test_person_metadata_json_field` - JSONField works

### Organization Tests (8 tests)
1. `test_organization_creation` - Create with required fields
2. `test_organization_has_uuid_pk` - UUID primary key
3. `test_organization_types` - All org types work
4. `test_organization_parent_hierarchy` - Parent FK works
5. `test_organization_subsidiaries_relation` - Reverse relation
6. `test_organization_soft_delete` - Soft delete works
7. `test_organization_str_representation` - String returns name
8. `test_organization_website_optional` - Optional fields

### Group Tests (8 tests)
1. `test_group_creation` - Create group
2. `test_group_add_person_member` - Add person via M2M
3. `test_group_add_org_member` - Add org via M2M
4. `test_group_membership_role` - Role field works
5. `test_group_membership_unique_constraint` - No duplicate members
6. `test_group_soft_delete` - Soft delete works
7. `test_group_str_representation` - String returns name
8. `test_group_members_relation` - Both member types

### PartyRelationship Tests (6 tests)
1. `test_relationship_person_to_org` - Person employee of org
2. `test_relationship_org_to_org` - Org vendor of org
3. `test_relationship_person_to_person` - Person reports to person
4. `test_relationship_validity_period` - valid_from/valid_to
5. `test_relationship_types` - All types work
6. `test_relationship_str_representation` - String format

### Contact Info Tests (12 tests)
1. `test_address_creation` - Create address
2. `test_address_full_address_property` - Formatted address
3. `test_address_coordinates_optional` - lat/lng nullable
4. `test_address_primary_flag` - is_primary works
5. `test_phone_creation` - Create phone
6. `test_phone_extension_optional` - Extension works
7. `test_phone_str_with_extension` - String includes ext
8. `test_email_creation` - Create email
9. `test_email_primary_flag` - is_primary works
10. `test_party_url_creation` - Create URL
11. `test_demographics_one_to_one` - Linked to person
12. `test_demographics_all_fields_optional` - All nullable

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    'Person',
    'Organization',
    'OrganizationType',
    'Group',
    'GroupMembership',
    'GroupOrgMembership',
    'PartyRelationship',
    'RelationshipType',
    'Address',
    'AddressType',
    'Phone',
    'PhoneType',
    'Email',
    'EmailType',
    'PartyURL',
    'Demographics',
    'PartyBaseMixin',
    'AddressMixin',
]

def __getattr__(name):
    if name in ('Person', 'Organization', 'OrganizationType', 'Group',
                'GroupMembership', 'GroupOrgMembership', 'PartyRelationship',
                'RelationshipType', 'Address', 'AddressType', 'Phone',
                'PhoneType', 'Email', 'EmailType', 'PartyURL', 'Demographics'):
        from .models import (
            Person, Organization, OrganizationType, Group,
            GroupMembership, GroupOrgMembership, PartyRelationship,
            RelationshipType, Address, AddressType, Phone,
            PhoneType, Email, EmailType, PartyURL, Demographics
        )
        return locals()[name]
    if name in ('PartyBaseMixin', 'AddressMixin'):
        from .mixins import PartyBaseMixin, AddressMixin
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Party Pattern**: Unified Person/Organization/Group hierarchy
2. **GenericFK Contact Info**: Address/Phone/Email attach to any party
3. **Relationship Types**: Typed bidirectional relationships
4. **Soft Delete**: Via BaseModel inheritance
5. **UUID Primary Keys**: Via UUIDModel inheritance
6. **Auto Name Building**: Person name from first/last components

## Usage Examples

```python
from django_parties import (
    Person, Organization, Group, PartyRelationship,
    Address, Phone, Email, RelationshipType
)

# Create person
john = Person.objects.create(
    first_name='John',
    last_name='Doe',
    display_name='Johnny D'
)

# Create organization
acme = Organization.objects.create(
    name='Acme Corp',
    org_type='company',
    website='https://acme.com'
)

# Create relationship
PartyRelationship.objects.create(
    from_party=john,
    to_party=acme,
    relationship_type=RelationshipType.EMPLOYEE
)

# Add contact info
Address.objects.create(
    owner=john,
    address_type='home',
    address_line1='123 Main St',
    city='Springfield',
    state='IL',
    postal_code='62701',
    is_primary=True
)

Phone.objects.create(
    owner=john,
    phone_type='mobile',
    number='+1-555-123-4567',
    is_primary=True
)

Email.objects.create(
    owner=john,
    email_type='work',
    address='john@acme.com',
    is_primary=True
)

# Create group with members
team = Group.objects.create(name='Engineering Team')
team.members.add(john, through_defaults={'role': 'Lead'})
team.org_members.add(acme, through_defaults={'role': 'Sponsor'})
```

## Acceptance Criteria

- [ ] Person model with name components
- [ ] Organization model with type and hierarchy
- [ ] Group model with M2M members
- [ ] PartyRelationship with GenericFK parties
- [ ] Address/Phone/Email/PartyURL with GenericFK owner
- [ ] Demographics one-to-one with Person
- [ ] All 44 tests passing
- [ ] README with usage examples
