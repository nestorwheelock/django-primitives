# Chapter 11: Audit

> Everything emits a trail. Silence is suspicious.

## The Primitive

**Audit** answers: What happened, when, by whom, and what changed?

- Append-only log
- Cannot be edited or deleted
- Captures before and after
- Logs are legal documents

## django-primitives Implementation

- `django-audit-log`: AuditLog, AuditAction, log(), log_create(), log_update(), log_delete()

## Historical Origin

Financial auditing. Legal discovery. Regulatory compliance. "Show me the receipts" is not optional in any serious system.

## Failure Mode When Ignored

- No record of changes
- "Who changed this?" unanswerable
- Compliance failures
- Legal liability
- Cannot debug production issues

## Minimal Data Model

```python
class AuditLog(models.Model):
    id = UUIDField(primary_key=True)
    target = GenericForeignKey()  # What was audited
    action = CharField()  # create, update, delete, view, custom
    actor = ForeignKey(Party, null=True)
    actor_repr = CharField()  # String snapshot of actor
    old_values = JSONField()
    new_values = JSONField()
    changed_fields = JSONField()  # List of field names
    message = TextField()
    metadata = JSONField()  # IP, user agent, etc.
    created_at = DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ImmutableLogError()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLogError("Audit logs cannot be deleted")
```

## Invariants That Must Never Break

1. Audit logs are append-only
2. Cannot update after creation
3. Cannot delete ever
4. Actor is captured at log time
5. Old and new values preserved

---

*Status: Planned*
