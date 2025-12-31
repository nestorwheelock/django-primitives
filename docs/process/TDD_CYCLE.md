# The 26-Step TDD Development Cycle

**Status:** Authoritative
**Enforcement:** All development follows this cycle

---

## Overview

Every task follows this 26-step cycle. No exceptions. Steps are grouped into phases for clarity, but the sequence is linear.

```
Phase 2.1: Planning (Steps 1-6)
Phase 2.2: TDD (Steps 7-10)
Phase 2.3: Quality (Steps 11-14)
Phase 2.4: Git (Steps 15-18)
Phase 2.5: Review (Steps 19-23)
Phase 2.6: Ship to Repo (Step 24)
Phase 2.7: Deploy to Test (Step 25)
Phase 2.8: Deploy to Production (Step 26) - MANUAL ONLY
```

---

## Phase 2.1: Planning & Questions (Steps 1-6)

### Step 1: Validate Planning Documents

Check that the request matches existing plans:
- Does a user story exist for this work?
- Does a task definition exist?
- Are prerequisites complete?

**If no planning exists:** Create task document first, or refuse to proceed.

### Step 2: Review Existing Code

Before writing anything:
- Search for similar implementations (use Grep/Glob)
- Check for existing patterns to follow
- Identify code that might be affected

**Goal:** Prevent duplication and understand context.

### Step 3: Verify Prerequisites Complete

Check that dependencies are done:
- Required models exist?
- Required services exist?
- Required migrations applied?

**If prerequisites missing:** Complete them first or document blocker.

### Step 4: Ask Clarifying Questions

Before implementation, clarify:
- Ambiguous requirements
- Edge cases
- Performance expectations
- Error handling approach

**Rule:** Ask before assuming.

### Step 5: Validate Acceptance Criteria

Confirm you understand "done":
- List acceptance criteria
- Identify test cases needed
- Confirm scope boundaries

### Step 6: Identify Dependencies and Patterns

Document:
- What existing code to reuse
- What patterns to follow
- What new patterns to establish

---

## Phase 2.2: Test-Driven Development (Steps 7-10)

### Step 7: Write Failing Tests First

**TDD STOP GATE - Output this before any code:**

```
=== TDD STOP GATE ===
Task: [task ID and name]
[x] I have read CONTRACT.md
[x] I have read the task's required reading
[x] I have read the acceptance criteria
[x] I am writing TESTS FIRST
=== PROCEEDING WITH FAILING TESTS ===
```

Then write tests based on acceptance criteria:

```python
def test_create_pet_with_valid_data_succeeds():
    pet = PetService.create(name="Max", species="dog")
    assert pet.id is not None
    assert pet.name == "Max"

def test_create_pet_without_name_raises_error():
    with pytest.raises(ValidationError):
        PetService.create(name="", species="dog")
```

### Step 8: Run Tests - Confirm They Fail

```bash
pytest -v
```

**Expected output:** Tests fail because implementation doesn't exist.

**Show the failure output.** This proves the test catches the right thing.

### Step 9: Write Minimal Code to Pass

Write the **minimum** code to make the test pass:

```python
class PetService:
    @staticmethod
    def create(name: str, species: str) -> Pet:
        if not name:
            raise ValidationError("Name required")
        return Pet.objects.create(name=name, species=species)
```

**Rule:** Don't over-engineer. Pass the test, nothing more.

### Step 10: Run Tests - Confirm They Pass

```bash
pytest -v
```

**Expected output:** All tests pass.

Repeat Steps 7-10 for each piece of functionality.

---

## Phase 2.3: Code Quality & Documentation (Steps 11-14)

### Step 11: Refactor While Keeping Tests Green

Now that tests pass, improve the code:
- Extract common patterns
- Improve naming
- Reduce duplication

**Rule:** Run tests after each refactor. Stay green.

### Step 12: Add Error Handling and Edge Cases

- Add validation for edge cases
- Add proper error messages
- Handle boundary conditions

Write tests for edge cases first (TDD).

### Step 13: Update Documentation

- Update docstrings
- Update README if public API changed
- Update usage examples

### Step 14: Run Full Test Suite

```bash
pytest --cov=. --cov-fail-under=95
```

**Requirements:**
- All tests pass
- Coverage >= 95%
- No regressions in other tests

---

## Phase 2.4: Git Workflow (Steps 15-18)

### Step 15: Git Add

```bash
git add -A
```

Review what's staged:
```bash
git status
git diff --staged
```

### Step 16: Git Commit

Use conventional commit format:

```bash
git commit -m "feat(pets): add pet creation service

- Add PetService.create() with validation
- Add tests for valid and invalid inputs
- 95% coverage on new code

Closes #123"
```

**Format:**
```
type(scope): brief description

- Bullet points explaining changes
- Include test coverage info

Closes #X (for tasks)
Addresses #X (for bugs - no auto-close)
```

