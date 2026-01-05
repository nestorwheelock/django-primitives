# UI & Data Integrity Audit Prompt

Use this prompt to audit the DiveOps codebase for:
1. Missing user interfaces
2. **Existing UIs that bypass services and skip audit events** (the dangerous ones)
3. Permission gaps
4. State machine violations

---

## The Prompt

```
You are auditing a Django application for UI completeness AND data integrity.
This is not just "what screens are missing" - it's "what screens exist but are unsafe."

## Step 1: Model Inventory

Read all models and classify them:

| Model | User-Facing? | Has State Machine? | Touches Money? | CRUD Needed? |
|-------|--------------|-------------------|----------------|--------------|

Flag models that:
- Have status/state fields (need transition enforcement)
- Have price/amount fields (need audit trail)
- Have relationships to settlements/ledger (need service layer)

## Step 2: Existing UI Inventory

Scan all templates and views:

| Template/View | Purpose | Model(s) | Operations | HTTP Methods |
|---------------|---------|----------|------------|--------------|

For each view handling POST/PUT/DELETE, note the entry point for Step 2.5.

## Step 2.5: Mutation Path Audit (CRITICAL)

**For every form/view that creates, updates, or deletes data:**

Check compliance:

1. **Service Layer:** Does it call a service function, or does it do direct ORM?
   - VIOLATION: `model.save()`, `Model.objects.create()`, `queryset.update()`, `delete()` in views/forms
   - COMPLIANT: `services.create_booking()`, `services.cancel_booking()`, etc.

2. **Audit Emission:** Does the mutation emit an audit event?
   - Check for `log_action()`, `log_dive_action()`, or service that wraps audit
   - Missing audit on financial operations = P0

3. **Transaction Safety:** Is it wrapped in `transaction.atomic()`?

Output table:

| Entry Point | Model | Mutation Type | Uses Service? | Audit Emitted? | Atomic? | Severity | Fix Required |
|-------------|-------|---------------|---------------|----------------|---------|----------|--------------|

**Severity Classification:**
- P0: Touches money, eligibility, or deletes - MUST use service + audit
- P1: State transitions - SHOULD use service + audit
- P2: Other mutations - RECOMMENDED service layer

**Common Violations to Find:**

```python
# BAD - Direct ORM in view
def create_booking(request):
    booking = Booking.objects.create(
        diver=diver,
        excursion=excursion,
        price_snapshot=price  # Where did this come from?
    )
    # No audit event!
    return redirect(...)

# GOOD - Service layer
def create_booking(request):
    booking = booking_service.create_booking(
        diver=diver,
        excursion=excursion,
        created_by=request.user
    )
    # Service handles pricing, validation, audit
    return redirect(...)
```

## Step 3: CRUD Gap Analysis with Permissions

For each user-facing model:

| Model | List | Detail | Create | Edit | Delete | Search | Portal | Role Required | Object-Level? |
|-------|------|--------|--------|------|--------|--------|--------|---------------|---------------|

**Portal:** Staff / Customer / Both
**Role Required:** Admin / Manager / Instructor / DM / Any Staff / Customer
**Object-Level:** Does user only see/edit their own records?

Flag permission gaps:
- Staff can edit things they shouldn't (e.g., any staff editing settlements)
- Missing object-level filtering (customer sees all bookings, not just theirs)
- No role check on sensitive operations

## Step 4: Workflow & State Machine Audit

For each workflow, verify UI supports the **state transitions** and **stop gates**:

### Booking Flow
| Step | UI Exists? | Service Used? | Audit Event? | Stop Gate Enforced? |
|------|------------|---------------|--------------|---------------------|
| Browse available trips | | | | |
| Check eligibility | | | | Ineligible blocked? |
| Display price (snapshot) | | | | Price locked at book? |
| Capture waiver signature | | | | Can't book without? |
| Create booking | | | | |
| Process payment | | | | |
| Send confirmation | | | | |

### Check-In Flow
| Step | UI Exists? | Service Used? | Audit Event? | Stop Gate Enforced? |
|------|------------|---------------|--------------|---------------------|
| Find booking | | | | |
| Verify diver (cert, medical) | | | | Expired blocked? |
| Assign equipment | | | | |
| Mark checked in | | | | |
| Generate manifest | | | | |

### Cancellation Flow
| Step | UI Exists? | Service Used? | Audit Event? | Stop Gate Enforced? |
|------|------------|---------------|--------------|---------------------|
| Find booking | | | | |
| Calculate refund (policy) | | | | |
| Confirm cancellation | | | | |
| Create refund settlement | | | | |
| Update booking status | | | | |

### Trip Execution Flow
| Step | UI Exists? | Service Used? | Audit Event? | Stop Gate Enforced? |
|------|------------|---------------|--------------|---------------------|
| Start excursion | | | | All checked in? |
| Track dives | | | | |
| Complete excursion | | | | |
| Create revenue settlement | | | | |
| Mark bookings complete | | | | |

### Equipment Flow
| Step | UI Exists? | Service Used? | Audit Event? | Stop Gate Enforced? |
|------|------------|---------------|--------------|---------------------|
| Add to inventory | | | | |
| Assign to booking | | | | |
| Return from booking | | | | |
| Schedule service | | | | Overdue blocked? |
| Record service | | | | |
| Retire equipment | | | | |

## Step 5: Dashboard & Exception Reporting

### Operational Dashboards
- [ ] Today's trips overview
- [ ] Upcoming bookings
- [ ] Check-in status
- [ ] Equipment availability
- [ ] Staff schedule
- [ ] Revenue summary

### Data Integrity Reports (CRITICAL)
These catch when something went wrong:

- [ ] Bookings missing waiver signature
- [ ] Bookings missing price_snapshot
- [ ] Completed bookings with no revenue settlement
- [ ] Cancelled bookings with refund > 0 but no refund settlement
- [ ] Excursions completed but bookings still "checked_in" status
- [ ] Equipment assigned but never returned
- [ ] Audit events with missing actor
- [ ] State transitions that skipped steps

### Compliance Reports
- [ ] Park visitor reports (by period, visitor type)
- [ ] Certification expiration warnings
- [ ] Equipment service due dates
- [ ] Staff certification status

## Step 6: Priority Matrix

**P0 - Data Integrity Risk:**
- Mutations bypassing service layer
- Missing audit on financial operations
- Missing audit on eligibility decisions
- No transaction wrapping on multi-step operations

**P1 - Security/Permission Risk:**
- Missing role checks on sensitive operations
- Missing object-level permissions
- Customers can see/edit other customers' data

**P2 - Operational Gaps:**
- Missing CRUD for user-facing models
- Missing workflow steps
- No dashboard visibility

**P3 - Polish:**
- Missing search/filter
- Missing bulk operations
- UX improvements

## Step 7: Output Summary

### Executive Summary
- Total mutation entry points audited: X
- Entry points with service layer violations: X (list them)
- Entry points with missing audit: X (list them)
- P0 issues: X
- P1 issues: X

### Violations Table (P0/P1 First)
| Priority | Location | Issue | Risk | Fix |
|----------|----------|-------|------|-----|

### Missing UI Table
| Priority | Model/Feature | Missing UI | Effort |
|----------|---------------|------------|--------|

### Recommended Fix Order
1. [P0 violations first - these are bugs, not features]
2. [P1 violations]
3. [Missing UI by workflow importance]

### Data Integrity Queries to Run
SQL/ORM queries to find existing bad data:

```python
# Bookings without price snapshot
Booking.objects.filter(price_snapshot__isnull=True)

