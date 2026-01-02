# Chapter 6: Agreements

> "The palest ink is better than the best memory."
>
> — Chinese proverb

---

Every business transaction rests on an agreement. Someone promised something to someone else, under specific terms, for a specific period. When disputes arise—and they always arise—the question is always the same: What was agreed?

Systems that treat agreements as afterthoughts, or worse, as static configuration, eventually face a reckoning. Customers claim they were promised different terms. Partners insist the contract said something else. Auditors ask for proof of what was agreed at the time of the transaction, not what the current terms say.

The problem isn't that agreements are complex. It's that most systems treat them as immutable documents rather than living, versioned data structures that evolve over time while preserving their complete history.

## The Oldest Primitive

Agreements predate writing. The handshake. The verbal contract. The witnessed oath. But the earliest written business records are contracts. The Code of Hammurabi, carved in stone around 1754 BCE, is largely a codification of contract law: what happens when parties fail to meet their obligations.

Luca Pacioli, documenting double-entry bookkeeping in 1494, assumed agreements as foundational. You can't record a sale without an agreement on price. You can't record a debt without an agreement on repayment terms. The ledger is a record of fulfilled obligations; agreements define what those obligations are.

Every ERP system, every order management system, every subscription service is fundamentally a machine for managing agreements. Yet most systems bury this primitive under layers of domain-specific terminology—"orders," "contracts," "subscriptions," "policies"—losing the underlying pattern.

## The Failure Modes

### Terms as Prose

The most common mistake is storing agreement terms as free text. A contract is uploaded as a PDF. Terms and conditions are stored in a text field. The subscription description lives in a marketing database.

This works until you need to compute with the terms. What's the cancellation policy? How many days notice is required for a price change? What's the penalty for early termination? If the answer requires a human to read a document and interpret it, you don't have data—you have literature.

In 2019, Disney acquired 21st Century Fox for $71.3 billion. Part of the integration involved reconciling thousands of content licensing agreements, many of which existed only as scanned PDFs with inconsistent terminology. The Wall Street Journal reported that Disney spent months and significant resources simply cataloging what rights they had acquired and under what terms.

Terms that can't be queried can't be enforced programmatically. Every decision becomes a manual process, every renewal becomes a research project, and every dispute becomes archaeology.

### The Vanishing History Problem

Most systems overwrite agreement terms when they change. A customer's subscription plan changes from Basic to Pro. The system updates a field. The old terms are gone.

Then the customer disputes a charge from two months ago. What plan were they on? What was the price? What features were included? If your system only stores current state, you're guessing.

This problem compounds in B2B relationships where contracts are negotiated, amended, and extended over years. A vendor might claim a 30-day payment term was always the deal; your system shows 15 days but has no record of when that changed or who agreed to it.

The legal principle is clear: agreements are binding based on what was agreed at the time, not what the current terms say. Systems that can't reconstruct historical terms fail this basic requirement.

### The "Who Agreed?" Problem

A salesperson offers a customer a special discount. The customer accepts. A year later, when the discount expires and the customer is charged full price, they complain.

Who authorized that discount? When? Was it within their authority? Is there any record of the customer's acceptance?

Without explicit signatory tracking, these questions are unanswerable. The agreement exists as a fact in the system, but the decision trail is missing. You can't prove who agreed to what, or when, or with what authority.

Sarbanes-Oxley, among other regulations, requires that companies maintain records of who authorized significant transactions. An agreement without a decision surface—who made this agreement, on what authority, with what evidence—is a compliance liability.

## The Two Parties, Always

Every agreement has at least two parties. This seems obvious, but many systems fail to model it correctly.

Consider a subscription service. The naive model: a User has a subscription_plan field. But this hides the agreement. Who is the subscription with? The company offering the service is a party to the agreement. So is the customer. The agreement exists between them.

Why does this matter? Because parties have different rights and obligations. The service provider agrees to provide access. The customer agrees to pay. The terms define what happens if either party fails to perform.

When you model the service provider as implicit—just "the system"—you lose the ability to handle multi-vendor scenarios, reseller relationships, or acquisitions where the providing party changes.

