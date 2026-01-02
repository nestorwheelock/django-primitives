#!/usr/bin/env python3
"""
Audit Django model conventions across a monorepo.

What it checks (default):
- Domain models should inherit from BaseModel (or whatever you configure)
- Flags classes inheriting directly from models.Model
- Flags manual id fields (AutoField/BigAutoField/UUIDField)
- Flags manual created_at/updated_at fields
- Flags use of UUIDModel (if you're trying to kill that pattern)

What it treats as "domain models" (by default):
- Any class defined in a file named models.py under packages/*/src/**
- That inherits from Model/BaseModel OR defines Django Field assignments
- Excludes QuerySet, Manager, Form, Serializer, ModelAdmin classes

Package classification (module-level markers):
- # PRIMITIVES: package-kind=domain    (default, BaseModel required)
- # PRIMITIVES: package-kind=system    (immutable forensic data, different rules)
- # PRIMITIVES: package-kind=utility   (no model rules enforced)

Escape hatch (class-level markers):
- # PRIMITIVES: allow-plain-model
- # PRIMITIVES: allow-manual-timestamps
- # PRIMITIVES: allow-manual-id
- # PRIMITIVES: allow-uuidmodel

Usage:
  python scripts/audit_models.py --root .
  python scripts/audit_models.py --root . --json scripts/audit-report.json
  python scripts/audit_models.py --root . --skip-package django-basemodels

Exit codes:
  0 = clean
  1 = violations found
  2 = script error
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

# Class-level escape hatches
ALLOW_PLAIN = "PRIMITIVES: allow-plain-model"
ALLOW_TS = "PRIMITIVES: allow-manual-timestamps"
ALLOW_ID = "PRIMITIVES: allow-manual-id"
ALLOW_UUIDMODEL = "PRIMITIVES: allow-uuidmodel"

# Package classification marker
PACKAGE_KIND_PATTERN = re.compile(r"PRIMITIVES:\s*package-kind\s*=\s*(\w+)")

# Default rules
DEFAULT_REQUIRED_BASE = {"BaseModel"}
DEFAULT_FORBIDDEN_BASES = {"UUIDModel"}

# Non-model base classes to skip (Filter B)
NON_MODEL_BASES = {
    "QuerySet",
    "Manager",
    "BaseManager",
    "SoftDeleteManager",
    "ModelAdmin",
    "Form",
    "ModelForm",
    "Serializer",
    "ModelSerializer",
    "APIView",
    "ViewSet",
    "TestCase",
}

# Django field types (for Filter A detection)
DJANGO_FIELD_TYPES = {
    "Field",
    "CharField",
    "TextField",
    "IntegerField",
    "BigIntegerField",
    "SmallIntegerField",
    "PositiveIntegerField",
    "PositiveSmallIntegerField",
    "FloatField",
    "DecimalField",
    "BooleanField",
    "NullBooleanField",
    "DateField",
    "DateTimeField",
    "TimeField",
    "DurationField",
    "EmailField",
    "URLField",
    "UUIDField",
    "SlugField",
    "IPAddressField",
    "GenericIPAddressField",
    "FileField",
    "ImageField",
    "FilePathField",
    "BinaryField",
    "JSONField",
    "ForeignKey",
    "OneToOneField",
    "ManyToManyField",
    "GenericForeignKey",
    "AutoField",
    "BigAutoField",
    "SmallAutoField",
}

MANUAL_ID_TYPES = {"AutoField", "BigAutoField", "UUIDField"}
MANUAL_TS_NAMES = {"created_at", "updated_at"}


@dataclass
class Finding:
    file: str
    class_name: str
    lineno: int
    issue: str
    detail: str


def _extract_package_name(path: Path) -> Optional[str]:
    """Extract package name from path like packages/django-foo/src/..."""
    m = re.search(r"packages/([^/]+)/", str(path).replace("\\", "/"))
    return m.group(1) if m else None


def iter_models_files(root: Path, skip_packages: set[str]) -> Iterable[Path]:
    """Iterate over models.py files, skipping specified packages."""
    for p in root.glob("packages/*/src/**/models.py"):
        if p.is_file():
            pkg_name = _extract_package_name(p)
            if pkg_name and pkg_name in skip_packages:
                continue
            yield p


def _base_name(node: ast.expr) -> Optional[str]:
    """Extract base class name from AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return None


