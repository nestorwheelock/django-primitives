# Chapter 16: Build a Clinic

## The Veterinary Challenge

A veterinary clinic is not a simple business. On any given day:

- A pet owner calls to schedule an appointment for next Tuesday
- A cat arrives for a wellness check; the vet finds an ear infection
- A dog needs emergency surgery; the owner can't pay today
- A horse farm orders 50 doses of dewormer for next month's delivery
- An insurance claim from three months ago finally gets approved
- A technician administers vaccines that need lot number tracking
- The end of day brings reconciliation of cash, credit, and insurance

Every one of these scenarios involves multiple primitives working together. Scheduling is agreements plus encounters. Billing is ledger plus catalog. Medical records are notes plus documents plus encounters. Insurance claims are agreements plus ledger plus decisions.

This chapter shows how to compose primitives to build a complete clinic management system.

---

## What We're Building

A veterinary practice management system with:

- **Patient management** - Pet records with owner relationships
- **Scheduling** - Appointments with confirmation workflow
- **Clinical workflow** - Check-in, exam, checkout state machine
- **Medical records** - Notes, diagnoses, treatments, vaccinations
- **Billing** - Invoices, payments, insurance claims
- **Inventory** - Medications, supplies with lot tracking

No new primitives. Just composition of existing packages.

---

## The Primitive Mapping

Every domain concept maps to a primitive:

| Domain Concept | Primitive | Package |
|----------------|-----------|---------|
| Pet owner | Party (Person) | django-parties |
| Patient (pet) | Party (Person) | django-parties |
| Clinic | Party (Organization) | django-parties |
| Veterinarian | Party (Person) + Role | django-parties, django-rbac |
| Technician | Party (Person) + Role | django-parties, django-rbac |
| Receptionist | Party (Person) + Role | django-parties, django-rbac |
| Appointment | Agreement | django-agreements |
| Visit | Encounter | django-encounters |
| Check-in workflow | EncounterDefinition | django-encounters |
| Exam notes | Note | django-notes |
| Lab results | Document | django-documents |
| Diagnosis | Decision | django-decisioning |
| Treatment | BasketItem | django-catalog |
| Medication | CatalogItem | django-catalog |
| Invoice | Basket (committed) | django-catalog |
| Payment | Transaction | django-ledger |
| Insurance claim | Agreement + Decision | django-agreements, django-decisioning |
| Prescription | Agreement | django-agreements |
| Vaccination | AuditLog (custom event) | django-audit-log |

---

## Project Setup

### INSTALLED_APPS

```python
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',

    # Primitives (install in this order)
    'django_basemodels',
    'django_singleton',
    'django_parties',
    'django_rbac',
    'django_decisioning',
    'django_agreements',
    'django_audit_log',
    'django_money',
    'django_ledger',
    'django_sequence',
    'django_catalog',
    'django_encounters',
    'django_worklog',
    'django_documents',
    'django_notes',

    # Application
    'vetclinic',
]
```

### Initial Configuration

```python
# vetclinic/apps.py
from django.apps import AppConfig


class VetClinicConfig(AppConfig):
    default_auto_field = 'django.db.models.UUIDField'
    name = 'vetclinic'

    def ready(self):
        # Register encounter definitions
        from .encounters import register_definitions
        register_definitions()

        # Register catalog items
        from .catalog import register_items
        register_items()
```

---

## Domain Layer: Patients and Owners

### The Pet Is a Party

A pet is a Person in the Party pattern. This seems odd until you realize:

- Pets have names, birth dates, and unique identifiers
- Pets have relationships (owner, breeder, previous owner)
- Pets have history that must be preserved

```python
# vetclinic/models.py
from django.db import models
from django_parties.models import Person, Organization, PartyRelationship


class Pet(Person):
    """
    A pet is a Person with veterinary-specific attributes.

    Using Person base class provides:
    - UUID primary key
    - Soft delete
    - Created/updated timestamps
    - Relationship capabilities
    """

    class Species(models.TextChoices):
        DOG = 'dog', 'Dog'
        CAT = 'cat', 'Cat'
        BIRD = 'bird', 'Bird'
        REPTILE = 'reptile', 'Reptile'
        SMALL_MAMMAL = 'small_mammal', 'Small Mammal'
        HORSE = 'horse', 'Horse'
        OTHER = 'other', 'Other'

    species = models.CharField(
        max_length=20,
        choices=Species.choices,
        default=Species.DOG
    )
    breed = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=100, blank=True, default='')
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    microchip_id = models.CharField(max_length=50, blank=True, default='')
    is_neutered = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'pet'
        verbose_name_plural = 'pets'


class PetOwnership(PartyRelationship):
    """
    Tracks pet ownership over time.

    Uses PartyRelationship which provides:
    - from_party, to_party (both FKs to Party)
    - valid_from, valid_to (temporal bounds)
    - relationship_type
    """

    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        CO_OWNER = 'co_owner', 'Co-Owner'
        GUARDIAN = 'guardian', 'Guardian'
        EMERGENCY_CONTACT = 'emergency', 'Emergency Contact'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.OWNER
    )
    is_primary = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'pet ownership'
        verbose_name_plural = 'pet ownerships'
```

