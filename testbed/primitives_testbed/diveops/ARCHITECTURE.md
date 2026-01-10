# DiveOps Architecture

## Overview

DiveOps is the dive operations domain module for the testbed. It provides booking, check-in, and trip management for a dive shop operation.

## Design Intent

- **Domain-focused**: Models dive shop operations (divers, trips, bookings, certifications)
- **Primitive-backed**: Uses django-primitives for cross-cutting concerns
- **Audit-first**: All mutations emit audit events for compliance

## Hard Rules

1. **All mutations MUST emit audit events** - no exceptions
2. **Audit events are emitted via the adapter** - never import django_audit_log directly
3. **Action strings are stable contracts** - never rename existing actions
4. **Actor is always Django User** - not Party, to keep audit log dependency-free

## Audit Logging

### Architecture

DiveOps follows a centralized audit adapter pattern:

```
Domain Code → diveops/audit.py → django_audit_log
```

The adapter (`diveops/audit.py`) is the ONLY module that imports django_audit_log.
All domain code must use the adapter functions.

### Action Taxonomy (Stable Contract)

These action strings are public contract - DO NOT RENAME existing actions.

| Domain | Actions |
|--------|---------|
| Diver | `diver_created`, `diver_updated`, `diver_deleted`, `diver_activated`, `diver_deactivated` |
| Certification | `certification_added`, `certification_updated`, `certification_removed`, `certification_verified`, `certification_unverified`, `certification_proof_uploaded`, `certification_proof_removed` |
| Trip | `trip_created`, `trip_updated`, `trip_deleted`, `trip_published`, `trip_cancelled`, `trip_rescheduled`, `trip_started`, `trip_completed` |
| Booking | `booking_created`, `booking_cancelled`, `booking_paid`, `booking_refunded` |
| Roster | `diver_checked_in`, `diver_no_show`, `diver_completed_trip`, `diver_removed_from_trip` |
| Eligibility | `eligibility_checked`, `eligibility_failed`, `eligibility_overridden` |
| Trip Req | `trip_requirement_added`, `trip_requirement_updated`, `trip_requirement_removed` |

### Audit Adapter API

```python
from diveops.audit import Actions, log_event, log_booking_event, log_trip_event

# Generic logging
log_event(
    action=Actions.BOOKING_CREATED,
    target=booking,
    actor=request.user,
    data={"trip_id": str(trip.pk)},
)

# Domain-specific (recommended)
log_booking_event(
    action=Actions.BOOKING_CREATED,
    booking=booking,
    actor=request.user,
)
```

### Specialized Logging Functions

| Function | Use For |
|----------|---------|
| `log_event()` | Generic events |
| `log_diver_event()` | Diver profile operations |
| `log_certification_event()` | Certification CRUD |
| `log_trip_event()` | Trip state transitions |
| `log_booking_event()` | Booking lifecycle |
| `log_roster_event()` | Check-in and roster events |
| `log_eligibility_event()` | Eligibility checks/overrides |
| `log_trip_requirement_event()` | Trip requirement changes |

### Audit Selectors (Read-Only)

```python
from diveops.selectors import diver_audit_feed, trip_audit_feed

# Get all audit events for a diver
events = diver_audit_feed(diver, limit=100)

# Get all audit events for a trip
events = trip_audit_feed(trip, limit=100)
```

### Deletion Semantics

- **Soft delete**: Audit event emitted AFTER deletion (deleted_at set)
- **Hard delete**: Audit event emitted BEFORE deletion (capture data first)

### Invariants

1. Every service function mutation MUST have a corresponding audit event
2. Audit events are emitted AFTER successful DB transaction
3. All audit metadata includes entity IDs as strings
4. Certification audit includes diver_id for traceability
5. Booking/roster audit includes trip_id and diver_id

## Modules Structure

