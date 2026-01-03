# Architecture: invoicing

**Status:** Alpha / Testbed Module

## Design Intent

- **Immutable**: Invoice line items snapshot prices at creation time; values never drift
- **Auditable**: Full trail from basket → priced items → invoice → ledger entries
- **Atomic**: All invoice creation and state transitions wrapped in `@transaction.atomic`
- **Constrained**: PostgreSQL CHECK constraints enforce data integrity at the database level

## What This Provides

| Component | Purpose |
|-----------|---------|
| `Invoice` | Financial document with totals, linked to basket/encounter/ledger |
| `InvoiceLineItem` | Snapshotted line item with quantity, price, and audit trail |
| `InvoiceContext` | Immutable value object with extracted billing context |
| `PricedLine` | Value object for a priced basket item ready for invoicing |
| `PricedBasket` | Value object containing all priced lines and subtotal |
| `create_invoice_from_basket()` | Main entry point: basket → invoice with line items |
| `issue_invoice()` | Transition draft to issued, recording ledger entry |
| `record_payment()` | Record payment against invoice with ledger entry |
| `price_basket()` | Price all basket items using price resolution |
| `extract_invoice_context()` | Extract patient, org, agreement from basket's encounter |

## What This Does NOT Do

- Void/refund workflow (not implemented)
- Partial payment tracking (single full payment only)
- Status transition validation (no explicit state machine)
- Credit memos or adjustments
- Multi-currency invoices (single currency enforced)
- Invoice editing after creation (immutable by design)

## Hard Rules

1. **Basket must be committed** before invoicing
2. **Single currency** per invoice (MixedCurrencyError if violated)
3. **Line items snapshot prices** at creation time; never recalculated
4. **Quantity must be > 0** (PostgreSQL CHECK constraint)
5. **Line total must equal quantity * unit_price** (PostgreSQL CHECK constraint)
6. **Invoice totals are non-negative** (PostgreSQL CHECK constraint)
7. **Invoice numbers are atomic** via `django-sequence` with `select_for_update()`

## Invariants

| Invariant | Enforcement |
|-----------|-------------|
| `line_total = quantity * unit_price` | PostgreSQL CHECK constraint |
| `quantity > 0` | PostgreSQL CHECK constraint |
| `subtotal >= 0` | PostgreSQL CHECK constraint |
| `total >= 0` | PostgreSQL CHECK constraint |
| `total = subtotal + tax` | Calculated at creation, immutable |
| One invoice per basket | `OneToOneField` with PROTECT |
| One ledger transaction per invoice | `OneToOneField` with PROTECT |

## Status Workflow

```
    ┌─────────┐
    │  draft  │
    └────┬────┘
         │ issue_invoice()
         │ (creates ledger entry)
         ▼
    ┌─────────┐
    │ issued  │
    └────┬────┘
         │ record_payment()
         │ (creates payment ledger entry)
         ▼
    ┌─────────┐
    │  paid   │
    └─────────┘

    Note: voided/cancelled states exist but
    transition logic is not yet implemented
```

## Data Flow

```
Patient check-in (Encounter)
         │
         ▼
Items added to Basket
         │
         ▼
Basket committed
         │
         ▼
extract_invoice_context(basket)
│   → InvoiceContext{patient, org, encounter, basket, agreement}
         │
         ▼
price_basket(basket, org, party, agreement)
│   → PricedBasket{lines: [PricedLine, ...], subtotal}
│   → Creates PricedBasketItem records
         │
         ▼
create_invoice_from_basket(basket, user)
│   → Invoice (status=draft)
│   → InvoiceLineItem × N (snapshotted prices)
│   → issue_invoice() if issue_immediately=True
         │
         ▼
issue_invoice(invoice)
│   → Creates ledger Transaction
│   │   Debit: Accounts Receivable
│   │   Credit: Revenue
│   → Invoice.status = 'issued'
         │
         ▼
record_payment(invoice, amount, method)
│   → Creates ledger Transaction
│   │   Debit: Cash
│   │   Credit: Accounts Receivable
│   → Invoice.status = 'paid' (if full payment)
```