# Completed bookings without settlement
Booking.objects.filter(
    status='completed'
).exclude(
    id__in=Settlement.objects.filter(
        settlement_type='revenue'
    ).values('booking_id')
)

# Cancelled with refund but no refund settlement
Booking.objects.filter(
    status='cancelled',
    refund_amount__gt=0
).exclude(
    id__in=Settlement.objects.filter(
        settlement_type='refund'
    ).values('booking_id')
)
```
```

---

## Quick Grep Commands

Run these to find violations fast:

```bash
# Find direct .save() calls in views
grep -rn "\.save()" */views.py */staff_views.py */forms.py

# Find direct .create() calls in views
grep -rn "objects\.create(" */views.py */staff_views.py */forms.py

# Find direct .update() calls in views
grep -rn "\.update(" */views.py */staff_views.py */forms.py

# Find direct .delete() calls in views
grep -rn "\.delete(" */views.py */staff_views.py */forms.py

# Find audit log imports (should exist in services)
grep -rn "log_action\|log_dive_action" */services.py

# Find audit log imports in views (might be OK, might be inconsistent)
grep -rn "log_action\|log_dive_action" */views.py */staff_views.py

# Find transaction.atomic usage
grep -rn "transaction\.atomic" */services.py */views.py
```

---

## Focused Audit Commands

### Audit a Specific View File

```
Read [path/to/views.py] and for every function that handles POST:
1. What model does it mutate?
2. Does it use a service function or direct ORM?
3. Does it emit an audit event?
4. Is it wrapped in transaction.atomic?

Output violations only.
```

### Audit Service Layer Coverage

```
1. Read all models in diveops/models.py
2. Read all services in diveops/services.py
3. For each model with state/status field:
   - Is there a service function for each transition?
   - Does each transition emit audit?
4. Output: Models with missing service coverage
```

### Audit Form Submissions

```
1. Find all forms in diveops/forms.py
2. For each form with a save() method:
   - Does it override save()?
   - Does the override call a service or direct ORM?
   - Where is this form used (which views)?
3. Output: Forms that bypass service layer
```

---

## Red Flags Checklist

When reviewing code, these patterns indicate problems:

```python
# RED FLAG: Form.save() doing business logic
class BookingForm(forms.ModelForm):
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.price_snapshot = calculate_price(...)  # Business logic in form!
        instance.save()
        return instance

# RED FLAG: View doing direct ORM mutation
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    booking.status = 'cancelled'  # No service!
    booking.save()  # No audit!
    return redirect(...)

# RED FLAG: Missing transaction on multi-step
def complete_trip(request, pk):
    excursion = get_object_or_404(Excursion, pk=pk)
    excursion.status = 'completed'
    excursion.save()
    for booking in excursion.bookings.all():
        booking.status = 'completed'
        booking.save()
    # If this fails halfway, data is inconsistent!

# GREEN FLAG: Proper service usage
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    result = booking_service.cancel_booking(
        booking=booking,
        cancelled_by=request.user,
        reason=request.POST.get('reason')
    )
    # Service handles: validation, refund calc, audit, transaction
    return redirect(...)
```

---

## Integration with Task System

After audit, create tasks for violations:

**For P0 Service Layer Violations:**
```markdown
# T-XXX: Fix [View Name] Service Layer Bypass

## Problem
[view_name] in [file] performs direct ORM mutation without service layer.

## Current Code
[paste violation]

## Risk
- No audit trail for [operation]
- Business logic not centralized
- [specific risk]

## Fix
1. Create/use service function
2. Add audit event emission
3. Wrap in transaction.atomic
4. Update view to call service

## Test Cases
- test_[operation]_creates_audit_event
- test_[operation]_uses_transaction
```
