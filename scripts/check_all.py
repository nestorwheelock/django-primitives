#!/usr/bin/env python3
"""
Run all boundary and contract checks.

Exit codes:
- 0: All checks pass
- 1: One or more checks failed
"""

import subprocess
import sys
from pathlib import Path


# Check definitions: (name, command_type, command)
# command_type: "script" for local Python scripts, "module" for Python modules
CHECKS = [
    ("Layer Boundaries", "module", "django_layers.cli"),
    ("BaseModel Usage", "script", "check_basemodel.py"),
]


def run_check(name: str, cmd_type: str, cmd: str) -> bool:
    """Run a single check."""
    root = Path(__file__).parent.parent

    print(f"{'=' * 60}")
    print(f"Running: {name}")
    print(f"{'=' * 60}")
    print()

    if cmd_type == "script":
        script_path = Path(__file__).parent / cmd
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=False
        )
    elif cmd_type == "module":
        # Run django-layers check
        env = {
            **subprocess.os.environ,
            "PYTHONPATH": str(root / "packages" / "django-layers" / "src"),
        }
        result = subprocess.run(
            [
                sys.executable, "-m", cmd, "check",
                "--config", str(root / "layers.yaml"),
                "--root", str(root / "packages"),
                "--format", "text",
            ],
            capture_output=False,
            env=env,
        )
    else:
        print(f"Unknown command type: {cmd_type}")
        return False

    print()
    return result.returncode == 0


def main():
    """Main entry point."""
    print()
    print("=" * 60)
    print("  DJANGO-PRIMITIVES BOUNDARY CHECKS")
    print("=" * 60)
    print()

    results = []
    for name, cmd_type, cmd in CHECKS:
        passed = run_check(name, cmd_type, cmd)
        results.append((name, passed))

    # Summary
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print()

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All checks passed!")
        return 0
    else:
        print("Some checks failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
