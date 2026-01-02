# django-agreements

Temporal agreement primitives for Django. Track contracts, consents, and legal relationships between parties with full version history.

## Design Principles

This package is **infrastructure**, not a workflow engine.

- **Append-only**: Agreements are historical facts. Amendments create versions, they don't overwrite.
- **Temporal**: Every agreement has a validity period. Query with `.current()` or `.as_of(date)`.
- **Auditable**: Complete version history preserved in AgreementVersion.

### What This Is NOT

- Not an approval workflow (no draft/pending/approved states)
- Not a document generator (no PDF output)
- Not a notification system (no "agreement expiring" alerts)
- Not a signature tool (no e-signature capture)

If you need those, build them on top of this primitive. This package is intentionally opinionated.

## Installation

```bash
pip install django-agreements
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django.contrib.contenttypes',
    'django_agreements',
]
```

Run migrations:

```bash
python manage.py migrate django_agreements
```

## Usage

### Creating Agreements

Always use the service layer:

```python
from django_agreements.services import create_agreement

agreement = create_agreement(
    party_a=customer,
    party_b=vendor,
    scope_type='service_contract',
    terms={'duration': '12 months', 'value': 10000},
    agreed_by=request.user,
    valid_from=timezone.now(),  # REQUIRED - be explicit
)
```

### Amending Agreements

```python
from django_agreements.services import amend_agreement

updated = amend_agreement(
    agreement=agreement,
    new_terms={'duration': '24 months', 'value': 18000},
    reason="Extended contract with discount",
    amended_by=request.user,
)
# agreement.current_version is now 2
# A new AgreementVersion record exists
```

### Terminating Agreements

```python
from django_agreements.services import terminate_agreement

terminated = terminate_agreement(
    agreement=agreement,
    terminated_by=request.user,
    reason="Contract cancelled by mutual consent",
)
# agreement.valid_to is now set
# Termination recorded as a version
```

### Querying Agreements

```python
from django_agreements.models import Agreement

# Get current agreements for a party
current = Agreement.objects.for_party(customer).current()

# Get agreements as of a specific date
historical = Agreement.objects.for_party(customer).as_of(some_date)

# Get terms as they were recorded at a point in time
from django_agreements.services import get_terms_as_of
old_terms = get_terms_as_of(agreement, last_month)
```

## Models

| Model | Purpose |
|-------|---------|
| Agreement | Contract between two parties with effective dating |
| AgreementVersion | Immutable amendment history (append-only ledger) |

## Service Functions

| Function | Purpose |
|----------|---------|
| `create_agreement()` | Create agreement with initial version |
| `amend_agreement()` | Amend terms, increment version |
| `terminate_agreement()` | End agreement by setting valid_to |
| `get_terms_as_of()` | Get terms recorded by a timestamp |

## QuerySet Methods

| Method | Description |
|--------|-------------|
| `.for_party(obj)` | Agreements where obj is either party |
| `.current()` | Agreements valid right now |
| `.as_of(timestamp)` | Agreements valid at a specific time |

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for:
- Design decisions
- Invariants
- Concurrency handling
- Projection vs ledger pattern

## License

MIT
