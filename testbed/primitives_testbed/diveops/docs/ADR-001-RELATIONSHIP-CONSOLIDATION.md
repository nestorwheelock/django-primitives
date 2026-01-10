# ADR-001: Relationship Model Consolidation

**Status:** Implemented (Phase 1-2 Complete)
**Date:** 2026-01-09
**Implemented:** 2026-01-09
**Decision Makers:** Architecture Review

## Context

DiveOps currently has two relationship models that duplicate capabilities provided by django-parties:

1. **EmergencyContact** - Links DiverProfile → Person with relationship type, priority ordering
2. **DiverRelationship** - Links DiverProfile → DiverProfile with relationship type, is_preferred_buddy flag

django-parties provides **PartyRelationship** which:
- Links any party type (Person, Organization, Group)
- Has built-in `emergency_contact` relationship type
- Has `is_primary` flag for priority indication
- Has `is_active` flag for status

## Decision

**We will use PartyRelationship as the canonical relationship model** with a DiveOps extension for domain-specific metadata.

### Architecture

```
django-parties (owns identity relationships)
┌─────────────────────────────────────────┐
│ PartyRelationship                       │
│ - from_person / from_organization       │
│ - to_person / to_organization / to_group│
│ - relationship_type                     │
│ - is_primary, is_active                 │
│ - title, contract_start/end             │
└─────────────────────────────────────────┘
              │
              │ OneToOne (optional)
              ▼
┌─────────────────────────────────────────┐
│ DiverRelationshipMeta (DiveOps)         │
│ - party_relationship (FK)               │
│ - priority (for ordering emergency)     │
│ - is_preferred_buddy                    │
│ - dive_specific_notes                   │
└─────────────────────────────────────────┘
```

### Relationship Type Mapping

| DiveOps Model | Old Type | New PartyRelationship Type | Extension Fields |
|--------------|----------|---------------------------|------------------|
| EmergencyContact | spouse | `emergency_contact` | priority |
| EmergencyContact | parent | `emergency_contact` | priority |
| EmergencyContact | child | `emergency_contact` | priority |
| EmergencyContact | sibling | `emergency_contact` | priority |
| EmergencyContact | friend | `emergency_contact` | priority |
| EmergencyContact | other | `emergency_contact` | priority |
| DiverRelationship | spouse | `spouse` | is_preferred_buddy |
| DiverRelationship | buddy | `dive_buddy` (new) | is_preferred_buddy |
| DiverRelationship | friend | `friend` (new) | is_preferred_buddy |
| DiverRelationship | family | `family` (new) | is_preferred_buddy |
| DiverRelationship | travel_companion | `travel_companion` (new) | is_preferred_buddy |
| DiverRelationship | instructor_student | `instructor_student` (new) | is_preferred_buddy |

### New Relationship Types to Add

django-parties PartyRelationship needs these new types for dive domain:
- `dive_buddy` - Regular dive partner
- `friend` - Personal friend
- `family` - Family member (generic)
- `travel_companion` - Travel together
- `instructor_student` - Training relationship

## Consequences

### Positive
- Single source of truth for relationships
- Follows primitives architecture (compose, don't duplicate)
- PartyRelationship supports all party types, not just DiverProfile
- Emergency contacts can be non-divers (Person without DiverProfile)
- Consistent with how django-parties intended relationships to work

### Negative
- Requires data migration
- Need extension model for domain-specific fields
- Slightly more complex queries (join through extension)

### Migration Strategy

**Phase 1: Add Infrastructure (No Breaking Changes)** ✅ COMPLETE
1. ✅ Add new relationship types to PartyRelationship.RELATIONSHIP_TYPES
   - Added: `friend`, `relative`, `buddy`, `travel_companion`, `instructor`, `student`
2. ✅ Create DiverRelationshipMeta model
   - Fields: `party_relationship` (OneToOne), `priority`, `is_preferred_buddy`, `notes`
3. ✅ Create selectors for new relationship queries
   - Migration: `0066_add_diver_relationship_meta.py`

**Phase 2: Data Migration** ✅ COMPLETE
1. ✅ Copy EmergencyContact → PartyRelationship + DiverRelationshipMeta
2. ✅ Copy DiverRelationship → PartyRelationship + DiverRelationshipMeta
3. ✅ Validate counts match
   - Migration: `0067_migrate_relationships_to_party_relationship.py`

**Phase 3: Switch Reads** 🔄 PENDING
1. Update DiverDetailView to query PartyRelationship
2. Update all list/detail templates
3. Update API endpoints (if any)

**Phase 4: Switch Writes** 🔄 PENDING
1. Update forms to create PartyRelationship + extension
2. Update staff views for add/edit
3. Deprecate old model forms

**Phase 5: Cleanup (Future PR)** 🔄 PENDING
1. Mark EmergencyContact as deprecated
2. Mark DiverRelationship as deprecated
3. Eventually remove in future migration

## Alternatives Considered

### Alternative B: Keep Domain Models, Document Deviation

**Rejected because:**
- Duplicates primitive functionality
- Creates confusion about where relationships live
- Person-to-Person relationships (emergency contacts) clearly belong in django-parties
- DiverProfile is an extension of Person, so diver relationships are Person relationships

## Implementation Notes

### Selector Pattern

```python
def get_diver_emergency_contacts(diver: DiverProfile) -> QuerySet:
    """Get emergency contacts via PartyRelationship."""
    return PartyRelationship.objects.filter(
        from_person=diver.person,
        relationship_type='emergency_contact',
        is_active=True,
        deleted_at__isnull=True,
    ).select_related(
        'to_person',
        'diver_meta',  # Extension
    ).order_by('diver_meta__priority', '-is_primary')
```

### Query Optimization

Use `Prefetch` for relationships:
```python
Prefetch(
    'person__relationships_from',
    queryset=PartyRelationship.objects.filter(
        relationship_type__in=['emergency_contact', 'dive_buddy', 'spouse'],
        deleted_at__isnull=True,
    ).select_related('to_person', 'diver_meta'),
    to_attr='diver_relationships'
)
```
