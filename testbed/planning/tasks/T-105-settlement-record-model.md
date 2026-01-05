# T-105: SettlementRecord Model + Services

**Status**: PLACEHOLDER (not started)
**Depends on**: T-001 (Price Immutability) - COMPLETE
**Priority**: Medium

---

## Objective

Implement INV-4: Idempotent settlement record model and service layer with ledger integration.

## Scope

### Model: SettlementRecord

```python
class SettlementRecord(BaseModel):
    """INV-4: Idempotent settlement record for booking payments.

    Tracks payments/settlements for bookings with ledger integration.
    The idempotency_key ensures duplicate settlements are rejected.
    """
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    transaction = models.ForeignKey(
        "django_ledger.Transaction",
        on_delete=models.PROTECT,
        null=True, blank=True,
    )
    settled_by = models.ForeignKey(User, on_delete=models.PROTECT)
    settled_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    method = models.CharField(max_length=50, blank=True)
```

### Service Functions

```python
@idempotent(key_param="idempotency_key")
def settle_booking(
    booking: Booking,
    amount: Decimal,
    *,
    idempotency_key: str,
    settled_by: User,
    method: str = "",
    notes: str = "",
) -> SettlementRecord:
    """Create settlement record and post to ledger."""
```

### Migration

- New migration `0009_settlement_record.py` (after T-119's 0008)
- Create SettlementRecord table with unique constraint on idempotency_key
- Add indexes on booking and settled_at

## Hard Rules (INV-4)

- idempotency_key is unique (prevents duplicate settlements)
- transaction FK links to posted ledger entry (immutable)
- amount/currency are the settled values
- Ledger entries are immutable (reversals, not edits)

## Test Cases

- test_settle_booking_creates_settlement_record
- test_settle_booking_is_idempotent
- test_settle_booking_rejects_duplicate_key
- test_settle_booking_posts_to_ledger
- test_settle_booking_emits_audit_event
- test_ledger_entry_is_immutable

## Definition of Done

- [ ] SettlementRecord model created
- [ ] Migration created and applied
- [ ] settle_booking() service implemented
- [ ] @idempotent decorator working
- [ ] Ledger integration implemented
- [ ] Audit events emitted
- [ ] Tests written and passing (>95% coverage)
- [ ] No scope creep into other invariants