def _call_func_name(node: ast.AST) -> Optional[str]:
    """Extract function name from a Call node."""
    if isinstance(node, ast.Call):
        return _base_name(node.func)
    return None


def _get_package_kind(src: str) -> str:
    """
    Extract package-kind from module-level comments.

    Returns: 'domain', 'system', or 'utility'
    Default: 'domain'
    """
    for line in src.split("\n")[:50]:  # Check first 50 lines
        m = PACKAGE_KIND_PATTERN.search(line)
        if m:
            return m.group(1).lower()
    return "domain"


def _has_allow_marker(lines: list[str], lineno: int, marker: str) -> bool:
    """Check if marker exists on same line or up to 2 lines above."""
    idx = max(0, lineno - 1)
    for j in (idx, idx - 1, idx - 2):
        if 0 <= j < len(lines) and marker in lines[j]:
            return True
    return False


def _is_model_class(node: ast.ClassDef, base_names: set[str]) -> bool:
    """
    Determine if a class is a Django model (worth auditing).

    Filter A: Has model-ish base OR defines Django field assignments.
    Filter B: Not a QuerySet/Manager/Form/etc.
    """
    # Filter B: Exclude known non-model classes
    if base_names & NON_MODEL_BASES:
        return False

    # Filter A, part 1: Inherits from Model or BaseModel
    model_bases = {"Model", "BaseModel", "TimeStampedModel", "SoftDeleteModel", "UUIDModel"}
    if base_names & model_bases:
        return True

    # Filter A, part 2: Has Django field assignments in body
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            if isinstance(stmt.targets[0], ast.Name):
                call_name = _call_func_name(stmt.value)
                if call_name and call_name in DJANGO_FIELD_TYPES:
                    return True

    # Also check for classes that inherit from other local base models
    # (e.g., CatalogBaseModel, EncountersBaseModel)
    for base in base_names:
        if base and ("Model" in base or "Base" in base):
            return True

    return False


def audit_file(
    path: Path,
    required_bases: set[str],
    forbidden_bases: set[str],
) -> list[Finding]:
    """Audit a single models.py file."""
    findings: list[Finding] = []
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()

    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        findings.append(Finding(
            str(path), "<parse>", getattr(e, "lineno", 0) or 0,
            "syntax_error", str(e)
        ))
        return findings

    # Check package kind
    package_kind = _get_package_kind(src)

    # Skip auditing utility packages entirely
    if package_kind == "utility":
        return findings

    # System packages have different rules (TODO: implement system rules)
    # For now, we skip them too - they need explicit design
    if package_kind == "system":
        return findings

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        class_name = node.name
        lineno = node.lineno

        base_names = {_base_name(b) for b in node.bases}
        base_names.discard(None)

        # Skip non-model classes (QuerySet, Manager, Form, etc.)
        if not _is_model_class(node, base_names):
            continue

        # --- Base inheritance checks (domain models only) ---

        # Flag plain models.Model inheritance
        if "Model" in base_names:
            if not _has_allow_marker(lines, lineno, ALLOW_PLAIN):
                findings.append(Finding(
                    str(path), class_name, lineno,
                    "inherits_models_model",
                    "Class inherits from models.Model. Domain models should inherit BaseModel.",
                ))

        # Require BaseModel (or configured required base)
        # Also accept classes that end with "BaseModel" (e.g., CatalogBaseModel)
        # These are local aliases that extend django_basemodels.BaseModel
        has_required_base = bool(base_names & required_bases)
        if not has_required_base:
            has_required_base = any(
                b and b.endswith("BaseModel") for b in base_names
            )
        if required_bases and not has_required_base:
            if not _has_allow_marker(lines, lineno, ALLOW_PLAIN):
                findings.append(Finding(
                    str(path), class_name, lineno,
                    "missing_required_base",
                    f"Expected one of {sorted(required_bases)} in bases, got {sorted(base_names)}.",
                ))

        # Forbidden bases like UUIDModel
        forbidden_hit = base_names & forbidden_bases
        if forbidden_hit and not _has_allow_marker(lines, lineno, ALLOW_UUIDMODEL):
            findings.append(Finding(
                str(path), class_name, lineno,
                "uses_forbidden_base",
                f"Uses forbidden base(s): {sorted(forbidden_hit)}.",
            ))

        # --- Field-level checks (manual id / timestamps) ---
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                if isinstance(stmt.targets[0], ast.Name):
                    attr = stmt.targets[0].id
                    call_name = _call_func_name(stmt.value)

                    if attr == "id" and call_name in MANUAL_ID_TYPES:
                        if not _has_allow_marker(lines, stmt.lineno, ALLOW_ID):
                            findings.append(Finding(
                                str(path), class_name, stmt.lineno,
                                "manual_id_field",
                                f"Manual id field declared ({call_name}). BaseModel should own PK.",
                            ))

                    if attr in MANUAL_TS_NAMES and call_name == "DateTimeField":
                        if not _has_allow_marker(lines, stmt.lineno, ALLOW_TS):
                            findings.append(Finding(
                                str(path), class_name, stmt.lineno,
                                "manual_timestamp_field",
                                f"Manual {attr} field declared. BaseModel should provide timestamps.",
                            ))

    return findings