### Why Not a Separate Pet Model?

You might think: "A pet isn't really a person. It should be its own model."

Consider what a separate Pet model would need:

- UUID primary key (Party has it)
- Created/updated timestamps (Party has it)
- Soft delete (Party has it)
- Relationships to owners (Party has it)
- History of relationships (Party has it)
- Works with GenericFK throughout system (Party has it)

A pet-specific model would duplicate all of Party's functionality. By extending Person, we get all capabilities for free.

The species, breed, and medical attributes are the only truly pet-specific fields.

---

## Clinical Workflow: The Visit Encounter

### Defining the Visit State Machine

A veterinary visit follows a predictable workflow:

```
scheduled → checked_in → in_exam → discharged → completed
                              ↓
                          in_surgery
                              ↓
                          recovery
```

```python
# vetclinic/encounters.py
from django_encounters.models import EncounterDefinition
from django_encounters.validators import RequiredFieldsValidator


def register_definitions():
    """Register encounter definitions on app startup."""

    # Outpatient visit
    EncounterDefinition.objects.update_or_create(
        code='outpatient_visit',
        defaults={
            'name': 'Outpatient Visit',
            'description': 'Standard veterinary examination',
            'initial_state': 'scheduled',
            'states': [
                'scheduled',
                'checked_in',
                'in_exam',
                'discharged',
                'completed',
                'cancelled',
                'no_show',
            ],
            'transitions': {
                'scheduled': ['checked_in', 'cancelled', 'no_show'],
                'checked_in': ['in_exam', 'cancelled'],
                'in_exam': ['discharged'],
                'discharged': ['completed'],
                'completed': [],  # Terminal
                'cancelled': [],  # Terminal
                'no_show': [],    # Terminal
            },
            'validators': [
                {
                    'transition': '*→checked_in',
                    'class': 'vetclinic.validators.PatientPresentValidator',
                },
                {
                    'transition': '*→discharged',
                    'class': 'vetclinic.validators.DischargeReadyValidator',
                },
            ],
        }
    )

    # Surgical procedure
    EncounterDefinition.objects.update_or_create(
        code='surgery',
        defaults={
            'name': 'Surgical Procedure',
            'description': 'Surgical operation requiring anesthesia',
            'initial_state': 'scheduled',
            'states': [
                'scheduled',
                'pre_op',
                'in_surgery',
                'recovery',
                'discharged',
                'completed',
                'cancelled',
            ],
            'transitions': {
                'scheduled': ['pre_op', 'cancelled'],
                'pre_op': ['in_surgery', 'cancelled'],
                'in_surgery': ['recovery'],
                'recovery': ['discharged'],
                'discharged': ['completed'],
                'completed': [],
                'cancelled': [],
            },
            'validators': [
                {
                    'transition': '*→in_surgery',
                    'class': 'vetclinic.validators.SurgeryConsentValidator',
                },
                {
                    'transition': '*→recovery',
                    'class': 'vetclinic.validators.VitalSignsStableValidator',
                },
            ],
        }
    )
```

### Custom Validators

```python
# vetclinic/validators.py
from django_encounters.validators import StateValidator


class PatientPresentValidator(StateValidator):
    """Ensure patient has been physically presented."""

    def validate(self, encounter, from_state, to_state, actor, metadata):
        if not metadata.get('patient_weight_kg'):
            raise ValidationError("Patient weight must be recorded at check-in")
        if not metadata.get('arrival_time'):
            raise ValidationError("Arrival time must be recorded")
        return True


class DischargeReadyValidator(StateValidator):
    """Ensure visit is ready for discharge."""

    def validate(self, encounter, from_state, to_state, actor, metadata):
        # Check that exam notes exist
        from django_notes.models import Note
        from django.contrib.contenttypes.models import ContentType

        notes = Note.objects.filter(
            target_content_type=ContentType.objects.get_for_model(encounter),
            target_id=str(encounter.pk),
            note_type='exam_notes'
        )
        if not notes.exists():
            raise ValidationError("Exam notes must be recorded before discharge")

        # Check that a basket exists (charges recorded)
        from django_catalog.models import Basket
        basket = Basket.objects.filter(
            owner_content_type=ContentType.objects.get_for_model(encounter),
            owner_id=str(encounter.pk),
            status__in=['draft', 'committed']
        ).first()

        if not basket:
            raise ValidationError("Charges must be recorded before discharge")

        return True


class SurgeryConsentValidator(StateValidator):
    """Ensure surgery consent is signed."""

    def validate(self, encounter, from_state, to_state, actor, metadata):
        from django_agreements.models import Agreement

        consent = Agreement.objects.filter(
            agreement_type='surgery_consent',
            parties__id=encounter.metadata.get('patient_id'),
            valid_to__isnull=True,  # Still active
        ).current().first()

        if not consent:
            raise ValidationError(
                "Surgery consent must be signed before proceeding"
            )

        return True
```

