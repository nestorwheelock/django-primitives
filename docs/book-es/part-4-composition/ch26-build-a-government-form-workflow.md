# Capitulo 26: Construir un Flujo de Trabajo de Formularios Gubernamentales

## La Solicitud de Informacion Publica

En 2019, una periodista presento una solicitud de registros publicos al departamento de planificacion de una ciudad. Queria saber quien aprobo una varianza de zonificacion controversial, cuando la aprobaron y que documentos revisaron.

La respuesta del departamento: "No podemos localizar registros completos para esta solicitud."

La varianza habia sido aprobada dos anos antes. La decision habia sucedido. El edificio se habia construido. Pero el rastro desde la solicitud hasta la aprobacion era fragmentario - disperso entre hilos de correo electronico, archivos en papel y un sistema de permisos antiguo que sobrescribia estados viejos con nuevos.

La ciudad gasto $1.8 millones reconstruyendo su sistema de permisos. El nuevo requisito era simple: cada accion debe ser registrada, cada decision debe ser explicada, y nada puede ser eliminado o modificado.

Este capitulo construye ese sistema. Las mismas primitivas. Dominio de burocracia.

---

## El Dominio

Un sistema de solicitud de permisos gubernamentales necesita:

- **Solicitantes y agencias** - quien solicita y quien revisa
- **Formularios de solicitud** - diferentes tipos de permisos con diferentes requisitos
- **Flujos de trabajo de revision** - progresion estructurada a traves de etapas
- **Aprobaciones y rechazos** - decisiones explicitas con fundamento
- **Documentos adjuntos** - materiales de soporte requeridos
- **Comentarios publicos** - entrada de ciudadanos sobre solicitudes
- **Tarifas** - procesamiento de pagos con manejo de reembolsos
- **Pista de auditoria** - registro inmutable de todo
- **Permisos emitidos** - el acuerdo final que otorga permiso

## Mapeo de Primitivas

| Concepto del Dominio | Primitiva | Paquete |
|---------------------|-----------|---------|
| Solicitante | Party (Person/Org) | django-parties |
| Agencia | Party (Organization) | django-parties |
| Departamento | PartyRelationship | django-parties |
| Revisor | Party + Role | django-parties, django-rbac |
| Tipo de permiso | Category + CatalogItem | django-catalog |
| Solicitud | Encounter | django-encounters |
| Etapas de revision | EncounterDefinition | django-encounters |
| Transicion de etapa | EncounterTransition | django-encounters |
| Asignacion de revisor | WorkItem | django-catalog |
| Decision de aprobacion | Decision | django-decisioning |
| Documentos adjuntos | Document | django-documents |
| Comentarios publicos | Note | django-notes |
| Tarifa de solicitud | Transaction | django-ledger |
| Permiso emitido | Agreement | django-agreements |
| Toda la actividad | AuditLog | django-audit-log |

Cero nuevos modelos. Los flujos de trabajo gubernamentales son composiciones de primitivas existentes con requisitos de auditoria mas estrictos.

---

## Agencias y Departamentos

Las organizaciones gubernamentales tienen estructura jerarquica. Los revisores pertenecen a departamentos dentro de agencias.

### Estructura de Agencia

```python
from django_parties.models import Organization, Person, PartyRelationship

# Gobierno de la ciudad
city = Organization.objects.create(
    name="Ciudad de Springfield",
    organization_type="government",
    metadata={
        "jurisdiction": "municipal",
        "state": "IL",
    }
)

# Departamento de planificacion
planning_dept = Organization.objects.create(
    name="Departamento de Planificacion y Zonificacion",
    organization_type="department",
    metadata={
        "agency_code": "PLZ",
        "parent_agency_id": str(city.id),
    }
)

# Relacion: El departamento pertenece a la ciudad
PartyRelationship.objects.create(
    from_party=planning_dept,
    to_party=city,
    relationship_type="department_of",
    valid_from=timezone.now(),
)

# Departamento de construccion
building_dept = Organization.objects.create(
    name="Departamento de Construccion y Seguridad",
    organization_type="department",
    metadata={
        "agency_code": "BSD",
        "parent_agency_id": str(city.id),
    }
)

PartyRelationship.objects.create(
    from_party=building_dept,
    to_party=city,
    relationship_type="department_of",
    valid_from=timezone.now(),
)
```

### Revisores y Roles

```python
from django_rbac.models import Role, Permission, UserRole

# Permisos
can_review = Permission.objects.create(
    code="review_applications",
    name="Revisar Solicitudes",
    description="Puede revisar y agregar comentarios a solicitudes",
)

can_approve = Permission.objects.create(
    code="approve_applications",
    name="Aprobar Solicitudes",
    description="Puede tomar decisiones finales de aprobacion",
)

can_reject = Permission.objects.create(
    code="reject_applications",
    name="Rechazar Solicitudes",
    description="Puede rechazar solicitudes",
)

can_request_info = Permission.objects.create(
    code="request_additional_info",
    name="Solicitar Informacion Adicional",
    description="Puede solicitar mas documentos al solicitante",
)

# Roles
reviewer_role = Role.objects.create(
    name="Revisor de Solicitudes",
    code="reviewer",
)
reviewer_role.permissions.add(can_review, can_request_info)

approver_role = Role.objects.create(
    name="Aprobador de Solicitudes",
    code="approver",
)
approver_role.permissions.add(can_review, can_approve, can_reject, can_request_info)

# Asignar personal a departamento con rol
planner = Person.objects.create(
    full_name="Sara Chen",
    email="sara.chen@springfield.gov",
    metadata={
        "employee_id": "PLZ-1042",
        "title": "Planificadora Senior",
    }
)

PartyRelationship.objects.create(
    from_party=planner,
    to_party=planning_dept,
    relationship_type="employee",
    valid_from=date(2018, 3, 15),
)

# Otorgar rol de revisor
UserRole.objects.create(
    user=planner_user,  # Usuario Django vinculado a planner
    role=approver_role,
    valid_from=timezone.now(),
)
```

### Consultando Personal del Departamento

```python
# Personal actual en departamento de planificacion
current_staff = PartyRelationship.objects.filter(
    to_party=planning_dept,
    relationship_type="employee",
).current()

# Personal con autoridad de aprobacion
approvers = UserRole.objects.filter(
    role__permissions__code="approve_applications",
    user__party__partyrelationship__to_party=planning_dept,
).current()

# Quien tenia autoridad de aprobacion en la fecha en que se tomo la decision?
approvers_then = UserRole.objects.filter(
    role__permissions__code="approve_applications",
).as_of(decision_date)
```

