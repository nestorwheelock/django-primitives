# Chapter 10: Decisions

> Who decided what, when, and why.

## The Primitive

**Decisions** answers: What choices were made, by whom, with what information, producing what outcome?

- Auditable intent
- Reproducible outcomes
- Idempotent operations
- Decision points as first-class objects

## django-primitives Implementation

- `django-decisioning`: Decision, IdempotencyKey, @idempotent decorator, TargetRef

## Historical Origin

Legal proceedings. Medical diagnostics. Loan approvals. Any domain where "why was this decision made?" matters requires explicit decision records.

## Failure Mode When Ignored

- No record of why something happened
- Cannot reproduce decision logic
- Double-processing on retry
- "Who approved this?"
- Audit trail is inference, not fact

## Minimal Data Model

```python
class Decision(models.Model):
    id = UUIDField(primary_key=True)
    decision_type = CharField()
    target = GenericForeignKey()  # What was decided about
    actor = ForeignKey(Party)
    inputs = JSONField()  # What information was available
    outcome = CharField()  # approved, rejected, deferred
    rationale = TextField()
    effective_at = DateTimeField()
    recorded_at = DateTimeField(auto_now_add=True)

class IdempotencyKey(models.Model):
    key = CharField(unique=True)
    created_at = DateTimeField(auto_now_add=True)
    expires_at = DateTimeField()
    status = CharField()  # pending, completed, failed
    result = JSONField(null=True)
```

## Invariants That Must Never Break

1. Every decision records inputs and outcome
2. Decisions are immutable
3. Idempotent operations use keys
4. Retries return same result
5. Decision logic is reproducible from inputs

---

*Status: Planned*
