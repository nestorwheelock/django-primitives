# Chapter 9: Workflow

> "Every process has a beginning, a middle, and an end. The hard part is knowing which one you're in."
>
> — Hospital administrator on patient flow

---

On February 20, 1991, a software bug killed 28 American soldiers in Dhahran, Saudi Arabia. A Patriot missile battery failed to intercept an incoming Iraqi Scud missile, which struck a barracks.

The bug wasn't in the missile's targeting system. It was in the state machine. The Patriot's software tracked elapsed time using a 24-bit integer, and after 100 hours of continuous operation, the accumulated rounding error in the floating-point time calculation was 0.34 seconds. That was enough for the missile to be nearly half a kilometer off-target.

The system had no mechanism to track its own state degradation. It had no concept of "operational hours" as a state requiring attention. It was either "on" or "off," with no states in between that would trigger recalibration.

State machines aren't just for hardware. Every business process—patient visits, order fulfillment, contract negotiation, support tickets—follows a lifecycle with defined states and transitions. When these lifecycles aren't modeled explicitly, they're modeled implicitly in if-else statements scattered across your codebase. And implicit state machines always fail in ways you don't expect.

## The Problem State Machines Solve

Consider a veterinary appointment. A patient visit might be:
- Scheduled
- Checked in
- In progress with a doctor
- Awaiting lab results
- Completed
- Cancelled
- No-show

Without explicit state modeling, you end up with code like this:

```python
# Scattered throughout the codebase
if appointment.checked_in and not appointment.completed:
    # Maybe in progress?
    if appointment.doctor_id:
        # Probably being seen...
        pass
```

This works until it doesn't. What happens when:
- Someone marks a visit "completed" before it was "checked in"?
- A cancelled visit is accidentally resumed?
- You need to know the history of how a visit progressed?

Without an explicit state machine, these questions require archaeological digs through logs and timestamps, guessing at what happened based on which fields were set when.

## The Encounter Pattern

The encounters primitive provides:

1. **EncounterDefinition** — Configures what states exist and which transitions are allowed
2. **Encounter** — Tracks a specific instance through its lifecycle
3. **EncounterTransition** — Append-only log of every state change
4. **StateValidator** — Pluggable validation for transitions

This pattern solves four problems simultaneously:

**Explicitness**: States are defined, not inferred. You can see exactly what "in_progress" means for a given encounter type.

**Constraints**: Transitions are validated. You can't jump from "scheduled" to "completed" if the definition requires going through "checked_in" first.

**History**: The transition log is append-only. You can always reconstruct exactly what happened and when.

**Flexibility**: Different encounter types have different state machines. A patient visit has different states than a work order or a support ticket.

## Append-Only Transitions

The transition log is immutable. Once a transition is recorded, it cannot be edited or deleted.

```python
class EncounterTransition(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=CASCADE, related_name='transitions')
    from_state = models.CharField(max_length=50)
    to_state = models.CharField(max_length=50)
    transitioned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    transitioned_at = models.DateTimeField(auto_now_add=True)  # System time
    effective_at = models.DateTimeField(default=timezone.now)  # Business time
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)

    def save(self, *args, **kwargs):
        if self.pk:
            raise EncounterError("Transitions are immutable")
        super().save(*args, **kwargs)
```

This pattern has consequences:

**You can backdate but not hide.** If a transition happened yesterday but wasn't recorded until today, you set `effective_at` to yesterday. The `transitioned_at` still shows today—the system time when the record was created.

**Corrections require new transitions.** If someone accidentally transitioned to the wrong state, you transition back. The error is visible in the log, not hidden.

**History is always reconstructable.** Given a timestamp, you can query what state the encounter was in at that moment.

## Pluggable Validators

Different encounter types need different validation rules. A patient visit might require that `started_at` is set before transitioning to "in_progress." A work order might require that all materials are allocated before "started."

Rather than hardcoding validation logic, validators are configured per definition:

```python
class EncounterDefinition(models.Model):
    validators = models.JSONField(
        default=list,
        help_text="List of validator class paths"
    )
```

A definition might specify:

```python
validators=[
    'django_encounters.validators.FinalStateValidator',
    {
        'path': 'django_encounters.validators.RequiredFieldsValidator',
        'params': {
            'state_requirements': {
                'completed': ['ended_at'],
                'in_progress': ['started_at']
            }
        }
    }
]
```

