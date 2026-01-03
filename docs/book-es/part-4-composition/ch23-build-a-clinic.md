# Capitulo 23: Construir una Clinica

## El Desafio Veterinario

Una clinica veterinaria no es un negocio simple. En cualquier dia:

- Un dueno de mascota llama para programar una cita para el proximo martes
- Un gato llega para un chequeo de bienestar; el veterinario encuentra una infeccion de oido
- Un perro necesita cirugia de emergencia; el dueno no puede pagar hoy
- Una granja de caballos ordena 50 dosis de desparasitante para entrega el proximo mes
- Un reclamo de seguro de hace tres meses finalmente es aprobado
- Un tecnico administra vacunas que requieren seguimiento de numero de lote
- El fin del dia trae la conciliacion de efectivo, credito y seguro

Cada uno de estos escenarios involucra multiples primitivas trabajando juntas. La programacion es acuerdos mas encuentros. La facturacion es libro mayor mas catalogo. Los registros medicos son notas mas documentos mas encuentros. Los reclamos de seguro son acuerdos mas libro mayor mas decisiones.

Este capitulo muestra como componer primitivas para construir un sistema completo de gestion de clinica.

---

## Lo Que Estamos Construyendo

Un sistema de gestion de practica veterinaria con:

- **Gestion de pacientes** - Registros de mascotas con relaciones de propietario
- **Programacion** - Citas con flujo de trabajo de confirmacion
- **Flujo de trabajo clinico** - Maquina de estados de registro, examen, salida
- **Registros medicos** - Notas, diagnosticos, tratamientos, vacunaciones
- **Facturacion** - Facturas, pagos, reclamos de seguro
- **Inventario** - Medicamentos, suministros con seguimiento de lote

Sin nuevas primitivas. Solo composicion de paquetes existentes.

---

## El Mapeo de Primitivas

Cada concepto del dominio se mapea a una primitiva:

| Concepto del Dominio | Primitiva | Paquete |
|---------------------|-----------|---------|
| Dueno de mascota | Party (Person) | django-parties |
| Paciente (mascota) | Party (Person) | django-parties |
| Clinica | Party (Organization) | django-parties |
| Veterinario | Party (Person) + Role | django-parties, django-rbac |
| Tecnico | Party (Person) + Role | django-parties, django-rbac |
| Recepcionista | Party (Person) + Role | django-parties, django-rbac |
| Cita | Agreement | django-agreements |
| Visita | Encounter | django-encounters |
| Flujo de trabajo de registro | EncounterDefinition | django-encounters |
| Notas de examen | Note | django-notes |
| Resultados de laboratorio | Document | django-documents |
| Diagnostico | Decision | django-decisioning |
| Tratamiento | BasketItem | django-catalog |
| Medicamento | CatalogItem | django-catalog |
| Factura | Basket (committed) | django-catalog |
| Pago | Transaction | django-ledger |
| Reclamo de seguro | Agreement + Decision | django-agreements, django-decisioning |
| Receta | Agreement | django-agreements |
| Vacunacion | AuditLog (evento personalizado) | django-audit-log |

---

## Configuracion del Proyecto

### INSTALLED_APPS

```python
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',

    # Primitivas (instalar en este orden)
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

    # Aplicacion
    'vetclinic',
]
```

### Configuracion Inicial

```python
# vetclinic/apps.py
from django.apps import AppConfig


class VetClinicConfig(AppConfig):
    default_auto_field = 'django.db.models.UUIDField'
    name = 'vetclinic'

    def ready(self):
        # Registrar definiciones de encuentros
        from .encounters import register_definitions
        register_definitions()

        # Registrar items del catalogo
        from .catalog import register_items
        register_items()
```

---

## Capa de Dominio: Pacientes y Duenos

### La Mascota Es una Party

Una mascota es una Person en el patron Party. Esto parece extrano hasta que te das cuenta:

- Las mascotas tienen nombres, fechas de nacimiento e identificadores unicos
- Las mascotas tienen relaciones (dueno, criador, dueno anterior)
- Las mascotas tienen historia que debe ser preservada

