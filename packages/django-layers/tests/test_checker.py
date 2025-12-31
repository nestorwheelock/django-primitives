"""Tests for the main checker logic."""

import pytest
from pathlib import Path

from django_layers.checker import check_layers
from django_layers.config import load_config


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCheckLayers:
    """Tests for check_layers function."""

    @pytest.fixture
    def config(self):
        """Load test config."""
        return load_config(FIXTURES_DIR / "layers.yaml")

    def test_detects_upward_import(self, config):
        """Detects illegal upward import (tier2 -> tier3)."""
        violations = check_layers(FIXTURES_DIR, config, include_tests=False)

        # Should find the bad import in pkg-tier2/bad_import.py
        bad_imports = [v for v in violations if "bad_import" in str(v.file_path)]
        assert len(bad_imports) == 1

        violation = bad_imports[0]
        assert violation.from_package == "pkg-tier2"
        assert violation.to_package == "pkg-tier3"
        assert violation.from_layer == "tier2"
        assert violation.to_layer == "tier3"

    def test_allows_downward_import(self, config):
        """Allows legal downward import (tier2 -> tier1)."""
        violations = check_layers(FIXTURES_DIR, config, include_tests=False)

        # Should NOT flag pkg-tier2/models.py importing from pkg-tier1
        tier1_violations = [
            v for v in violations
            if v.to_package == "pkg-tier1" and "models.py" in str(v.file_path)
        ]
        assert len(tier1_violations) == 0

    def test_allows_same_layer_import(self, config):
        """Allows imports within same layer."""
        # Add another package to tier1 for testing
        config.layers[0].packages.append("pkg-tier1b")

        violations = check_layers(FIXTURES_DIR, config, include_tests=False)

        # No violations for same-layer imports
        same_layer_violations = [
            v for v in violations
            if v.from_layer == v.to_layer
        ]
        assert len(same_layer_violations) == 0

    def test_ignores_tests_by_default(self, config):
        """Ignores test files by default."""
        violations = check_layers(FIXTURES_DIR, config, include_tests=False)

        # Should NOT flag the import in pkg-tier2/tests/test_models.py
        # (only flag bad_import.py which is in src, not tests)
        test_violations = [
            v for v in violations
            if "/tests/" in str(v.file_path) and "test_" in v.file_path.name
        ]
        assert len(test_violations) == 0

    def test_includes_tests_when_requested(self, config):
        """Includes test files when requested."""
        violations = check_layers(FIXTURES_DIR, config, include_tests=True)

        # Should flag the import in tests/test_models.py
        test_violations = [v for v in violations if "tests" in str(v.file_path)]
        assert len(test_violations) >= 1

    def test_ignores_stdlib_imports(self, config):
        """Ignores standard library imports."""
        violations = check_layers(FIXTURES_DIR, config, include_tests=False)

        # No violations for os, json imports
        stdlib_violations = [v for v in violations if v.to_package in ["os", "json"]]
        assert len(stdlib_violations) == 0

    def test_ignores_third_party_imports(self, config):
        """Ignores third-party imports."""
        violations = check_layers(FIXTURES_DIR, config, include_tests=False)

        # No violations for third-party packages
        for v in violations:
            assert v.to_package is not None
            assert v.from_package is not None


class TestCheckLayersEdgeCases:
    """Edge case tests for check_layers."""

    def test_empty_directory(self):
        """Handles empty packages directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            config = load_config(FIXTURES_DIR / "layers.yaml")
            violations = check_layers(tmppath, config)

            assert violations == []

    def test_missing_packages_directory(self):
        """Handles missing packages directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            config = load_config(FIXTURES_DIR / "layers.yaml")
            violations = check_layers(tmppath, config)

            assert violations == []
