#!/usr/bin/env python3
"""
Performance Audit Script for Django Primitives.

Analyzes packages for:
- Potential N+1 query patterns
- Missing select_related/prefetch_related
- Loops with DB operations
- Memory-intensive patterns
- Missing query count tests

Generates:
- Query-count test templates
- Profiling runbooks
- Performance fix recommendations

Usage:
  python scripts/audit_performance.py --root .
  python scripts/audit_performance.py --root . --package django-parties
  python scripts/audit_performance.py --root . --generate-tests
  python scripts/audit_performance.py --root . --json out/performance_audit.json
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
from typing import Iterator


@dataclass
class PerformanceIssue:
    """A detected performance issue."""
    category: str  # n_plus_one, loop_query, memory, missing_prefetch, etc.
    severity: str  # critical, warning, info
    file: str
    line: int
    code: str
    message: str
    fix: str


@dataclass
class PackageAudit:
    """Performance audit results for a package."""
    package: str
    issues: list[PerformanceIssue] = field(default_factory=list)
    hot_paths: list[str] = field(default_factory=list)
    query_budget: dict[str, int] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


class PerformanceAnalyzer(ast.NodeVisitor):
    """AST visitor that detects performance anti-patterns."""

    def __init__(self, filename: str, source: str):
        self.filename = filename
        self.source = source
        self.lines = source.splitlines()
        self.issues: list[PerformanceIssue] = []
        self.in_loop = False
        self.loop_depth = 0
        self.current_function = None
        self.hot_paths: list[str] = []

    def get_line(self, lineno: int) -> str:
        """Get source line (1-indexed)."""
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_function = self.current_function
        self.current_function = node.name

        # Identify potential hot paths (selectors, views, services)
        if any(hint in node.name for hint in ['get_', 'list_', 'search_', 'filter_']):
            self.hot_paths.append(f"{self.filename}:{node.name}")

        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)  # type: ignore

    def visit_For(self, node: ast.For):
        self.loop_depth += 1
        old_in_loop = self.in_loop
        self.in_loop = True
        self.generic_visit(node)
        self.in_loop = old_in_loop
        self.loop_depth -= 1

    def visit_While(self, node: ast.While):
        self.loop_depth += 1
        old_in_loop = self.in_loop
        self.in_loop = True
        self.generic_visit(node)
        self.in_loop = old_in_loop
        self.loop_depth -= 1

    def visit_ListComp(self, node: ast.ListComp):
        # Check for DB calls inside list comprehensions
        old_in_loop = self.in_loop
        self.in_loop = True
        self.generic_visit(node)
        self.in_loop = old_in_loop

    def visit_Call(self, node: ast.Call):
        # Detect ORM operations - must have .objects in chain to be ORM
        call_str = self._get_call_string(node)

        # Check if this is likely an ORM operation (has .objects somewhere)
        is_orm_call = '.objects.' in call_str or '.objects)' in call_str

        # N+1 patterns: DB calls inside loops (only flag confirmed ORM operations)
        if self.in_loop and is_orm_call:
            # These are definitely DB operations when preceded by .objects
            orm_operations = [
                ('.objects.get(', 'get'),
                ('.objects.filter(', 'filter'),
                ('.objects.exclude(', 'exclude'),
                ('.objects.all()', 'all'),
                ('.objects.first()', 'first'),
                ('.objects.last()', 'last'),
                ('.objects.count()', 'count'),
                ('.objects.exists()', 'exists'),
                ('.objects.create(', 'create'),
                ('.objects.values(', 'values'),
                ('.objects.values_list(', 'values_list'),
            ]
            for pattern, op_name in orm_operations:
                if pattern in call_str:
                    self.issues.append(PerformanceIssue(
                        category="n_plus_one",
                        severity="critical",
                        file=self.filename,
                        line=node.lineno,
                        code=self.get_line(node.lineno),
                        message=f"ORM operation '.objects.{op_name}()' inside loop (N+1 query pattern)",
                        fix=f"Move query outside loop, use prefetch_related/select_related, or batch with __in lookup"
                    ))
                    break

        # Bulk operation opportunities - only flag .objects.create in loop
        if self.in_loop and '.objects.create(' in call_str:
            self.issues.append(PerformanceIssue(
                category="bulk_opportunity",
                severity="critical",
                file=self.filename,
                line=node.lineno,
                code=self.get_line(node.lineno),
                message="Model.objects.create() inside loop",
                fix="Use bulk_create() for batch insertion"
            ))

        # .save() in loop (need to check it's on a model instance)
        if self.in_loop and isinstance(node.func, ast.Attribute):
            if node.func.attr == 'save':
                # Heuristic: if calling .save() on something, it might be a model
                # Only flag if not in a list comprehension (those are often intentional)
                line = self.get_line(node.lineno)
                if '.save()' in line and 'for ' not in line:
                    self.issues.append(PerformanceIssue(
                        category="bulk_opportunity",
                        severity="warning",
                        file=self.filename,
                        line=node.lineno,
                        code=line,
                        message="Model.save() inside loop",
                        fix="Consider bulk_update() if updating multiple rows"
                    ))

        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        # Detect repeated linear searches: `x in list` patterns
        # This is tricky to detect via AST, simplified check
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        # Detect `x in large_list` patterns
        for op in node.ops:
            if isinstance(op, ast.In):
                # If right side is a list/queryset and we're in a loop, flag it
                if self.in_loop and self.loop_depth > 0:
                    self.issues.append(PerformanceIssue(
                        category="linear_search",
                        severity="info",
                        file=self.filename,
                        line=node.lineno,
                        code=self.get_line(node.lineno),
                        message="'in' check inside loop (potential O(n*m) if checking against list)",
                        fix="Convert list to set for O(1) membership testing"
                    ))
        self.generic_visit(node)

    def _get_call_string(self, node: ast.Call) -> str:
        """Get a string representation of the call for pattern matching."""
        try:
            return ast.unparse(node)
        except:
            return ""


def analyze_file(filepath: Path) -> tuple[list[PerformanceIssue], list[str]]:
    """Analyze a Python file for performance issues."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
        analyzer = PerformanceAnalyzer(str(filepath), source)
        analyzer.visit(tree)
        return analyzer.issues, analyzer.hot_paths
    except SyntaxError:
        return [], []
    except Exception as e:
        return [], []


