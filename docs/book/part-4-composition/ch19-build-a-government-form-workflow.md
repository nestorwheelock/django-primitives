# Chapter 19: Build a Government Form Workflow

## The Freedom of Information Request

In 2019, a journalist filed a public records request with a city planning department. She wanted to know who approved a controversial zoning variance, when they approved it, and what documents they reviewed.

The department's response: "We are unable to locate complete records for this application."

The variance had been approved two years earlier. The decision happened. The building was constructed. But the trail from application to approval was fragmentary—scattered across email threads, paper files, and an aging permit system that overwrote old states with new ones.

The city spent $1.8 million rebuilding their permit system. The new requirement was simple: every action must be recorded, every decision must be explained, and nothing can be deleted or modified.

This chapter builds that system. Same primitives. Bureaucracy domain.

---

## The Domain

A government permit application system needs:

- **Applicants and agencies** - who is applying and who is reviewing
- **Application forms** - different permit types with different requirements
- **Review workflows** - structured progression through stages
- **Approvals and rejections** - explicit decisions with rationale
- **Document attachments** - required supporting materials
- **Public comments** - citizen input on applications
- **Fees** - payment processing with refund handling
- **Audit trail** - immutable record of everything
- **Issued permits** - the final agreement granting permission

## Primitive Mapping

| Domain Concept | Primitive | Package |
|----------------|-----------|---------|
| Applicant | Party (Person/Org) | django-parties |
| Agency | Party (Organization) | django-parties |
| Department | PartyRelationship | django-parties |
| Reviewer | Party + Role | django-parties, django-rbac |
| Permit type | Category + CatalogItem | django-catalog |
| Application | Encounter | django-encounters |
| Review stages | EncounterDefinition | django-encounters |
| Stage transition | EncounterTransition | django-encounters |
| Reviewer assignment | WorkItem | django-catalog |
| Approval decision | Decision | django-decisioning |
| Attached documents | Document | django-documents |
| Public comments | Note | django-notes |
| Application fee | Transaction | django-ledger |
| Issued permit | Agreement | django-agreements |
| All activity | AuditLog | django-audit-log |

Zero new models. Government workflows are compositions of existing primitives with stricter audit requirements.

---

## Agencies and Departments

Government organizations have hierarchical structure. Reviewers belong to departments within agencies.

### Agency Structure

```python
from django_parties.models import Organization, Person, PartyRelationship

# City government
city = Organization.objects.create(
    name="City of Springfield",
    organization_type="government",
    metadata={
        "jurisdiction": "municipal",
        "state": "IL",
    }
)

# Planning department
planning_dept = Organization.objects.create(
    name="Planning and Zoning Department",
    organization_type="department",
    metadata={
        "agency_code": "PLZ",
        "parent_agency_id": str(city.id),
    }
)

# Relationship: Department belongs to City
PartyRelationship.objects.create(
    from_party=planning_dept,
    to_party=city,
    relationship_type="department_of",
    valid_from=timezone.now(),
)

# Building department
building_dept = Organization.objects.create(
    name="Building and Safety Department",
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

### Reviewers and Roles

```python
from django_rbac.models import Role, Permission, UserRole

# Permissions
can_review = Permission.objects.create(
    code="review_applications",
    name="Review Applications",
    description="Can review and add comments to applications",
)

can_approve = Permission.objects.create(
    code="approve_applications",
    name="Approve Applications",
    description="Can make final approval decisions",
)

can_reject = Permission.objects.create(
    code="reject_applications",
    name="Reject Applications",
    description="Can reject applications",
)

can_request_info = Permission.objects.create(
    code="request_additional_info",
    name="Request Additional Information",
    description="Can request more documents from applicant",
)

# Roles
reviewer_role = Role.objects.create(
    name="Application Reviewer",
    code="reviewer",
)
reviewer_role.permissions.add(can_review, can_request_info)

approver_role = Role.objects.create(
    name="Application Approver",
    code="approver",
)
approver_role.permissions.add(can_review, can_approve, can_reject, can_request_info)

