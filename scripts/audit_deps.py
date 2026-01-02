#!/usr/bin/env python3
"""
Audit package dependencies across the monorepo.

Checks:
- Circular dependencies between packages
- Version floor requirements (django-basemodels>=0.2.0)
- Tier violations (lower tier importing higher tier)
- Version consistency (__version__ vs pyproject.toml)

Usage:
  python scripts/audit_deps.py --root .
  python scripts/audit_deps.py --root . --json out/deps.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

# Package tier classification
TIER_MAP = {
    # Tier 0 - Foundation
    "django-basemodels": 0,
    "django-singleton": 0,
    "django-layers": 0,
    "django-modules": 0,
    # Tier 1 - Identity + Infrastructure
    "django-parties": 1,
    "django-rbac": 1,
    "django-decisioning": 1,
    "django-audit-log": 1,
    # Tier 2 - Domain
    "django-catalog": 2,
    "django-encounters": 2,
    "django-worklog": 2,
    "django-ledger": 2,
    "django-geo": 2,
    # Tier 3 - Content
    "django-documents": 3,
    "django-notes": 3,
    "django-agreements": 3,
    # Tier 4 - Value Objects
    "django-money": 4,
    "django-sequence": 4,
}

# Required version floors for key dependencies
REQUIRED_FLOORS = {
    "django-basemodels": "0.2.0",
}


@dataclass
class DepFinding:
    package: str
    issue: str
    severity: str  # error, warning
    detail: str


@dataclass
class PackageDeps:
    name: str
    tier: int
    version_pyproject: str
    version_runtime: Optional[str]
    dependencies: list[str]
    internal_deps: list[str]
    findings: list[DepFinding] = field(default_factory=list)


def parse_version_spec(spec: str) -> tuple[str, Optional[str]]:
    """Parse 'package>=1.0.0' into ('package', '1.0.0')."""
    match = re.match(r"([a-zA-Z0-9_-]+)([><=!]+)?([\d.]+)?", spec)
    if match:
        name = match.group(1)
        version = match.group(3)
        return name, version
    return spec, None


def get_pyproject_info(pkg_path: Path) -> tuple[str, list[str]]:
    """Extract version and dependencies from pyproject.toml."""
    pyproject = pkg_path / "pyproject.toml"
    if not pyproject.exists():
        return "", []

    content = pyproject.read_text()

    # Extract version
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    version = version_match.group(1) if version_match else ""

    # Extract dependencies (simple regex, not full TOML parsing)
    deps = []
    in_deps = False
    for line in content.split("\n"):
        if line.strip() == "dependencies = [":
            in_deps = True
            continue
        if in_deps:
            if line.strip() == "]":
                break
            # Extract quoted dependency
            match = re.search(r'"([^"]+)"', line)
            if match:
                deps.append(match.group(1))

    return version, deps


def get_runtime_version(pkg_path: Path) -> Optional[str]:
    """Extract __version__ from package __init__.py."""
    pkg_name = pkg_path.name.replace("-", "_")
    init_file = pkg_path / "src" / pkg_name / "__init__.py"

    if not init_file.exists():
        return None

    content = init_file.read_text()
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    return match.group(1) if match else None


def find_internal_deps(deps: list[str], all_packages: set[str]) -> list[str]:
    """Find dependencies that are internal packages."""
    internal = []
    for dep in deps:
        name, _ = parse_version_spec(dep)
        if name in all_packages:
            internal.append(name)
    return internal


def detect_cycles(packages: dict[str, PackageDeps]) -> list[list[str]]:
    """Detect circular dependencies using DFS."""
    cycles = []
    visited = set()
    rec_stack = set()
    path = []

    def dfs(pkg: str):
        if pkg not in packages:
            return
        visited.add(pkg)
        rec_stack.add(pkg)
        path.append(pkg)

        for dep in packages[pkg].internal_deps:
            if dep not in visited:
                dfs(dep)
            elif dep in rec_stack:
                # Found cycle
                cycle_start = path.index(dep)
                cycles.append(path[cycle_start:] + [dep])

        path.pop()
        rec_stack.remove(pkg)

    for pkg in packages:
        if pkg not in visited:
            dfs(pkg)

    return cycles


def audit_package(pkg_path: Path, all_packages: set[str]) -> PackageDeps:
    """Audit a single package's dependencies."""
    pkg_name = pkg_path.name
    tier = TIER_MAP.get(pkg_name, 99)

    version_pyproject, deps = get_pyproject_info(pkg_path)
    version_runtime = get_runtime_version(pkg_path)
    internal_deps = find_internal_deps(deps, all_packages)

    findings = []

    # Check version consistency
    if version_pyproject and version_runtime:
        if version_pyproject != version_runtime:
            findings.append(DepFinding(
                package=pkg_name,
                issue="version_mismatch",
                severity="error",
                detail=f"pyproject.toml={version_pyproject}, __version__={version_runtime}"
            ))

    # Check required version floors
    for dep in deps:
        dep_name, dep_version = parse_version_spec(dep)
        if dep_name in REQUIRED_FLOORS:
            required = REQUIRED_FLOORS[dep_name]
            if dep_version is None:
                findings.append(DepFinding(
                    package=pkg_name,
                    issue="missing_version_floor",
                    severity="error",
                    detail=f"{dep_name} should have >={required}"
                ))
            elif dep_version < required:
                findings.append(DepFinding(
                    package=pkg_name,
                    issue="insufficient_version_floor",
                    severity="error",
                    detail=f"{dep_name}>={dep_version} should be >={required}"
                ))

    # Check tier violations
    for int_dep in internal_deps:
        dep_tier = TIER_MAP.get(int_dep, 99)
        if dep_tier > tier:
            findings.append(DepFinding(
                package=pkg_name,
                issue="tier_violation",
                severity="error",
                detail=f"Tier {tier} package imports Tier {dep_tier} package {int_dep}"
            ))

    return PackageDeps(
        name=pkg_name,
        tier=tier,
        version_pyproject=version_pyproject,
        version_runtime=version_runtime,
        dependencies=deps,
        internal_deps=internal_deps,
        findings=findings
    )


