# Chapter 4: Project Structure

Before we dive into the primitives, you need a place to put them.

This interlude shows you how to structure a project that uses django-primitives. It takes 10 minutes to set up and will save you hours of confusion later.

---

## The Monorepo Structure

All django-primitives packages live in a single repository. Your application will have a similar structure:

```
your-project/
├── packages/                      # Reusable primitives
│   ├── django-basemodels/         # Foundation (UUIDModel, BaseModel)
│   ├── django-parties/            # Identity (Person, Organization)
│   ├── django-rbac/               # Access control (Roles, Permissions)
│   ├── django-catalog/            # Products and services
│   ├── django-ledger/             # Financial transactions
│   ├── django-encounters/         # Workflow state machines
│   ├── django-decisioning/        # Time semantics, decisions
│   ├── django-audit-log/          # Immutable event log
│   ├── django-agreements/         # Contracts and terms
│   ├── django-documents/          # File attachments
│   ├── django-notes/              # Text annotations
│   ├── django-money/              # Currency handling
│   └── django-sequence/           # Sequential IDs
│
├── apps/                          # Your domain applications
│   └── yourapp/                   # Composes primitives
│       ├── models.py              # Empty or minimal
│       ├── services.py            # Business logic
│       ├── views.py               # API/UI endpoints
│       └── tests/                 # Integration tests
│
├── pyproject.toml                 # Root project config
├── CLAUDE.md                      # AI instructions
└── layers.yaml                    # Import boundary rules
```

---

## Why This Structure?

### 1. Primitives Are Packages

Each primitive is a separate installable package:

```toml
# In your app's pyproject.toml
dependencies = [
    "django-basemodels",
    "django-parties",
    "django-catalog",
    "django-ledger",
]
```

This means:
- You can upgrade primitives independently
- You can use primitives in multiple projects
- Dependencies are explicit, not implicit

### 2. Applications Compose, Not Create

Your application code (in `apps/`) should:
- Import from packages
- Compose primitives into domain workflows
- Add domain-specific services

Your application code should NOT:
- Create new Django models (with rare exceptions)
- Duplicate functionality from packages
- Modify primitives directly

### 3. Layer Boundaries Are Enforced

The `layers.yaml` file defines what can import what:

```yaml
# layers.yaml
layers:
  - name: infrastructure
    packages:
      - django_basemodels
      - django_singleton
      - django_sequence

  - name: foundation
    packages:
      - django_parties
      - django_rbac
    allowed_imports:
      - infrastructure

  - name: domain
    packages:
      - django_catalog
      - django_encounters
      - django_agreements
      - django_ledger
      - django_decisioning
      - django_documents
      - django_notes
      - django_money
      - django_audit_log
    allowed_imports:
      - infrastructure
      - foundation

  - name: application
    packages:
      - apps.*
    allowed_imports:
      - infrastructure
      - foundation
      - domain
```

Run `python -m django_layers check` to verify boundaries aren't violated.

---

## Package Structure

Each primitive package follows the same structure:

```
packages/django-parties/
├── pyproject.toml               # Package metadata
├── README.md                    # Usage documentation
├── src/
│   └── django_parties/
│       ├── __init__.py          # Public exports
│       ├── apps.py              # Django app config
│       ├── models.py            # Django models
│       ├── services.py          # Service functions
│       ├── querysets.py         # Custom QuerySet methods
│       ├── mixins.py            # Reusable model mixins
│       ├── exceptions.py        # Custom exceptions
│       └── migrations/
│           ├── __init__.py
│           └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py              # Pytest fixtures
    ├── settings.py              # Test Django settings
    ├── test_models.py           # Model tests
    └── test_services.py         # Service tests
```

### pyproject.toml

```toml
[project]
name = "django-parties"
version = "0.1.0"
description = "Identity primitives for Django applications"
requires-python = ">=3.11"
dependencies = [
    "Django>=4.2",
    "django-basemodels",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-django>=4.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/django_parties"]
```

### __init__.py

Explicit exports only:

```python
# src/django_parties/__init__.py

from django_parties.models import Party, Person, Organization, Group
from django_parties.services import create_person, create_organization

__all__ = [
    # Models
    "Party",
    "Person",
    "Organization",
    "Group",
    # Services
    "create_person",
    "create_organization",
]
```

### apps.py

Django app configuration:

```python
# src/django_parties/apps.py

from django.apps import AppConfig

class DjangoPartiesConfig(AppConfig):
    name = "django_parties"
    verbose_name = "Parties"
    default_auto_field = "django.db.models.UUIDField"
```

---

## Setting Up Your CLAUDE.md

The `CLAUDE.md` file at your project root tells AI assistants how to work with your codebase:

```markdown
# Project: [Your Project Name]

## Primitives in Use

This project uses django-primitives. All domain models come from packages:
- django-parties (Person, Organization, Group, PartyRelationship)
- django-catalog (Category, CatalogItem, Basket, WorkItem)
- django-ledger (Account, Transaction, Entry)
- django-encounters (EncounterDefinition, Encounter, EncounterTransition)
- django-decisioning (Decision, IdempotencyKey)
- django-audit-log (AuditLog)
- django-agreements (Agreement, AgreementParty)

## Must Do

- Use UUID primary keys for all models
- Use DecimalField for money (never float)
- Inherit from UUIDModel or BaseModel
- Wrap mutations in @transaction.atomic
- Add time semantics (effective_at, recorded_at) to events
- Implement soft delete (deleted_at) for domain entities

## Must Not Do

- Never create new Django models (compose existing primitives)
- Never import from higher layers
- Never use auto-increment primary keys
- Never delete audit logs
- Never mutate posted transactions

## Architecture

- Application layer: apps/yourapp/
- Domain layer: packages/django-*
- Foundation layer: django-parties, django-rbac
- Infrastructure layer: django-basemodels

## Commands

- Run tests: `pytest`
- Check layers: `python -m django_layers check`
- Run dev server: `python manage.py runserver`
```

