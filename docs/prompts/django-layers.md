# Prompt: Rebuild django-layers

## Instruction

Create a Django package called `django-layers` that enforces import boundary rules in monorepo architectures using AST-based static analysis.

## Package Purpose

Enforce architectural layers in Django monorepos:
- Parse Python imports using AST
- Validate imports against YAML layer configuration
- Layer hierarchy enforcement (lower layers cannot import from higher)
- CLI tool for CI/CD integration

## Dependencies

- Python >= 3.11
- PyYAML >= 6.0

## File Structure

```
packages/django-layers/
├── pyproject.toml
├── README.md
├── src/django_layers/
│   ├── __init__.py
│   ├── config.py
│   ├── scanner.py
│   ├── resolver.py
│   ├── checker.py
│   ├── report.py
│   └── cli.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    │   └── layers.yaml
    ├── test_config.py
    ├── test_scanner.py
    ├── test_resolver.py
    ├── test_checker.py
    ├── test_report.py
    └── test_cli.py
```

## Configuration (layers.yaml)

```yaml
layers:
  - name: tier1
    packages:
      - pkg-tier1
  - name: tier2
    packages:
      - pkg-tier2
  - name: tier3
    packages:
      - pkg-tier3

rules:
  default: same_or_lower

ignore:
  paths:
    - "**/tests/**"
    - "**/migrations/**"

allow:
  imports:
    - from: pkg-tier2
      to: pkg-tier3
```

## Dataclass Specification

### config.py

```python
from dataclasses import dataclass

@dataclass
class Layer:
    """Represents a single architectural layer."""
    name: str
    packages: list[str]
    level: int  # Lower = more foundational

@dataclass
class LayersConfig:
    """Complete parsed configuration."""
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

    def is_import_allowed(self, from_package: str, to_package: str) -> tuple[bool, str]:
        """Validate if import is allowed."""
        from_layer = self.get_layer_for_package(from_package)
        to_layer = self.get_layer_for_package(to_package)

        if from_layer is None or to_layer is None:
            return (True, "not configured")

        # Check explicit allowlist
        for allowed in self.allowed_imports:
            if allowed['from'] == from_package and allowed['to'] == to_package:
                return (True, "explicitly allowed")

        # Apply default rule
        if self.default_rule == "same_or_lower":
            if to_layer.level <= from_layer.level:
                return (True, f"allowed: {to_layer.name} <= {from_layer.name}")
            return (False, f"violation: {from_layer.name} (level {from_layer.level}) cannot import from {to_layer.name} (level {to_layer.level})")

        return (True, "allowed")


class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


def load_config(config_path: Path) -> LayersConfig:
    """Load and validate configuration from YAML file."""
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return _parse_config(data)


def _parse_config(data: dict) -> LayersConfig:
    """Parse configuration dictionary into LayersConfig."""
    if not isinstance(data, dict):
        raise ConfigError("Config must be a YAML mapping")

    layers = []
    for i, layer_data in enumerate(data.get('layers', [])):
        if not isinstance(layer_data, dict):
            raise ConfigError(f"Layer {i} must be a mapping")
        if 'name' not in layer_data:
            raise ConfigError(f"Layer {i} missing 'name'")

        layers.append(Layer(
            name=layer_data['name'],
            packages=layer_data.get('packages', []),
            level=i  # Level assigned by position
        ))

    return LayersConfig(
        layers=layers,
        ignore_paths=data.get('ignore', {}).get('paths', []),
        allowed_imports=data.get('allow', {}).get('imports', []),
        default_rule=data.get('rules', {}).get('default', 'same_or_lower')
    )
```

### scanner.py