This configuration is data, not code. You can change the validation rules for an encounter type without deploying new code.

The base validator is an abstract class:

```python
class StateValidator(ABC):
    @abstractmethod
    def validate(self, encounter, from_state, to_state, context=None):
        """
        Raise ValidationError if transition is invalid.
        """
        pass
```

Built-in validators cover common patterns:

- **RequiredFieldsValidator** — Ensure specific fields are set before entering certain states
- **NoBackwardsTransitionValidator** — Prevent moving backwards in a linear workflow
- **FinalStateValidator** — Prevent any transitions out of terminal states

Custom validators can implement domain-specific rules:

```python
class AllMaterialsAllocatedValidator(StateValidator):
    def validate(self, encounter, from_state, to_state, context=None):
        if to_state == 'in_progress':
            if not encounter.subject.materials_ready:
                raise ValidationError(
                    self.__class__.__name__,
                    "Cannot start work: materials not allocated"
                )
```

## GenericFK for Polymorphic Subjects

Encounters track any kind of subject—patients, work orders, support tickets, contracts. The encounter doesn't care what it's tracking; it just needs a reference.

```python
class Encounter(models.Model):
    subject_content_type = models.ForeignKey(ContentType, on_delete=CASCADE)
    subject_id = models.CharField(max_length=255)  # CharField for UUID support
    subject = GenericForeignKey('subject_content_type', 'subject_id')
```

The same encounter framework handles:

```python
# Patient visit
visit = create_encounter(definition=visit_def, subject=patient)

# Work order
work_order_encounter = create_encounter(definition=work_order_def, subject=work_order)

# Support ticket
ticket = create_encounter(definition=support_def, subject=ticket)
```

The states and transitions differ by definition. The primitive is the same.

## The Full Prompt

Here is the complete prompt to generate an encounters/workflow package. Copy this prompt, paste it into your AI assistant, and it will generate correct state machine primitives.

---

````markdown
# Prompt: Build django-encounters

## Instruction

Create a Django package called `django-encounters` that provides a state machine
framework for encounter/visit tracking with pluggable validators.

## Package Purpose

Provide encounter state management primitives:
- EncounterDefinition - Define encounter types with allowed states
- Encounter - Track an encounter through its lifecycle
- EncounterTransition - Append-only log of state changes
- StateValidator - Pluggable validation for transitions
- State machine with configurable allowed transitions

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel, BaseModel)
- django.contrib.contenttypes
- django.contrib.auth

## File Structure

```
packages/django-encounters/
├── pyproject.toml
├── README.md
├── src/django_encounters/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── validators.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── models.py
    ├── test_models.py
    ├── test_services.py
    └── test_validators.py
```

## Exceptions Specification

### exceptions.py

```python
class EncounterError(Exception):
    """Base exception for encounter errors."""
    pass


class InvalidTransitionError(EncounterError):
    """Raised when a state transition is not allowed."""
    def __init__(self, from_state: str, to_state: str, reason: str = ''):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        message = f"Cannot transition from '{from_state}' to '{to_state}'"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class ValidationError(EncounterError):
    """Raised when a transition fails validation."""
    def __init__(self, validator: str, message: str):
        self.validator = validator
        super().__init__(f"Validation failed ({validator}): {message}")


class EncounterNotFoundError(EncounterError):
    """Raised when an encounter is not found."""
    pass
```

## Models Specification

### EncounterDefinition Model

