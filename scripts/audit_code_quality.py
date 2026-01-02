#!/usr/bin/env python3
"""
Code Quality Inspection Suite for Django Primitives.

Runs senior-level code review tests against packages or files.
Each test produces structured findings that can be used for review.

Usage:
  # Run all tests on a package
  python scripts/audit_code_quality.py --package django-parties

  # Run specific test
  python scripts/audit_code_quality.py --package django-ledger --test naming

  # Run on specific file
  python scripts/audit_code_quality.py --file packages/django-parties/src/django_parties/selectors.py

  # Generate prompt for Claude review
  python scripts/audit_code_quality.py --package django-parties --test intent --prompt

  # Output JSON report
  python scripts/audit_code_quality.py --package django-parties --json out/quality.json

Available tests:
  intent       - Single responsibility violations
  naming       - Unclear or misleading names
  side_effects - Hidden I/O and mutations
  data_access  - N+1, query efficiency (Django ORM)
  complexity   - Nested conditionals, long functions
  errors       - Exception handling patterns
  testability  - Coupling and mock-ability
  architecture - Layer violations
  pr_review    - Would you approve this PR?
  all          - Run all tests
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable


# =============================================================================
# TEST DEFINITIONS
# =============================================================================

TESTS = {
    "intent": {
        "name": "Intent & Responsibility Test",
        "goal": "Detect unclear purpose and mixed responsibilities",
        "prompt": """Review the following code as a senior engineer.

For each function or class:

1. State its single responsibility in one sentence.
2. List all responsibilities it currently performs.
3. Flag any function that has more than one responsibility.

Do not suggest rewrites yet. Only identify violations.

PASS CONDITION: Every function has exactly one responsibility.""",
    },

    "naming": {
        "name": "Naming & Semantics Test",
        "goal": "Catch junior naming that hides intent",
        "prompt": """Review the code and identify:

* Function names that do not describe intent.
* Variable names that are vague, overloaded, or misleading.

For each issue:

* Explain what the name *suggests*
* Explain what the code *actually does*
* Propose a senior-level name that reflects intent.

Do not rename everything. Only flag names that materially reduce clarity.

PASS CONDITION: Names reflect domain intent, not mechanics.""",
    },

    "side_effects": {
        "name": "Side Effects & Hidden I/O Test",
        "goal": "Surface surprise behavior",
        "prompt": """Identify all functions with side effects.

For each function, state:

* Whether it performs I/O (DB, network, filesystem)
* Whether it mutates external state
* Whether those side effects are obvious from the name and signature

Flag any function whose side effects are non-obvious.

PASS CONDITION: Side effects are explicit and predictable.""",
    },

    "data_access": {
        "name": "Data Access Efficiency Test",
        "goal": "Catch N+1, query leaks, and Python-side filtering",
        "prompt": """Inspect all ORM usage.

Identify:

* Queries inside loops
* `.all()` followed by Python filtering
* Missing `select_related` / `prefetch_related`
* Repeated `.count()` or `.exists()` calls

For each issue:

* Describe the inefficiency
* Estimate its impact at scale
* Propose the minimal fix

PASS CONDITION: Query count is bounded and intentional.""",
    },

    "complexity": {
        "name": "Control Flow & Complexity Test",
        "goal": "Kill pyramids of doom",
        "prompt": """Review control flow in all functions.

Flag:

* Deeply nested conditionals (>2 levels)
* Long functions (>40 lines)
* Repeated conditional logic across functions

For each, propose:

* Guard clause refactor, or
* Extraction into a pure helper function

PASS CONDITION: Control flow is flat and readable.""",
    },

    "errors": {
        "name": "Error Handling & Failure Semantics Test",
        "goal": "Ensure failures are deliberate, not accidental",
        "prompt": """Identify all error handling patterns.

Flag:

* Broad exception catches (except Exception, bare except)
* Silent failures (pass in except block)
* Returning None without explanation
* Swallowed exceptions without logging

For each case:

* State what failure is being handled
* Whether the handling is appropriate
* Where the failure *should* be handled instead (layer-wise)

PASS CONDITION: Errors fail loudly at boundaries, quietly internally.""",
    },

    "testability": {
        "name": "Testability & Refactor Safety Test",
        "goal": "Ensure the code can be safely changed",
        "prompt": """Evaluate how testable this code is.

