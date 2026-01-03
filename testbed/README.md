# Django Primitives Testbed

A verification harness for the django-primitives monorepo. This project validates that all 18 packages integrate correctly, migrations apply cleanly, and database constraints are properly enforced.

## Purpose

This testbed is **NOT a product**. It exists to:

1. **Prove integration**: Validate that all primitives work together
2. **Verify constraints**: Test that PostgreSQL CHECK/UNIQUE constraints reject invalid data
3. **Provide examples**: Show realistic usage of primitives in combination
4. **Enable CI testing**: Run integration tests against a real PostgreSQL database

## Quick Start

```bash
# 1. Start PostgreSQL
docker compose up -d db

# 2. Install dependencies (from testbed directory)
pip install -r requirements.txt

# 3. Apply migrations
python manage.py migrate

# 4. Seed sample data
python manage.py seed_testbed

# 5. Verify constraints
python manage.py verify_integrity

# 6. Run tests
pytest tests/ -v
```

Or use the Makefile:

```bash
make setup    # Start DB, migrate, and seed
make verify   # Run constraint verification
make test     # Run pytest
```

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 16 (via Docker)

## Installation

### 1. Start PostgreSQL

```bash
docker compose up -d db

# Wait for PostgreSQL to be ready
docker compose exec db pg_isready -U postgres -d primitives_testbed
```

### 2. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install requirements (includes all django-primitives as editable installs)
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit if needed (defaults work with docker-compose)
```

### 4. Apply Migrations

```bash
python manage.py migrate
```

This applies migrations from all 18 django-primitives packages.

## Usage

### Seeding Data

Create realistic sample data across all primitives:

```bash
# Seed all scenarios
python manage.py seed_testbed

# Seed a specific scenario
python manage.py seed_testbed --scenario parties

# List available scenarios
python manage.py seed_testbed --list
```

### Verifying Constraints

Run negative write tests to confirm database constraints are enforced:

```bash
# Verify all constraints
python manage.py verify_integrity

# Verbose output
python manage.py verify_integrity -v

# Verify specific scenario
python manage.py verify_integrity --scenario catalog
```

Example output:

```
============================================================
Django Primitives Testbed - Integrity Verification
============================================================

[PARTIES]
--------------------------------------------------
  PASS address_exactly_one_party (no party)
  PASS address_exactly_one_party (multiple)
  PASS phone_exactly_one_party
  PASS email_exactly_one_party

[RBAC]
--------------------------------------------------
  PASS role_hierarchy_level_range (below 10)
  PASS role_hierarchy_level_range (above 100)
  PASS userrole_valid_to_after_valid_from

...

============================================================
SUMMARY
============================================================

  PASS: 24
  FAIL: 0
  SKIP: 2
  TOTAL: 26

All integrity checks passed!
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=primitives_testbed

# Run specific test class
pytest tests/test_integration.py::TestCatalog -v

# Run concurrency tests
pytest tests/test_concurrency.py -v
```

## Interpreting Results

### What verify_integrity Failures Mean

Each `verify_integrity` check attempts an invalid database operation and expects it to fail:

| Result | Meaning |
|--------|---------|
| **PASS** | Invalid data was correctly rejected by database constraint |
| **FAIL** | Invalid data was accepted - constraint is missing or broken |
| **SKIP** | Test could not run (missing prerequisite data) |

A **FAIL** indicates a regression. The database constraint that should enforce the rule is either:
- Missing from the migration
- Defined incorrectly
- Not applied (run `migrate`)

### How to Interpret IntegrityError

When a constraint rejects data, PostgreSQL raises `IntegrityError`. Common patterns:

```python
# CHECK constraint violation
IntegrityError: new row violates check constraint "entry_amount_positive"
# → The CHECK constraint on Entry.amount rejected a non-positive value

# UNIQUE constraint violation
IntegrityError: duplicate key value violates unique constraint "sequence_unique_per_scope_org"
# → Attempted to insert a duplicate (scope, org_content_type, org_id) tuple

# EXCLUSION constraint violation
IntegrityError: conflicting key value violates exclusion constraint "worksession_one_active_per_user"
# → Tried to create overlapping rows that the exclusion constraint forbids

# Foreign key violation
IntegrityError: insert or update on table "basket" violates foreign key constraint
# → Referenced row doesn't exist in parent table
```

To debug a failing constraint:
1. Check the constraint name in the error message
2. Find the constraint in the model's `Meta.constraints` or migration
3. Verify the constraint condition matches the business rule

### How to Add a New Scenario

1. **Create the scenario module** in `primitives_testbed/scenarios/`:

```python
# primitives_testbed/scenarios/mypackage.py
"""MyPackage scenario: describe what it tests."""

from django.db import IntegrityError, transaction
from django_mypackage.models import MyModel


def seed():
    """Create sample data. Must be idempotent."""
    count = 0

    obj, created = MyModel.objects.get_or_create(
        unique_field="value",
        defaults={"other_field": "data"}
    )
    if created:
        count += 1

    return count


