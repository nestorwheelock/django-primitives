#!/usr/bin/env python3
"""
Tier 1 comprehensive audit orchestrator.

Runs all audit scripts and produces a combined report.

Usage:
  python scripts/audit_tier1.py --root .
  python scripts/audit_tier1.py --root . --json out/tier1_audit.json
  python scripts/audit_tier1.py --root . --output-dir out/
  python scripts/audit_tier1.py --root . --fail-fast
  python scripts/audit_tier1.py --root . --package django-parties
  python scripts/audit_tier1.py --root . --package django-parties --package django-rbac
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_audit(
    script: str,
    root: Path,
    json_path: Path,
    extra_args: list[str] = None
) -> tuple[int, str, str]:
    """Run an audit script and capture output."""
    cmd = [
        sys.executable,
        str(root / "scripts" / script),
        "--root", str(root),
        "--json", str(json_path)
    ]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=root
    )

    return result.returncode, result.stdout, result.stderr


def main() -> int:
    ap = argparse.ArgumentParser(description="Tier 1 comprehensive audit")
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--json", default=None, help="Write combined JSON report")
    ap.add_argument("--output-dir", default="out", help="Output directory for individual reports")
    ap.add_argument("--skip-packages", action="append", default=[], help="Packages to skip")
    ap.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first audit failure instead of running all"
    )
    ap.add_argument(
        "--package",
        action="append",
        dest="packages",
        default=[],
        help="Only audit specific package(s). Can be repeated."
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("TIER 1 COMPREHENSIVE AUDIT")
    print(f"Root: {root}")
    print(f"Time: {datetime.now().isoformat()}")
    if args.packages:
        print(f"Packages: {', '.join(args.packages)}")
    if args.fail_fast:
        print("Mode: fail-fast")
    print("=" * 70)

    results = {}
    total_exit = 0

    # Build package filter args for sub-scripts that support it
    # Note: Not all scripts support --package yet, so we pass it where possible

    # Run model audit
    print("\n" + "=" * 70)
    print("1. MODEL AUDIT (BaseModel compliance)")
    print("=" * 70)

    skip_args = []
    for p in ["django-basemodels"] + args.skip_packages:
        skip_args.extend(["--skip-package", p])

    model_exit, model_stdout, model_stderr = run_audit(
        "audit_models.py",
        root,
        out_dir / "models.json",
        extra_args=skip_args
    )
    print(model_stdout)
    if model_stderr:
        print(model_stderr, file=sys.stderr)

    results["models"] = {
        "exit_code": model_exit,
        "report_path": str(out_dir / "models.json")
    }
    total_exit |= model_exit

    if args.fail_fast and model_exit != 0:
        print("\n❌ FAIL-FAST: Model audit failed, stopping.")
        return _write_report_and_exit(args, root, out_dir, results, total_exit)

    # Run dependency audit
    print("\n" + "=" * 70)
    print("2. DEPENDENCY AUDIT (versions, cycles, tiers)")
    print("=" * 70)

    deps_exit, deps_stdout, deps_stderr = run_audit(
        "audit_deps.py",
        root,
        out_dir / "deps.json"
    )
    print(deps_stdout)
    if deps_stderr:
        print(deps_stderr, file=sys.stderr)

    results["deps"] = {
        "exit_code": deps_exit,
        "report_path": str(out_dir / "deps.json")
    }
    total_exit |= deps_exit

    if args.fail_fast and deps_exit != 0:
        print("\n❌ FAIL-FAST: Dependency audit failed, stopping.")
        return _write_report_and_exit(args, root, out_dir, results, total_exit)

    # Run migration audit
    print("\n" + "=" * 70)
    print("3. MIGRATION AUDIT (UUIDs, dependencies)")
    print("=" * 70)

    mig_exit, mig_stdout, mig_stderr = run_audit(
        "audit_migrations.py",
        root,
        out_dir / "migrations.json"
    )
    print(mig_stdout)
    if mig_stderr:
        print(mig_stderr, file=sys.stderr)

    results["migrations"] = {
        "exit_code": mig_exit,
        "report_path": str(out_dir / "migrations.json")
    }
    total_exit |= mig_exit

    if args.fail_fast and mig_exit != 0:
        print("\n❌ FAIL-FAST: Migration audit failed, stopping.")
        return _write_report_and_exit(args, root, out_dir, results, total_exit)

    return _write_report_and_exit(args, root, out_dir, results, total_exit)


def _write_report_and_exit(args, root: Path, out_dir: Path, results: dict, total_exit: int) -> int:
    """Print summary, write JSON report, and return exit code."""
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for audit_name, audit_result in results.items():
        status = "✅ PASS" if audit_result["exit_code"] == 0 else "❌ FAIL"
        print(f"{audit_name:<15} {status}")

    # Check for audits that didn't run (fail-fast)
    all_audits = ["models", "deps", "migrations"]
    skipped = [a for a in all_audits if a not in results]
    if skipped:
        for audit_name in skipped:
            print(f"{audit_name:<15} ⏭️  SKIPPED")

    overall = "✅ ALL AUDITS PASSED" if total_exit == 0 else "❌ SOME AUDITS FAILED"
    print(f"\n{overall}")

    # Combined JSON report
    if args.json:
        combined = {
            "timestamp": datetime.now().isoformat(),
            "root": str(root),
            "fail_fast": args.fail_fast,
            "packages_filter": args.packages if args.packages else None,
            "audits": results,
            "overall_exit_code": total_exit,
        }

        # Load individual reports if they exist
        for audit_name in results:
            report_path = Path(results[audit_name]["report_path"])
            if report_path.exists():
                combined[f"{audit_name}_detail"] = json.loads(report_path.read_text())

        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(combined, indent=2))
        print(f"\nWrote combined report to {json_path}")

    print(f"\nIndividual reports in: {out_dir}/")
    for audit_name in results:
        print(f"  - {audit_name}.json")

    return total_exit


if __name__ == "__main__":
    sys.exit(main())
