# Chapter 14: Schema-First Generation

> Define the shape, then fill it in.

## The Concept

Do not ask AI to invent structure. Give AI the structure and ask it to implement.

```
Bad:  "Create a model for tracking work sessions"
Good: "Create WorkSession with these exact fields:
       - user: FK to AUTH_USER_MODEL
       - started_at: DateTimeField(default=now)
       - stopped_at: DateTimeField(null=True)
       - duration_seconds: IntegerField(null=True)
       - target: GenericForeignKey"
```

## Why Schema-First Works

1. **No Invention** - AI cannot hallucinate fields
2. **Consistency** - Same schema across regenerations
3. **Review** - Humans approve schema before code
4. **Testing** - Test cases derive from schema

## The Per-Package Prompt Pattern

Each primitive has a rebuild prompt:

```markdown
# Prompt: Rebuild django-worklog

## Models Specification

### WorkSession Model

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUIDField | primary_key=True |
| user | ForeignKey | AUTH_USER_MODEL |
| started_at | DateTimeField | default=timezone.now |
| stopped_at | DateTimeField | null=True |
| duration_seconds | IntegerField | null=True |

## Test Cases (31 tests)

1. test_session_creation
2. test_session_has_uuid_pk
3. test_session_user_fk
...
```

## The Rebuild Guarantee

With schema-first prompts:

- Delete the package
- Run the prompt
- Get identical output
- All tests pass

Reproducibility proves correctness.

---

*Status: Planned*
