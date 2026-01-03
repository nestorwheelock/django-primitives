# Django Primitives Development Instructions

You are developing reusable Django packages for the django-primitives monorepo. Follow these instructions exactly.

---

## PROJECT CONTEXT

This is a monorepo of 18 standalone Django packages that compose to build ERP/business applications:

**Foundation:** django-basemodels, django-singleton, django-modules, django-layers
**Identity:** django-parties, django-rbac
**Infrastructure:** django-decisioning, django-audit-log
**Domain:** django-catalog, django-encounters, django-worklog, django-geo, django-ledger
**Content:** django-documents, django-notes, django-agreements
**Value Objects:** django-money, django-sequence

**Dependency Rule:** Never import from a higher layer. Foundation has no dependencies. Each layer only imports from layers below it.

---

## DATABASE: PostgreSQL Only

**This ecosystem is PostgreSQL-only.** All packages assume PostgreSQL semantics for:

- **Constraints:** Partial UniqueConstraints, CheckConstraints, expression indexes
- **Concurrency:** `select_for_update()`, row-level locking, transaction isolation
- **Data types:** UUID (native), JSONB, array fields where appropriate
- **Indexes:** Partial indexes, GIN/GiST indexes for JSONB

**Hard Rules:**

1. **No SQLite fallback** - Tests run against PostgreSQL
2. **Prefer DB-enforced invariants** - Use constraints instead of application validation
3. **Use PostgreSQL-specific features** - When they provide correctness or performance benefits
4. **CI runs PostgreSQL** - Development and CI both use PostgreSQL containers

---

### Standardized Patterns

**1. UUIDField (Native PostgreSQL UUID)**
```python
# All models use native PostgreSQL UUID type
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
```
- Uses PostgreSQL `uuid` type, not `varchar(36)`
- Indexed efficiently, compares as native type
- All GenericFKs use `CharField(max_length=255)` for UUID compatibility

**2. Default Indexes for Common Query Paths**
```python
class Meta:
    indexes = [
        # Composite for GenericFK lookups
        models.Index(fields=["content_type", "object_id"]),
        # Temporal queries (common in all time-semantic models)
        models.Index(fields=["effective_at"]),
        models.Index(fields=["created_at"]),
        # Soft-delete aware queries
        models.Index(fields=["deleted_at"]),
        # State machine lookups
        models.Index(fields=["status", "created_at"]),
    ]
```

**3. Soft-Delete Pattern (Standardized via BaseModel)**
```python
# All domain models inherit from django_basemodels.BaseModel
# which provides:
deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def with_deleted(self):
        return super().get_queryset()

objects = SoftDeleteManager()  # Default excludes deleted
all_objects = models.Manager()  # Includes deleted

def delete(self):  # Soft delete
    self.deleted_at = timezone.now()
    self.save(update_fields=["deleted_at", "updated_at"])

def hard_delete(self):  # Actual deletion
    super().delete()
```

**4. Deferrable Constraints (For Ledger Integrity)**
```python
# Use DEFERRABLE INITIALLY DEFERRED for ledger-like constraints
# that need to be validated at COMMIT, not INSERT

# Example: Transaction must balance (sum of debits = sum of credits)
# This is validated in post() service, not as a DB constraint
# because cross-row constraints require triggers in PostgreSQL

# For foreign key cycles (rare), use:
models.ForeignKey(
    ...,
    db_constraint=True,
    # Add in migration: ALTER TABLE ... ADD CONSTRAINT ... DEFERRABLE INITIALLY DEFERRED
)
```

**Decision on Deferrable Constraints:**
- **Ledger balancing:** Use service layer validation (post() method) rather than DB triggers
- **FK cycles:** Use deferrable constraints if needed for circular references
- **General rule:** Prefer immediate constraints; use deferrable only when insertion order matters

---

**Test Configuration:**

```python
# tests/settings.py - USE THIS TEMPLATE
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_db",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

For local development, run PostgreSQL in Docker:
```bash
docker run -d --name postgres-test -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
```

---

## PHASE 1: SPEC (When Asked to Create a New Package)

When asked to create a new django primitive package, FIRST create planning documents before any code.

### Create Project Charter

Create `packages/django-{name}/SPEC.md`:

```markdown
# django-{name} Specification

## What
[One paragraph: what this package provides]

## Why
[One paragraph: what problem it solves, why it's needed]

## How
[One paragraph: technical approach]

## Success Criteria
- [ ] [Measurable outcome 1]
- [ ] [Measurable outcome 2]
- [ ] All tests passing (>95% coverage)

## Risks
- [Risk 1 and mitigation]
- [Risk 2 and mitigation]

## Scope

**IN SCOPE:**
- [Feature 1]
- [Feature 2]

**OUT OF SCOPE:**
- [Excluded feature 1]
- [Excluded feature 2]
```

### Create User Stories

For each feature, create a user story in this format:

```markdown
## S-001: [Story Title]

**As a** [developer/user type]
**I want** [capability]
**So that** [benefit]

### Acceptance Criteria
- [ ] When I [action], [expected result]
- [ ] When I [action], [expected result]

### Definition of Done
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] Code reviewed
```

### Create Task Breakdown

Break each story into tasks:

```markdown
## T-001: [Task Title]