```
diveops/
├── models.py         # Domain models (DiverProfile, DiveTrip, etc.)
├── services.py       # Business logic with audit logging
├── selectors.py      # Read-only queries (including audit selectors)
├── audit.py          # Centralized audit adapter (ONLY import point)
├── accounts.py       # Centralized account management for ledger operations
├── decisioning.py    # Eligibility rules via django_decisioning
├── forms.py          # Staff portal forms
├── staff_views.py    # Staff portal views
└── templates/        # Staff portal templates
```

## Dependencies

DiveOps depends on these primitives:

| Primitive | Purpose |
|-----------|---------|
| django_parties | Person/Organization for divers and shops |
| django_audit_log | Audit event persistence |
| django_decisioning | Eligibility rule evaluation |
| django_documents | Certification proof documents |
| django_encounters | Trip encounter tracking |
| django_catalog | Trip catalog items for billing |
| django_ledger | Invoice/billing integration |
| django_geo | Dive site location data |

## Relationship Consolidation (ADR-001)

### Overview

DiveOps consolidates relationship models to use `django-parties.PartyRelationship` as the canonical source, with a domain extension for dive-specific metadata.

See: `docs/ADR-001-RELATIONSHIP-CONSOLIDATION.md`

### Architecture

```
django-parties (owns identity relationships)
┌─────────────────────────────────────────┐
│ PartyRelationship                       │
│ - from_person / from_organization       │
│ - to_person / to_organization / to_group│
│ - relationship_type                     │
│ - is_primary, is_active                 │
└─────────────────────────────────────────┘
              │
              │ OneToOne (optional)
              ▼
┌─────────────────────────────────────────┐
│ DiverRelationshipMeta (DiveOps)         │
│ - party_relationship (FK)               │
│ - priority (emergency contact ordering) │
│ - is_preferred_buddy                    │
│ - notes (dive-specific)                 │
└─────────────────────────────────────────┘
```

### Relationship Types

New types added to `PartyRelationship.RELATIONSHIP_TYPES`:

| Type | Description |
|------|-------------|
| `friend` | Personal friend |
| `relative` | Family member (generic) |
| `buddy` | Activity partner / dive buddy |
| `travel_companion` | Travel together |
| `instructor` | Instructor/trainer |
| `student` | Student/trainee |

### DiverRelationshipMeta Extension

| Field | Purpose |
|-------|---------|
| `priority` | Emergency contact ordering (1=primary, 2=secondary) |
| `is_preferred_buddy` | Prefer to pair these divers on excursions |
| `notes` | Dive-specific notes about the relationship |

### Legacy Models (Deprecated)

The following models are deprecated but preserved for backward compatibility:

| Model | Replacement |
|-------|-------------|
| `EmergencyContact` | `PartyRelationship(type=emergency_contact)` + `DiverRelationshipMeta` |
| `DiverRelationship` | `PartyRelationship(type=buddy/spouse/friend)` + `DiverRelationshipMeta` |

Data has been migrated to the new structure. Legacy models will be removed in a future release.

### Querying Relationships

```python
from django_parties.models import PartyRelationship

# Get emergency contacts for a diver
emergency_contacts = PartyRelationship.objects.filter(
    from_person=diver.person,
    relationship_type='emergency_contact',
    is_active=True,
    deleted_at__isnull=True,
).select_related('to_person', 'diver_meta').order_by('diver_meta__priority')

# Get dive buddies
buddies = PartyRelationship.objects.filter(
    from_person=diver.person,
    relationship_type='buddy',
    deleted_at__isnull=True,
).select_related('to_person', 'diver_meta')
```

## Account Management

### Architecture

DiveOps uses a centralized account management pattern for all ledger operations:

```
Services → diveops/accounts.py → django_ledger
```

The `accounts.py` module is the central point for:
- Defining standard account types
- Creating and seeding accounts for shops
- Retrieving required accounts for financial operations
- Per-vendor payable account management

### Hard Rules

1. **Accounts are owned by shops** - never by vendors or other parties
2. **Missing accounts raise errors** - no silent fallbacks or defaults
3. **Seeding is idempotent** - can be run multiple times safely
4. **Per-vendor AP accounts are named for the vendor** - but owned by the shop