Identify:

* Logic tightly coupled to Django (request/response in business logic)
* Hard-to-mock dependencies (inline imports, global state)
* Missing seams for testing (no dependency injection)
* Functions that require full database setup to test

Propose:

* One characterization test per risky area
* One refactor that improves testability without changing behavior

PASS CONDITION: Core logic can be tested without full system setup.""",
    },

    "architecture": {
        "name": "Architecture Alignment Test",
        "goal": "Enforce layered discipline",
        "prompt": """Map each function/class to a layer:

* View / Controller - HTTP handling only
* Service (write) - Business logic that mutates
* Selector (read) - Query logic, read-only
* Validator - Input validation
* Model - Data structure and invariants

Flag:

* Cross-layer violations (view calling model directly for complex queries)
* Business logic in views (if/else logic, calculations)
* Write logic in selectors (create/update/delete in read functions)
* Query logic in models (complex filtering in model methods)

Propose how to relocate code to the correct layer.

PASS CONDITION: Each layer has a single, clear role.""",
    },

    "pr_review": {
        "name": "PR Review Test",
        "goal": "Force a senior judgment",
        "prompt": """Assume this code is a pull request from a junior developer.

Would you approve it?

* Yes / No

If No, provide:

1. BLOCKING ISSUES (must fix before merge):
   - List each issue with file:line reference

2. NON-BLOCKING SUGGESTIONS (improve but not required):
   - List improvements for follow-up PR

3. ACCEPTANCE CHECKLIST:
   - [ ] Specific items that must be true before approval

PASS CONDITION: Feedback is concrete and actionable.""",
    },
}


# =============================================================================
# FULL REVIEW META-PROMPT (Django-Primitives Architecture-Aware)
# =============================================================================

FULL_REVIEW_PROMPT = """You are acting as a senior engineer reviewing code in the django-primitives ecosystem.

Project context (must follow):
- We have a layered/package-tier architecture. Lower tiers may NOT import higher tiers.
- Domain models should inherit from django_basemodels.BaseModel (UUID, timestamps, soft delete).
- "Plain models" are only allowed in rare foundation/pattern cases and must be annotated with an allow-marker comment.
- Read access should go through selectors (read-only API). Write logic belongs in services.
- Views should be thin: parse input -> call service/selector -> render response.
- Django ORM performance matters: avoid N+1, avoid queries in loops, prefer select_related/prefetch_related.
- Packages must expose __version__ in package __init__.py and must have README.md.
- Avoid direct import of django.contrib.auth.models.User; use get_user_model or settings.AUTH_USER_MODEL patterns.
- Prefer UniqueConstraint over unique_together (advisory).
- Append-only models should guard updates (advisory unless clearly required).

TASK:
Given the code I provide (one or more files), run an ordered quality inspection and produce a single structured report.

ORDERED INSPECTION (do in this exact order and include each section even if "No issues"):

1) Intent & Responsibility
   - For each function/class: 1 sentence responsibility.
   - Flag SRP violations (mixed concerns).

2) Layering & Architecture Alignment
   - Map each function/class/module to a layer: View/Controller, Selector (read), Service (write), Validator, Model, Admin, Forms.
   - Flag cross-layer violations and propose relocation targets (file/module names).

3) Package Tier / Import Hygiene
   - Identify any imports that violate lower->higher tier rule, or cause circular imports risk.
   - Note any imports that should be "lazy" (deferred) to avoid side effects at import time.

4) BaseModel / Model Rules
   - Verify domain models inherit BaseModel.
   - Identify any "plain model" usage and whether it has a proper allow-marker.
   - Verify GenericFK object_id uses CharField (if applicable).
   - Check ForeignKey on_delete usage for audit/history-like models (avoid CASCADE there).

5) ORM / Query Efficiency Review (Django-specific)
   - Identify likely N+1 patterns, queries in loops, Python filtering after .all(), repeated count/exists.
   - For each issue: show the exact code line(s) responsible and the minimal fix (select_related/prefetch_related/query rewrite).
   - Provide an estimated impact statement (query count growth or O(N) pattern).

6) Naming & Semantics
   - Flag misleading names (functions/vars).
   - Provide senior-level rename suggestions only where it materially improves clarity.

