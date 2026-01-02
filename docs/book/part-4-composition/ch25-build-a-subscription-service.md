# Chapter 25: Build a Subscription Service

## The Churn Spreadsheet

In 2012, a bootstrapped SaaS founder discovered her customers were churning faster than she could acquire them. Her subscription management system—a collection of Stripe webhooks and cron jobs—couldn't answer basic questions:

- When did this customer's plan actually change?
- What was their usage during the billing period that just ended?
- Why did we charge them $127.43 instead of $99?
- Who on their team had access to what features, and when?

She spent three weeks rebuilding her subscription system with proper temporal tracking and immutable billing records. Churn dropped 23% in the next quarter—not from product changes, but from being able to answer customer billing questions accurately.

This chapter builds that system: subscription management with time semantics, usage tracking, and ledger-based billing. Same primitives. Different domain.

---

## The Domain

A SaaS subscription service needs:

- **Customers and accounts** - individuals or organizations that subscribe
- **Plans and pricing** - what they can buy and at what price
- **Subscriptions** - the ongoing relationship between customer and plan
- **Billing cycles** - when and how much to charge
- **Usage tracking** - what they actually used (for usage-based pricing)
- **Invoices** - immutable records of what was charged
- **Feature access** - what features are available on which plans
- **Plan changes** - upgrades, downgrades, and proration

## Primitive Mapping

| Domain Concept | Primitive | Package |
|----------------|-----------|---------|
| Customer | Party (Person) | django-parties |
| Company account | Party (Organization) | django-parties |
| Team member | PartyRelationship | django-parties |
| Plan | CatalogItem | django-catalog |
| Plan tier | Category | django-catalog |
| Subscription | Agreement | django-agreements |
| Billing cycle | Agreement terms | django-agreements |
| Invoice | Transaction | django-ledger |
| Payment | Entry | django-ledger |
| Usage event | AuditLog (custom event) | django-audit-log |
| Feature access | Role + Permission | django-rbac |
| Plan features | Agreement terms | django-agreements |

Zero new models. Subscriptions are compositions of existing primitives.

---

## Customer Accounts

A SaaS customer might be an individual or an organization. Organizations have team members with different roles.

### Person as Customer

```python
from django_parties.models import Person

# Individual customer
customer = Person.objects.create(
    email="developer@example.com",
    full_name="Alex Developer",
    metadata={
        "source": "organic_signup",
        "referral_code": "HACKERNEWS",
    }
)
```

### Organization as Customer

```python
from django_parties.models import Organization, Person, PartyRelationship

# Company account
company = Organization.objects.create(
    name="Acme Corp",
    email="billing@acme.com",
    metadata={
        "industry": "technology",
        "employee_count": "50-200",
    }
)

# Account owner
owner = Person.objects.create(
    email="cto@acme.com",
    full_name="Jamie CTO",
)

# Relationship with role
PartyRelationship.objects.create(
    from_party=owner,
    to_party=company,
    relationship_type="account_owner",
    valid_from=timezone.now(),
)

# Team member with billing access
billing_admin = Person.objects.create(
    email="finance@acme.com",
    full_name="Morgan Finance",
)

PartyRelationship.objects.create(
    from_party=billing_admin,
    to_party=company,
    relationship_type="billing_admin",
    valid_from=timezone.now(),
)
```

### Querying Team at Any Point

```python
# Current team
current_team = PartyRelationship.objects.filter(
    to_party=company,
).current()

# Team as of last billing date
team_at_billing = PartyRelationship.objects.filter(
    to_party=company,
).as_of(last_invoice_date)

# Who was account owner when they upgraded?
owner_at_upgrade = PartyRelationship.objects.filter(
    to_party=company,
    relationship_type="account_owner",
).as_of(upgrade_date).first()
```

---

## Plans as Catalog Items

Subscription plans are catalog items with pricing and feature metadata.

### Plan Hierarchy

```python
from django_catalog.models import Category, CatalogItem
from decimal import Decimal

# Plan tiers
tier_starter = Category.objects.create(
    name="Starter",
    code="starter",
    metadata={"max_seats": 5, "support_level": "community"},
)

tier_pro = Category.objects.create(
    name="Professional",
    code="pro",
    metadata={"max_seats": 50, "support_level": "email"},
)

tier_enterprise = Category.objects.create(
    name="Enterprise",
    code="enterprise",
    metadata={"max_seats": None, "support_level": "dedicated"},  # Unlimited
)
```

### Plan Definitions

