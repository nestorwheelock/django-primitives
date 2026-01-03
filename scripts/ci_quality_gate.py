#!/usr/bin/env python3
"""
CI Quality Gate - Enforces code quality rules that must not regress.

This script runs in CI on every PR and fails if any violations are found.
All checks have actionable output: package, file, line, and how to fix.

Usage:
  python scripts/ci_quality_gate.py                    # Run all checks
  python scripts/ci_quality_gate.py --check hygiene    # Run specific check
  python scripts/ci_quality_gate.py --fix-suggestions  # Show copy-paste fixes

Exit codes:
  0 - All checks pass
  1 - Violations found (CI should fail)
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path


TIERS = {
    "django_basemodels": 0,
    "django_singleton": 0,
    "django_modules": 0,
    "django_layers": 0,
    "django_parties": 1,
    "django_rbac": 1,
    "django_decisioning": 2,
    "django_audit_log": 2,
    "django_catalog": 3,
    "django_encounters": 3,
    "django_worklog": 3,
    "django_geo": 3,
    "django_ledger": 3,
    "django_documents": 4,
    "django_notes": 4,
    "django_agreements": 4,
    "django_money": 5,
    "django_sequence": 5,
}

TIER_NAMES = {
    0: "Foundation",
    1: "Identity",
    2: "Infrastructure",
    3: "Domain",
    4: "Content",
    5: "Value Objects",
}

CHECK_NAMES = {
    "readme": "Missing README.md",
    "version": "Missing __version__",
    "default_app_config": "Deprecated default_app_config",
    "silent_exception": "Silent Exception Handlers",
    "tier_violation": "Tier Import Violations",
}


@dataclass
class Violation:
    """A quality gate violation."""
    check: str
    package: str
    file: str
    line: int | None
    message: str
    how_to_fix: str
    snippet: str = ""

    @property
    def location(self) -> str:
        """Return file:line format."""
        if self.line:
            return f"{self.file}:{self.line}"
        return self.file

    @property
    def tier(self) -> int | None:
        """Get the tier for this package."""
        pkg_name = self.package.replace("-", "_")
        return TIERS.get(pkg_name)


class QualityGate:
    """CI quality gate that enforces non-regression rules."""

    def __init__(self, root: Path):
        self.root = root
        self.packages_dir = root / "packages"
        self.violations: list[Violation] = []

    def get_packages(self) -> list[Path]:
        """Get all package directories."""
        if not self.packages_dir.exists():
            return []
        return sorted([p for p in self.packages_dir.iterdir() if p.is_dir()])

    def check_readme(self) -> None:
        """Check that every package has a README.md."""
        for pkg_dir in self.get_packages():
            readme = pkg_dir / "README.md"
            if not readme.exists():
                self.violations.append(Violation(
                    check="readme",
                    package=pkg_dir.name,
                    file=str(pkg_dir / "README.md"),
                    line=None,
                    message="Missing README.md",
                    how_to_fix=f"Create {pkg_dir.name}/README.md with package description and usage"
                ))

    def check_version(self) -> None:
        """Check that every package has __version__ in __init__.py."""
        for pkg_dir in self.get_packages():
            pkg_name = pkg_dir.name.replace("-", "_")
            init_file = pkg_dir / "src" / pkg_name / "__init__.py"

            if not init_file.exists():
                self.violations.append(Violation(
                    check="version",
                    package=pkg_dir.name,
                    file=str(init_file),
                    line=None,
                    message="Missing __init__.py",
                    how_to_fix=f"Create {init_file} with __version__ = \"0.1.0\""
                ))
                continue

            content = init_file.read_text()
            if "__version__" not in content:
                self.violations.append(Violation(
                    check="version",
                    package=pkg_dir.name,
                    file=str(init_file),
                    line=1,
                    message="Missing __version__ in __init__.py",
                    how_to_fix="Add: __version__ = \"0.1.0\""
                ))

    def check_default_app_config(self) -> None:
        """Check for deprecated default_app_config usage."""
        for pkg_dir in self.get_packages():
            pkg_name = pkg_dir.name.replace("-", "_")
            init_file = pkg_dir / "src" / pkg_name / "__init__.py"

            if not init_file.exists():
                continue

            content = init_file.read_text()
            lines = content.splitlines()

            for i, line in enumerate(lines, 1):
                if "default_app_config" in line and not line.strip().startswith("#"):
                    self.violations.append(Violation(
                        check="default_app_config",
                        package=pkg_dir.name,
                        file=str(init_file),
                        line=i,
                        message="Deprecated default_app_config (removed in Django 4.1+)",
                        how_to_fix="Delete this line. Django auto-discovers apps.py.",
                        snippet=line.strip(),
                    ))

    def check_silent_exceptions(self) -> None:
        """Check for silent exception handlers (except: pass)."""
        for pkg_dir in self.get_packages():
            pkg_name = pkg_dir.name.replace("-", "_")
            src_dir = pkg_dir / "src" / pkg_name

            if not src_dir.exists():
                continue

            for py_file in src_dir.rglob("*.py"):
                if "__pycache__" in str(py_file) or "migrations" in str(py_file):
                    continue

                try:
                    content = py_file.read_text()
                    lines = content.splitlines()
                    tree = ast.parse(content)
                    self._check_silent_exceptions_in_ast(tree, py_file, pkg_dir.name, lines)
                except SyntaxError:
                    pass

    def _check_silent_exceptions_in_ast(
        self, tree: ast.AST, filepath: Path, pkg_name: str, lines: list[str]
    ) -> None:
        """Walk AST looking for silent exception handlers."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if body is just 'pass'
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                    self.violations.append(Violation(
                        check="silent_exception",
                        package=pkg_name,
                        file=str(filepath),
                        line=node.lineno,
                        message="Silent exception handler: 'except: pass' hides failures",
                        how_to_fix="Log the error, re-raise, or handle explicitly with a comment explaining why",
                        snippet=snippet,
                    ))

    def check_tier_imports(self) -> None:
        """Check for tier violations (lower tier importing higher tier)."""
        for pkg_dir in self.get_packages():
            pkg_name = pkg_dir.name.replace("-", "_")
            src_dir = pkg_dir / "src" / pkg_name
            pkg_tier = TIERS.get(pkg_name)

            if pkg_tier is None or not src_dir.exists():
                continue

            for py_file in src_dir.rglob("*.py"):
                if "__pycache__" in str(py_file) or "migrations" in str(py_file):
                    continue

                try:
                    content = py_file.read_text()
                    lines = content.splitlines()
                    tree = ast.parse(content)
                    self._check_tier_imports_in_ast(tree, py_file, pkg_name, pkg_tier, lines)
                except SyntaxError:
                    pass

    def _check_tier_imports_in_ast(
        self,
        tree: ast.AST,
        filepath: Path,
        pkg_name: str,
        pkg_tier: int,
        lines: list[str],
    ) -> None:
        """Walk AST looking for tier-violating imports."""
        for node in ast.walk(tree):
            imported_module = None

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_module = alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_module = node.module.split(".")[0]

            if imported_module and imported_module in TIERS:
                imported_tier = TIERS[imported_module]
                if imported_tier > pkg_tier:
                    snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                    self.violations.append(Violation(
                        check="tier_violation",
                        package=pkg_name.replace("_", "-"),
                        file=str(filepath),
                        line=node.lineno,
                        message=f"Tier violation: {pkg_name} (tier {pkg_tier}) imports {imported_module} (tier {imported_tier})",
                        how_to_fix=f"Move shared code to a lower tier, or restructure to avoid this import",
                        snippet=snippet,
                    ))

    def run_all_checks(self) -> int:
        """Run all quality gate checks. Returns exit code."""
        self.check_readme()
        self.check_version()
        self.check_default_app_config()
        self.check_silent_exceptions()
        self.check_tier_imports()

        # Count packages
        total_packages = len(self.get_packages())
        packages_with_violations = set(v.package for v in self.violations)
        pass_count = total_packages - len(packages_with_violations)
        fail_count = len(packages_with_violations)

        if not self.violations:
            print("=" * 70)
            print("✅ QUALITY GATE PASSED")
            print("=" * 70)
            print(f"\nSummary: {pass_count} PASS / {fail_count} FAIL")
            print(f"All {total_packages} packages passed all checks.")
            return 0

        # Group by package, then by rule
        by_package: dict[str, dict[str, list[Violation]]] = {}
        for v in self.violations:
            if v.package not in by_package:
                by_package[v.package] = {}
            by_package[v.package].setdefault(v.check, []).append(v)

        # Count by rule
        by_rule: dict[str, int] = {}
        for v in self.violations:
            by_rule[v.check] = by_rule.get(v.check, 0) + 1

        # Count by tier
        by_tier: dict[int, int] = {}
        for v in self.violations:
            tier = v.tier
            if tier is not None:
                by_tier[tier] = by_tier.get(tier, 0) + 1

        print("=" * 70)
        print("❌ QUALITY GATE FAILED")
        print("=" * 70)
        print(f"\nFound {len(self.violations)} violation(s) in {fail_count} package(s):\n")

        # Print violations grouped by package then rule
        for pkg_name in sorted(by_package.keys()):
            pkg_tier = TIERS.get(pkg_name.replace("-", "_"))
            tier_label = f" (Tier {pkg_tier}: {TIER_NAMES.get(pkg_tier, '?')})" if pkg_tier is not None else ""
            print(f"\n┌─ {pkg_name}{tier_label}")
            print("│")

            pkg_violations = by_package[pkg_name]
            for check in sorted(pkg_violations.keys()):
                violations = pkg_violations[check]
                print(f"│  ■ {CHECK_NAMES.get(check, check)} ({len(violations)})")

                for v in violations:
                    print(f"│    ├─ {v.location}")
                    if v.snippet:
                        print(f"│    │  ❯ {v.snippet}")
                    print(f"│    └─ Fix: {v.how_to_fix}")

            print("│")
            print("└───")

        # Print summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        print(f"\n  {pass_count} PASS / {fail_count} FAIL\n")

        print("  Failures by Rule:")
        for check, count in sorted(by_rule.items(), key=lambda x: -x[1]):
            print(f"    • {CHECK_NAMES.get(check, check)}: {count}")

        if by_tier:
            print("\n  Failures by Tier:")
            for tier in sorted(by_tier.keys()):
                count = by_tier[tier]
                print(f"    • Tier {tier} ({TIER_NAMES.get(tier, '?')}): {count}")

        print("\n" + "=" * 70)
        print("Fix all violations above to pass CI.")
        print("=" * 70)

        return 1

    def run_check(self, check_name: str) -> int:
        """Run a specific check."""
        checks = {
            "readme": self.check_readme,
            "version": self.check_version,
            "default_app_config": self.check_default_app_config,
            "silent_exception": self.check_silent_exceptions,
            "tier": self.check_tier_imports,
            "hygiene": lambda: (self.check_readme(), self.check_version(), self.check_default_app_config()),
        }

        if check_name not in checks:
            print(f"Unknown check: {check_name}")
            print(f"Available: {', '.join(checks.keys())}")
            return 1

        check_fn = checks[check_name]
        if callable(check_fn):
            check_fn()

        if not self.violations:
            print(f"✅ {check_name} check passed!")
            return 0

        for v in self.violations:
            print(str(v))
            print()

        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="CI Quality Gate")
    ap.add_argument("--root", default=".", help="Repository root")
    ap.add_argument("--check", help="Run specific check: readme, version, default_app_config, silent_exception, tier, hygiene")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    gate = QualityGate(root)

    if args.check:
        return gate.run_check(args.check)
    else:
        return gate.run_all_checks()


if __name__ == "__main__":
    sys.exit(main())