## Ledger Integration

| Operation | Debit Account | Credit Account |
|-----------|--------------|----------------|
| Issue invoice | Accounts Receivable | Revenue |
| Record payment | Cash/Bank | Accounts Receivable |

Accounts are auto-created per organization via `get_or_create_account()`.

## Dependencies

| Package | Usage |
|---------|-------|
| `django-sequence` | Atomic invoice number generation |
| `django-ledger` | Double-entry transaction recording |
| `django-catalog` | Basket, BasketItem, CatalogItem |
| `django-encounters` | Encounter (invoice context) |
| `django-parties` | Organization, Person (billed_to, issued_by) |
| `django-agreements` | Optional pricing agreements |
| `django-money` | Money value object |
| `pricing` | Price resolution, PricedBasketItem |

## File Structure

```
invoicing/
├── models.py          # Invoice, InvoiceLineItem with constraints
├── services.py        # create_invoice_from_basket, issue_invoice, get_or_create_account
├── context.py         # InvoiceContext, extract_invoice_context
├── pricing.py         # PricedLine, PricedBasket, price_basket
├── payments.py        # record_payment
├── exceptions.py      # Error hierarchy
├── admin.py           # Django admin configuration
└── migrations/
    ├── 0001_initial.py
    └── 0002_add_line_item_constraints.py
```

## Exception Hierarchy

```
InvoicingError (base)
├── ContextExtractionError     # Failed to extract context
├── BasketNotCommittedError    # Basket not in committed status
├── PricingError               # Pricing failure
│   └── MixedCurrencyError     # Multiple currencies in basket
├── InvoiceStateError          # Invalid state transition
└── LedgerIntegrationError     # Ledger transaction failed
```

## Database Constraints

```sql
-- Line item quantity must be positive
CHECK (quantity > 0)
  NAME: invoicelineitem_quantity_positive

-- Line total must equal calculated value (prevents drift)
CHECK (line_total_amount = quantity * unit_price_amount)
  NAME: invoicelineitem_total_equals_qty_times_price

-- Invoice subtotal non-negative
CHECK (subtotal_amount >= 0)
  NAME: invoice_subtotal_non_negative

-- Invoice total non-negative
CHECK (total_amount >= 0)
  NAME: invoice_total_non_negative
```

## Foreign Key Behavior

| Relationship | on_delete | Rationale |
|--------------|-----------|-----------|
| Invoice → Basket | PROTECT | Cannot delete basket with invoice |
| Invoice → Encounter | PROTECT | Cannot delete encounter with invoices |
| Invoice → Person (billed_to) | PROTECT | Cannot delete patient with invoices |
| Invoice → Organization | PROTECT | Cannot delete org with invoices |
| Invoice → Agreement | SET_NULL | Agreements can be archived |
| Invoice → Transaction | PROTECT | Cannot delete ledger entry |
| Invoice → User (created_by) | PROTECT | Audit trail preserved |
| InvoiceLineItem → Invoice | CASCADE | Delete lines with invoice |
| InvoiceLineItem → PricedBasketItem | PROTECT | Cannot delete pricing record |

## Known Limitations

1. **No partial payment tracking**: Full payment only, no balance tracking
2. **No void/refund flow**: Status exists but logic not implemented
3. **No status transition validation**: Can set any status directly
4. **Agreement FK uses SET_NULL**: Consider PROTECT for stricter audit
5. **No idempotency keys**: Duplicate submissions not prevented at API level
6. **Admin has N+1 risk**: Needs `list_select_related` optimization

## Test Coverage

22 tests covering:
- Context extraction (4 tests)
- Basket pricing (3 tests)
- Invoice creation (4 tests)
- Ledger integration (4 tests)
- Payment flow (2 tests)
- Line item constraints (3 tests)
- Invoice number generation (2 tests)
