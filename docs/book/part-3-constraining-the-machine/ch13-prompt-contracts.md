# Chapter 13: Prompt Contracts

> Tell AI what it cannot do, not just what it should do.

## The Concept

A prompt contract defines:

- What the AI must do
- What the AI must not do
- What invariants must hold
- What outputs are acceptable

## Why Contracts Matter

Unconstrained prompts produce creative output. Creative output in ERP means bugs.

```
Bad:  "Build me an invoicing system"
Good: "Build an invoicing system where:
       - Invoices are immutable after posting
       - All amounts use Decimal, never float
       - Every invoice references a ledger transaction
       - Line items snapshot prices from catalog"
```

## Contract Structure

```markdown
## Must Do
- Use UUID primary keys
- Implement soft delete
- Add time semantics to events

## Must Not Do
- Never use auto-increment IDs
- Never store currency as float
- Never mutate historical records
- Never delete audit logs

## Invariants
- Transactions always balance
- Agreements are append-only
- Parties are never hard-deleted

## Acceptable Outputs
- Models inherit from BaseModel
- Services use @transaction.atomic
- Tests achieve >95% coverage
```

## Enforcement

Contracts are enforced by:

1. CLAUDE.md rules (always loaded)
2. Per-package prompts (loaded on demand)
3. Test suites (runtime verification)
4. Code review (human verification)

---

*Status: Planned*
