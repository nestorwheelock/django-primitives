# Chapter 5: Time

> "As of" is more important than "now."

## The Primitive

**Time** answers: When did things actually happen, and when did we learn about them?

Two timestamps, always:
- `effective_at`: When it happened in reality
- `recorded_at`: When we learned about it

## django-primitives Implementation

- `django-decisioning`: TimeSemanticsMixin, EffectiveDatedMixin
- EventAsOfQuerySet, EffectiveDatedQuerySet

## Historical Origin

Bitemporal data modeling. Insurance claims, legal proceedings, financial audits. The question is never just "what happened" but "what did we know, and when did we know it?"

## Failure Mode When Ignored

- Cannot backdate corrections
- Cannot answer "what was the state at time X?"
- Cannot distinguish late data from wrong data
- Auditors ask questions you cannot answer
- Legal discovery becomes archaeology

## Minimal Data Model

```python
class TimeSemanticsMixin(models.Model):
    effective_at = DateTimeField(default=timezone.now)
    recorded_at = DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

class EffectiveDatedMixin(models.Model):
    valid_from = DateTimeField()
    valid_to = DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
```

## Invariants That Must Never Break

1. Every fact has two timestamps
2. `recorded_at` is immutable (auto_now_add)
3. `effective_at` can be in the past (backdating is accuracy)
4. Queries must specify "as of when"
5. Current state is just "as of now"

---

*Status: Planned*
