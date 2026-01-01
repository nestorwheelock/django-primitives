# Package Extraction Roadmap

**Status:** Planning
**Last Updated:** 2026-01-01

---

## Overview

This roadmap defines the order for extracting reusable Django packages from VetFriendly patterns. Tiers are ordered by dependency: Tier 1 must be stable before Tier 2 begins.

---

## Tier 1: Foundation (Extract First)

These packages have no dependencies on other primitives and form the foundation.

### 1.1 django-basemodels

**Purpose:** BaseModel with UUID PKs, timestamps, soft delete

**Extracts from:**
- SYSTEM_CHARTER.md: "All domain models inherit from BaseModel"
- SYSTEM_CHARTER.md: "Soft Delete & Reversibility"

**Provides:**
```python
from django_basemodels.models import BaseModel

class Pet(BaseModel):
    name = models.CharField(max_length=100)
    # Inherits: id (UUID), created_at, updated_at, deleted_at
    # Inherits: delete(), restore(), hard_delete()
    # Default manager excludes soft-deleted
```

**Why first:** Every other package depends on BaseModel.

**Status:** ✅ Complete (packages/django-basemodels, 30 tests)

---

### 1.2 django-parties

**Purpose:** Party pattern (Person, Organization, Group, Relationships)

**Extracts from:**
- SYSTEM_CHARTER.md: "Party Pattern is foundational"
- SYSTEM_CHARTER.md: "User vs Person"
- S-100: Unified People Architecture

**Provides:**
```python
from django_parties.models import Person, Organization, Group, PartyRelationship

# Relationships handle ownership, employment, guardianship, billing
rel = PartyRelationship.objects.create(
    from_person=person,
    to_organization=organization,
    relationship_type='employee'
)
```

**Depends on:** django-basemodels

**Status:** ✅ Complete (packages/django-parties, 44 tests)

---

### 1.3 django-rbac

**Purpose:** Role-based access control with hierarchy enforcement

**Extracts from:**
- SYSTEM_CHARTER.md: "RBAC Hierarchy"
- S-079: Audit Logging Staff Actions

**Provides:**
```python
from django_rbac.models import Role, UserRole
from django_rbac.mixins import RBACUserMixin
from django_rbac.decorators import require_permission, requires_hierarchy_level
from django_rbac.views import ModulePermissionMixin, HierarchyPermissionMixin

# Add mixin to User model
class User(RBACUserMixin, AbstractUser):
    pass

# User methods
user.hierarchy_level  # 60 (from highest role)
user.can_manage_user(other)  # True if level > other's level
user.get_manageable_roles()  # Roles below user's level
user.has_module_permission('practice', 'view')  # Permission check

@requires_hierarchy_level(60)  # Manager or higher
def approve_leave_request(request):
    ...
```

**Key rule:** Users can only manage users with LOWER hierarchy levels.

**Depends on:** django-basemodels

**Status:** ✅ Complete (packages/django-rbac, 30 tests)

---

### 1.4 django-audit-log

**Purpose:** Append-only audit trail for all model changes

**Extracts from:**
- SYSTEM_CHARTER.md: "Medical records are append-only"
- S-079: Audit Logging Staff Actions
- WORKITEM_SPAWN_AUDIT.md patterns

**Provides:**
```python
from django_audit_log import log, log_event

# Log a model operation
log(action='create', obj=my_instance, actor=request.user, request=request)

# Log with changes
log(action='update', obj=customer, actor=request.user,
    changes={'email': {'old': 'a@b.com', 'new': 'x@y.com'}})

# Log a non-model event
log_event(action='login', actor=user, metadata={'method': 'oauth'})
```

**Key features:**
- UUID primary keys, immutable logs (no updates/deletes)
- Actor tracking with string snapshots
- Before/after change diffs (JSON)
- Request context (IP, user agent, request ID)
- Sensitivity classification (normal/high/critical)

**Depends on:** None (standalone)

**Status:** ✅ Complete (packages/django-audit-log, 23 tests)

---

## Tier 2: Domain Patterns (After Tier 1 Stable)

These packages implement domain-specific patterns and depend on Tier 1.

### 2.1 django-catalog

**Purpose:** Order catalog with basket workflow and work item spawning