```python
from django.db import models
from django_basemodels.models import UUIDModel, BaseModel


class EncounterDefinition(UUIDModel, BaseModel):
    """
    Defines an encounter type and its allowed states/transitions.
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')

    # State machine configuration
    states = models.JSONField(
        default=list,
        help_text="List of allowed state names"
    )
    initial_state = models.CharField(max_length=50)
    final_states = models.JSONField(
        default=list,
        help_text="List of terminal state names"
    )
    transitions = models.JSONField(
        default=dict,
        help_text="Dict mapping state to list of allowed next states"
    )

    # Validators
    validators = models.JSONField(
        default=list,
        help_text="List of validator class paths"
    )

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_encounters'
        verbose_name = 'encounter definition'
        verbose_name_plural = 'encounter definitions'
        ordering = ['name']

    def is_valid_state(self, state: str) -> bool:
        """Check if a state is defined for this encounter type."""
        return state in self.states

    def is_final_state(self, state: str) -> bool:
        """Check if a state is a final/terminal state."""
        return state in self.final_states

    def is_valid_transition(self, from_state: str, to_state: str) -> bool:
        """Check if a transition between two states is allowed."""
        if from_state not in self.transitions:
            return False
        return to_state in self.transitions.get(from_state, [])

    def get_allowed_transitions(self, from_state: str) -> list:
        """Get list of states that can be transitioned to from current state."""
        return self.transitions.get(from_state, [])

    def __str__(self):
        return self.name
```

### Encounter Model

```python
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone


class Encounter(UUIDModel, BaseModel):
    """
    An encounter instance tracking progress through states.
    """
    definition = models.ForeignKey(
        EncounterDefinition,
        on_delete=models.PROTECT,
        related_name='encounters'
    )

    # Subject via GenericFK (what/who this encounter is about)
    subject_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    subject_id = models.CharField(max_length=255)
    subject = GenericForeignKey('subject_content_type', 'subject_id')

    # Current state
    state = models.CharField(max_length=50)

    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Participants
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='encounters_created'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='encounters_assigned'
    )

    # Metadata
    notes = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_encounters'
        verbose_name = 'encounter'
        verbose_name_plural = 'encounters'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subject_content_type', 'subject_id']),
            models.Index(fields=['state']),
            models.Index(fields=['scheduled_at']),
        ]

    def save(self, *args, **kwargs):
        self.subject_id = str(self.subject_id)

        # Set initial state if not set
        if not self.state and self.definition:
            self.state = self.definition.initial_state

        super().save(*args, **kwargs)

    @property
    def is_final(self) -> bool:
        """Check if encounter is in a final state."""
        return self.definition.is_final_state(self.state)

    @property
    def allowed_transitions(self) -> list:
        """Get list of states that can be transitioned to."""
        return self.definition.get_allowed_transitions(self.state)

    def __str__(self):
        return f"{self.definition.name} - {self.state}"
```

### EncounterTransition Model

```python
class EncounterTransition(UUIDModel):
    """
    Append-only log of state transitions.
    """
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.CASCADE,
        related_name='transitions'
    )

    # Transition details
    from_state = models.CharField(max_length=50)
    to_state = models.CharField(max_length=50)

    # Who and when
    transitioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transitions_made'
    )
    transitioned_at = models.DateTimeField(auto_now_add=True)
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When transition actually occurred (for backdating)"
    )

    # Context
    reason = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_encounters'
        verbose_name = 'encounter transition'
        verbose_name_plural = 'encounter transitions'
        ordering = ['-transitioned_at']

    def save(self, *args, **kwargs):
        # Append-only - cannot update existing
        if self.pk:
            raise EncounterError("Transitions are immutable")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.from_state} → {self.to_state}"
```

## Validators Specification

### validators.py