# Assign staff to department with role
planner = Person.objects.create(
    full_name="Sarah Chen",
    email="sarah.chen@springfield.gov",
    metadata={
        "employee_id": "PLZ-1042",
        "title": "Senior Planner",
    }
)

PartyRelationship.objects.create(
    from_party=planner,
    to_party=planning_dept,
    relationship_type="employee",
    valid_from=date(2018, 3, 15),
)

# Grant reviewer role
UserRole.objects.create(
    user=planner_user,  # Django User linked to planner
    role=approver_role,
    valid_from=timezone.now(),
)
```

### Querying Department Staff

```python
# Current staff in planning department
current_staff = PartyRelationship.objects.filter(
    to_party=planning_dept,
    relationship_type="employee",
).current()

# Staff with approval authority
approvers = UserRole.objects.filter(
    role__permissions__code="approve_applications",
    user__party__partyrelationship__to_party=planning_dept,
).current()

# Who had approval authority on the date the decision was made?
approvers_then = UserRole.objects.filter(
    role__permissions__code="approve_applications",
).as_of(decision_date)
```

---

## Permit Types as Catalog

Different permits have different requirements, fees, and workflows.

### Permit Categories

```python
from django_catalog.models import Category, CatalogItem
from decimal import Decimal

# Categories by department
building_permits = Category.objects.create(
    name="Building Permits",
    code="building",
    metadata={
        "department_id": str(building_dept.id),
        "typical_review_days": 30,
    }
)

planning_permits = Category.objects.create(
    name="Planning Permits",
    code="planning",
    metadata={
        "department_id": str(planning_dept.id),
        "typical_review_days": 45,
    }
)

# Subcategories
residential_building = Category.objects.create(
    name="Residential Building",
    code="residential_building",
    parent=building_permits,
)

commercial_building = Category.objects.create(
    name="Commercial Building",
    code="commercial_building",
    parent=building_permits,
)
```

### Permit Type Definitions

```python
# Residential building permit
residential_permit = CatalogItem.objects.create(
    category=residential_building,
    name="Single Family Residence Permit",
    sku="BLDG-RES-SFR",
    unit_price=Decimal("450.00"),  # Base fee
    currency="USD",
    metadata={
        "description": "New construction of single family residence",
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
        "fee_formula": "base + (sqft * 0.25)",  # $0.25 per sq ft
    }
)

