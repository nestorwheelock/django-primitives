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


CHECKS = [
    ("Dependency Boundaries", "check_dependencies.py"),
    ("BaseModel Usage", "check_basemodel.py"),
]


def run_check(name: str, script: str) -> bool:
    """Run a single check script."""
    script_path = Path(__file__).parent / script

    print(f"{'=' * 60}")
    print(f"Running: {name}")
    print(f"{'=' * 60}")
    print()

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=False
    )

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
    for name, script in CHECKS:
        passed = run_check(name, script)
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