**Story:** S-001
**Estimate:** [X hours]

### Deliverables
- [ ] [Concrete deliverable 1]
- [ ] [Concrete deliverable 2]

### Test Cases
- test_[scenario_1]
- test_[scenario_2]
```

---

## PHASE 2: ARCHITECTURE (Before Writing Code)

Create `packages/django-{name}/ARCHITECTURE.md`:

```markdown
# Architecture: django-{name}

**Status:** Alpha / v0.1.0

## Design Intent

- **[Adjective]**: [What this means for the package]
- **[Adjective]**: [What this means for the package]

## What This Provides

| Component | Purpose |
|-----------|---------|
| [Model/Class] | [One-line description] |

## What This Does NOT Do

- [Excluded responsibility 1]
- [Excluded responsibility 2]

## Hard Rules

1. [Non-negotiable constraint]
2. [Non-negotiable constraint]

## Invariants

- [Data integrity rule that must always be true]
- [Data integrity rule that must always be true]

## Dependencies

- Depends on: [list packages this imports from]
- Depended on by: [list packages that import this]
```

---

## PHASE 3: TDD WORKFLOW (Writing Code)

### TDD Stop Gate

BEFORE writing ANY implementation code, output this confirmation:

```
=== TDD STOP GATE ===
Package: django-{name}
Task: [current task]
[ ] I have read the SPEC and ARCHITECTURE
[ ] I am writing TESTS FIRST
[ ] Tests will fail because implementation doesn't exist
=== PROCEEDING WITH FAILING TESTS ===
```

### Write Failing Tests First

1. Create test file: `tests/test_{feature}.py`
2. Write test cases from the task's Test Cases list
3. Run pytest and SHOW the failing output
4. Confirm tests fail because code doesn't exist

### Implement Minimal Code

1. Write the minimum code to make ONE test pass
2. Run pytest and show output
3. Repeat until all tests pass

### Refactor

1. Clean up code while keeping tests green
2. Run pytest after each change
3. Never break passing tests

### Output Completion

```
=== TDD CYCLE COMPLETE ===
Tests written BEFORE implementation: YES
All tests passing: [X/X]
Coverage: [X%]
=== READY FOR COMMIT ===
```

---

## PHASE 4: IMPLEMENTATION PATTERNS

### File Structure

Always create this exact structure:

```
packages/django-{name}/
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
├── src/django_{name}/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── querysets.py      # if custom queries needed
│   ├── services.py       # if business logic needed
│   ├── exceptions.py     # if custom errors needed
│   └── migrations/
│       └── __init__.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    └── test_models.py
```

### pyproject.toml

Always use this template:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "django-{name}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
dependencies = ["Django>=4.2"]

[tool.hatch.build.targets.wheel]
packages = ["src/django_{name}"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
python_files = ["test_*.py"]
pythonpath = ["."]
testpaths = ["tests"]
```

### apps.py

Always use this template:

```python
from django.apps import AppConfig


class Django{Name}Config(AppConfig):
    name = "django_{name}"
    verbose_name = "{Human Name}"
    default_auto_field = "django.db.models.BigAutoField"
```

### __init__.py

Always use lazy imports to prevent AppRegistryNotReady:

```python
__version__ = "0.1.0"

__all__ = ["Model1", "Model2"]


def __getattr__(name):
    if name == "Model1":
        from .models import Model1
        return Model1
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Model Patterns

**Pattern 1: UUID Primary Key** (use for all models)
```python
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
```

**Pattern 2: Timestamps** (use for all models)
```python
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

**Pattern 3: Soft Delete** (use for domain models)
```python
deleted_at = models.DateTimeField(null=True, blank=True)

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

objects = SoftDeleteManager()
all_objects = models.Manager()
```

**Pattern 4: Time Semantics** (use for events/facts)
```python
effective_at = models.DateTimeField(default=timezone.now)  # when it happened
recorded_at = models.DateTimeField(auto_now_add=True)      # when logged
```

**Pattern 5: Effective Dating** (use for assignments)
```python
valid_from = models.DateTimeField()
valid_to = models.DateTimeField(null=True, blank=True)
```

**Pattern 6: Custom QuerySet**
```python
class MyQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

class MyModel(models.Model):
    objects = MyQuerySet.as_manager()
```

**Pattern 7: GenericForeignKey** (link to any model)
```python
target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
target_object_id = models.CharField(max_length=255)
target = GenericForeignKey("target_content_type", "target_object_id")
```

**Pattern 8: Value Object** (no database, immutable)
```python
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str
```

### Service Layer

Put business logic in services.py, not models:

```python
from django.db import transaction

def do_operation(entity, **kwargs):
    """Perform operation atomically."""
    with transaction.atomic():
        # validate
        # execute
        # save
        return result
```

---

## PHASE 5: TESTING STRATEGY

### tests/settings.py

Always use this template (PostgreSQL required):

```python
import os

SECRET_KEY = "test-secret-key"
DEBUG = True
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_{name}",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "test_db"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
```