def verify():
    """Run negative write tests. Return list of (name, passed, detail)."""
    results = []

    # Test pattern: wrap in transaction.atomic() to rollback on success
    try:
        with transaction.atomic():
            MyModel.objects.create(
                unique_field="value",  # Duplicate - should fail
            )
        # If we get here, constraint didn't fire
        results.append(("unique_field_constraint", False, "Should have raised IntegrityError"))
    except IntegrityError:
        # Expected behavior
        results.append(("unique_field_constraint", True, "Correctly rejected duplicate"))

    return results
```

2. **Register in `__init__.py`**:

```python
# primitives_testbed/scenarios/__init__.py
from .mypackage import seed as seed_mypackage, verify as verify_mypackage

SCENARIOS = [
    # ... existing scenarios
    ("mypackage", seed_mypackage, verify_mypackage),
]
```

3. **Add integration test** in `tests/test_integration.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestMyPackage:
    def test_unique_field_constraint(self):
        from django_mypackage.models import MyModel

        MyModel.objects.create(unique_field="test")

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                MyModel.objects.create(unique_field="test")  # Duplicate
```

4. **Run to verify**:

```bash
python manage.py seed_testbed --scenario mypackage
python manage.py verify_integrity --scenario mypackage
pytest tests/test_integration.py::TestMyPackage -v
```

### Django Admin

Inspect data through Django admin:

```bash
# Create a superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver

# Visit http://localhost:8000/admin/
```

### Health Check

```bash
curl http://localhost:8000/health/
# {"status": "ok", "database": "ok"}
```

## Project Structure

```
testbed/
├── docker-compose.yml       # PostgreSQL container
├── manage.py               # Django management
├── requirements.txt        # Python dependencies
├── Makefile               # Common commands
├── .env.example           # Environment template
├── primitives_testbed/
│   ├── settings.py        # Django settings
│   ├── urls.py            # URL configuration
│   ├── views.py           # Index and health check
│   ├── models.py          # Custom User model
│   ├── admin.py           # Admin configuration
│   ├── management/
│   │   └── commands/
│   │       ├── seed_testbed.py      # Seed command
│   │       └── verify_integrity.py  # Verify command
│   └── scenarios/         # Scenario modules
│       ├── __init__.py
│       ├── parties.py
│       ├── rbac.py
│       ├── catalog.py
│       ├── geo.py
│       ├── encounters.py
│       ├── documents.py
│       ├── notes.py
│       ├── sequence.py
│       ├── ledger.py
│       ├── worklog.py
│       └── agreements.py
├── templates/
│   └── index.html         # Dashboard template
└── tests/
    ├── conftest.py        # Pytest fixtures
    └── test_integration.py # Integration tests
```

## Scenarios

Each scenario module provides:

- `seed()`: Create sample data (idempotent)
- `verify()`: Run negative write tests

| Scenario | Primitives | Constraints Tested |
|----------|------------|-------------------|
| parties | django-parties | address/phone/email XOR, relationship XOR |
| rbac | django-rbac | hierarchy_level range, valid_to after valid_from |
| catalog | django-catalog | quantity positive, priority range, unique basket |
| geo | django-geo | latitude/longitude range, positive radius |
| encounters | django-encounters | transition validation, immutability |
| documents | django-documents | checksum immutability |
| notes | django-notes | unique tag slug, unique object tag |
| sequence | django-sequence | unique scope per org, atomic increment |
| ledger | django-ledger | entry amount positive, balance calculation |
| worklog | django-worklog | unique active session, duration consistency |
| agreements | django-agreements | unique version, valid_to after valid_from |

## Adding a New Primitive Scenario

1. Create `primitives_testbed/scenarios/newprimitive.py`:

```python
"""New primitive scenario."""

from django.db import IntegrityError, transaction
from django_newprimitive.models import SomeModel


def seed():
    """Create sample data."""
    count = 0

    obj, created = SomeModel.objects.get_or_create(
        name="Sample",
        defaults={"field": "value"}
    )
    if created:
        count += 1

    return count


def verify():
    """Verify constraints."""
    results = []

    try:
        with transaction.atomic():
            SomeModel.objects.create(invalid_field=-1)
        results.append(("constraint_name", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("constraint_name", True, "Correctly rejected"))

    return results
```

2. Register in `primitives_testbed/scenarios/__init__.py`:

```python
from .newprimitive import seed as seed_newprimitive, verify as verify_newprimitive

SCENARIOS = [
    # ... existing scenarios
    ("newprimitive", seed_newprimitive, verify_newprimitive),
]
```

3. Add admin registration in `primitives_testbed/admin.py`

4. Add integration tests in `tests/test_integration.py`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| SECRET_KEY | test-key | Django secret key |
| DEBUG | True | Debug mode |
| POSTGRES_DB | primitives_testbed | Database name |
| POSTGRES_USER | postgres | Database user |
| POSTGRES_PASSWORD | postgres | Database password |
| POSTGRES_HOST | localhost | Database host |
| POSTGRES_PORT | 5432 | Database port |

## Makefile Commands

```bash
make help      # Show available commands
make db-up     # Start PostgreSQL
make db-down   # Stop PostgreSQL
make migrate   # Apply migrations
make seed      # Seed sample data
make verify    # Run integrity verification
make test      # Run pytest
make shell     # Django shell
make run       # Development server
make clean     # Remove database volume
make setup     # Full setup (db-up, migrate, seed)
```

## License

MIT
