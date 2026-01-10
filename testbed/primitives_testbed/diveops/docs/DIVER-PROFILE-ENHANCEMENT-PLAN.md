# Diver Profile Enhancement Plan

## Overview

This plan aligns the DiveOps staff diver detail view with the django-primitives architecture, displaying the full Party graph and operational history.

## Phases

### Phase 0: Infrastructure (P0) - Selectors & Models ✅ COMPLETE

**Goal:** Add selectors and extension model without breaking existing code.

#### Files to Create/Modify:

1. **`diveops/selectors/divers.py`** (NEW)
   - `get_diver_with_full_context()` - Main selector for detail view
   - `get_diver_person_details()` - Person fields + phone metadata
   - `get_diver_normalized_contacts()` - Address/Phone/Email from django-parties
   - `get_diver_emergency_contacts()` - Via PartyRelationship
   - `get_diver_relationships()` - Buddy/family relationships
   - `get_diver_booking_history()` - Last N bookings
   - `get_diver_dive_history()` - Last N roster entries
   - `get_diver_medical_details()` - Full medical dates

2. **`diveops/models.py`** - Add DiverRelationshipMeta
   ```python
   class DiverRelationshipMeta(BaseModel):
       """Domain-specific metadata for diver relationships.

       Extension of PartyRelationship for dive-specific fields.
       Not all PartyRelationships have this - only diver-relevant ones.
       """
       party_relationship = models.OneToOneField(
           'django_parties.PartyRelationship',
           on_delete=models.CASCADE,
           related_name='diver_meta',
       )
       priority = models.PositiveSmallIntegerField(
           null=True, blank=True,
           help_text="Priority ordering (1=primary) for emergency contacts",
       )
       is_preferred_buddy = models.BooleanField(
           default=False,
           help_text="Prefer pairing these divers together",
       )
       secondary_relationship = models.CharField(
           max_length=20, blank=True,
           help_text="More specific relationship (spouse, parent, etc.)",
       )
   ```

3. **Migration:** `0062_add_diver_relationship_meta.py`

### Phase 1: Staff View Context (P1) ✅ COMPLETE

**Goal:** Add missing data to DiverDetailView context.

#### File: `diveops/staff_views.py`

Update `DiverDetailView.get_context_data()` to include:

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    diver = self.object
    person = diver.person

    # === EXISTING (keep) ===
    context["certifications"] = ...
    context["permits"] = ...
    context["medical_status"] = ...
    context["medical_instance"] = ...
    context["staff_notes"] = ...
    context["documents"] = ...
    context["agreements"] = ...
    context["photo_tags"] = ...
    context["diver_user"] = ...
    context["preference_status"] = ...
    context["preferences_by_category"] = ...

    # === NEW: Person details bundle ===
    context["person_details"] = {
        "date_of_birth": person.date_of_birth,
        "age": person.age if hasattr(person, 'age') else calculate_age(person.date_of_birth),
        "preferred_name": person.preferred_name,
        "phone_is_mobile": person.phone_is_mobile,
        "phone_has_whatsapp": person.phone_has_whatsapp,
        "phone_can_receive_sms": person.phone_can_receive_sms,
        "address": {
            "line1": person.address_line1,
            "line2": person.address_line2,
            "city": person.city,
            "state": person.state,
            "postal_code": person.postal_code,
            "country": person.country,
        } if person.address_line1 else None,
        "notes": person.notes,
    }

    # === NEW: Normalized contacts (from django-parties) ===
    context["normalized_contacts"] = {
        "addresses": person.addresses.filter(deleted_at__isnull=True).order_by('-is_primary'),
        "phones": person.phone_numbers.filter(deleted_at__isnull=True).order_by('-is_primary'),
        "emails": person.email_addresses.filter(deleted_at__isnull=True).order_by('-is_primary'),
    }

    # === NEW: Demographics (if exists) ===
    context["demographics"] = getattr(person, 'demographics', None)

    # === NEW: Emergency contacts via PartyRelationship ===
    # (Transitional: query both old and new until migration complete)
    context["emergency_contacts"] = get_diver_emergency_contacts(diver)

    # === NEW: Buddy/family relationships ===
    context["diver_relationships"] = get_diver_relationships(diver)

    # === NEW: Booking history ===
    context["booking_history"] = Booking.objects.filter(
        diver=diver,
        deleted_at__isnull=True,
    ).select_related(
        'excursion', 'excursion__dive_site', 'excursion__dive_shop'
    ).order_by('-excursion__departure_time')[:10]

    # === NEW: Dive/check-in history ===
    context["dive_history"] = ExcursionRoster.objects.filter(
        diver=diver,
        deleted_at__isnull=True,
    ).select_related(
        'excursion', 'excursion__dive_site', 'checked_in_by'
    ).order_by('-checked_in_at')[:10]

    # === NEW: Full medical dates ===
    context["medical_dates"] = {
        "clearance_date": diver.medical_clearance_date,
        "valid_until": diver.medical_clearance_valid_until,
    }

    return context