7) Error Handling & Failure Semantics
   - Identify silent failures, broad excepts, None returns without contract.
   - Recommend where errors should be handled (boundary vs internal).

8) Testability & Refactor Safety
   - Identify risky areas lacking seams.
   - Propose characterization tests (what to assert) before refactor.

9) Hygiene Requirements
   - Confirm README.md and __version__ presence/consistency for the package(s) represented.
   - If missing, propose minimal content/stub and where it should live.

10) Senior Rewrite Proposal (minimal-diff)
    - Choose ONE high-leverage improvement (smallest change that yields biggest clarity/perf win).
    - Provide:
      a) Before snippet
      b) After snippet
      c) Why it's safer/better
    - Constraint: no behavior change, no new features, minimal diff.

OUTPUT FORMAT (strict):
- Title: "Django-Primitives Code Quality Report"
- A short "Executive Summary" (5 bullets max): biggest risks and quickest wins.
- Then sections 1-10 exactly, with:
  - Findings (bullets)
  - Evidence (quote small snippets, not entire files)
  - Recommendation (actionable, minimal)
- End with "Action Checklist":
  - P0 (must-fix), P1 (should-fix), P2 (nice-to-have)
  - Each item: file -> change -> reason.

RULES:
- Do not invent files or code that was not provided.
- If you need more context, continue anyway and explicitly mark assumptions.
- Prefer minimal diffs and architecture-consistent moves.
- No generic advice. Every point must tie to a concrete spot in the provided code.

---

## Code to Review

{code}
"""


# =============================================================================
# STATIC ANALYZERS (Pre-LLM checks)
# =============================================================================

@dataclass
class StaticFinding:
    """A finding from static analysis."""
    test: str
    severity: str  # critical, warning, info
    file: str
    line: int
    code: str
    message: str


class StaticAnalyzer(ast.NodeVisitor):
    """AST-based static analysis for code quality issues."""

    def __init__(self, filename: str, source: str):
        self.filename = filename
        self.source = source
        self.lines = source.splitlines()
        self.findings: list[StaticFinding] = []
        self.current_function: str | None = None
        self.nesting_depth = 0
        self.function_lines: dict[str, int] = {}

    def get_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_func = self.current_function
        self.current_function = node.name

        # Check function length
        func_lines = node.end_lineno - node.lineno if node.end_lineno else 0
        if func_lines > 40:
            self.findings.append(StaticFinding(
                test="complexity",
                severity="warning",
                file=self.filename,
                line=node.lineno,
                code=f"def {node.name}(...)",
                message=f"Function is {func_lines} lines (>40). Consider extracting logic."
            ))

        # Check naming
        if len(node.name) < 3 or node.name in ('do', 'run', 'go', 'f', 'fn', 'func'):
            self.findings.append(StaticFinding(
                test="naming",
                severity="warning",
                file=self.filename,
                line=node.lineno,
                code=f"def {node.name}",
                message=f"Function name '{node.name}' is too vague. Use intent-revealing name."
            ))

        self.generic_visit(node)
        self.current_function = old_func

    def visit_If(self, node: ast.If):
        self.nesting_depth += 1
        if self.nesting_depth > 3:
            self.findings.append(StaticFinding(
                test="complexity",
                severity="warning",
                file=self.filename,
                line=node.lineno,
                code=self.get_line(node.lineno),
                message=f"Nesting depth {self.nesting_depth} (>3). Use guard clauses or extract."
            ))
        self.generic_visit(node)
        self.nesting_depth -= 1

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # Check for broad exception catches
        if node.type is None:
            self.findings.append(StaticFinding(
                test="errors",
                severity="critical",
                file=self.filename,
                line=node.lineno,
                code=self.get_line(node.lineno),
                message="Bare 'except:' catches everything including KeyboardInterrupt."
            ))
        elif isinstance(node.type, ast.Name) and node.type.id == 'Exception':
            self.findings.append(StaticFinding(
                test="errors",
                severity="warning",
                file=self.filename,
                line=node.lineno,
                code=self.get_line(node.lineno),
                message="Broad 'except Exception'. Catch specific exceptions."
            ))

        # Check for silent failures (pass in except)
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.findings.append(StaticFinding(
                test="errors",
                severity="critical",
                file=self.filename,
                line=node.lineno,
                code=self.get_line(node.lineno),
                message="Silent failure: 'except: pass'. Log or re-raise."
            ))

        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        # Check for unexplained None returns
        if node.value is None:
            # This is 'return' or 'return None' - check context
            pass  # Hard to detect without more context
        self.generic_visit(node)


def run_static_analysis(filepath: Path) -> list[StaticFinding]:
    """Run static analysis on a Python file."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
        analyzer = StaticAnalyzer(str(filepath), source)
        analyzer.visit(tree)
        return analyzer.findings
    except SyntaxError:
        return []
    except Exception:
        return []


