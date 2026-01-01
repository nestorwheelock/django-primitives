# Django Primitives: Module Creation Prompt

Use this prompt to instruct Claude to create new django-primitives packages that follow established patterns.

---

## THE PROMPT

```
You are building a Django primitive package for a modular ERP/business application framework.

## Context

Django-primitives is a collection of 18+ standalone, pip-installable packages that compose together to build any business application. Each package follows strict conventions for consistency.

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
├── src/django_{name}/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── querysets.py      # If custom filtering needed
│   ├── services.py       # If complex operations needed
│   ├── mixins.py         # If adding capabilities to other models
│   ├── exceptions.py     # If domain-specific errors needed
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
"""Django {Name} - {description}."""

__version__ = "0.1.0"

__all__ = [
    # List public classes
]


def __getattr__(name):
    """Lazy import to avoid AppRegistryNotReady."""
    if name == "SomeModel":
        from .models import SomeModel
        return SomeModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### tests/settings.py

```python
SECRET_KEY = "test-secret-key"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_{name}",
    # Add dependencies
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
                "django_{name}",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
        )
    django.setup()
```

## Model Patterns to Use

### Pattern 1: UUID Primary Key (recommended for all models)

```python
import uuid
from django.db import models

class MyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
```

### Pattern 2: Timestamps (all models should have these)

```python
class MyModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Pattern 3: Soft Delete (domain models)

```python
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class MyModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])
```

### Pattern 4: Time Semantics (for events/facts)

```python
class MyEvent(models.Model):
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the fact is true (can be backdated)"
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When system recorded (immutable)"
    )
```

### Pattern 5: Effective Dating (for assignments/periods)

```python
class MyAssignment(models.Model):
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["valid_from", "valid_to"]),
        ]
```

### Pattern 6: Custom QuerySet

```python
class MyQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def as_of(self, timestamp):
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=timestamp)
        )


class MyModel(models.Model):
    objects = MyQuerySet.as_manager()
```

### Pattern 7: GenericForeignKey (link to any model)

```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class MyModel(models.Model):
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_object_id = models.CharField(max_length=255)
    target = GenericForeignKey("target_content_type", "target_object_id")

    class Meta:
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"]),
        ]
```

### Pattern 8: Immutable Value Object (no database)

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

## Service Layer Pattern

```python
from django.db import transaction

def do_operation(entity, **kwargs):
    """
    Perform operation on entity.

    Args:
        entity: The target entity
        **kwargs: Operation parameters

    Returns:
        Result of operation

    Raises:
        DomainError: If operation invalid
    """
    # Validate
    if not entity.can_operate():
        raise DomainError("Cannot operate")

    # Execute atomically
    with transaction.atomic():
        result = entity.operate(**kwargs)
        entity.save()

    return result
```

## Test Pattern (TDD)

```python
import pytest
from decimal import Decimal

@pytest.mark.django_db
class TestMyModel:
    def test_creation(self):
        """Model can be created with required fields."""
        from django_{name}.models import MyModel

        obj = MyModel.objects.create(
            name="Test",
            value=Decimal("10.00"),
        )

        assert obj.pk is not None
        assert obj.name == "Test"

    def test_some_behavior(self):
        """Model exhibits expected behavior."""
        # Arrange
        # Act
        # Assert
```

## README Pattern

```markdown
# django-{name}

{One paragraph description}

## Installation

\`\`\`bash
pip install django-{name}
\`\`\`

Add to INSTALLED_APPS:

\`\`\`python
INSTALLED_APPS = [
    ...
    "django_{name}",
]
\`\`\`

Run migrations:

\`\`\`bash
python manage.py migrate django_{name}
\`\`\`

## Usage

\`\`\`python
from django_{name}.models import MyModel

# Example usage
obj = MyModel.objects.create(name="Example")
\`\`\`

## Models

| Model | Purpose |
|-------|---------|
| MyModel | Description |

## QuerySet Methods

- `active()` - Filter to active records
- `as_of(timestamp)` - Records valid at time

## License

MIT
```

## Hard Rules

1. **TDD**: Write failing tests FIRST, then implement
2. **UUID PKs**: All models use UUID primary keys
3. **Timestamps**: All models have created_at/updated_at
4. **Soft Delete**: Domain models use soft delete, not hard delete
5. **No Upward Dependencies**: Never import from higher-layer packages
6. **Lazy Imports**: Use __getattr__ in __init__.py to avoid AppRegistryNotReady
7. **Type Hints**: All functions have type hints
8. **Docstrings**: All public APIs documented
9. **Atomic Operations**: Use @transaction.atomic for multi-step operations
10. **Custom Exceptions**: Domain packages define their own exceptions

## Checklist Before Done

- [ ] All files created per structure
- [ ] pyproject.toml complete with dependencies
- [ ] apps.py with default_auto_field
- [ ] __init__.py with lazy imports and __all__
- [ ] Models follow patterns above
- [ ] Tests written and passing
- [ ] README with installation and usage
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
- Notification model for storing user notifications
- Support for different notification types (info, warning, error, success)
- Read/unread status tracking
- QuerySet methods for filtering by user and read status
- Service function to send notifications
```

### Example 2: Create a Tags Primitive

```
You are building a Django primitive package...

Your Task: Create a Django primitive package called `django-tags` that provides:
- Tag model for categorization
- ObjectTag model using GenericForeignKey to tag any model
- QuerySet methods for finding objects by tag
- Service functions for bulk tagging operations
```

### Example 3: Create a Scheduling Primitive

```
You are building a Django primitive package...

Your Task: Create a Django primitive package called `django-scheduling` that provides:
- TimeSlot model for available time windows
- Booking model for reserving slots
- Conflict detection logic
- QuerySet methods for finding available slots
- Service functions for booking with atomic conflict checking
```

---

## KEY INSIGHTS FROM EXISTING PACKAGES

### What Makes a Good Primitive

1. **Single Responsibility**: Each package does ONE thing well
2. **Composable**: Works with other primitives without tight coupling
3. **Swappable**: Uses settings for model references where flexibility needed
4. **Tested**: High test coverage with real scenarios
5. **Documented**: Clear README and ARCHITECTURE.md

### Common Mistakes to Avoid

1. **Importing models at module level** → Use lazy imports
2. **Hard-coding model references** → Use settings + get_model()
3. **Missing indexes** → Add indexes for common query patterns
4. **No custom exceptions** → Domain errors should be specific
5. **Business logic in models** → Move to services.py
6. **Missing __all__** → Define public API explicitly

### Package Dependencies

```
Foundation (no dependencies):
  - django-basemodels
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
  - django-geo → (standalone)
  - django-ledger → basemodels, money
  - django-documents → basemodels
  - django-notes → basemodels
  - django-agreements → basemodels, decisioning
  - django-sequence → basemodels
```

---

## QUICK REFERENCE

| Need | Pattern | Example Package |
|------|---------|-----------------|
| Base model with UUID/timestamps | UUIDModel + TimeStampedModel | django-basemodels |
| Soft delete | SoftDeleteModel + Manager | django-basemodels |
| One-row config | SingletonModel | django-singleton |
| Time semantics | TimeSemanticsMixin | django-decisioning |
| Validity periods | EffectiveDatedMixin | django-rbac |
| Link to any model | GenericForeignKey | django-worklog |
| Geographic queries | Custom QuerySet | django-geo |
| Immutable values | frozen dataclass | django-money |
| Idempotent operations | @idempotent decorator | django-decisioning |
| Feature flags | Module + OrgModuleState | django-modules |
