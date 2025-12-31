"""Tests for import scanning."""

import pytest
from pathlib import Path
import tempfile

from django_layers.scanner import (
    Import,
    scan_file,
    scan_directory,
    _matches_pattern,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestScanFile:
    """Tests for scan_file function."""

    def test_scan_import_statement(self):
        """Detects 'import x' statements."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import os\nimport json\n")
            f.flush()

            imports = scan_file(Path(f.name))

            modules = {i.module for i in imports}
            assert "os" in modules
            assert "json" in modules

    def test_scan_from_import_statement(self):
        """Detects 'from x import y' statements."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from pathlib import Path\nfrom django.db import models\n")
            f.flush()

            imports = scan_file(Path(f.name))

            modules = {i.module for i in imports}
            assert "pathlib" in modules
            assert "django.db" in modules

    def test_scan_captures_line_numbers(self):
        """Captures correct line numbers."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# comment\nimport os\n\nimport json\n")
            f.flush()

            imports = scan_file(Path(f.name))

            os_import = next(i for i in imports if i.module == "os")
            json_import = next(i for i in imports if i.module == "json")

            assert os_import.line_number == 2
            assert json_import.line_number == 4

    def test_scan_captures_file_path(self):
        """Captures file path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import os\n")
            f.flush()
            path = Path(f.name)

            imports = scan_file(path)

            assert imports[0].file_path == path

    def test_scan_empty_file(self):
        """Handles empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            f.flush()

            imports = scan_file(Path(f.name))

            assert imports == []

    def test_scan_syntax_error_file(self):
        """Handles file with syntax error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(\n")
            f.flush()

            imports = scan_file(Path(f.name))

            assert imports == []

    def test_scan_missing_file(self):
        """Handles missing file."""
        imports = scan_file(Path("/nonexistent/file.py"))
        assert imports == []


class TestScanDirectory:
    """Tests for scan_directory function."""

    def test_scan_fixture_directory(self):
        """Scans all Python files in fixtures."""
        imports = scan_directory(FIXTURES_DIR / "packages")

        # Should find imports from multiple files
        modules = {i.module for i in imports}
        assert "pkg_tier1.models" in modules
        assert "pkg_tier2.models" in modules

    def test_scan_with_ignore_pattern(self):
        """Respects ignore patterns."""
        imports_all = scan_directory(FIXTURES_DIR / "packages")
        imports_no_tests = scan_directory(
            FIXTURES_DIR / "packages",
            ignore_patterns=["**/tests/**"],
        )

        # Should have fewer imports when ignoring tests
        assert len(imports_no_tests) <= len(imports_all)

        # Files in /tests/ subdirectories should be excluded
        for imp in imports_no_tests:
            rel_path = imp.file_path.relative_to(FIXTURES_DIR / "packages")
            # Check that we don't have paths like pkg-tier2/tests/test_models.py
            assert "/tests/" not in str(rel_path)


class TestMatchesPattern:
    """Tests for _matches_pattern function."""

    def test_simple_glob(self):
        """Matches simple glob pattern."""
        assert _matches_pattern("foo.py", "*.py") is True
        assert _matches_pattern("foo.txt", "*.py") is False

    def test_double_star_middle(self):
        """Matches ** in the middle of pattern."""
        assert _matches_pattern("a/tests/b.py", "**/tests/**") is True
        assert _matches_pattern("a/tests/c/d.py", "**/tests/**") is True
        # Path starting with the pattern component
        assert _matches_pattern("tests/b.py", "**/tests/**") is True

    def test_double_star_start(self):
        """Matches ** at start of pattern."""
        assert _matches_pattern("a/b/migrations/c.py", "**/migrations/**") is True

    def test_no_match(self):
        """Doesn't match unrelated paths."""
        assert _matches_pattern("src/models.py", "**/tests/**") is False
