"""Service functions for encounter management.

Provides:
- create_encounter: Create new encounter from definition
- transition: Move encounter to new state
- get_allowed_transitions: Get valid next states
- validate_transition: Check if transition is valid
"""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .conf import get_validators_for_definition
from .exceptions import InvalidTransition, TransitionBlocked, DefinitionNotFound
from .models import Encounter, EncounterDefinition, EncounterTransition


def create_encounter(
    definition_key: str,
    subject,
    created_by=None,
    metadata: dict = None,
) -> Encounter:
    """
    Create a new encounter from a definition.

    Args:
        definition_key: The key of the EncounterDefinition to use
        subject: The subject model instance (any model via GenericFK)
        created_by: Optional user who created the encounter
        metadata: Optional initial metadata dict

    Returns:
        The created Encounter instance

    Raises:
        DefinitionNotFound: If definition_key doesn't exist
    """
    try:
        definition = EncounterDefinition.objects.get(key=definition_key, active=True)
    except EncounterDefinition.DoesNotExist:
        raise DefinitionNotFound(definition_key)

    encounter = Encounter.objects.create(
        definition=definition,
        subject_type=ContentType.objects.get_for_model(subject),
        subject_id=subject.pk,
        state=definition.initial_state,
        created_by=created_by,
        metadata=metadata or {},
    )

    return encounter


def get_allowed_transitions(encounter: Encounter) -> list[str]:
    """
    Get list of valid next states from definition.

    Args:
        encounter: The encounter to check

    Returns:
        List of state names that can be transitioned to
    """
    definition = encounter.definition
    current_state = encounter.state

    # Terminal states have no outgoing transitions
    if current_state in definition.terminal_states:
        return []

    return definition.transitions.get(current_state, [])


def validate_transition(
    encounter: Encounter,
    to_state: str,
) -> tuple[bool, list[str], list[str]]:
    """
    Validate whether a transition is allowed.

    Checks:
    1. Graph validity (to_state is in allowed transitions)
    2. Custom validators from definition

    Args:
        encounter: The encounter to transition
        to_state: Target state

    Returns:
        Tuple of (allowed, hard_blocks, soft_warnings)
    """
    hard_blocks = []
    soft_warnings = []

    # Check graph validity
    allowed_states = get_allowed_transitions(encounter)
    if to_state not in allowed_states:
        if encounter.state in encounter.definition.terminal_states:
            hard_blocks.append(f"Cannot transition from terminal state '{encounter.state}'")
        else:
            hard_blocks.append(
                f"Transition from '{encounter.state}' to '{to_state}' not allowed"
            )
        return False, hard_blocks, soft_warnings

    # Run custom validators
    validators = get_validators_for_definition(encounter.definition)
    for validator in validators:
        blocks, warnings = validator.validate(encounter, encounter.state, to_state)
        hard_blocks.extend(blocks)
        soft_warnings.extend(warnings)

    allowed = len(hard_blocks) == 0
    return allowed, hard_blocks, soft_warnings


@transaction.atomic
def transition(
    encounter: Encounter,
    to_state: str,
    by_user=None,
    override_warnings: bool = False,
    metadata: dict = None,
) -> Encounter:
    """
    Transition encounter to a new state.

    Creates an audit record and updates the encounter state.
    Sets ended_at when reaching a terminal state.

    Args:
        encounter: The encounter to transition
        to_state: Target state
        by_user: Optional user performing the transition
        override_warnings: If True, proceed despite soft warnings
        metadata: Optional metadata for the transition record

    Returns:
        The updated Encounter instance

    Raises:
        InvalidTransition: If to_state not in allowed transitions
        TransitionBlocked: If validators return hard blocks
    """
    # First check graph validity (this is always a hard error)
    allowed_states = get_allowed_transitions(encounter)
    if to_state not in allowed_states:
        if encounter.state in encounter.definition.terminal_states:
            raise InvalidTransition(
                encounter.state, to_state,
                f"Cannot transition from terminal state '{encounter.state}'"
            )
        raise InvalidTransition(encounter.state, to_state)

    # Now run validators (these raise TransitionBlocked, not InvalidTransition)
    allowed, hard_blocks, soft_warnings = validate_transition(encounter, to_state)

    if hard_blocks:
        raise TransitionBlocked(hard_blocks)

    if soft_warnings and not override_warnings:
        raise TransitionBlocked(soft_warnings)

    from_state = encounter.state

    # Create audit record
    transition_metadata = metadata or {}
    if soft_warnings and override_warnings:
        transition_metadata["overridden_warnings"] = soft_warnings

    EncounterTransition.objects.create(
        encounter=encounter,
        from_state=from_state,
        to_state=to_state,
        transitioned_by=by_user,
        metadata=transition_metadata,
    )

    # Update encounter state
    encounter.state = to_state

    # Set ended_at if reaching terminal state
    if to_state in encounter.definition.terminal_states:
        encounter.ended_at = timezone.now()

    encounter.save(update_fields=["state", "ended_at", "updated_at"])

    return encounter
