# Prompt: Rebuild django-agreements

## Instruction

Create a Django package called `django-agreements` that provides agreement and contract primitives with version history and effective dating.

## Package Purpose

Track agreements between parties with:
- Two parties via GenericForeignKey (supports any model)
- Flexible JSON terms storage
- Effective dating (valid_from, valid_to)
- Append-only version history for amendments
- QuerySet methods for temporal queries

## Dependencies

- Django >= 4.2
- django.contrib.contenttypes
- django.contrib.auth

## File Structure

```
packages/django-agreements/
├── pyproject.toml
├── README.md
├── src/django_agreements/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── models.py
    └── test_agreement.py
```

## Models Specification

### Agreement Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone

class AgreementQuerySet(models.QuerySet):
    def for_party(self, party):
        """Find agreements where party is either party_a or party_b."""
        content_type = ContentType.objects.get_for_model(party)
        party_id = str(party.pk)
        return self.filter(
            models.Q(party_a_content_type=content_type, party_a_id=party_id) |
            models.Q(party_b_content_type=content_type, party_b_id=party_id)
        )

    def current(self):
        """Get currently valid agreements."""
        return self.as_of(timezone.now())

    def as_of(self, timestamp):
        """Get agreements valid at a specific timestamp."""
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=timestamp)
        )


class Agreement(models.Model):
    # Party A (via GenericFK)
    party_a_content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name='+'
    )
    party_a_id = models.CharField(max_length=255)
    party_a = GenericForeignKey('party_a_content_type', 'party_a_id')

    # Party B (via GenericFK)
    party_b_content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name='+'
    )
    party_b_id = models.CharField(max_length=255)
    party_b = GenericForeignKey('party_b_content_type', 'party_b_id')

    # Scope
    scope_type = models.CharField(max_length=50)  # e.g., 'order', 'subscription', 'consent'
    scope_ref_content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT,
        null=True, blank=True, related_name='+'
    )
    scope_ref_id = models.CharField(max_length=255, blank=True, default='')
    scope_ref = GenericForeignKey('scope_ref_content_type', 'scope_ref_id')

    # Terms
    terms = models.JSONField()

    # Validity
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)  # null = indefinite

    # Decision surface
    agreed_at = models.DateTimeField()
    agreed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='agreements_made'
    )

    # Version
    version = models.PositiveIntegerField(default=1)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AgreementQuerySet.as_manager()

    class Meta:
        app_label = 'django_agreements'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['party_a_content_type', 'party_a_id']),
            models.Index(fields=['party_b_content_type', 'party_b_id']),
            models.Index(fields=['scope_type']),
            models.Index(fields=['valid_from', 'valid_to']),
        ]

    def save(self, *args, **kwargs):
        # Ensure IDs are strings
        self.party_a_id = str(self.party_a_id)
        self.party_b_id = str(self.party_b_id)
        if self.scope_ref_id:
            self.scope_ref_id = str(self.scope_ref_id)

        # Default valid_from to agreed_at
        if not self.valid_from:
            self.valid_from = self.agreed_at or timezone.now()

        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        """Check if agreement is currently valid."""
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_to and now >= self.valid_to:
            return False
        return True

    def __str__(self):
        return f"Agreement ({self.scope_type}) - v{self.version}"
```

### AgreementVersion Model

```python
class AgreementVersion(models.Model):
    """Append-only version history for agreement amendments."""
    agreement = models.ForeignKey(
        Agreement, on_delete=models.CASCADE, related_name='versions'
    )
    version = models.PositiveIntegerField()
    terms = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    reason = models.TextField()

    class Meta:
        app_label = 'django_agreements'
        unique_together = ['agreement', 'version']
        ordering = ['-version']

    def __str__(self):
        return f"Agreement {self.agreement.pk} - v{self.version}"
```

## Test Models

### tests/models.py

```python
from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

class Customer(models.Model):
    name = models.CharField(max_length=100)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)

    class Meta:
        app_label = 'tests'