---

## Tipos de Permiso como Catalogo

Diferentes permisos tienen diferentes requisitos, tarifas y flujos de trabajo.

### Categorias de Permiso

```python
from django_catalog.models import Category, CatalogItem
from decimal import Decimal

# Categorias por departamento
building_permits = Category.objects.create(
    name="Permisos de Construccion",
    code="building",
    metadata={
        "department_id": str(building_dept.id),
        "typical_review_days": 30,
    }
)

planning_permits = Category.objects.create(
    name="Permisos de Planificacion",
    code="planning",
    metadata={
        "department_id": str(planning_dept.id),
        "typical_review_days": 45,
    }
)

# Subcategorias
residential_building = Category.objects.create(
    name="Construccion Residencial",
    code="residential_building",
    parent=building_permits,
)

commercial_building = Category.objects.create(
    name="Construccion Comercial",
    code="commercial_building",
    parent=building_permits,
)
```

### Definiciones de Tipo de Permiso

```python
# Permiso de construccion residencial
residential_permit = CatalogItem.objects.create(
    category=residential_building,
    name="Permiso de Residencia Unifamiliar",
    sku="BLDG-RES-SFR",
    unit_price=Decimal("450.00"),  # Tarifa base
    currency="USD",
    metadata={
        "description": "Nueva construccion de residencia unifamiliar",
        "required_documents": [
            "site_plan",
            "floor_plans",
            "elevation_drawings",
            "structural_calculations",
            "energy_compliance_report",
        ],
        "workflow": "building_permit_standard",
        "review_departments": ["planning", "building", "fire"],
        "public_notice_required": False,
        "estimated_review_days": 21,
        "fee_formula": "base + (sqft * 0.25)",  # $0.25 por pie cuadrado
    }
)

# Varianza de zonificacion
variance_permit = CatalogItem.objects.create(
    category=planning_permits,
    name="Varianza de Zonificacion",
    sku="PLN-VAR",
    unit_price=Decimal("1500.00"),
    currency="USD",
    metadata={
        "description": "Solicitud de varianza de requisitos de zonificacion",
        "required_documents": [
            "variance_justification",
            "site_survey",
            "neighbor_notification_proof",
            "photos",
        ],
        "workflow": "variance_with_hearing",
        "review_departments": ["planning"],
        "public_notice_required": True,
        "public_comment_period_days": 30,
        "requires_hearing": True,
        "estimated_review_days": 90,
    }
)

# Licencia comercial
business_license = CatalogItem.objects.create(
    category=planning_permits,
    name="Licencia Comercial",
    sku="PLN-BIZ",
    unit_price=Decimal("150.00"),
    currency="USD",
    metadata={
        "description": "Licencia para operar un negocio en ubicacion especificada",
        "required_documents": [
            "business_registration",
            "lease_agreement",
            "liability_insurance",
        ],
        "workflow": "business_license_standard",
        "review_departments": ["planning", "fire"],
        "public_notice_required": False,
        "renewal_period_months": 12,
        "estimated_review_days": 14,
    }
)
```

---

## Solicitudes como Encounters

Una solicitud de permiso es un encuentro que progresa a traves de etapas definidas.

### Definicion del Flujo de Trabajo

```python
from django_encounters.models import EncounterDefinition, EncounterValidator

# Flujo de trabajo estandar de permiso de construccion
building_workflow = EncounterDefinition.objects.create(
    name="Permiso de Construccion - Estandar",
    code="building_permit_standard",
    initial_state="draft",
    metadata={
        "permit_category": "building",
        "auto_assign_reviewers": True,
    }
)

# Definir estados
states = {
    "draft": {
        "description": "Solicitud siendo preparada por el solicitante",
        "can_edit": True,
        "public_visible": False,
    },
    "submitted": {
        "description": "Presentada, pendiente de pago de tarifa",
        "can_edit": False,
        "public_visible": False,
    },
    "fee_paid": {
        "description": "Tarifa pagada, pendiente de revision inicial",
        "can_edit": False,
        "public_visible": True,
    },
    "plan_check": {
        "description": "Planos bajo revision tecnica",
        "can_edit": False,
        "public_visible": True,
    },
    "corrections_required": {
        "description": "Se necesitan correcciones del solicitante",
        "can_edit": True,  # El solicitante puede actualizar
        "public_visible": True,
    },
    "corrections_submitted": {
        "description": "Correcciones presentadas, pendiente de re-revision",
        "can_edit": False,
        "public_visible": True,
    },
    "approved": {
        "description": "Solicitud aprobada, permiso emitido",
        "is_terminal": True,
        "public_visible": True,
    },
    "denied": {
        "description": "Solicitud denegada",
        "is_terminal": True,
        "public_visible": True,
    },
    "withdrawn": {
        "description": "Solicitud retirada por el solicitante",
        "is_terminal": True,
        "public_visible": True,
    },
    "expired": {
        "description": "Solicitud expirada por inactividad",
        "is_terminal": True,
        "public_visible": True,
    },
}

# Definir transiciones permitidas
transitions = {
    "draft": ["submitted", "withdrawn"],
    "submitted": ["fee_paid", "withdrawn"],
    "fee_paid": ["plan_check", "withdrawn"],
    "plan_check": ["corrections_required", "approved", "denied"],
    "corrections_required": ["corrections_submitted", "withdrawn", "expired"],
    "corrections_submitted": ["plan_check"],  # De vuelta a revision
}

building_workflow.metadata["states"] = states
building_workflow.metadata["transitions"] = transitions
building_workflow.save()
```

### Flujo de Trabajo de Varianza (Con Audiencia Publica)