def print_table(findings: list[Finding], skipped_packages: set[str]) -> None:
    """Print findings as a formatted table."""
    if skipped_packages:
        print(f"\nSkipped packages: {', '.join(sorted(skipped_packages))}")

    if not findings:
        print("\n✅ Model audit clean. Humans briefly approximated discipline.")
        return

    def pkg_of(f: Finding) -> str:
        m = re.search(r"packages/([^/]+)/", f.file.replace("\\", "/"))
        return m.group(1) if m else "(unknown)"

    findings_sorted = sorted(findings, key=lambda f: (pkg_of(f), f.file, f.lineno, f.class_name))

    print(f"\n❌ Model audit violations found: {len(findings)}\n")
    print(f"{'Package':20} {'File':50} {'Line':>5} {'Class':25} {'Issue':28} Detail")
    print("-" * 140)

    for f in findings_sorted:
        file_short = f.file.replace("\\", "/")
        if len(file_short) > 50:
            file_short = "…" + file_short[-49:]
        print(
            f"{pkg_of(f):20} {file_short:50} {f.lineno:5d} {f.class_name:25} {f.issue:28} {f.detail}"
        )

    print("\nFix them or add an explicit allow-marker (and accept eternal shame).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit Django model conventions")
    ap.add_argument("--root", default=".", help="Repo root (default: .)")
    ap.add_argument(
        "--required-base", action="append", default=[],
        help="Required base class name (repeatable). Default: BaseModel",
    )
    ap.add_argument(
        "--forbidden-base", action="append", default=[],
        help="Forbidden base class name (repeatable). Default: UUIDModel",
    )
    ap.add_argument(
        "--skip-package", action="append", default=[],
        help="Package name to skip (repeatable). E.g., --skip-package django-basemodels",
    )
    ap.add_argument("--json", default=None, help="Write JSON report to path")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    required_bases = set(args.required_base) if args.required_base else set(DEFAULT_REQUIRED_BASE)
    forbidden_bases = set(args.forbidden_base) if args.forbidden_base else set(DEFAULT_FORBIDDEN_BASES)
    skip_packages = set(args.skip_package)

    all_findings: list[Finding] = []
    for path in iter_models_files(root, skip_packages):
        all_findings.extend(audit_file(path, required_bases, forbidden_bases))

    print_table(all_findings, skip_packages)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "required_bases": sorted(required_bases),
            "forbidden_bases": sorted(forbidden_bases),
            "skipped_packages": sorted(skip_packages),
            "violations": [asdict(f) for f in all_findings],
            "count": len(all_findings),
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote JSON report to {out_path}")

    return 0 if not all_findings else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"Audit failed with error: {e}", file=sys.stderr)
        raise SystemExit(2)
