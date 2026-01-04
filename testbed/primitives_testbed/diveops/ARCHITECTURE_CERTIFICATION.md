# Certification Modeling Architecture

## Overview

This document describes the normalized certification model design for diveops, replacing free-form string fields with proper relational models.

## Current State (Problems)

```python
# DiverProfile - free-form certification fields
certification_level = CharField(choices=CERTIFICATION_LEVELS)  # "ow", "aow", etc.
certification_agency = CharField(max_length=50)  # Free text: "PADI", "padi", "P.A.D.I."
certification_number = CharField(max_length=100)
certification_date = DateField()

# DiveSite - string-based requirement
min_certification_level = CharField(choices=CERTIFICATION_LEVELS)
```

**Issues:**
1. No data normalization for agencies (duplicates, typos)
2. Single certification per diver (real divers have multiple)
3. No proof/document attachment capability
4. No expiration tracking for certifications
5. Level hierarchy hardcoded in Python dict

---

## Proposed Model Structure

### CertificationLevel (Reference Data)
```
┌─────────────────────────────────────────┐
│ CertificationLevel                      │
├─────────────────────────────────────────┤
│ id: UUID (pk)                           │
│ code: CharField (unique, e.g., "ow")    │
│ name: CharField ("Open Water Diver")    │
│ rank: PositiveIntegerField              │
│ description: TextField                  │
│ is_active: BooleanField                 │
│ created_at, updated_at, deleted_at      │
└─────────────────────────────────────────┘
```
- **rank** enables comparison: `level.rank >= required_level.rank`
- Replaces CERTIFICATION_LEVELS choices and LEVEL_HIERARCHY dict

### CertificationAgency (uses django_parties.Organization)
```
┌─────────────────────────────────────────┐
│ Organization (from django_parties)      │
├─────────────────────────────────────────┤
│ id: UUID (pk)                           │
│ name: "PADI", "SSI", "NAUI"             │
│ org_type: "certification_agency"        │
│ website: URLField (optional)            │
└─────────────────────────────────────────┘
```
- Reuse existing primitive instead of creating new model
- Add `org_type = "certification_agency"` choice if needed

### DiverCertification (Join Table)
```
┌─────────────────────────────────────────┐
│ DiverCertification                      │
├─────────────────────────────────────────┤
│ id: UUID (pk)                           │
│ diver: FK → DiverProfile                │
│ level: FK → CertificationLevel          │
│ agency: FK → Organization               │
│ certification_number: CharField         │
│ certified_on: DateField                 │
│ expires_on: DateField (nullable)        │
│ is_verified: BooleanField               │
│ verified_by: FK → User (nullable)       │
│ verified_at: DateTimeField (nullable)   │
│ created_at, updated_at, deleted_at      │
└─────────────────────────────────────────┘
```
- One diver can have multiple certifications
- Supports expiration tracking
- Supports verification workflow
- Can attach proof via django_documents.Document

### TripRequirement
```
┌─────────────────────────────────────────┐
│ TripRequirement                         │
├─────────────────────────────────────────┤
│ id: UUID (pk)                           │
│ trip: FK → DiveTrip                     │
│ requirement_type: CharField             │
│   ("certification", "medical", "gear")  │
│ certification_level: FK (nullable)      │
│ description: TextField                  │
│ is_mandatory: BooleanField              │
│ created_at, updated_at, deleted_at      │
└─────────────────────────────────────────┘
```
- Trip-level requirements (not just site default)
- Supports multiple requirement types
- Can add requirements beyond certification

---

## Relationships Diagram

```
Organization (agency)
       │
       │ FK
       ▼
DiverCertification ◄──────── Document (proof)
       │                     (via GenericFK)
       │ FK
       ▼
DiverProfile ◄──────────────── Booking ──────────────► DiveTrip
       │                                                   │
       │                                                   │ FK
       │                                                   ▼
       │                                            TripRequirement
       │                                                   │
       │                                                   │ FK
       ▼                                                   ▼
CertificationLevel ◄───────────────────────────────────────┘
```

