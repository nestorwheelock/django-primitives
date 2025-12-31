"""Resolve import modules to package names."""

import sys
from pathlib import Path


# Known standard library modules (subset - enough for common cases)
STDLIB_MODULES = {
    "abc", "argparse", "ast", "asyncio", "base64", "collections", "contextlib",
    "copy", "csv", "dataclasses", "datetime", "decimal", "enum", "fnmatch",
    "functools", "glob", "hashlib", "html", "http", "importlib", "inspect",
    "io", "itertools", "json", "logging", "math", "os", "pathlib", "pickle",
    "pprint", "queue", "random", "re", "shutil", "signal", "socket", "sqlite3",
    "string", "subprocess", "sys", "tempfile", "textwrap", "threading", "time",
    "traceback", "types", "typing", "unittest", "urllib", "uuid", "warnings",
    "xml", "zipfile",
    # Built-in modules
    "builtins", "_thread", "errno", "gc", "marshal", "posix", "pwd", "grp",
}


class PackageResolver:
    """Resolves import module names to package names."""

    def __init__(
        self,
        packages_dir: Path,
        package_layout: str = "packages/{pkg}/src/{module}/",
    ):
        """Initialize resolver.

        Args:
            packages_dir: Root directory containing packages
            package_layout: Layout pattern for packages
        """
        self.packages_dir = packages_dir
        self.package_layout = package_layout
        self._module_to_package: dict[str, str] = {}
        self._build_module_map()

    def _build_module_map(self) -> None:
        """Build mapping from module names to package names."""
        packages_path = self.packages_dir / "packages"
        if not packages_path.exists():
            return

        for pkg_dir in packages_path.iterdir():
            if not pkg_dir.is_dir():
                continue

            pkg_name = pkg_dir.name
            src_dir = pkg_dir / "src"

            if not src_dir.exists():
                continue

            # Find Python modules in src/
            for module_dir in src_dir.iterdir():
                if module_dir.is_dir() and (module_dir / "__init__.py").exists():
                    module_name = module_dir.name
                    self._module_to_package[module_name] = pkg_name

    def resolve(self, import_module: str) -> str | None:
        """Resolve an import module to its owning package.

        Args:
            import_module: Module name from import statement (e.g., 'django_catalog.models')

        Returns:
            Package name (e.g., 'django-catalog') or None if not a local package
        """
        # Get the top-level module
        top_module = import_module.split(".")[0]

        # Check if it's stdlib
        if self.is_stdlib(top_module):
            return None

        # Check if it's a known local package
        if top_module in self._module_to_package:
            return self._module_to_package[top_module]

        # Not a local package (third-party or unknown)
        return None

    def is_stdlib(self, module: str) -> bool:
        """Check if a module is from the standard library."""
        if module in STDLIB_MODULES:
            return True

        # Check if it's a submodule of stdlib
        top = module.split(".")[0]
        return top in STDLIB_MODULES

    def is_third_party(self, module: str) -> bool:
        """Check if a module is third-party (not stdlib, not local)."""
        if self.is_stdlib(module):
            return False

        top_module = module.split(".")[0]
        return top_module not in self._module_to_package

    def get_source_package(self, file_path: Path) -> str | None:
        """Determine which package a source file belongs to.

        Args:
            file_path: Path to a Python source file

        Returns:
            Package name or None
        """
        # Normalize path
        try:
            rel_path = file_path.relative_to(self.packages_dir)
        except ValueError:
            return None

        parts = rel_path.parts

        # Expected: packages/<pkg>/src/<module>/...
        if len(parts) >= 2 and parts[0] == "packages":
            return parts[1]

        return None