```python
variance_workflow = EncounterDefinition.objects.create(
    name="Varianza de Zonificacion - Con Audiencia",
    code="variance_with_hearing",
    initial_state="draft",
    metadata={
        "permit_category": "planning",
        "requires_public_notice": True,
        "requires_hearing": True,
    }
)

variance_states = {
    "draft": {"description": "Solicitud siendo preparada"},
    "submitted": {"description": "Presentada, pendiente de verificacion de completitud"},
    "incomplete": {"description": "Faltan documentos requeridos"},
    "complete": {"description": "Solicitud completa, se requiere tarifa"},
    "fee_paid": {"description": "Tarifa pagada, pendiente de aviso publico"},
    "public_notice": {"description": "Periodo de aviso publico activo"},
    "public_comment": {"description": "Periodo de comentarios publicos abierto"},
    "staff_review": {"description": "Personal preparando recomendacion"},
    "hearing_scheduled": {"description": "Fecha de audiencia programada"},
    "hearing_held": {"description": "Audiencia completada, decision pendiente"},
    "approved": {"description": "Varianza aprobada", "is_terminal": True},
    "approved_with_conditions": {"description": "Aprobada con condiciones", "is_terminal": True},
    "denied": {"description": "Varianza denegada", "is_terminal": True},
    "withdrawn": {"description": "Retirada", "is_terminal": True},
}

variance_transitions = {
    "draft": ["submitted", "withdrawn"],
    "submitted": ["incomplete", "complete"],
    "incomplete": ["submitted", "withdrawn"],
    "complete": ["fee_paid", "withdrawn"],
    "fee_paid": ["public_notice"],
    "public_notice": ["public_comment"],
    "public_comment": ["staff_review"],
    "staff_review": ["hearing_scheduled"],
    "hearing_scheduled": ["hearing_held", "withdrawn"],
    "hearing_held": ["approved", "approved_with_conditions", "denied"],
}

variance_workflow.metadata["states"] = variance_states
variance_workflow.metadata["transitions"] = variance_transitions
variance_workflow.save()
```

### Creando una Solicitud

```python
from django_encounters.models import Encounter
from django_encounters.services import create_encounter

# Solicitante
applicant = Person.objects.create(
    full_name="Roberto Smith",
    email="rsmith@example.com",
    metadata={
        "phone": "555-0123",
        "address": "123 Main St, Springfield, IL",
    }
)

# Crear solicitud de permiso de construccion
application = create_encounter(
    definition=building_workflow,
    subject=applicant,
    metadata={
        "permit_type": "BLDG-RES-SFR",
        "project_address": "456 Oak Avenue",
        "project_description": "Nueva residencia unifamiliar, 220 m2",
        "parcel_number": "12-34-567-890",
        "estimated_cost": 450000,
        "square_footage": 2400,
        "stories": 2,
        "submitted_at": None,  # Se establecera al presentar
    }
)

# Registrar la creacion
log_event(
    target=application,
    event_type="application_created",
    actor=applicant,
    metadata={
        "permit_type": "BLDG-RES-SFR",
        "project_address": "456 Oak Avenue",
    }
)
```

---

## Documentos Adjuntos

Las solicitudes de permisos requieren documentos de soporte. Cada documento se rastrea con auditoria completa.

### Subiendo Documentos Requeridos

```python
from django_documents.models import Document
from django_documents.services import upload_document

# Plano del sitio
site_plan = upload_document(
    file=site_plan_file,
    document_type="site_plan",
    owner=applicant,
    target=application,
    metadata={
        "description": "Plano del sitio mostrando dimensiones del lote y ubicacion del edificio",
        "prepared_by": "ABC Engineering",
        "dated": "2024-01-15",
        "sheet_number": "A-1",
    }
)

# Planos de piso
floor_plans = upload_document(
    file=floor_plans_file,
    document_type="floor_plans",
    owner=applicant,
    target=application,
    metadata={
        "description": "Planos de primer y segundo piso",
        "prepared_by": "Smith Architecture",
        "sheets": ["A-2", "A-3"],
    }
)

# Calculos estructurales
structural = upload_document(
    file=structural_file,
    document_type="structural_calculations",
    owner=applicant,
    target=application,
    metadata={
        "description": "Calculos de ingenieria estructural",
        "engineer": "PE #12345",
        "dated": "2024-01-10",
    }
)

# Cada carga se registra automaticamente por django-documents
```

### Verificando Completitud de Documentos

```python
def check_required_documents(application):
    """Verificar si todos los documentos requeridos estan cargados."""
    permit_type = CatalogItem.objects.get(sku=application.metadata["permit_type"])
    required = permit_type.metadata.get("required_documents", [])

    uploaded = Document.objects.for_target(application).values_list(
        "document_type", flat=True
    ).distinct()

    missing = set(required) - set(uploaded)

    return {
        "complete": len(missing) == 0,
        "required": required,
        "uploaded": list(uploaded),
        "missing": list(missing),
    }

# Uso
completeness = check_required_documents(application)
if not completeness["complete"]:
    print(f"Documentos faltantes: {completeness['missing']}")
```

### Revision de Documentos

```python
def review_document(document, reviewer, status, notes=None):
    """Registrar revision de documento por personal."""
    log_event(
        target=document,
        event_type="document_reviewed",
        actor=reviewer,
        metadata={
            "status": status,  # "accepted", "rejected", "needs_revision"
            "notes": notes,
        }
    )

    # Tambien registrar en la solicitud
    log_event(
        target=document.target,
        event_type="document_reviewed",
        actor=reviewer,
        metadata={
            "document_id": str(document.id),
            "document_type": document.document_type,
            "status": status,
            "notes": notes,
        }
    )

    return document
```

---

## Flujo de Trabajo de Revision

Las solicitudes se mueven a traves de etapas de revision. Cada transicion se registra con el actor que la realizo.

### Presentando una Solicitud

```python
from django_encounters.services import transition_encounter

def submit_application(application, applicant):
    """Presentar solicitud para revision."""
    # Verificar completitud
    completeness = check_required_documents(application)
    if not completeness["complete"]:
        raise IncompleteApplicationError(
            f"Faltan documentos requeridos: {completeness['missing']}"
        )

    # Transicionar a presentada
    transition_encounter(
        encounter=application,
        to_state="submitted",
        actor=applicant,
        metadata={
            "submitted_at": timezone.now().isoformat(),
            "documents_count": len(completeness["uploaded"]),
        }
    )

    # Actualizar metadata de solicitud
    application.metadata["submitted_at"] = timezone.now().isoformat()
    application.save()

    # Registrar
    log_event(
        target=application,
        event_type="application_submitted",
        actor=applicant,
    )

    return application
```

### Asignando Revisores