```python
import ast
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Import:
    """Represents a detected import statement."""
    module: str
    file_path: Path
    line_number: int


class ImportVisitor(ast.NodeVisitor):
    """AST visitor that extracts import statements."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports: list[Import] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(Import(
                module=alias.name,
                file_path=self.file_path,
                line_number=node.lineno
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:  # Ignore relative imports without module
            self.imports.append(Import(
                module=node.module,
                file_path=self.file_path,
                line_number=node.lineno
            ))


def scan_file(file_path: Path) -> list[Import]:
    """Scan a single Python file for imports."""
    try:
        content = file_path.read_text(encoding='utf-8')
        tree = ast.parse(content)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    visitor = ImportVisitor(file_path)
    visitor.visit(tree)
    return visitor.imports


def scan_directory(directory: Path, ignore_patterns: list[str] = None) -> list[Import]:
    """Recursively scan directory for all Python imports."""
    imports = []
    for py_file in directory.rglob("*.py"):
        if not _should_ignore(py_file, ignore_patterns or []):
            imports.extend(scan_file(py_file))
    return imports
```

### resolver.py

```python
class PackageResolver:
    """Maps import module names to package names."""

    STDLIB_MODULES = {
        'abc', 'argparse', 'ast', 'asyncio', 'base64', 'collections',
        'contextlib', 'copy', 'csv', 'dataclasses', 'datetime', 'decimal',
        'enum', 'functools', 'glob', 'hashlib', 'http', 'io', 'itertools',
        'json', 'logging', 'math', 'os', 'pathlib', 'pickle', 'random',
        're', 'shutil', 'signal', 'socket', 'string', 'subprocess', 'sys',
        'tempfile', 'threading', 'time', 'typing', 'unittest', 'urllib',
        'uuid', 'warnings', 'xml', 'zipfile'
    }

    def __init__(self, packages_dir: Path):
        self.packages_dir = packages_dir
        self._module_to_package: dict[str, str] = {}
        self._build_module_map()

    def _build_module_map(self):
        """Build mapping from module names to package names."""
        packages_path = self.packages_dir / 'packages'
        if not packages_path.exists():
            return

        for pkg_dir in packages_path.iterdir():
            if not pkg_dir.is_dir():
                continue
            src_dir = pkg_dir / 'src'
            if src_dir.exists():
                for module_dir in src_dir.iterdir():
                    if module_dir.is_dir() and (module_dir / '__init__.py').exists():
                        self._module_to_package[module_dir.name] = pkg_dir.name

    def resolve(self, import_module: str) -> str | None:
        """Resolve import to package name."""
        top_level = import_module.split('.')[0]
        if self.is_stdlib(top_level):
            return None
        return self._module_to_package.get(top_level)

    def is_stdlib(self, module: str) -> bool:
        """Check if module is standard library."""
        return module in self.STDLIB_MODULES

    def get_source_package(self, file_path: Path) -> str | None:
        """Determine which package a source file belongs to."""
        try:
            rel = file_path.relative_to(self.packages_dir)
            parts = rel.parts
            if parts[0] == 'packages' and len(parts) > 1:
                return parts[1]
        except ValueError:
            pass
        return None
```

### checker.py

```python
from dataclasses import dataclass

@dataclass
class Violation:
    """Represents a layer boundary violation."""
    file_path: Path
    line_number: int
    import_module: str
    from_package: str
    to_package: str
    from_layer: str
    to_layer: str
    reason: str


def check_layers(
    root_dir: Path,
    config: LayersConfig,
    include_tests: bool = False
) -> list[Violation]:
    """Check all Python files for layer boundary violations."""
    violations = []

    ignore_patterns = list(config.ignore_paths)
    if not include_tests:
        ignore_patterns.extend(['**/tests/**', '**/test_*.py'])

    resolver = PackageResolver(root_dir)
    packages_dir = root_dir / 'packages'

    if not packages_dir.exists():
        return []

    imports = scan_directory(packages_dir, ignore_patterns)

    for imp in imports:
        from_package = resolver.get_source_package(imp.file_path)
        to_package = resolver.resolve(imp.module)

        if not from_package or not to_package:
            continue
        if from_package == to_package:
            continue

        allowed, reason = config.is_import_allowed(from_package, to_package)

        if not allowed:
            from_layer = config.get_layer_for_package(from_package)
            to_layer = config.get_layer_for_package(to_package)
            violations.append(Violation(
                file_path=imp.file_path,
                line_number=imp.line_number,
                import_module=imp.module,
                from_package=from_package,
                to_package=to_package,
                from_layer=from_layer.name if from_layer else 'unknown',
                to_layer=to_layer.name if to_layer else 'unknown',
                reason=reason
            ))

    return violations
```