---

## Medical Records: Notes and Documents

### Exam Notes

```python
# vetclinic/services/medical_records.py
from django_notes import add_note
from django_documents import attach_document
from django_audit_log import log_event


def record_exam_notes(
    encounter,
    actor,
    subjective: str,
    objective: str,
    assessment: str,
    plan: str,
):
    """
    Record SOAP notes for an encounter.

    Uses the SOAP format:
    - Subjective: Owner's observations
    - Objective: Exam findings
    - Assessment: Diagnosis/impression
    - Plan: Treatment plan
    """
    note_content = f"""## Subjective
{subjective}

## Objective
{objective}

## Assessment
{assessment}

## Plan
{plan}"""

    note = add_note(
        target=encounter,
        content=note_content,
        note_type='exam_notes',
        author=actor,
        metadata={
            'format': 'SOAP',
            'sections': ['subjective', 'objective', 'assessment', 'plan'],
        }
    )

    # Log the clinical event
    log_event(
        target=encounter,
        event_type='exam_notes_recorded',
        actor=actor,
        metadata={
            'note_id': str(note.id),
        }
    )

    return note


def record_diagnosis(
    encounter,
    actor,
    diagnosis_code: str,
    diagnosis_text: str,
    severity: str = 'moderate',
    is_primary: bool = True,
):
    """
    Record a diagnosis as a Decision.

    Using Decision provides:
    - Audit trail (who diagnosed what when)
    - Rationale capture
    - Time semantics (when diagnosed vs when recorded)
    """
    from django_decisioning import decide

    decision = decide(
        decision_type='diagnosis',
        target=encounter,
        actor=actor,
        inputs={
            'exam_findings': encounter.metadata.get('exam_findings', {}),
            'patient_history': encounter.metadata.get('patient_history', {}),
        },
        outcome=diagnosis_code,
        rationale=diagnosis_text,
        metadata={
            'severity': severity,
            'is_primary': is_primary,
        }
    )

    # Also add as a note for easy reading
    add_note(
        target=encounter,
        content=f"**Diagnosis**: {diagnosis_text} ({diagnosis_code})",
        note_type='diagnosis',
        author=actor,
    )

    return decision


def attach_lab_results(
    encounter,
    actor,
    file,
    lab_type: str,
    lab_date=None,
):
    """
    Attach lab results document to an encounter.

    Documents are immutable after creation.
    """
    from django.utils import timezone

    document = attach_document(
        target=encounter,
        file=file,
        document_type='lab_results',
        uploaded_by=actor,
        metadata={
            'lab_type': lab_type,
            'lab_date': (lab_date or timezone.now()).isoformat(),
        }
    )

    log_event(
        target=encounter,
        event_type='lab_results_attached',
        actor=actor,
        metadata={
            'document_id': str(document.id),
            'lab_type': lab_type,
        }
    )

    return document
```

### Vaccinations with Lot Tracking

```python
# vetclinic/services/vaccinations.py
from django_audit_log import log_event
from django_agreements import create_agreement
from django.utils import timezone
from datetime import timedelta


def record_vaccination(
    patient,
    vaccine_catalog_item,
    actor,
    lot_number: str,
    expiration_date,
    site: str,
    dose_ml: float,
    next_due_date=None,
    encounter=None,
):
    """
    Record a vaccination with full lot tracking.

    Vaccinations are:
    - AuditLog events (for the administration)
    - Agreements (for the vaccination schedule)
    """
    # Log the vaccination event
    log_event(
        target=patient,
        event_type='vaccination_administered',
        actor=actor,
        metadata={
            'vaccine_id': str(vaccine_catalog_item.id),
            'vaccine_name': vaccine_catalog_item.name,
            'lot_number': lot_number,
            'expiration_date': expiration_date.isoformat(),
            'site': site,
            'dose_ml': dose_ml,
            'encounter_id': str(encounter.id) if encounter else None,
        }
    )

    # Create agreement for vaccination schedule
    if next_due_date:
        schedule = create_agreement(
            agreement_type='vaccination_schedule',
            parties=[patient],
            terms={
                'vaccine_id': str(vaccine_catalog_item.id),
                'vaccine_name': vaccine_catalog_item.name,
                'last_administered': timezone.now().isoformat(),
                'administered_by': str(actor.id),
                'lot_number': lot_number,
            },
            valid_from=timezone.now(),
            valid_to=next_due_date + timedelta(days=30),  # Grace period
            metadata={
                'due_date': next_due_date.isoformat(),
                'reminder_date': (next_due_date - timedelta(days=14)).isoformat(),
            }
        )
        return schedule

    return None


def get_vaccination_history(patient):
    """Get complete vaccination history for a patient."""
    from django_audit_log.models import AuditLog

    return AuditLog.objects.for_target(patient).filter(
        event_type='vaccination_administered'
    ).order_by('-effective_at')


def get_due_vaccinations(patient, as_of=None):
    """Get vaccinations that are due or overdue."""
    from django_agreements.models import Agreement
    from django.utils import timezone

    as_of = as_of or timezone.now()

    return Agreement.objects.filter(
        agreement_type='vaccination_schedule',
        parties=patient,
    ).current(as_of=as_of).filter(
        metadata__due_date__lte=as_of.isoformat()
    )
```

