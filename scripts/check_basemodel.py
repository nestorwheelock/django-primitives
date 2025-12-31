#!/usr/bin/env python3
"""
Check that domain models inherit from BaseModel and don't redefine timestamps.

Rules:
- Domain models must inherit from BaseModel
- Models must not redefine: id, created_at, updated_at, deleted_at

Exit codes:
- 0: No violations
- 1: Violations found
"""

import ast
import re
import sys
from pathlib import Path


# Fields that should never be redefined (inherited from BaseModel)
PROTECTED_FIELDS = {"id", "created_at", "updated_at", "deleted_at"}

# Models that are allowed to not inherit from BaseModel
EXEMPT_MODELS = {
    "BaseModel",  # The base itself
    "AbstractBaseModel",
    "Migration",  # Django migrations
    # django-basemodels mixin classes (they define the fields)
    "TimeStampedModel",
    "UUIDModel",
    "SoftDeleteModel",
    # django-audit-log is standalone (no BaseModel dependency)
    "AuditLog",
    # django-catalog base (standalone package)
    "CatalogBaseModel",
    # django-encounters base (standalone package)
    "EncountersBaseModel",
}


class ModelChecker(ast.NodeVisitor):
    """AST visitor that checks model definitions."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.violations = []

    def visit_ClassDef(self, node: ast.ClassDef):
        # Skip exempt models
        if node.name in EXEMPT_MODELS:
            self.generic_visit(node)
            return

        # Check if this looks like a Django model
        if self._is_django_model(node):
            # Check for protected field redefinition
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id in PROTECTED_FIELDS:
                                self.violations.append({
                                    "file": str(self.filepath),
                                    "line": item.lineno,
                                    "model": node.name,
                                    "field": target.id,
                                    "message": f"Model '{node.name}' redefines '{target.id}' (should be inherited from BaseModel)"
                                })

        self.generic_visit(node)

    def _is_django_model(self, node: ast.ClassDef) -> bool:
        """Check if class appears to be a Django model."""
        for base in node.bases:
            base_name = self._get_base_name(base)
            if base_name and ("Model" in base_name or "Base" in base_name):
                return True
        return False

    def _get_base_name(self, base: ast.expr) -> str | None:
        """Extract base class name from AST node."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return base.attr
        return None


def check_file(filepath: Path) -> list[dict]:
    """Check a single Python file for violations."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
        checker = ModelChecker(filepath)
        checker.visit(tree)
        return checker.violations
    except SyntaxError as e:
        print(f"WARNING: Syntax error in {filepath}: {e}")
        return []


def find_model_files(root: Path) -> list[Path]:
    """Find all models.py files in packages/*/src/."""
    packages_dir = root / "packages"
    if not packages_dir.exists():
        return []

    files = []
    for package_dir in packages_dir.iterdir():
        if not package_dir.is_dir():
            continue
        src_dir = package_dir / "src"
        if src_dir.exists():
            for model_file in src_dir.rglob("models.py"):
                # Skip test models
                if "/tests/" not in str(model_file):
                    files.append(model_file)
    return files


def main():
    """Main entry point."""
    root = Path(__file__).parent.parent

    print("Checking BaseModel usage...")
    print()

    all_violations = []
    files = find_model_files(root)

    if not files:
        print("No models.py files found yet. Skipping check.")
        return 0

    for filepath in files:
        violations = check_file(filepath)
        all_violations.extend(violations)

    if all_violations:
        print("VIOLATIONS FOUND:")
        print()
        for v in all_violations:
            print(f"  {v['file']}:{v['line']}")
            print(f"    Model: {v['model']}")
            print(f"    Field: {v['field']}")
            print(f"    → {v['message']}")
            print()
        print(f"FAILED: {len(all_violations)} violation(s) found")
        return 1
    else:
        print(f"OK: Checked {len(files)} files, no violations")
        return 0


if __name__ == "__main__":
    sys.exit(main())
