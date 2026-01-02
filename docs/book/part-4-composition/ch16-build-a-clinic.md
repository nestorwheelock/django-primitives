# Chapter 16: Build a Clinic

> Same primitives. Veterinary domain.

## The Domain

A veterinary clinic needs:

- Patient records
- Appointments
- Medical procedures
- Prescriptions
- Invoicing
- Inventory (medications, supplies)

## Primitive Mapping

| Domain Concept | Primitive | Package |
|----------------|-----------|---------|
| Pet owner | Party (Person) | django-parties |
| Patient (pet) | Party (Person) | django-parties |
| Clinic | Party (Organization) | django-parties |
| Veterinarian | Party (Person) + Role | django-parties, django-rbac |
| Appointment | Encounter | django-encounters |
| Check-in flow | EncounterDefinition | django-encounters |
| Services rendered | BasketItem | django-catalog |
| Medical notes | Note | django-notes |
| Lab results | Document | django-documents |
| Prescription | Agreement | django-agreements |
| Invoice | Transaction | django-ledger |
| Payment | Entry | django-ledger |
| Vaccination schedule | Agreement (valid_from/to) | django-agreements |

## No New Primitives

Everything maps to existing packages:

```python
INSTALLED_APPS = [
    'django_basemodels',
    'django_parties',
    'django_rbac',
    'django_catalog',
    'django_encounters',
    'django_ledger',
    'django_agreements',
    'django_documents',
    'django_notes',
    'django_audit_log',
]
```

## Domain-Specific Code

What the clinic app adds:

- Encounter definitions (check-in → triage → exam → checkout)
- Catalog items (exam types, procedures, medications)
- Role definitions (vet, tech, receptionist)
- UI and workflows
- Business rules

What the clinic app does NOT add:

- New primitives
- New data models for core concepts
- Custom time semantics
- Custom audit logging

## The Pattern

1. Map domain concepts to primitives
2. Configure primitives (definitions, items, roles)
3. Build domain-specific UI
4. Add domain-specific business rules
5. Done

---

*Status: Planned*
