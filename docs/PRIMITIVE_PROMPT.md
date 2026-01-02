# Django Primitives: Module Creation Prompt

Use this prompt to instruct Claude to create new django-primitives packages that follow established patterns.

---

## THE PROMPT

```
You are building a Django primitive package for a modular ERP/business application framework.

## Context

Django-primitives is a collection of 18 standalone, pip-installable packages that compose together to build any business application. Each package follows strict conventions for consistency.

## Package Categories

1. **Foundation** - Base classes inherited by all models (basemodels, singleton)
2. **Infrastructure** - Cross-cutting concerns (modules, layers, decisioning)
3. **Identity** - Who does business (parties, rbac)
4. **Domain** - Core business entities (catalog, encounters, worklog, geo, ledger)
5. **Content** - Attachments and annotations (documents, notes, agreements)
6. **Value Objects** - Immutable domain concepts (money, sequence)

## Your Task

Create a Django primitive package called `django-{name}` that provides: {description}

## Required File Structure

```
django-{name}/
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md          # REQUIRED - design decisions and invariants
├── src/django_{name}/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── querysets.py         # If custom filtering needed
│   ├── services.py          # REQUIRED for domain models with business rules
│   ├── exceptions.py        # If domain-specific errors needed
│   └── migrations/
│       └── __init__.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    └── test_models.py
```

## File Templates

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "django-{name}"
version = "0.1.0"
description = "{One-line description}"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
dependencies = [
    "Django>=4.2",
    "django-basemodels>=0.2.0",  # Provides BaseModel with UUID + timestamps + soft delete
    # Add other django-primitives dependencies as needed
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-django>=4.5"]

[tool.hatch.build.targets.wheel]
packages = ["src/django_{name}"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
python_files = ["test_*.py"]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

### apps.py

```python
from django.apps import AppConfig


class Django{Name}Config(AppConfig):
    name = "django_{name}"
    verbose_name = "{Human Readable Name}"
    default_auto_field = "django.db.models.BigAutoField"
```

### __init__.py (with lazy imports)

```python
"""Django {Name} - {description}.

Models:
    {Model}: {description}

Services (the only supported write path):
    {service_func}: {description}
"""

__version__ = "0.1.0"

__all__ = [
    # Models
    "{Model}",
    # Services
    "{service_func}",
    # Exceptions
    "{Exception}",
]


def __getattr__(name):
    """Lazy import to avoid AppRegistryNotReady."""
    if name == "{Model}":
        from .models import {Model}
        return {Model}

    if name == "{service_func}":
        from .services import {service_func}
        return {service_func}

    if name == "{Exception}":
        from .exceptions import {Exception}
        return {Exception}

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### ARCHITECTURE.md (REQUIRED)

```markdown
# Architecture: django-{name}

**Status:** Alpha / v0.1.0

## Design Intent

- **[Adjective]**: [What this means for the package]
- **[Adjective]**: [What this means for the package]

## What This Provides

| Component | Purpose |
|-----------|---------|
| {Model} | {One-line description} |
| {service_func}() | {One-line description} |

## What This Does NOT Do

- [Excluded responsibility - build on top if needed]
- [Excluded responsibility - build on top if needed]

## Hard Rules

1. [Non-negotiable constraint]
2. [Non-negotiable constraint]

## Write Authority

All writes go through the service layer:

| Operation | Service Function |
|-----------|------------------|
| Create | `create_{entity}()` |
| Update | `update_{entity}()` |
| Delete | `delete_{entity}()` |

**Why services?** Models define structure. Services enforce business rules atomically.

## Invariants

These must ALWAYS be true:

1. [Data integrity rule]
2. [Data integrity rule]

## Concurrency

[How concurrent access is handled - select_for_update, etc.]

## Dependencies

- **Depends on:** django-basemodels
- **Depended on by:** [list or "None yet"]
```

### tests/settings.py

```python
SECRET_KEY = "test-secret-key"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_basemodels",
    "django_{name}",
    "tests",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
```