# Zoning variance
variance_permit = CatalogItem.objects.create(
    category=planning_permits,
    name="Zoning Variance",
    sku="PLN-VAR",
    unit_price=Decimal("1500.00"),
    currency="USD",
    metadata={
        "description": "Request for variance from zoning requirements",
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

# Business license
business_license = CatalogItem.objects.create(
    category=planning_permits,
    name="Business License",
    sku="PLN-BIZ",
    unit_price=Decimal("150.00"),
    currency="USD",
    metadata={
        "description": "License to operate a business at specified location",
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

## Applications as Encounters

A permit application is an encounter that progresses through defined stages.

### Workflow Definition

```python
from django_encounters.models import EncounterDefinition, EncounterValidator

# Standard building permit workflow
building_workflow = EncounterDefinition.objects.create(
    name="Building Permit - Standard",
    code="building_permit_standard",
    initial_state="draft",
    metadata={
        "permit_category": "building",
        "auto_assign_reviewers": True,
    }
)

# Define states
states = {
    "draft": {
        "description": "Application being prepared by applicant",
        "can_edit": True,
        "public_visible": False,
    },
    "submitted": {
        "description": "Submitted, pending fee payment",
        "can_edit": False,
        "public_visible": False,
    },
    "fee_paid": {
        "description": "Fee paid, pending initial review",
        "can_edit": False,
        "public_visible": True,
    },
    "plan_check": {
        "description": "Plans under technical review",
        "can_edit": False,
        "public_visible": True,
    },
    "corrections_required": {
        "description": "Corrections needed from applicant",
        "can_edit": True,  # Applicant can update
        "public_visible": True,
    },
    "corrections_submitted": {
        "description": "Corrections submitted, pending re-review",
        "can_edit": False,
        "public_visible": True,
    },
    "approved": {
        "description": "Application approved, permit issued",
        "is_terminal": True,
        "public_visible": True,
    },
    "denied": {
        "description": "Application denied",
        "is_terminal": True,
        "public_visible": True,
    },
    "withdrawn": {
        "description": "Application withdrawn by applicant",
        "is_terminal": True,
        "public_visible": True,
    },
    "expired": {
        "description": "Application expired due to inactivity",
        "is_terminal": True,
        "public_visible": True,
    },
}

# Define allowed transitions
transitions = {
    "draft": ["submitted", "withdrawn"],
    "submitted": ["fee_paid", "withdrawn"],
    "fee_paid": ["plan_check", "withdrawn"],
    "plan_check": ["corrections_required", "approved", "denied"],
    "corrections_required": ["corrections_submitted", "withdrawn", "expired"],
    "corrections_submitted": ["plan_check"],  # Back to review
}

building_workflow.metadata["states"] = states
building_workflow.metadata["transitions"] = transitions
building_workflow.save()
```

### Variance Workflow (With Public Hearing)

```python
variance_workflow = EncounterDefinition.objects.create(
    name="Zoning Variance - With Hearing",
    code="variance_with_hearing",
    initial_state="draft",
    metadata={
        "permit_category": "planning",
        "requires_public_notice": True,
        "requires_hearing": True,
    }
)

variance_states = {
    "draft": {"description": "Application being prepared"},
    "submitted": {"description": "Submitted, pending completeness check"},
    "incomplete": {"description": "Missing required documents"},
    "complete": {"description": "Application complete, fee required"},
    "fee_paid": {"description": "Fee paid, pending public notice"},
    "public_notice": {"description": "Public notice period active"},
    "public_comment": {"description": "Public comment period open"},
    "staff_review": {"description": "Staff preparing recommendation"},
    "hearing_scheduled": {"description": "Hearing date set"},
    "hearing_held": {"description": "Hearing completed, decision pending"},
    "approved": {"description": "Variance approved", "is_terminal": True},
    "approved_with_conditions": {"description": "Approved with conditions", "is_terminal": True},
    "denied": {"description": "Variance denied", "is_terminal": True},
    "withdrawn": {"description": "Withdrawn", "is_terminal": True},
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

### Creating an Application

```python
from django_encounters.models import Encounter
from django_encounters.services import create_encounter

# Applicant
applicant = Person.objects.create(
    full_name="Robert Smith",
    email="rsmith@example.com",
    metadata={
        "phone": "555-0123",
        "address": "123 Main St, Springfield, IL",
    }
)

# Create building permit application
application = create_encounter(
    definition=building_workflow,
    subject=applicant,
    metadata={
        "permit_type": "BLDG-RES-SFR",
        "project_address": "456 Oak Avenue",
        "project_description": "New single family residence, 2,400 sq ft",
        "parcel_number": "12-34-567-890",
        "estimated_cost": 450000,
        "square_footage": 2400,
        "stories": 2,
        "submitted_at": None,  # Will be set on submission
    }
)

# Log the creation
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

## Document Attachments

Permit applications require supporting documents. Each document is tracked with full audit.

### Uploading Required Documents

```python
from django_documents.models import Document
from django_documents.services import upload_document

# Site plan
site_plan = upload_document(
    file=site_plan_file,
    document_type="site_plan",
    owner=applicant,
    target=application,
    metadata={
        "description": "Site plan showing lot dimensions and building placement",
        "prepared_by": "ABC Engineering",
        "dated": "2024-01-15",
        "sheet_number": "A-1",
    }
)

# Floor plans
floor_plans = upload_document(
    file=floor_plans_file,
    document_type="floor_plans",
    owner=applicant,
    target=application,
    metadata={
        "description": "First and second floor plans",
        "prepared_by": "Smith Architecture",
        "sheets": ["A-2", "A-3"],
    }
)

# Structural calculations
structural = upload_document(
    file=structural_file,
    document_type="structural_calculations",
    owner=applicant,
    target=application,
    metadata={
        "description": "Structural engineering calculations",
        "engineer": "PE #12345",
        "dated": "2024-01-10",
    }
)

# Each upload is logged automatically by django-documents
```

### Checking Document Completeness

```python
def check_required_documents(application):
    """Check if all required documents are uploaded."""
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

# Usage
completeness = check_required_documents(application)
if not completeness["complete"]:
    print(f"Missing documents: {completeness['missing']}")
```

### Document Review

```python
def review_document(document, reviewer, status, notes=None):
    """Record document review by staff."""
    log_event(
        target=document,
        event_type="document_reviewed",
        actor=reviewer,
        metadata={
            "status": status,  # "accepted", "rejected", "needs_revision"
            "notes": notes,
        }
    )

    # Also log on the application
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

## Review Workflow

Applications move through review stages. Each transition is recorded with the actor who made it.

### Submitting an Application

```python
from django_encounters.services import transition_encounter

def submit_application(application, applicant):
    """Submit application for review."""
    # Check completeness
    completeness = check_required_documents(application)
    if not completeness["complete"]:
        raise IncompleteApplicationError(
            f"Missing required documents: {completeness['missing']}"
        )

    # Transition to submitted
    transition_encounter(
        encounter=application,
        to_state="submitted",
        actor=applicant,
        metadata={
            "submitted_at": timezone.now().isoformat(),
            "documents_count": len(completeness["uploaded"]),
        }
    )

    # Update application metadata
    application.metadata["submitted_at"] = timezone.now().isoformat()
    application.save()

    # Log
    log_event(
        target=application,
        event_type="application_submitted",
        actor=applicant,
    )

    return application
```

### Assigning Reviewers

```python
from django_catalog.models import WorkItem

def assign_reviewer(application, reviewer, department):
    """Assign a reviewer to an application."""
    # Create work item for the reviewer
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

    # Link to application via GenericFK
    work_item.target = application
    work_item.save()

    log_event(
        target=application,
        event_type="reviewer_assigned",
        actor=None,  # System action
        metadata={
            "reviewer_id": str(reviewer.id),
            "reviewer_name": reviewer.full_name,
            "department": department,
            "work_item_id": str(work_item.id),
        }
    )

    return work_item
```

### Moving Through Review

```python
def start_plan_check(application, reviewer):
    """Move application to plan check state."""
    # Verify reviewer has permission
    if not user_has_permission(reviewer.user, "review_applications"):
        raise PermissionDenied("User cannot review applications")

    transition_encounter(
        encounter=application,
        to_state="plan_check",
        actor=reviewer,
        metadata={
            "started_by": str(reviewer.id),
            "started_at": timezone.now().isoformat(),
        }
    )

    # Mark work item as in progress
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
    """Request corrections from applicant."""
    transition_encounter(
        encounter=application,
        to_state="corrections_required",
        actor=reviewer,
        metadata={
            "corrections": corrections_list,
            "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
        }
    )

    # Create note with correction details
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

## Decisions

Every approval or rejection is an explicit Decision with rationale.

### Making an Approval Decision

```python
from django_decisioning.models import Decision
from django_decisioning.services import create_decision

def approve_application(application, approver, conditions=None):
    """Approve a permit application."""
    # Verify approver has authority
    if not user_has_permission(approver.user, "approve_applications"):
        raise PermissionDenied("User cannot approve applications")

    # Gather inputs (what was considered)
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

    # Create decision record
    decision = create_decision(
        decision_type="permit_approval",
        target=application,
        actor=approver,
        inputs=inputs,
        outcome="approved" if not conditions else "approved_with_conditions",
        rationale=f"Application meets all requirements for {application.metadata['permit_type']}.",
        effective_at=timezone.now(),
        metadata={
            "conditions": conditions or [],
            "permit_number": generate_permit_number(),
        }
    )

    # Transition application
    transition_encounter(
        encounter=application,
        to_state="approved" if not conditions else "approved_with_conditions",
        actor=approver,
        metadata={
            "decision_id": str(decision.id),
            "permit_number": decision.metadata["permit_number"],
        }
    )

    # Issue the permit as an Agreement
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

### Making a Denial Decision

```python
def deny_application(application, approver, reasons):
    """Deny a permit application."""
    if not user_has_permission(approver.user, "reject_applications"):
        raise PermissionDenied("User cannot reject applications")

    # Gather inputs
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

### Querying Decisions

```python
# Who approved this application?
approval = Decision.objects.filter(
    target_id=str(application.id),
    decision_type="permit_approval",
    outcome__in=["approved", "approved_with_conditions"],
).first()

if approval:
    print(f"Approved by: {approval.actor.full_name}")
    print(f"On: {approval.effective_at}")
    print(f"Rationale: {approval.rationale}")
    print(f"Inputs considered: {approval.inputs}")

# All decisions by this approver
approver_decisions = Decision.objects.filter(
    actor=approver,
    decision_type__startswith="permit_",
).order_by("-effective_at")

# Decisions made in date range
decisions_this_month = Decision.objects.filter(
    effective_at__gte=month_start,
    effective_at__lt=month_end,
)
```

---

## Issuing Permits

An approved permit becomes an Agreement—a formal grant of permission with terms.

### Creating the Permit Agreement

```python
from django_agreements.models import Agreement, AgreementParty

def issue_permit(application, decision):
    """Issue a permit as an Agreement."""
    permit_type = CatalogItem.objects.get(sku=application.metadata["permit_type"])

    # Validity period (1 year for building permit)
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

    # Applicant is permit holder
    applicant = application.subject
    AgreementParty.objects.create(
        agreement=permit,
        party=applicant,
        role="permit_holder",
    )

    # Issuing agency
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
    """Generate unique permit number."""
    from django_sequence.services import next_value

    year = timezone.now().year
    seq = next_value(f"permit_{year}")
    return f"PLN-{year}-{seq:06d}"
```

### Querying Permits

```python
# Active permits for a property
active_permits = Agreement.objects.filter(
    agreement_type="permit",
    status="active",
    metadata__project_address="456 Oak Avenue",
).current()

# Permits issued this year
permits_this_year = Agreement.objects.filter(
    agreement_type="permit",
    valid_from__year=2024,
)

# Expired permits (for enforcement)
expired_permits = Agreement.objects.filter(
    agreement_type="permit",
    status="active",
    valid_to__lt=timezone.now(),
)
```

---

## Public Comments

Some permits require public notice and accept citizen comments.

### Public Comment Period

```python
from django_notes.services import create_note

def open_public_comment(application, comment_period_days=30):
    """Open public comment period for an application."""
    end_date = timezone.now() + timedelta(days=comment_period_days)

    transition_encounter(
        encounter=application,
        to_state="public_comment",
        actor=None,  # System action
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
    """Submit a public comment on an application."""
    # Verify comment period is open
    if application.current_state != "public_comment":
        raise InvalidStateError("Public comment period is not open")

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

### Querying Public Comments

```python
from django_notes.models import Note

# All public comments on application
comments = Note.objects.for_target(application).filter(
    note_type="public_comment"
).order_by("created_at")

# Comments by position
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

## Fee Processing

Permit fees are ledger transactions.

### Calculating Fees

```python
from decimal import Decimal
from django_ledger.models import Account, Transaction, Entry
from django_ledger.services import post_transaction

def calculate_permit_fee(application):
    """Calculate total fee for permit application."""
    permit_type = CatalogItem.objects.get(sku=application.metadata["permit_type"])
    base_fee = permit_type.unit_price

    # Formula-based fee (e.g., per square foot)
    formula = permit_type.metadata.get("fee_formula", "base")

    if "sqft" in formula:
        sqft = application.metadata.get("square_footage", 0)
        rate = Decimal("0.25")  # $0.25 per sq ft
        variable_fee = Decimal(sqft) * rate
    else:
        variable_fee = Decimal("0")

    total = base_fee + variable_fee

    return {
        "base_fee": base_fee,
        "variable_fee": variable_fee,
        "total": total,
        "breakdown": [
            {"description": "Base permit fee", "amount": base_fee},
            {"description": f"Plan check ({sqft} sq ft @ $0.25)", "amount": variable_fee},
        ]
    }
```

### Recording Fee Payment

```python
# Accounts
permit_fees = Account.objects.get(code="4300")  # Revenue
cash = Account.objects.get(code="1000")  # Asset

def record_permit_fee(application, payment_method, payment_ref):
    """Record permit fee payment."""
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
        description=f"Permit fee: {application.metadata['permit_type']}",
    )

    Entry.objects.create(
        transaction=payment,
        account=permit_fees,
        amount=fee["total"],
        entry_type="credit",
        description=f"Permit fee: {application.metadata['permit_type']}",
    )

    post_transaction(payment)

    # Transition application
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

### Refund Processing

```python
def refund_permit_fee(application, reason, refund_amount=None):
    """Process refund for withdrawn or denied application."""
    # Find original payment
    original = Transaction.objects.filter(
        transaction_type="permit_fee",
        metadata__application_id=str(application.id),
    ).first()

    if not original:
        raise ValueError("No fee payment found for this application")

    # Calculate refund (may be partial)
    original_amount = original.entries.filter(entry_type="debit").first().amount

    if refund_amount is None:
        # Full refund if not specified
        refund_amount = original_amount

    # Create refund transaction
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

    # Reverse the entries
    Entry.objects.create(
        transaction=refund,
        account=permit_fees,
        amount=refund_amount,
        entry_type="debit",
        description=f"Refund: {reason}",
    )

    Entry.objects.create(
        transaction=refund,
        account=cash,
        amount=refund_amount,
        entry_type="credit",
        description=f"Refund: {reason}",
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

## Complete Audit Trail

Government systems require complete, immutable audit trails.

### Querying Application History

```python
def get_complete_audit_trail(application):
    """Get complete history of an application."""
    from django_audit_log.models import AuditLog

    events = AuditLog.objects.for_target(application).order_by("created_at")

    trail = []
    for event in events:
        trail.append({
            "timestamp": event.created_at,
            "event_type": event.event_type,
            "actor": str(event.actor_id) if event.actor_id else "System",
            "actor_repr": event.actor_repr,
            "details": event.metadata,
        })

    # Also get document events
    documents = Document.objects.for_target(application)
    for doc in documents:
        doc_events = AuditLog.objects.for_target(doc)
        for event in doc_events:
            trail.append({
                "timestamp": event.created_at,
                "event_type": f"document:{event.event_type}",
                "actor": str(event.actor_id) if event.actor_id else "System",
                "details": event.metadata,
            })

    # Sort by timestamp
    trail.sort(key=lambda x: x["timestamp"])

    return trail

# Usage
trail = get_complete_audit_trail(application)
for entry in trail:
    print(f"{entry['timestamp']}: {entry['event_type']} by {entry['actor']}")
```

### Public Records Query

```python
def generate_public_record(application):
    """Generate public record for FOIA request."""
    # Get all non-confidential events
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

    # Get decisions
    decisions = Decision.objects.filter(
        target_id=str(application.id),
    ).order_by("effective_at")

    # Get public comments
    comments = Note.objects.for_target(application).filter(
        note_type="public_comment",
    )

    # Compile record
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

## Complete Rebuild Prompt

```markdown
# Prompt: Rebuild Government Permit Workflow

## Instruction

Build a government permit application system by composing these primitives:
- django-parties (applicants, agencies, reviewers)
- django-catalog (permit types, requirements)
- django-encounters (application workflow)
- django-decisioning (approval decisions)
- django-documents (required attachments)
- django-notes (public comments)
- django-ledger (fees)
- django-agreements (issued permits)
- django-audit-log (complete trail)
- django-rbac (reviewer permissions)

## Domain Purpose

Enable government agencies to:
- Accept and process permit applications
- Route applications through review workflows
- Record explicit decisions with rationale
- Accept public comments on applications
- Issue permits as formal agreements
- Maintain complete audit trail for public records

## NO NEW MODELS

Do not create any new Django models. All permit functionality
is implemented by composing existing primitives.

## Primitive Composition

### Parties
- Person = Applicant or individual reviewer
- Organization = Agency or department
- PartyRelationship = Department structure, staff assignments

### Permit Types
- Category = Permit categories (building, planning, business)
- CatalogItem = Specific permit type with requirements and fees

### Applications
- Encounter = The application instance
- EncounterDefinition = Workflow states and transitions
- EncounterTransition = State change with actor and timestamp

### Review Process
- WorkItem = Reviewer assignment
- Decision = Approval/denial with full rationale

### Documents
- Document = Uploaded attachment with metadata
- AuditLog = Document review/acceptance events

### Public Input
- Note (note_type="public_comment") = Citizen comments

### Fees
- Transaction = Fee payment
- Entry = Debit cash, credit revenue

### Issued Permits
- Agreement = Permit granting permission
- AgreementParty = Permit holder and issuing agency

### Audit Trail
- AuditLog = Every action on application
- All events immutable and queryable

## Service Functions

### submit_application()
```python
def submit_application(
    application: Encounter,
    applicant: Person,
) -> Encounter:
    """Submit completed application for review."""
```

### assign_reviewer()
```python
def assign_reviewer(
    application: Encounter,
    reviewer: Person,
    department: str,
) -> WorkItem:
    """Assign reviewer to application."""
```

### approve_application()
```python
def approve_application(
    application: Encounter,
    approver: Person,
    conditions: list[str] = None,
) -> tuple[Decision, Agreement]:
    """Approve application and issue permit."""
```

### deny_application()
```python
def deny_application(
    application: Encounter,
    approver: Person,
    reasons: list[str],
) -> Decision:
    """Deny application with reasons."""
```

### submit_public_comment()
```python
def submit_public_comment(
    application: Encounter,
    commenter: Person,
    comment_text: str,
    position: str,  # support, oppose, neutral
) -> Note:
    """Submit public comment during comment period."""
```

### get_audit_trail()
```python
def get_audit_trail(
    application: Encounter,
) -> list[dict]:
    """Get complete audit trail for FOIA."""
```

## Test Cases (48 tests)

### Agency Structure Tests (6 tests)
1. test_create_agency
2. test_create_department
3. test_assign_staff_to_department
4. test_staff_roles
5. test_reviewer_permissions
6. test_department_hierarchy

### Permit Type Tests (6 tests)
7. test_create_permit_category
8. test_create_permit_type
9. test_permit_required_documents
10. test_permit_fee_calculation
11. test_permit_workflow_assignment
12. test_permit_type_metadata

### Application Workflow Tests (12 tests)
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

### Decision Tests (8 tests)
25. test_approval_decision
26. test_denial_decision
27. test_decision_captures_inputs
28. test_decision_rationale_required
29. test_decision_immutable
30. test_query_decisions_by_actor
31. test_query_decisions_by_date
32. test_conditional_approval

### Public Comment Tests (6 tests)
33. test_open_comment_period
34. test_submit_comment
35. test_comment_position
36. test_query_comments
37. test_comment_summary
38. test_close_comment_period

### Fee Tests (6 tests)
39. test_calculate_base_fee
40. test_calculate_variable_fee
41. test_record_payment
42. test_refund_full
43. test_refund_partial
44. test_fee_ledger_entries

### Permit Issuance Tests (4 tests)
45. test_issue_permit
46. test_permit_has_parties
47. test_permit_validity_period
48. test_query_active_permits

## Key Behaviors

1. **Applications are Encounters** - State machine with transitions
2. **Decisions are explicit** - Captured with inputs, outcome, rationale
3. **Permits are Agreements** - Formal grant with validity period
4. **Audit trail is immutable** - Every action recorded, nothing deleted
5. **Public comments via Notes** - Queryable by position
6. **Fees via Ledger** - Proper double-entry accounting

## Acceptance Criteria

- [ ] No new Django models created
- [ ] Applications use Encounter with proper workflow
- [ ] Decisions capture inputs and rationale
- [ ] Permits use Agreement with party relationships
- [ ] Complete audit trail for FOIA compliance
- [ ] Public comments queryable
- [ ] Fees use ledger transactions
- [ ] All 48 tests passing
- [ ] README with workflow examples
```

---

## Hands-On Exercise: Build Permit Dashboard

Create dashboards for applicants and reviewers.

**Step 1: Applicant Dashboard**

```python
def get_applicant_dashboard(applicant):
    """Get dashboard data for applicant."""
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

**Step 2: Reviewer Queue**

```python
def get_reviewer_queue(reviewer):
    """Get review queue for staff member."""
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

**Step 3: Department Statistics**

```python
def get_department_stats(department, period_start, period_end):
    """Get processing statistics for department."""
    # Applications received
    received = Encounter.objects.filter(
        definition__metadata__department_id=str(department.id),
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).count()

    # Decisions made
    decisions = Decision.objects.filter(
        actor__partyrelationship__to_party=department,
        effective_at__gte=period_start,
        effective_at__lt=period_end,
    )

    approved = decisions.filter(outcome__startswith="approved").count()
    denied = decisions.filter(outcome="denied").count()

    # Average processing time
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
        "period": f"{period_start} to {period_end}",
        "received": received,
        "approved": approved,
        "denied": denied,
        "approval_rate": (approved / (approved + denied) * 100) if (approved + denied) > 0 else 0,
        "average_processing_days": avg_days,
    }
```

---

## What AI Gets Wrong About Government Workflows

### Assuming Edits Are Acceptable

AI may allow editing submitted applications:

```python
# WRONG
def update_application(application, new_data):
    application.metadata.update(new_data)
    application.save()
```

**Why it's wrong:** Once submitted, the official record cannot be modified. Only corrections through formal process.

**Solution:** Use state machine. Corrections require transition to "corrections_required" state with full logging.

### Skipping Decision Rationale

AI may record decisions without explanation:

```python
# WRONG
Decision.objects.create(
    target=application,
    outcome="denied",
    # No rationale, no inputs captured
)
```

**Why it's wrong:** Government decisions must be explainable. "Why was this denied?" requires answer.

**Solution:** Always capture inputs, rationale, and actor. Decision model requires these fields.

### Soft-Deleting Audit Records

AI may try to "clean up" old records:

```python
# WRONG
AuditLog.objects.filter(created_at__lt=three_years_ago).delete()
```

**Why it's wrong:** Public records laws require retention. Deleting destroys legal evidence.

**Solution:** Audit logs are immutable and never deleted. Archive to cold storage if needed.

### Direct State Assignment

AI may bypass state machine:

```python
# WRONG
application.current_state = "approved"
application.save()
```

**Why it's wrong:** Loses transition history. No actor recorded. Audit trail broken.

**Solution:** Always use `transition_encounter()` which creates EncounterTransition record.

---

## Why This Matters

The journalist from the opening story eventually got her answer—from the new permit system:

```python
# Query: Who approved this variance?
decision = Decision.objects.filter(
    target_id=str(variance_application.id),
    outcome__startswith="approved",
).first()

print(f"Approved by: {decision.actor.full_name}")
print(f"On: {decision.effective_at}")
print(f"Rationale: {decision.rationale}")
print(f"Documents reviewed: {decision.inputs['documents_reviewed']}")
```

The new system could answer:
- Who made the decision
- When they made it
- What they considered
- Why they decided as they did
- Every step from application to approval

No more "we are unable to locate complete records." The records exist because the system makes recording them impossible to skip.

---

## Summary

| Domain Concept | Primitive | Key Insight |
|----------------|-----------|-------------|
| Application | Encounter | State machine with recorded transitions |
| Workflow | EncounterDefinition | States and transitions configured, not coded |
| Decision | Decision | Inputs, outcome, rationale all captured |
| Permit | Agreement | Formal grant with validity period |
| Review | WorkItem | Assignment with due date |
| Comment | Note | Typed for public comments |
| Fee | Transaction | Proper ledger entries |
| Audit | AuditLog | Immutable, complete, queryable |

Government workflows are encounters with decisions. Every action is logged. Nothing is deleted. The primitives enforce accountability.

Same primitives. Bureaucracy domain.

---

## Sources

- National Association of Counties. (2020). *Digital Transformation in Local Government*.
- Government Accountability Office. (2019). *Federal Records Management: Agencies Should Strengthen Controls*.
- International City/County Management Association. (2021). *Permit Management Best Practices Guide*.
