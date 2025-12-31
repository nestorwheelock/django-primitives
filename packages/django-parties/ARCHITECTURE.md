# Architecture: django-parties

**Status:** Stable / Feature-Complete / v0.1.0
**Author:** Nestor Wheelock
**License:** Proprietary

This package provides the Party Pattern for identity and relationships. It sits on top of django-basemodels and provides the identity layer for applications.

---

## Design Intent

- **Identity only** - No domain-specific logic
- **Stable** - Changes require migration notes and justification
- **Composable** - Used by domain packages (accounting, CRM, etc.)

---

## What This Package Provides

| Model | Purpose |
|-------|---------|
| `Person` | Human beings (separate from User/auth) |
| `Organization` | Companies, clinics, suppliers |
| `Group` | Households, families, teams |
| `PartyRelationship` | Links between any parties |
| `Address` | Physical/mailing addresses |
| `Phone` | Phone numbers with SMS/WhatsApp flags |
| `Email` | Email addresses with marketing prefs |
| `Demographics` | Extended demographic data |
| `PartyURL` | Websites and social media |

---

## What This Package Does NOT Do

- No authentication (that's User, not Person)
- No business logic
- No domain-specific relationships
- No views, forms, or templates (except admin)
- No workflows

---

## Hard Rules

1. **All models inherit from BaseModel** - No redefining timestamps or soft delete
2. **No business logic** - Domain logic belongs in application layer
3. **No upward dependencies** - This package depends only on basemodels and Django
4. **Soft delete is mandatory** - `.delete()` sets `deleted_at`, never removes rows

---

## Inheritance

All models inherit from `django_basemodels`:

```python
class Person(UUIDModel, BaseModel, Party):
    ...
```

This provides:
- UUID primary key
- `created_at` / `updated_at` timestamps
- `deleted_at` soft delete
- `objects` manager (excludes deleted)
- `all_objects` manager (includes deleted)

---

## Dependency Direction

```
Application Layer (your app)
    ↓ imports
django-accounting (finance)
    ↓ imports
django-parties (identity)  ← YOU ARE HERE
    ↓ imports
django-basemodels (foundation)
    ↓ imports
Django
```

Never import upward.

---

## The Party Pattern Explained

### Core Concept

A "Party" is any entity that can participate in business relationships:
- **Person** - A human being (NOT a login account)
- **Organization** - A company, clinic, or formal entity
- **Group** - An informal grouping (household, family)

### Person vs User

**CRITICAL:** Person and User are separate concepts.

```
Person (django_parties)          User (your auth app)
├── Real-world identity         ├── Login credentials
├── first_name, last_name       ├── email, password
├── date_of_birth               ├── permissions
├── Contact info                ├── last_login
└── Can exist WITHOUT login     └── Can exist WITHOUT Person
```

**Relationship:**
- One Person can have multiple Users (email login + OAuth)
- A Person can exist without any User (contacts, leads)
- A User can exist without a Person (service accounts, API keys)

**Implementation in your app:**
```python
# In your User model (NOT in django-parties)
class User(AbstractBaseUser):
    person = models.ForeignKey(
        'django_parties.Person',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
```

### PartyRelationship Flexibility

PartyRelationship supports ALL relationship combinations:

| From | To | Example |
|------|-----|---------|
| Person | Organization | Employee, Customer, Contact |
| Person | Person | Emergency Contact, Spouse |
| Person | Group | Household Member |
| Organization | Organization | Vendor, Partner, Subsidiary |

```python
# Person works at Company
PartyRelationship.objects.create(
    from_person=employee,
    to_organization=company,
    relationship_type='employee',
    title='Software Engineer',
)

# Person is emergency contact for Person
PartyRelationship.objects.create(
    from_person=contact,
    to_person=patient,
    relationship_type='emergency_contact',
)
```

---

## Known Gotchas (READ THIS)

### 1. Soft Delete Cascading

**Problem:** Deleting a Person does NOT cascade-delete related addresses, phones, etc.

```python
person = Person.objects.get(pk=...)
person.delete()  # Soft deletes person only
# person.addresses are still visible!
```

**Solution:** Implement cascade logic explicitly in your application:
```python
def soft_delete_person_with_related(person):
    from django.utils import timezone
    now = timezone.now()

    # Delete related objects first
    person.addresses.all().update(deleted_at=now)
    person.phone_numbers.all().update(deleted_at=now)
    person.email_addresses.all().update(deleted_at=now)

    # Then delete the person
    person.delete()
```

### 2. Foreign Keys to Soft-Deleted Parties

**Problem:** FK references to soft-deleted parties still work at DB level.

```python
# Create invoice for customer
invoice = Invoice.objects.create(customer=customer)
customer.delete()  # Soft delete

# FK still works!
invoice.customer  # Returns the soft-deleted customer
invoice.customer.is_deleted  # True
```

**Solution:** Check `is_deleted` in your views/serializers:
```python
class InvoiceSerializer(serializers.ModelSerializer):
    def validate_customer(self, value):
        if value.is_deleted:
            raise ValidationError("Cannot assign to deleted customer")
        return value
```

### 3. Unique Email/Phone Constraints

**Problem:** Same issue as django-basemodels - naive unique constraints break with soft delete.

```python
# Person with email bob@example.com deleted
# Now cannot create new person with same email
```

**Solution:** Use conditional unique constraints:
```python
class Person(UUIDModel, BaseModel, Party):
    # ...
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_person_email'
            )
        ]
```

### 4. Demographics is One-to-One

**Problem:** Trying to create multiple Demographics for same Person.

```python
Demographics.objects.create(person=person)
Demographics.objects.create(person=person)  # IntegrityError!
```

**Solution:** Use get_or_create:
```python
demo, created = Demographics.objects.get_or_create(
    person=person,
    defaults={'gender': 'male'}
)
```

### 5. PartyRelationship Requires Explicit From/To

**Problem:** Forgetting which FK to set.

```python
# WRONG - no from_* set
PartyRelationship.objects.create(
    to_organization=company,
    relationship_type='employee',
)
```

**Solution:** Always set BOTH from_* and to_*:
```python
PartyRelationship.objects.create(
    from_person=employee,      # Who has the relationship
    to_organization=company,   # Target of relationship
    relationship_type='employee',
)
```

### 6. Contact Info Denormalization

**Problem:** Person has both inline contact fields AND related tables.

```python
person.email           # Inline field (convenience)
person.email_addresses # Related Email objects (full data)
```

**Design Decision:** This is intentional:
- Inline fields for quick entry/display
- Related tables for full contact management
- Applications decide which to use

**Recommendation:**
- Use inline fields for simple cases (single email/phone)
- Use related tables when tracking multiple emails, verification status, etc.

### 7. Party Abstract Class

**Problem:** Party is abstract and has no table.

```python
Party.objects.all()  # Error! Party is abstract
```

**Solution:** Query concrete models:
```python
from itertools import chain
all_parties = list(chain(
    Person.objects.all(),
    Organization.objects.all(),
    Group.objects.all(),
))
```

---

## Usage Examples

### Standard Person (Most Cases)

```python
from django_parties.models import Person, Address, Phone

# Create person
person = Person.objects.create(
    first_name='John',
    last_name='Doe',
    email='john@example.com',
    phone='+1 555-1234',
)

# Add detailed address
Address.objects.create(
    person=person,
    address_type='home',
    line1='123 Main St',
    city='Anytown',
    state='CA',
    postal_code='12345',
    is_primary=True,
)
```

### Organization with Contacts

```python
from django_parties.models import Organization, Person, PartyRelationship

# Create organization
org = Organization.objects.create(
    name='Acme Corporation',
    org_type='company',
    tax_id='12-3456789',
)

# Add primary contact
contact = Person.objects.create(
    first_name='Jane',
    last_name='Smith',
)

PartyRelationship.objects.create(
    from_person=contact,
    to_organization=org,
    relationship_type='contact',
    is_primary=True,
)
```

### Household Group

```python
from django_parties.models import Person, Group, PartyRelationship

# Create family members
husband = Person.objects.create(first_name='John', last_name='Smith')
wife = Person.objects.create(first_name='Jane', last_name='Smith')

# Create household
household = Group.objects.create(
    name='Smith Household',
    group_type='household',
    primary_contact=husband,
)

# Add members
for person, role in [(husband, 'head'), (wife, 'spouse')]:
    PartyRelationship.objects.create(
        from_person=person,
        to_group=household,
        relationship_type=role,
    )
```

---

## Testing Your Models

Verify party pattern behavior:

```python
def test_person_soft_delete(self):
    person = Person.objects.create(first_name='Test')
    person.delete()

    assert person.is_deleted is True
    assert Person.objects.filter(pk=person.pk).exists() is False
    assert Person.all_objects.filter(pk=person.pk).exists() is True

def test_party_relationship_links_parties(self):
    person = Person.objects.create(first_name='John')
    org = Organization.objects.create(name='Acme')

    rel = PartyRelationship.objects.create(
        from_person=person,
        to_organization=org,
        relationship_type='employee',
    )

    assert rel.from_party == person
    assert rel.to_party == org

def test_person_age_calculation(self):
    from datetime import date
    person = Person(date_of_birth=date(1990, 1, 1))
    # Age depends on current date
    assert person.age > 0
```

---

## Versioning

This package follows semantic versioning:
- **MAJOR**: Breaking changes to model fields or relationships
- **MINOR**: New features (new models, new fields)
- **PATCH**: Bug fixes only

Pin to specific versions:
```
django-parties==0.1.0
```

---

## Changes

Any modifications to this package require:
- Clear justification
- Migration notes for downstream consumers
- Review of all dependent packages

**Do not add features casually. Identity is boring. Keep it that way.**

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial stable release
- Person, Organization, Group party types
- PartyRelationship for flexible party linking
- Address, Phone, Email contact info
- Demographics extended data
- PartyURL web presence
- 44 comprehensive tests
- Full soft delete support inherited from django-basemodels