### tests/conftest.py

```python
import django
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django_basemodels",
                "django_{name}",
                "tests",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
        )
    django.setup()
```

## The Standard Base Class: BaseModel

**All domain models inherit from BaseModel.** This provides:

- `id`: UUID primary key (globally unique, non-guessable)
- `created_at`: When the record was created
- `updated_at`: When the record was last modified
- `deleted_at`: Soft delete timestamp (None if active)
- `objects`: Manager that excludes soft-deleted records
- `all_objects`: Manager that includes all records
- `delete()`: Soft deletes (sets deleted_at)
- `hard_delete()`: Actually removes from database
- `restore()`: Clears deleted_at

```python
from django_basemodels import BaseModel

class MyModel(BaseModel):
    """Domain model with UUID, timestamps, and soft delete built in."""
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "django_{name}"
```

**Do NOT manually add UUID, timestamps, or soft delete fields.** BaseModel handles this.

## Model Patterns

### Pattern 1: Effective Dating (for assignments/periods)

```python
from django.db import models
from django.db.models import Q, F
from django_basemodels import BaseModel

class MyAssignment(BaseModel):
    # valid_from has NO DEFAULT - service layer provides it
    valid_from = models.DateTimeField(
        help_text="When the assignment becomes effective",
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the assignment expires (null = indefinite)",
    )

    class Meta:
        app_label = "django_{name}"
        indexes = [
            models.Index(fields=["valid_from", "valid_to"]),
        ]
        constraints = [
            # Django 6.0+: use 'condition', not 'check'
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gt=F('valid_from')),
                name='{name}_valid_to_after_valid_from'
            ),
        ]
```

**Important:** `valid_from` has no default. The service layer provides `valid_from=timezone.now()` as a convenience parameter. The model enforces correctness; the service provides convenience.

### Pattern 2: Time Semantics (for events/facts)

```python
class MyEvent(BaseModel):
    # When the fact is true (can be backdated by service)
    effective_at = models.DateTimeField(
        help_text="When this happened in the real world"
    )
    # recorded_at comes from BaseModel.created_at - when system recorded it
```

### Pattern 3: Custom QuerySet with Manager

When combining custom queries with soft delete:

```python
from django.db import models
from django.utils import timezone
from django_basemodels import BaseModel, SoftDeleteManager


class MyQuerySet(models.QuerySet):
    """Custom queries for MyModel."""

    def active(self):
        """Return currently active records."""
        now = timezone.now()
        return self.filter(
            valid_from__lte=now
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=now)
        )

    def as_of(self, timestamp):
        """Return records valid at a specific timestamp."""
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=timestamp)
        )


class MyManager(SoftDeleteManager):
    """Manager combining soft-delete filtering with custom queryset."""

    def get_queryset(self):
        return MyQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)

    def active(self):
        return self.get_queryset().active()

    def as_of(self, timestamp):
        return self.get_queryset().as_of(timestamp)


class MyModel(BaseModel):
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)

    objects = MyManager()
    all_objects = models.Manager()
```

### Pattern 4: GenericForeignKey (link to any model)

```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class MyModel(BaseModel):
    # Use CharField for object_id to support UUIDs
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='+',
    )
    target_object_id = models.CharField(max_length=255)
    target = GenericForeignKey("target_content_type", "target_object_id")

    class Meta:
        app_label = "django_{name}"
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"]),
        ]

    def save(self, *args, **kwargs):
        """Ensure GenericFK ID is stored as string."""
        if self.target_object_id is not None:
            self.target_object_id = str(self.target_object_id)
        super().save(*args, **kwargs)
```

### Pattern 5: Projection + Ledger (for versioned entities)

When you need both current state AND complete history:

```python
class Agreement(BaseModel):
    """
    Current state of the agreement (projection).

    The terms field is updated on each amendment.
    For historical terms, query AgreementVersion.
    """
    terms = models.JSONField(help_text="Current terms (projection of latest version)")
    current_version = models.PositiveIntegerField(default=1)

    class Meta:
        app_label = "django_{name}"


class AgreementVersion(BaseModel):
    """
    Immutable version history (ledger).

    Never modified after creation. Each amendment creates a new version.
    """
    agreement = models.ForeignKey(
        Agreement,
        on_delete=models.CASCADE,
        related_name='versions',
    )
    version = models.PositiveIntegerField()
    terms = models.JSONField(help_text="Terms snapshot (immutable)")
    reason = models.TextField(help_text="Why this version was created")

    class Meta:
        app_label = "django_{name}"
        constraints = [
            models.UniqueConstraint(
                fields=['agreement', 'version'],
                name='unique_{name}_version'
            ),
        ]
        ordering = ['-version']
```

**Invariant:** `Agreement.current_version == max(AgreementVersion.version)`

This is maintained by the service layer, not the model.

### Pattern 6: Immutable Value Object (no database)

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))

    def __add__(self, other):
        if self.currency != other.currency:
            raise ValueError("Currency mismatch")
        return Money(self.amount + other.amount, self.currency)
```

## Service Layer Pattern (REQUIRED for domain models)

**Models define structure. Services enforce business rules.**

All writes go through services. Models should NOT have business logic in `save()`.

```python
"""Service functions for {name} operations.

Write through these functions only:
- create_{entity}()
- update_{entity}()
- delete_{entity}()
"""

from django.db import transaction
from django.utils import timezone

from .models import MyModel
from .exceptions import MyError


class MyError(Exception):
    """Base exception for {name} operations."""
    pass


def create_entity(
    *,  # Force keyword arguments
    name: str,
    valid_from: datetime | None = None,  # Convenience default
    **kwargs,
) -> MyModel:
    """
    Create a new entity.

    Args:
        name: Entity name
        valid_from: When effective (defaults to now)

    Returns:
        Created entity

    Raises:
        MyError: If validation fails
    """
    if valid_from is None:
        valid_from = timezone.now()

    # Validate
    if not name:
        raise MyError("Name is required")

    # Create atomically
    with transaction.atomic():
        entity = MyModel.objects.create(
            name=name,
            valid_from=valid_from,
            **kwargs,
        )

    return entity


def update_entity(
    entity: MyModel,
    *,
    reason: str,
    updated_by: "User",
    **updates,
) -> MyModel:
    """
    Update entity with version tracking.

    Uses select_for_update to prevent concurrent modification.
    """
    with transaction.atomic():
        # Lock the row
        entity = MyModel.objects.select_for_update().get(pk=entity.pk)

        # Apply updates
        for field, value in updates.items():
            setattr(entity, field, value)

        entity.save()

    return entity
```

### Concurrency Pattern

For models with version counters or where concurrent updates could cause issues:

```python
def increment_version(entity, new_data, reason, user):
    """Safely increment version with optimistic locking."""
    with transaction.atomic():
        # Lock the row to prevent concurrent modifications
        entity = Entity.objects.select_for_update().get(pk=entity.pk)

        new_version = entity.current_version + 1

        # Create version record (ledger)
        EntityVersion.objects.create(
            entity=entity,
            version=new_version,
            data=new_data,
            reason=reason,
            created_by=user,
        )

        # Update projection
        entity.data = new_data
        entity.current_version = new_version
        entity.save()

    return entity
```

## Test Pattern (TDD)

Write tests FIRST, then implement.

```python
import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='testpass')


