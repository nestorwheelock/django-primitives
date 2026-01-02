# Chapter 21: Schema-First Generation

## The Rebuild Test

In 2023, a developer accidentally deleted an entire Django package from a monorepo. Thirty-seven models, 80 tests, 2,000 lines of code. Gone.

Three hours later, the package was rebuilt from scratch. Every model, every field, every test. The new code was functionally identical to the original.

This was not magic. It was not extraordinary programming skill. It was the result of a simple practice: schema-first generation.

The package had a rebuild prompt. The prompt specified every model, every field, every test case. When the code was lost, regenerating it was just running the prompt again.

This chapter explains how to write prompts that make your code reproducible.

---

## Why Schema-First Works

When you ask AI to "create a model for tracking work sessions," you get whatever the AI thinks a work session model should look like.

Today you might get:
```python
class WorkSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)
```

Tomorrow, with the same prompt, you might get:
```python
class Session(models.Model):
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(blank=True, null=True)
    duration = models.DurationField(null=True)
```

Both are reasonable. Neither is reproducible.

Schema-first generation eliminates this variance by specifying exactly what the output should be:

```markdown
### WorkSession Model

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUIDField | primary_key=True, default=uuid.uuid4 |
| user | ForeignKey | settings.AUTH_USER_MODEL, on_delete=PROTECT |
| started_at | DateTimeField | default=timezone.now |
| stopped_at | DateTimeField | null=True, blank=True |
| duration_seconds | IntegerField | null=True, blank=True |
```

With this schema, every regeneration produces the same model. Field names match. Types match. Constraints match. Tests that depend on these fields continue to work.

---

## The Anatomy of a Rebuild Prompt

A rebuild prompt is a complete specification for generating a package from scratch. It has six sections:

### 1. Package Purpose

One paragraph explaining what this package does and why it exists.

```markdown
## Package Purpose

Provide time-tracking primitives for recording work sessions.
Sessions have a start time, optional stop time, and can be attached
to any model via GenericForeignKey. Only one session per user can
be active at a time (starting a new session stops the previous one).
```

This is not marketing copy. This is the single-sentence answer to "what does this do?"

### 2. Dependencies

What this package requires to work.

```markdown
## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel)
- django.contrib.contenttypes (for GenericForeignKey)
- django.contrib.auth (for user reference)
```

Dependencies are both runtime (what must be installed) and conceptual (what patterns must be understood).

### 3. File Structure

The exact files that should be created.

```markdown
## File Structure

packages/django-worklog/
├── pyproject.toml
├── README.md
├── src/django_worklog/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_models.py
    └── test_services.py
```

The AI knows exactly what to create. No invention required.

### 4. Models Specification

The exact schema for each model, including field names, types, and constraints.

```markdown
## Models Specification

### WorkSession Model

class WorkSession(UUIDModel, BaseModel):
    """
    A time-bounded work session attached to any target.

    Only one session per user can be active (started but not stopped).
    Starting a new session automatically stops any active session.
    """

    # Owner
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='work_sessions'
    )

    # Target via GenericFK
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+'
    )
    target_id = models.CharField(max_length=255, blank=True, default='')
    target = GenericForeignKey('target_content_type', 'target_id')

    # Timing
    started_at = models.DateTimeField(default=timezone.now)
    stopped_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Metadata
    session_type = models.CharField(max_length=50, default='work')
    notes = models.TextField(blank=True, default='')
```

This is not pseudo-code. This is the actual code that should be generated. Field names, types, defaults, help text—everything specified.

### 5. Service Functions

The exact function signatures and behaviors.

```markdown
## Services Specification

### start_session()

def start_session(
    user,
    target=None,
    session_type: str = 'work',
    notes: str = '',
    stop_active: bool = True,
) -> WorkSession:
    """
    Start a new work session for a user.

    Args:
        user: The user starting the session
        target: Optional object to attach session to (GenericFK)
        session_type: Type of session (default 'work')
        notes: Optional notes
        stop_active: If True, stop any active session first

    Returns:
        The new WorkSession

    Raises:
        ActiveSessionError: If stop_active=False and user has active session
    """
```

Function signatures are contracts. If the AI generates different signatures, the code that calls these functions breaks.

### 6. Test Cases

A numbered list of every test that must pass.

```markdown
## Test Cases (31 tests)

### WorkSession Model Tests (12 tests)
1. test_session_creation - Create with required fields
2. test_session_has_uuid_pk - UUID primary key
3. test_session_user_fk - User foreign key works
4. test_session_target_generic_fk - GenericFK to any model
5. test_session_started_at_default - Default to now
6. test_session_stopped_at_nullable - Can be null
7. test_session_duration_calculated - Duration computed on stop
8. test_session_is_active_property - True if not stopped
9. test_session_ordering - Ordered by started_at desc
10. test_session_soft_delete - Soft delete works
11. test_session_target_id_as_string - Stores UUID as string
12. test_session_str_representation - String format

### Service Function Tests (19 tests)
13. test_start_session_creates_session
14. test_start_session_with_target
15. test_start_session_stops_active
...
```