```python
from abc import ABC, abstractmethod
from typing import Optional


class StateValidator(ABC):
    """
    Base class for transition validators.

    Subclass and implement validate() to add custom validation logic.
    """

    @abstractmethod
    def validate(
        self,
        encounter,
        from_state: str,
        to_state: str,
        context: Optional[dict] = None
    ) -> None:
        """
        Validate a transition.

        Args:
            encounter: Encounter instance
            from_state: Current state
            to_state: Target state
            context: Additional context dict

        Raises:
            ValidationError: If validation fails
        """
        pass


class RequiredFieldsValidator(StateValidator):
    """
    Validates that required fields are set before transitioning to certain states.
    """

    def __init__(self, state_requirements: dict):
        """
        Args:
            state_requirements: Dict mapping state to list of required fields
                e.g., {'completed': ['ended_at'], 'in_progress': ['started_at']}
        """
        self.state_requirements = state_requirements

    def validate(self, encounter, from_state, to_state, context=None):
        from .exceptions import ValidationError

        required_fields = self.state_requirements.get(to_state, [])
        for field in required_fields:
            value = getattr(encounter, field, None)
            if value is None:
                raise ValidationError(
                    self.__class__.__name__,
                    f"Field '{field}' is required for state '{to_state}'"
                )


class NoBackwardsTransitionValidator(StateValidator):
    """
    Prevents transitions to earlier states in the workflow.
    """

    def __init__(self, state_order: list):
        """
        Args:
            state_order: List of states in order (earlier to later)
        """
        self.state_order = state_order

    def validate(self, encounter, from_state, to_state, context=None):
        from .exceptions import ValidationError

        try:
            from_index = self.state_order.index(from_state)
            to_index = self.state_order.index(to_state)
            if to_index < from_index:
                raise ValidationError(
                    self.__class__.__name__,
                    f"Cannot transition backwards from '{from_state}' to '{to_state}'"
                )
        except ValueError:
            # State not in order list - allow
            pass


class FinalStateValidator(StateValidator):
    """
    Prevents transitions out of final states.
    """

    def validate(self, encounter, from_state, to_state, context=None):
        from .exceptions import ValidationError

        if encounter.definition.is_final_state(from_state):
            raise ValidationError(
                self.__class__.__name__,
                f"Cannot transition from final state '{from_state}'"
            )


def get_validator_instance(validator_path: str, config: dict = None):
    """
    Instantiate a validator from its class path.

    Args:
        validator_path: Dotted path to validator class
        config: Optional configuration dict for validator

    Returns:
        Validator instance
    """
    import importlib

    module_path, class_name = validator_path.rsplit('.', 1)
    module = importlib.module_module(module_path)
    validator_class = getattr(module, class_name)

    if config:
        return validator_class(**config)
    return validator_class()
```

## Service Functions

### services.py

```python
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.utils import timezone
from .models import Encounter, EncounterTransition, EncounterDefinition
from .exceptions import InvalidTransitionError, ValidationError, EncounterNotFoundError
from .validators import get_validator_instance, StateValidator


def create_encounter(
    definition: EncounterDefinition,
    subject,
    created_by=None,
    assigned_to=None,
    scheduled_at=None,
    notes: str = '',
    metadata: Optional[Dict] = None,
) -> Encounter:
    """
    Create a new encounter in its initial state.

    Args:
        definition: EncounterDefinition to use
        subject: Subject of the encounter (any model)
        created_by: User creating the encounter
        assigned_to: User assigned to handle the encounter
        scheduled_at: When encounter is scheduled
        notes: Initial notes
        metadata: Additional metadata

    Returns:
        Encounter instance
    """
    encounter = Encounter.objects.create(
        definition=definition,
        subject=subject,
        state=definition.initial_state,
        created_by=created_by,
        assigned_to=assigned_to,
        scheduled_at=scheduled_at,
        notes=notes,
        metadata=metadata or {},
    )
    return encounter


@transaction.atomic
def transition(
    encounter: Encounter,
    to_state: str,
    transitioned_by=None,
    reason: str = '',
    context: Optional[Dict] = None,
    effective_at=None,
    skip_validation: bool = False,
) -> EncounterTransition:
    """
    Transition an encounter to a new state.

    Args:
        encounter: Encounter to transition
        to_state: Target state
        transitioned_by: User making the transition
        reason: Reason for transition
        context: Additional context for validators
        effective_at: When transition actually occurred (for backdating)
        skip_validation: Skip custom validators (for admin override)

    Returns:
        EncounterTransition instance

    Raises:
        InvalidTransitionError: If transition is not allowed
        ValidationError: If validation fails
    """
    # Lock encounter for update
    encounter = Encounter.objects.select_for_update().get(pk=encounter.pk)
    from_state = encounter.state

    # Check if transition is allowed
    if not encounter.definition.is_valid_transition(from_state, to_state):
        raise InvalidTransitionError(
            from_state, to_state,
            f"Allowed transitions: {encounter.allowed_transitions}"
        )

    # Run validators
    if not skip_validation:
        run_validators(encounter, from_state, to_state, context)

    # Create transition log
    transition_record = EncounterTransition.objects.create(
        encounter=encounter,
        from_state=from_state,
        to_state=to_state,
        transitioned_by=transitioned_by,
        effective_at=effective_at or timezone.now(),
        reason=reason,
        metadata=context or {},
    )

    # Update encounter state
    encounter.state = to_state

    # Update timing fields based on state
    if to_state in encounter.definition.final_states:
        encounter.ended_at = effective_at or timezone.now()

    encounter.save()

    return transition_record


def run_validators(
    encounter: Encounter,
    from_state: str,
    to_state: str,
    context: Optional[Dict] = None,
) -> None:
    """
    Run all validators for an encounter transition.

    Args:
        encounter: Encounter being transitioned
        from_state: Current state
        to_state: Target state
        context: Additional context

    Raises:
        ValidationError: If any validator fails
    """
    validator_configs = encounter.definition.validators or []

    for config in validator_configs:
        if isinstance(config, str):
            validator = get_validator_instance(config)
        elif isinstance(config, dict):
            path = config.get('path')
            params = config.get('params', {})
            validator = get_validator_instance(path, params)
        else:
            continue

        validator.validate(encounter, from_state, to_state, context)


def get_encounter_history(encounter: Encounter) -> List[EncounterTransition]:
    """
    Get the full transition history for an encounter.

    Args:
        encounter: Encounter to get history for

    Returns:
        List of EncounterTransition ordered by time
    """
    return list(
        encounter.transitions.order_by('transitioned_at')
    )


def get_state_at(encounter: Encounter, timestamp) -> str:
    """
    Get the state of an encounter at a specific point in time.

    Args:
        encounter: Encounter to check
        timestamp: Point in time to check

    Returns:
        State string at that time
    """
    # Find the last transition before or at the timestamp
    transition = encounter.transitions.filter(
        effective_at__lte=timestamp
    ).order_by('-effective_at').first()

    if transition:
        return transition.to_state

    # No transitions found - must be initial state
    return encounter.definition.initial_state
```

