# Chapter 18: Build a Subscription Service

> Same primitives. Recurring revenue domain.

## The Domain

A SaaS subscription service needs:

- Customers and accounts
- Plans and pricing
- Subscriptions
- Recurring billing
- Usage tracking
- Invoices

## Primitive Mapping

| Domain Concept | Primitive | Package |
|----------------|-----------|---------|
| Customer | Party (Person) | django-parties |
| Company account | Party (Organization) | django-parties |
| Team member | PartyRelationship | django-parties |
| Plan | CatalogItem | django-catalog |
| Subscription | Agreement | django-agreements |
| Billing cycle | Agreement terms | django-agreements |
| Invoice | Transaction | django-ledger |
| Payment | Entry | django-ledger |
| Usage event | AuditLog (custom event) | django-audit-log |
| Feature access | Role + Permission | django-rbac |

## Subscriptions Are Agreements

A subscription is just an agreement with time bounds:

```python
Agreement.objects.create(
    agreement_type="subscription",
    parties=[customer, provider],
    terms={
        "plan_id": "pro_monthly",
        "price_cents": 4999,
        "billing_cycle": "monthly",
        "features": ["unlimited_users", "api_access", "priority_support"],
    },
    valid_from=now(),
    valid_to=None,  # Until cancelled
)
```

## Billing Is Ledger Transactions

Monthly billing:

```python
# Find active subscriptions due for billing
due_subscriptions = Agreement.objects.filter(
    agreement_type="subscription",
    valid_to__isnull=True,
    terms__billing_cycle="monthly",
).as_of(now())

for subscription in due_subscriptions:
    Transaction.objects.create(
        entries=[
            Entry(account=accounts_receivable, amount=4999, entry_type="debit"),
            Entry(account=subscription_revenue, amount=4999, entry_type="credit"),
        ],
        metadata={"subscription_id": str(subscription.id)}
    )
```

## Usage Tracking Is Audit Events

```python
log_event(
    target=subscription,
    event_type="api_call",
    metadata={"endpoint": "/v1/data", "response_time_ms": 42}
)

# Query usage
usage = AuditLog.objects.for_target(subscription).filter(
    event_type="api_call",
    created_at__gte=billing_period_start
).count()
```

## The Pattern

Subscriptions = Agreements + Ledger + Audit. No new primitives.

---

*Status: Planned*