---

## Billing: Catalog and Ledger

### Setting Up the Service Catalog

```python
# vetclinic/catalog.py
from django_catalog.models import CatalogItem
from decimal import Decimal


def register_items():
    """Register clinic services and products in catalog."""

    # Exam types
    CatalogItem.objects.update_or_create(
        code='EXAM-WELLNESS',
        defaults={
            'name': 'Wellness Examination',
            'description': 'Annual wellness check-up',
            'item_type': 'service',
            'unit_price': Decimal('65.00'),
            'is_active': True,
            'metadata': {
                'duration_minutes': 30,
                'category': 'exam',
            }
        }
    )

    CatalogItem.objects.update_or_create(
        code='EXAM-SICK',
        defaults={
            'name': 'Sick Visit Examination',
            'description': 'Examination for illness or injury',
            'item_type': 'service',
            'unit_price': Decimal('75.00'),
            'is_active': True,
            'metadata': {
                'duration_minutes': 20,
                'category': 'exam',
            }
        }
    )

    # Vaccinations
    CatalogItem.objects.update_or_create(
        code='VAX-RABIES',
        defaults={
            'name': 'Rabies Vaccination',
            'description': '1-year or 3-year rabies vaccine',
            'item_type': 'service',
            'unit_price': Decimal('25.00'),
            'is_active': True,
            'metadata': {
                'category': 'vaccination',
                'requires_lot_tracking': True,
            }
        }
    )

    # Procedures
    CatalogItem.objects.update_or_create(
        code='PROC-SPAY-DOG',
        defaults={
            'name': 'Spay - Dog',
            'description': 'Ovariohysterectomy for dogs',
            'item_type': 'service',
            'unit_price': Decimal('350.00'),
            'is_active': True,
            'metadata': {
                'category': 'surgery',
                'requires_consent': True,
                'duration_minutes': 60,
            }
        }
    )

    # Medications (inventory items)
    CatalogItem.objects.update_or_create(
        code='MED-AMOXICILLIN-250',
        defaults={
            'name': 'Amoxicillin 250mg',
            'description': 'Amoxicillin capsule 250mg',
            'item_type': 'product',
            'unit_price': Decimal('1.50'),
            'unit_of_measure': 'capsule',
            'is_active': True,
            'metadata': {
                'category': 'medication',
                'requires_prescription': True,
                'dea_schedule': None,
            }
        }
    )
```

### Creating an Invoice