@pytest.mark.django_db
class TestMyModel:
    """Tests for MyModel structure."""

    def test_has_uuid_primary_key(self, user):
        """Model should use UUID primary key from BaseModel."""
        from django_{name}.models import MyModel
        import uuid

        obj = MyModel.objects.create(name="Test", created_by=user, valid_from=timezone.now())
        assert isinstance(obj.id, uuid.UUID)

    def test_has_timestamps(self, user):
        """Model should have created_at and updated_at from BaseModel."""
        from django_{name}.models import MyModel

        obj = MyModel.objects.create(name="Test", created_by=user, valid_from=timezone.now())
        assert obj.created_at is not None
        assert obj.updated_at is not None

    def test_soft_delete(self, user):
        """Model should soft delete, not hard delete."""
        from django_{name}.models import MyModel

        obj = MyModel.objects.create(name="Test", created_by=user, valid_from=timezone.now())
        obj.delete()

        assert MyModel.objects.filter(pk=obj.pk).exists() is False
        assert MyModel.all_objects.filter(pk=obj.pk).exists() is True


@pytest.mark.django_db
class TestCreateEntityService:
    """Tests for create_entity service function."""

    def test_creates_entity(self, user):
        """Service should create entity with all required fields."""
        from django_{name}.services import create_entity

        entity = create_entity(name="Test", created_by=user)

        assert entity.pk is not None
        assert entity.name == "Test"
        assert entity.valid_from is not None  # Service provides default

    def test_rejects_empty_name(self, user):
        """Service should reject empty name."""
        from django_{name}.services import create_entity
        from django_{name}.exceptions import MyError

        with pytest.raises(MyError):
            create_entity(name="", created_by=user)
```

## README Pattern

```markdown
# django-{name}

{One paragraph description}

## Design Principles

This package is **infrastructure**, not a workflow engine.

- **[Principle 1]**: [What this means]
- **[Principle 2]**: [What this means]

### What This Is NOT

- Not a [excluded feature] (build on top if needed)
- Not a [excluded feature] (build on top if needed)

## Installation

\`\`\`bash
pip install django-{name}
\`\`\`

Add to INSTALLED_APPS:

\`\`\`python
INSTALLED_APPS = [
    ...
    "django_basemodels",
    "django_{name}",
]
\`\`\`

Run migrations:

\`\`\`bash
python manage.py migrate django_{name}
\`\`\`

## Usage

Always use the service layer for writes:

\`\`\`python
from django_{name}.services import create_entity

entity = create_entity(
    name="Example",
    created_by=request.user,
    valid_from=timezone.now(),  # Be explicit
)
\`\`\`

### Querying

\`\`\`python
from django_{name}.models import MyModel

# Get current records
current = MyModel.objects.active()

# Get records as of a date
historical = MyModel.objects.as_of(some_date)
\`\`\`

## Models

| Model | Purpose |
|-------|---------|
| MyModel | Description |

## Service Functions

| Function | Purpose |
|----------|---------|
| `create_entity()` | Create with validation |
| `update_entity()` | Update with versioning |

## QuerySet Methods

| Method | Description |
|--------|-------------|
| `.active()` | Currently valid records |
| `.as_of(timestamp)` | Records valid at time |

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for design decisions and invariants.

## License

MIT
```

## Hard Rules

1. **Inherit from BaseModel**: All domain models use BaseModel (UUID + timestamps + soft delete)
2. **Service layer for writes**: Business logic lives in services.py, not model.save()
3. **No defaults for valid_from in models**: Service provides convenience, model enforces correctness
4. **No upward dependencies**: Never import from higher-layer packages
5. **Lazy imports**: Use __getattr__ in __init__.py to avoid AppRegistryNotReady
6. **ARCHITECTURE.md required**: Document design intent, hard rules, and invariants
7. **TDD**: Write failing tests FIRST, then implement
8. **Atomic operations**: Use transaction.atomic() for multi-step operations
9. **Concurrency safety**: Use select_for_update() when incrementing counters
10. **Django 6.0 compatible**: Use `condition=` not `check=` in CheckConstraint

## Checklist Before Done

- [ ] All files created per structure
- [ ] pyproject.toml complete with django-basemodels dependency
- [ ] apps.py with default_auto_field
- [ ] __init__.py with lazy imports, __all__, and docstring
- [ ] Models inherit from BaseModel (not manual UUID/timestamps)
- [ ] ARCHITECTURE.md documents design and invariants
- [ ] services.py with all write operations
- [ ] Tests written BEFORE implementation
- [ ] Tests cover UUID, timestamps, soft delete from BaseModel
- [ ] README with design principles and service layer usage
- [ ] Migrations created (run makemigrations)
- [ ] No import errors when installed

