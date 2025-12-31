"""Tests for CLI interface."""

import pytest
from pathlib import Path

from django_layers.cli import main


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCLI:
    """Tests for CLI commands."""

    def test_no_command_shows_help(self, capsys):
        """No command shows help and returns 2."""
        result = main([])

        assert result == 2

    def test_check_with_violations(self, capsys):
        """Check command returns 1 when violations found."""
        result = main([
            "check",
            "--config", str(FIXTURES_DIR / "layers.yaml"),
            "--root", str(FIXTURES_DIR),
        ])

        assert result == 1
        captured = capsys.readouterr()
        assert "violation" in captured.out.lower()

    def test_check_missing_config(self, capsys):
        """Check command returns 2 for missing config."""
        result = main([
            "check",
            "--config", "/nonexistent/layers.yaml",
        ])

        assert result == 2
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_check_json_format(self, capsys):
        """Check command outputs JSON when requested."""
        result = main([
            "check",
            "--config", str(FIXTURES_DIR / "layers.yaml"),
            "--root", str(FIXTURES_DIR),
            "--format", "json",
        ])

        captured = capsys.readouterr()
        assert '"violations"' in captured.out
        assert '"count"' in captured.out

    def test_check_include_tests(self, capsys):
        """Check command includes tests when requested."""
        result_no_tests = main([
            "check",
            "--config", str(FIXTURES_DIR / "layers.yaml"),
            "--root", str(FIXTURES_DIR),
            "--format", "json",
        ])

        result_with_tests = main([
            "check",
            "--config", str(FIXTURES_DIR / "layers.yaml"),
            "--root", str(FIXTURES_DIR),
            "--include-tests",
            "--format", "json",
        ])

        # Both should have violations
        assert result_no_tests == 1
        assert result_with_tests == 1


class TestCLIOutput:
    """Tests for CLI output formatting."""

    def test_text_format_readable(self, capsys):
        """Text format is human-readable."""
        main([
            "check",
            "--config", str(FIXTURES_DIR / "layers.yaml"),
            "--root", str(FIXTURES_DIR),
            "--format", "text",
        ])

        captured = capsys.readouterr()
        assert "From:" in captured.out or "violation" in captured.out.lower()

    def test_json_format_parseable(self, capsys):
        """JSON format is parseable."""
        import json

        main([
            "check",
            "--config", str(FIXTURES_DIR / "layers.yaml"),
            "--root", str(FIXTURES_DIR),
            "--format", "json",
        ])

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert "violations" in data
        assert "count" in data
        assert isinstance(data["violations"], list)
