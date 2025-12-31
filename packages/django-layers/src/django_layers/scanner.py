"""AST-based import scanner for Python source files."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Import:
    """A detected import statement."""

    module: str  # The imported module (e.g., 'django_catalog.models')
    file_path: Path  # Source file containing the import
    line_number: int  # Line number of the import


class ImportVisitor(ast.NodeVisitor):
    """AST visitor that collects import statements."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports: list[Import] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import x' statements."""
        for alias in node.names:
            self.imports.append(
                Import(
                    module=alias.name,
                    file_path=self.file_path,
                    line_number=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from x import y' statements."""
        if node.module:  # Ignore 'from . import x' with no module
            self.imports.append(
                Import(
                    module=node.module,
                    file_path=self.file_path,
                    line_number=node.lineno,
                )
            )
        self.generic_visit(node)


def scan_file(file_path: Path) -> list[Import]:
    """Scan a Python file for imports.

    Args:
        file_path: Path to Python source file

    Returns:
        List of Import objects found in the file
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    visitor = ImportVisitor(file_path)
    visitor.visit(tree)
    return visitor.imports


def scan_directory(
    directory: Path,
    ignore_patterns: list[str] | None = None,
) -> list[Import]:
    """Scan all Python files in a directory for imports.

    Args:
        directory: Root directory to scan
        ignore_patterns: Glob patterns for paths to ignore

    Returns:
        List of all Import objects found
    """
    ignore_patterns = ignore_patterns or []
    all_imports: list[Import] = []

    for py_file in directory.rglob("*.py"):
        # Check ignore patterns
        if _should_ignore(py_file, directory, ignore_patterns):
            continue

        all_imports.extend(scan_file(py_file))

    return all_imports


def _should_ignore(file_path: Path, root: Path, patterns: list[str]) -> bool:
    """Check if a file should be ignored based on patterns."""
    rel_path = file_path.relative_to(root)
    rel_str = str(rel_path)

    for pattern in patterns:
        # Simple glob matching
        if _matches_pattern(rel_str, pattern):
            return True

    return False


def _matches_pattern(path: str, pattern: str) -> bool:
    """Simple glob pattern matching.

    Supports:
    - ** for any directory depth
    - * for any characters in a segment
    """
    import fnmatch

    # Normalize pattern
    pattern = pattern.replace("\\", "/")
    path = path.replace("\\", "/")

    # Handle ** patterns like **/tests/** or **/migrations/**
    if "**" in pattern:
        parts = pattern.split("**")
        # Filter out empty parts and strip slashes
        segments = [p.strip("/") for p in parts if p.strip("/")]

        if not segments:
            # Pattern is just ** or **/** - matches everything
            return True

        # For patterns like **/tests/** we need to check if 'tests' appears
        # as a directory component in the path
        normalized = f"/{path}/"
        for segment in segments:
            if f"/{segment}/" not in normalized:
                return False
        return True

    return fnmatch.fnmatch(path, pattern)
