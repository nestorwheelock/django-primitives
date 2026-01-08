# Architecture: django-questionnaires

**Status:** Stable / v0.1.0

Domain-agnostic questionnaire and survey primitives for Django.

---

## What This Package Is For

Answering the question: **"What is the respondent's status based on their questionnaire answers?"**

Use cases:
- Health screening questionnaires
- Compliance checklists
- Onboarding forms
- Surveys with expiration
- Any form where answers can trigger flags requiring clearance

---

## What This Package Is NOT For

- **Not a form builder UI** - Use Django forms or frontend libraries for UI
- **Not analytics** - Use BI tools for survey analytics
- **Not file upload** - Use django-documents for attachments
- **Not notifications** - Use django-notifications for alerts
- **Not scheduling** - Use celery for recurring questionnaires

---

## Design Principles

1. **Domain-agnostic** - Works for health, compliance, HR, any domain
2. **Versioned definitions** - Publish once, never modify (create new version)
3. **GenericFK respondents** - Attach to any model (Patient, Employee, Vendor)
4. **Flag-based workflow** - Answers trigger flags, clearance resolves them
5. **Temporal validity** - Instances expire, status determined by most recent valid
6. **Voidable instances** - Incorrect data can be voided, falls back to previous

---

## Data Model

```
QuestionnaireDefinition
├── id (UUID, BaseModel)
├── slug (unique among non-archived)
├── name, description
├── version (semver string)
├── status (draft | published | archived)
├── validity_days (null = forever)
├── metadata (JSON)
└── BaseModel fields

Question
├── id (UUID, BaseModel)
├── definition (FK)
├── sequence (unique per definition)
├── category
├── question_type (yes_no | text | number | date | choice | multi_choice)
├── question_text, help_text
├── is_required
├── triggers_flag (if True, certain answers flag the instance)
├── choices (JSON for choice types)
├── validation_rules (JSON)
└── BaseModel fields

QuestionnaireInstance
├── id (UUID, BaseModel)
├── definition (FK, PROTECT)
├── definition_version (snapshot)
├── respondent (GenericFK)
├── status (pending | completed | flagged | cleared | expired | voided)
├── expires_at
├── completed_at, flagged_at
├── cleared_at, cleared_by, clearance_notes
├── voided_at, voided_by, void_reason
├── clearance_document (GenericFK, optional)
├── metadata (JSON for signatures, etc.)
└── BaseModel fields

Response
├── id (UUID, BaseModel)
├── instance (FK)
├── question (FK, PROTECT)
├── answer_text, answer_bool, answer_date, answer_number, answer_choices
├── triggered_flag
└── BaseModel fields

State Machine (Instance Status):
  PENDING → submit_response() → COMPLETED (no flags)
  PENDING → submit_response() → FLAGGED (has flags)
  FLAGGED → clear_instance() → CLEARED
  PENDING/COMPLETED/FLAGGED → expires_at < now → EXPIRED
  ANY → void_instance() → VOIDED
```

---

## Public API

### Definition Lifecycle

```python
from django_questionnaires.services import (
    create_definition,
    publish_definition,
    archive_definition,
    import_definition_from_json,
)

# Create draft definition with questions
definition = create_definition(
    slug="health-screening",
    name="Health Screening",
    description="Basic health questionnaire",
    version="1.0.0",
    questions_data=[
        {
            "sequence": 1,
            "question_type": "yes_no",
            "question_text": "Do you have any allergies?",
            "is_required": True,
            "triggers_flag": True,  # "Yes" flags the instance
        },
        {
            "sequence": 2,
            "question_type": "text",
            "question_text": "List any medications",
            "is_required": False,
        },
    ],
    actor=user,
    validity_days=365,
)

# Publish (now immutable, can create instances)
publish_definition(definition, actor=user)

# Archive (can no longer create instances)
archive_definition(definition, actor=user)

# Import from JSON file
definition = import_definition_from_json(
    json_path=Path("questionnaires/health.json"),
    actor=user,
)
```

### Instance Lifecycle

```python
from django_questionnaires.services import (
    create_instance,
    submit_response,
    clear_instance,
    void_instance,
    get_current_instance,
    is_instance_valid,
    get_flagged_questions,
)

# Create instance for a respondent
instance = create_instance(
    definition_slug="health-screening",
    respondent=patient,  # Any model via GenericFK
    expires_in_days=30,
    actor=user,
)

# Submit responses
instance = submit_response(
    instance=instance,
    answers={
        str(q1.id): {"answer_bool": True},   # Triggers flag
        str(q2.id): {"answer_text": "None"},
    },
    actor=user,
)
# instance.status is now FLAGGED

# Clear flagged instance
instance = clear_instance(
    instance=instance,
    cleared_by=reviewer,
    notes="Verified allergies are managed",
    clearance_document=uploaded_doc,  # Optional GenericFK
)
# instance.status is now CLEARED

# Void instance (falls back to previous)
void_instance(
    instance=instance,
    voided_by=admin,
    reason="Data entry error",
)
# instance.status is now VOIDED

# Get current valid instance (skips voided)
current = get_current_instance(respondent=patient, definition_slug="health-screening")

# Check validity
if is_instance_valid(current):
    print("Patient cleared for activity")

# Get flagged questions
flags = get_flagged_questions(instance)
```