def analyze_for_missing_prefetch(filepath: Path) -> list[PerformanceIssue]:
    """Check for querysets that should use select_related/prefetch_related."""
    issues = []
    try:
        source = filepath.read_text()

        # Pattern: .objects.filter/all() without select_related on FK models
        # This is a heuristic - look for FK access patterns

        # Find views/selectors that return querysets without prefetch
        queryset_pattern = r'\.objects\.(filter|all|exclude)\([^)]*\)(?!\.select_related|\.prefetch_related)'

        for i, line in enumerate(source.splitlines(), 1):
            if re.search(queryset_pattern, line):
                # Check if there's related access nearby (within 10 lines)
                context = source.splitlines()[max(0, i-1):min(len(source.splitlines()), i+10)]
                context_str = '\n'.join(context)

                # Look for FK traversal patterns
                fk_patterns = [
                    r'\.\w+_set\.', r'\.related_', r'\.from_\w+', r'\.to_\w+',
                    r'for .+ in .+:', r'\.\w+\.\w+\.'  # Nested attribute access
                ]

                for pattern in fk_patterns:
                    if re.search(pattern, context_str):
                        issues.append(PerformanceIssue(
                            category="missing_prefetch",
                            severity="info",
                            file=str(filepath),
                            line=i,
                            code=line.strip(),
                            message="QuerySet may benefit from select_related/prefetch_related",
                            fix="Add .select_related('fk_field') or .prefetch_related('reverse_relation')"
                        ))
                        break
    except Exception:
        pass

    return issues


