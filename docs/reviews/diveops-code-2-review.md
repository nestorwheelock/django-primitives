# Prompt: Build AI-Code Quality Gate + Scorecard for DiveOps (App Only)

## Role
You are a senior engineer implementing an automated evaluation pipeline to measure and enforce the quality of AI-generated code in this repo.

This repo contains Django primitives and a testbed application:
- DO NOT change primitive internals.
- Target: DiveOps app under testbed/primitives_testbed/diveops (and its tests/migrations).

## Mandatory Pre-Read
Before making changes:
1) Read claude.md and summarize the rules that affect CI, TDD, service-layer, and architecture.
2) Identify current test runner, lint config, and any existing CI workflow.

Deliver: "Constraints Recap" + "Current Tooling Recap".

---

## Goal
Create an evaluation pipeline that produces:
1) A machine-readable JSON scorecard per run (saved as an artifact)
2) CI gates that fail when quality/security regressions occur
3) A short human summary printed in CI logs

This should measure:
- Functional correctness (tests)
- Coverage (overall + diff if available)
- Static quality (lint/type)
- Security (SAST + dangerous-pattern greps)
- Maintainability (complexity + duplication light checks)
- Concurrency robustness (race-condition tests)

---

## Requirements

### A) Tests + Coverage (Primary Gate)
- Run the DiveOps test suite.
- Produce coverage XML + terminal summary.
- Enforce:
  - tests must pass
  - coverage must not decrease (use a configurable threshold if diff-based is hard)
  - write services must be covered (document how you approximate this)

Preferred tools: pytest + pytest-django + coverage.py (use existing repo patterns).

### B) Static Quality Gate
- Add/enable linting (prefer ruff if not present; otherwise existing linter).
- Fail CI on:
  - unused imports
  - obvious code smells (select a minimal set, don’t bikeshed style)

Optional: mypy if typing is already established (do not introduce typing overhaul).

### C) Security Gate (App-Level)
Add a lightweight SAST + grep-based checks:
1) bandit for Python (fail on High severity, warn on Medium)
2) grep checks that fail if introduced in DiveOps app:
   - csrf_exempt usage
   - mark_safe usage
   - raw SQL usage: cursor.execute, RawSQL, extra(
   - eval/exec
3) Optional: pip-audit (only if dependency lock is stable and the repo supports it)

Note: Do not scan primitive internals; focus on DiveOps app paths.

### D) Maintainability Gate (Practical)
Add two lightweight checks:
1) Complexity: flag any function in diveops/services.py or decisioning.py over a threshold
   - Keep threshold configurable (e.g., 12)
   - Prefer radon or ruff complexity if supported
2) Duplication: detect obvious duplicated blocks
   - Keep it light (don’t introduce heavy tooling). Even “identical > N lines” is acceptable.

### E) Concurrency Robustness Gate
- Ensure concurrency/race tests exist and are run in CI.
- If they do not exist, add minimal deterministic tests:
  - booking capacity race (book_trip)
  - trip completion race (complete_trip)
- Prefer a deterministic DB-transaction orchestration approach over ThreadPoolExecutor flakiness.
- If perfect determinism is not possible with the current harness, document the limitation and provide the best stable approximation.

### F) Scorecard Artifact
Generate a JSON file like:
{
  "timestamp": "...",
  "commit": "...",
  "tests": {"passed": true, "count": 280},
  "coverage": {"percent": 87.3, "threshold": 85.0, "ok": true},
  "lint": {"ok": true, "errors": 0},
  "security": {"bandit_high": 0, "grep_violations": []},
  "maintainability": {"max_complexity": 10, "dup_blocks": 0},
  "concurrency": {"race_tests_present": true, "race_tests_passed": true},
  "notes": []
}

- Save this as an artifact in CI.
- Print a short markdown-ish summary in the CI logs.

### G) Repo Integration
Implement:
- scripts under scripts/quality/ (or existing convention):
  - run_quality.sh or run_quality.py
  - generate_scorecard.py
- update CI workflow (GitHub Actions or existing system):
  - add a job "quality-gate"
  - cache dependencies appropriately
  - artifact upload for scorecard + coverage xml + bandit report

### H) Configurability
Add a small config file (YAML or TOML) for thresholds:
- coverage minimum
- max complexity
- duplication threshold
- bandit severity threshold

Do not add a massive config system.

---

## Output: What you must produce
1) A short implementation plan (steps + files)
2) The code changes (scripts + CI updates)
3) A sample scorecard JSON (from a local run or mocked if necessary)
4) A brief "How to run locally" section

---

## Guardrails (Non-Negotiable)
- Do not modify primitive package internals.
- Do not weaken security defaults (no adding csrf_exempt “for convenience”).
- Keep tools minimal; prefer existing tooling already in the repo.
- All changes must keep tests passing.

Proceed now by reading claude.md and identifying existing CI + test tooling, then implement incrementally.
