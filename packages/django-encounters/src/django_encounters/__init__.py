"""
django-encounters: Domain-agnostic encounter state machine.

Provides:
- EncounterDefinition: Define reusable state machine graphs
- Encounter: Instance attached to any subject via GenericFK
- EncounterTransition: Audit log of all state changes
- Pluggable validators for hard blocks and soft warnings
"""

__version__ = "0.1.0"

default_app_config = "django_encounters.apps.DjangoEncountersConfig"