```python
from django_catalog.models import WorkItem

def assign_reviewer(application, reviewer, department):
    """Asignar un revisor a una solicitud."""
    # Crear item de trabajo para el revisor
    work_item = WorkItem.objects.create(
        status="pending",
        assigned_to=reviewer,
        metadata={
            "application_id": str(application.id),
            "department": department,
            "assigned_at": timezone.now().isoformat(),
            "due_date": (timezone.now() + timedelta(days=14)).isoformat(),
        }
    )

    # Vincular a solicitud via GenericFK
    work_item.target = application
    work_item.save()

    log_event(
        target=application,
        event_type="reviewer_assigned",
        actor=None,  # Accion del sistema
        metadata={
            "reviewer_id": str(reviewer.id),
            "reviewer_name": reviewer.full_name,
            "department": department,
            "work_item_id": str(work_item.id),
        }
    )

    return work_item
```

### Moviéndose a Traves de la Revision

```python
def start_plan_check(application, reviewer):
    """Mover solicitud a estado de revision de planos."""
    # Verificar que el revisor tiene permiso
    if not user_has_permission(reviewer.user, "review_applications"):
        raise PermissionDenied("El usuario no puede revisar solicitudes")

    transition_encounter(
        encounter=application,
        to_state="plan_check",
        actor=reviewer,
        metadata={
            "started_by": str(reviewer.id),
            "started_at": timezone.now().isoformat(),
        }
    )

    # Marcar item de trabajo como en progreso
    work_item = WorkItem.objects.filter(
        target_id=str(application.id),
        assigned_to=reviewer,
        status="pending",
    ).first()

    if work_item:
        work_item.status = "in_progress"
        work_item.started_at = timezone.now()
        work_item.save()

def request_corrections(application, reviewer, corrections_list):
    """Solicitar correcciones al solicitante."""
    transition_encounter(
        encounter=application,
        to_state="corrections_required",
        actor=reviewer,
        metadata={
            "corrections": corrections_list,
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }
    )

    # Crear nota con detalles de correcciones
    from django_notes.services import create_note

    create_note(
        target=application,
        note_type="correction_request",
        content="\n".join(f"- {c}" for c in corrections_list),
        author=reviewer,
        metadata={
            "corrections": corrections_list,
            "response_due": (timezone.now() + timedelta(days=30)).isoformat(),
        }
    )

    log_event(
        target=application,
        event_type="corrections_requested",
        actor=reviewer,
        metadata={
            "corrections_count": len(corrections_list),
            "corrections": corrections_list,
        }
    )
```

---

## Decisiones

Cada aprobacion o rechazo es una Decision explicita con fundamento.

### Tomando una Decision de Aprobacion

```python
from django_decisioning.models import Decision
from django_decisioning.services import create_decision

def approve_application(application, approver, conditions=None):
    """Aprobar una solicitud de permiso."""
    # Verificar que el aprobador tiene autoridad
    if not user_has_permission(approver.user, "approve_applications"):
        raise PermissionDenied("El usuario no puede aprobar solicitudes")

    # Reunir inputs (que fue considerado)
    documents = Document.objects.for_target(application)
    review_notes = Note.objects.for_target(application).filter(
        note_type__in=["review_note", "correction_request"]
    )

    inputs = {
        "application_data": application.metadata,
        "documents_reviewed": [
            {"id": str(d.id), "type": d.document_type, "name": d.filename}
            for d in documents
        ],
        "review_notes": [
            {"author": str(n.author_id), "content": n.content[:200]}
            for n in review_notes
        ],
        "checklist": get_review_checklist(application),
    }

    # Crear registro de decision
    decision = create_decision(
        decision_type="permit_approval",
        target=application,
        actor=approver,
        inputs=inputs,
        outcome="approved" if not conditions else "approved_with_conditions",
        rationale=f"La solicitud cumple todos los requisitos para {application.metadata['permit_type']}.",
        effective_at=timezone.now(),
        metadata={
            "conditions": conditions or [],
            "permit_number": generate_permit_number(),
        }
    )

    # Transicionar solicitud
    transition_encounter(
        encounter=application,
        to_state="approved" if not conditions else "approved_with_conditions",
        actor=approver,
        metadata={
            "decision_id": str(decision.id),
            "permit_number": decision.metadata["permit_number"],
        }
    )

    # Emitir el permiso como un Agreement
    permit = issue_permit(application, decision)

    log_event(
        target=application,
        event_type="application_approved",
        actor=approver,
        metadata={
            "decision_id": str(decision.id),
            "permit_id": str(permit.id),
            "permit_number": decision.metadata["permit_number"],
            "conditions": conditions,
        }
    )

    return decision, permit
```

### Tomando una Decision de Denegacion

```python
def deny_application(application, approver, reasons):
    """Denegar una solicitud de permiso."""
    if not user_has_permission(approver.user, "reject_applications"):
        raise PermissionDenied("El usuario no puede rechazar solicitudes")

    # Reunir inputs
    documents = Document.objects.for_target(application)

    inputs = {
        "application_data": application.metadata,
        "documents_reviewed": [str(d.id) for d in documents],
        "denial_reasons": reasons,
    }

    decision = create_decision(
        decision_type="permit_denial",
        target=application,
        actor=approver,
        inputs=inputs,
        outcome="denied",
        rationale="\n".join(f"- {r}" for r in reasons),
        effective_at=timezone.now(),
        metadata={
            "reasons": reasons,
            "appeal_deadline": (timezone.now() + timedelta(days=30)).isoformat(),
        }
    )

    transition_encounter(
        encounter=application,
        to_state="denied",
        actor=approver,
        metadata={
            "decision_id": str(decision.id),
            "reasons": reasons,
        }
    )

    log_event(
        target=application,
        event_type="application_denied",
        actor=approver,
        metadata={
            "decision_id": str(decision.id),
            "reasons": reasons,
        }
    )

    return decision
```

### Consultando Decisiones

```python
# Quien aprobo esta solicitud?
approval = Decision.objects.filter(
    target_id=str(application.id),
    decision_type="permit_approval",
    outcome__in=["approved", "approved_with_conditions"],
).first()

if approval:
    print(f"Aprobado por: {approval.actor.full_name}")
    print(f"En: {approval.effective_at}")
    print(f"Fundamento: {approval.rationale}")
    print(f"Inputs considerados: {approval.inputs}")

# Todas las decisiones por este aprobador
approver_decisions = Decision.objects.filter(
    actor=approver,
    decision_type__startswith="permit_",
).order_by("-effective_at")

# Decisiones tomadas en rango de fechas
decisions_this_month = Decision.objects.filter(
    effective_at__gte=month_start,
    effective_at__lt=month_end,
)
```

---

## Emitiendo Permisos