## Test Cases (80 tests)

### EncounterDefinition Model Tests (12 tests)
1. `test_definition_creation` - Create with required fields
2. `test_definition_has_uuid_pk` - UUID primary key
3. `test_definition_unique_name` - Unique name constraint
4. `test_definition_unique_code` - Unique code constraint
5. `test_definition_states_json` - JSONField works
6. `test_definition_transitions_json` - JSONField works
7. `test_definition_is_valid_state` - State validation
8. `test_definition_is_valid_state_false` - Invalid state
9. `test_definition_is_final_state` - Final state check
10. `test_definition_is_valid_transition` - Transition validation
11. `test_definition_is_valid_transition_false` - Invalid transition
12. `test_definition_get_allowed_transitions` - Returns allowed list

### Encounter Model Tests (14 tests)
1. `test_encounter_creation` - Create with required fields
2. `test_encounter_has_uuid_pk` - UUID primary key
3. `test_encounter_definition_fk` - FK to definition
4. `test_encounter_subject_generic_fk` - GenericFK works
5. `test_encounter_initial_state_set` - Auto-sets initial state
6. `test_encounter_state_can_be_overridden` - Custom state
7. `test_encounter_is_final_property` - Final state check
8. `test_encounter_allowed_transitions_property` - Returns list
9. `test_encounter_soft_delete` - Soft delete works
10. `test_encounter_ordering` - Ordered by created_at desc
11. `test_encounter_scheduled_at_optional` - Nullable
12. `test_encounter_timing_fields_optional` - All nullable
13. `test_encounter_metadata_json` - JSONField works
14. `test_encounter_str_representation` - String format

### EncounterTransition Model Tests (10 tests)
1. `test_transition_creation` - Create with required fields
2. `test_transition_has_uuid_pk` - UUID primary key
3. `test_transition_encounter_fk` - FK to encounter
4. `test_transition_immutable` - Cannot update after create
5. `test_transition_transitioned_at_auto` - Auto-set on create
6. `test_transition_effective_at_default` - Defaults to now
7. `test_transition_effective_at_custom` - Can be backdated
8. `test_transition_ordering` - Ordered by transitioned_at desc
9. `test_transition_reason_optional` - Optional field
10. `test_transition_str_representation` - String format

