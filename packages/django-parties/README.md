# django-parties

A Django package implementing the **Party Pattern** - an enterprise architecture pattern for modeling entities (Person, Organization, Group) and their relationships.

## Overview

The Party Pattern provides a unified approach to handling different types of entities that can:
- Own things (pets, vehicles, property)
- Have relationships (customer, vendor, employee)
- Do business (buy, sell, contract)
- Be billed or bill others

## Key Concepts

### Person vs User

This is a critical distinction:

| Concept | Purpose | Example |
|---------|---------|---------|
| **Person** | Real-world human identity | John Smith |
| **User** | Authentication/login account | john@email.com login |

**Key relationships:**
- One Person can have multiple Users (email + Google + phone logins)
- A Person can exist without any User (contacts, leads)
- A User can exist without a Person (API/service accounts)

### Party Types

```
Party (Abstract)
├── Person - Individual human beings
├── Organization - Companies, clinics, suppliers
└── Group - Households, families, partnerships
```

### Party Relationships

Relationships link any two parties:
- Person → Organization (employee, contractor, contact)
- Person → Person (spouse, parent, emergency contact)
- Organization → Organization (vendor, partner, client)
- Person → Group (member, head of household)

### Contact Information

Normalized tables for contact data:
- **Address** - Physical/mailing addresses with geolocation
- **Phone** - Phone numbers with SMS/WhatsApp capabilities
- **Email** - Email addresses with marketing preferences
- **PartyURL** - Websites and social media profiles
- **Demographics** - Extended demographic data for Person

## Installation

```bash
pip install django-parties
```

Or for development:

```bash
pip install -e ./path/to/django-parties
```

## Configuration

Add to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_parties',
]
```

Run migrations:

```bash
python manage.py migrate django_parties
```

## Usage

### Creating Parties

```python
from django_parties.models import Person, Organization, Group

# Create a person
person = Person.objects.create(
    first_name="Jane",
    last_name="Doe",
    email="jane@example.com",
    phone="+1-555-0100",
)

# Create an organization
org = Organization.objects.create(
    name="Acme Corp",
    org_type="company",
    tax_id="12-3456789",
)

# Create a household group
household = Group.objects.create(
    name="The Doe Family",
    group_type="household",
    primary_contact=person,
)
```

### Creating Relationships

```python
from django_parties.models import PartyRelationship

# Person works for organization
PartyRelationship.objects.create(
    from_person=person,
    to_organization=org,
    relationship_type="employee",
    title="Software Engineer",
    is_primary=True,
)

# Person is member of household
PartyRelationship.objects.create(
    from_person=person,
    to_group=household,
    relationship_type="head",
)
```

### Contact Information

```python
from django_parties.models import Address, Phone, Email

# Add address to person
Address.objects.create(
    person=person,
    address_type="home",
    is_primary=True,
    line1="123 Main Street",
    city="Springfield",
    state="IL",
    postal_code="62701",
    country="USA",
)

# Add phone number
Phone.objects.create(
    person=person,
    phone_type="mobile",
    is_primary=True,
    country_code="+1",
    number="555-0100",
    can_receive_sms=True,
)

# Add email
Email.objects.create(
    person=person,
    email_type="work",
    email="jane.doe@acme.com",
    is_primary=False,
)
```

### Using Selectors

```python
from django_parties.selectors import (
    get_person_by_id,
    search_people,
    get_employees_of_organization,
    get_primary_address_for_person,
)

# Get person by ID
person = get_person_by_id(1)

# Search people
results = search_people("Jane", limit=10)

# Get employees
employees = get_employees_of_organization(org.id)

# Get primary address
address = get_primary_address_for_person(person.id)
```

### Linking to User Model

To link User accounts to Person, add a ForeignKey in your User model:

```python
# In your accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    person = models.ForeignKey(
        'django_parties.Person',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounts',
    )
```

## Models Reference

### Person

| Field | Type | Description |
|-------|------|-------------|
| first_name | CharField | First name (required) |
| last_name | CharField | Last name |
| middle_name | CharField | Middle name |
| preferred_name | CharField | What they want to be called |
| display_name | CharField | Auto-generated full name |
| date_of_birth | DateField | Birth date |
| date_of_death | DateField | Death date (if applicable) |
| is_active | BooleanField | Active status |
| email | EmailField | Primary email |
| phone | CharField | Primary phone |

### Organization

| Field | Type | Description |
|-------|------|-------------|
| name | CharField | Organization name (required) |
| org_type | CharField | Type (company, clinic, etc.) |
| website | URLField | Website URL |
| tax_id | CharField | Tax ID (EIN, RFC, VAT) |
| legal_name | CharField | Legal business name |
| is_active | BooleanField | Active status |

### Group

| Field | Type | Description |
|-------|------|-------------|
| name | CharField | Group name (required) |
| group_type | CharField | Type (household, family, etc.) |
| primary_contact | ForeignKey | Primary contact person |
| is_active | BooleanField | Active status |

### PartyRelationship

| Field | Type | Description |
|-------|------|-------------|
| from_person/from_organization | ForeignKey | Source party |
| to_person/to_organization/to_group | ForeignKey | Target party |
| relationship_type | CharField | Type of relationship |
| title | CharField | Job title or role |
| contract_start/end | DateField | Contract dates |
| is_primary | BooleanField | Primary relationship of type |
| is_active | BooleanField | Active status |

## Architecture Principles

This package follows these principles from enterprise architecture:

1. **Party Pattern** is foundational - Do not collapse Person/Organization/Group
2. **Separation of Concerns** - Identity is separate from authentication
3. **All relationships flow through PartyRelationship** - Ownership, employment, guardianship, billing
4. **Auditability** - All models have created_at/updated_at

## License

Copyright (c) 2025 Nestor Wheelock. All Rights Reserved.

This software is proprietary and confidential.