def generate_query_count_test(package: str, hot_paths: list[str]) -> str:
    """Generate a query count test template for a package."""
    test_template = f'''"""
Query count tests for {package}.

These tests enforce query budgets to prevent N+1 regressions.
Run with: pytest tests/test_query_counts.py -v
"""
import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection


class TestQueryBudgets:
    """Enforce query count limits on critical paths."""

'''

    for path in hot_paths[:5]:  # Top 5 hot paths
        func_name = path.split(':')[-1] if ':' in path else 'operation'
        test_template += f'''
    @pytest.mark.django_db
    def test_{func_name}_query_count(self):
        """Verify {func_name} stays within query budget."""
        # TODO: Set up test data
        # records = [Model.objects.create(...) for _ in range(10)]

        with CaptureQueriesContext(connection) as context:
            # TODO: Call the function under test
            # result = {func_name}(...)
            pass

        # TODO: Set expected query count
        expected_queries = 2  # 1 for main query + 1 for prefetch
        assert len(context) <= expected_queries, (
            f"Query budget exceeded: {{len(context)}} > {{expected_queries}}\\n"
            f"Queries:\\n" + "\\n".join(q['sql'] for q in context)
        )
'''

    return test_template


def generate_profiling_runbook(package: str, issues: list[PerformanceIssue]) -> str:
    """Generate a profiling runbook for a package."""
    runbook = f'''# Performance Profiling Runbook: {package}

Generated: {datetime.now().isoformat()}

## Quick Start

### 1. Install profiling tools
```bash
pip install django-debug-toolbar pyinstrument py-spy
```

### 2. Enable query logging (settings.py)
```python
LOGGING = {{
    'version': 1,
    'handlers': {{'console': {{'class': 'logging.StreamHandler'}}}},
    'loggers': {{
        'django.db.backends': {{'handlers': ['console'], 'level': 'DEBUG'}},
    }},
}}
```

### 3. Profile with pyinstrument
```python
from pyinstrument import Profiler

profiler = Profiler()
profiler.start()
# ... your code ...
profiler.stop()
print(profiler.output_text(unicode=True, color=True))
```

## Issues to Investigate

'''

    critical = [i for i in issues if i.severity == "critical"]
    warnings = [i for i in issues if i.severity == "warning"]

    if critical:
        runbook += "### Critical (Fix First)\n\n"
        for issue in critical:
            runbook += f"- **{issue.file}:{issue.line}** - {issue.message}\n"
            runbook += f"  - Code: `{issue.code[:80]}...`\n"
            runbook += f"  - Fix: {issue.fix}\n\n"

    if warnings:
        runbook += "### Warnings\n\n"
        for issue in warnings:
            runbook += f"- **{issue.file}:{issue.line}** - {issue.message}\n"
            runbook += f"  - Fix: {issue.fix}\n\n"

    runbook += '''## Metrics to Capture

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Query count per request | < 10 | Django Debug Toolbar |
| p95 latency | < 200ms | Application metrics |
| Memory per request | < 50MB | py-spy / memory_profiler |
| N+1 queries | 0 | assertNumQueries in tests |

## Query Count Test Template

```python
from django.test.utils import CaptureQueriesContext
from django.db import connection

def test_view_query_count(client):
    with CaptureQueriesContext(connection) as ctx:
        response = client.get('/api/endpoint/')

    assert len(ctx) <= 5, f"Too many queries: {len(ctx)}"
```

## Common Fixes

### N+1 Queries
```python
# Before (N+1)
for obj in Model.objects.all():
    print(obj.related_fk.name)  # Query per iteration

# After (2 queries)
for obj in Model.objects.select_related('related_fk'):
    print(obj.related_fk.name)
```

### Bulk Operations
```python
# Before (N inserts)
for item in items:
    Model.objects.create(**item)

# After (1 insert)
Model.objects.bulk_create([Model(**item) for item in items])
```

### Set Lookups
```python
# Before (O(n*m))
for x in large_list:
    if x in another_list:  # O(m) each time
        ...

# After (O(n))
lookup_set = set(another_list)  # O(m) once
for x in large_list:
    if x in lookup_set:  # O(1) each time
        ...
```
'''

    return runbook