**Extracts from:**
- planning/catalog/*.md
- SYSTEM_EXECUTION_RULES.md: "Catalog owns definitions"
- planning/workitems/WORKITEM_SPAWNER_RULES.md

**Provides:**
```python
from django_catalog.models import CatalogItem, Basket, BasketItem, WorkItem
from django_catalog.services import commit_basket, get_or_create_draft_basket

# CatalogItem: Definition layer for orderable items
item = CatalogItem.objects.create(
    kind='service',
    service_category='lab',
    display_name='Blood Test',
)

# Basket workflow: collect items, commit spawns WorkItems
basket = get_or_create_draft_basket(encounter, user)
BasketItem.objects.create(basket=basket, catalog_item=item, added_by=user)
work_items = commit_basket(basket, user)
```

**Key features:**
- CatalogItem: services and stock items with routing rules
- Basket: encounter-scoped container for items before commit
- WorkItem: spawned executable tasks with board routing
- DispenseLog: clinical record of pharmacy dispensing
- Configurable encounter model via settings

**Key rules:**
- Catalog items become actionable only when added to a Basket and committed
- Tasks spawn only on Basket commit (idempotent)
- Routing is deterministic and stored at spawn time

**Depends on:** Configurable encounter model, django-singleton (optional for CatalogSettings)

**Status:** ✅ Complete (packages/django-catalog, 83 tests)

---

### 2.2 django-workitems

**Purpose:** Task spawning and execution tracking

**Note:** This functionality is now included in django-catalog as WorkItem model.

**Status:** ✅ Merged into django-catalog

---

### 2.3 django-encounters

**Purpose:** Domain-agnostic encounter state machine with pluggable validators

**Provides:**
```python
from django_encounters.models import EncounterDefinition, Encounter, EncounterTransition
from django_encounters.services import create_encounter, transition, get_allowed_transitions

# Define a reusable state machine
definition = EncounterDefinition.objects.create(
    key="repair_job",
    states=["pending", "active", "review", "completed"],
    transitions={"pending": ["active"], "active": ["review"], "review": ["completed"]},
    initial_state="pending",
    terminal_states=["completed"],
    validator_paths=["myapp.validators.ChecklistValidator"],
)

# Create encounter attached to ANY subject via GenericFK
encounter = create_encounter("repair_job", subject=my_asset, created_by=user)

# Transition with validation
result = transition(encounter, "active", by_user=user)
```

**Key features:**
- Definition-driven state machines (no hardcoded states)
- GenericFK subject attachment (any model: patient, asset, case, project)
- Graph validation (reachability, no orphan states, terminal state enforcement)
- Pluggable validators for hard blocks and soft warnings
- Transition audit log with metadata

**Depends on:** None (standalone, uses Django's ContentType)

**Note:** Domain-specific encounter workflows (vet clinic pipeline, legal case flow, etc.)
should be built as vertical packages that use django-encounters as a foundation.

**Status:** ✅ Complete (packages/django-encounters, 80 tests)

---

### 2.4 django-worklog

**Purpose:** Server-side work session timing for operational work tracking

**Provides:**
```python
from django_worklog.models import WorkSession
from django_worklog.services import start_session, stop_session, get_active_session

# Start a session (context via GenericFK - any model)
session = start_session(user=user, context=task)

# ... work happens ...

# Stop the active session
stopped = stop_session(user)
print(stopped.duration_seconds)  # Computed on stop

# Switch policy: starting new session auto-stops existing
start_session(user, task_a)
start_session(user, task_b)  # Stops task_a, starts task_b
```

**Key rules:**
- Server-side timestamps only (no client timestamps)
- One active session per user (Switch policy)
- GenericFK for context attachment to any model
- duration_seconds computed on stop, immutable after

**Key features:**
- `start_session(user, context)` - Switch policy (stops old, starts new)
- `stop_session(user)` - Raises NoActiveSession if none active
- `get_active_session(user)` - Returns session or None

**Depends on:** None (standalone)

**Status:** ✅ Complete (packages/django-worklog, 31 tests)

---

## Tier 3: Infrastructure (After Tier 2 Stable)

### 3.1 django-modules

**Purpose:** Module enable/disable per organization

**Extracts from:**
- SYSTEM_CHARTER.md: "Module Configuration"

**Provides:**
```python
from django_modules import is_module_enabled, require_module, list_enabled_modules
from django_modules.models import Module, OrgModuleState

# Define a module
Module.objects.create(key='pharmacy', name='Pharmacy', active=True)

# Per-org override (disable pharmacy for this org)
OrgModuleState.objects.create(org=org, module=module, enabled=False)

# Check if enabled (resolution: org override > global default)
if is_module_enabled(org, 'pharmacy'):
    # pharmacy features available

# Enforce in views/services
require_module(org, 'pharmacy')  # Raises ModuleDisabled if disabled

# List all enabled modules for org
enabled = list_enabled_modules(org)  # {'billing', 'lab', ...}
```

**Key rules:**
- One boolean: enabled/disabled (no variants, no percentage rollout)
- Resolution order: OrgModuleState.enabled > Module.active (global default)
- Swappable org model via MODULES_ORG_MODEL setting

**Depends on:** django-basemodels

**Status:** ✅ Complete (packages/django-modules, 57 tests)

---

### 3.2 django-singleton

**Purpose:** Singleton settings pattern (pk=1 enforcement)

**Provides:**
```python
from django_singleton.models import SingletonModel

class StoreSettings(SingletonModel):
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        app_label = "store"

# Access the singleton
settings = StoreSettings.get_instance()
settings.tax_rate = 7.5
settings.save()
```

**Key features:**
- `pk=1` enforced on every save
- `get_instance()` classmethod with race condition handling
- `delete()` raises `SingletonDeletionError` (no silent no-ops)
- Detects rogue rows and raises `SingletonViolationError`

**Depends on:** None (standalone abstract model)

**Status:** ✅ Complete (packages/django-singleton, 15 tests)

**Consumers:** django-catalog (CatalogSettings singleton for allow_inactive_items behavior)

---

### 3.3 django-layers

**Purpose:** Import boundary enforcement for CI

**Extracts from:**
- ARCHITECTURE_ENFORCEMENT.md

**Provides:**
```bash
# CLI command
django-layers check --config layers.yaml --root /path/to/repo

# Exit 0 if clean, 1 if violations found
```

```yaml
# layers.yaml - defines allowed import directions
layers:
  - name: tier1
    packages: [django-basemodels, django-parties, django-rbac, django-audit-log]
  - name: tier2
    packages: [django-catalog, django-encounters, django-worklog]
  - name: tier3
    packages: [django-singleton, django-modules, django-layers]

rules:
  default: same_or_lower  # Can import same layer or lower

ignore:
  paths: ["**/tests/**", "**/migrations/**"]
```

**Key features:**
- AST-based import scanning (accurate for standard imports)
- Ignores stdlib and third-party imports
- Configurable ignore patterns for tests/migrations
- Supports monorepo layout: `packages/<pkg>/src/<module>/`
- JSON and text output formats

**Depends on:** None (standalone CLI tool, uses PyYAML)

**Status:** ✅ Complete (packages/django-layers, 64 tests)

---

## Extraction Order Summary

```
Phase 1: Foundation
  └── django-basemodels (no deps) ✅
  └── django-parties (needs basemodels) ✅
  └── django-rbac (needs basemodels) ✅
  └── django-audit-log (standalone) ✅

Phase 2: Domain
  └── django-catalog (standalone, configurable encounter) ✅
  └── django-workitems (merged into django-catalog) ✅
  └── django-encounters (standalone, GenericFK) ✅
  └── django-worklog (standalone) ✅

Phase 3: Infrastructure
  └── django-modules (needs basemodels) ✅
  └── django-singleton (no deps) ✅
  └── django-layers (standalone tool) ✅
```

---

## Success Criteria

Each package is "done" when:

1. [x] Standalone repo with pyproject.toml
2. [x] 95%+ test coverage
3. [x] No imports from other primitives (except foundation)
4. [x] README with installation and usage
5. [ ] Published to PyPI (or private index)
6. [ ] VetFriendly migrated to use the package

---

## Current Status

**All 11 packages extracted and tested.** Layer boundaries enforced via `django-layers check`.

| Package | Tests | Status |
|---------|-------|--------|
| django-basemodels | 30 | ✅ Complete |
| django-parties | 44 | ✅ Complete |
| django-rbac | 30 | ✅ Complete |
| django-audit-log | 23 | ✅ Complete |
| django-catalog | 83 | ✅ Complete |
| django-encounters | 80 | ✅ Complete |
| django-worklog | 31 | ✅ Complete |
| django-modules | 57 | ✅ Complete |
| django-singleton | 15 | ✅ Complete |
| django-layers | 64 | ✅ Complete |
| **Total** | **457** | ✅ |

**Remaining:**
- Publish to PyPI (when ready for public release)
- Migrate VetFriendly to use packages

---

## Phase 4: Framework Correctness (Next)

**Goal:** Build the "constitutional law" of the framework - consistent decision surfaces that make every future vertical (pizza, vet, dive ops, rentals) behave the same under stress.

### Architectural Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Decisioning location** | Standalone `django-decisioning` | basemodels stays boringly universal; decisioning is behavior+governance |
| **Money location** | Standalone `django-money` | Not ledger-specific; needed by pricing, billing, refunds, points systems |
| **Retrofit timing** | Contract-first, staged compliance | Lock time contract NOW, apply to new surfaces immediately, backport by risk |
| **Build order** | decisioning → money → agreements → ledger | Each depends on the previous |

### Non-Negotiable Rules

- **Every decision surface must be idempotent** (commit basket, post transition, post settlement)
- **Every irreversible fact must support reversals** (never edits)
- **Every fact has `effective_at` + `recorded_at`** (even if effective_at defaults to recorded_at)
- **Snapshots are required at the boundary** (don't point at mutable state and call it evidence)

### Current Gaps Identified

**Time Semantics:**
- Mixed patterns: DispenseLog allows backdating, WorkSession prevents it
- No `effective_at` vs `recorded_at` distinction
- No `as_of()` query support

**Idempotency:**
- Database-level constraints exist (WorkItem, DispenseLog, UserRole)
- **Gap:** No request-level idempotency key enforcement
- **Gap:** BasketItem creation vulnerable to double-click

**Decision Surface Inconsistency:**
- Each package has implicit "commit / transition / log / switch"
- No explicit contract for authority, finality, reversibility

**Financial Primitives:**
- No money value object, pricing, agreements, or ledger

### 4.1 django-decisioning

**Purpose:** Standardize the Decision Surface Contract across all packages

**Provides:**
```python
from django.conf import settings
from django_decisioning.mixins import TimeSemanticsMixin, EffectiveDatedMixin
from django_decisioning.models import Decision, IdempotencyKey
from django_decisioning.decorators import idempotent
from django_decisioning.querysets import EventAsOfQuerySet, EffectiveDatedQuerySet

# Time semantics for any fact
class MyFact(TimeSemanticsMixin, models.Model):
    # Inherits: effective_at (default=now), recorded_at (auto_now_add)
    pass

# Idempotency with state tracking
@idempotent(scope='basket_commit', key_from=lambda basket, user: str(basket.id))
def commit_basket(basket, user):
    ...

# Separate query helpers for different record types
AuditLog.objects.as_of(timestamp)  # EventAsOfQuerySet
UserRole.objects.as_of(timestamp)  # EffectiveDatedQuerySet
UserRole.objects.current()  # Currently valid records
```

**Key models:**
- `TimeSemanticsMixin` - effective_at (default=timezone.now) + recorded_at (auto_now_add)
- `EffectiveDatedMixin` - valid_from/valid_to
- `EventAsOfQuerySet` - for append-only facts
- `EffectiveDatedQuerySet` - for validity-period records
- `IdempotencyKey` - with state tracking (pending/processing/succeeded/failed)
- `Decision` - uses AUTH_USER_MODEL + Party, CharField for GenericFK IDs

**Depends on:** django-basemodels

**Status:** 🔜 Planned

---

### 4.2 django-money

**Purpose:** Immutable money value object with currency-aware arithmetic

**Design Decision:** No custom MoneyField. Store as separate fields, use descriptor for convenience.

**Provides:**
```python
from django_money import Money
from django_money.exceptions import CurrencyMismatchError

# Immutable, currency-safe arithmetic
price = Money("19.99", "USD")
total = price * 3  # Money("59.97", "USD")

# Currency mismatch prevention
price_usd + price_eur  # Raises CurrencyMismatchError

# Quantize for display/settlement (not during calculations)
display_price = price.quantized()  # Rounds to currency decimals

# Storage pattern: separate fields, property accessor
class Invoice(models.Model):
    amount = models.DecimalField(max_digits=19, decimal_places=4)  # Internal precision
    currency = models.CharField(max_length=3, default='USD')

    @property
    def total(self) -> Money:
        """Return Money object for calculations."""
        return Money(self.amount, self.currency)

    def set_total(self, money: Money):
        """Set from Money object."""
        self.amount = money.amount
        self.currency = money.currency
```

**Key features:**
- Frozen dataclass (immutable)
- No auto-quantization in `__post_init__` (preserve precision during calculations)
- `quantized()` method for display/settlement (banker's rounding)
- Currency-specific decimal precision (USD=2, JPY=0, BTC=8)
- Arithmetic operators (+, -, *, negation)
- `CurrencyMismatchError` for type safety

**Precision policy:**
- **Storage:** `decimal_places=4` for internal precision (discount pro-rating, tax calculations)
- **Display/Settlement:** Quantize to currency decimals at decision surfaces
- **Rule:** Never quantize during intermediate calculations, only at boundaries

**Depends on:** None (standalone)

**Status:** 🔜 Planned

---

### 4.3 django-sequence

**Purpose:** Atomic, per-org sequence generation for human-readable IDs

**Provides:**
```python
from django_sequence import next_sequence

# Generate: "INV-0001", "INV-0002", ...
invoice_number = next_sequence(scope='invoice', org=org)

# Per-org isolation
next_sequence('order', org_a)  # "ORD-0001"
next_sequence('order', org_b)  # "ORD-0001" (separate sequence)
```

**Key features:**
- Atomic increment (safe under concurrency)
- Per-org isolation
- Configurable prefix and padding
- Gap policy (allow gaps vs no gaps)

**Depends on:** None (standalone)

**Status:** 🔜 Planned

---

### 4.4 django-documents

**Purpose:** Immutable document attachment with storage abstraction

**Provides:**
```python
from django_documents.models import Document
from django_documents.services import attach_document

# Attach to any model via GenericFK
doc = attach_document(
    target=invoice,
    file=uploaded_file,
    uploaded_by=user
)
# Stores: checksum, content_type, storage_ref
```

**Key features:**
- GenericFK attachment to any model
- SHA256 checksum verification
- Storage abstraction (local/S3)
- Retention policy fields
- Immutable after creation

**Depends on:** None (standalone)

**Status:** 🔜 Planned

---

### 4.5 django-notes

**Purpose:** Notes and tags attachable to any model

**Provides:**
```python
from django_notes.models import Note, Tag
from django_notes.services import add_note, tag_object

# Add note to any model
note = add_note(target=customer, content="VIP client", author=user)

# Tag any object
tag_object(target=invoice, tags=['urgent', 'review-needed'])

# Query by tag
Invoice.objects.filter(tags__name='urgent')
```

**Key features:**
- GenericFK for universal attachment
- Note visibility levels (internal/external)
- Tag with slug, name, color
- ObjectTag many-to-many via GenericFK

**Depends on:** None (standalone)

**Status:** 🔜 Planned

---

### 4.6 django-agreements

**Purpose:** Universal price/terms/consent snapshot - "we agreed to X at time T"

**Provides:**
```python
from django_agreements.models import Agreement
from django_agreements.services import create_agreement, amend_agreement

# Create agreement between parties
agreement = create_agreement(
    party_a=customer,
    party_b=organization,
    scope_type='service_plan',
    terms={'monthly_fee': 99.00, 'features': ['basic', 'reports']},
    agreed_by=user
)

# Amend (creates new version, original preserved)
amend_agreement(agreement, new_terms={...}, reason="Price increase")
```

**Use cases:**
- Quotes and proposals
- Consent/waivers
- Service plans
- Negotiated discounts
- Terms of service acceptance

**Depends on:** django-decisioning

**Status:** 🔜 Planned

---

### 4.7 django-ledger

**Purpose:** Universal obligation/reversal engine - append-only double-entry

**Design Decision:** Transaction→Entry is FK (not M2M). Entry created with FK reference to Transaction.

**Provides:**
```python
from django_ledger.models import Account, Entry, Transaction
from django_ledger.services import post_entry, reverse_entry, get_balance

# Create transaction first
transaction = Transaction.objects.create(
    description="Invoice payment",
    metadata={'invoice_id': str(invoice.id)}
)

# Post entries referencing the transaction (FK, not M2M)
debit_entry = Entry.objects.create(
    transaction=transaction,  # FK reference
    account=receivables_account,
    amount=Decimal("100.00"),
    entry_type='debit',
    source=invoice
)
credit_entry = Entry.objects.create(
    transaction=transaction,  # Same transaction
    account=cash_account,
    amount=Decimal("100.00"),
    entry_type='credit',
    source=invoice
)

# Post the transaction (validates double-entry, locks entries)
transaction.posted_at = timezone.now()
transaction.save()  # Validates sum(debits) == sum(credits)

# Reverse (creates NEW entry, one direction only)
reversal = reverse_entry(debit_entry, reason="Invoice cancelled")
# reversal.reverses = debit_entry (FK reference)
# Find reversals via: debit_entry.reversal_entries.all()

# Get balance as of any point in time
balance = get_balance(account, as_of=datetime(2024, 12, 31))
```

**Key models:**
```python
class Entry(UUIDModel, TimeSemanticsMixin):
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name='entries')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='entries')
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    entry_type = models.CharField(max_length=10)  # 'debit' or 'credit'

    # Single reversal direction (find reversing entries via related_name)
    reverses = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='reversal_entries'
    )

    # Source (GenericFK with CharField for UUID support)
    source_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT)
    source_id = models.CharField(max_length=255, blank=True)
```

**Key rules:**
- Entries are immutable once transaction is posted
- Reversals are NEW entries with `reverses` FK to original (one direction only)
- Find all reversals via `entry.reversal_entries.all()`
- Double-entry constraint enforced on transaction post: sum(debits) == sum(credits)
- Entry currency must match account currency (enforced on save)
- `effective_at` vs `recorded_at` for backdating support
- GenericFK source uses CharField for UUID support

**Depends on:** django-decisioning, django-money

**Status:** 🔜 Planned

---

### Phase 4 Implementation Order

```
Phase 0: Time Contract
  └── docs/architecture/TIME_SEMANTICS.md ✅
  └── docs/architecture/POSTGRES_GOTCHAS.md ✅

Phase 1: django-decisioning
  └── TimeSemanticsMixin (default=timezone.now), EffectiveDatedMixin
  └── EventAsOfQuerySet (append-only facts), EffectiveDatedQuerySet (validity periods)
  └── IdempotencyKey with state tracking (pending/processing/succeeded/failed)
  └── Decision model (AUTH_USER_MODEL, CharField for GenericFK IDs)
  └── @idempotent decorator

Phase 2: django-money
  └── Money frozen dataclass (no MoneyField - use separate fields + property)
  └── quantized() method, CurrencyMismatchError

Phase 3: django-sequence
  └── Sequence model, next_sequence() service

Phase 4: django-documents
  └── Document model, storage abstraction

Phase 5: django-notes
  └── Note, Tag, ObjectTag models

Phase 6: django-agreements
  └── Agreement, AgreementVersion models
  └── GenericFK parties with CharField IDs

Phase 7: django-ledger
  └── Account, Transaction, Entry models
  └── Entry→Transaction is FK (not M2M)
  └── Single reversal direction (reverses FK, find via related_name)
  └── Currency match enforcement

Phase 8: Retrofit Existing Packages
  └── Add time semantics + idempotency to existing packages
```

### Dependency Graph (Phase 4)

```
                    ┌─────────────────┐
                    │ django-basemodels │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐
│ django-parties  │  │ django-rbac │  │ django-decisioning │ ◄── NEW
└─────────────────┘  └─────────────┘  └────────┬────────┘
                                               │
                         ┌─────────────────────┼─────────────────────┐
                         │                     │                     │
                         ▼                     ▼                     ▼
               ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
               │  django-money   │   │django-agreements│   │  django-ledger  │
               │     (NEW)       │   │     (NEW)       │   │     (NEW)       │
               └─────────────────┘   └─────────────────┘   └─────────────────┘
```

### Torture Tests (Framework-Level)

Every decision surface must pass:

| Test | Description | Packages |
|------|-------------|----------|
| **Retry** | Same request 3x → exactly one effect | All with idempotency |
| **Backdate** | Record today, effective yesterday → coherent | All with effective_at |
| **Reversal** | Undo requires authority + produces new facts | Ledger, Agreements |
| **Delegation** | Actor vs on_behalf_of captured | Decisioning mixin |
| **Snapshot** | Reconstruct decision without mutable state | Catalog, Agreements |

---

## Future Packages (Deferred)

| Package | Purpose | When |
|---------|---------|------|
| **django-settlements** | Payment as decision surface | After ledger is proven |
| **django-inventory** | Stock tracking with movements | When physical goods needed |
| **django-notifications** | Multi-channel delivery | When user-facing alerts needed |
| **django-scheduling** | Availability + booking | When time slots needed |

These are NOT part of this roadmap. Build them when a vertical needs them