Un permiso aprobado se convierte en un Agreement - una concesion formal de permiso con terminos.

### Creando el Acuerdo de Permiso

```python
from django_agreements.models import Agreement, AgreementParty

def issue_permit(application, decision):
    """Emitir un permiso como un Agreement."""
    permit_type = CatalogItem.objects.get(sku=application.metadata["permit_type"])

    # Periodo de validez (1 ano para permiso de construccion)
    valid_from = timezone.now()
    valid_to = valid_from + timedelta(days=365)

    permit = Agreement.objects.create(
        agreement_type="permit",
        status="active",
        valid_from=valid_from,
        valid_to=valid_to,
        metadata={
            "permit_number": decision.metadata["permit_number"],
            "permit_type": permit_type.sku,
            "permit_name": permit_type.name,
            "application_id": str(application.id),
            "decision_id": str(decision.id),
            "project_address": application.metadata["project_address"],
            "project_description": application.metadata["project_description"],
            "conditions": decision.metadata.get("conditions", []),
            "issued_at": timezone.now().isoformat(),
            "issued_by": str(decision.actor.id),
        }
    )

    # El solicitante es titular del permiso
    applicant = application.subject
    AgreementParty.objects.create(
        agreement=permit,
        party=applicant,
        role="permit_holder",
    )

    # Agencia emisora
    agency = Organization.objects.get(id=permit_type.metadata["department_id"])
    AgreementParty.objects.create(
        agreement=permit,
        party=agency,
        role="issuing_authority",
    )

    log_event(
        target=permit,
        event_type="permit_issued",
        actor=decision.actor,
        metadata={
            "application_id": str(application.id),
            "permit_number": decision.metadata["permit_number"],
        }
    )

    return permit

def generate_permit_number():
    """Generar numero de permiso unico."""
    from django_sequence.services import next_value

    year = timezone.now().year
    seq = next_value(f"permit_{year}")
    return f"PLN-{year}-{seq:06d}"
```

### Consultando Permisos

```python
# Permisos activos para una propiedad
active_permits = Agreement.objects.filter(
    agreement_type="permit",
    status="active",
    metadata__project_address="456 Oak Avenue",
).current()

# Permisos emitidos este ano
permits_this_year = Agreement.objects.filter(
    agreement_type="permit",
    valid_from__year=2024,
)

# Permisos expirados (para cumplimiento)
expired_permits = Agreement.objects.filter(
    agreement_type="permit",
    status="active",
    valid_to__lt=timezone.now(),
)
```

---

## Comentarios Publicos

Algunos permisos requieren aviso publico y aceptan comentarios de ciudadanos.

### Periodo de Comentarios Publicos

```python
from django_notes.services import create_note

def open_public_comment(application, comment_period_days=30):
    """Abrir periodo de comentarios publicos para una solicitud."""
    end_date = timezone.now() + timedelta(days=comment_period_days)

    transition_encounter(
        encounter=application,
        to_state="public_comment",
        actor=None,  # Accion del sistema
        metadata={
            "comment_period_start": timezone.now().isoformat(),
            "comment_period_end": end_date.isoformat(),
        }
    )

    log_event(
        target=application,
        event_type="public_comment_opened",
        metadata={
            "end_date": end_date.isoformat(),
            "days": comment_period_days,
        }
    )

def submit_public_comment(application, commenter, comment_text, position=None):
    """Presentar un comentario publico sobre una solicitud."""
    # Verificar que el periodo de comentarios esta abierto
    if application.current_state != "public_comment":
        raise InvalidStateError("El periodo de comentarios publicos no esta abierto")

    comment = create_note(
        target=application,
        note_type="public_comment",
        content=comment_text,
        author=commenter,
        metadata={
            "position": position,  # "support", "oppose", "neutral"
            "submitted_at": timezone.now().isoformat(),
            "commenter_address": commenter.metadata.get("address"),
        }
    )

    log_event(
        target=application,
        event_type="public_comment_submitted",
        actor=commenter,
        metadata={
            "note_id": str(comment.id),
            "position": position,
            "content_preview": comment_text[:100],
        }
    )

    return comment
```

### Consultando Comentarios Publicos

```python
from django_notes.models import Note

# Todos los comentarios publicos sobre la solicitud
comments = Note.objects.for_target(application).filter(
    note_type="public_comment"
).order_by("created_at")

# Comentarios por posicion
support = comments.filter(metadata__position="support").count()
oppose = comments.filter(metadata__position="oppose").count()
neutral = comments.filter(metadata__position="neutral").count()

summary = {
    "total": comments.count(),
    "support": support,
    "oppose": oppose,
    "neutral": neutral,
}
```

---

## Procesamiento de Tarifas

Las tarifas de permisos son transacciones del libro mayor.

### Calculando Tarifas

```python
from decimal import Decimal
from django_ledger.models import Account, Transaction, Entry
from django_ledger.services import post_transaction

def calculate_permit_fee(application):
    """Calcular tarifa total para solicitud de permiso."""
    permit_type = CatalogItem.objects.get(sku=application.metadata["permit_type"])
    base_fee = permit_type.unit_price

    # Tarifa basada en formula (ej. por pie cuadrado)
    formula = permit_type.metadata.get("fee_formula", "base")

    if "sqft" in formula:
        sqft = application.metadata.get("square_footage", 0)
        rate = Decimal("0.25")  # $0.25 por pie cuadrado
        variable_fee = Decimal(sqft) * rate
    else:
        variable_fee = Decimal("0")

    total = base_fee + variable_fee

    return {
        "base_fee": base_fee,
        "variable_fee": variable_fee,
        "total": total,
        "breakdown": [
            {"description": "Tarifa base de permiso", "amount": base_fee},
            {"description": f"Revision de planos ({sqft} pies2 @ $0.25)", "amount": variable_fee},
        ]
    }
```

### Registrando Pago de Tarifa