# =============================================================================
# CODE COLLECTION
# =============================================================================

def collect_code(path: Path, extensions: set[str] = {'.py'}) -> dict[str, str]:
    """Collect source code from a path (file or directory)."""
    code_map: dict[str, str] = {}

    if path.is_file():
        if path.suffix in extensions:
            code_map[str(path)] = path.read_text()
    elif path.is_dir():
        for py_file in path.rglob("*.py"):
            if "__pycache__" not in str(py_file) and "migrations" not in str(py_file):
                try:
                    code_map[str(py_file)] = py_file.read_text()
                except Exception:
                    pass

    return code_map


def format_code_for_review(code_map: dict[str, str], max_lines: int = 500) -> str:
    """Format collected code for LLM review."""
    output = []
    total_lines = 0

    for filepath, content in sorted(code_map.items()):
        lines = content.splitlines()
        if total_lines + len(lines) > max_lines:
            # Truncate
            remaining = max_lines - total_lines
            if remaining > 20:
                lines = lines[:remaining]
                output.append(f"\n### {filepath} (truncated)\n```python\n{chr(10).join(lines)}\n```")
            break

        output.append(f"\n### {filepath}\n```python\n{content}\n```")
        total_lines += len(lines)

    return "\n".join(output)


# =============================================================================
# REPORT GENERATION
# =============================================================================

@dataclass
class TestResult:
    """Result of running a quality test."""
    test_id: str
    test_name: str
    goal: str
    static_findings: list[StaticFinding] = field(default_factory=list)
    pass_status: str = "pending"  # pass, fail, pending
    notes: str = ""


def generate_prompt(test_id: str, code: str) -> str:
    """Generate a review prompt for a specific test."""
    if test_id not in TESTS:
        return f"Unknown test: {test_id}"

    test = TESTS[test_id]

    return f"""# Code Quality Test: {test['name']}

**Goal:** {test['goal']}

## Instructions

{test['prompt']}

## Code to Review

{code}

---

Provide your analysis following the test instructions above.
"""