```python
# vetclinic/services/billing.py
from django_catalog.models import Basket, BasketItem, CatalogItem
from django_catalog.services import commit_basket
from django_ledger.services import create_transaction
from django_sequence import get_next_sequence
from decimal import Decimal


def create_invoice_for_encounter(encounter, actor):
    """
    Create an invoice (basket) for services rendered during an encounter.

    Returns a draft basket that can be modified before committing.
    """
    # Get or create basket for this encounter
    basket, created = Basket.objects.get_or_create(
        owner=encounter,
        status='draft',
        defaults={
            'basket_type': 'invoice',
            'metadata': {
                'encounter_id': str(encounter.id),
                'patient_id': encounter.metadata.get('patient_id'),
            }
        }
    )

    return basket


def add_service_to_invoice(basket, service_code, quantity=1, actor=None, notes=''):
    """Add a service or product to an invoice."""
    catalog_item = CatalogItem.objects.get(code=service_code)

    item = BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_item,
        quantity=quantity,
        unit_price_snapshot=catalog_item.unit_price,  # Snapshot price
        metadata={
            'notes': notes,
            'added_by': str(actor.id) if actor else None,
        }
    )

    return item


def apply_discount(basket, discount_percent, reason, actor):
    """Apply a discount to an invoice."""
    # Get current total
    subtotal = sum(
        item.unit_price_snapshot * item.quantity
        for item in basket.items.all()
    )

    discount_amount = subtotal * (Decimal(discount_percent) / Decimal('100'))

    # Add discount as negative line item
    return BasketItem.objects.create(
        basket=basket,
        catalog_item=None,  # Custom line
        description=f"Discount ({discount_percent}%): {reason}",
        quantity=1,
        unit_price_snapshot=-discount_amount,
        metadata={
            'discount_percent': discount_percent,
            'reason': reason,
            'applied_by': str(actor.id),
        }
    )


def finalize_invoice(basket, actor):
    """
    Finalize an invoice and create ledger entries.

    This commits the basket (making it immutable) and creates
    the corresponding accounting transaction.
    """
    # Generate invoice number
    invoice_number = get_next_sequence('invoice')

    # Commit the basket
    order = commit_basket(
        basket_id=basket.id,
        committed_by=actor,
        metadata={
            'invoice_number': invoice_number,
        }
    )

    # Calculate total
    total = sum(
        item.unit_price_snapshot * item.quantity
        for item in order.items.all()
    )

    # Create accounting entry (debit AR, credit revenue)
    from django_ledger.models import Account

    ar_account = Account.objects.get(code='accounts-receivable')
    revenue_account = Account.objects.get(code='service-revenue')

    transaction = create_transaction(
        entries=[
            {'account': ar_account, 'amount': total, 'entry_type': 'debit'},
            {'account': revenue_account, 'amount': total, 'entry_type': 'credit'},
        ],
        memo=f"Invoice {invoice_number}",
        metadata={
            'invoice_number': invoice_number,
            'basket_id': str(order.id),
            'encounter_id': str(basket.owner.id),
        }
    )

    # Update basket with references
    order.metadata['transaction_id'] = str(transaction.id)
    order.save(update_fields=['metadata'])

    return order, transaction


def record_payment(invoice, amount, payment_method, actor, reference=''):
    """
    Record a payment against an invoice.

    Payments reduce accounts receivable.
    """
    from django_ledger.models import Account
    from django_ledger.services import create_transaction

    ar_account = Account.objects.get(code='accounts-receivable')
    cash_account = Account.objects.get(code=f'cash-{payment_method}')

    transaction = create_transaction(
        entries=[
            {'account': cash_account, 'amount': amount, 'entry_type': 'debit'},
            {'account': ar_account, 'amount': amount, 'entry_type': 'credit'},
        ],
        memo=f"Payment for invoice {invoice.metadata.get('invoice_number')}",
        metadata={
            'payment_method': payment_method,
            'reference': reference,
            'invoice_id': str(invoice.id),
        }
    )

    return transaction
```

---

## Appointments: Agreements with Time

### Scheduling

```python
# vetclinic/services/scheduling.py
from django_agreements import create_agreement
from django_encounters.services import create_encounter
from django.utils import timezone
from datetime import timedelta


def schedule_appointment(
    patient,
    owner,
    appointment_type: str,
    scheduled_time,
    duration_minutes: int = 30,
    provider=None,
    notes: str = '',
):
    """
    Schedule an appointment.

    An appointment is:
    - An Agreement (commitment to show up)
    - Linked to an Encounter (the actual visit when it happens)
    """
    from django_encounters.models import EncounterDefinition

    # Create the agreement
    appointment = create_agreement(
        agreement_type='appointment',
        parties=[patient, owner],
        terms={
            'appointment_type': appointment_type,
            'scheduled_time': scheduled_time.isoformat(),
            'duration_minutes': duration_minutes,
            'provider_id': str(provider.id) if provider else None,
            'notes': notes,
        },
        valid_from=timezone.now(),
        valid_to=scheduled_time + timedelta(hours=24),  # Valid until day after
        metadata={
            'confirmation_status': 'pending',
        }
    )

    # Pre-create the encounter in 'scheduled' state
    definition = EncounterDefinition.objects.get(code='outpatient_visit')

    encounter = create_encounter(
        definition=definition,
        subject=patient,
        metadata={
            'appointment_id': str(appointment.id),
            'patient_id': str(patient.id),
            'owner_id': str(owner.id),
            'scheduled_time': scheduled_time.isoformat(),
        }
    )

    # Link back
    appointment.metadata['encounter_id'] = str(encounter.id)
    appointment.save(update_fields=['metadata'])

    return appointment, encounter


def confirm_appointment(appointment, confirmed_by):
    """Mark an appointment as confirmed."""
    from django_audit_log import log_event

    appointment.metadata['confirmation_status'] = 'confirmed'
    appointment.metadata['confirmed_at'] = timezone.now().isoformat()
    appointment.metadata['confirmed_by'] = str(confirmed_by.id)
    appointment.save(update_fields=['metadata'])

    log_event(
        target=appointment,
        event_type='appointment_confirmed',
        actor=confirmed_by,
    )

    return appointment


def cancel_appointment(appointment, cancelled_by, reason: str):
    """Cancel an appointment."""
    from django_audit_log import log_event
    from django_encounters.models import Encounter

    # End the agreement
    appointment.valid_to = timezone.now()
    appointment.metadata['cancelled_at'] = timezone.now().isoformat()
    appointment.metadata['cancelled_by'] = str(cancelled_by.id)
    appointment.metadata['cancellation_reason'] = reason
    appointment.save()

    # Cancel the encounter
    encounter_id = appointment.metadata.get('encounter_id')
    if encounter_id:
        encounter = Encounter.objects.get(id=encounter_id)
        encounter.transition_to(
            'cancelled',
            actor=cancelled_by,
            metadata={'reason': reason}
        )

    log_event(
        target=appointment,
        event_type='appointment_cancelled',
        actor=cancelled_by,
        metadata={'reason': reason}
    )

    return appointment


def get_schedule_for_day(date, provider=None):
    """Get all appointments for a given day."""
    from django_agreements.models import Agreement

    start = timezone.make_aware(
        timezone.datetime.combine(date, timezone.datetime.min.time())
    )
    end = start + timedelta(days=1)

    queryset = Agreement.objects.filter(
        agreement_type='appointment',
        terms__scheduled_time__gte=start.isoformat(),
        terms__scheduled_time__lt=end.isoformat(),
    ).current()

    if provider:
        queryset = queryset.filter(terms__provider_id=str(provider.id))

    return queryset.order_by('terms__scheduled_time')
```