```python
# Cuentas
permit_fees = Account.objects.get(code="4300")  # Ingresos
cash = Account.objects.get(code="1000")  # Activo

def record_permit_fee(application, payment_method, payment_ref):
    """Registrar pago de tarifa de permiso."""
    fee = calculate_permit_fee(application)

    payment = Transaction.objects.create(
        transaction_type="permit_fee",
        effective_at=timezone.now(),
        metadata={
            "application_id": str(application.id),
            "permit_type": application.metadata["permit_type"],
            "fee_breakdown": fee["breakdown"],
            "payment_method": payment_method,
            "payment_ref": payment_ref,
        }
    )

    Entry.objects.create(
        transaction=payment,
        account=cash,
        amount=fee["total"],
        entry_type="debit",
        description=f"Tarifa de permiso: {application.metadata['permit_type']}",
    )

    Entry.objects.create(
        transaction=payment,
        account=permit_fees,
        amount=fee["total"],
        entry_type="credit",
        description=f"Tarifa de permiso: {application.metadata['permit_type']}",
    )

    post_transaction(payment)

    # Transicionar solicitud
    transition_encounter(
        encounter=application,
        to_state="fee_paid",
        actor=application.subject,
        metadata={
            "payment_id": str(payment.id),
            "amount": str(fee["total"]),
        }
    )

    log_event(
        target=application,
        event_type="fee_paid",
        actor=application.subject,
        metadata={
            "payment_id": str(payment.id),
            "amount": str(fee["total"]),
        }
    )

    return payment
```

### Procesamiento de Reembolsos

```python
def refund_permit_fee(application, reason, refund_amount=None):
    """Procesar reembolso para solicitud retirada o denegada."""
    # Encontrar pago original
    original = Transaction.objects.filter(
        transaction_type="permit_fee",
        metadata__application_id=str(application.id),
    ).first()

    if not original:
        raise ValueError("No se encontro pago de tarifa para esta solicitud")

    # Calcular reembolso (puede ser parcial)
    original_amount = original.entries.filter(entry_type="debit").first().amount

    if refund_amount is None:
        # Reembolso completo si no se especifica
        refund_amount = original_amount

    # Crear transaccion de reembolso
    refund = Transaction.objects.create(
        transaction_type="permit_fee_refund",
        effective_at=timezone.now(),
        metadata={
            "application_id": str(application.id),
            "original_payment_id": str(original.id),
            "reason": reason,
            "refund_type": "full" if refund_amount == original_amount else "partial",
        }
    )

    # Revertir las entradas
    Entry.objects.create(
        transaction=refund,
        account=permit_fees,
        amount=refund_amount,
        entry_type="debit",
        description=f"Reembolso: {reason}",
    )

    Entry.objects.create(
        transaction=refund,
        account=cash,
        amount=refund_amount,
        entry_type="credit",
        description=f"Reembolso: {reason}",
    )

    post_transaction(refund)

    log_event(
        target=application,
        event_type="fee_refunded",
        metadata={
            "refund_id": str(refund.id),
            "amount": str(refund_amount),
            "reason": reason,
        }
    )

    return refund
```

---

## Pista de Auditoria Completa

Los sistemas gubernamentales requieren pistas de auditoria completas e inmutables.

### Consultando Historial de Solicitud

```python
def get_complete_audit_trail(application):
    """Obtener historial completo de una solicitud."""
    from django_audit_log.models import AuditLog

    events = AuditLog.objects.for_target(application).order_by("created_at")

    trail = []
    for event in events:
        trail.append({
            "timestamp": event.created_at,
            "event_type": event.event_type,
            "actor": str(event.actor_id) if event.actor_id else "Sistema",
            "actor_repr": event.actor_repr,
            "details": event.metadata,
        })

    # Tambien obtener eventos de documentos
    documents = Document.objects.for_target(application)
    for doc in documents:
        doc_events = AuditLog.objects.for_target(doc)
        for event in doc_events:
            trail.append({
                "timestamp": event.created_at,
                "event_type": f"document:{event.event_type}",
                "actor": str(event.actor_id) if event.actor_id else "Sistema",
                "details": event.metadata,
            })

    # Ordenar por timestamp
    trail.sort(key=lambda x: x["timestamp"])

    return trail

# Uso
trail = get_complete_audit_trail(application)
for entry in trail:
    print(f"{entry['timestamp']}: {entry['event_type']} por {entry['actor']}")
```

### Consulta de Registros Publicos

```python
def generate_public_record(application):
    """Generar registro publico para solicitud FOIA."""
    # Obtener todos los eventos no confidenciales
    events = AuditLog.objects.for_target(application).filter(
        event_type__in=[
            "application_created",
            "application_submitted",
            "reviewer_assigned",
            "corrections_requested",
            "corrections_submitted",
            "public_comment_opened",
            "public_comment_submitted",
            "application_approved",
            "application_denied",
            "permit_issued",
        ]
    ).order_by("created_at")

    # Obtener decisiones
    decisions = Decision.objects.filter(
        target_id=str(application.id),
    ).order_by("effective_at")

    # Obtener comentarios publicos
    comments = Note.objects.for_target(application).filter(
        note_type="public_comment",
    )

    # Compilar registro
    record = {
        "application": {
            "id": str(application.id),
            "permit_type": application.metadata["permit_type"],
            "project_address": application.metadata["project_address"],
            "submitted_at": application.metadata.get("submitted_at"),
            "current_status": application.current_state,
        },
        "timeline": [
            {
                "date": e.created_at.isoformat(),
                "event": e.event_type,
                "actor": e.actor_repr,
            }
            for e in events
        ],
        "decisions": [
            {
                "date": d.effective_at.isoformat(),
                "type": d.decision_type,
                "outcome": d.outcome,
                "rationale": d.rationale,
                "decided_by": d.actor.full_name,
            }
            for d in decisions
        ],
        "public_comments": [
            {
                "date": c.created_at.isoformat(),
                "position": c.metadata.get("position"),
                "content": c.content,
            }
            for c in comments
        ],
    }

    return record
```

---

## Prompt Completo de Reconstruccion

