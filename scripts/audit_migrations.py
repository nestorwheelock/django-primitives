#!/usr/bin/env python3
"""
Audit migrations across the monorepo.

Checks:
- AutoField/BigAutoField in domain packages (should be UUIDField)
- Migration dependency graph consistency
- Testapp migrations in wrong locations
- GenericForeignKey object_id field types

Usage:
  python scripts/audit_migrations.py --root .
  python scripts/audit_migrations.py --root . --json out/migrations.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

# Package classification
DOMAIN_PACKAGES = {
    "django-parties",
    "django-rbac",
    "django-catalog",
    "django-encounters",
    "django-worklog",
    "django-ledger",
    "django-geo",
    "django-documents",
    "django-notes",
    "django-agreements",
    "django-modules",
    "django-money",
    "django-sequence",
}

SYSTEM_PACKAGES = {
    "django-audit-log",
    "django-decisioning",
}

UTILITY_PACKAGES = {
    "django-basemodels",
    "django-singleton",
    "django-layers",
}


@dataclass
class MigrationFinding:
    package: str
    migration: str
    issue: str
    severity: str
    detail: str
    line: Optional[int] = None


@dataclass
class PackageMigrations:
    name: str
    kind: str
    migrations: list[str]
    findings: list[MigrationFinding] = field(default_factory=list)


def get_package_kind(pkg_name: str) -> str:
    """Determine package classification."""
    if pkg_name in DOMAIN_PACKAGES:
        return "domain"
    elif pkg_name in SYSTEM_PACKAGES:
        return "system"
    elif pkg_name in UTILITY_PACKAGES:
        return "utility"
    return "unknown"


def find_migrations(pkg_path: Path) -> list[Path]:
    """Find all migration files in a package."""
    migrations = []
    pkg_name = pkg_path.name.replace("-", "_")

    # Check src/<pkg>/migrations/
    src_migrations = pkg_path / "src" / pkg_name / "migrations"
    if src_migrations.exists():
        migrations.extend(src_migrations.glob("*.py"))

    return [m for m in migrations if m.name != "__init__.py"]


def audit_migration_file(migration_path: Path, pkg_name: str, pkg_kind: str) -> list[MigrationFinding]:
    """Audit a single migration file."""
    findings = []
    content = migration_path.read_text()
    migration_name = migration_path.name

    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        # Check for AutoField/BigAutoField in domain packages
        if pkg_kind == "domain":
            if "AutoField(" in line or "BigAutoField(" in line:
                # Check if it's for an 'id' field
                if '"id"' in line or "'id'" in line or 'name="id"' in line:
                    findings.append(MigrationFinding(
                        package=pkg_name,
                        migration=migration_name,
                        issue="autofield_id",
                        severity="error",
                        detail="Domain package should use UUIDField for id, not AutoField/BigAutoField",
                        line=i
                    ))

        # Check for PositiveIntegerField on object_id (GenericFK)
        if "PositiveIntegerField" in line:
            if "object_id" in line or "_id" in line:
                # This might be a GenericFK object_id
                findings.append(MigrationFinding(
                    package=pkg_name,
                    migration=migration_name,
                    issue="generic_fk_int",
                    severity="warning",
                    detail="GenericForeignKey object_id should be CharField for UUID support",
                    line=i
                ))

    # Check for testapp in production migrations
    if "testapp" in content.lower() and "tests/" not in str(migration_path):
        findings.append(MigrationFinding(
            package=pkg_name,
            migration=migration_name,
            issue="testapp_reference",
            severity="error",
            detail="Production migration references testapp"
        ))

    # Check migration dependencies
    dep_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if dep_match:
        deps_str = dep_match.group(1)
        # Look for broken app labels
        app_refs = re.findall(r'\("([^"]+)"', deps_str)
        for app_ref in app_refs:
            # Check for common typos or inconsistencies
            if app_ref.startswith("django_") and app_ref not in [
                "django_catalog", "django_encounters", "django_parties",
                "django_rbac", "django_modules", "django_worklog",
                "django_ledger", "django_geo", "django_documents",
                "django_notes", "django_agreements", "django_money",
                "django_sequence", "django_audit_log", "django_decisioning",
                "django_singleton", "django_basemodels"
            ]:
                if app_ref not in ["django_content_type", "django_contenttypes"]:
                    findings.append(MigrationFinding(
                        package=pkg_name,
                        migration=migration_name,
                        issue="unknown_app_dependency",
                        severity="warning",
                        detail=f"Unknown app label in dependencies: {app_ref}"
                    ))

    return findings


def audit_package(pkg_path: Path) -> PackageMigrations:
    """Audit all migrations in a package."""
    pkg_name = pkg_path.name
    pkg_kind = get_package_kind(pkg_name)

    migrations = find_migrations(pkg_path)
    migration_names = [m.name for m in sorted(migrations)]

    findings = []
    for migration in migrations:
        findings.extend(audit_migration_file(migration, pkg_name, pkg_kind))

    return PackageMigrations(
        name=pkg_name,
        kind=pkg_kind,
        migrations=migration_names,
        findings=findings
    )


def iter_packages(root: Path) -> list[Path]:
    """Find all django-* packages."""
    packages_dir = root / "packages"
    if not packages_dir.exists():
        return []
    return sorted([p for p in packages_dir.iterdir() if p.is_dir() and p.name.startswith("django-")])


def print_table(packages: dict[str, PackageMigrations]) -> None:
    """Print summary table."""
    print(f"\n{'Package':<25} {'Kind':<10} {'Migrations':>10} {'Findings':>10}")
    print("-" * 60)

    for pkg in sorted(packages.values(), key=lambda p: p.name):
        findings_count = len(pkg.findings)
        status = "✅" if findings_count == 0 else f"❌ {findings_count}"
        print(f"{pkg.name:<25} {pkg.kind:<10} {len(pkg.migrations):>10} {status:>10}")

    total_findings = sum(len(p.findings) for p in packages.values())
    if total_findings == 0:
        print(f"\n✅ Migration audit clean.")
    else:
        print(f"\n❌ {total_findings} migration issues found:")
        for pkg in packages.values():
            for f in pkg.findings:
                loc = f":{f.line}" if f.line else ""
                print(f"   [{f.severity}] {f.package}/{f.migration}{loc}: {f.issue}")
                print(f"            {f.detail}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit migrations")
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--json", default=None, help="Write JSON report to path")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    pkg_paths = iter_packages(root)

    packages = {}
    for pkg_path in pkg_paths:
        pkg_migrations = audit_package(pkg_path)
        packages[pkg_migrations.name] = pkg_migrations

    print_table(packages)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "packages": {k: asdict(v) for k, v in packages.items()},
            "total_findings": sum(len(p.findings) for p in packages.values()),
        }
        out_path.write_text(json.dumps(payload, indent=2))
        print(f"\nWrote JSON report to {out_path}")

    total_errors = sum(1 for p in packages.values() for f in p.findings if f.severity == "error")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