```python
# Monthly plans
starter_monthly = CatalogItem.objects.create(
    category=tier_starter,
    name="Starter Monthly",
    sku="starter_monthly",
    unit_price=Decimal("29.00"),
    currency="USD",
    metadata={
        "billing_interval": "month",
        "billing_interval_count": 1,
        "features": [
            "5_team_members",
            "1000_api_calls",
            "community_support",
            "basic_analytics",
        ],
        "limits": {
            "team_members": 5,
            "api_calls_per_month": 1000,
            "storage_gb": 5,
        },
    }
)

pro_monthly = CatalogItem.objects.create(
    category=tier_pro,
    name="Professional Monthly",
    sku="pro_monthly",
    unit_price=Decimal("99.00"),
    currency="USD",
    metadata={
        "billing_interval": "month",
        "billing_interval_count": 1,
        "features": [
            "50_team_members",
            "50000_api_calls",
            "email_support",
            "advanced_analytics",
            "api_access",
            "custom_integrations",
        ],
        "limits": {
            "team_members": 50,
            "api_calls_per_month": 50000,
            "storage_gb": 100,
        },
    }
)

# Annual plans (discounted)
pro_annual = CatalogItem.objects.create(
    category=tier_pro,
    name="Professional Annual",
    sku="pro_annual",
    unit_price=Decimal("990.00"),  # 2 months free
    currency="USD",
    metadata={
        "billing_interval": "year",
        "billing_interval_count": 1,
        "features": pro_monthly.metadata["features"],  # Same features
        "limits": pro_monthly.metadata["limits"],      # Same limits
        "annual_discount": "16.67%",
    }
)
```

### Usage-Based Add-ons

```python
# API call overage
api_overage = CatalogItem.objects.create(
    category=tier_pro,
    name="API Calls (overage)",
    sku="api_calls_overage",
    unit_price=Decimal("0.001"),  # $0.001 per call
    currency="USD",
    metadata={
        "billing_type": "usage",
        "unit": "api_call",
    }
)

# Additional storage
storage_addon = CatalogItem.objects.create(
    category=tier_pro,
    name="Additional Storage",
    sku="storage_addon_10gb",
    unit_price=Decimal("5.00"),
    currency="USD",
    metadata={
        "billing_type": "recurring",
        "storage_gb": 10,
    }
)
```

---

## Subscriptions as Agreements

A subscription is an agreement between a customer and the service provider. The agreement captures what plan they're on, when it started, and the billing terms.

### Creating a Subscription

```python
from django_agreements.models import Agreement
from django_parties.models import Organization

# The provider (your company)
provider = Organization.objects.get(name="CloudSoft Inc")

# Subscribe customer to Pro Monthly
subscription = Agreement.objects.create(
    agreement_type="subscription",
    status="active",
    valid_from=timezone.now(),
    valid_to=None,  # Until cancelled
    metadata={
        "plan_sku": "pro_monthly",
        "price_at_signup": "99.00",
        "currency": "USD",
        "billing_day": 15,  # Bill on 15th of each month
        "payment_method_id": "pm_card_visa_4242",
    }
)

# Link parties to agreement
from django_agreements.models import AgreementParty

AgreementParty.objects.create(
    agreement=subscription,
    party=company,  # Customer
    role="subscriber",
)

AgreementParty.objects.create(
    agreement=subscription,
    party=provider,
    role="provider",
)
```

### Subscription with Trial

```python
from datetime import timedelta

trial_start = timezone.now()
trial_end = trial_start + timedelta(days=14)

subscription = Agreement.objects.create(
    agreement_type="subscription",
    status="trialing",
    valid_from=trial_start,
    valid_to=None,
    metadata={
        "plan_sku": "pro_monthly",
        "price_at_signup": "99.00",
        "trial_start": trial_start.isoformat(),
        "trial_end": trial_end.isoformat(),
        "billing_starts": trial_end.isoformat(),
    }
)
```

### Querying Active Subscriptions

```python
# All currently active subscriptions
active_subs = Agreement.objects.filter(
    agreement_type="subscription",
    status__in=["active", "trialing"],
).current()

# Subscriptions that were active on a specific date
subs_last_month = Agreement.objects.filter(
    agreement_type="subscription",
).as_of(last_month)

# Find customer's subscription
customer_sub = Agreement.objects.filter(
    agreement_type="subscription",
    agreementparty__party=customer,
    agreementparty__role="subscriber",
).current().first()
```

---

## Billing Cycles and Invoicing

Billing uses the ledger. Each invoice is an immutable transaction that records what was charged and why.

### Account Structure

```python
from django_ledger.models import Account

# Revenue accounts
subscription_revenue = Account.objects.create(
    name="Subscription Revenue",
    code="4100",
    account_type="revenue",
)

usage_revenue = Account.objects.create(
    name="Usage Revenue",
    code="4200",
    account_type="revenue",
)

# Asset accounts
accounts_receivable = Account.objects.create(
    name="Accounts Receivable",
    code="1200",
    account_type="asset",
)

cash = Account.objects.create(
    name="Cash",
    code="1000",
    account_type="asset",
)
```