### Standard Account Types

| Key | Type | Purpose |
|-----|------|---------|
| `dive_revenue` | revenue | Income from dive trips |
| `equipment_rental_revenue` | revenue | Income from equipment rentals |
| `excursion_costs` | expense | Costs for excursions/trips |
| `gas_costs` | expense | Air/Nitrox fill costs |
| `equipment_costs` | expense | Equipment expenses |
| `cash_bank` | asset | Cash and bank accounts |
| `accounts_receivable` | receivable | Customer balances owed |
| `accounts_payable` | payable | General vendor payables |

### Required Accounts

These accounts MUST be seeded before financial operations:

- `excursion_costs` - for recording vendor invoices
- `cash_bank` - for recording vendor payments
- `accounts_payable` - general payables account
- `dive_revenue` - for booking revenue
- `accounts_receivable` - for customer billing

### Account Seeding

Accounts can be seeded via:

1. **Management command**:
```bash
python manage.py seed_chart_of_accounts --org "Dive Shop Name" --currency MXN
```

2. **Staff portal**: `/staff/accounts/seed/`

3. **Programmatically**:
```python
from diveops.accounts import seed_accounts
account_set = seed_accounts(shop, currency="MXN", vendors=[vendor1, vendor2])
```

### AccountConfigurationError

When required accounts are missing, operations raise `AccountConfigurationError`:

```python
from diveops.accounts import AccountConfigurationError, get_required_accounts

try:
    accounts = get_required_accounts(shop, "MXN")
except AccountConfigurationError as e:
    # e.shop - the shop missing accounts
    # e.currency - the currency
    # e.missing_types - list of missing account keys
    print(f"Missing accounts: {e.missing_types}")
    print(f"Run: python manage.py seed_chart_of_accounts --org '{shop.name}'")
```

### Per-Vendor Payable Accounts

Each vendor gets a dedicated payable account for reconciliation:

```python
from diveops.accounts import get_vendor_payable_account

# Get or create vendor-specific AP account (owned by shop)
payable_account = get_vendor_payable_account(
    shop=dive_shop,
    vendor=vendor_org,
    currency="MXN",
    auto_create=True,
)
# Account name: "AP - {vendor.name} ({currency})"
# Account owner: shop (not vendor)
```

### Accounts API

```python
from diveops.accounts import (
    get_required_accounts,     # Get AccountSet or raise error
    get_vendor_payable_account, # Get per-vendor AP account
    seed_accounts,              # Create all standard accounts
    get_account,                # Get single account by key
    list_accounts,              # List all accounts for shop
    clear_account_cache,        # Clear cached accounts (for testing)
)

# Get all required accounts (raises if not seeded)
accounts = get_required_accounts(shop, "MXN")
revenue_account = accounts.dive_revenue
expense_account = accounts.excursion_costs

# Get with auto-create (seeds missing accounts)
accounts = get_required_accounts(shop, "MXN", auto_create=True)

# List all accounts for a shop
shop_accounts = list_accounts(shop, currency="MXN")
```

### AccountSet Dataclass

The `AccountSet` dataclass provides typed access to accounts:

```python
@dataclass
class AccountSet:
    shop: Organization
    currency: str
    dive_revenue: Account | None
    equipment_rental_revenue: Account | None
    excursion_costs: Account | None
    gas_costs: Account | None
    equipment_costs: Account | None
    cash_bank: Account | None
    accounts_receivable: Account | None
    accounts_payable: Account | None

    def get_missing_required(self) -> list[str]
    def is_complete(self) -> bool
```

### Audit Actions

Account operations emit these audit events:

| Action | When |
|--------|------|
| `account_created` | New account created |
| `account_updated` | Account details modified |
| `account_deleted` | Account removed |
| `accounts_seeded` | Chart of accounts seeded for shop |

### Integration with Services

Services use the centralized accounts module:

```python
# In services.py
from .accounts import get_required_accounts, get_vendor_payable_account

def record_vendor_invoice(*, actor, shop, vendor, amount, currency, ...):
    # Get required accounts (raises if not seeded)
    accounts = get_required_accounts(shop, currency)

    # Get vendor-specific payable account (auto-creates)
    payable_account = get_vendor_payable_account(
        shop, vendor, currency, auto_create=True
    )

    # Use accounts for ledger entries
    expense_account = accounts.excursion_costs
    # ... create transaction
```

### Invariants

1. All financial operations require accounts to be seeded first
2. Account names follow template: `"{type} - {shop.name} ({currency})"`
3. Vendor AP accounts follow: `"AP - {vendor.name} ({currency})"`
4. Account cache is cleared on seed operations
5. Seeding is safe to run multiple times (idempotent)

## Protected Area Permits

### Overview

DiveOps manages permits for diving in protected areas. The permit system uses a unified model (`ProtectedAreaPermit`) that supports multiple permit types through type discrimination.

### Architecture

```
ProtectedAreaPermit (base)
├── permit_type="guide" → DiverProfile holder + GuidePermitDetails (1:1 extension)
└── permit_type="vessel" → vessel_name holder + Organization operator
```

### Permit Types

| Type | Holder | Purpose |
|------|--------|---------|
| `guide` | DiverProfile | Authorizes a guide to lead dives in the protected area |
| `vessel` | vessel_name (string) | Authorizes a vessel to operate in the protected area |

### Hard Rules

1. **permit_type is immutable** - Cannot change after creation
2. **Holder fields are mutually exclusive** - GUIDE permits must have diver, no vessel_name; VESSEL permits must have vessel_name, no diver
3. **DB constraints enforce invariants** - CheckConstraints validate holder/type alignment
4. **One guide permit per diver per area** - UniqueConstraint on (protected_area, diver) for GUIDE permits
5. **permit_number unique per area and type** - UniqueConstraint on (protected_area, permit_type, permit_number)

### Database Constraints

| Constraint | Description |
|------------|-------------|
| `diveops_unique_permit_number_per_area_type` | Unique permit_number within area and type (soft-delete aware) |
| `diveops_unique_guide_permit_per_diver_area` | One guide permit per diver per area (soft-delete aware) |
| `diveops_guide_permit_requires_diver` | GUIDE permits must have diver_id |
| `diveops_guide_permit_no_vessel` | GUIDE permits must not have vessel_name |
| `diveops_vessel_permit_requires_vessel` | VESSEL permits must have vessel_name |
| `diveops_vessel_permit_no_diver` | VESSEL permits must not have diver_id |
| `diveops_permit_expires_after_issued` | expires_at >= issued_at (when set) |

### GuidePermitDetails Extension

Guide permits can have additional details stored in a 1:1 `GuidePermitDetails` model:

| Field | Purpose |
|-------|---------|
| `carta_eval_agreement` | Link to signed carta evaluación document |
| `carta_eval_signed_by` | Person who signed (can be boat owner) |
| `carta_eval_signed_at` | Date signed |
| `is_owner` | True if guide is also boat owner |
| `last_refresher_at` | Date of last park refresher course |
| `next_refresher_due_at` | When next refresher is due |
| `suspended_at` | Suspension timestamp (if suspended) |
| `suspension_reason` | Reason for suspension |

### Models

```python
# Unified permit model
class ProtectedAreaPermit(BaseModel):
    protected_area = FK(ProtectedArea)
    permit_type = CharField(choices=PermitType)
    permit_number = CharField(max_length=50)
    issued_at = DateField()
    expires_at = DateField(null=True, blank=True)
    is_active = BooleanField(default=True)
    authorized_zones = M2M(ProtectedAreaZone, blank=True)

    # Holder fields (constrained by permit_type)
    diver = FK(DiverProfile, null=True, blank=True)  # GUIDE only
    vessel_name = CharField(blank=True)               # VESSEL only
    vessel_registration = CharField(blank=True)       # VESSEL only
    organization = FK(Organization, null=True)        # VESSEL only (operator)
    max_divers = PositiveIntegerField(null=True)      # VESSEL only

# Extension for guide-specific details
class GuidePermitDetails(BaseModel):
    permit = OneToOneField(ProtectedAreaPermit, related_name="guide_details")
    # ... guide-specific fields
```