---

## The Complete Visit Flow

### From Check-In to Checkout

```python
# vetclinic/services/visits.py
from django_encounters.services import transition_encounter
from django.utils import timezone


def check_in_patient(encounter, receptionist, weight_kg):
    """Check in a patient for their appointment."""
    transition_encounter(
        encounter=encounter,
        to_state='checked_in',
        actor=receptionist,
        metadata={
            'patient_weight_kg': weight_kg,
            'arrival_time': timezone.now().isoformat(),
        }
    )

    # Update encounter metadata
    encounter.metadata['checked_in_at'] = timezone.now().isoformat()
    encounter.metadata['checked_in_by'] = str(receptionist.id)
    encounter.metadata['current_weight_kg'] = weight_kg
    encounter.save(update_fields=['metadata'])

    return encounter


def start_exam(encounter, veterinarian):
    """Veterinarian begins examination."""
    transition_encounter(
        encounter=encounter,
        to_state='in_exam',
        actor=veterinarian,
        metadata={
            'exam_started_at': timezone.now().isoformat(),
        }
    )

    return encounter


def complete_exam_and_discharge(encounter, veterinarian, discharge_instructions):
    """Complete exam and prepare for discharge."""
    from .medical_records import record_exam_notes
    from .billing import create_invoice_for_encounter

    # Transition to discharged
    transition_encounter(
        encounter=encounter,
        to_state='discharged',
        actor=veterinarian,
        metadata={
            'discharged_at': timezone.now().isoformat(),
            'discharge_instructions': discharge_instructions,
        }
    )

    return encounter


def complete_checkout(encounter, receptionist, payment_info=None):
    """Complete checkout after payment."""
    from .billing import finalize_invoice, record_payment

    # Finalize the invoice
    basket = Basket.objects.get(owner=encounter, status='draft')
    invoice, transaction = finalize_invoice(basket, receptionist)

    # Record payment if provided
    if payment_info:
        record_payment(
            invoice=invoice,
            amount=payment_info['amount'],
            payment_method=payment_info['method'],
            actor=receptionist,
            reference=payment_info.get('reference', '')
        )

    # Complete the encounter
    transition_encounter(
        encounter=encounter,
        to_state='completed',
        actor=receptionist,
        metadata={
            'completed_at': timezone.now().isoformat(),
            'invoice_number': invoice.metadata.get('invoice_number'),
        }
    )

    return encounter, invoice
```

---

## Complete Rebuild Prompt

The following prompt demonstrates how to instruct Claude to rebuild this clinic system from scratch. This is the methodology in action—constrained AI composing known primitives.

