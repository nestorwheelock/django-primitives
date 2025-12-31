"""
Pure function validators for encounter definition graphs.

These functions validate state machine graphs without any Django model lifecycle.
Used by EncounterDefinition.clean() AND tests directly.
"""


def validate_definition_graph(
    states: list[str],
    transitions: dict[str, list[str]],
    initial_state: str,
    terminal_states: list[str]
) -> list[str]:
    """
    Validate state machine graph is sane and usable.

    Returns list of error messages (empty = valid).

    Checks:
    - initial_state exists in states
    - all terminal_states exist in states
    - all transition sources and targets exist in states
    - terminal states have no outgoing transitions
    - all states reachable from initial_state
    - all terminal states reachable

    Args:
        states: List of valid state names
        transitions: Dict mapping state -> list of reachable states
        initial_state: Starting state for new encounters
        terminal_states: States that end the encounter (no outgoing transitions)

    Returns:
        List of error message strings (empty if valid)
    """
    errors = []
    states_set = set(states)

    # Basic membership: initial_state in states
    if initial_state not in states_set:
        errors.append(f"initial_state '{initial_state}' not in states")

    # Basic membership: terminal_states subset of states
    for ts in terminal_states:
        if ts not in states_set:
            errors.append(f"terminal_state '{ts}' not in states")

    # Transition sources and targets exist in states
    for from_state, to_states in transitions.items():
        if from_state not in states_set:
            errors.append(f"transition from unknown state '{from_state}'")
        for to_state in to_states:
            if to_state not in states_set:
                errors.append(f"transition to unknown state '{to_state}'")

    # Terminal states have no outgoing transitions
    for ts in terminal_states:
        if ts in transitions and transitions[ts]:
            errors.append(f"terminal state '{ts}' has outgoing transitions")

    # Reachability: all states reachable from initial_state
    if initial_state in states_set:  # Only check if initial_state is valid
        reachable = _find_reachable_states(initial_state, transitions)
        for state in states:
            if state not in reachable:
                errors.append(f"state '{state}' unreachable from initial_state")

    return errors


def _find_reachable_states(start: str, transitions: dict[str, list[str]]) -> set[str]:
    """
    BFS to find all reachable states from start.

    Args:
        start: Starting state
        transitions: Dict mapping state -> list of reachable states

    Returns:
        Set of all states reachable from start (including start itself)
    """
    visited = {start}
    queue = [start]

    while queue:
        current = queue.pop(0)
        for next_state in transitions.get(current, []):
            if next_state not in visited:
                visited.add(next_state)
                queue.append(next_state)

    return visited