```python
# vetclinic/models.py
from django.db import models
from django_parties.models import Person, Organization, PartyRelationship


class Pet(Person):
    """
    Una mascota es una Person con atributos especificos veterinarios.

    Usar la clase base Person proporciona:
    - Clave primaria UUID
    - Soft delete
    - Timestamps de creacion/actualizacion
    - Capacidades de relacion
    """

    class Species(models.TextChoices):
        DOG = 'dog', 'Perro'
        CAT = 'cat', 'Gato'
        BIRD = 'bird', 'Ave'
        REPTILE = 'reptile', 'Reptil'
        SMALL_MAMMAL = 'small_mammal', 'Mamifero Pequeno'
        HORSE = 'horse', 'Caballo'
        OTHER = 'other', 'Otro'

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
        verbose_name = 'mascota'
        verbose_name_plural = 'mascotas'


class PetOwnership(PartyRelationship):
    """
    Rastrea la propiedad de mascotas a lo largo del tiempo.

    Usa PartyRelationship que proporciona:
    - from_party, to_party (ambas FK a Party)
    - valid_from, valid_to (limites temporales)
    - relationship_type
    """

    class Role(models.TextChoices):
        OWNER = 'owner', 'Propietario'
        CO_OWNER = 'co_owner', 'Co-Propietario'
        GUARDIAN = 'guardian', 'Guardian'
        EMERGENCY_CONTACT = 'emergency', 'Contacto de Emergencia'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.OWNER
    )
    is_primary = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'propiedad de mascota'
        verbose_name_plural = 'propiedades de mascotas'
```

### Por Que No Un Modelo Separado de Mascota?

Podrias pensar: "Una mascota no es realmente una persona. Deberia ser su propio modelo."

Considera lo que un modelo Pet separado necesitaria:

- Clave primaria UUID (Party lo tiene)
- Timestamps de creacion/actualizacion (Party lo tiene)
- Soft delete (Party lo tiene)
- Relaciones con duenos (Party lo tiene)
- Historia de relaciones (Party lo tiene)
- Funciona con GenericFK en todo el sistema (Party lo tiene)

Un modelo especifico de mascota duplicaria toda la funcionalidad de Party. Al extender Person, obtenemos todas las capacidades gratis.

La especie, raza y atributos medicos son los unicos campos verdaderamente especificos de mascotas.

---

## Flujo de Trabajo Clinico: El Encuentro de Visita

### Definiendo la Maquina de Estados de Visita