---

## Constraint Strategy

### Postgres-Enforced (Database Level)

| Constraint | Model | Type | Purpose |
|------------|-------|------|---------|
| Unique level code | CertificationLevel | UniqueConstraint | No duplicate codes |
| Unique diver+level+agency | DiverCertification | UniqueConstraint | One cert per combo |
| Rank ordering | CertificationLevel | CheckConstraint | rank > 0 |
| Certified date <= today | DiverCertification | CheckConstraint | No future certs |
| Expires > certified | DiverCertification | CheckConstraint | Logical dates |

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["diver", "level", "agency"],
            condition=Q(deleted_at__isnull=True),
            name="unique_active_certification"
        ),
        models.CheckConstraint(
            check=Q(expires_on__isnull=True) | Q(expires_on__gt=F("certified_on")),
            name="expires_after_certified"
        ),
    ]
```

### Service/Decisioning Layer (Python Level)

| Check | Location | Reason |
|-------|----------|--------|
| Diver meets trip requirements | decisioning.py | Complex business logic |
| Certification is current (not expired) | decisioning.py | Date math with timezone |
| Medical clearance valid | decisioning.py | Cross-model check |
| Booking capacity | decisioning.py | Aggregation query |

---

## Integration Points with Primitives

### django_parties
- **Organization**: Used for certification agencies
- Add `org_type="certification_agency"` to choices if not present
- No adapter needed, direct FK relationship

### django_documents
- **Document**: Attach proof to DiverCertification via GenericForeignKey
- DiverCertification becomes a valid target for documents
- Query: `Document.objects.filter(target=certification)`

### django_basemodels
- **BaseModel**: All new models inherit UUID, timestamps, soft delete
- Use `objects` manager (excludes deleted) by default
- Use `all_objects` when need to include deleted records

### django_audit_log (future)
- Log certification verification actions
- Log requirement changes on trips

---

## Migration Path

### Phase 1: Add New Models (Non-Breaking)
1. Create CertificationLevel with seed data matching current choices
2. Create DiverCertification model
3. Create TripRequirement model
4. **Keep existing fields on DiverProfile and DiveSite**

### Phase 2: Data Migration
1. Create CertificationLevel records from CERTIFICATION_LEVELS
2. Migrate existing certifications to DiverCertification
3. Migrate DiveSite.min_certification_level to TripRequirement

### Phase 3: Update Decisioning
1. Update `can_diver_join_trip()` to use TripRequirement
2. Update `meets_certification_level()` to use DiverCertification
3. Return structured `required_actions` with level details

### Phase 4: Remove Old Fields
1. Remove deprecated fields from DiverProfile
2. Remove min_certification_level from DiveSite
3. Remove CERTIFICATION_LEVELS and LEVEL_HIERARCHY

---

## Selector Queries (N+1 Prevention)

```python
# Get diver with all certifications
def get_diver_with_certifications(diver_id: UUID) -> DiverProfile | None:
    return DiverProfile.objects.prefetch_related(
        Prefetch(
            "certifications",
            queryset=DiverCertification.objects.select_related("level", "agency")
        )
    ).get(pk=diver_id)

# Get trip with requirements
def get_trip_with_requirements(trip_id: UUID) -> DiveTrip | None:
    return DiveTrip.objects.prefetch_related(
        Prefetch(
            "requirements",
            queryset=TripRequirement.objects.select_related("certification_level")
        )
    ).select_related("dive_site").get(pk=trip_id)
```

---

## Summary

| Component | Action |
|-----------|--------|
| CertificationLevel | New model (reference data) |
| DiverCertification | New model (join table) |
| TripRequirement | New model |
| Organization | Reuse from django_parties |
| Document | Reuse from django_documents |
| DiverProfile.certification_* | Deprecated → remove in Phase 4 |
| DiveSite.min_certification_level | Deprecated → remove in Phase 4 |
| decisioning.can_diver_join_trip | Update to use new models |
