"""Base validator interface for encounter transitions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Encounter


class BaseEncounterValidator:
    """
    Base class for encounter transition validators.

    Validators are domain-specific and live OUTSIDE this package.
    They're registered via EncounterDefinition.validator_paths or settings.

    Example usage in a vertical package:

        class CheckoutRequirementsValidator(BaseEncounterValidator):
            def validate(self, encounter, from_state, to_state):
                if to_state != 'checkout':
                    return [], []

                blocks = []
                if not encounter.metadata.get('vitals_complete'):
                    blocks.append("Vitals required before checkout")
                return blocks, []
    """

    def validate(
        self,
        encounter: "Encounter",
        from_state: str,
        to_state: str
    ) -> tuple[list[str], list[str]]:
        """
        Validate a state transition.

        Args:
            encounter: The encounter being transitioned
            from_state: Current state
            to_state: Target state

        Returns:
            Tuple of (hard_blocks, soft_warnings)
            - hard_blocks: Transition cannot proceed (list of reasons)
            - soft_warnings: Transition allowed but with warnings (list)
        """
        return [], []
