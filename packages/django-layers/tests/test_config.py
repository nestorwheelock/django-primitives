"""Tests for configuration loading and validation."""

import pytest
from pathlib import Path
import tempfile

from django_layers.config import (
    ConfigError,
    Layer,
    LayersConfig,
    load_config,
    _parse_config,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self):
        """Loads valid layers.yaml successfully."""
        config = load_config(FIXTURES_DIR / "layers.yaml")

        assert len(config.layers) == 3
        assert config.layers[0].name == "tier1"
        assert config.layers[1].name == "tier2"
        assert config.layers[2].name == "tier3"

    def test_load_missing_file_raises(self):
        """Raises ConfigError for missing file."""
        with pytest.raises(ConfigError) as exc_info:
            load_config(Path("/nonexistent/layers.yaml"))

        assert "not found" in str(exc_info.value)

    def test_load_invalid_yaml_raises(self):
        """Raises ConfigError for invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()

            with pytest.raises(ConfigError) as exc_info:
                load_config(Path(f.name))

            assert "Invalid YAML" in str(exc_info.value)


class TestParseConfig:
    """Tests for _parse_config function."""

    def test_parse_layers(self):
        """Parses layers with correct levels."""
        data = {
            "layers": [
                {"name": "foundation", "packages": ["pkg-a"]},
                {"name": "domain", "packages": ["pkg-b", "pkg-c"]},
            ]
        }

        config = _parse_config(data)

        assert len(config.layers) == 2
        assert config.layers[0].level == 0
        assert config.layers[1].level == 1
        assert config.layers[0].packages == ["pkg-a"]
        assert config.layers[1].packages == ["pkg-b", "pkg-c"]

    def test_parse_ignore_paths(self):
        """Parses ignore paths."""
        data = {
            "layers": [],
            "ignore": {"paths": ["**/tests/**", "**/migrations/**"]},
        }

        config = _parse_config(data)

        assert "**/tests/**" in config.ignore_paths
        assert "**/migrations/**" in config.ignore_paths

    def test_parse_allowed_imports(self):
        """Parses allowed imports."""
        data = {
            "layers": [],
            "allow": {
                "imports": [
                    {"from": "pkg-a", "to": "pkg-b"},
                ]
            },
        }

        config = _parse_config(data)

        assert len(config.allowed_imports) == 1
        assert config.allowed_imports[0]["from"] == "pkg-a"

    def test_parse_default_rule(self):
        """Parses default rule."""
        data = {
            "layers": [],
            "rules": {"default": "same_or_lower"},
        }

        config = _parse_config(data)

        assert config.default_rule == "same_or_lower"

    def test_missing_layer_name_raises(self):
        """Raises ConfigError for layer without name."""
        data = {"layers": [{"packages": ["pkg-a"]}]}

        with pytest.raises(ConfigError) as exc_info:
            _parse_config(data)

        assert "missing 'name'" in str(exc_info.value)

    def test_layers_not_list_raises(self):
        """Raises ConfigError if layers is not a list."""
        data = {"layers": "not a list"}

        with pytest.raises(ConfigError) as exc_info:
            _parse_config(data)

        assert "must be a list" in str(exc_info.value)


class TestLayersConfig:
    """Tests for LayersConfig class."""

    @pytest.fixture
    def config(self):
        """Create a test config."""
        return LayersConfig(
            layers=[
                Layer(name="tier1", packages=["pkg-a"], level=0),
                Layer(name="tier2", packages=["pkg-b"], level=1),
                Layer(name="tier3", packages=["pkg-c"], level=2),
            ]
        )

    def test_get_layer_for_package(self, config):
        """Finds correct layer for package."""
        layer = config.get_layer_for_package("pkg-a")
        assert layer.name == "tier1"

        layer = config.get_layer_for_package("pkg-b")
        assert layer.name == "tier2"

    def test_get_layer_for_unknown_package(self, config):
        """Returns None for unknown package."""
        layer = config.get_layer_for_package("unknown-pkg")
        assert layer is None

    def test_is_import_allowed_same_layer(self, config):
        """Same layer imports are allowed."""
        config.layers[0].packages.append("pkg-a2")

        allowed, reason = config.is_import_allowed("pkg-a", "pkg-a2")
        assert allowed is True

    def test_is_import_allowed_lower_layer(self, config):
        """Lower layer imports are allowed."""
        allowed, reason = config.is_import_allowed("pkg-b", "pkg-a")
        assert allowed is True

    def test_is_import_not_allowed_higher_layer(self, config):
        """Higher layer imports are not allowed."""
        allowed, reason = config.is_import_allowed("pkg-a", "pkg-b")
        assert allowed is False
        assert "violation" in reason

    def test_is_import_allowed_unknown_package(self, config):
        """Unknown packages are allowed (not our concern)."""
        allowed, reason = config.is_import_allowed("pkg-a", "unknown")
        assert allowed is True
        assert "not configured" in reason

    def test_explicit_allowlist(self, config):
        """Explicit allowlist overrides layer rules."""
        config.allowed_imports.append({"from": "pkg-a", "to": "pkg-c"})

        allowed, reason = config.is_import_allowed("pkg-a", "pkg-c")
        assert allowed is True
        assert "explicitly allowed" in reason