### Creating an Invoice

```python
from django_ledger.models import Transaction, Entry
from django_ledger.services import post_transaction

def create_invoice(subscription, billing_period_start, billing_period_end):
    """Create invoice for a billing period."""
    plan = CatalogItem.objects.get(sku=subscription.metadata["plan_sku"])
    amount = plan.unit_price

    # Create the invoice transaction
    invoice = Transaction.objects.create(
        transaction_type="invoice",
        effective_at=billing_period_end,
        metadata={
            "subscription_id": str(subscription.id),
            "billing_period_start": billing_period_start.isoformat(),
            "billing_period_end": billing_period_end.isoformat(),
            "plan_sku": plan.sku,
            "plan_name": plan.name,
        }
    )

    # Debit receivables, credit revenue
    Entry.objects.create(
        transaction=invoice,
        account=accounts_receivable,
        amount=amount,
        entry_type="debit",
        description=f"Subscription: {plan.name}",
    )

    Entry.objects.create(
        transaction=invoice,
        account=subscription_revenue,
        amount=amount,
        entry_type="credit",
        description=f"Subscription: {plan.name}",
    )

    # Post the transaction (makes it immutable)
    post_transaction(invoice)

    return invoice
```

### Recording Payment

```python
def record_payment(invoice, payment_method, payment_ref):
    """Record payment against an invoice."""
    amount = invoice.entries.filter(entry_type="debit").aggregate(
        total=Sum("amount")
    )["total"]

    payment = Transaction.objects.create(
        transaction_type="payment",
        effective_at=timezone.now(),
        metadata={
            "invoice_id": str(invoice.id),
            "payment_method": payment_method,
            "payment_ref": payment_ref,
        }
    )

    # Debit cash, credit receivables
    Entry.objects.create(
        transaction=payment,
        account=cash,
        amount=amount,
        entry_type="debit",
    )

    Entry.objects.create(
        transaction=payment,
        account=accounts_receivable,
        amount=amount,
        entry_type="credit",
    )

    post_transaction(payment)

    # Log the payment event
    log_event(
        target=invoice,
        event_type="payment_received",
        metadata={
            "payment_id": str(payment.id),
            "amount": str(amount),
            "method": payment_method,
        }
    )

    return payment
```

### Billing Run

```python
from dateutil.relativedelta import relativedelta

def run_monthly_billing(billing_date):
    """Run billing for all subscriptions due on this date."""

    # Find active subscriptions with matching billing day
    due_subscriptions = Agreement.objects.filter(
        agreement_type="subscription",
        status="active",
        metadata__billing_day=billing_date.day,
    ).current()

    results = []

    for subscription in due_subscriptions:
        # Calculate billing period
        period_end = billing_date
        period_start = period_end - relativedelta(months=1)

        try:
            # Create invoice
            invoice = create_invoice(
                subscription=subscription,
                billing_period_start=period_start,
                billing_period_end=period_end,
            )

            # Attempt payment
            payment_method = subscription.metadata.get("payment_method_id")
            payment_result = charge_payment_method(
                payment_method,
                invoice.total,
            )

            if payment_result.success:
                record_payment(invoice, "card", payment_result.charge_id)
                results.append({"subscription": subscription.id, "status": "paid"})
            else:
                results.append({
                    "subscription": subscription.id,
                    "status": "failed",
                    "reason": payment_result.error,
                })

        except Exception as e:
            results.append({
                "subscription": subscription.id,
                "status": "error",
                "reason": str(e),
            })

    return results
```

---

## Usage Tracking

Usage-based billing requires tracking what customers actually use. The audit log captures usage events.

### Recording Usage

```python
from django_audit_log.services import log_event

def record_api_call(subscription, endpoint, response_time_ms, response_code):
    """Record an API call for usage tracking."""
    log_event(
        target=subscription,
        event_type="api_call",
        metadata={
            "endpoint": endpoint,
            "response_time_ms": response_time_ms,
            "response_code": response_code,
            "timestamp": timezone.now().isoformat(),
        }
    )

def record_storage_usage(subscription, bytes_stored):
    """Record storage snapshot for usage tracking."""
    log_event(
        target=subscription,
        event_type="storage_snapshot",
        metadata={
            "bytes_stored": bytes_stored,
            "gb_stored": bytes_stored / (1024 ** 3),
            "timestamp": timezone.now().isoformat(),
        }
    )
```

### Querying Usage