### StateValidator Tests (12 tests)
1. `test_required_fields_validator_passes` - Fields present
2. `test_required_fields_validator_fails` - Field missing
3. `test_required_fields_validator_multiple` - Multiple fields
4. `test_no_backwards_validator_allows_forward` - Forward OK
5. `test_no_backwards_validator_blocks_backward` - Backward blocked
6. `test_no_backwards_validator_unknown_state` - Unknown allowed
7. `test_final_state_validator_allows` - Non-final OK
8. `test_final_state_validator_blocks` - Final blocked
9. `test_get_validator_instance_simple` - No config
10. `test_get_validator_instance_with_config` - With config
11. `test_custom_validator_implementation` - Subclass works
12. `test_validator_context_passed` - Context available

### create_encounter Service Tests (8 tests)
1. `test_create_encounter_basic` - Creates encounter
2. `test_create_encounter_initial_state` - State set
3. `test_create_encounter_with_subject` - Subject attached
4. `test_create_encounter_with_users` - Users assigned
5. `test_create_encounter_with_schedule` - Scheduled time
6. `test_create_encounter_with_notes` - Notes stored
7. `test_create_encounter_with_metadata` - Metadata stored
8. `test_create_encounter_returns_encounter` - Returns instance

### transition Service Tests (16 tests)
1. `test_transition_changes_state` - State updates
2. `test_transition_creates_log` - Log created
3. `test_transition_invalid_raises` - Error on invalid
4. `test_transition_with_reason` - Reason stored
5. `test_transition_with_user` - User recorded
6. `test_transition_with_effective_at` - Backdating works
7. `test_transition_runs_validators` - Validators called
8. `test_transition_skip_validation` - Skip flag works
9. `test_transition_atomic` - Transaction rollback
10. `test_transition_locks_encounter` - Select for update
11. `test_transition_to_final_sets_ended_at` - Ended time
12. `test_transition_multiple_sequential` - Multiple transitions
13. `test_transition_returns_log` - Returns transition
14. `test_transition_context_to_metadata` - Context stored
15. `test_transition_from_initial` - First transition
16. `test_transition_validator_error` - Validation error

### get_encounter_history Tests (4 tests)
1. `test_history_empty_for_new` - No transitions yet
2. `test_history_ordered_by_time` - Chronological order
3. `test_history_includes_all` - All transitions
4. `test_history_returns_list` - Returns list

### get_state_at Tests (4 tests)
1. `test_state_at_before_first` - Returns initial
2. `test_state_at_after_transition` - Returns new state
3. `test_state_at_between_transitions` - Correct state
4. `test_state_at_current` - Latest state

## Key Behaviors

1. State Machine: Configurable states and transitions per definition
2. Append-Only Transitions: Immutable transition log
3. Pluggable Validators: Custom validation via class paths
4. GenericFK Subject: Encounters for any model type
5. Temporal Queries: get_state_at() for historical state

## Usage Example

```python
from django_encounters import (
    EncounterDefinition, create_encounter, transition,
    RequiredFieldsValidator, NoBackwardsTransitionValidator
)

# Define an encounter type
visit_def = EncounterDefinition.objects.create(
    name='Patient Visit',
    code='VISIT',
    states=['scheduled', 'checked_in', 'in_progress', 'completed', 'cancelled'],
    initial_state='scheduled',
    final_states=['completed', 'cancelled'],
    transitions={
        'scheduled': ['checked_in', 'cancelled'],
        'checked_in': ['in_progress', 'cancelled'],
        'in_progress': ['completed', 'cancelled'],
    },
    validators=[
        'django_encounters.validators.FinalStateValidator',
        {
            'path': 'django_encounters.validators.RequiredFieldsValidator',
            'params': {
                'state_requirements': {
                    'completed': ['ended_at'],
                    'in_progress': ['started_at']
                }
            }
        }
    ]
)

# Create encounter
encounter = create_encounter(
    definition=visit_def,
    subject=patient,
    created_by=request.user,
    scheduled_at=appointment_time
)

# Transition through states
transition(encounter, 'checked_in', transitioned_by=receptionist)
encounter.started_at = timezone.now()
encounter.save()
transition(encounter, 'in_progress', transitioned_by=doctor)
encounter.ended_at = timezone.now()
encounter.save()
transition(encounter, 'completed', transitioned_by=doctor, reason='Visit concluded')

# Query history
history = get_encounter_history(encounter)
past_state = get_state_at(encounter, some_past_time)
```

