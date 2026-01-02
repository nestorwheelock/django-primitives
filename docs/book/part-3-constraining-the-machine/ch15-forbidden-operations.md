# Chapter 15: Forbidden Operations

> The most important rules are what you cannot do.

## The Concept

Constraints are more powerful than instructions. Tell AI what is forbidden, and correct behavior emerges.

## The Forbidden List

### Data Integrity

- **Never** use auto-increment primary keys
- **Never** store currency as float
- **Never** delete audit logs
- **Never** mutate posted transactions
- **Never** edit agreements (version instead)

### Time

- **Never** use naive datetimes
- **Never** assume "now" is when it happened
- **Never** backdate recorded_at (only effective_at)
- **Never** query without "as of" context

### Identity

- **Never** hard-delete parties
- **Never** assume one user = one person
- **Never** store roles in user table
- **Never** skip relationship time bounds

### Architecture

- **Never** import from higher layers
- **Never** put business logic in models
- **Never** skip the service layer
- **Never** invent new primitives

## Enforcement Mechanisms

| Level | Mechanism |
|-------|-----------|
| Prompt | CLAUDE.md rules |
| Code | Model constraints, validators |
| Database | CHECK constraints, triggers |
| Test | Negative test cases |
| Review | Human verification |

## The Negative Test Pattern

For every forbidden operation, write a test that proves it fails:

```python
def test_cannot_delete_audit_log():
    log = AuditLog.objects.create(...)
    with pytest.raises(ImmutableLogError):
        log.delete()

def test_cannot_update_audit_log():
    log = AuditLog.objects.create(...)
    log.message = "changed"
    with pytest.raises(ImmutableLogError):
        log.save()
```

Forbidden operations are tested, not trusted.

---

*Status: Planned*
