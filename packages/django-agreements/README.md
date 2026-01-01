# django-agreements

Agreement and contract primitives for Django applications.

## Features

- **Agreement Model**: Track agreements between parties with GenericFK
- **Version History**: Immutable amendment history via AgreementVersion
- **Effective Dating**: Valid from/to date range support
- **Terms Storage**: JSON-based terms storage for flexibility

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

```python
from django_agreements.services import create_agreement

agreement = create_agreement(
    party_a=customer,
    party_b=vendor,
    scope_type='service_contract',
    terms={'duration': '12 months', 'value': 10000},
    agreed_by=request.user,
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
```

### Querying Agreements

```python
from django_agreements.models import Agreement

# Get current agreements for a party
current = Agreement.objects.for_party(customer).current()

# Get agreements as of a specific date
historical = Agreement.objects.for_party(customer).as_of(some_date)
```

## License

MIT