---

## Installing Packages for Development

During development, install packages in editable mode:

```bash
# From project root
pip install -e packages/django-basemodels
pip install -e packages/django-parties
pip install -e packages/django-catalog
# ... etc
```

Or use a requirements file:

```
# requirements-dev.txt
-e packages/django-basemodels
-e packages/django-parties
-e packages/django-catalog
-e packages/django-ledger
-e packages/django-encounters
-e packages/django-decisioning
-e packages/django-audit-log
-e packages/django-agreements
-e packages/django-documents
-e packages/django-notes
-e packages/django-money
-e packages/django-sequence
```

Then:

```bash
pip install -r requirements-dev.txt
```

---

## Django Settings

Your Django settings should include all primitives:

```python
# settings.py

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",

    # Primitives (order matters for migrations)
    "django_basemodels",
    "django_parties",
    "django_rbac",
    "django_catalog",
    "django_ledger",
    "django_encounters",
    "django_decisioning",
    "django_audit_log",
    "django_agreements",
    "django_documents",
    "django_notes",
    "django_money",
    "django_sequence",

    # Your applications
    "apps.yourapp",
]

# Party model configuration
PARTY_PERSON_MODEL = "django_parties.Person"
PARTY_ORGANIZATION_MODEL = "django_parties.Organization"
```

---

## Your First Composition

Here's what your application code looks like when composing primitives:

```python
# apps/yourapp/services.py

from django.db import transaction
from django_parties.models import Person, Organization
from django_catalog.models import CatalogItem, Basket, BasketItem
from django_ledger.services import post_transaction
from django_agreements.models import Agreement
from django_audit_log.services import log_event

@transaction.atomic
def process_order(customer: Person, items: list, payment_method: str):
    """
    Process an order using primitives.

    No new models. Just composition.
    """
    # Create basket (Catalog)
    basket = Basket.objects.create(
        owner=customer,
        status="draft",
    )

    for item_data in items:
        catalog_item = CatalogItem.objects.get(sku=item_data["sku"])
        BasketItem.objects.create(
            basket=basket,
            catalog_item=catalog_item,
            quantity=item_data["quantity"],
            unit_price_snapshot=catalog_item.unit_price,
        )

    # Commit basket (triggers ledger transaction)
    basket.status = "committed"
    basket.save()

    # Create sales agreement (Agreements)
    agreement = Agreement.objects.create(
        agreement_type="sale",
        metadata={
            "basket_id": str(basket.id),
            "payment_method": payment_method,
        }
    )

    # Log the event (Audit)
    log_event(
        target=agreement,
        event_type="order_placed",
        actor=customer,
        metadata={
            "item_count": basket.items.count(),
            "total": str(basket.total),
        }
    )

    return agreement
```

Notice:
- No new models created
- All domain objects come from packages
- Services compose primitives
- Audit logging is automatic

---

## Testing

Tests live in each package:

```python
# packages/django-parties/tests/test_models.py

import pytest
from django_parties.models import Person

@pytest.mark.django_db
class TestPerson:
    def test_create_person(self):
        person = Person.objects.create(
            full_name="Jane Doe",
            email="jane@example.com",
        )

        assert person.id is not None
        assert person.full_name == "Jane Doe"

    def test_person_soft_delete(self):
        person = Person.objects.create(full_name="To Delete")
        person.soft_delete()

        assert person.deleted_at is not None
        assert Person.objects.active().count() == 0
```

Run all tests:

```bash
pytest
```

Run tests for one package:

```bash
pytest packages/django-parties/tests/
```

---

## Adding a New Package

When you need a new primitive (rare), follow this pattern:

**1. Create the package structure:**

```bash
mkdir -p packages/django-newprimitive/src/django_newprimitive
mkdir -p packages/django-newprimitive/tests
```

**2. Copy pyproject.toml and adapt:**

```bash
cp packages/django-parties/pyproject.toml packages/django-newprimitive/
# Edit name, description, dependencies
```

**3. Add to layers.yaml:**

```yaml
- name: domain
  packages:
    - django_newprimitive  # Add here
```

**4. Write tests first (TDD):**

```python
# packages/django-newprimitive/tests/test_models.py

@pytest.mark.django_db
def test_new_model_creation():
    # Write failing test first
    pass
```

**5. Implement the primitive:**

```python
# packages/django-newprimitive/src/django_newprimitive/models.py

from django_basemodels.models import UUIDModel, BaseModel

class NewPrimitive(UUIDModel, BaseModel):
    # Implementation
    pass
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Run all tests | `pytest` |
| Run package tests | `pytest packages/django-parties/` |
| Check layer boundaries | `python -m django_layers check` |
| Make migrations | `python manage.py makemigrations` |
| Apply migrations | `python manage.py migrate` |
| Install package (dev) | `pip install -e packages/django-xxx` |

---

## Summary

| Concept | Purpose |
|---------|---------|
| Monorepo | All primitives in one repository |
| Packages | Reusable, installable components |
| Applications | Compose primitives, add domain logic |
| layers.yaml | Enforce import boundaries |
| CLAUDE.md | AI instructions for your project |
| TDD | Tests first for all primitives |

With this structure in place, you're ready to learn the primitives themselves. Chapter 5 covers the Foundation Layer, followed by Chapter 6: Identity—the most fundamental domain primitive.