Una visita veterinaria sigue un flujo de trabajo predecible:

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
    """Registrar definiciones de encuentros al iniciar la aplicacion."""

    # Visita ambulatoria
    EncounterDefinition.objects.update_or_create(
        code='outpatient_visit',
        defaults={
            'name': 'Visita Ambulatoria',
            'description': 'Examen veterinario estandar',
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

    # Procedimiento quirurgico
    EncounterDefinition.objects.update_or_create(
        code='surgery',
        defaults={
            'name': 'Procedimiento Quirurgico',
            'description': 'Operacion quirurgica que requiere anestesia',
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

### Validadores Personalizados

```python
# vetclinic/validators.py
from django_encounters.validators import StateValidator


class PatientPresentValidator(StateValidator):
    """Asegurar que el paciente ha sido presentado fisicamente."""

    def validate(self, encounter, from_state, to_state, actor, metadata):
        if not metadata.get('patient_weight_kg'):
            raise ValidationError("El peso del paciente debe registrarse en el check-in")
        if not metadata.get('arrival_time'):
            raise ValidationError("La hora de llegada debe registrarse")
        return True


class DischargeReadyValidator(StateValidator):
    """Asegurar que la visita esta lista para el alta."""

    def validate(self, encounter, from_state, to_state, actor, metadata):
        # Verificar que existan notas de examen
        from django_notes.models import Note
        from django.contrib.contenttypes.models import ContentType

        notes = Note.objects.filter(
            target_content_type=ContentType.objects.get_for_model(encounter),
            target_id=str(encounter.pk),
            note_type='exam_notes'
        )
        if not notes.exists():
            raise ValidationError("Las notas de examen deben registrarse antes del alta")

        # Verificar que existe una canasta (cargos registrados)
        from django_catalog.models import Basket
        basket = Basket.objects.filter(
            owner_content_type=ContentType.objects.get_for_model(encounter),
            owner_id=str(encounter.pk),
            status__in=['draft', 'committed']
        ).first()

        if not basket:
            raise ValidationError("Los cargos deben registrarse antes del alta")

        return True


class SurgeryConsentValidator(StateValidator):
    """Asegurar que el consentimiento de cirugia este firmado."""

    def validate(self, encounter, from_state, to_state, actor, metadata):
        from django_agreements.models import Agreement

        consent = Agreement.objects.filter(
            agreement_type='surgery_consent',
            parties__id=encounter.metadata.get('patient_id'),
            valid_to__isnull=True,  # Todavia activo
        ).current().first()

        if not consent:
            raise ValidationError(
                "El consentimiento de cirugia debe estar firmado antes de proceder"
            )

        return True
```

---

## Registros Medicos: Notas y Documentos

### Notas de Examen

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
    Registrar notas SOAP para un encuentro.

    Usa el formato SOAP:
    - Subjective: Observaciones del dueno
    - Objective: Hallazgos del examen
    - Assessment: Diagnostico/impresion
    - Plan: Plan de tratamiento
    """
    note_content = f"""## Subjetivo
{subjective}

## Objetivo
{objective}

## Evaluacion
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

    # Registrar el evento clinico
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
    Registrar un diagnostico como una Decision.

    Usar Decision proporciona:
    - Pista de auditoria (quien diagnostico que y cuando)
    - Captura de fundamento
    - Semantica temporal (cuando se diagnostico vs cuando se registro)
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

    # Tambien agregar como nota para lectura facil
    add_note(
        target=encounter,
        content=f"**Diagnostico**: {diagnosis_text} ({diagnosis_code})",
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
    Adjuntar documento de resultados de laboratorio a un encuentro.

    Los documentos son inmutables despues de la creacion.
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

### Vacunaciones con Seguimiento de Lote

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
    Registrar una vacunacion con seguimiento completo de lote.

    Las vacunaciones son:
    - Eventos de AuditLog (para la administracion)
    - Agreements (para el calendario de vacunacion)
    """
    # Registrar el evento de vacunacion
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

    # Crear acuerdo para el calendario de vacunacion
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
            valid_to=next_due_date + timedelta(days=30),  # Periodo de gracia
            metadata={
                'due_date': next_due_date.isoformat(),
                'reminder_date': (next_due_date - timedelta(days=14)).isoformat(),
            }
        )
        return schedule

    return None


def get_vaccination_history(patient):
    """Obtener historial completo de vacunacion para un paciente."""
    from django_audit_log.models import AuditLog

    return AuditLog.objects.for_target(patient).filter(
        event_type='vaccination_administered'
    ).order_by('-effective_at')


def get_due_vaccinations(patient, as_of=None):
    """Obtener vacunaciones que estan vencidas o atrasadas."""
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

## Facturacion: Catalogo y Libro Mayor

### Configurando el Catalogo de Servicios

```python
# vetclinic/catalog.py
from django_catalog.models import CatalogItem
from decimal import Decimal


def register_items():
    """Registrar servicios y productos de la clinica en el catalogo."""

    # Tipos de examen
    CatalogItem.objects.update_or_create(
        code='EXAM-WELLNESS',
        defaults={
            'name': 'Examen de Bienestar',
            'description': 'Chequeo anual de bienestar',
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
            'name': 'Examen de Visita por Enfermedad',
            'description': 'Examen por enfermedad o lesion',
            'item_type': 'service',
            'unit_price': Decimal('75.00'),
            'is_active': True,
            'metadata': {
                'duration_minutes': 20,
                'category': 'exam',
            }
        }
    )

    # Vacunaciones
    CatalogItem.objects.update_or_create(
        code='VAX-RABIES',
        defaults={
            'name': 'Vacunacion Antirrabica',
            'description': 'Vacuna antirrabica de 1 ano o 3 anos',
            'item_type': 'service',
            'unit_price': Decimal('25.00'),
            'is_active': True,
            'metadata': {
                'category': 'vaccination',
                'requires_lot_tracking': True,
            }
        }
    )

    # Procedimientos
    CatalogItem.objects.update_or_create(
        code='PROC-SPAY-DOG',
        defaults={
            'name': 'Esterilizacion - Perro',
            'description': 'Ovariohisterectomia para perros',
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

    # Medicamentos (items de inventario)
    CatalogItem.objects.update_or_create(
        code='MED-AMOXICILLIN-250',
        defaults={
            'name': 'Amoxicilina 250mg',
            'description': 'Capsula de Amoxicilina 250mg',
            'item_type': 'product',
            'unit_price': Decimal('1.50'),
            'unit_of_measure': 'capsula',
            'is_active': True,
            'metadata': {
                'category': 'medication',
                'requires_prescription': True,
                'dea_schedule': None,
            }
        }
    )
```

### Creando una Factura

```python
# vetclinic/services/billing.py
from django_catalog.models import Basket, BasketItem, CatalogItem
from django_catalog.services import commit_basket
from django_ledger.services import create_transaction
from django_sequence import get_next_sequence
from decimal import Decimal


def create_invoice_for_encounter(encounter, actor):
    """
    Crear una factura (canasta) para servicios prestados durante un encuentro.

    Retorna una canasta borrador que puede ser modificada antes de confirmar.
    """
    # Obtener o crear canasta para este encuentro
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
    """Agregar un servicio o producto a una factura."""
    catalog_item = CatalogItem.objects.get(code=service_code)

    item = BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_item,
        quantity=quantity,
        unit_price_snapshot=catalog_item.unit_price,  # Instantanea del precio
        metadata={
            'notes': notes,
            'added_by': str(actor.id) if actor else None,
        }
    )

    return item


def apply_discount(basket, discount_percent, reason, actor):
    """Aplicar un descuento a una factura."""
    # Obtener total actual
    subtotal = sum(
        item.unit_price_snapshot * item.quantity
        for item in basket.items.all()
    )

    discount_amount = subtotal * (Decimal(discount_percent) / Decimal('100'))

    # Agregar descuento como linea negativa
    return BasketItem.objects.create(
        basket=basket,
        catalog_item=None,  # Linea personalizada
        description=f"Descuento ({discount_percent}%): {reason}",
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
    Finalizar una factura y crear entradas en el libro mayor.

    Esto confirma la canasta (haciendola inmutable) y crea
    la transaccion contable correspondiente.
    """
    # Generar numero de factura
    invoice_number = get_next_sequence('invoice')

    # Confirmar la canasta
    order = commit_basket(
        basket_id=basket.id,
        committed_by=actor,
        metadata={
            'invoice_number': invoice_number,
        }
    )

    # Calcular total
    total = sum(
        item.unit_price_snapshot * item.quantity
        for item in order.items.all()
    )

    # Crear entrada contable (debitar CxC, acreditar ingresos)
    from django_ledger.models import Account

    ar_account = Account.objects.get(code='accounts-receivable')
    revenue_account = Account.objects.get(code='service-revenue')

    transaction = create_transaction(
        entries=[
            {'account': ar_account, 'amount': total, 'entry_type': 'debit'},
            {'account': revenue_account, 'amount': total, 'entry_type': 'credit'},
        ],
        memo=f"Factura {invoice_number}",
        metadata={
            'invoice_number': invoice_number,
            'basket_id': str(order.id),
            'encounter_id': str(basket.owner.id),
        }
    )

    # Actualizar canasta con referencias
    order.metadata['transaction_id'] = str(transaction.id)
    order.save(update_fields=['metadata'])

    return order, transaction


def record_payment(invoice, amount, payment_method, actor, reference=''):
    """
    Registrar un pago contra una factura.

    Los pagos reducen las cuentas por cobrar.
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
        memo=f"Pago para factura {invoice.metadata.get('invoice_number')}",
        metadata={
            'payment_method': payment_method,
            'reference': reference,
            'invoice_id': str(invoice.id),
        }
    )

    return transaction
```

---

## Citas: Acuerdos con Tiempo

### Programacion

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
    Programar una cita.

    Una cita es:
    - Un Agreement (compromiso de asistir)
    - Vinculado a un Encounter (la visita real cuando sucede)
    """
    from django_encounters.models import EncounterDefinition

    # Crear el acuerdo
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
        valid_to=scheduled_time + timedelta(hours=24),  # Valido hasta el dia siguiente
        metadata={
            'confirmation_status': 'pending',
        }
    )

    # Pre-crear el encuentro en estado 'scheduled'
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

    # Vincular de vuelta
    appointment.metadata['encounter_id'] = str(encounter.id)
    appointment.save(update_fields=['metadata'])

    return appointment, encounter


def confirm_appointment(appointment, confirmed_by):
    """Marcar una cita como confirmada."""
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
    """Cancelar una cita."""
    from django_audit_log import log_event
    from django_encounters.models import Encounter

    # Terminar el acuerdo
    appointment.valid_to = timezone.now()
    appointment.metadata['cancelled_at'] = timezone.now().isoformat()
    appointment.metadata['cancelled_by'] = str(cancelled_by.id)
    appointment.metadata['cancellation_reason'] = reason
    appointment.save()

    # Cancelar el encuentro
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
    """Obtener todas las citas para un dia dado."""
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

## El Flujo Completo de Visita

### Desde el Check-In hasta el Checkout

```python
# vetclinic/services/visits.py
from django_encounters.services import transition_encounter
from django.utils import timezone


def check_in_patient(encounter, receptionist, weight_kg):
    """Registrar la llegada de un paciente para su cita."""
    transition_encounter(
        encounter=encounter,
        to_state='checked_in',
        actor=receptionist,
        metadata={
            'patient_weight_kg': weight_kg,
            'arrival_time': timezone.now().isoformat(),
        }
    )

    # Actualizar metadata del encuentro
    encounter.metadata['checked_in_at'] = timezone.now().isoformat()
    encounter.metadata['checked_in_by'] = str(receptionist.id)
    encounter.metadata['current_weight_kg'] = weight_kg
    encounter.save(update_fields=['metadata'])

    return encounter


def start_exam(encounter, veterinarian):
    """El veterinario comienza el examen."""
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
    """Completar el examen y preparar para el alta."""
    from .medical_records import record_exam_notes
    from .billing import create_invoice_for_encounter

    # Transicionar a dado de alta
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
    """Completar el checkout despues del pago."""
    from .billing import finalize_invoice, record_payment

    # Finalizar la factura
    basket = Basket.objects.get(owner=encounter, status='draft')
    invoice, transaction = finalize_invoice(basket, receptionist)

    # Registrar pago si se proporciona
    if payment_info:
        record_payment(
            invoice=invoice,
            amount=payment_info['amount'],
            payment_method=payment_info['method'],
            actor=receptionist,
            reference=payment_info.get('reference', '')
        )

    # Completar el encuentro
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

## Prompt Completo de Reconstruccion

El siguiente prompt demuestra como instruir a Claude para reconstruir este sistema de clinica desde cero. Esta es la metodologia en accion - IA restringida componiendo primitivas conocidas.

```markdown
# Prompt: Construir Sistema de Gestion de Clinica Veterinaria

## Rol

Eres un desarrollador Django construyendo un sistema de gestion de clinica veterinaria.
Debes componer primitivas existentes de los paquetes django-primitives.
NO debes crear nuevos modelos Django para conceptos que las primitivas ya manejan.

## Instruccion

Construir un sistema de gestion de practica veterinaria componiendo estas primitivas:
- django-parties (pacientes, duenos, personal)
- django-rbac (roles de veterinario, tecnico, recepcionista)
- django-agreements (citas, recetas, calendarios de vacunacion)
- django-encounters (flujo de trabajo de visita)
- django-catalog (servicios, medicamentos)
- django-ledger (facturas, pagos)
- django-documents (resultados de laboratorio, radiografias)
- django-notes (notas de examen, formato SOAP)
- django-decisioning (diagnosticos)
- django-audit-log (seguimiento de lotes de vacunacion)

## Proposito del Dominio

Permitir a las clinicas veterinarias:
- Gestionar pacientes mascotas con relaciones de propietario
- Programar y confirmar citas
- Rastrear visitas a traves del flujo check-in → examen → alta → checkout
- Registrar notas medicas en formato SOAP
- Capturar diagnosticos como decisiones auditables
- Rastrear vacunaciones con numeros de lote para cumplimiento de retiro
- Generar facturas y procesar pagos
- Mantener historial medico completo

## SIN NUEVOS MODELOS

No crear ningun nuevo modelo Django para:
- Mascotas (extender Person de django-parties)
- Citas (usar Agreement)
- Visitas (usar Encounter)
- Facturas (usar Basket/Transaction)
- Registros medicos (usar Note + Document + Decision)

El UNICO nuevo modelo permitido es Pet, que DEBE extender Person de django-parties
para heredar UUID, timestamps, soft delete y capacidades de relacion.

## Composicion de Primitivas

### Pacientes y Duenos
- Pet extiende Person (especie, raza, peso como campos adicionales)
- Owner es Person
- PetOwnership extiende PartyRelationship (rastrea propiedad a lo largo del tiempo)

### Personal
- Veterinario = Person + Role (permisos de aprobador)
- Tecnico = Person + Role (puede administrar, no puede diagnosticar)
- Recepcionista = Person + Role (programacion, checkout)

### Citas
- Agreement (agreement_type="appointment")
  - parties: [mascota, dueno]
  - terms.scheduled_time, terms.duration_minutes, terms.provider_id
  - valid_from: ahora, valid_to: dia despues de la cita
  - metadata.confirmation_status

### Visitas
- Encounter con EncounterDefinition "outpatient_visit"
- Estados: scheduled → checked_in → in_exam → discharged → completed
- Los validadores aseguran: peso registrado en check-in, notas antes del alta

### Registros Medicos
- Note (note_type="exam_notes") con contenido en formato SOAP
- Document (document_type="lab_results") para adjuntos
- Decision (decision_type="diagnosis") con inputs, outcome, rationale

### Vacunaciones
- AuditLog (event_type="vaccination_administered")
  - metadata: lot_number, expiration_date, site, dose_ml
- Agreement (agreement_type="vaccination_schedule") para proxima fecha vencida

### Facturacion
- Basket (basket_type="invoice") vinculado a Encounter
- BasketItem con catalog_item (servicio/medicamento)
- Transaction para pago (debitar efectivo, acreditar cuentas por cobrar)

## Funciones de Servicio

### schedule_appointment()
```python
def schedule_appointment(
    patient: Pet,
    owner: Person,
    appointment_type: str,
    scheduled_time: datetime,
    provider: Person = None,
) -> tuple[Agreement, Encounter]:
    """Programar cita y pre-crear encuentro."""
```

### check_in_patient()
```python
def check_in_patient(
    encounter: Encounter,
    receptionist: Person,
    weight_kg: Decimal,
) -> Encounter:
    """Registrar paciente, registrar peso, transicionar a checked_in."""
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
    """Registrar notas SOAP para el encuentro."""
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
    """Registrar diagnostico como decision auditable."""
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
    """Registrar vacunacion con seguimiento de lote, crear calendario si se proporciona fecha."""
```

### finalize_invoice()
```python
def finalize_invoice(
    encounter: Encounter,
    receptionist: Person,
) -> tuple[Basket, Transaction]:
    """Confirmar canasta y crear transaccion contable."""
```

## Casos de Prueba (38 pruebas)

### Pruebas de Paciente (6 pruebas)
1. test_create_pet_extends_person
2. test_pet_owner_relationship
3. test_ownership_history
4. test_pet_soft_delete
5. test_multiple_owners
6. test_ownership_transfer

### Pruebas de Cita (6 pruebas)
7. test_schedule_appointment
8. test_confirm_appointment
9. test_cancel_appointment
10. test_reschedule_appointment
11. test_appointment_creates_encounter
12. test_daily_schedule_query

### Pruebas de Flujo de Visita (8 pruebas)
13. test_check_in_records_weight
14. test_check_in_transitions_state
15. test_start_exam
16. test_exam_notes_required_for_discharge
17. test_charges_required_for_discharge
18. test_discharge_transition
19. test_complete_checkout
20. test_workflow_validators

### Pruebas de Registros Medicos (8 pruebas)
21. test_soap_notes_format
22. test_diagnosis_as_decision
23. test_diagnosis_captures_inputs
24. test_attach_lab_results
25. test_document_immutable
26. test_vaccination_lot_tracking
27. test_vaccination_schedule
28. test_due_vaccinations_query

### Pruebas de Facturacion (6 pruebas)
29. test_create_invoice_for_encounter
30. test_add_service_to_invoice
31. test_apply_discount
32. test_finalize_invoice
33. test_record_payment
34. test_ledger_entries_balance

### Pruebas de Integracion (4 pruebas)
35. test_complete_visit_flow
36. test_visit_with_vaccination
37. test_visit_audit_trail
38. test_patient_history_query

## Comportamientos Clave

1. **Las mascotas son Parties** - Extender Person, no crear modelo separado
2. **Las citas son Agreements** - Compromisos con limites de tiempo
3. **Las visitas son Encounters** - Maquina de estados con validadores
4. **Los diagnosticos son Decisions** - Capturar inputs, outcome, rationale
5. **Las vacunaciones son eventos de AuditLog** - Seguimiento de lote en metadata
6. **Las facturas usan Catalog + Ledger** - Basket para items, Transaction para pago
7. **Los registros medicos son Notes + Documents** - Adjuntos al encuentro

## Operaciones Prohibidas

- DELETE en cualquier registro de paciente (solo soft delete)
- Asignacion directa de estado en encuentros (usar transition_encounter)
- Almacenar diagnostico sin rationale
- Registrar vacunacion sin numero de lote
- Modificar facturas confirmadas
- Evadir validadores de flujo de trabajo

## Criterios de Aceptacion

- [ ] El modelo Pet extiende Person de django-parties
- [ ] Las citas usan Agreement con relaciones de party apropiadas
- [ ] Las visitas usan Encounter con transiciones de estado validadas
- [ ] Los diagnosticos capturan inputs y rationale via Decision
- [ ] Las vacunaciones rastreadas con numeros de lote en AuditLog
- [ ] Las facturas usan Basket + Transaction
- [ ] Pista de auditoria completa para cada paciente
- [ ] Las 38 pruebas pasando
- [ ] README con ejemplos de uso
```

---

## Usando Este Prompt

Para reconstruir este sistema de clinica con Claude:

**Paso 1: Configurar la pila de instrucciones**

Capa 1 (Fundacion): "Eres un desarrollador Django..."
Capa 2 (Dominio): Las reglas de composicion de primitivas
Capa 3 (Tarea): Las funciones de servicio especificas a implementar
Capa 4 (Seguridad): Las operaciones prohibidas

**Paso 2: Generar incrementalmente**

No pidas todo de una vez. Solicita:
1. Primero: Modelos y configuracion basica
2. Luego: Funciones de servicio una a la vez
3. Luego: Pruebas para cada funcion
4. Finalmente: Pruebas de integracion

**Paso 3: Verificar contra restricciones**

Despues de cada generacion, verifica:
- Creo nuevos modelos que no deberia?
- Evadio las primitivas por implementaciones personalizadas?
- Incluyo las operaciones prohibidas?

**Paso 4: Iterar con correcciones**

Si Claude viola las restricciones, responde:
"Esto crea un modelo Appointment personalizado. Usa Agreement de django-agreements en su lugar.
La cita es un acuerdo entre la clinica y el dueno con terms.scheduled_time."

El prompt es la especificacion. Las restricciones previenen la invencion. El enfoque incremental detecta violaciones temprano.

---

## Lo Que No Construimos

Nota lo que la aplicacion de clinica NO contiene:

1. **Sin modelos personalizados para conceptos core** - Pet extiende Party, no es un modelo nuevo
2. **Sin semantica de tiempo personalizada** - Usa effective_at/recorded_at existentes
3. **Sin registro de auditoria personalizado** - Usa django-audit-log en todas partes
4. **Sin sistema de facturacion personalizado** - Compone Catalog + Ledger
5. **Sin motor de flujo de trabajo personalizado** - Usa django-encounters
6. **Sin almacenamiento de documentos personalizado** - Usa django-documents
7. **Sin sistema de notas personalizado** - Usa django-notes

El codigo de aplicacion es puramente:
- Configuracion especifica del dominio (definiciones de encuentros, items del catalogo)
- Logica de negocio (validadores, funciones de servicio)
- Composicion (conectando primitivas juntas)

---

## Ejercicio Practico

Construir un sistema de clinica minimo:

**Paso 1: Configurar el proyecto**
```bash
pip install django-primitives
django-admin startproject vetclinic
cd vetclinic
python manage.py startapp clinic
```

**Paso 2: Agregar primitivas a INSTALLED_APPS**

**Paso 3: Crear el modelo Pet extendiendo Person**

**Paso 4: Registrar una EncounterDefinition para visitas basicas**

**Paso 5: Crear funciones de servicio para:**
- Programar una cita
- Registrar la llegada de un paciente
- Registrar notas de examen
- Crear y finalizar una factura

**Paso 6: Escribir pruebas para el flujo completo**

---

## Por Que Esto Importa

El ejemplo de la clinica demuestra la tesis central de este libro:

**Las primitivas son capacidades. Las aplicaciones son composiciones.**

Cada caracteristica de la clinica veterinaria - programacion, registros medicos, facturacion, inventario - es solo una composicion de las mismas primitivas usadas en cada otra aplicacion de negocios.

La aplicacion de entrega de pizza del proximo ano? Las mismas primitivas. Diferente composicion.

El sistema de reservas de tienda de buceo del proximo mes? Las mismas primitivas. Diferente composicion.

Las primitivas son aburridas. Las primitivas son correctas. Las primitivas no cambian.

Todo el trabajo interesante esta en el dominio: como configuras los encuentros, que pones en el catalogo, como validas las transiciones. Ahi es donde vive tu conocimiento del negocio.

---

## Resumen

| Concepto del Dominio | Primitiva Usada | Por Que |
|---------------------|-----------------|---------|
| Mascota | Person | Tiene identidad, relaciones, historia |
| Cita | Agreement | Compromiso con limites de tiempo |
| Visita | Encounter | Maquina de estados con transiciones |
| Diagnostico | Decision | Eleccion auditable con fundamento |
| Notas de examen | Note | Adjunta al encuentro |
| Resultados de laboratorio | Document | Adjunto de archivo inmutable |
| Servicios | CatalogItem | Cosas que pueden facturarse |
| Factura | Basket | Coleccion de items con precios |
| Pago | Transaction | Entrada de libro mayor de doble entrada |
| Vacunacion | AuditLog | Evento con metadata de seguimiento de lote |

La clinica no es una coleccion de modelos personalizados. Es una composicion de primitivas con configuracion especifica del dominio.

Esa es la revolucion aburrida.