```python
from django_audit_log.models import AuditLog
from django.db.models import Count, Avg

def get_usage_for_period(subscription, start_date, end_date):
    """Get usage metrics for a billing period."""

    events = AuditLog.objects.for_target(subscription).filter(
        created_at__gte=start_date,
        created_at__lt=end_date,
    )

    # API calls
    api_calls = events.filter(event_type="api_call").count()

    # Average response time
    avg_response = events.filter(event_type="api_call").aggregate(
        avg_ms=Avg("metadata__response_time_ms")
    )["avg_ms"]

    # Peak storage (latest snapshot in period)
    storage_snapshot = events.filter(
        event_type="storage_snapshot"
    ).order_by("-created_at").first()

    storage_gb = 0
    if storage_snapshot:
        storage_gb = storage_snapshot.metadata.get("gb_stored", 0)

    return {
        "api_calls": api_calls,
        "avg_response_ms": avg_response,
        "storage_gb": storage_gb,
    }
```

### Usage-Based Billing

```python
def calculate_overage_charges(subscription, period_start, period_end):
    """Calculate overage charges for a billing period."""
    plan = CatalogItem.objects.get(sku=subscription.metadata["plan_sku"])
    limits = plan.metadata.get("limits", {})

    usage = get_usage_for_period(subscription, period_start, period_end)
    charges = []

    # API call overage
    api_limit = limits.get("api_calls_per_month", 0)
    api_used = usage["api_calls"]

    if api_used > api_limit:
        overage = api_used - api_limit
        overage_rate = Decimal("0.001")  # $0.001 per call
        charges.append({
            "type": "api_overage",
            "quantity": overage,
            "unit_price": overage_rate,
            "amount": overage * overage_rate,
            "description": f"API calls overage: {overage} calls @ ${overage_rate}/call",
        })

    # Storage overage
    storage_limit = limits.get("storage_gb", 0)
    storage_used = usage["storage_gb"]

    if storage_used > storage_limit:
        overage = storage_used - storage_limit
        overage_rate = Decimal("0.50")  # $0.50 per GB
        charges.append({
            "type": "storage_overage",
            "quantity": overage,
            "unit_price": overage_rate,
            "amount": Decimal(overage) * overage_rate,
            "description": f"Storage overage: {overage:.2f} GB @ ${overage_rate}/GB",
        })

    return charges
```

---

## Feature Access with RBAC

Different plans unlock different features. RBAC controls what users can do.

### Plan-Based Roles

```python
from django_rbac.models import Role, Permission

# Create permissions for features
api_access = Permission.objects.create(
    code="api_access",
    name="API Access",
    description="Can use the API",
)

advanced_analytics = Permission.objects.create(
    code="advanced_analytics",
    name="Advanced Analytics",
    description="Can access advanced analytics",
)

custom_integrations = Permission.objects.create(
    code="custom_integrations",
    name="Custom Integrations",
    description="Can configure custom integrations",
)

priority_support = Permission.objects.create(
    code="priority_support",
    name="Priority Support",
    description="Can access priority support channel",
)

# Create plan-based roles
starter_role = Role.objects.create(
    name="Starter Plan",
    code="plan_starter",
)
# Starter gets no premium permissions

pro_role = Role.objects.create(
    name="Professional Plan",
    code="plan_pro",
)
pro_role.permissions.add(api_access, advanced_analytics, custom_integrations)

enterprise_role = Role.objects.create(
    name="Enterprise Plan",
    code="plan_enterprise",
)
enterprise_role.permissions.add(
    api_access, advanced_analytics, custom_integrations, priority_support
)
```

### Syncing Subscription to Role

```python
from django_rbac.models import UserRole

def sync_subscription_role(subscription, user):
    """Sync user's role based on their subscription."""
    plan_sku = subscription.metadata["plan_sku"]

    # Map plan to role
    plan_role_map = {
        "starter_monthly": "plan_starter",
        "starter_annual": "plan_starter",
        "pro_monthly": "plan_pro",
        "pro_annual": "plan_pro",
        "enterprise_monthly": "plan_enterprise",
        "enterprise_annual": "plan_enterprise",
    }

    role_code = plan_role_map.get(plan_sku)
    if not role_code:
        return

    role = Role.objects.get(code=role_code)

    # Expire any existing plan roles
    UserRole.objects.filter(
        user=user,
        role__code__startswith="plan_",
        valid_to__isnull=True,
    ).update(valid_to=timezone.now())

    # Assign new role
    UserRole.objects.create(
        user=user,
        role=role,
        valid_from=timezone.now(),
    )
```

### Checking Feature Access

```python
def user_can_access_feature(user, permission_code):
    """Check if user has access to a feature."""
    return UserRole.objects.filter(
        user=user,
        role__permissions__code=permission_code,
    ).current().exists()

# Usage
if user_can_access_feature(user, "api_access"):
    # Allow API call
    pass
else:
    raise PermissionDenied("API access requires Professional plan or higher")
```

---

## Plan Changes

Customers upgrade, downgrade, and cancel. Each change is a new agreement version.

