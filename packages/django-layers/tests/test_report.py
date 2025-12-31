"""Tests for report formatting."""

import json
import pytest
from pathlib import Path

from django_layers.report import Violation, format_text, format_json


class TestViolation:
    """Tests for Violation dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        v = Violation(
            file_path=Path("/path/to/file.py"),
            line_number=42,
            import_module="pkg_b.models",
            from_package="pkg-a",
            to_package="pkg-b",
            from_layer="tier1",
            to_layer="tier2",
            reason="violation: tier1 cannot import tier2",
        )

        d = v.to_dict()

        assert d["file"] == "/path/to/file.py"
        assert d["line"] == 42
        assert d["import"] == "pkg_b.models"
        assert d["from_package"] == "pkg-a"
        assert d["to_package"] == "pkg-b"
        assert d["reason"] == "violation: tier1 cannot import tier2"


class TestFormatText:
    """Tests for format_text function."""

    def test_format_empty_violations(self):
        """Formats empty violation list."""
        result = format_text([])
        assert "No layer violations found" in result

    def test_format_single_violation(self):
        """Formats single violation."""
        violations = [
            Violation(
                file_path=Path("/path/to/file.py"),
                line_number=42,
                import_module="pkg_b.models",
                from_package="pkg-a",
                to_package="pkg-b",
                from_layer="tier1",
                to_layer="tier2",
                reason="violation",
            )
        ]

        result = format_text(violations)

        assert "1 layer violation" in result
        assert "file.py:42" in result
        assert "pkg_b.models" in result
        assert "pkg-a" in result
        assert "tier1" in result

    def test_format_multiple_violations(self):
        """Formats multiple violations."""
        violations = [
            Violation(
                file_path=Path("/path/to/file1.py"),
                line_number=10,
                import_module="pkg_b.models",
                from_package="pkg-a",
                to_package="pkg-b",
                from_layer="tier1",
                to_layer="tier2",
                reason="violation",
            ),
            Violation(
                file_path=Path("/path/to/file2.py"),
                line_number=20,
                import_module="pkg_c.utils",
                from_package="pkg-a",
                to_package="pkg-c",
                from_layer="tier1",
                to_layer="tier3",
                reason="violation",
            ),
        ]

        result = format_text(violations)

        assert "2 layer violation" in result
        assert "file1.py" in result
        assert "file2.py" in result

    def test_format_with_root_dir(self):
        """Uses relative paths when root_dir provided."""
        violations = [
            Violation(
                file_path=Path("/root/packages/pkg-a/file.py"),
                line_number=10,
                import_module="pkg_b.models",
                from_package="pkg-a",
                to_package="pkg-b",
                from_layer="tier1",
                to_layer="tier2",
                reason="violation",
            ),
        ]

        result = format_text(violations, root_dir=Path("/root"))

        assert "packages/pkg-a/file.py" in result


class TestFormatJson:
    """Tests for format_json function."""

    def test_format_empty_violations(self):
        """Formats empty violation list as JSON."""
        result = format_json([])
        data = json.loads(result)

        assert data["violations"] == []
        assert data["count"] == 0

    def test_format_single_violation(self):
        """Formats single violation as JSON."""
        violations = [
            Violation(
                file_path=Path("/path/to/file.py"),
                line_number=42,
                import_module="pkg_b.models",
                from_package="pkg-a",
                to_package="pkg-b",
                from_layer="tier1",
                to_layer="tier2",
                reason="violation",
            )
        ]

        result = format_json(violations)
        data = json.loads(result)

        assert data["count"] == 1
        assert len(data["violations"]) == 1
        assert data["violations"][0]["line"] == 42

    def test_json_is_valid(self):
        """Output is valid JSON."""
        violations = [
            Violation(
                file_path=Path("/path/to/file.py"),
                line_number=42,
                import_module="pkg_b.models",
                from_package="pkg-a",
                to_package="pkg-b",
                from_layer="tier1",
                to_layer="tier2",
                reason="violation",
            )
        ]

        result = format_json(violations)

        # Should not raise
        json.loads(result)
