# Chapter 19: Build a Government Form Workflow

> Same primitives. Bureaucracy domain.

## The Domain

A government permit application system needs:

- Applicants and agencies
- Application forms
- Review workflows
- Approvals and rejections
- Document attachments
- Audit trail
- Public records

## Primitive Mapping

| Domain Concept | Primitive | Package |
|----------------|-----------|---------|
| Applicant | Party (Person/Org) | django-parties |
| Agency | Party (Organization) | django-parties |
| Reviewer | Party + Role | django-parties, django-rbac |
| Application form | CatalogItem (form type) | django-catalog |
| Application | Encounter | django-encounters |
| Review stages | EncounterDefinition | django-encounters |
| Stage transition | EncounterTransition | django-encounters |
| Approval decision | Decision | django-decisioning |
| Attached documents | Document | django-documents |
| Public comments | Note | django-notes |
| Fees | Transaction | django-ledger |
| Permit (issued) | Agreement | django-agreements |
| All activity | AuditLog | django-audit-log |

## Workflow As Encounter

A permit application is an encounter with defined states:

```python
EncounterDefinition.objects.create(
    name="Building Permit Application",
    initial_state="submitted",
    states=["submitted", "under_review", "additional_info_needed",
            "approved", "rejected", "withdrawn"],
    transitions={
        "submitted": ["under_review", "withdrawn"],
        "under_review": ["additional_info_needed", "approved", "rejected"],
        "additional_info_needed": ["under_review", "withdrawn"],
        "approved": [],  # Terminal
        "rejected": [],  # Terminal
        "withdrawn": [],  # Terminal
    }
)
```

## Decisions Are Explicit

Every approval/rejection is a Decision:

```python
Decision.objects.create(
    decision_type="permit_review",
    target=application,
    actor=reviewer,
    inputs={
        "application_data": application.metadata,
        "documents": [str(d.id) for d in application.documents.all()],
        "checklist": reviewer_checklist,
    },
    outcome="approved",
    rationale="All requirements met. Zoning compliant.",
    effective_at=now()
)

# Transition encounter to approved state
application.transition_to("approved", actor=reviewer)
```

## Audit Is Mandatory

Government systems require complete audit trails:

```python
# Every action is logged
log_event(application, "document_uploaded", actor=applicant, metadata={...})
log_event(application, "review_started", actor=reviewer, metadata={...})
log_event(application, "comment_added", actor=public_user, metadata={...})
log_event(application, "decision_made", actor=reviewer, metadata={...})

# Query: "Show me everything that happened on this application"
AuditLog.objects.for_target(application).order_by('created_at')

# Query: "Show me all actions by this reviewer today"
AuditLog.objects.by_actor(reviewer).filter(created_at__date=today)
```

## The Pattern

Government workflows are just:

- Encounters (state machines with transitions)
- Decisions (auditable choices)
- Audit logs (complete history)
- Agreements (issued permits/licenses)

No new primitives. Just configuration and stricter audit requirements.

---

*Status: Planned*