def audit_package(pkg_dir: Path, pkg_name: str) -> PackageAudit:
    """Run performance audit on a package."""
    audit = PackageAudit(package=pkg_name)
    src_dir = pkg_dir / "src" / pkg_name.replace("-", "_")

    if not src_dir.exists():
        return audit

    # Analyze all Python files
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        # AST analysis
        issues, hot_paths = analyze_file(py_file)
        audit.issues.extend(issues)
        audit.hot_paths.extend(hot_paths)

        # Pattern-based analysis
        prefetch_issues = analyze_for_missing_prefetch(py_file)
        audit.issues.extend(prefetch_issues)

    return audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Performance audit for Django packages")
    ap.add_argument("--root", default=".", help="Repository root")
    ap.add_argument("--package", action="append", dest="packages", default=[],
                    help="Specific package(s) to audit")
    ap.add_argument("--json", default=None, help="Output JSON report")
    ap.add_argument("--generate-tests", action="store_true",
                    help="Generate query count test templates")
    ap.add_argument("--generate-runbook", action="store_true",
                    help="Generate profiling runbooks")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    packages_dir = root / "packages"

    if not packages_dir.exists():
        print(f"ERROR: packages/ directory not found at {packages_dir}")
        return 1

    # Find packages to audit
    if args.packages:
        pkg_dirs = [packages_dir / p for p in args.packages if (packages_dir / p).exists()]
    else:
        pkg_dirs = sorted(p for p in packages_dir.iterdir() if p.is_dir() and p.name.startswith("django-"))

    print("=" * 70)
    print("PERFORMANCE AUDIT")
    print(f"Root: {root}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)

    results: dict[str, PackageAudit] = {}
    total_critical = 0
    total_warning = 0

    for pkg_dir in pkg_dirs:
        pkg_name = pkg_dir.name
        audit = audit_package(pkg_dir, pkg_name)
        results[pkg_name] = audit

        total_critical += audit.critical_count
        total_warning += audit.warning_count

        # Print results
        status = "PASS" if audit.critical_count == 0 else "FAIL"
        icon = "\u2705" if status == "PASS" else "\u274c"

        print(f"\n{icon} {pkg_name}: {status}")
        print(f"   Critical: {audit.critical_count}, Warnings: {audit.warning_count}")
        print(f"   Hot paths: {len(audit.hot_paths)}")

        if audit.critical_count > 0:
            print("   Critical issues:")
            for issue in audit.issues:
                if issue.severity == "critical":
                    print(f"     - {issue.file}:{issue.line}: {issue.message}")

        # Generate tests if requested
        if args.generate_tests and audit.hot_paths:
            test_file = pkg_dir / "tests" / "test_query_counts.py"
            test_content = generate_query_count_test(pkg_name, audit.hot_paths)
            print(f"   Generated: {test_file}")
            test_file.parent.mkdir(exist_ok=True)
            test_file.write_text(test_content)

        # Generate runbook if requested
        if args.generate_runbook and audit.issues:
            runbook_file = pkg_dir / "PERFORMANCE.md"
            runbook_content = generate_profiling_runbook(pkg_name, audit.issues)
            print(f"   Generated: {runbook_file}")
            runbook_file.write_text(runbook_content)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Packages audited: {len(results)}")
    print(f"Total critical issues: {total_critical}")
    print(f"Total warnings: {total_warning}")
    print(f"Total hot paths identified: {sum(len(a.hot_paths) for a in results.values())}")

    # JSON output
    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)

        output = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "packages": len(results),
                "critical": total_critical,
                "warnings": total_warning,
            },
            "packages": {
                name: {
                    "critical": audit.critical_count,
                    "warnings": audit.warning_count,
                    "hot_paths": audit.hot_paths,
                    "issues": [
                        {
                            "category": i.category,
                            "severity": i.severity,
                            "file": i.file,
                            "line": i.line,
                            "message": i.message,
                            "fix": i.fix,
                        }
                        for i in audit.issues
                    ]
                }
                for name, audit in results.items()
            }
        }

        json_path.write_text(json.dumps(output, indent=2))
        print(f"\nJSON report: {json_path}")

    return 1 if total_critical > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
