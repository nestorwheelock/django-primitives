# Chapter 9: Workflow

> State machines. Explicit transitions. Humans are unreliable nodes.

## The Primitive

**Workflow** answers: What stages does work pass through, and what triggers transitions?

- Defined states
- Explicit transitions
- Guards and validations
- Humans are just another node

## django-primitives Implementation

- `django-encounters`: EncounterDefinition, EncounterState, Encounter, EncounterTransition

## Historical Origin

Manufacturing process control. Hospital patient flow. Government form processing. Any system where work moves through stages needs explicit workflow.

## Failure Mode When Ignored

- Status fields with no transition rules
- Invalid state combinations
- No history of transitions
- "How did it get into this state?"
- Workflow logic scattered across codebase

## Minimal Data Model

```python
class EncounterDefinition(models.Model):
    name = CharField()
    initial_state = CharField()
    states = JSONField()  # List of valid states
    transitions = JSONField()  # From -> To mappings with guards

class Encounter(models.Model):
    id = UUIDField(primary_key=True)
    definition = ForeignKey(EncounterDefinition)
    current_state = CharField()
    subject = GenericForeignKey()  # What this encounter is about
    started_at = DateTimeField()
    completed_at = DateTimeField(null=True)

class EncounterTransition(models.Model):
    encounter = ForeignKey(Encounter)
    from_state = CharField()
    to_state = CharField()
    transitioned_at = DateTimeField()
    actor = ForeignKey(Party)
    metadata = JSONField()
```

## Invariants That Must Never Break

1. Only defined transitions are allowed
2. Every transition is recorded
3. Current state is derived from last transition
4. Guards must pass before transition
5. Transitions are append-only

---

*Status: Planned*