class ServiceContract(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'
```

## Test Cases (31 tests)

### TestAgreementModel (14 tests)
1. `test_agreement_has_party_a_generic_fk` - GenericFK works
2. `test_agreement_has_party_b_generic_fk` - GenericFK works
3. `test_agreement_party_ids_are_charfield` - UUID support
4. `test_agreement_has_scope_type` - Scope type stored
5. `test_agreement_has_optional_scope_ref` - Optional scope ref works
6. `test_agreement_scope_ref_is_nullable` - Can be None
7. `test_agreement_has_terms_json_field` - JSONField works
8. `test_agreement_has_valid_from` - Valid from stored
9. `test_agreement_valid_from_defaults_to_agreed_at` - Default behavior
10. `test_agreement_has_valid_to_nullable` - Can be indefinite
11. `test_agreement_has_agreed_at` - Decision timestamp
12. `test_agreement_has_agreed_by` - Decision maker FK
13. `test_agreement_has_version_field` - Version number
14. `test_agreement_has_timestamps` - created_at, updated_at

### TestAgreementProperties (4 tests)
1. `test_is_active_returns_true_when_valid` - True for current
2. `test_is_active_returns_false_when_expired` - False for expired
3. `test_is_active_returns_false_when_not_yet_valid` - False for future
4. `test_is_active_returns_true_when_no_end_date` - True for perpetual

### TestAgreementQuerySet (5 tests)
1. `test_for_party_returns_agreements_as_party_a` - Finds as party_a
2. `test_for_party_returns_agreements_as_party_b` - Finds as party_b
3. `test_for_party_returns_both_directions` - Bidirectional
4. `test_current_returns_active_agreements` - Currently valid
5. `test_as_of_returns_agreements_valid_at_date` - Historical query

### TestAgreementVersionModel (8 tests)
1. `test_version_has_agreement_fk` - FK to Agreement
2. `test_version_has_version_number` - Version stored
3. `test_version_has_terms_snapshot` - Terms snapshot
4. `test_version_has_created_by` - User tracking
5. `test_version_has_reason` - Amendment reason
6. `test_version_has_created_at` - Timestamp
7. `test_version_unique_constraint` - No duplicate versions
8. `test_versions_ordered_by_version_desc` - Ordering

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = ['Agreement', 'AgreementVersion']

def __getattr__(name):
    if name == 'Agreement':
        from .models import Agreement
        return Agreement
    if name == 'AgreementVersion':
        from .models import AgreementVersion
        return AgreementVersion
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Dual Party GenericFK**: Agreements between any models
2. **Effective Dating**: valid_from/valid_to for temporal validity
3. **Append-Only Versions**: Immutable amendment history
4. **Decision Surface**: agreed_at/agreed_by for accountability
5. **Bidirectional Queries**: for_party finds agreements in either direction

## Usage Examples

```python
# Create service contract agreement
from django_agreements.models import Agreement, AgreementVersion

agreement = Agreement.objects.create(
    party_a=vendor_org,
    party_b=customer_org,
    scope_type='service_contract',
    scope_ref=contract_object,
    terms={'duration': '12 months', 'value': 50000},
    valid_from=timezone.now(),
    valid_to=timezone.now() + timedelta(days=365),
    agreed_at=timezone.now(),
    agreed_by=request.user,
)

# Record version
AgreementVersion.objects.create(
    agreement=agreement,
    version=1,
    terms=agreement.terms,
    created_by=request.user,
    reason='Initial agreement'
)

# Query current agreements
current = Agreement.objects.current()

# Query agreements for a party
org_agreements = Agreement.objects.for_party(vendor_org)

# Historical query
at_date = Agreement.objects.as_of(historical_date)
```

## Acceptance Criteria

- [ ] Agreement model with dual GenericFK parties
- [ ] AgreementVersion model for append-only history
- [ ] is_active property with valid_from/valid_to logic
- [ ] QuerySet methods: for_party, current, as_of
- [ ] All 31 tests passing
- [ ] README with usage examples