### report.py

```python
def format_text(violations: list[Violation], root_dir: Path = None) -> str:
    """Format violations as human-readable text."""
    if not violations:
        return "No layer violations found."

    lines = [f"Found {len(violations)} layer violation(s):", ""]

    for v in violations:
        path = v.file_path
        if root_dir:
            try:
                path = v.file_path.relative_to(root_dir)
            except ValueError:
                pass

        lines.extend([
            f"  {path}:{v.line_number}",
            f"    Import: {v.import_module}",
            f"    From: {v.from_package} ({v.from_layer})",
            f"    To: {v.to_package} ({v.to_layer})",
            f"    Reason: {v.reason}",
            "",
            "    Fix: Move shared code to a lower layer, or add an explicit allow rule.",
            ""
        ])

    return "\n".join(lines)


def format_json(violations: list[Violation]) -> str:
    """Format violations as JSON."""
    import json
    return json.dumps({
        "violations": [v.to_dict() for v in violations],
        "count": len(violations)
    }, indent=2)
```

### cli.py

```python
import argparse
import sys

def main(args: list[str] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Check layer boundaries")
    subparsers = parser.add_subparsers(dest='command')

    check_parser = subparsers.add_parser('check', help='Check for violations')
    check_parser.add_argument('--config', '-c', type=Path, default=Path('layers.yaml'))
    check_parser.add_argument('--root', '-r', type=Path, default=Path('.'))
    check_parser.add_argument('--include-tests', action='store_true')
    check_parser.add_argument('--format', '-f', choices=['text', 'json'], default='text')

    parsed = parser.parse_args(args)

    if parsed.command == 'check':
        return run_check(parsed)

    parser.print_help()
    return 2


def run_check(args) -> int:
    """Run layer check command."""
    try:
        config = load_config(args.config.resolve())
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2

    violations = check_layers(
        args.root.resolve(),
        config,
        include_tests=args.include_tests
    )

    if args.format == 'json':
        print(format_json(violations))
    else:
        print(format_text(violations, args.root.resolve()))

    return 1 if violations else 0
```

## Test Cases (64 tests)

### Config Tests (16 tests)
1. `test_load_valid_config` - Loads valid YAML
2. `test_load_missing_file_raises` - ConfigError for missing
3. `test_load_invalid_yaml_raises` - ConfigError for malformed
4. `test_parse_layers` - Parses layers with levels
5. `test_parse_ignore_paths` - Parses ignore patterns
6. `test_parse_allowed_imports` - Parses allowlist
7. `test_parse_default_rule` - Parses rules section
8. `test_missing_layer_name_raises` - Validates name required
9. `test_layers_not_list_raises` - Validates layers is list
10. `test_get_layer_for_package` - Finds correct layer
11. `test_get_layer_for_unknown_package` - Returns None
12. `test_is_import_allowed_same_layer` - Same layer allowed
13. `test_is_import_allowed_lower_layer` - Downward allowed
14. `test_is_import_not_allowed_higher_layer` - Upward blocked
15. `test_is_import_allowed_unknown` - Unknown allowed
16. `test_explicit_allowlist` - Allowlist overrides