### Upgrade

```python
def upgrade_subscription(subscription, new_plan_sku, prorate=True):
    """Upgrade a subscription to a higher plan."""
    old_plan = CatalogItem.objects.get(sku=subscription.metadata["plan_sku"])
    new_plan = CatalogItem.objects.get(sku=new_plan_sku)

    now = timezone.now()

    if prorate:
        # Calculate proration credit for unused time
        days_in_period = 30  # Simplified
        days_remaining = calculate_days_remaining(subscription)
        daily_rate = old_plan.unit_price / days_in_period
        credit_amount = daily_rate * days_remaining

        # Calculate prorated charge for new plan
        new_daily_rate = new_plan.unit_price / days_in_period
        charge_amount = new_daily_rate * days_remaining

        # Net difference
        proration = charge_amount - credit_amount

        # Create proration invoice
        if proration > 0:
            create_proration_invoice(
                subscription=subscription,
                amount=proration,
                description=f"Upgrade proration: {old_plan.name} to {new_plan.name}",
            )

    # End current subscription
    subscription.valid_to = now
    subscription.status = "upgraded"
    subscription.save()

    # Create new subscription
    new_subscription = Agreement.objects.create(
        agreement_type="subscription",
        status="active",
        valid_from=now,
        valid_to=None,
        metadata={
            "plan_sku": new_plan_sku,
            "price_at_signup": str(new_plan.unit_price),
            "currency": subscription.metadata["currency"],
            "billing_day": subscription.metadata["billing_day"],
            "payment_method_id": subscription.metadata["payment_method_id"],
            "upgraded_from": str(subscription.id),
        }
    )

    # Copy party relationships
    for party in subscription.agreementparty_set.all():
        AgreementParty.objects.create(
            agreement=new_subscription,
            party=party.party,
            role=party.role,
        )

    # Log the upgrade
    log_event(
        target=subscription,
        event_type="subscription_upgraded",
        metadata={
            "old_plan": old_plan.sku,
            "new_plan": new_plan.sku,
            "new_subscription_id": str(new_subscription.id),
            "proration_amount": str(proration) if prorate else "0",
        }
    )

    # Sync RBAC roles
    subscriber = subscription.agreementparty_set.filter(role="subscriber").first()
    if subscriber:
        sync_subscription_role(new_subscription, subscriber.party)

    return new_subscription
```

### Downgrade

```python
def schedule_downgrade(subscription, new_plan_sku):
    """Schedule a downgrade for end of billing period."""
    # Don't apply immediately - wait until period ends
    subscription.metadata["scheduled_plan_change"] = {
        "new_plan_sku": new_plan_sku,
        "effective_date": calculate_next_billing_date(subscription).isoformat(),
        "reason": "customer_requested_downgrade",
    }
    subscription.save()

    log_event(
        target=subscription,
        event_type="downgrade_scheduled",
        metadata=subscription.metadata["scheduled_plan_change"],
    )
```

### Cancellation

```python
def cancel_subscription(subscription, reason, immediate=False):
    """Cancel a subscription."""
    now = timezone.now()

    if immediate:
        # Cancel immediately
        subscription.valid_to = now
        subscription.status = "cancelled"
    else:
        # Cancel at end of billing period
        subscription.metadata["scheduled_cancellation"] = {
            "effective_date": calculate_next_billing_date(subscription).isoformat(),
            "reason": reason,
        }
        subscription.status = "pending_cancellation"

    subscription.save()

    log_event(
        target=subscription,
        event_type="subscription_cancelled",
        metadata={
            "reason": reason,
            "immediate": immediate,
            "effective_date": subscription.valid_to.isoformat() if immediate else subscription.metadata["scheduled_cancellation"]["effective_date"],
        }
    )

    # Expire RBAC roles if immediate
    if immediate:
        subscriber = subscription.agreementparty_set.filter(role="subscriber").first()
        if subscriber:
            UserRole.objects.filter(
                user=subscriber.party,
                role__code__startswith="plan_",
                valid_to__isnull=True,
            ).update(valid_to=now)
```

### Reactivation

```python
def reactivate_subscription(old_subscription, plan_sku=None):
    """Reactivate a cancelled subscription."""
    if not plan_sku:
        plan_sku = old_subscription.metadata["plan_sku"]

    now = timezone.now()

    new_subscription = Agreement.objects.create(
        agreement_type="subscription",
        status="active",
        valid_from=now,
        valid_to=None,
        metadata={
            "plan_sku": plan_sku,
            "price_at_signup": CatalogItem.objects.get(sku=plan_sku).unit_price,
            "currency": old_subscription.metadata["currency"],
            "billing_day": now.day,  # New billing day
            "payment_method_id": old_subscription.metadata["payment_method_id"],
            "reactivated_from": str(old_subscription.id),
        }
    )

    # Copy parties
    for party in old_subscription.agreementparty_set.all():
        AgreementParty.objects.create(
            agreement=new_subscription,
            party=party.party,
            role=party.role,
        )

    log_event(
        target=old_subscription,
        event_type="subscription_reactivated",
        metadata={
            "new_subscription_id": str(new_subscription.id),
        }
    )

    return new_subscription
```

