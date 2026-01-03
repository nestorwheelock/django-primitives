# Architecture: django-encounters

**Status:** Stable / v0.1.0

State machine engine for domain-agnostic encounter workflows.

---

## What This Package Is For

Answering the question: **"What state is this encounter in, and where can it go?"**

Use cases:
- Defining reusable state machine graphs (repair_job, legal_case, medical_visit)
- Attaching encounters to any subject via GenericFK
- Validating state transitions
- Auditing all state changes with immutable records
- Historical queries for encounter state at any point in time

---

## What This Package Is NOT For

- **Not domain-specific** - This is pure workflow, not healthcare/legal/repair logic
- **Not a task queue** - Use django-catalog for work item management
- **Not scheduling** - Encounters track state, not appointment slots
- **Not notifications** - Use signals to trigger notifications on transitions

---

## Design Principles

1. **Domain-agnostic** - No assumptions about what encounters represent
2. **Graph validation** - All states reachable, no orphan states
3. **Immutable transitions** - Audit log cannot be modified after creation
4. **GenericFK subject** - Attach to any model (Patient, Asset, Case, etc.)
5. **Time semantics** - Transitions have effective_at and recorded_at

---

## Data Model

```
EncounterDefinition                    Encounter
├── id (UUID)                          ├── id (UUID)
├── key (unique slug)                  ├── definition (FK)
├── name                               ├── subject (GenericFK)
├── states (JSON list)                 │   ├── subject_type (FK → ContentType)
├── transitions (JSON dict)            │   └── subject_id (CharField for UUID)
├── initial_state                      ├── state (current state)
├── terminal_states (JSON list)        ├── created_by (FK → User)
├── validator_paths (JSON list)        ├── started_at
├── active                             ├── ended_at
└── BaseModel fields                   ├── metadata (JSON)
                                       └── BaseModel fields

EncounterTransition (IMMUTABLE)
├── id (UUID)
├── encounter (FK)
├── from_state
├── to_state
├── transitioned_by (FK → User)
├── transitioned_at (auto)
├── metadata (JSON)
├── effective_at (time semantics)
├── recorded_at (time semantics)
└── BaseModel fields

Graph Structure (states/transitions):
{
  "states": ["scheduled", "checked_in", "in_progress", "completed", "cancelled"],
  "transitions": {
    "scheduled": ["checked_in", "cancelled"],
    "checked_in": ["in_progress", "cancelled"],
    "in_progress": ["completed", "cancelled"],
    "completed": [],   // terminal
    "cancelled": []    // terminal
  },
  "initial_state": "scheduled",
  "terminal_states": ["completed", "cancelled"]
}
```

---

## Public API

### Creating Definitions

```python
from django_encounters.models import EncounterDefinition

definition = EncounterDefinition.objects.create(
    key='repair_job',
    name='Repair Job',
    states=['received', 'diagnosing', 'repairing', 'completed', 'cancelled'],
    transitions={
        'received': ['diagnosing', 'cancelled'],
        'diagnosing': ['repairing', 'cancelled'],
        'repairing': ['completed', 'cancelled'],
        'completed': [],
        'cancelled': [],
    },
    initial_state='received',
    terminal_states=['completed', 'cancelled'],
    validator_paths=[],  # Optional: dotted paths to validator classes
)
```

### Creating Encounters

```python
from django_encounters.models import Encounter
from django.contrib.contenttypes.models import ContentType

# Attach to any model (e.g., Patient, Asset, Case)
encounter = Encounter.objects.create(
    definition=definition,
    subject_type=ContentType.objects.get_for_model(asset),
    subject_id=str(asset.pk),  # CharField supports UUID
    state=definition.initial_state,
    created_by=user,
)
```

### Transitioning State

```python
from django_encounters.services import transition_encounter

# This validates the transition and creates an audit record
transition_encounter(
    encounter=encounter,
    to_state='diagnosing',
    user=technician,
    metadata={'notes': 'Initial assessment complete'},
)
```

### Querying Transitions

```python
from django_encounters.models import EncounterTransition

# All transitions for an encounter
history = EncounterTransition.objects.filter(encounter=encounter)

# Transitions as of a specific time
past = EncounterTransition.objects.as_of(some_date)

# Find when encounter entered a specific state
entered_diagnosing = EncounterTransition.objects.filter(
    encounter=encounter,
    to_state='diagnosing',
).first()
```

---

## Graph Validation Rules

The `validate_definition_graph()` function enforces:

| Rule | Description |
|------|-------------|
| initial_state in states | Starting state must exist |
| terminal_states ⊆ states | All terminal states must exist |
| transition sources ∈ states | Can't transition from unknown state |
| transition targets ∈ states | Can't transition to unknown state |
| terminal states have no outgoing | Terminal states must end the workflow |
| all states reachable from initial | No orphan states |

---

## Hard Rules

1. **Transitions are immutable** - Cannot update or delete EncounterTransition records
2. **Graph must be valid** - EncounterDefinition.clean() validates on save
3. **Subject uses GenericFK** - Works with any model, not just specific types
4. **terminal_states have no outgoing** - Once terminal, workflow is complete
5. **All states must be reachable** - BFS from initial_state must reach all

---

## Invariants

- `initial_state` is always in `states` list
- All `terminal_states` are in `states` list
- All transition source/target states are in `states` list
- No state in `terminal_states` has outgoing transitions
- Every state is reachable from `initial_state` via BFS
- `EncounterTransition.recorded_at` is immutable after creation
- `Encounter.state` matches the `to_state` of its most recent transition

---

## Known Gotchas

### 1. Transitions Are Truly Immutable

**Problem:** Attempting to update a transition record.

```python
transition = EncounterTransition.objects.first()
transition.metadata['correction'] = 'Updated notes'
transition.save()
# Raises: ImmutableTransitionError
```

**Solution:** Create a new transition with corrected metadata. The history preserves both.

### 2. Terminal States Cannot Transition

**Problem:** Trying to transition from a terminal state.

```python
encounter.state = 'completed'  # Terminal
transition_encounter(encounter, 'diagnosing', user)
# Raises: InvalidTransitionError
```

**Solution:** If you need to reopen, add a "reopened" transition in the graph.

### 3. Subject ID Must Be String

**Problem:** Using integer or UUID directly as subject_id.

```python
# WRONG - will fail for UUID PKs
encounter.subject_id = patient.pk

# CORRECT - always stringify
encounter.subject_id = str(patient.pk)
```

### 4. Graph Validation on Save

**Problem:** Creating invalid definition succeeds then fails on clean.

```python
definition = EncounterDefinition(
    states=['a', 'b'],
    transitions={'a': ['c']},  # 'c' doesn't exist!
    initial_state='a',
    terminal_states=['b'],
)
definition.full_clean()  # Raises ValidationError
definition.save()  # Would fail on DB constraints anyway
```

**Solution:** Always call `full_clean()` or use validated forms.

### 5. Orphan States Rejected

**Problem:** State that can't be reached from initial.

```python
definition = EncounterDefinition(
    states=['a', 'b', 'orphan'],  # 'orphan' unreachable
    transitions={'a': ['b']},
    initial_state='a',
    terminal_states=['b'],
)
definition.full_clean()
# Error: "state 'orphan' unreachable from initial_state"
```

---

## Recommended Usage

### 1. Define Once, Reuse Many

```python
# Define workflow once
REPAIR_WORKFLOW = EncounterDefinition.objects.get_or_create(
    key='repair_job',
    defaults={
        'name': 'Repair Job',
        'states': ['received', 'diagnosing', 'repairing', 'completed'],
        'transitions': {...},
        'initial_state': 'received',
        'terminal_states': ['completed'],
    }
)[0]

# Create many encounters using it
def create_repair_job(asset, user):
    return Encounter.objects.create(
        definition=REPAIR_WORKFLOW,
        subject_type=ContentType.objects.get_for_model(asset),
        subject_id=str(asset.pk),
        state=REPAIR_WORKFLOW.initial_state,
        created_by=user,
    )
```

### 2. Use Services for Transitions

```python
from django_encounters.services import transition_encounter

# RECOMMENDED - validates and creates audit record
transition_encounter(encounter, 'in_progress', user)

# AVOID - bypasses validation
encounter.state = 'in_progress'
encounter.save()  # No audit record!
```

### 3. Check Valid Next States

```python
def get_valid_next_states(encounter):
    """Get list of states this encounter can transition to."""
    current = encounter.state
    transitions = encounter.definition.transitions
    return transitions.get(current, [])

# In view
valid_states = get_valid_next_states(encounter)
# Returns: ['diagnosing', 'cancelled']
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)
- django-decisioning (for time semantics querysets)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- EncounterDefinition with graph validation
- Encounter with GenericFK subject attachment
- Immutable EncounterTransition audit log
- Time semantics (effective_at, recorded_at)
- BFS reachability validation
