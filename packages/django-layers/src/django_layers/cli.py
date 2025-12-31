"""Command-line interface for django-layers."""

import argparse
import sys
from pathlib import Path

from django_layers.checker import check_layers
from django_layers.config import ConfigError, load_config
from django_layers.report import format_json, format_text


def main(args: list[str] | None = None) -> int:
    """Main entry point for django-layers CLI.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, 1 for violations, 2 for errors)
    """
    parser = argparse.ArgumentParser(
        prog="django-layers",
        description="Check import boundaries in a Django monorepo",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check for layer violations")
    check_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=Path("layers.yaml"),
        help="Path to layers.yaml config file (default: layers.yaml)",
    )
    check_parser.add_argument(
        "--root",
        "-r",
        type=Path,
        default=Path.cwd(),
        help="Root directory of the monorepo (default: current directory)",
    )
    check_parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in the check",
    )
    check_parser.add_argument(
        "--exclude-tests",
        action="store_true",
        help="Exclude test files from the check (default)",
    )
    check_parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return 2

    if parsed.command == "check":
        return run_check(parsed)

    return 2


def run_check(args: argparse.Namespace) -> int:
    """Run the layer check.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code
    """
    config_path = args.config
    root_dir = args.root.resolve()
    include_tests = args.include_tests and not args.exclude_tests
    output_format = args.format

    # Load config
    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    # Run check
    violations = check_layers(root_dir, config, include_tests=include_tests)

    # Output results
    if output_format == "json":
        print(format_json(violations))
    else:
        print(format_text(violations, root_dir))

    # Return exit code
    if violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
