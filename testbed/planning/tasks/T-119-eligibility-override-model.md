# T-119: EligibilityOverride Model + Services

**Status**: PLACEHOLDER (not started)
**Depends on**: T-001 (Price Immutability) - COMPLETE
**Priority**: Medium

---

## Objective

Implement INV-1: Booking-scoped eligibility override model and service layer.

## Scope

### Model: EligibilityOverride

```python
class EligibilityOverride(BaseModel):
    """INV-1: Booking-scoped eligibility override.

    Allows staff to override eligibility checks for a SPECIFIC booking.
    NOT a global override for a diver or excursion.
    """
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    reason = models.TextField()
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT)
    approved_at = models.DateTimeField(default=timezone.now)
    bypassed_checks = models.JSONField(default=list, blank=True)
```

### Service Functions

- `book_excursion(..., override_eligibility=True, override_reason=str, override_by=User)`
- Creates EligibilityOverride record when override is used
- Emits audit event for override

### Migration

- New migration `0008_eligibility_override.py` (after T-001's 0007)
- Create EligibilityOverride table

## Hard Rules (INV-1)

- OneToOne relationship to Booking (not Excursion or Trip)
- Must have approved_by and reason
- Override is ONLY created via book_excursion() with override=True
- Override does NOT bypass can_diver_join_trip() checks (layered eligibility)

## Test Cases

- test_override_creates_eligibility_override_record
- test_override_requires_reason
- test_override_requires_approver
- test_override_emits_audit_event
- test_override_is_booking_scoped_not_global

## Definition of Done

- [ ] EligibilityOverride model created
- [ ] Migration created and applied
- [ ] book_excursion() updated to handle override
- [ ] Audit events emitted
- [ ] Tests written and passing (>95% coverage)
- [ ] No scope creep into other invariants