Test names are specific. Each test has a one-line description. When the AI writes tests, it knows exactly what to test.

---

## The Rebuild Guarantee

A properly written rebuild prompt provides a guarantee:

1. Delete the package
2. Run the prompt
3. Get identical output
4. All tests pass

This is not aspirational. This is the test. If regenerating the package produces different output or breaks tests, the prompt is incomplete.

### Testing the Guarantee

Every rebuild prompt should be tested:

```bash
# Save current test count
pytest packages/django-worklog/tests/ --collect-only | grep "test" > original.txt

# Delete the package
rm -rf packages/django-worklog/

# Regenerate from prompt
# (run AI with docs/prompts/django-worklog.md)

# Verify tests pass
pytest packages/django-worklog/tests/ -v

# Compare test count
pytest packages/django-worklog/tests/ --collect-only | grep "test" > regenerated.txt
diff original.txt regenerated.txt
```

If the diff is empty and all tests pass, the prompt is complete.

---

## The Complete Prompt Pattern

Here is the full pattern used for every primitive package:

```markdown
# Prompt: Rebuild [package-name]

## Instruction

Create a Django package called `[package-name]` that provides [purpose].

## Package Purpose

[1-3 sentences explaining what this package does]

## Dependencies

- Django >= 4.2
- [other dependencies]

## File Structure

[exact directory and file layout]

## Exceptions Specification

[custom exception classes]

## Models Specification

[complete model definitions with all fields]

## QuerySet Specification

[custom QuerySet methods if any]

## Services Specification

[all service function signatures and docstrings]

## __init__.py Exports

[what the package exports]

## Test Cases (N tests)

[numbered list of every test]

## Key Behaviors

[summary of important behaviors]

## Usage Examples

[example code showing how to use the package]

## Acceptance Criteria

[checklist for completion]
```

---

## Real Example: django-worklog Prompt

Here is the actual rebuild prompt for django-worklog (abbreviated for space):

```markdown
# Prompt: Rebuild django-worklog

## Instruction

Create a Django package called `django-worklog` that provides time-tracking
primitives for recording work sessions with automatic switch behavior.

## Package Purpose

Provide time-tracking capabilities:
- `WorkSession` - Time-bounded session with GenericFK target
- `start_session()` - Start a session (auto-stops active)
- `stop_session()` - Stop active session
- `get_active_session()` - Get user's current session
- Switch policy: starting new session stops previous

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel, BaseModel)
- django.contrib.contenttypes
- django.contrib.auth

## Models Specification

### WorkSession Model

class WorkSession(UUIDModel, BaseModel):
    """
    A time-bounded work session attached to any target.
    """

    # Owner
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='work_sessions'
    )

    # Target via GenericFK
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    target_id = models.CharField(max_length=255, blank=True)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Timing
    started_at = models.DateTimeField(default=timezone.now)
    stopped_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    @property
    def is_active(self) -> bool:
        return self.stopped_at is None

## Services Specification

### start_session()

def start_session(user, target=None, session_type='work',
                  stop_active=True) -> WorkSession:
    """Start a new session, optionally stopping any active one."""

### stop_session()

def stop_session(user) -> Optional[WorkSession]:
    """Stop the user's active session if one exists."""

### get_active_session()

def get_active_session(user) -> Optional[WorkSession]:
    """Get the user's currently active session, or None."""

## Test Cases (31 tests)

### Model Tests (12)
1. test_session_creation
2. test_session_uuid_pk
3. test_session_user_fk
4. test_session_target_generic_fk
5. test_session_started_at_default
6. test_session_stopped_at_nullable
7. test_session_duration_calculated
8. test_session_is_active_true
9. test_session_is_active_false
10. test_session_ordering
11. test_session_soft_delete
12. test_session_str

### Service Tests (19)
13. test_start_session_creates
14. test_start_session_with_target
15. test_start_session_stops_previous
16. test_start_session_error_when_active
...

## Acceptance Criteria

- [ ] WorkSession with GenericFK target
- [ ] Switch policy (start new = stop old)
- [ ] Duration calculated on stop
- [ ] All 31 tests passing
- [ ] README with examples
```

With this prompt, the package can be rebuilt at any time. The AI doesn't invent. It executes.

---

## Why Tables Work Better Than Prose

Notice how the models specification uses structured format, not prose:

**Prose (harder to follow):**
```markdown
The WorkSession model should have a user field that is a foreign key
to AUTH_USER_MODEL with PROTECT on delete. It should also have fields
for tracking start and stop times, with the stop time being nullable.
The duration should be stored in seconds as an integer.
```

**Structured (precise):**
```markdown
### WorkSession Model

| Field | Type | Constraints |
|-------|------|-------------|
| user | ForeignKey | AUTH_USER_MODEL, on_delete=PROTECT |
| started_at | DateTimeField | default=timezone.now |
| stopped_at | DateTimeField | null=True, blank=True |
| duration_seconds | IntegerField | null=True, blank=True |
```

Tables eliminate ambiguity. The AI cannot misinterpret "should have fields for tracking" because every field is explicitly named and typed.

---

## The Test Case Numbering System

