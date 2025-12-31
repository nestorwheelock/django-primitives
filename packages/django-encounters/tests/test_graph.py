"""Tests for graph validation pure functions.

These tests run WITHOUT Django model lifecycle - pure function testing.
"""

import pytest

from django_encounters.graph import validate_definition_graph, _find_reachable_states


class TestValidateDefinitionGraph:
    """Tests for validate_definition_graph pure function."""

    def test_valid_graph_returns_empty_errors(self):
        """A valid graph returns no errors."""
        states = ["pending", "active", "completed"]
        transitions = {"pending": ["active"], "active": ["completed"]}
        initial_state = "pending"
        terminal_states = ["completed"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert errors == []

    def test_invalid_initial_state_caught(self):
        """Initial state not in states list is caught."""
        states = ["pending", "active", "completed"]
        transitions = {"pending": ["active"]}
        initial_state = "unknown"
        terminal_states = ["completed"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert len(errors) == 1
        assert "initial_state 'unknown' not in states" in errors[0]

    def test_invalid_terminal_state_caught(self):
        """Terminal state not in states list is caught."""
        states = ["pending", "active", "completed"]
        transitions = {"pending": ["active"]}
        initial_state = "pending"
        terminal_states = ["finished"]  # Not in states

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert any("terminal_state 'finished' not in states" in e for e in errors)

    def test_transition_to_nonexistent_state_caught(self):
        """Transition to a state not in states list is caught."""
        states = ["pending", "active", "completed"]
        transitions = {"pending": ["active"], "active": ["unknown"]}  # unknown not in states
        initial_state = "pending"
        terminal_states = ["completed"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert any("transition to unknown state 'unknown'" in e for e in errors)

    def test_transition_from_unknown_state_caught(self):
        """Transition from a state not in states list is caught."""
        states = ["pending", "active", "completed"]
        transitions = {"pending": ["active"], "unknown": ["completed"]}
        initial_state = "pending"
        terminal_states = ["completed"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert any("transition from unknown state 'unknown'" in e for e in errors)

    def test_transition_from_terminal_state_caught(self):
        """Terminal states with outgoing transitions are caught."""
        states = ["pending", "active", "completed"]
        transitions = {"pending": ["active"], "active": ["completed"], "completed": ["pending"]}
        initial_state = "pending"
        terminal_states = ["completed"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert any("terminal state 'completed' has outgoing transitions" in e for e in errors)

    def test_unreachable_state_caught(self):
        """States unreachable from initial_state are caught."""
        states = ["pending", "active", "completed", "orphan"]
        transitions = {"pending": ["active"], "active": ["completed"]}
        initial_state = "pending"
        terminal_states = ["completed"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert any("state 'orphan' unreachable from initial_state" in e for e in errors)

    def test_unreachable_terminal_state_caught(self):
        """Terminal states that cannot be reached are caught."""
        states = ["pending", "active", "completed", "cancelled"]
        transitions = {"pending": ["active"], "active": ["completed"]}
        initial_state = "pending"
        terminal_states = ["completed", "cancelled"]  # cancelled unreachable

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert any("state 'cancelled' unreachable" in e for e in errors)

    def test_self_loops_allowed(self):
        """Self-loops are allowed by default (not an error)."""
        states = ["pending", "active", "completed"]
        transitions = {"pending": ["active", "pending"], "active": ["completed", "active"]}
        initial_state = "pending"
        terminal_states = ["completed"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert errors == []

    def test_empty_transitions_valid_if_initial_is_terminal(self):
        """Empty transitions valid when initial state is also terminal."""
        states = ["done"]
        transitions = {}
        initial_state = "done"
        terminal_states = ["done"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert errors == []

    def test_multiple_errors_returned_together(self):
        """All errors are collected and returned, not just the first."""
        states = ["pending", "completed"]
        transitions = {"unknown": ["nowhere"]}  # Multiple errors
        initial_state = "missing"
        terminal_states = ["gone"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        # Should have at least 3 errors: bad initial, bad terminal, bad transition
        assert len(errors) >= 3

    def test_multiple_terminal_states_valid(self):
        """Multiple terminal states are allowed."""
        states = ["pending", "active", "completed", "cancelled"]
        transitions = {
            "pending": ["active", "cancelled"],
            "active": ["completed", "cancelled"]
        }
        initial_state = "pending"
        terminal_states = ["completed", "cancelled"]

        errors = validate_definition_graph(states, transitions, initial_state, terminal_states)

        assert errors == []


class TestFindReachableStates:
    """Tests for _find_reachable_states helper."""

    def test_finds_direct_transitions(self):
        """Finds states directly reachable."""
        transitions = {"a": ["b"], "b": ["c"]}

        reachable = _find_reachable_states("a", transitions)

        assert "a" in reachable
        assert "b" in reachable
        assert "c" in reachable

    def test_start_state_always_reachable(self):
        """Start state is always in reachable set."""
        reachable = _find_reachable_states("start", {})

        assert "start" in reachable

    def test_handles_cycles(self):
        """Handles cycles without infinite loop."""
        transitions = {"a": ["b"], "b": ["c"], "c": ["a"]}

        reachable = _find_reachable_states("a", transitions)

        assert reachable == {"a", "b", "c"}

    def test_does_not_find_disconnected_states(self):
        """States not connected to start are not found."""
        transitions = {"a": ["b"], "x": ["y"]}

        reachable = _find_reachable_states("a", transitions)

        assert "a" in reachable
        assert "b" in reachable
        assert "x" not in reachable
        assert "y" not in reachable