```python
from django_basemodels import BaseModel
from django.db.models import Q, F

class Agreement(BaseModel):
    """Agreement between two parties. Inherits UUID, timestamps, soft delete."""

    # Both parties are explicit
    party_a_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    party_a_id = models.CharField(max_length=255)
    party_a = GenericForeignKey('party_a_content_type', 'party_a_id')

    party_b_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    party_b_id = models.CharField(max_length=255)
    party_b = GenericForeignKey('party_b_content_type', 'party_b_id')

    # Terms are structured data, not prose
    terms = models.JSONField()

    # Validity period - valid_from has NO DEFAULT (service provides it)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)

    # Version counter - synced by service layer
    current_version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            # Django 6.0+: use 'condition', not 'check'
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gt=F('valid_from')),
                name='agreements_valid_to_after_valid_from'
            ),
        ]
```

The GenericForeignKey pattern allows either party to be any model: a Person, an Organization, or any other entity. This flexibility handles the full spectrum of agreements from consumer subscriptions to enterprise contracts to multi-party consortiums.

## Terms as Data

The critical design decision is storing terms as structured data, not prose.

Compare:

**Prose version:**
```
"Customer agrees to pay $49.99 per month for the Pro plan,
billed on the 15th of each month. Service includes unlimited
API calls and 24/7 support. Either party may terminate with
30 days written notice."
```

**Data version:**
```json
{
  "plan": "pro",
  "price_cents": 4999,
  "currency": "USD",
  "billing_cycle": "monthly",
  "billing_day": 15,
  "features": ["unlimited_api", "24_7_support"],
  "termination_notice_days": 30
}
```

The data version can be computed. You can query all agreements with `termination_notice_days < 30`. You can calculate total monthly revenue by summing `price_cents`. You can automatically send notices based on `termination_notice_days`.

The prose version requires human interpretation for every operation.

This doesn't mean you eliminate prose entirely. Legal agreements often require human-readable text for enforceability. But the authoritative terms—the ones the system acts on—must be structured data. The prose is documentation; the JSON is truth.

## The Projection + Ledger Pattern

Agreements use a pattern that appears throughout business software: **projection + ledger**.

- **Agreement** stores current state (the projection). Its `terms` field reflects the latest terms. Its `current_version` field tells you how many amendments have occurred.

- **AgreementVersion** stores immutable history (the ledger). Each amendment creates a new version record. These records are never modified after creation.

When agreement terms change, you don't edit the agreement. You create a new version and update the projection.

```python
class AgreementVersion(BaseModel):
    """Immutable version history. Never modified after creation."""

    agreement = models.ForeignKey(Agreement, on_delete=CASCADE, related_name='versions')
    version = models.PositiveIntegerField()
    terms = models.JSONField()
    created_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT)
    reason = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['agreement', 'version'],
                name='unique_agreement_version'
            ),
        ]
        ordering = ['-version']
```

**The invariant:** `Agreement.current_version == max(AgreementVersion.version)`

This invariant is maintained by the service layer, not the model. More on that shortly.

Now you have complete history. Version 1 is the original agreement. Version 2 is the first amendment. Version 3 is the second. Each version captures:

- What the terms were
- When the change was made (via BaseModel's `created_at`)
- Who authorized it
- Why it was changed

To answer "What were the terms on March 15th?", you query for the latest version where `created_at <= March 15th`. The answer is unambiguous and auditable.

This pattern also supports rollbacks. If an amendment was made in error, you create a new version that restores the previous terms. The erroneous version remains in history—you never destroy data—but the current effective terms are correct.

## The Decision Surface

Every agreement represents a decision. Someone authorized it. That decision must be recorded.

```python
class Agreement(models.Model):
    # ... party fields ...

    # Decision surface
    agreed_at = models.DateTimeField()  # When the agreement was made
    agreed_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT)  # Who authorized it

    # Validity
    valid_from = models.DateTimeField()  # When terms take effect
    valid_to = models.DateTimeField(null=True, blank=True)  # When terms expire
```

Notice the distinction between `agreed_at` and `valid_from`. An agreement might be signed in December but take effect in January. The decision happened at `agreed_at`; the terms apply from `valid_from`.

For complex agreements requiring multiple signatories—like partnership contracts or multi-party licensing deals—you extend this with a Signatory model:

```python
class Signatory(models.Model):
    agreement_version = models.ForeignKey(AgreementVersion, on_delete=CASCADE)
    party = GenericForeignKey()
    signed_at = models.DateTimeField()
    signature_metadata = models.JSONField()  # IP address, device, method
```

Now you can track exactly who signed what version of what agreement, when, and how.

## Temporal Queries

The `valid_from` and `valid_to` fields enable temporal queries essential for business operations.

**Current agreements:**
```python
Agreement.objects.filter(
    valid_from__lte=now(),
).filter(
    Q(valid_to__isnull=True) | Q(valid_to__gt=now())
)
```

**Agreements valid on a specific date:**
```python
Agreement.objects.as_of(specific_date)
```

**Agreements for a specific party:**
```python
Agreement.objects.for_party(customer)
```

These queries are fundamental for:

- Billing: What agreements are active this billing cycle?
- Compliance: What terms applied when this transaction occurred?
- Renewals: What agreements expire in the next 30 days?
- Disputes: What did the customer agree to at the time of this event?

A nullable `valid_to` means "until further notice"—the agreement continues indefinitely until explicitly terminated. This handles month-to-month subscriptions and evergreen contracts.

## Scope and Context

Agreements often relate to something else—an order, a service, an asset. The scope field captures this:

```python
class Agreement(models.Model):
    # ... other fields ...

    scope_type = models.CharField(max_length=50)  # 'order', 'subscription', 'consent'
    scope_ref_content_type = models.ForeignKey(ContentType, null=True, blank=True)
    scope_ref_id = models.CharField(max_length=255, blank=True)
    scope_ref = GenericForeignKey('scope_ref_content_type', 'scope_ref_id')
```

This allows agreements to be linked to any domain object:

- A service level agreement (SLA) linked to a support contract
- Terms of sale linked to a specific order
- Consent to data processing linked to a user account
- A warranty linked to a purchased product

The `scope_type` provides a quick filter without requiring a join, while `scope_ref` provides the full linkage.

## The Service Layer

Models define structure. Services enforce business rules.

For agreements, the service layer maintains the projection + ledger invariant and provides atomic operations:

```python
# services.py
from django.db import transaction
from django.utils import timezone

class AgreementError(Exception):
    """Base exception for agreement operations."""
    pass

class InvalidTerminationError(AgreementError):
    """Raised when termination date is invalid."""
    pass


def create_agreement(
    party_a,
    party_b,
    scope_type,
    terms,
    agreed_by,
    valid_from=None,  # Convenience default
    agreed_at=None,
    valid_to=None,
    scope_ref=None,
):
    """Create agreement with initial version."""
    if valid_from is None:
        valid_from = timezone.now()
    if agreed_at is None:
        agreed_at = timezone.now()

    # Validate dates
    if valid_to and valid_to <= valid_from:
        raise AgreementError("valid_to must be after valid_from")

    with transaction.atomic():
        agreement = Agreement.objects.create(
            party_a=party_a,
            party_b=party_b,
            scope_type=scope_type,
            terms=terms,
            agreed_by=agreed_by,
            agreed_at=agreed_at,
            valid_from=valid_from,
            valid_to=valid_to,
            scope_ref=scope_ref,
            current_version=1,
        )

        AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms=terms,
            created_by=agreed_by,
            reason="Initial agreement",
        )

    return agreement


def amend_agreement(agreement, new_terms, reason, amended_by):
    """Amend agreement terms, creating new version."""
    with transaction.atomic():
        # Lock the row for safe version increment
        agreement = Agreement.objects.select_for_update().get(pk=agreement.pk)

        new_version = agreement.current_version + 1

        # Create ledger entry (immutable)
        AgreementVersion.objects.create(
            agreement=agreement,
            version=new_version,
            terms=new_terms,
            created_by=amended_by,
            reason=reason,
        )

        # Update projection
        agreement.terms = new_terms
        agreement.current_version = new_version
        agreement.save()

    return agreement


def terminate_agreement(agreement, terminated_by, valid_to=None, reason="Terminated"):
    """Terminate agreement by setting valid_to."""
    if valid_to is None:
        valid_to = timezone.now()

    if valid_to <= agreement.valid_from:
        raise InvalidTerminationError("Termination date must be after valid_from")

    with transaction.atomic():
        agreement = Agreement.objects.select_for_update().get(pk=agreement.pk)

        new_version = agreement.current_version + 1

        AgreementVersion.objects.create(
            agreement=agreement,
            version=new_version,
            terms=agreement.terms,
            created_by=terminated_by,
            reason=reason,
        )

        agreement.valid_to = valid_to
        agreement.current_version = new_version
        agreement.save()

    return agreement
```

**Why services instead of model.save()?**

1. **Atomic invariants.** Creating an agreement requires creating a version. Amending requires updating both projection and ledger. These must happen together or not at all.

2. **Concurrency safety.** `select_for_update()` prevents two simultaneous amendments from creating the same version number.

3. **Validation in context.** The termination date must be after `valid_from`. This check belongs in the operation, not in `model.clean()`.

4. **Convenience defaults.** The model has no default for `valid_from`—it's required. The service provides `timezone.now()` as a sensible default.

## Hands-On: Building Agreements with AI

Now we put the primitive into practice. These exercises demonstrate how to direct an AI to generate agreement-aware code correctly.

### Exercise 1: Unconstrained Agreement

Ask an AI:

```
Build a Django model for tracking customer subscriptions.
Include the plan name, price, and start date.
```

Examine what you get. Typically:

- A single model with mutable fields
- No version history
- No party relationships (customer might be there, but service provider is implicit)
- No temporal queries
- Price as a stored value, not a computed reference

The AI produces something that works for the happy path but fails every edge case.

### Exercise 2: Constrained Agreement

Now ask with explicit constraints:

```
Build a Django app for subscription agreements using these constraints:

1. Agreement model inheriting from BaseModel (UUID, timestamps, soft delete)
   - TWO explicit parties via GenericForeignKey
   - party_a_id and party_b_id are CharField (not IntegerField) for UUID support

2. Terms stored as JSONField, not prose
   - Must support: plan_id, price_cents, currency, billing_cycle
   - Never store price as float

3. Projection + Ledger pattern
   - Agreement has terms (current projection) and current_version counter
   - AgreementVersion stores immutable history (the ledger)
   - Invariant: Agreement.current_version == max(AgreementVersion.version)

4. Service layer for all writes
   - create_agreement(): Creates agreement + initial version atomically
   - amend_agreement(): Creates new version, updates projection
   - terminate_agreement(): Sets valid_to, creates termination version
   - Use select_for_update() for safe version increment

5. Temporal validity
   - valid_from (REQUIRED, no default in model - service provides convenience)
   - valid_to (nullable means indefinite)
   - CheckConstraint: valid_to > valid_from (use 'condition' for Django 6.0+)
   - QuerySet methods: current(), as_of(timestamp), for_party(party)

6. Agreements are never hard deleted (soft delete from BaseModel)

Write tests first using TDD.
```

The output should match the pattern from this chapter. If any constraint is violated, the test suite will catch it.

### Exercise 3: Subscription Lifecycle

Test your understanding by implementing a complete subscription flow using the service layer:

```
Using the Agreement model and services from Exercise 2, implement:

1. create_subscription(customer, provider, plan_terms, started_by)
   - Calls create_agreement() with scope_type='subscription'
   - valid_from defaults to now (via service), valid_to is None
   - Returns the Agreement

2. upgrade_subscription(agreement, new_plan_terms, upgraded_by, reason)
   - Calls amend_agreement() with the new terms
   - Increments current_version via select_for_update()
   - Updates projection, creates immutable ledger entry
   - Returns the updated Agreement

3. cancel_subscription(agreement, cancelled_by, cancellation_date, reason)
   - Calls terminate_agreement()
   - Sets valid_to to cancellation_date
   - Creates termination version in ledger
   - Returns the updated Agreement

4. get_terms_as_of(agreement, timestamp)
   - Returns the terms snapshot from the latest version where created_at <= timestamp
   - Returns None if no version existed at that time

Write tests covering:
- Creating a subscription (verify Agreement + AgreementVersion created atomically)
- Upgrading twice (version 1 → 2 → 3, projection matches latest)
- Querying terms at various points in history (use version created_at)
- Cancelling and confirming is_active returns False
- Rejecting invalid termination date (must be after valid_from)
- Concurrency: two simultaneous amendments don't corrupt version
```

This exercise forces the AI to implement the full projection + ledger pattern with service layer correctly.

## The Prompt Contract for Agreements

When using AI to work with agreements in your codebase, enforce these rules:

```markdown
## Agreement Primitive Constraints

### Must Do
- Inherit from BaseModel (UUID, timestamps, soft delete)
- Use GenericForeignKey for both parties (supports any model type)
- Store terms as JSONField with structured, computable data
- Use Projection + Ledger pattern (Agreement + AgreementVersion)
- Track decision surface (agreed_at, agreed_by for every agreement)
- Implement temporal queries (current(), as_of(), for_party())
- Use valid_from/valid_to for temporal validity
- Add CheckConstraint: valid_to > valid_from (use 'condition' for Django 6.0+)
- Write all mutations through service layer (create, amend, terminate)
- Use select_for_update() when incrementing version counters

### Must Not
- Never edit agreement terms directly (use amend_agreement service)
- Never hard delete agreements (soft delete from BaseModel)
- Never put business logic in model.save() (use services)
- Never store terms as prose in TextField
- Never use Float for monetary amounts in terms
- Never assume parties are always User model (use GenericFK)
- Never modify AgreementVersion records after creation
- Never add default for valid_from in model (service provides convenience)

### Invariants
- Agreement.current_version == max(AgreementVersion.version)
- Every Agreement has at least one AgreementVersion (the original)
- Version numbers are strictly increasing per agreement
- valid_to must be > valid_from when both are set
- AgreementVersion records are immutable after creation
```

Include this in your project's CLAUDE.md or load it when working on agreement-related features.

## What AI Gets Wrong

Without explicit constraints, AI-generated agreement code typically:

1. **Skips BaseModel** — Manually adds UUID, timestamps, or soft delete fields. Or worse, uses auto-increment IDs.

2. **Models only one party** — The customer has a `subscription`, but who is the subscription with? The provider is implicit, breaking when you add resellers or multi-vendor scenarios.

3. **Puts logic in save()** — Business rules in `model.save()` instead of service functions. No atomicity, no concurrency safety.

4. **Uses mutable fields** — Plan changes update the subscription record. History is lost. No projection + ledger pattern.

5. **Adds defaults to valid_from** — `default=timezone.now` in the model. This hides accidental omissions instead of enforcing explicit dates.

6. **Ignores temporal validity** — No valid_from/valid_to means you can't query historical state or handle future-dated agreements.

7. **Uses FloatField for money** — `"price": 49.99` stored as a float introduces rounding errors.

8. **Uses check= in CheckConstraint** — Django 6.0 changed the API to `condition=`. Old code breaks silently.

9. **No concurrency handling** — Two simultaneous amendments create duplicate version numbers.

The fix is always explicit constraints. Tell the AI exactly what pattern to follow—BaseModel, service layer, projection + ledger, select_for_update—and it will follow it consistently.

## Why This Matters Later

Agreements are the foundation for:

- **Billing**: Subscriptions, invoices, and payment schedules are all derived from agreement terms.

- **Catalogs**: When an order is placed, the terms at that moment—prices, discounts, delivery promises—become part of an implicit agreement.

- **Workflows**: Service level agreements define response times and escalation paths for encounters.

- **Audit**: Every financial transaction should trace back to the agreement that authorized it.

Get agreements wrong, and every system that depends on "what was promised" becomes unreliable. Get them right, and you have a solid foundation for subscription management, contract negotiations, and compliance reporting.

---

## How to Rebuild This Primitive

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-agreements | `docs/PRIMITIVE_PROMPT.md` | ~47 tests |

### Using the Prompt

```bash
cat docs/PRIMITIVE_PROMPT.md | claude

# Request: "Create django-agreements package with:
# - Agreement model inheriting BaseModel
# - AgreementVersion for immutable history
# - Service layer: create_agreement, amend_agreement, terminate_agreement
# - Projection + ledger pattern"
```

### Key Constraints

- **Inherit from BaseModel**: UUID, timestamps, soft delete built in
- **Projection + Ledger pattern**: Agreement.terms is projection, AgreementVersion is ledger
- **Service layer required**: All writes go through create/amend/terminate functions
- **Invariant enforced by services**: Agreement.current_version == max(AgreementVersion.version)
- **No defaults for valid_from**: Model requires it, service provides convenience
- **Concurrency safe**: select_for_update() when incrementing versions
- **Django 6.0 compatible**: CheckConstraint uses `condition=` not `check=`

If Claude puts business logic in model.save() or adds defaults to valid_from, that's a constraint violation.

---

## Sources and References

1. **Code of Hammurabi** — Written circa 1754 BCE, the earliest known written legal code, primarily addressing contractual relationships. British Museum, London.

2. **Pacioli, Luca** (1494). *Summa de arithmetica, geometria, proportioni et proportionalita*. The section on double-entry bookkeeping assumes contracts as the foundation of commercial transactions.

3. **Disney-Fox Integration** — "Disney's Fox Deal: A $71.3 Billion Bet," *Wall Street Journal*, March 20, 2019. The content licensing reconciliation challenge was discussed in subsequent integration reports.

4. **Sarbanes-Oxley Act** — Public Law 107-204 (2002), Section 302 and 404 on internal controls and documentation of authorization chains.

5. **GenericForeignKey pattern** — Django documentation on the contenttypes framework. This pattern enables polymorphic relationships essential for flexible agreement parties.

---

*Status: Complete*