Notice how test cases are numbered, not just named:

```markdown
## Test Cases (31 tests)

### Model Tests (12)
1. test_session_creation
2. test_session_uuid_pk
...

### Service Tests (19)
13. test_start_session_creates
14. test_start_session_with_target
...
```

Numbering serves three purposes:

1. **Counting**: You know exactly how many tests should exist. If the AI generates 29 tests, something is missing.

2. **Ordering**: The AI writes tests in a predictable order. Code review becomes easier when you know where each test should appear.

3. **Reference**: You can refer to specific tests by number. "Test 14 is failing" is clearer than "the test for starting with target."

---

## Handling Edge Cases in Prompts

Schema-first doesn't mean no edge cases. It means edge cases are explicitly specified:

```markdown
## Edge Cases

### What if user starts session when one is active?
- If stop_active=True: Stop existing session, start new one
- If stop_active=False: Raise ActiveSessionError

### What if stop_session called with no active session?
- Return None (not an error)
- Log a warning

### What if target is deleted?
- GenericFK becomes orphaned (target returns None)
- Session remains valid
- Use target_content_type and target_id for historical reference
```

Every "what if" you can think of goes in the prompt. The AI doesn't decide edge case behavior. You do.

---

## Hands-On Exercise: Write a Rebuild Prompt

Take an existing model in your codebase. Write a rebuild prompt for it.

**Step 1: Document the Purpose**
What does this model do? Why does it exist?

**Step 2: Document the Schema**
Every field, type, and constraint. Use a table.

**Step 3: Document the Behaviors**
What methods does it have? What are the edge cases?

**Step 4: Document the Tests**
Number every test. One line each.

**Step 5: Test the Prompt**
Can an AI regenerate the model from just this prompt? If not, what's missing?

---

## What AI Gets Wrong About Schemas

### Over-Engineering

Given freedom, AI adds fields you didn't ask for:
```python
class WorkSession(models.Model):
    # Your specified fields
    user = models.ForeignKey(...)
    started_at = models.DateTimeField(...)

    # AI additions (not requested)
    created_by = models.ForeignKey(...)  # Redundant with user
    status = models.CharField(...)        # Over-engineering
    priority = models.IntegerField(...)   # Not needed
    tags = models.ManyToManyField(...)    # Feature creep
```

**Solution:** Be explicit that the schema is exhaustive. "The model has ONLY these fields. Do not add additional fields."

### Field Name Creativity

Given similar concepts, AI uses inconsistent names:
```python
# In WorkSession
started_at = models.DateTimeField()

# In a different model, same session
begin_time = models.DateTimeField()
```

**Solution:** Include a naming conventions section:
```markdown
## Naming Conventions
- Datetime fields: [verb]_at (started_at, stopped_at, created_at)
- Boolean fields: is_[adjective] (is_active, is_deleted)
- Foreign keys: [related_model] (user, organization)
```

### Default Value Drift

Given prompts at different times, AI uses different defaults:
```python
# First generation
session_type = models.CharField(max_length=50, default='work')

# Second generation
session_type = models.CharField(max_length=100, default='general')
```

**Solution:** Specify every default explicitly. Never leave defaults to interpretation.

---

## Why This Matters Later

Schema-first generation is the foundation of reproducible AI-assisted development.

Without schema-first:
- Every regeneration is different
- Tests break when code is regenerated
- Migrations conflict between versions
- Team members generate incompatible code

With schema-first:
- Code is reproducible
- Tests are stable
- Migrations are predictable
- Anyone can regenerate the same package

In the next chapter, we'll explore the flip side: forbidden operations. If schema-first tells AI what to build, forbidden operations tell AI what to never do.

---

## Summary

| Concept | Purpose |
|---------|---------|
| Schema-first | Specify exact output before generation |
| Rebuild prompt | Complete specification for regenerating a package |
| Models specification | Exact fields, types, constraints |
| Services specification | Exact function signatures |
| Test cases | Numbered list of required tests |
| Rebuild guarantee | Delete, regenerate, tests pass |
| Tables over prose | Eliminate ambiguity |
| Edge case documentation | Explicit handling of special cases |

The goal is not to constrain AI. The goal is to make AI's output predictable.

When you can delete a package and regenerate it identically, you have escaped the trap of irreproducible code.

---

## The Prompt Collection

The complete rebuild prompts for all primitives are in Part II of this book:

| Package | Chapter | Test Count |
|---------|---------|------------|
| django-parties | Chapter 6: Identity | 44 tests |
| django-rbac | Chapter 6: Identity | 30 tests |
| django-agreements | Chapter 8: Agreements | 47 tests |
| django-catalog | Chapter 9: Catalog | 83 tests |
| django-ledger | Chapter 10: Ledger | 48 tests |
| django-money | Chapter 10: Ledger | 63 tests |
| django-encounters | Chapter 11: Workflow | 80 tests |
| django-decisioning | Chapter 12: Decisions | 78 tests |
| django-audit-log | Chapter 13: Audit | 23 tests |

Each prompt follows the pattern in this chapter. Each package can be rebuilt from its prompt.

That is the power of schema-first generation.
