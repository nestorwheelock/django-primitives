#!/usr/bin/env python3
"""
Check that primitive packages don't import from each other.

Primitives may only import from:
- django_basemodels (foundation)
- django.* (Django framework)
- stdlib

Exit codes:
- 0: No violations
- 1: Violations found
"""

import ast
import sys
from pathlib import Path


# Primitive packages - these must not import from each other
PRIMITIVE_PACKAGES = {
    "django_party",
    "django_rbac",
    "django_audit",
    "django_catalog",
    "django_workitems",
    "django_encounters",
    "django_worklog",
    "django_modules",
    "django_singleton",
}

# Foundation package - can be imported by any primitive
FOUNDATION_PACKAGES = {
    "django_basemodels",
}

# Allowed imports (Django, stdlib)
ALLOWED_PREFIXES = (
    "django.",
    "django_basemodels",
    # stdlib - handled by not being in PRIMITIVE_PACKAGES
)


class ImportChecker(ast.NodeVisitor):
    """AST visitor that collects import statements."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.violations = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._check_import(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self._check_import(node.module, node.lineno)
        self.generic_visit(node)

    def _check_import(self, module: str, lineno: int):
        """Check if import violates boundary rules."""
        # Get the package being imported
        top_level = module.split(".")[0]

        # If importing from another primitive, that's a violation
        if top_level in PRIMITIVE_PACKAGES:
            # Check if we're inside that same package (allowed)
            current_package = self._get_current_package()
            if current_package and current_package != top_level:
                self.violations.append({
                    "file": str(self.filepath),
                    "line": lineno,
                    "module": module,
                    "message": f"Primitive '{current_package}' imports from primitive '{top_level}'"
                })

    def _get_current_package(self) -> str | None:
        """Determine which primitive package this file belongs to."""
        parts = self.filepath.parts
        for part in parts:
            if part in PRIMITIVE_PACKAGES or part.replace("-", "_") in PRIMITIVE_PACKAGES:
                return part.replace("-", "_")
        return None


def check_file(filepath: Path) -> list[dict]:
    """Check a single Python file for import violations."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
        checker = ImportChecker(filepath)
        checker.visit(tree)
        return checker.violations
    except SyntaxError as e:
        print(f"WARNING: Syntax error in {filepath}: {e}")
        return []


def find_python_files(root: Path) -> list[Path]:
    """Find all Python files in primitive packages."""
    files = []
    for package in PRIMITIVE_PACKAGES:
        package_dir = root / "src" / package
        if package_dir.exists():
            for pyfile in package_dir.rglob("*.py"):
                # Skip test files
                if "/tests/" not in str(pyfile):
                    files.append(pyfile)
    return files


def main():
    """Main entry point."""
    root = Path(__file__).parent.parent

    print("Checking primitive package dependencies...")
    print()

    all_violations = []
    files = find_python_files(root)

    if not files:
        print("No primitive packages found yet. Skipping check.")
        print("(Packages should be in src/django_*/)")
        return 0

    for filepath in files:
        violations = check_file(filepath)
        all_violations.extend(violations)

    if all_violations:
        print("VIOLATIONS FOUND:")
        print()
        for v in all_violations:
            print(f"  {v['file']}:{v['line']}")
            print(f"    imports: {v['module']}")
            print(f"    → {v['message']}")
            print()
        print(f"FAILED: {len(all_violations)} violation(s) found")
        return 1
    else:
        print(f"OK: Checked {len(files)} files, no violations")
        return 0


if __name__ == "__main__":
    sys.exit(main())
