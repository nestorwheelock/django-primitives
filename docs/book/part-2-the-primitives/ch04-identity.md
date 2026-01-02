# Chapter 4: Identity

> Before you can do anything, you must know who is doing it.

## The Primitive

**Identity** answers: Who are the actors in this system?

- People (customers, employees, contractors)
- Organizations (companies, departments, vendors)
- Groups (teams, committees, households)
- Service accounts (systems, integrations)

## django-primitives Implementation

- `django-parties`: Person, Organization, Group, PartyRelationship
- `django-rbac`: Role, Permission, UserRole with hierarchy

## Historical Origin

Every civilization starts with identity. Census records. Tax rolls. Membership lists. Before you can trade, tax, or govern, you must answer: who?

## Failure Mode When Ignored

- User table becomes god object
- "Customer" means five different things
- No distinction between person and org
- Roles hardcoded in if-statements
- No party relationships (who works for whom?)

## Minimal Data Model

```python
class Party(models.Model):
    id = UUIDField(primary_key=True)
    party_type = CharField()  # person, organization, group
    created_at = DateTimeField()
    deleted_at = DateTimeField(null=True)  # Never truly deleted

class PartyRelationship(models.Model):
    from_party = ForeignKey(Party)
    to_party = ForeignKey(Party)
    relationship_type = CharField()  # employee_of, member_of, owns
    valid_from = DateTimeField()
    valid_to = DateTimeField(null=True)
```

## Invariants That Must Never Break

1. Every actor is a Party
2. Parties are never deleted, only soft-deleted
3. Relationships have time bounds
4. A Party can have multiple types over time

---

*Status: Planned*