### Step 17: Git Push

```bash
git push origin main  # or feature branch
```

### Step 18: Update Tracking

- Mark todo as complete
- Update GitHub issue
- Update project board

---

## Phase 2.5: Review & Iteration (Steps 19-23)

### Step 19: Code Review

Self-review or peer review:
- [ ] Code follows conventions
- [ ] No security issues
- [ ] No performance issues
- [ ] Tests are meaningful

### Step 20: Testing Review

- [ ] Coverage meets 95%
- [ ] Edge cases covered
- [ ] Tests are independent
- [ ] Tests are fast

### Step 21: Fix Issues Found

If review finds issues:
- Write test for the issue (TDD)
- Fix the issue
- Run all tests

### Step 22: Re-test, Re-commit, Re-push

```bash
pytest -v
git add -A
git commit --amend  # or new commit
git push --force-with-lease  # if amended
```

### Step 23: Review Complete

All checks pass, ready for deployment.

---

## Phase 2.6: Ship to Repository (Step 24)

### Step 24: Final Commit & Push

Ensure everything is synced:

```bash
git status  # Should be clean
git log -1  # Verify last commit
git push    # Sync to remote
```

Verify on GitHub that commit appears.

---

## Phase 2.7: Deploy to Test Server (Step 25)

### Step 25: Deploy to Staging

```bash
# Build and deploy
docker-compose build
docker-compose up -d

# Verify
docker-compose logs
curl http://localhost:8000/health/
```

Run smoke tests on staging:
- Core functionality works
- No error logs
- Performance acceptable

---

## Phase 2.8: Deploy to Production (Step 26)

### Step 26: Production Deployment (MANUAL ONLY)

**This step requires explicit user request.**

Never auto-deploy to production.

Checklist:
- [ ] All tests pass on staging
- [ ] No critical bugs in staging
- [ ] User explicitly requested deploy
- [ ] Backup taken (if applicable)

Then deploy:
```bash
# Production deploy command
./deploy-production.sh
```

Monitor after deploy:
- Error rates
- Performance metrics
- User feedback

---

## TDD Cycle Complete Output

After completing all steps, output:

```
=== TDD CYCLE COMPLETE ===
Task: [task ID and name]
Tests written BEFORE implementation: YES
All tests passing: YES
Coverage: 97%
Committed: abc1234
Pushed: YES
Staging: VERIFIED
=== READY FOR PRODUCTION (if requested) ===
```

---

## Quick Reference

```
┌─────────────────────────────────────────────────────┐
│  26-STEP TDD CYCLE CHECKLIST                        │
├─────────────────────────────────────────────────────┤
│  PLANNING (1-6)                                     │
│  □ 1. Validate planning docs exist                  │
│  □ 2. Review existing code                          │
│  □ 3. Verify prerequisites complete                 │
│  □ 4. Ask clarifying questions                      │
│  □ 5. Validate acceptance criteria                  │
│  □ 6. Identify dependencies and patterns            │
├─────────────────────────────────────────────────────┤
│  TDD (7-10)                                         │
│  □ 7. Write failing tests FIRST                     │
│  □ 8. Run tests - confirm they FAIL                 │
│  □ 9. Write minimal code to pass                    │
│  □ 10. Run tests - confirm they PASS                │
├─────────────────────────────────────────────────────┤
│  QUALITY (11-14)                                    │
│  □ 11. Refactor (keep tests green)                  │
│  □ 12. Add error handling / edge cases              │
│  □ 13. Update documentation                         │
│  □ 14. Run full test suite (95%+ coverage)          │
├─────────────────────────────────────────────────────┤
│  GIT (15-18)                                        │
│  □ 15. Git add                                      │
│  □ 16. Git commit (conventional format)             │
│  □ 17. Git push                                     │
│  □ 18. Update tracking (todos, issues)              │
├─────────────────────────────────────────────────────┤
│  REVIEW (19-23)                                     │
│  □ 19. Code review                                  │
│  □ 20. Testing review                               │
│  □ 21. Fix issues found                             │
│  □ 22. Re-test, re-commit, re-push                  │
│  □ 23. Review complete                              │
├─────────────────────────────────────────────────────┤
│  SHIP (24-26)                                       │
│  □ 24. Final commit & push                          │
│  □ 25. Deploy to staging                            │
│  □ 26. Deploy to production (MANUAL ONLY)           │
└─────────────────────────────────────────────────────┘
```

---

## Why 26 Steps?

Previous versions had 23 steps, which bundled deployment. The 26-step version explicitly separates:

- Step 24: Ship to repository (always)
- Step 25: Deploy to staging (always)
- Step 26: Deploy to production (only when requested)

This prevents accidental production deploys and makes the staging step mandatory.