```markdown
# Prompt: Build Veterinary Clinic Management System

## Role

You are a Django developer building a veterinary clinic management system.
You must compose existing primitives from django-primitives packages.
You must NOT create new Django models for concepts that primitives already handle.

## Instruction

Build a veterinary practice management system by composing these primitives:
- django-parties (patients, owners, staff)
- django-rbac (veterinarian, technician, receptionist roles)
- django-agreements (appointments, prescriptions, vaccination schedules)
- django-encounters (visit workflow)
- django-catalog (services, medications)
- django-ledger (invoices, payments)
- django-documents (lab results, x-rays)
- django-notes (exam notes, SOAP format)
- django-decisioning (diagnoses)
- django-audit-log (vaccination lot tracking)

## Domain Purpose

Enable veterinary clinics to:
- Manage pet patients with owner relationships
- Schedule and confirm appointments
- Track visits through check-in → exam → discharge → checkout workflow
- Record medical notes in SOAP format
- Capture diagnoses as auditable decisions
- Track vaccinations with lot numbers for recall compliance
- Generate invoices and process payments
- Maintain complete medical history

## NO NEW MODELS

Do not create any new Django models for:
- Pets (extend Person from django-parties)
- Appointments (use Agreement)
- Visits (use Encounter)
- Invoices (use Basket/Transaction)
- Medical records (use Note + Document + Decision)

The ONLY new model allowed is Pet, which MUST extend Person from django-parties
to inherit UUID, timestamps, soft delete, and relationship capabilities.

## Primitive Composition

### Patients and Owners
- Pet extends Person (species, breed, weight as additional fields)
- Owner is Person
- PetOwnership extends PartyRelationship (tracks ownership over time)

### Staff
- Veterinarian = Person + Role (approver permissions)
- Technician = Person + Role (can administer, cannot diagnose)
- Receptionist = Person + Role (scheduling, checkout)

### Appointments
- Agreement (agreement_type="appointment")
  - parties: [pet, owner]
  - terms.scheduled_time, terms.duration_minutes, terms.provider_id
  - valid_from: now, valid_to: day after appointment
  - metadata.confirmation_status

### Visits
- Encounter with EncounterDefinition "outpatient_visit"
- States: scheduled → checked_in → in_exam → discharged → completed
- Validators enforce: weight recorded at check-in, notes before discharge

### Medical Records
- Note (note_type="exam_notes") with SOAP format content
- Document (document_type="lab_results") for attachments
- Decision (decision_type="diagnosis") with inputs, outcome, rationale

### Vaccinations
- AuditLog (event_type="vaccination_administered")
  - metadata: lot_number, expiration_date, site, dose_ml
- Agreement (agreement_type="vaccination_schedule") for next due date

### Billing
- Basket (basket_type="invoice") linked to Encounter
- BasketItem with catalog_item (service/medication)
- Transaction for payment (debit cash, credit receivables)

## Service Functions

### schedule_appointment()
```python
def schedule_appointment(
    patient: Pet,
    owner: Person,
    appointment_type: str,
    scheduled_time: datetime,
    provider: Person = None,
) -> tuple[Agreement, Encounter]:
    """Schedule appointment and pre-create encounter."""
```

### check_in_patient()
```python
def check_in_patient(
    encounter: Encounter,
    receptionist: Person,
    weight_kg: Decimal,
) -> Encounter:
    """Check in patient, record weight, transition to checked_in."""
```

### record_exam_notes()
```python
def record_exam_notes(
    encounter: Encounter,
    veterinarian: Person,
    subjective: str,
    objective: str,
    assessment: str,
    plan: str,
) -> Note:
    """Record SOAP notes for encounter."""
```

### record_diagnosis()
```python
def record_diagnosis(
    encounter: Encounter,
    veterinarian: Person,
    diagnosis_code: str,
    diagnosis_text: str,
    severity: str,
) -> Decision:
    """Record diagnosis as auditable decision."""
```

### record_vaccination()
```python
def record_vaccination(
    patient: Pet,
    vaccine: CatalogItem,
    veterinarian: Person,
    lot_number: str,
    expiration_date: date,
    site: str,
    dose_ml: float,
    next_due_date: date = None,
) -> Agreement:
    """Record vaccination with lot tracking, create schedule if due date provided."""
```

### finalize_invoice()
```python
def finalize_invoice(
    encounter: Encounter,
    receptionist: Person,
) -> tuple[Basket, Transaction]:
    """Commit basket and create accounting transaction."""
```

## Test Cases (38 tests)

### Patient Tests (6 tests)
1. test_create_pet_extends_person
2. test_pet_owner_relationship
3. test_ownership_history
4. test_pet_soft_delete
5. test_multiple_owners
6. test_ownership_transfer

### Appointment Tests (6 tests)
7. test_schedule_appointment
8. test_confirm_appointment
9. test_cancel_appointment
10. test_reschedule_appointment
11. test_appointment_creates_encounter
12. test_daily_schedule_query

### Visit Workflow Tests (8 tests)
13. test_check_in_records_weight
14. test_check_in_transitions_state
15. test_start_exam
16. test_exam_notes_required_for_discharge
17. test_charges_required_for_discharge
18. test_discharge_transition
19. test_complete_checkout
20. test_workflow_validators

### Medical Records Tests (8 tests)
21. test_soap_notes_format
22. test_diagnosis_as_decision
23. test_diagnosis_captures_inputs
24. test_attach_lab_results
25. test_document_immutable
26. test_vaccination_lot_tracking
27. test_vaccination_schedule
28. test_due_vaccinations_query

### Billing Tests (6 tests)
29. test_create_invoice_for_encounter
30. test_add_service_to_invoice
31. test_apply_discount
32. test_finalize_invoice
33. test_record_payment
34. test_ledger_entries_balance

### Integration Tests (4 tests)
35. test_complete_visit_flow
36. test_visit_with_vaccination
37. test_visit_audit_trail
38. test_patient_history_query

## Key Behaviors

1. **Pets are Parties** - Extend Person, don't create separate model
2. **Appointments are Agreements** - Time-bounded commitments
3. **Visits are Encounters** - State machine with validators
4. **Diagnoses are Decisions** - Capture inputs, outcome, rationale
5. **Vaccinations are AuditLog events** - Lot tracking in metadata
6. **Invoices use Catalog + Ledger** - Basket for items, Transaction for payment
7. **Medical records are Notes + Documents** - Attached to encounter

## Forbidden Operations

- DELETE on any patient record (soft delete only)
- Direct state assignment on encounters (use transition_encounter)
- Storing diagnosis without rationale
- Recording vaccination without lot number
- Modifying committed invoices
- Bypassing workflow validators

## Acceptance Criteria

- [ ] Pet model extends Person from django-parties
- [ ] Appointments use Agreement with proper party relationships
- [ ] Visits use Encounter with validated state transitions
- [ ] Diagnoses capture inputs and rationale via Decision
- [ ] Vaccinations tracked with lot numbers in AuditLog
- [ ] Invoices use Basket + Transaction
- [ ] Complete audit trail for every patient
- [ ] All 38 tests passing
- [ ] README with usage examples
```