### Scanner Tests (13 tests)
1. `test_scan_import_statement` - Detects `import x`
2. `test_scan_from_import` - Detects `from x import y`
3. `test_scan_captures_line_numbers` - Correct line numbers
4. `test_scan_captures_file_path` - Correct file paths
5. `test_scan_empty_file` - Handles empty files
6. `test_scan_syntax_error_file` - Graceful on errors
7. `test_scan_missing_file` - Returns empty list
8. `test_scan_fixture_directory` - Scans all files
9. `test_scan_with_ignore_pattern` - Respects patterns
10. `test_simple_glob` - Pattern matching
11. `test_double_star_middle` - `**/tests/**` pattern
12. `test_double_star_start` - Patterns starting with **
13. `test_no_match` - Non-matching paths

### Resolver Tests (9 tests)
1. `test_resolve_local_package` - Resolves local modules
2. `test_resolve_submodule` - Resolves deep paths
3. `test_resolve_stdlib` - Returns None for stdlib
4. `test_resolve_unknown` - Returns None for unknown
5. `test_is_stdlib` - Identifies stdlib correctly
6. `test_is_third_party` - Identifies third-party
7. `test_get_source_package` - Package from file path
8. `test_get_source_package_test_file` - Works for tests
9. `test_get_source_package_outside` - Returns None

### Checker Tests (8 tests)
1. `test_detects_upward_import` - Detects violations
2. `test_allows_downward_import` - Allows legal imports
3. `test_allows_same_layer_import` - Same layer OK
4. `test_ignores_tests_by_default` - Tests excluded
5. `test_includes_tests_when_requested` - Tests included
6. `test_ignores_stdlib` - Stdlib not flagged
7. `test_ignores_third_party` - Third-party not flagged
8. `test_empty_directory` - Handles empty

### Report Tests (8 tests)
1. `test_violation_to_dict` - Converts to dict
2. `test_format_empty_violations` - Formats empty
3. `test_format_single_violation` - Formats one
4. `test_format_multiple_violations` - Formats many
5. `test_format_with_root_dir` - Relative paths
6. `test_format_json_empty` - JSON format empty
7. `test_format_json_single` - JSON format one
8. `test_json_is_valid` - Valid JSON output

### CLI Tests (10 tests)
1. `test_no_command_shows_help` - Help on no args
2. `test_check_with_violations` - Returns 1
3. `test_check_no_violations` - Returns 0
4. `test_check_missing_config` - Returns 2
5. `test_check_json_format` - JSON output
6. `test_check_text_format` - Text output
7. `test_check_include_tests` - Include tests flag
8. `test_text_format_readable` - Human-readable
9. `test_json_format_parseable` - Valid JSON
10. `test_custom_root_path` - Custom root works

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    'load_config',
    'check_layers',
    'Violation',
    'ConfigError',
]

def __getattr__(name):
    if name == 'load_config':
        from .config import load_config
        return load_config
    if name == 'check_layers':
        from .checker import check_layers
        return check_layers
    if name == 'Violation':
        from .checker import Violation
        return Violation
    if name == 'ConfigError':
        from .config import ConfigError
        return ConfigError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Layer Hierarchy**: Lower level (0) is foundational, higher depends on lower
2. **Same or Lower Rule**: Can only import from same level or lower
3. **AST Parsing**: Static analysis without code execution
4. **Glob Patterns**: Ignore tests and migrations by default
5. **Explicit Allowlist**: Override layer rules for specific pairs

## Usage Examples

```bash
# Basic usage
django-layers check --config layers.yaml --root /path/to/monorepo

# Include tests in check
django-layers check --include-tests

# JSON output for CI
django-layers check --format json
```

```python
from django_layers import load_config, check_layers

config = load_config(Path("layers.yaml"))
violations = check_layers(Path("."), config)

for v in violations:
    print(f"{v.file_path}:{v.line_number}: {v.reason}")
```

## Acceptance Criteria

- [ ] Layer dataclass with name, packages, level
- [ ] LayersConfig with validation methods
- [ ] AST-based import scanning
- [ ] Module-to-package resolution
- [ ] Layer boundary checking
- [ ] Text and JSON report formats
- [ ] CLI with check command
- [ ] All 64 tests passing
- [ ] README with usage examples