### Forms

| Form | Purpose |
|------|---------|
| `GuidePermitForm` | Create/edit GUIDE permits - sets permit_type automatically |
| `VesselPermitFormNew` | Create/edit VESSEL permits - sets permit_type automatically |

### Staff UI

The protected area detail page shows a unified "Permits" section with sub-sections for:
- Guide Permits (with diver link, authorized zones)
- Vessel Permits (with vessel name, operator)

Both types share:
- Add button routes to type-specific create view
- Edit routes to type-specific update view
- Delete uses shared PermitDeleteView

### URL Patterns

```
# Unified Permits (area-scoped)
/protected-areas/<area_pk>/permits/guide/add/        # GuidePermitCreateView
/protected-areas/<area_pk>/permits/guide/<pk>/edit/  # GuidePermitUpdateView
/protected-areas/<area_pk>/permits/vessel/add/       # VesselPermitCreateViewNew
/protected-areas/<area_pk>/permits/vessel/<pk>/edit/ # VesselPermitUpdateViewNew
/protected-areas/<area_pk>/permits/<pk>/delete/      # PermitDeleteView (any type)
```

### Diver Profile Integration

The diver detail page shows all GUIDE permits for that diver across all protected areas. Permits are read-only from the diver page; edits route back to the protected area context.

### Migration Strategy

The unified permit model replaces the previous separate models:
- `ProtectedAreaGuideCredential` → `ProtectedAreaPermit` (type=guide) + `GuidePermitDetails`
- `VesselPermit` → `ProtectedAreaPermit` (type=vessel)

Migration:
1. `0033_unified_permits.py` - Create schema
2. `0034_migrate_permits_data.py` - Copy data from old models

Legacy views and URLs are kept for backward compatibility during transition.

## Agreements (Electronic Signatures)

### Overview

DiveOps provides a legally-compliant electronic signature system for waivers and agreements. The system uses a workflow model (`SignableAgreement`) layered on top of the immutable `django-agreements` primitive.

### Architecture

```
AgreementTemplate (reusable content)
        ↓ send_agreement()
SignableAgreement (workflow: draft → sent → signed → void)
        ↓ sign_agreement()
django_agreements.Agreement (immutable ledger record)
```

### Design Intent

- **Legally defensible**: ESIGN/UETA compliant with full audit trail
- **Database-enforced invariants**: PostgreSQL constraints prevent invalid states
- **Token-based public signing**: Customers sign via secure link without login
- **PDF generation**: Signed agreements generate archival PDFs with digital proof

### Hard Rules

1. **Signed agreements are immutable** - Cannot edit after signing
2. **All consent must be explicit** - Database rejects signing without consent flags
3. **Digital proof is mandatory** - IP, user agent, signer name required
4. **Tokens are single-use** - Consumed after signing
5. **Ledger record is immutable** - `django_agreements.Agreement` never modified
6. **Party type filtering** - Templates only show appropriate parties when sending

### Target Party Types

Agreement templates have a `target_party_type` field that controls which parties appear in the send form:

| Party Type | Source | Description |
|------------|--------|-------------|
| `diver` | DiverProfile → Person | Persons who have a DiverProfile |
| `employee` | PartyRelationship(type=employee) | Persons employed by the dive shop |
| `vendor` | PartyRelationship(type=vendor) | Organizations that supply to the dive shop |
| `any` | Person | Any person (fallback for general agreements) |

**Note**: A party can have multiple types. A person can be both a diver (has DiverProfile) AND an employee (has employee relationship). The template's target type determines which party list to show when sending.

### Database Constraints (PostgreSQL)

The `SignableAgreement` model enforces 11 check constraints:

| Category | Constraint | Enforces |
|----------|------------|----------|
| Workflow | `signable_signed_requires_signed_at` | Signed → has timestamp |
| Workflow | `signable_sent_requires_sent_at` | Sent → has timestamp |
| Workflow | `signable_sent_signed_requires_token` | Sent/Signed → has token hash |
| Workflow | `signable_signed_requires_ledger` | Signed → has ledger record |
| Data | `signable_valid_content_hash` | Content hash is 64 hex chars (SHA-256) |
| Data | `signable_unique_pending_per_party_object` | No duplicate pending agreements |
| Legal | `signable_signed_requires_terms_consent` | Signed → agreed_to_terms=True |
| Legal | `signable_signed_requires_esign_consent` | Signed → agreed_to_esign=True |
| Digital Proof | `signable_signed_requires_ip` | Signed → has IP address |
| Digital Proof | `signable_signed_requires_user_agent` | Signed → has browser fingerprint |
| Digital Proof | `signable_signed_requires_signer_name` | Signed → has signer name |

### Models

```python
# Reusable agreement content
class AgreementTemplate(BaseModel):
    dive_shop = FK(Organization)
    name = CharField(max_length=255)
    template_type = CharField(choices=["waiver", "rental", "liability", "other"])
    target_party_type = CharField(choices=["diver", "employee", "vendor", "any"])
    content = TextField()  # HTML content with template variables
    status = CharField(choices=["draft", "published", "archived"])
    version = CharField(max_length=20)

# Workflow instance sent to a party for signing
class SignableAgreement(BaseModel):
    template = FK(AgreementTemplate)
    template_version = CharField()  # Snapshot at creation
    party_a = GenericFK()  # The signer (Person)
    party_b = GenericFK()  # Counter-party (optional)
    related_object = GenericFK()  # Linked booking/enrollment

    # Content (editable until signed)
    content_snapshot = TextField()  # Rendered HTML
    content_hash = CharField(max_length=64)  # SHA-256

    # Workflow
    status = CharField(choices=["draft", "sent", "signed", "void", "expired"])
    sent_at = DateTimeField(null=True)
    signed_at = DateTimeField(null=True)
    expires_at = DateTimeField(null=True)

    # Token (hash stored, not raw)
    access_token_hash = CharField(max_length=64)
    token_consumed = BooleanField(default=False)

    # Digital proof (required for signing)
    signed_by_name = CharField()
    signed_ip = GenericIPAddressField()
    signed_user_agent = TextField()

    # Consent (required for signing)
    agreed_to_terms = BooleanField(default=False)
    agreed_to_esign = BooleanField(default=False)

    # Documents
    signature_document = FK(Document)  # PNG signature image
    signed_document = FK(Document)  # Archival PDF

    # Immutable record
    ledger_agreement = FK(django_agreements.Agreement)

# Edit history for auditability
class SignableAgreementRevision(BaseModel):
    agreement = FK(SignableAgreement)
    revision_number = PositiveIntegerField()
    previous_content_hash = CharField()
    new_content_hash = CharField()
    change_note = TextField()  # Required
    changed_by = FK(User)
```

### Service Layer API

```python
from diveops.services import (
    create_agreement_from_template,
    edit_agreement,
    send_agreement,
    sign_agreement,
    void_agreement,
    get_agreement_by_token,
    expire_stale_agreements,
)

# Create draft from template
agreement = create_agreement_from_template(
    template=waiver_template,
    party_a=diver.person,
    related_object=booking,
    actor=staff_user,
)

# Send to customer (returns raw token ONCE)
agreement, raw_token = send_agreement(
    agreement=agreement,
    delivery_method="email",
    expires_in_days=30,
    actor=staff_user,
)
signing_url = f"/sign/{raw_token}/"

# Customer signs via public page
sign_agreement(
    agreement=agreement,
    raw_token=raw_token,
    signature_image=png_bytes,
    signed_by_name="John Doe",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0...",
    agreed_to_terms=True,
    agreed_to_esign=True,
)

# Void (for legal recall)
void_agreement(
    agreement=agreement,
    reason="Customer requested cancellation",
    actor=staff_user,
)
```