```markdown
# Prompt: Reconstruir Flujo de Trabajo de Permisos Gubernamentales

## Instruccion

Construir un sistema de solicitud de permisos gubernamentales componiendo estas primitivas:
- django-parties (solicitantes, agencias, revisores)
- django-catalog (tipos de permiso, requisitos)
- django-encounters (flujo de trabajo de solicitud)
- django-decisioning (decisiones de aprobacion)
- django-documents (adjuntos requeridos)
- django-notes (comentarios publicos)
- django-ledger (tarifas)
- django-agreements (permisos emitidos)
- django-audit-log (pista completa)
- django-rbac (permisos de revisor)

## Proposito del Dominio

Permitir a las agencias gubernamentales:
- Aceptar y procesar solicitudes de permisos
- Enrutar solicitudes a traves de flujos de revision
- Registrar decisiones explicitas con fundamento
- Aceptar comentarios publicos sobre solicitudes
- Emitir permisos como acuerdos formales
- Mantener pista de auditoria completa para registros publicos

## SIN NUEVOS MODELOS

No crear ningun nuevo modelo Django. Toda la funcionalidad de permisos
se implementa componiendo primitivas existentes.

## Composicion de Primitivas

### Parties
- Person = Solicitante o revisor individual
- Organization = Agencia o departamento
- PartyRelationship = Estructura de departamento, asignaciones de personal

### Tipos de Permiso
- Category = Categorias de permiso (construccion, planificacion, negocios)
- CatalogItem = Tipo de permiso especifico con requisitos y tarifas

### Solicitudes
- Encounter = La instancia de solicitud
- EncounterDefinition = Estados y transiciones del flujo de trabajo
- EncounterTransition = Cambio de estado con actor y timestamp

### Proceso de Revision
- WorkItem = Asignacion de revisor
- Decision = Aprobacion/denegacion con fundamento completo

### Documentos
- Document = Adjunto cargado con metadata
- AuditLog = Eventos de revision/aceptacion de documentos

### Entrada Publica
- Note (note_type="public_comment") = Comentarios de ciudadanos

### Tarifas
- Transaction = Pago de tarifa
- Entry = Debitar efectivo, acreditar ingresos

### Permisos Emitidos
- Agreement = Permiso que otorga autorizacion
- AgreementParty = Titular del permiso y agencia emisora

### Pista de Auditoria
- AuditLog = Cada accion sobre la solicitud
- Todos los eventos inmutables y consultables

## Funciones de Servicio

### submit_application()
```python
def submit_application(
    application: Encounter,
    applicant: Person,
) -> Encounter:
    """Presentar solicitud completada para revision."""
```

### assign_reviewer()
```python
def assign_reviewer(
    application: Encounter,
    reviewer: Person,
    department: str,
) -> WorkItem:
    """Asignar revisor a solicitud."""
```

### approve_application()
```python
def approve_application(
    application: Encounter,
    approver: Person,
    conditions: list[str] = None,
) -> tuple[Decision, Agreement]:
    """Aprobar solicitud y emitir permiso."""
```

### deny_application()
```python
def deny_application(
    application: Encounter,
    approver: Person,
    reasons: list[str],
) -> Decision:
    """Denegar solicitud con razones."""
```

### submit_public_comment()
```python
def submit_public_comment(
    application: Encounter,
    commenter: Person,
    comment_text: str,
    position: str,  # support, oppose, neutral
) -> Note:
    """Presentar comentario publico durante periodo de comentarios."""
```

### get_audit_trail()
```python
def get_audit_trail(
    application: Encounter,
) -> list[dict]:
    """Obtener pista de auditoria completa para FOIA."""
```

## Casos de Prueba (48 pruebas)

### Pruebas de Estructura de Agencia (6 pruebas)
1. test_create_agency
2. test_create_department
3. test_assign_staff_to_department
4. test_staff_roles
5. test_reviewer_permissions
6. test_department_hierarchy

### Pruebas de Tipo de Permiso (6 pruebas)
7. test_create_permit_category
8. test_create_permit_type
9. test_permit_required_documents
10. test_permit_fee_calculation
11. test_permit_workflow_assignment
12. test_permit_type_metadata

### Pruebas de Flujo de Trabajo de Solicitud (12 pruebas)
13. test_create_application
14. test_submit_application
15. test_document_upload
16. test_document_completeness_check
17. test_assign_reviewer
18. test_start_plan_check
19. test_request_corrections
20. test_submit_corrections
21. test_approve_application
22. test_deny_application
23. test_withdraw_application
24. test_workflow_transitions

### Pruebas de Decision (8 pruebas)
25. test_approval_decision
26. test_denial_decision
27. test_decision_captures_inputs
28. test_decision_rationale_required
29. test_decision_immutable
30. test_query_decisions_by_actor
31. test_query_decisions_by_date
32. test_conditional_approval

### Pruebas de Comentarios Publicos (6 pruebas)
33. test_open_comment_period
34. test_submit_comment
35. test_comment_position
36. test_query_comments
37. test_comment_summary
38. test_close_comment_period

### Pruebas de Tarifa (6 pruebas)
39. test_calculate_base_fee
40. test_calculate_variable_fee
41. test_record_payment
42. test_refund_full
43. test_refund_partial
44. test_fee_ledger_entries

### Pruebas de Emision de Permiso (4 pruebas)
45. test_issue_permit
46. test_permit_has_parties
47. test_permit_validity_period
48. test_query_active_permits

## Comportamientos Clave

1. **Las solicitudes son Encounters** - Maquina de estados con transiciones
2. **Las decisiones son explicitas** - Capturadas con inputs, outcome, rationale
3. **Los permisos son Agreements** - Concesion formal con periodo de validez
4. **La pista de auditoria es inmutable** - Cada accion registrada, nada eliminado
5. **Los comentarios publicos via Notes** - Consultables por posicion
6. **Las tarifas via Ledger** - Contabilidad de doble entrada apropiada

## Criterios de Aceptacion

- [ ] Sin nuevos modelos Django creados
- [ ] Las solicitudes usan Encounter con flujo de trabajo apropiado
- [ ] Las decisiones capturan inputs y fundamento
- [ ] Los permisos usan Agreement con relaciones de party
- [ ] Pista de auditoria completa para cumplimiento FOIA
- [ ] Los comentarios publicos consultables
- [ ] Las tarifas usan transacciones de libro mayor
- [ ] Las 48 pruebas pasando
- [ ] README con ejemplos de flujo de trabajo
```

---

## Ejercicio Practico: Construir Dashboard de Permisos

Crear dashboards para solicitantes y revisores.

**Paso 1: Dashboard del Solicitante**

```python
def get_applicant_dashboard(applicant):
    """Obtener datos del dashboard para solicitante."""
    applications = Encounter.objects.filter(
        subject=applicant,
        definition__metadata__permit_category__isnull=False,
    ).order_by("-created_at")

    return {
        "applications": [
            {
                "id": str(app.id),
                "permit_type": app.metadata["permit_type"],
                "project_address": app.metadata["project_address"],
                "status": app.current_state,
                "submitted_at": app.metadata.get("submitted_at"),
                "last_updated": app.updated_at,
            }
            for app in applications
        ],
        "active_count": applications.exclude(
            current_state__in=["approved", "denied", "withdrawn"]
        ).count(),
        "approved_count": applications.filter(current_state="approved").count(),
    }
```

