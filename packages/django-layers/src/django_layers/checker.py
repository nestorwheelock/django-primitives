"""Main checker logic for layer boundary enforcement."""

from pathlib import Path

from django_layers.config import LayersConfig
from django_layers.report import Violation
from django_layers.resolver import PackageResolver
from django_layers.scanner import scan_directory


def check_layers(
    root_dir: Path,
    config: LayersConfig,
    include_tests: bool = False,
) -> list[Violation]:
    """Check all Python files for layer violations.

    Args:
        root_dir: Root directory of the monorepo
        config: Parsed layers configuration
        include_tests: Whether to check test files

    Returns:
        List of violations found
    """
    violations: list[Violation] = []

    # Build ignore patterns
    ignore_patterns = list(config.ignore_paths)
    if not include_tests:
        # Add default test ignores if not including tests
        if "**/tests/**" not in ignore_patterns:
            ignore_patterns.append("**/tests/**")
        if "**/test_*.py" not in ignore_patterns:
            ignore_patterns.append("**/test_*.py")

    # Create resolver
    resolver = PackageResolver(root_dir)

    # Scan for imports
    packages_dir = root_dir / "packages"
    if not packages_dir.exists():
        return violations

    imports = scan_directory(packages_dir, ignore_patterns)

    # Check each import
    for imp in imports:
        # Determine source package
        from_package = resolver.get_source_package(imp.file_path)
        if not from_package:
            continue

        # Resolve imported module to package
        to_package = resolver.resolve(imp.module)
        if not to_package:
            # Not a local package (stdlib or third-party)
            continue

        # Skip self-imports
        if from_package == to_package:
            continue

        # Check if import is allowed
        allowed, reason = config.is_import_allowed(from_package, to_package)

        if not allowed:
            from_layer = config.get_layer_for_package(from_package)
            to_layer = config.get_layer_for_package(to_package)

            violations.append(
                Violation(
                    file_path=imp.file_path,
                    line_number=imp.line_number,
                    import_module=imp.module,
                    from_package=from_package,
                    to_package=to_package,
                    from_layer=from_layer.name if from_layer else "unknown",
                    to_layer=to_layer.name if to_layer else "unknown",
                    reason=reason,
                )
            )

    return violations