---

## Hard Rules

1. **Published definitions are immutable** - Create new version to change
2. **slug unique among non-archived** - Partial unique constraint
3. **sequence unique per definition** - Partial unique constraint
4. **One response per question per instance** - Unique constraint
5. **Cannot modify completed/flagged/cleared** - Submit fails with error
6. **Cannot clear non-flagged instance** - Must be FLAGGED status
7. **Voided instances are skipped** - get_current_instance excludes them

---

## Invariants

- `QuestionnaireDefinition.slug` is unique among non-deleted, non-archived definitions
- `Question.sequence` is unique within a definition
- `Response(instance, question)` is unique
- `QuestionnaireInstance.definition_version` matches definition.version at creation
- `QuestionnaireInstance.status` follows state machine transitions
- Voided instances cannot be submitted to, cleared, or un-voided

---

## Status Determination Logic

```python
def get_respondent_status(respondent, definition_slug):
    """Determine current questionnaire status for a respondent."""
    instance = get_current_instance(respondent, definition_slug)

    if instance is None:
        return "NO_QUESTIONNAIRE"

    if instance.is_expired:
        return "EXPIRED"

    if instance.status == InstanceStatus.PENDING:
        return "PENDING"

    if instance.status == InstanceStatus.FLAGGED:
        return "FLAGGED"  # Needs clearance

    if instance.status in [InstanceStatus.COMPLETED, InstanceStatus.CLEARED]:
        return "VALID"

    return "UNKNOWN"
```

---

## Known Gotchas

### 1. Definition Already Published

**Problem:** Trying to modify published definition.

```python
definition.name = "New Name"
definition.save()
# Works, but creates inconsistency with existing instances!

# CORRECT - create new version instead
new_def = create_definition(
    slug="health-screening",  # Same slug
    version="1.1.0",          # New version
    ...
)
publish_definition(new_def, actor=user)
archive_definition(definition, actor=user)  # Archive old
```

### 2. Flag Trigger Logic

**Problem:** Not understanding which answers trigger flags.

```python
# Currently only yes_no with answer_bool=True triggers flags
# If question.triggers_flag is True AND answer is True

# For other question types, customize submit_response logic
```

### 3. Voided Instance Fallback

**Problem:** Expecting voided instance to remain current.

```python
# After voiding, get_current_instance returns the PREVIOUS instance
instance = get_current_instance(respondent, "health-screening")
void_instance(instance, voided_by=admin, reason="Error")

# Now get_current_instance returns the instance BEFORE the voided one
previous = get_current_instance(respondent, "health-screening")
# previous is NOT the voided instance
```

### 4. Expired vs Valid Check

**Problem:** Not checking expiration separately.

```python
instance = get_current_instance(respondent, slug)
if instance and instance.status == InstanceStatus.COMPLETED:
    # WRONG - might be expired!
    pass

# CORRECT - use is_instance_valid()
if is_instance_valid(instance):
    pass
```

---

## Recommended Usage

### 1. Define Questionnaires via JSON

```json
{
  "slug": "health-screening",
  "name": "Health Screening Questionnaire",
  "version": "1.0.0",
  "validity_days": 365,
  "categories": ["medical-history", "current-health"],
  "questions": [
    {
      "sequence": 1,
      "category": "medical-history",
      "question_type": "yes_no",
      "question_text": "Have you been hospitalized in the past year?",
      "is_required": true,
      "triggers_flag": true
    }
  ]
}
```

### 2. Use Services, Not Direct Model Access

```python
# CORRECT - use service functions
instance = create_instance(slug, respondent, expires_in_days, actor)
instance = submit_response(instance, answers, actor)

# AVOID - bypasses validation and workflow
instance = QuestionnaireInstance.objects.create(...)
instance.status = InstanceStatus.COMPLETED
instance.save()
```

### 3. Store Signatures in Metadata

```python
instance = submit_response(
    instance=instance,
    answers=answers,
    actor=user,
)
instance.metadata = {
    "signature": "base64...",
    "signed_at": timezone.now().isoformat(),
    "ip_address": request.META.get("REMOTE_ADDR"),
}
instance.save()
```

### 4. Handle Flag Clearance Workflow

```python
# In staff view
flagged = QuestionnaireInstance.objects.filter(
    status=InstanceStatus.FLAGGED,
    deleted_at__isnull=True,
)

for instance in flagged:
    questions = get_flagged_questions(instance)
    # Display for review, then:
    clear_instance(instance, cleared_by=staff_user, notes="Reviewed OK")
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete, timestamps)

---

## Changelog

### v0.1.0 (2025-01-07)
- Initial release
- QuestionnaireDefinition with draft/published/archived lifecycle
- Question with multiple types and flag triggers
- QuestionnaireInstance with GenericFK respondent
- Response with typed answer fields
- Service functions for full lifecycle management
- Flag-based workflow with clearance
- Void functionality with fallback to previous instance
- JSON import for definition creation