## Acceptance Criteria

- [ ] EncounterDefinition with state machine config
- [ ] Encounter model with GenericFK subject
- [ ] EncounterTransition append-only log
- [ ] StateValidator base class with implementations
- [ ] create_encounter, transition, get_encounter_history, get_state_at
- [ ] Pluggable validator configuration
- [ ] All 80 tests passing
- [ ] README with usage examples
````

---

## Hands-On: Generate Your Encounters Package

Copy the prompt above and paste it into your AI assistant. The AI will generate:

1. The complete package structure with src/ layout
2. Models with proper GenericFK, immutability, and indexes
3. Service functions with atomic transactions
4. Validator classes and loading mechanism
5. Exception hierarchy
6. 80 test cases covering all behaviors

After generation, run the tests:

```bash
cd packages/django-encounters
pip install -e .
pytest tests/ -v
```

All 80 tests should pass. If any fail, the test name tells you which constraint was violated. Ask the AI to fix the specific failing test.

### Exercise: Add Support Ticket Workflow

Define a support ticket encounter with different states and transitions:

```
Create a support ticket encounter definition:

States: new, assigned, investigating, waiting_customer, resolved, closed, reopened

Initial state: new
Final states: closed

Transitions:
- new → assigned
- assigned → investigating, waiting_customer
- investigating → waiting_customer, resolved
- waiting_customer → investigating, resolved
- resolved → closed, reopened
- reopened → investigating

Validators:
- RequiredFieldsValidator: assigned requires assigned_to, resolved requires resolution_notes
- Custom validator: cannot close within 24 hours of resolution (customer confirmation window)

Write the validator for the 24-hour confirmation window.
```

### Exercise: State History Report

Use `get_state_at()` to build a time-series report:

```
Write a function duration_in_state(encounter, state) that calculates
total time (in hours) an encounter spent in a specific state.

Handle cases where:
- Encounter entered and left the state multiple times
- Encounter is currently in the state
- Encounter never entered the state

Return Decimal for precision.
```

## What AI Gets Wrong

Without explicit constraints, AI-generated workflow code typically:

1. **Stores state as an enum without history** — You know the current state, but not how you got there. Debugging requires guessing.

2. **Allows any transition** — No constraints on what states can follow what. Invalid state combinations happen silently.

3. **Uses mutable transition logs** — Someone "corrects" a transition record. The audit trail is destroyed.

4. **Hardcodes validation in transition logic** — Every new rule requires code changes. You can't configure validation per encounter type.

5. **Uses IntegerField for subject_id** — Breaks with UUID primary keys, which are standard in enterprise systems.

6. **Lacks temporal queries** — No way to know what state something was in at a past point in time. Auditors hate this.

7. **Conflates system time and business time** — When something was recorded vs. when it actually happened. Backdating is either impossible or corrupts history.

The prompt above prevents all of these mistakes.

## Why This Matters Later

The encounters primitive is the operational backbone:

- **Catalog**: Work items spawn encounters. A basket item becomes a work order that tracks through fulfillment states.

- **Audit**: Every transition is a permanent record. Combined with the audit log, you have complete accountability.

- **Decisions**: Approval workflows use encounters. A purchase request transitions through review states, with decisions recorded at each step.

- **Agreements**: Contract negotiations are encounters. Each version and approval is a state transition.

Every system that tracks "things moving through stages" needs this pattern. The specific states differ; the primitive is the same.

---

## Sources and References

1. **Patriot Missile Failure** — Report by the Government Accountability Office, "Patriot Missile Defense: Software Problem Led to System Failure at Dhahran, Saudi Arabia," GAO/IMTEC-92-26, February 1992. The 0.34-second drift after 100 hours of operation.

2. **State Machine Theory** — Hopcroft, Motwani, and Ullman. *Introduction to Automata Theory, Languages, and Computation* (3rd Edition). The mathematical foundation for finite state machines.

3. **Temporal Data Models** — Snodgrass, Richard T. *Developing Time-Oriented Database Applications in SQL*. Morgan Kaufmann, 2000. The academic treatment of business time vs. system time.

4. **Django ContentTypes Framework** — Django documentation on the contenttypes framework for generic relations. The technical implementation of GenericForeignKey.

---

*Status: Complete*