### Public Signing Flow

1. Customer receives email/SMS with signing link: `/sign/{token}/`
2. Public page displays agreement content (no login required)
3. Customer must:
   - Enter full legal name
   - Draw signature on canvas
   - Check "I agree to terms" checkbox
   - Check "I consent to e-sign" checkbox
4. On submit:
   - Token verified and marked consumed
   - Signature image stored as Document
   - PDF generated with digital proof stamp
   - Immutable ledger record created
   - Audit event logged

### PDF Generation

Signed agreements generate archival PDFs with:

- Agreement content
- Signature image with name and date
- Digital proof footer:
  - Signer name
  - Signed date/time (UTC)
  - IP address
  - Browser fingerprint (truncated)
  - Content hash (SHA-256)
  - Document ID

### Audit Actions

| Action | When |
|--------|------|
| `agreement_template_created` | Template created |
| `agreement_template_updated` | Template content modified |
| `agreement_template_published` | Template made available |
| `agreement_template_archived` | Template retired |
| `agreement_created` | SignableAgreement created from template |
| `agreement_edited` | Content modified (before signing) |
| `agreement_sent` | Sent to party for signing |
| `agreement_signed` | Signed by party (includes PDF metadata) |
| `agreement_voided` | Voided by staff |
| `agreement_expired` | Marked expired by system |

### Signing Audit Data

The `agreement_signed` audit event captures:

```json
{
  "signed_by_name": "John Doe",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS...",
  "has_signature_image": true,
  "content_hash": "a1b2c3d4...",
  "consent": {
    "agreed_to_terms": true,
    "agreed_to_esign": true,
    "terms_text": "I have read and understand...",
    "esign_text": "I consent to sign electronically..."
  },
  "pdf": {
    "filename": "signed_agreement_abc123.pdf",
    "location": "/media/documents/...",
    "checksum": "sha256:...",
    "document_id": "uuid..."
  }
}
```

### URL Patterns

```
# Staff: Templates
/agreements/templates/                          # List
/agreements/templates/add/                      # Create
/agreements/templates/<pk>/                     # Detail
/agreements/templates/<pk>/edit/                # Edit
/agreements/templates/<pk>/preview/             # Preview
/agreements/templates/<pk>/publish/             # Publish
/agreements/templates/<pk>/archive/             # Archive
/agreements/templates/<pk>/send/                # Send to party

# Staff: Signable Agreements
/agreements/                                    # List (filterable)
/agreements/<pk>/                               # Detail
/agreements/<pk>/edit/                          # Edit (draft/sent only)
/agreements/<pk>/resend/                        # Generate new token
/agreements/<pk>/void/                          # Void

# Public: Signing (no login required)
/sign/<token>/                                  # Signing page (rate-limited)
```

### Security Considerations

1. **Token storage**: Raw token returned once; only SHA-256 hash stored
2. **Token verification**: Constant-time comparison prevents timing attacks
3. **Token consumption**: Marked consumed after signing (no replay)
4. **Invalid tokens**: Return 404 (no existence leak)
5. **Rate limiting**: Public signing endpoint should be rate-limited at nginx/CDN
6. **Expiration**: Enforced at signing time, not just display time

### ESIGN/UETA Compliance

| Requirement | Implementation |
|-------------|----------------|
| Intent to sign | Signature drawing + explicit submit |
| Consent to e-sign | Required checkbox with legal text |
| Understanding of terms | Required checkbox confirming reading |
| Association with record | SHA-256 content hash |
| Record retention | Immutable ledger + archival PDF |
| Reproduction | PDF downloadable by staff |

### Invariants

1. Cannot sign without both consent flags = True
2. Cannot sign without IP address and user agent
3. Cannot sign without signer name
4. Cannot sign expired agreement
5. Cannot reuse consumed token
6. Signed agreement creates immutable ledger record
7. Content edits create revision records with required change_note
8. Only one pending agreement per template+party+related_object
