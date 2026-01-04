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