def generate_checklist(test_results: list[TestResult]) -> str:
    """Generate a review checklist from test results."""
    output = ["# Code Quality Review Checklist\n"]
    output.append(f"Generated: {datetime.now().isoformat()}\n")

    for result in test_results:
        status_icon = {"pass": "✅", "fail": "❌", "pending": "⏳"}.get(result.pass_status, "?")
        output.append(f"\n## {status_icon} {result.test_name}\n")
        output.append(f"**Goal:** {result.goal}\n")

        if result.static_findings:
            output.append("\n### Static Analysis Findings\n")
            for finding in result.static_findings:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(finding.severity, "")
                output.append(f"- {icon} `{finding.file}:{finding.line}` - {finding.message}")

        output.append(f"\n**Status:** {result.pass_status.upper()}")
        if result.notes:
            output.append(f"\n**Notes:** {result.notes}")

    return "\n".join(output)


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Code quality inspection suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    ap.add_argument("--package", help="Package to audit (e.g., django-parties)")
    ap.add_argument("--file", help="Specific file to audit")
    ap.add_argument("--test", default="all",
                    help="Test to run: " + ", ".join(list(TESTS.keys()) + ["all"]))
    ap.add_argument("--root", default=".", help="Repository root")
    ap.add_argument("--prompt", action="store_true",
                    help="Output prompt for Claude review")
    ap.add_argument("--json", help="Output JSON report to file")
    ap.add_argument("--checklist", action="store_true",
                    help="Output markdown checklist")
    ap.add_argument("--static-only", action="store_true",
                    help="Only run static analysis (no prompts)")
    ap.add_argument("--full-review", action="store_true",
                    help="Generate comprehensive senior review prompt (architecture-aware)")
    ap.add_argument("--max-lines", type=int, default=500,
                    help="Max lines of code to include in prompts (default: 500)")
    args = ap.parse_args()

    root = Path(args.root).resolve()

    # Determine what to analyze
    if args.file:
        target_path = Path(args.file)
        if not target_path.is_absolute():
            target_path = root / target_path
        target_name = target_path.name
    elif args.package:
        pkg_name = args.package.replace("django-", "django_")
        target_path = root / "packages" / args.package / "src" / pkg_name
        target_name = args.package
    else:
        print("ERROR: Specify --package or --file")
        return 1

    if not target_path.exists():
        print(f"ERROR: Path not found: {target_path}")
        return 1

    # Collect code
    code_map = collect_code(target_path)
    if not code_map:
        print(f"ERROR: No Python files found in {target_path}")
        return 1

    formatted_code = format_code_for_review(code_map, max_lines=args.max_lines)

    # Determine which tests to run
    if args.test == "all":
        test_ids = list(TESTS.keys())
    else:
        test_ids = [args.test]
        if args.test not in TESTS:
            print(f"ERROR: Unknown test '{args.test}'")
            print(f"Available: {', '.join(TESTS.keys())}")
            return 1

    # Run static analysis
    all_static_findings: list[StaticFinding] = []
    for filepath in code_map.keys():
        findings = run_static_analysis(Path(filepath))
        all_static_findings.extend(findings)

    # Build test results
    results: list[TestResult] = []
    for test_id in test_ids:
        test = TESTS[test_id]
        static_for_test = [f for f in all_static_findings if f.test == test_id]

        # Determine pass/fail based on static analysis
        critical_count = sum(1 for f in static_for_test if f.severity == "critical")
        pass_status = "fail" if critical_count > 0 else ("pending" if not args.static_only else "pass")

        results.append(TestResult(
            test_id=test_id,
            test_name=test["name"],
            goal=test["goal"],
            static_findings=static_for_test,
            pass_status=pass_status,
        ))

    # Output
    if args.full_review:
        # Generate comprehensive senior review prompt
        print(FULL_REVIEW_PROMPT.format(code=formatted_code))

    elif args.prompt:
        # Generate prompts for Claude review
        for test_id in test_ids:
            print("=" * 70)
            print(generate_prompt(test_id, formatted_code))
            print("=" * 70)
            print()

    elif args.checklist:
        print(generate_checklist(results))

    elif args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)

        output = {
            "timestamp": datetime.now().isoformat(),
            "target": str(target_path),
            "files_analyzed": len(code_map),
            "tests": [
                {
                    "id": r.test_id,
                    "name": r.test_name,
                    "goal": r.goal,
                    "status": r.pass_status,
                    "findings": [
                        {
                            "severity": f.severity,
                            "file": f.file,
                            "line": f.line,
                            "message": f.message,
                        }
                        for f in r.static_findings
                    ]
                }
                for r in results
            ]
        }

        json_path.write_text(json.dumps(output, indent=2))
        print(f"Report written to: {json_path}")

    else:
        # Default: print summary
        print("=" * 70)
        print(f"CODE QUALITY AUDIT: {target_name}")
        print(f"Files analyzed: {len(code_map)}")
        print(f"Time: {datetime.now().isoformat()}")
        print("=" * 70)

        total_critical = 0
        total_warnings = 0

        for result in results:
            critical = sum(1 for f in result.static_findings if f.severity == "critical")
            warnings = sum(1 for f in result.static_findings if f.severity == "warning")
            total_critical += critical
            total_warnings += warnings

            icon = "✅" if critical == 0 else "❌"
            print(f"\n{icon} {result.test_name}")
            print(f"   Critical: {critical}, Warnings: {warnings}")

            if critical > 0:
                for f in result.static_findings:
                    if f.severity == "critical":
                        print(f"   🔴 {f.file}:{f.line} - {f.message}")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Tests run: {len(results)}")
        print(f"Critical issues: {total_critical}")
        print(f"Warnings: {total_warnings}")

        if total_critical == 0 and total_warnings == 0:
            print("\n✅ All static checks pass.")
            print("   Run with --prompt to generate Claude review prompts.")
        else:
            print("\n❌ Issues found. Fix critical issues before review.")

        return 1 if total_critical > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
