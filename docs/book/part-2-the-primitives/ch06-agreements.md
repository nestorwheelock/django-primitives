# Chapter 6: Agreements

> Terms as data, not prose.

## The Primitive

**Agreements** answer: What was promised, by whom, and under what conditions?

- Two or more parties
- Terms that can be computed
- Amendments are append-only
- Snapshots of conditions at signing

## django-primitives Implementation

- `django-agreements`: Agreement, AgreementVersion, Term, Signatory

## Historical Origin

Contracts. The Code of Hammurabi. Every exchange beyond barter requires agreement on terms. Software that handles money, services, or obligations must encode this.

## Failure Mode When Ignored

- Terms stored as free text (uncomputable)
- No versioning (which terms applied?)
- Edits instead of amendments (history lost)
- No signatory tracking (who agreed?)
- Price changes affect past orders

## Minimal Data Model

```python
class Agreement(models.Model):
    id = UUIDField(primary_key=True)
    agreement_type = CharField()
    status = CharField()  # draft, active, expired, terminated
    effective_at = DateTimeField()
    expires_at = DateTimeField(null=True)

class AgreementVersion(models.Model):
    agreement = ForeignKey(Agreement)
    version_number = IntegerField()
    terms = JSONField()  # Computable, not prose
    created_at = DateTimeField(auto_now_add=True)

class Signatory(models.Model):
    agreement_version = ForeignKey(AgreementVersion)
    party = ForeignKey(Party)
    signed_at = DateTimeField()
    signature_metadata = JSONField()
```

## Invariants That Must Never Break

1. Agreements are never edited, only versioned
2. Terms are structured data, not free text
3. Each version records who signed
4. Past versions remain queryable
5. Snapshots freeze terms at transaction time

---

*Status: Planned*
