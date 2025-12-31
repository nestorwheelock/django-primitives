"""Tests for package resolution."""

import pytest
from pathlib import Path

from django_layers.resolver import PackageResolver, STDLIB_MODULES


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestPackageResolver:
    """Tests for PackageResolver class."""

    @pytest.fixture
    def resolver(self):
        """Create resolver for fixtures directory."""
        return PackageResolver(FIXTURES_DIR)

    def test_resolve_local_package(self, resolver):
        """Resolves local package module to package name."""
        result = resolver.resolve("pkg_tier1.models")
        assert result == "pkg-tier1"

        result = resolver.resolve("pkg_tier2")
        assert result == "pkg-tier2"

    def test_resolve_submodule(self, resolver):
        """Resolves submodule to package name."""
        result = resolver.resolve("pkg_tier1.models.BaseModel")
        assert result == "pkg-tier1"

    def test_resolve_stdlib(self, resolver):
        """Returns None for stdlib modules."""
        result = resolver.resolve("os")
        assert result is None

        result = resolver.resolve("pathlib.Path")
        assert result is None

    def test_resolve_unknown(self, resolver):
        """Returns None for unknown modules."""
        result = resolver.resolve("unknown_package.module")
        assert result is None

    def test_is_stdlib(self, resolver):
        """Correctly identifies stdlib modules."""
        assert resolver.is_stdlib("os") is True
        assert resolver.is_stdlib("json") is True
        assert resolver.is_stdlib("pathlib") is True
        assert resolver.is_stdlib("collections.abc") is True
        assert resolver.is_stdlib("django") is False
        assert resolver.is_stdlib("pkg_tier1") is False

    def test_is_third_party(self, resolver):
        """Correctly identifies third-party modules."""
        assert resolver.is_third_party("django") is True
        assert resolver.is_third_party("requests") is True
        assert resolver.is_third_party("os") is False
        assert resolver.is_third_party("pkg_tier1") is False

    def test_get_source_package(self, resolver):
        """Determines package from file path."""
        file_path = FIXTURES_DIR / "packages/pkg-tier1/src/pkg_tier1/models.py"
        result = resolver.get_source_package(file_path)
        assert result == "pkg-tier1"

    def test_get_source_package_test_file(self, resolver):
        """Determines package from test file path."""
        file_path = FIXTURES_DIR / "packages/pkg-tier2/tests/test_models.py"
        result = resolver.get_source_package(file_path)
        assert result == "pkg-tier2"

    def test_get_source_package_outside_packages(self, resolver):
        """Returns None for files outside packages directory."""
        file_path = Path("/some/other/path/file.py")
        result = resolver.get_source_package(file_path)
        assert result is None


class TestStdlibModules:
    """Tests for STDLIB_MODULES set."""

    def test_common_modules_included(self):
        """Common stdlib modules are included."""
        common = ["os", "sys", "json", "pathlib", "collections", "typing"]
        for module in common:
            assert module in STDLIB_MODULES, f"{module} should be in STDLIB_MODULES"

    def test_third_party_not_included(self):
        """Third-party modules are not included."""
        third_party = ["django", "requests", "flask", "numpy"]
        for module in third_party:
            assert module not in STDLIB_MODULES, f"{module} should not be in STDLIB_MODULES"