**Paso 2: Cola de Revisor**

```python
def get_reviewer_queue(reviewer):
    """Obtener cola de revision para miembro del personal."""
    assignments = WorkItem.objects.filter(
        assigned_to=reviewer,
        status__in=["pending", "in_progress"],
    ).order_by("created_at")

    queue = []
    for item in assignments:
        application = Encounter.objects.get(id=item.target_id)
        queue.append({
            "work_item_id": str(item.id),
            "application_id": str(application.id),
            "permit_type": application.metadata["permit_type"],
            "project_address": application.metadata["project_address"],
            "submitted_at": application.metadata.get("submitted_at"),
            "days_waiting": (timezone.now() - item.created_at).days,
            "due_date": item.metadata.get("due_date"),
            "status": item.status,
        })

    return {
        "queue": queue,
        "pending": len([q for q in queue if q["status"] == "pending"]),
        "in_progress": len([q for q in queue if q["status"] == "in_progress"]),
        "overdue": len([q for q in queue if q["days_waiting"] > 14]),
    }
```

**Paso 3: Estadisticas del Departamento**

```python
def get_department_stats(department, period_start, period_end):
    """Obtener estadisticas de procesamiento para departamento."""
    # Solicitudes recibidas
    received = Encounter.objects.filter(
        definition__metadata__department_id=str(department.id),
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).count()

    # Decisiones tomadas
    decisions = Decision.objects.filter(
        actor__partyrelationship__to_party=department,
        effective_at__gte=period_start,
        effective_at__lt=period_end,
    )

    approved = decisions.filter(outcome__startswith="approved").count()
    denied = decisions.filter(outcome="denied").count()

    # Tiempo promedio de procesamiento
    completed = Encounter.objects.filter(
        definition__metadata__department_id=str(department.id),
        current_state__in=["approved", "denied"],
        updated_at__gte=period_start,
        updated_at__lt=period_end,
    )

    processing_times = []
    for app in completed:
        submitted = app.metadata.get("submitted_at")
        if submitted:
            submitted_dt = datetime.fromisoformat(submitted)
            processing_times.append((app.updated_at - submitted_dt).days)

    avg_days = sum(processing_times) / len(processing_times) if processing_times else 0

    return {
        "period": f"{period_start} a {period_end}",
        "received": received,
        "approved": approved,
        "denied": denied,
        "approval_rate": (approved / (approved + denied) * 100) if (approved + denied) > 0 else 0,
        "average_processing_days": avg_days,
    }
```

---

## Lo Que la IA Se Equivoca Sobre Flujos de Trabajo Gubernamentales

### Asumir Que Las Ediciones Son Aceptables

La IA puede permitir editar solicitudes presentadas:

```python
# MAL
def update_application(application, new_data):
    application.metadata.update(new_data)
    application.save()
```

**Por que esta mal:** Una vez presentada, el registro oficial no puede ser modificado. Solo correcciones a traves del proceso formal.

**Solucion:** Usar maquina de estados. Las correcciones requieren transicion al estado "corrections_required" con registro completo.

### Omitir Fundamento de Decision

La IA puede registrar decisiones sin explicacion:

```python
# MAL
Decision.objects.create(
    target=application,
    outcome="denied",
    # Sin rationale, sin inputs capturados
)
```

**Por que esta mal:** Las decisiones gubernamentales deben ser explicables. "Por que fue denegado esto?" requiere una respuesta.

**Solucion:** Siempre capturar inputs, rationale y actor. El modelo Decision requiere estos campos.

### Soft-Delete de Registros de Auditoria

La IA puede intentar "limpiar" registros viejos:

```python
# MAL
AuditLog.objects.filter(created_at__lt=three_years_ago).delete()
```

**Por que esta mal:** Las leyes de registros publicos requieren retencion. Eliminar destruye evidencia legal.

**Solucion:** Los logs de auditoria son inmutables y nunca se eliminan. Archivar en almacenamiento frio si es necesario.

### Asignacion Directa de Estado

La IA puede evadir la maquina de estados:

```python
# MAL
application.current_state = "approved"
application.save()
```

**Por que esta mal:** Pierde historial de transicion. Ningun actor registrado. Pista de auditoria rota.

**Solucion:** Siempre usar `transition_encounter()` que crea registro EncounterTransition.

---

## Por Que Esto Importa

La periodista de la historia inicial eventualmente obtuvo su respuesta - del nuevo sistema de permisos:

```python
# Consulta: Quien aprobo esta varianza?
decision = Decision.objects.filter(
    target_id=str(variance_application.id),
    outcome__startswith="approved",
).first()

print(f"Aprobado por: {decision.actor.full_name}")
print(f"En: {decision.effective_at}")
print(f"Fundamento: {decision.rationale}")
print(f"Documentos revisados: {decision.inputs['documents_reviewed']}")
```

El nuevo sistema podia responder:
- Quien tomo la decision
- Cuando la tomaron
- Que consideraron
- Por que decidieron como lo hicieron
- Cada paso desde la solicitud hasta la aprobacion

No mas "no podemos localizar registros completos." Los registros existen porque el sistema hace imposible omitir su registro.

---

## Resumen

| Concepto del Dominio | Primitiva | Insight Clave |
|---------------------|-----------|---------------|
| Solicitud | Encounter | Maquina de estados con transiciones registradas |
| Flujo de trabajo | EncounterDefinition | Estados y transiciones configurados, no codificados |
| Decision | Decision | Inputs, outcome, rationale todos capturados |
| Permiso | Agreement | Concesion formal con periodo de validez |
| Revision | WorkItem | Asignacion con fecha de vencimiento |
| Comentario | Note | Tipado para comentarios publicos |
| Tarifa | Transaction | Entradas de libro mayor apropiadas |
| Auditoria | AuditLog | Inmutable, completa, consultable |

Los flujos de trabajo gubernamentales son encuentros con decisiones. Cada accion se registra. Nada se elimina. Las primitivas imponen la responsabilidad.

Las mismas primitivas. Dominio de burocracia.

---

## Fuentes

- National Association of Counties. (2020). *Digital Transformation in Local Government*.
- Government Accountability Office. (2019). *Federal Records Management: Agencies Should Strengthen Controls*.
- International City/County Management Association. (2021). *Permit Management Best Practices Guide*.