```

### Phase 2: Template Updates (P2) ✅ COMPLETE

**Goal:** Add new sections to diver_detail.html

#### File: `templates/diveops/staff/diver_detail.html`

Add these sections:

1. **Personal Details Card** (after Diver Info)
   - Date of Birth with age
   - Preferred Name (if different from first name)
   - Address (collapsible)
   - Phone metadata icons
   - Person notes (separate from staff notes)

2. **Normalized Contacts Section** (if present)
   - Multiple addresses table
   - Multiple phones table
   - Multiple emails table

3. **Booking History Section**
   - Table with excursion name, date, site, status
   - Links to excursion detail

4. **Dive History Section**
   - Table with excursion, date, site, role
   - Completion status

5. **Enhanced Medical Status**
   - Explicit clearance date
   - Valid until date
   - Days remaining badge

### Phase 3: Relationship Migration (P3) ✅ COMPLETE

**Goal:** Migrate EmergencyContact and DiverRelationship to PartyRelationship.

#### Migration Steps:

1. **Add new relationship types to django-parties**
   - `dive_buddy`, `friend`, `family`, `travel_companion`, `instructor_student`

2. **Data migration script:**
   ```python
   def migrate_emergency_contacts():
       for ec in EmergencyContact.objects.filter(deleted_at__isnull=True):
           # Create PartyRelationship
           pr, created = PartyRelationship.objects.get_or_create(
               from_person=ec.diver.person,
               to_person=ec.contact_person,
               relationship_type='emergency_contact',
               defaults={
                   'is_active': True,
                   'is_primary': ec.priority == 1,
               }
           )
           # Create extension
           DiverRelationshipMeta.objects.get_or_create(
               party_relationship=pr,
               defaults={
                   'priority': ec.priority,
                   'secondary_relationship': ec.relationship,
               }
           )

   def migrate_diver_relationships():
       TYPE_MAP = {
           'spouse': 'spouse',
           'buddy': 'dive_buddy',
           'friend': 'friend',
           'family': 'family',
           'travel_companion': 'travel_companion',
           'instructor_student': 'instructor_student',
       }
       for dr in DiverRelationship.objects.filter(deleted_at__isnull=True):
           pr, created = PartyRelationship.objects.get_or_create(
               from_person=dr.from_diver.person,
               to_person=dr.to_diver.person,
               relationship_type=TYPE_MAP.get(dr.relationship_type, 'friend'),
               defaults={'is_active': True}
           )
           DiverRelationshipMeta.objects.get_or_create(
               party_relationship=pr,
               defaults={
                   'is_preferred_buddy': dr.is_preferred_buddy,
               }
           )
   ```

3. **Validation:**
   - Count before: `EmergencyContact.objects.count()`
   - Count after: `PartyRelationship.objects.filter(relationship_type='emergency_contact').count()`
   - Assert counts match

### Phase 4: Update Forms (P4) 🔄 PENDING

**Goal:** Switch add/edit forms to use PartyRelationship.

1. Update `EmergencyContactForm` → creates PartyRelationship + DiverRelationshipMeta
2. Update `DiverRelationshipForm` → creates PartyRelationship + DiverRelationshipMeta
3. Add staff URLs for new relationship management

### Phase 5: Tests (P5) ✅ COMPLETE

**Goal:** Add comprehensive test coverage.

**Implemented:** `tests/test_diver_selectors.py` with 22 test cases.

#### Test Cases:

1. **test_diver_detail_shows_person_dob_and_age**
2. **test_diver_detail_shows_address_when_present**
3. **test_diver_detail_shows_phone_metadata_icons**
4. **test_diver_detail_shows_booking_history**
5. **test_diver_detail_shows_dive_history**
6. **test_diver_detail_shows_emergency_contacts_via_party_relationship**
7. **test_diver_detail_shows_buddy_relationships**
8. **test_diver_detail_shows_medical_dates**
9. **test_diver_detail_normalized_contacts_when_present**
10. **test_migration_preserves_emergency_contact_count**
11. **test_migration_preserves_diver_relationship_count**

---

## File-by-File Change List

### New Files:

| File | Purpose |
|------|---------|
| `diveops/selectors/divers.py` | Diver-specific selectors |
| `diveops/selectors/__init__.py` | Package init |
| `diveops/migrations/0062_diver_relationship_meta.py` | New model migration |
| `diveops/migrations/0063_migrate_relationships.py` | Data migration |
| `diveops/docs/ADR-001-RELATIONSHIP-CONSOLIDATION.md` | Architecture decision |
| `tests/test_diver_detail_enhanced.py` | New test cases |

### Modified Files:

| File | Changes |
|------|---------|
| `diveops/models.py` | Add DiverRelationshipMeta model |
| `diveops/staff_views.py` | Update DiverDetailView context |
| `templates/diveops/staff/diver_detail.html` | Add new sections |
| `packages/django-parties/src/django_parties/models.py` | Add new relationship types |

---

## Implementation Order

1. ✅ Create ADR document (done)
2. ✅ Create this plan document (done)
3. ✅ Add selectors module (`diveops/selectors/divers.py`)
4. ✅ Add DiverRelationshipMeta model + migration (`0066_add_diver_relationship_meta.py`)
5. ✅ Update DiverDetailView context (person_details, medical_details, booking_history, dive_history)
6. ✅ Update template with new sections (DOB/age, phone metadata, address, medical dates)
7. ✅ Create data migration for relationships (`0067_migrate_relationships_to_party_relationship.py`)
8. ✅ Add tests (`tests/test_diver_selectors.py` - 22 tests)
9. 🔄 Update forms (Phase 4) - PENDING