### tests/conftest.py

Always use this template (uses settings.py for PostgreSQL config):

```python
import django
import os
from django.conf import settings

def pytest_configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": os.environ.get("POSTGRES_DB", "test_db"),
                    "USER": os.environ.get("POSTGRES_USER", "postgres"),
                    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
                    "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
                    "PORT": os.environ.get("POSTGRES_PORT", "5432"),
                }
            },
            INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth", "django_{name}"],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
        )
    django.setup()
```

### Test Patterns

Always structure tests like this:

```python
import pytest
from decimal import Decimal

@pytest.mark.django_db
class TestMyModel:
    def test_creation(self):
        """Model can be created with required fields."""
        obj = MyModel.objects.create(name="Test")
        assert obj.pk is not None

    def test_some_behavior(self):
        """Model exhibits expected behavior."""
        # Arrange
        obj = MyModel.objects.create(name="Test")
        # Act
        result = obj.do_something()
        # Assert
        assert result == expected
```

### Edge Cases to Always Test

- Empty/null values
- Boundary conditions (0, -1, max values)
- Uniqueness constraint violations
- Soft delete behavior (excluded from queries)
- Invalid state transitions
- Concurrent access (if applicable)

### Coverage Requirement

All packages must have >95% test coverage. Run:

```bash
pytest --cov=src/django_{name} --cov-report=term-missing
```

---

## PHASE 6: DOCUMENTATION

### README.md Template

Always create README.md with this structure:

```markdown
# django-{name}

{One paragraph description}

## Installation

\`\`\`bash
pip install django-{name}
\`\`\`

Add to INSTALLED_APPS:

\`\`\`python
INSTALLED_APPS = [..., "django_{name}"]
\`\`\`

Run migrations:

\`\`\`bash
python manage.py migrate django_{name}
\`\`\`

## Usage

\`\`\`python
from django_{name}.models import MyModel

obj = MyModel.objects.create(name="Example")
\`\`\`

## Models

| Model | Purpose |
|-------|---------|
| MyModel | Description |

## QuerySet Methods

| Method | Description |
|--------|-------------|
| .active() | Filter to active records |

## License

MIT
```

---

## PHASE 7: GIT WORKFLOW

### Commit Messages

Always use conventional commit format:

```
feat(django-{name}): add initial models and migrations

- Add MyModel with UUID, timestamps
- Add MyQuerySet with active() method
- Add 15 tests (100% coverage)
```

Prefixes:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Tests only
- `refactor`: Code change that doesn't add feature or fix bug

### When to Commit

Commit after:
1. All tests pass
2. Coverage >95%
3. No import errors
4. README updated

### No AI Attribution

NEVER include:
- "Generated with Claude"
- "Co-Authored-By: Claude"
- Any AI/assistant references

This is a security requirement.

---

## CHECKLISTS

### New Package Checklist

Before marking a package complete:

```
□ SPEC.md created with scope boundaries
□ ARCHITECTURE.md created with hard rules
□ File structure matches template exactly
□ pyproject.toml complete
□ apps.py has default_auto_field
□ __init__.py uses lazy imports
□ All models have UUID + timestamps
□ Tests written BEFORE implementation
□ All tests passing
□ Coverage >95%
□ Migrations created (makemigrations)
□ README.md complete with examples
□ Package installs without errors (pip install -e .)
□ No import errors when imported
```

### Pre-Commit Checklist

Before every commit:

```
□ pytest passes
□ No linting errors
□ Coverage >95%
□ README reflects changes
□ Commit message is conventional format
```

### Definition of Done

A package is DONE when:

1. All user stories have passing acceptance tests
2. ARCHITECTURE.md documents all hard rules
3. README.md has installation + usage examples
4. All tests pass with >95% coverage
5. Package installs and imports without errors
6. No TODO comments left in code

---

## QUICK REFERENCE

### Create New Package Command Sequence

```bash
# 1. Create structure
mkdir -p packages/django-{name}/src/django_{name}/migrations
mkdir -p packages/django-{name}/tests
touch packages/django-{name}/src/django_{name}/__init__.py
touch packages/django-{name}/src/django_{name}/migrations/__init__.py
touch packages/django-{name}/tests/__init__.py

# 2. Create files (use templates above)
# pyproject.toml, apps.py, models.py, tests/settings.py, tests/conftest.py

# 3. Install in dev mode
cd packages/django-{name}
pip install -e .

# 4. Run tests
pytest tests/ -v

# 5. Create migrations
DJANGO_SETTINGS_MODULE=tests.settings python -c "import django; django.setup(); from django.core.management import call_command; call_command('makemigrations', 'django_{name}')"

# 6. Run tests again
pytest tests/ -v --cov=src/django_{name}
```

### Common Fixes

**AppRegistryNotReady error:**
→ Use lazy imports in __init__.py

**No module named django_{name}:**
→ Run `pip install -e .` in package directory

**No such table:**
→ Run makemigrations and check migrations/ has files

**Tests not found:**
→ Check DJANGO_SETTINGS_MODULE in pyproject.toml