---

## Subscription History

Because subscriptions are agreements with time bounds, you can query the complete history.

### Subscription Timeline

```python
def get_subscription_history(customer):
    """Get complete subscription history for a customer."""
    return Agreement.objects.filter(
        agreement_type="subscription",
        agreementparty__party=customer,
        agreementparty__role="subscriber",
    ).order_by("valid_from")

# Usage
history = get_subscription_history(company)
for sub in history:
    print(f"{sub.valid_from} - {sub.valid_to or 'Current'}: {sub.metadata['plan_sku']} ({sub.status})")
```

### MRR Calculation

```python
def calculate_mrr(as_of=None):
    """Calculate Monthly Recurring Revenue."""
    if as_of is None:
        as_of = timezone.now()

    active_subs = Agreement.objects.filter(
        agreement_type="subscription",
        status="active",
    ).as_of(as_of)

    mrr = Decimal("0")
    for sub in active_subs:
        plan = CatalogItem.objects.get(sku=sub.metadata["plan_sku"])
        interval = plan.metadata.get("billing_interval", "month")

        if interval == "month":
            mrr += plan.unit_price
        elif interval == "year":
            mrr += plan.unit_price / 12  # Convert to monthly

    return mrr

# Historical MRR
for month in range(1, 13):
    date = datetime(2024, month, 1, tzinfo=timezone.utc)
    mrr = calculate_mrr(as_of=date)
    print(f"{date.strftime('%B %Y')}: ${mrr:,.2f} MRR")
```

### Churn Analysis

```python
def calculate_churn_rate(period_start, period_end):
    """Calculate churn rate for a period."""
    # Subscriptions active at start
    subs_at_start = Agreement.objects.filter(
        agreement_type="subscription",
        status="active",
    ).as_of(period_start).count()

    # Subscriptions that churned during period
    churned = Agreement.objects.filter(
        agreement_type="subscription",
        status__in=["cancelled", "expired"],
        valid_to__gte=period_start,
        valid_to__lt=period_end,
    ).count()

    if subs_at_start == 0:
        return Decimal("0")

    return (Decimal(churned) / Decimal(subs_at_start)) * 100
```

---

## Complete Rebuild Prompt

```markdown
# Prompt: Rebuild Subscription Service

## Instruction

Build a SaaS subscription management service by composing these primitives:
- django-parties (customers, organizations, team members)
- django-catalog (plans, pricing)
- django-agreements (subscriptions)
- django-ledger (invoices, payments)
- django-audit-log (usage tracking)
- django-rbac (feature access)

## Domain Purpose

Enable SaaS businesses to:
- Manage customers (individuals and organizations)
- Define subscription plans with features and limits
- Handle subscription lifecycle (trial, active, cancelled)
- Bill customers on recurring schedules
- Track usage for usage-based pricing
- Control feature access based on plan

## NO NEW MODELS

Do not create any new Django models. All subscription functionality
is implemented by composing existing primitives.

## Primitive Composition

### Customers
- Person = Individual customer
- Organization = Company account
- PartyRelationship = Team member with role (owner, admin, member, billing)

### Plans
- Category = Plan tier (Starter, Pro, Enterprise)
- CatalogItem = Specific plan with price and features
  - metadata.billing_interval: "month" or "year"
  - metadata.features: list of feature codes
  - metadata.limits: dict of usage limits

### Subscriptions
- Agreement (agreement_type="subscription")
  - status: "trialing", "active", "pending_cancellation", "cancelled"
  - valid_from: subscription start
  - valid_to: subscription end (null = ongoing)
  - metadata.plan_sku: reference to CatalogItem
  - metadata.billing_day: day of month to bill
  - metadata.payment_method_id: stored payment method
- AgreementParty = links customer to subscription

### Billing
- Transaction (transaction_type="invoice") = invoice
  - entries: debit receivables, credit revenue
  - metadata.billing_period_start/end
  - metadata.subscription_id
- Transaction (transaction_type="payment") = payment
  - entries: debit cash, credit receivables
  - metadata.invoice_id

### Usage Tracking
- AuditLog (event_type="api_call") = API usage
- AuditLog (event_type="storage_snapshot") = storage usage
- Query with .for_target(subscription)

### Feature Access
- Permission = feature capability
- Role = plan-based role (plan_starter, plan_pro, plan_enterprise)
- UserRole = assigns plan role to user

## Service Functions

### subscribe_customer()
```python
def subscribe_customer(
    customer: Party,
    plan_sku: str,
    payment_method_id: str,
    trial_days: int = 0,
) -> Agreement:
    """Create a new subscription for a customer."""
