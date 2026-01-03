# Architecture: django-layers

**Status:** Stable / v0.1.0

Import boundary enforcement for monorepo package architecture.

---

## What This Package Is For

Answering the question: **"Is this import allowed by our architecture?"**

Use cases:
- Enforcing layer boundaries in monorepos
- Preventing circular dependencies between packages
- CI/CD validation of import rules
- Documenting package tier hierarchy
- Catching architecture violations early

---

## What This Package Is NOT For

- **Not a Django app** - This is a CLI tool, no models or migrations
- **Not runtime enforcement** - Checks at build/CI time, not runtime
- **Not a linter** - Doesn't check code style, only import structure
- **Not dependency management** - Use pip/poetry for package dependencies

---

## Design Principles

1. **Configuration-driven** - Rules defined in YAML, not code
2. **Hierarchical tiers** - Lower tiers cannot import from higher tiers
3. **Explicit allowlist** - Override rules when needed
4. **CI-friendly** - Exit codes and machine-readable output
5. **Fast scanning** - AST-based, no execution required

---

## Configuration Model

```yaml
# layers.yaml

layers:
  - name: foundation    # Level 0 (lowest)
    packages:
      - django-basemodels
      - django-singleton
      - django-modules

  - name: identity      # Level 1
    packages:
      - django-parties
      - django-rbac

  - name: domain        # Level 2
    packages:
      - django-catalog
      - django-encounters

rules:
  default: same_or_lower  # Can import same level or lower

ignore:
  paths:
    - "**/tests/**"
    - "**/migrations/**"

allow:                    # Explicit exceptions
  imports:
    - from: django-catalog
      to: django-rbac     # Override for specific case
```

---

## Architecture Rules

```
Layer Level  │  Can Import From
─────────────┼──────────────────────────────────
   0         │  None (no dependencies)
   1         │  Level 0 only
   2         │  Level 0, 1
   N         │  Levels 0 through N

Violation Example:
  Level 0 (foundation) imports Level 2 (domain)
  → VIOLATION: lower tier importing higher tier
```

---

## Public API

### CLI Usage

```bash
# Check all packages
django-layers check --config layers.yaml --root .

# Include test files
django-layers check --config layers.yaml --root . --include-tests

# Output formats
django-layers check --config layers.yaml --root . --format json
django-layers check --config layers.yaml --root . --format text

# Exit codes
# 0: No violations
# 1: Violations found
# 2: Configuration error
```

### Programmatic Usage

```python
from pathlib import Path
from django_layers.config import load_config
from django_layers.checker import check_layers

# Load configuration
config = load_config(Path("layers.yaml"))

# Run check
violations = check_layers(
    root_dir=Path("."),
    config=config,
    include_tests=False,
)

# Process results
for v in violations:
    print(f"{v.file_path}:{v.line_number}")
    print(f"  {v.from_package} -> {v.to_package}")
    print(f"  {v.reason}")
```

---

## Components

| Component | Purpose |
|-----------|---------|
| `config.py` | Parse and validate layers.yaml |
| `scanner.py` | Scan Python files for imports |
| `resolver.py` | Map import paths to packages |
| `checker.py` | Apply rules and detect violations |
| `report.py` | Format and output results |
| `cli.py` | Command-line interface |

---

## Hard Rules

1. **Lower cannot import higher** - Tier 0 cannot import Tier 1+
2. **Same-tier allowed** - Packages in same tier can import each other
3. **Unknown packages ignored** - Third-party imports are not checked
4. **Self-imports ignored** - Package can always import itself

---

## Invariants

- Layer level is determined by position in `layers` list (first = 0)
- Package appears in exactly one layer (no duplicates)
- Violations include both file path and line number
- Configuration errors prevent any checking (fail fast)

---

## Known Gotchas

### 1. Package Name Resolution

**Problem:** Import paths don't match package names.

```python
# Package name: django-catalog
# Import path: from django_catalog import ...

# The tool understands this mapping via directory scanning
```

### 2. Relative Imports

**Problem:** Relative imports within a package.

```python
# In django_catalog/services.py
from .models import CatalogItem  # Same package, always allowed
from ..other import Something    # Parent package, depends on rules
```

**Solution:** Relative imports within same package are always allowed.

### 3. Test File Defaults

**Problem:** Tests often import across layers for fixtures.

```yaml
# Default behavior ignores test paths
ignore:
  paths:
    - "**/tests/**"
    - "**/migrations/**"
```

**Solution:** Use `--include-tests` only when specifically validating tests.

### 4. Circular Layer Detection

**Problem:** Package A imports B, B imports A (different layers).

```
django-catalog (tier 2) imports django-rbac (tier 1)
django-rbac (tier 1) imports django-catalog (tier 2)  # VIOLATION
```

**Solution:** Both imports are checked independently. Second is a violation.

---

## Recommended Usage

### 1. Add to CI Pipeline

```yaml
# .github/workflows/check.yaml
- name: Check layer boundaries
  run: |
    pip install django-layers
    django-layers check --config layers.yaml --root .
```

### 2. Document Layer Purpose

```yaml
layers:
  # Tier 0: Foundation - No dependencies on other primitives
  - name: foundation
    packages:
      - django-basemodels

  # Tier 1: Identity - Depends on Foundation only
  - name: identity
    packages:
      - django-parties
```

### 3. Use Allowlist Sparingly

```yaml
allow:
  imports:
    # Document WHY this exception exists
    - from: django-catalog
      to: django-rbac
      # Reason: Catalog needs role checking for commit authorization
```

---

## Dependencies

- Python >= 3.11
- PyYAML

Note: This is a standalone CLI tool, not a Django app.

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- YAML configuration loading
- AST-based import scanning
- Layer violation detection
- CLI with JSON/text output
- Ignore patterns support