---

## Using This Prompt

To rebuild this clinic system with Claude:

**Step 1: Set up the instruction stack**

Layer 1 (Foundation): "You are a Django developer..."
Layer 2 (Domain): The primitive composition rules
Layer 3 (Task): The specific service functions to implement
Layer 4 (Safety): The forbidden operations

**Step 2: Generate incrementally**

Don't ask for everything at once. Request:
1. First: Models and basic setup
2. Then: Service functions one at a time
3. Then: Tests for each function
4. Finally: Integration tests

**Step 3: Verify against constraints**

After each generation, check:
- Did it create new models it shouldn't have?
- Did it bypass primitives for custom implementations?
- Did it include the forbidden operations?

**Step 4: Iterate with corrections**

If Claude violates constraints, respond:
"This creates a custom Appointment model. Use Agreement from django-agreements instead.
The appointment is an agreement between clinic and owner with terms.scheduled_time."

The prompt is the specification. The constraints prevent invention. The incremental approach catches violations early.

---

## What We Didn't Build

Notice what the clinic application does NOT contain:

1. **No custom models for core concepts** - Pet extends Party, not a new model
2. **No custom time semantics** - Uses existing effective_at/recorded_at
3. **No custom audit logging** - Uses django-audit-log everywhere
4. **No custom billing system** - Composes Catalog + Ledger
5. **No custom workflow engine** - Uses django-encounters
6. **No custom document storage** - Uses django-documents
7. **No custom notes system** - Uses django-notes

The application code is purely:
- Domain-specific configuration (encounter definitions, catalog items)
- Business logic (validators, service functions)
- Composition (connecting primitives together)

---

## Hands-On Exercise

Build a minimal clinic system:

**Step 1: Set up the project**
```bash
pip install django-primitives
django-admin startproject vetclinic
cd vetclinic
python manage.py startapp clinic
```

**Step 2: Add primitives to INSTALLED_APPS**

**Step 3: Create the Pet model extending Person**

**Step 4: Register one EncounterDefinition for basic visits**

**Step 5: Create service functions for:**
- Scheduling an appointment
- Checking in a patient
- Recording exam notes
- Creating and finalizing an invoice

**Step 6: Write tests for the complete flow**

---

## Why This Matters

The clinic example demonstrates the core thesis of this book:

**Primitives are capabilities. Applications are compositions.**

Every veterinary clinic feature—scheduling, medical records, billing, inventory—is just a composition of the same primitives used in every other business application.

Next year's pizza delivery app? Same primitives. Different composition.

Next month's dive shop booking system? Same primitives. Different composition.

The primitives are boring. The primitives are correct. The primitives don't change.

All the interesting work is in the domain: how you configure encounters, what you put in the catalog, how you validate transitions. That's where your business knowledge lives.

---

## Summary

| Domain Concept | Primitive Used | Why |
|----------------|----------------|-----|
| Pet | Person | Has identity, relationships, history |
| Appointment | Agreement | Commitment with time bounds |
| Visit | Encounter | State machine with transitions |
| Diagnosis | Decision | Auditable choice with rationale |
| Exam notes | Note | Attached to encounter |
| Lab results | Document | Immutable file attachment |
| Services | CatalogItem | Things that can be billed |
| Invoice | Basket | Collection of items with prices |
| Payment | Transaction | Double-entry ledger entry |
| Vaccination | AuditLog | Event with lot tracking metadata |

The clinic is not a collection of custom models. It's a composition of primitives with domain-specific configuration.

That's the boring revolution.
