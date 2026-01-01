# Prompt: Rebuild django-encounters

## Instruction

Create a Django package called `django-encounters` that provides a state machine framework for encounter/visit tracking with pluggable validators.

## Package Purpose

Provide encounter state management primitives:
- `EncounterDefinition` - Define encounter types with allowed states
- `Encounter` - Track an encounter through its lifecycle
- `EncounterTransition` - Append-only log of state changes
- `StateValidator` - Pluggable validation for transitions
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
    def __init__(self, encounter_id):
        self.encounter_id = encounter_id
        super().__init__(f"Encounter {encounter_id} not found")
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
    module = importlib.import_module(module_path)
    validator_class = getattr(module, class_name)

    if config:
        return validator_class(**config)
    return validator_class()
```

## Services Specification

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

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    # Models
    'EncounterDefinition',
    'Encounter',
    'EncounterTransition',
    # Validators
    'StateValidator',
    'RequiredFieldsValidator',
    'NoBackwardsTransitionValidator',
    'FinalStateValidator',
    # Services
    'create_encounter',
    'transition',
    'get_encounter_history',
    'get_state_at',
    # Exceptions
    'EncounterError',
    'InvalidTransitionError',
    'ValidationError',
    'EncounterNotFoundError',
]

def __getattr__(name):
    if name in ('EncounterDefinition', 'Encounter', 'EncounterTransition'):
        from .models import EncounterDefinition, Encounter, EncounterTransition
        return locals()[name]
    if name in ('StateValidator', 'RequiredFieldsValidator',
                'NoBackwardsTransitionValidator', 'FinalStateValidator'):
        from .validators import (
            StateValidator, RequiredFieldsValidator,
            NoBackwardsTransitionValidator, FinalStateValidator
        )
        return locals()[name]
    if name in ('create_encounter', 'transition', 'get_encounter_history', 'get_state_at'):
        from .services import create_encounter, transition, get_encounter_history, get_state_at
        return locals()[name]
    if name in ('EncounterError', 'InvalidTransitionError',
                'ValidationError', 'EncounterNotFoundError'):
        from .exceptions import (
            EncounterError, InvalidTransitionError,
            ValidationError, EncounterNotFoundError
        )
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **State Machine**: Configurable states and transitions per definition
2. **Append-Only Transitions**: Immutable transition log
3. **Pluggable Validators**: Custom validation via class paths
4. **GenericFK Subject**: Encounters for any model type
5. **Temporal Queries**: get_state_at() for historical state

## Usage Examples

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