```

### upgrade_subscription()
```python
def upgrade_subscription(
    subscription: Agreement,
    new_plan_sku: str,
    prorate: bool = True,
) -> Agreement:
    """Upgrade to a higher plan with optional proration."""
```

### cancel_subscription()
```python
def cancel_subscription(
    subscription: Agreement,
    reason: str,
    immediate: bool = False,
) -> Agreement:
    """Cancel a subscription immediately or at period end."""
```

### run_billing()
```python
def run_billing(billing_date: date) -> list[dict]:
    """Run billing for all subscriptions due on this date."""
```

### record_usage()
```python
def record_usage(
    subscription: Agreement,
    event_type: str,
    metadata: dict,
) -> AuditLog:
    """Record a usage event for a subscription."""
```

### get_usage_for_period()
```python
def get_usage_for_period(
    subscription: Agreement,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Get usage metrics for a billing period."""
```

### sync_subscription_role()
```python
def sync_subscription_role(
    subscription: Agreement,
    user: User,
) -> UserRole:
    """Sync user's RBAC role based on subscription plan."""
```

## Test Cases (42 tests)

### Customer Tests (6 tests)
1. test_create_individual_customer
2. test_create_organization_customer
3. test_add_team_member
4. test_team_member_roles
5. test_team_at_point_in_time
6. test_organization_hierarchy

### Plan Tests (8 tests)
7. test_create_plan_tiers
8. test_create_monthly_plan
9. test_create_annual_plan
10. test_plan_with_features
11. test_plan_with_limits
12. test_usage_addon_plan
13. test_plan_price_snapshot
14. test_plan_comparison

### Subscription Tests (12 tests)
15. test_create_subscription
16. test_subscription_with_trial
17. test_subscription_active_query
18. test_subscription_as_of_query
19. test_upgrade_subscription
20. test_upgrade_with_proration
21. test_downgrade_scheduled
22. test_cancel_immediate
23. test_cancel_at_period_end
24. test_reactivate_subscription
25. test_subscription_history
26. test_multiple_subscriptions_same_customer

### Billing Tests (10 tests)
27. test_create_invoice
28. test_invoice_immutable
29. test_record_payment
30. test_billing_run_monthly
31. test_billing_run_annual
32. test_proration_calculation
33. test_usage_overage_charges
34. test_invoice_with_overage
35. test_failed_payment_handling
36. test_mrr_calculation

### Feature Access Tests (6 tests)
37. test_plan_role_permissions
38. test_sync_role_on_subscribe
39. test_sync_role_on_upgrade
40. test_expire_role_on_cancel
41. test_feature_access_check
42. test_feature_access_denied

## Key Behaviors

1. **Subscriptions are Agreements** - same primitives as contracts
2. **Invoices are immutable Transactions** - cannot be modified after posting
3. **Usage is AuditLog events** - query with temporal filters
4. **Feature access via RBAC** - roles synced to subscription plan
5. **Plan changes create new Agreements** - history preserved
6. **Billing is ledger Transactions** - double-entry accounting

## Acceptance Criteria

- [ ] No new Django models created
- [ ] Subscriptions use Agreement with proper party relationships
- [ ] Invoices use immutable Transactions
- [ ] Usage tracked via AuditLog events
- [ ] Feature access controlled by RBAC
- [ ] Plan changes preserve history
- [ ] Proration calculated correctly
- [ ] MRR calculable at any point in time
- [ ] All 42 tests passing
- [ ] README with integration examples
```

---

## Hands-On Exercise: Build Subscription Analytics

Add analytics to your subscription service.

**Step 1: Cohort Retention**

```python
def cohort_retention(signup_month: date) -> dict:
    """Calculate retention by signup cohort."""
    cohort_start = signup_month.replace(day=1)
    cohort_end = (cohort_start + relativedelta(months=1))

    # Subscriptions started in this cohort
    cohort = Agreement.objects.filter(
        agreement_type="subscription",
        valid_from__gte=cohort_start,
        valid_from__lt=cohort_end,
    )

    cohort_size = cohort.count()
    retention = {}

    # Check retention for each month
    for months_later in range(0, 12):
        check_date = cohort_start + relativedelta(months=months_later)
        still_active = cohort.filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=check_date)
        ).count()

        retention[f"month_{months_later}"] = {
            "active": still_active,
            "rate": (still_active / cohort_size * 100) if cohort_size > 0 else 0,
        }

    return {
        "cohort": cohort_start.isoformat(),
        "cohort_size": cohort_size,
        "retention": retention,
    }
```

**Step 2: Revenue by Plan**

```python
def revenue_by_plan(period_start: date, period_end: date) -> dict:
    """Calculate revenue breakdown by plan."""
    invoices = Transaction.objects.filter(
        transaction_type="invoice",
        effective_at__gte=period_start,
        effective_at__lt=period_end,
        status="posted",
    )

    by_plan = {}
    for invoice in invoices:
        plan_sku = invoice.metadata.get("plan_sku", "unknown")
        amount = invoice.entries.filter(entry_type="credit").aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        if plan_sku not in by_plan:
            by_plan[plan_sku] = Decimal("0")
        by_plan[plan_sku] += amount

    return by_plan
```

**Step 3: Customer Lifetime Value**

```python
def calculate_ltv(customer: Party) -> Decimal:
    """Calculate lifetime value for a customer."""
    # All invoices paid by this customer
    subscriptions = Agreement.objects.filter(
        agreement_type="subscription",
        agreementparty__party=customer,
        agreementparty__role="subscriber",
    )

    total_revenue = Decimal("0")
    for sub in subscriptions:
        invoices = Transaction.objects.filter(
            transaction_type="invoice",
            metadata__subscription_id=str(sub.id),
            status="posted",
        )

        for invoice in invoices:
            paid = Transaction.objects.filter(
                transaction_type="payment",
                metadata__invoice_id=str(invoice.id),
                status="posted",
            ).exists()

            if paid:
                amount = invoice.entries.filter(entry_type="credit").aggregate(
                    total=Sum("amount")
                )["total"] or Decimal("0")
                total_revenue += amount

    return total_revenue
```

---

## What AI Gets Wrong About Subscriptions

### Storing Current Plan on Customer

AI may want to add a `current_plan` field to the customer:

```python
# WRONG
class Customer(models.Model):
    current_plan = models.ForeignKey(Plan, ...)
    subscription_status = models.CharField(...)
```

**Why it's wrong:** Loses history. Can't answer "what plan were they on in March?"

**Solution:** The subscription Agreement IS the plan relationship. Query with `.current()` or `.as_of()`.

### Mutable Invoices

AI may allow invoice modifications:

```python
# WRONG
invoice.amount = new_amount
invoice.save()
```

**Why it's wrong:** Destroys audit trail. Financial records must be immutable.

**Solution:** Use ledger Transactions with posting. Post reversals for corrections.

### Checking Features at Request Time

AI may check plan features directly:

```python
# WRONG
if subscription.plan.has_feature("api_access"):
    allow_api_call()
```

**Why it's wrong:** Tightly couples code to subscription model. Hard to test.

**Solution:** Use RBAC. Check `user_can_access_feature(user, "api_access")`. Sync roles on subscription changes.

### Inline Usage Calculations

AI may calculate usage inline during requests:

```python
# WRONG (slow, blocking)
def handle_api_request(request):
    usage = count_api_calls_this_month(subscription)  # DB query
    if usage > limit:
        return HttpResponseForbidden()
```

**Why it's wrong:** Slow. Every API call queries the database.

**Solution:** Cache usage counts. Update async. Check against cached limit.

---

## Why This Matters

The founder from the opening story rebuilt her subscription system with:

1. **Agreements for subscriptions** - complete history of plan changes
2. **Ledger for billing** - immutable invoices, proper accounting
3. **Audit log for usage** - queryable usage at any point in time
4. **RBAC for features** - decoupled access control

When customers asked "Why was I charged $127.43?", she could show:
- Base plan: $99.00
- API overage (2,743 calls over limit): $27.43
- Storage: included
- Total: $127.43

When they asked "What plan was I on when that happened?", she could query:

```python
subscription_at_incident = Agreement.objects.filter(
    agreement_type="subscription",
    agreementparty__party=customer,
).as_of(incident_date).first()
```

No guessing. No "I think it was." Just facts.

---

## Summary

| Domain Concept | Primitive | Key Insight |
|----------------|-----------|-------------|
| Subscription | Agreement | Time-bounded relationship, not a status field |
| Plan | CatalogItem | Features and limits in metadata |
| Invoice | Transaction | Immutable ledger entry |
| Usage | AuditLog | Queryable events with temporal filters |
| Feature access | RBAC | Roles synced to subscription plan |
| Plan change | New Agreement | History preserved, not overwritten |

Subscriptions are agreements. Billing is ledger transactions. Usage is audit events. Feature access is RBAC.

Same primitives. Recurring revenue domain.

---

## Sources

- Recurly. (2023). *State of Subscriptions Report*. https://recurly.com/research/state-of-subscriptions/
- Zuora. (2023). *Subscription Economy Index*. https://www.zuora.com/sei/