def iter_packages(root: Path) -> list[Path]:
    """Find all django-* packages."""
    packages_dir = root / "packages"
    if not packages_dir.exists():
        return []
    return sorted([p for p in packages_dir.iterdir() if p.is_dir() and p.name.startswith("django-")])


def print_table(packages: dict[str, PackageDeps], cycles: list[list[str]]) -> None:
    """Print summary table."""
    print(f"\n{'Package':<25} {'Tier':>4} {'Version':>10} {'Deps':>4} {'Findings':>8}")
    print("-" * 60)

    for pkg in sorted(packages.values(), key=lambda p: (p.tier, p.name)):
        findings_count = len(pkg.findings)
        status = "✅" if findings_count == 0 else f"❌ {findings_count}"
        print(f"{pkg.name:<25} {pkg.tier:>4} {pkg.version_pyproject:>10} {len(pkg.internal_deps):>4} {status:>8}")

    if cycles:
        print(f"\n❌ Circular dependencies detected: {len(cycles)}")
        for cycle in cycles:
            print(f"   {' -> '.join(cycle)}")
    else:
        print(f"\n✅ No circular dependencies")

    total_findings = sum(len(p.findings) for p in packages.values())
    if total_findings == 0:
        print(f"\n✅ Dependency audit clean.")
    else:
        print(f"\n❌ {total_findings} dependency issues found.")
        for pkg in packages.values():
            for f in pkg.findings:
                print(f"   [{f.severity}] {f.package}: {f.issue} - {f.detail}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit package dependencies")
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--json", default=None, help="Write JSON report to path")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    pkg_paths = iter_packages(root)

    all_packages = {p.name for p in pkg_paths}
    packages = {}

    for pkg_path in pkg_paths:
        pkg_deps = audit_package(pkg_path, all_packages)
        packages[pkg_deps.name] = pkg_deps

    cycles = detect_cycles(packages)

    # Add cycle findings
    for cycle in cycles:
        for pkg_name in cycle[:-1]:  # Skip last (duplicate)
            if pkg_name in packages:
                packages[pkg_name].findings.append(DepFinding(
                    package=pkg_name,
                    issue="circular_dependency",
                    severity="error",
                    detail=f"Cycle: {' -> '.join(cycle)}"
                ))

    print_table(packages, cycles)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "packages": {k: asdict(v) for k, v in packages.items()},
            "cycles": cycles,
            "total_findings": sum(len(p.findings) for p in packages.values()),
        }
        out_path.write_text(json.dumps(payload, indent=2))
        print(f"\nWrote JSON report to {out_path}")

    total_errors = sum(1 for p in packages.values() for f in p.findings if f.severity == "error")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
