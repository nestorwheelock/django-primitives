"""Configuration loading and validation for django-layers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when configuration is invalid."""

    pass


@dataclass
class Layer:
    """A named layer containing packages."""

    name: str
    packages: list[str]
    level: int  # Lower = more foundational (tier1=0, tier2=1, etc.)


@dataclass
class LayersConfig:
    """Parsed layers configuration."""

    layers: list[Layer]
    ignore_paths: list[str] = field(default_factory=list)
    allowed_imports: list[dict[str, str]] = field(default_factory=list)
    default_rule: str = "same_or_lower"

    def get_layer_for_package(self, package_name: str) -> Layer | None:
        """Find which layer a package belongs to."""
        for layer in self.layers:
            if package_name in layer.packages:
                return layer
        return None

    def is_import_allowed(
        self, from_package: str, to_package: str
    ) -> tuple[bool, str]:
        """Check if an import from one package to another is allowed.

        Returns:
            (allowed, reason) tuple
        """
        from_layer = self.get_layer_for_package(from_package)
        to_layer = self.get_layer_for_package(to_package)

        # If either package is not in config, allow (not our concern)
        if from_layer is None or to_layer is None:
            return True, "not configured"

        # Check explicit allowlist
        for allowed in self.allowed_imports:
            if allowed.get("from") == from_package and allowed.get("to") == to_package:
                return True, "explicitly allowed"

        # Apply default rule
        if self.default_rule == "same_or_lower":
            if to_layer.level <= from_layer.level:
                return True, f"allowed: {to_layer.name} <= {from_layer.name}"
            else:
                return (
                    False,
                    f"violation: {from_layer.name} (level {from_layer.level}) "
                    f"cannot import from {to_layer.name} (level {to_layer.level})",
                )

        return True, "unknown rule"


def load_config(config_path: Path | str) -> LayersConfig:
    """Load and validate layers configuration from YAML file.

    Args:
        config_path: Path to layers.yaml

    Returns:
        LayersConfig object

    Raises:
        ConfigError: If configuration is invalid
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML: {e}")

    if not isinstance(data, dict):
        raise ConfigError("Config must be a YAML mapping")

    return _parse_config(data)


def _parse_config(data: dict[str, Any]) -> LayersConfig:
    """Parse configuration dictionary into LayersConfig."""
    # Parse layers
    layers_data = data.get("layers", [])
    if not isinstance(layers_data, list):
        raise ConfigError("'layers' must be a list")

    layers = []
    for i, layer_data in enumerate(layers_data):
        if not isinstance(layer_data, dict):
            raise ConfigError(f"Layer {i} must be a mapping")

        name = layer_data.get("name")
        if not name:
            raise ConfigError(f"Layer {i} missing 'name'")

        packages = layer_data.get("packages", [])
        if not isinstance(packages, list):
            raise ConfigError(f"Layer '{name}' packages must be a list")

        layers.append(Layer(name=name, packages=packages, level=i))

    # Parse ignore paths
    ignore_data = data.get("ignore", {})
    ignore_paths = ignore_data.get("paths", []) if isinstance(ignore_data, dict) else []

    # Parse allowed imports
    allow_data = data.get("allow", {})
    allowed_imports = allow_data.get("imports", []) if isinstance(allow_data, dict) else []

    # Parse rules
    rules_data = data.get("rules", {})
    default_rule = rules_data.get("default", "same_or_lower") if isinstance(rules_data, dict) else "same_or_lower"

    return LayersConfig(
        layers=layers,
        ignore_paths=ignore_paths,
        allowed_imports=allowed_imports,
        default_rule=default_rule,
    )
