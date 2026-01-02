# tests/test_architecture_contracts.py
"""
Architecture contract tests for django-primitives.

These tests enforce structural invariants that unit tests don't catch:
- Tier/layer violations (importing from higher tiers)
- Version consistency (__init__.py vs pyproject.toml)
- GenericForeignKey field types (CharField for UUID support)
- ForeignKey on_delete patterns
- Lazy imports in __init__.py (prevent AppRegistryNotReady)
- Test/doc file existence
- Circular import detection
- AUTH_USER_MODEL usage (not direct User imports)
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

# Package tier classification
TIER_MAP = {
    # Tier 0: Foundation
    "django-basemodels": 0,
    "django-singleton": 0,
    "django-layers": 0,
    "django-modules": 0,
    # Tier 1: Identity/Infrastructure
    "django-parties": 1,
    "django-rbac": 1,
    "django-decisioning": 1,
    "django-audit-log": 1,
    # Tier 2: Domain
    "django-catalog": 2,
    "django-encounters": 2,
    "django-worklog": 2,
    "django-geo": 2,
    "django-ledger": 2,
    # Tier 3: Content
    "django-documents": 3,
    "django-notes": 3,
    "django-agreements": 3,
    # Tier 4: Value Objects
    "django-money": 4,
    "django-sequence": 4,
}

PACKAGES_DIR = Path(__file__).parent.parent / "packages"


def get_package_dirs() -> List[Path]:
    """Get all django-* package directories."""
    return sorted([p for p in PACKAGES_DIR.iterdir() if p.is_dir() and p.name.startswith("django-")])


def module_path(module_name: str) -> Path:
    """Get the file path for a module."""
    spec = importlib.util.find_spec(module_name)
    if spec and spec.origin:
        return Path(spec.origin).resolve()
    raise ImportError(f"Cannot find module {module_name}")


def get_imports_from_file(path: Path) -> Set[str]:
    """Extract all import statements from a Python file."""
    if not path.exists():
        return set()

    try:
        source = path.read_text()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return imports


# -----------------------------
# 1) Tier violation detection
# -----------------------------

def test_no_tier_violations():
    """
    Lower-tier packages cannot import from higher-tier packages.

    Tier 0 (foundation) has no dependencies.
    Tier 1 can only import from Tier 0.
    Tier 2 can import from Tier 0-1.
    etc.
    """
    violations = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        if pkg_name not in TIER_MAP:
            continue

        pkg_tier = TIER_MAP[pkg_name]
        src_dir = pkg_dir / "src" / pkg_name.replace("-", "_")

        if not src_dir.exists():
            continue

        for py_file in src_dir.rglob("*.py"):
            imports = get_imports_from_file(py_file)

            for imp in imports:
                # Check if import is a django_* package
                if imp.startswith("django_"):
                    # Convert import name to package name
                    dep_pkg = imp.replace("_", "-")

                    if dep_pkg in TIER_MAP:
                        dep_tier = TIER_MAP[dep_pkg]
                        if dep_tier > pkg_tier:
                            violations.append(
                                f"{pkg_name} (tier {pkg_tier}) imports {dep_pkg} (tier {dep_tier}) "
                                f"in {py_file.relative_to(PACKAGES_DIR)}"
                            )

    assert not violations, (
        "Tier violations detected (lower tiers cannot import higher tiers):\n"
        + "\n".join(violations)
    )


# -----------------------------
# 2) Version consistency
# -----------------------------

def test_version_consistency():
    """
    __init__.py __version__ must match pyproject.toml version.
    """
    mismatches = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        pyproject = pkg_dir / "pyproject.toml"
        init_py = pkg_dir / "src" / pkg_name.replace("-", "_") / "__init__.py"

        if not pyproject.exists() or not init_py.exists():
            continue

        # Extract version from pyproject.toml
        pyproject_text = pyproject.read_text()
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', pyproject_text)
        if not match:
            continue
        pyproject_version = match.group(1)

        # Extract version from __init__.py
        init_text = init_py.read_text()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_text)
        if not match:
            mismatches.append(f"{pkg_name}: __init__.py missing __version__")
            continue
        init_version = match.group(1)

        if pyproject_version != init_version:
            mismatches.append(
                f"{pkg_name}: pyproject.toml={pyproject_version}, __init__.py={init_version}"
            )

    assert not mismatches, (
        "Version mismatches detected:\n" + "\n".join(mismatches)
    )


# -----------------------------
# 3) GenericForeignKey object_id types
# -----------------------------

def test_genericfk_object_id_uses_charfield():
    """
    GenericForeignKey object_id fields should use CharField, not PositiveIntegerField.

    This ensures UUID support across the ecosystem.
    """
    violations = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        models_py = pkg_dir / "src" / pkg_name.replace("-", "_") / "models.py"

        if not models_py.exists():
            continue

        source = models_py.read_text()
        lines = source.split('\n')

        for i, line in enumerate(lines, 1):
            # Look for object_id fields using PositiveIntegerField
            if 'PositiveIntegerField' in line and 'object_id' in line.lower():
                violations.append(
                    f"{pkg_name}/models.py:{i}: GenericFK object_id uses PositiveIntegerField "
                    "(should be CharField for UUID support)"
                )

    assert not violations, (
        "GenericForeignKey object_id should use CharField:\n" + "\n".join(violations)
    )


# -----------------------------
# 4) AUTH_USER_MODEL usage
# -----------------------------

def test_uses_auth_user_model_not_direct_import():
    """
    Packages should use settings.AUTH_USER_MODEL, not direct User imports.

    Direct imports break swappable user model support.
    """
    violations = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        src_dir = pkg_dir / "src" / pkg_name.replace("-", "_")

        if not src_dir.exists():
            continue

        for py_file in src_dir.rglob("*.py"):
            if py_file.name == '__init__.py':
                continue

            source = py_file.read_text()

            # Check for direct User imports
            if re.search(r'from django\.contrib\.auth\.models import.*\bUser\b', source):
                # Exception: importing AbstractUser for subclassing is OK
                if 'AbstractUser' not in source:
                    violations.append(
                        f"{pkg_name}/{py_file.name}: imports User directly. "
                        "Use settings.AUTH_USER_MODEL instead."
                    )

            # Check for get_user_model() which is also acceptable
            # but ForeignKey should use settings.AUTH_USER_MODEL string

    assert not violations, (
        "Direct User imports detected (breaks swappable user model):\n"
        + "\n".join(violations)
    )


# -----------------------------
# 5) Lazy imports in __init__.py
# -----------------------------

def test_init_uses_lazy_imports():
    """
    __init__.py should use lazy imports (__getattr__) to prevent AppRegistryNotReady.

    Eager model imports in __init__.py cause import-time errors.
    """
    warnings = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        init_py = pkg_dir / "src" / pkg_name.replace("-", "_") / "__init__.py"

        if not init_py.exists():
            continue

        source = init_py.read_text()

        # Check for eager model imports
        if re.search(r'^from \.models import', source, re.MULTILINE):
            # Check if __getattr__ is defined (lazy import pattern)
            if '__getattr__' not in source:
                warnings.append(
                    f"{pkg_name}/__init__.py: eager model import without __getattr__. "
                    "Use lazy imports to prevent AppRegistryNotReady."
                )

    assert not warnings, (
        "Eager model imports in __init__.py (use lazy imports):\n"
        + "\n".join(warnings)
    )


# -----------------------------
# 6) Test file existence
# -----------------------------

def test_packages_have_tests():
    """All packages should have test files."""
    missing = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        tests_dir = pkg_dir / "tests"

        if not tests_dir.exists():
            missing.append(f"{pkg_name}: no tests/ directory")
            continue

        test_files = list(tests_dir.glob("test_*.py"))
        if not test_files:
            missing.append(f"{pkg_name}: no test_*.py files in tests/")

    assert not missing, (
        "Packages missing tests:\n" + "\n".join(missing)
    )


# -----------------------------
# 7) README existence
# -----------------------------

def test_packages_have_readme():
    """All packages should have README.md."""
    missing = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        readme = pkg_dir / "README.md"

        if not readme.exists():
            missing.append(pkg_name)

    assert not missing, (
        f"Packages missing README.md: {', '.join(missing)}"
    )


# -----------------------------
# 8) ForeignKey on_delete patterns
# -----------------------------

def test_foreignkey_on_delete_not_cascade_for_audit():
    """
    Audit/logging models should use on_delete=PROTECT, not CASCADE.

    CASCADE on audit logs means deleting a user deletes their audit trail.
    """
    audit_packages = ["django-audit-log", "django-decisioning"]
    violations = []

    for pkg_name in audit_packages:
        pkg_dir = PACKAGES_DIR / pkg_name
        models_py = pkg_dir / "src" / pkg_name.replace("-", "_") / "models.py"

        if not models_py.exists():
            continue

        source = models_py.read_text()
        lines = source.split('\n')

        for i, line in enumerate(lines, 1):
            if 'ForeignKey' in line and 'on_delete=models.CASCADE' in line:
                # Check if it's a user reference
                if 'USER_MODEL' in line or 'user' in line.lower():
                    violations.append(
                        f"{pkg_name}/models.py:{i}: User FK uses CASCADE. "
                        "Audit models should use PROTECT to preserve history."
                    )

    assert not violations, (
        "Audit model ForeignKey should use PROTECT:\n" + "\n".join(violations)
    )


# -----------------------------
# 9) unique_together vs UniqueConstraint
# -----------------------------

def test_prefer_unique_constraint_over_unique_together():
    """
    Prefer UniqueConstraint over legacy unique_together.

    unique_together is deprecated in favor of UniqueConstraint.
    """
    usages = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        models_py = pkg_dir / "src" / pkg_name.replace("-", "_") / "models.py"

        if not models_py.exists():
            continue

        source = models_py.read_text()

        if 'unique_together' in source:
            usages.append(f"{pkg_name}/models.py uses unique_together (prefer UniqueConstraint)")

    # This is a warning, not a hard failure
    if usages:
        pytest.skip(
            "Legacy unique_together usage (consider migrating to UniqueConstraint):\n"
            + "\n".join(usages)
        )


# -----------------------------
# 10) Append-only model enforcement
# -----------------------------

def test_append_only_models_block_updates():
    """
    Models marked as append-only should override save() to block updates.
    """
    append_only_models = [
        ("django-audit-log", "AuditLog"),
    ]

    violations = []

    for pkg_name, model_name in append_only_models:
        pkg_dir = PACKAGES_DIR / pkg_name
        models_py = pkg_dir / "src" / pkg_name.replace("-", "_") / "models.py"

        if not models_py.exists():
            continue

        source = models_py.read_text()

        # Check if the model has a save() override that blocks updates
        # Simple heuristic: look for "def save" and "pk" check
        class_pattern = f"class {model_name}"
        if class_pattern in source:
            class_start = source.find(class_pattern)
            # Find next class or end of file
            next_class = source.find("\nclass ", class_start + 1)
            if next_class == -1:
                next_class = len(source)
            class_source = source[class_start:next_class]

            if "def save" not in class_source:
                violations.append(
                    f"{pkg_name}/{model_name}: append-only model missing save() override"
                )
            elif "self.pk" not in class_source and "self._state.adding" not in class_source:
                violations.append(
                    f"{pkg_name}/{model_name}: save() doesn't check for existing pk"
                )

    assert not violations, (
        "Append-only models missing update protection:\n" + "\n".join(violations)
    )


# -----------------------------
# 11) Domain models inherit BaseModel
# -----------------------------

def test_domain_models_inherit_basemodel():
    """
    Domain package models should inherit from BaseModel.

    Exceptions must be marked with '# PRIMITIVES: allow-plain-model'.
    """
    domain_packages = [
        "django-parties", "django-catalog", "django-encounters",
        "django-worklog", "django-geo", "django-ledger",
        "django-documents", "django-notes", "django-agreements",
    ]

    violations = []

    for pkg_name in domain_packages:
        pkg_dir = PACKAGES_DIR / pkg_name
        models_py = pkg_dir / "src" / pkg_name.replace("-", "_") / "models.py"

        if not models_py.exists():
            continue

        source = models_py.read_text()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            # Skip abstract models
            is_abstract = False
            for stmt in node.body:
                if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
                    for meta_stmt in stmt.body:
                        if isinstance(meta_stmt, ast.Assign):
                            for target in meta_stmt.targets:
                                if isinstance(target, ast.Name) and target.id == "abstract":
                                    is_abstract = True

            if is_abstract:
                continue

            # Check bases
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(base.attr)

            # Skip if inherits from BaseModel or another model that does
            if "BaseModel" in base_names:
                continue

            # Skip if has Model in bases (might inherit from abstract that has BaseModel)
            if "Model" not in base_names and not any("Model" in b for b in base_names):
                continue

            # Check for allow-plain-model marker
            class_line = node.lineno
            preceding_lines = source.split('\n')[max(0, class_line-5):class_line]
            preceding = '\n'.join(preceding_lines)

            if "allow-plain-model" not in preceding:
                # Check if it's just models.Model (concrete)
                if "models.Model" in [f"{b}" for b in base_names] or "Model" in base_names:
                    violations.append(
                        f"{pkg_name}/{node.name}: inherits models.Model, not BaseModel. "
                        f"Add '# PRIMITIVES: allow-plain-model' or inherit BaseModel."
                    )

    assert not violations, (
        "Domain models should inherit BaseModel:\n" + "\n".join(violations)
    )


# -----------------------------
# 12) Circular import detection (basic)
# -----------------------------

def test_no_circular_imports():
    """
    Packages should not have circular imports.

    This is a basic check - imports each package and catches ImportError.
    """
    errors = []

    for pkg_dir in get_package_dirs():
        pkg_name = pkg_dir.name
        module_name = pkg_name.replace("-", "_")

        try:
            # Fresh import
            if module_name in sys.modules:
                del sys.modules[module_name]
            importlib.import_module(module_name)
        except ImportError as e:
            if "circular" in str(e).lower():
                errors.append(f"{pkg_name}: {e}")
        except Exception:
            pass  # Other errors are OK for this test

    assert not errors, (
        "Circular imports detected:\n" + "\n".join(errors)
    )