Now create the `django-{name}` package following these patterns exactly.
```

---

## USAGE EXAMPLES

### Example 1: Create a Notifications Primitive

```
You are building a Django primitive package...

Your Task: Create a Django primitive package called `django-notifications` that provides:
- Notification model for storing user notifications (inherits BaseModel)
- Support for different notification types (info, warning, error, success)
- Read/unread status tracking with read_at timestamp
- QuerySet methods for filtering by user and read status
- Service functions: create_notification(), mark_as_read(), mark_all_read()
```

### Example 2: Create a Tags Primitive

```
You are building a Django primitive package...

Your Task: Create a Django primitive package called `django-tags` that provides:
- Tag model for categorization (inherits BaseModel)
- ObjectTag model using GenericForeignKey to tag any model
- QuerySet methods for finding objects by tag
- Service functions: create_tag(), tag_object(), untag_object(), bulk_tag()
```

### Example 3: Create a Scheduling Primitive

```
You are building a Django primitive package...

Your Task: Create a Django primitive package called `django-scheduling` that provides:
- TimeSlot model for available time windows with effective dating
- Booking model for reserving slots (projection + ledger pattern for amendments)
- Conflict detection via database constraints
- QuerySet methods for finding available slots
- Service functions: create_slot(), book_slot(), cancel_booking(), amend_booking()
- Concurrency handling with select_for_update for booking operations
```

---

## KEY INSIGHTS FROM EXISTING PACKAGES

### What Makes a Good Primitive

1. **Single Responsibility**: Each package does ONE thing well
2. **Composable**: Works with other primitives without tight coupling
3. **Service Layer**: All writes go through documented service functions
4. **Auditable**: Uses BaseModel for timestamps and soft delete
5. **Documented**: ARCHITECTURE.md explains design decisions and invariants

### Common Mistakes to Avoid

1. **Not using BaseModel** → Manually adding UUID/timestamps/soft delete
2. **Business logic in save()** → Move to services.py
3. **Defaults for valid_from in models** → Service provides convenience
4. **Importing models at module level** → Use lazy imports
5. **Missing ARCHITECTURE.md** → Document hard rules and invariants
6. **Using check= in CheckConstraint** → Django 6.0 uses condition=
7. **No concurrency handling** → Use select_for_update for counters

### Package Dependencies

```
Foundation (no dependencies):
  - django-basemodels (provides BaseModel)
  - django-singleton
  - django-money (value object, no DB)

Platform (depends on foundation):
  - django-decisioning → basemodels
  - django-parties → basemodels
  - django-audit-log → basemodels, decisioning

Domain (depends on platform):
  - django-rbac → basemodels, parties
  - django-catalog → basemodels, decisioning
  - django-encounters → basemodels, decisioning
  - django-worklog → basemodels, decisioning
  - django-geo → basemodels
  - django-ledger → basemodels, money
  - django-documents → basemodels
  - django-notes → basemodels
  - django-agreements → basemodels
  - django-sequence → basemodels
```

---

## QUICK REFERENCE

| Need | Pattern | Example |
|------|---------|---------|
| Base model with all features | `class X(BaseModel)` | All domain models |
| Effective dating | valid_from/valid_to + CheckConstraint | Assignments, agreements |
| Current + history | Projection + Ledger pattern | Agreements, versioned entities |
| Link to any model | GenericForeignKey with CharField | Worklog, documents |
| Custom queries + soft delete | Custom Manager extending SoftDeleteManager | Agreements |
| Atomic writes | service function with transaction.atomic | All mutations |
| Safe counter increment | select_for_update() | Version numbers |
| Immutable values | frozen dataclass | Money |
