#!/usr/bin/env python3
"""
Tier 1 comprehensive audit orchestrator.

Runs all audit scripts and produces a combined report.

Usage:
  python scripts/audit_tier1.py --root .
  python scripts/audit_tier1.py --root . --json out/tier1_audit.json
  python scripts/audit_tier1.py --root . --output-dir out/
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_audit(script: str, root: Path, json_path: Path) -> tuple[int, str]:
    """Run an audit script and capture output."""
    cmd = [
        sys.executable,
        str(root / "scripts" / script),
        "--root", str(root),
        "--json", str(json_path)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=root
    )

    output = result.stdout + result.stderr
    return result.returncode, output


def main() -> int:
    ap = argparse.ArgumentParser(description="Tier 1 comprehensive audit")
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--json", default=None, help="Write combined JSON report")
    ap.add_argument("--output-dir", default="out", help="Output directory for individual reports")
    ap.add_argument("--skip-packages", action="append", default=[], help="Packages to skip")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("TIER 1 COMPREHENSIVE AUDIT")
    print(f"Root: {root}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)

    results = {}
    total_exit = 0

    # Run model audit
    print("\n" + "=" * 70)
    print("1. MODEL AUDIT (BaseModel compliance)")
    print("=" * 70)

    skip_args = " ".join(f"--skip-package {p}" for p in ["django-basemodels"] + args.skip_packages)
    model_cmd = f"{sys.executable} {root}/scripts/audit_models.py --root {root} --json {out_dir}/models.json {skip_args}"

    model_result = subprocess.run(
        model_cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=root
    )
    print(model_result.stdout)
    if model_result.stderr:
        print(model_result.stderr, file=sys.stderr)
    results["models"] = {
        "exit_code": model_result.returncode,
        "report_path": str(out_dir / "models.json")
    }
    total_exit |= model_result.returncode

    # Run dependency audit
    print("\n" + "=" * 70)
    print("2. DEPENDENCY AUDIT (versions, cycles, tiers)")
    print("=" * 70)

    deps_result = subprocess.run(
        [sys.executable, str(root / "scripts" / "audit_deps.py"),
         "--root", str(root),
         "--json", str(out_dir / "deps.json")],
        capture_output=True,
        text=True,
        cwd=root
    )
    print(deps_result.stdout)
    if deps_result.stderr:
        print(deps_result.stderr, file=sys.stderr)
    results["deps"] = {
        "exit_code": deps_result.returncode,
        "report_path": str(out_dir / "deps.json")
    }
    total_exit |= deps_result.returncode

    # Run migration audit
    print("\n" + "=" * 70)
    print("3. MIGRATION AUDIT (UUIDs, dependencies)")
    print("=" * 70)

    mig_result = subprocess.run(
        [sys.executable, str(root / "scripts" / "audit_migrations.py"),
         "--root", str(root),
         "--json", str(out_dir / "migrations.json")],
        capture_output=True,
        text=True,
        cwd=root
    )
    print(mig_result.stdout)
    if mig_result.stderr:
        print(mig_result.stderr, file=sys.stderr)
    results["migrations"] = {
        "exit_code": mig_result.returncode,
        "report_path": str(out_dir / "migrations.json")
    }
    total_exit |= mig_result.returncode

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for audit_name, audit_result in results.items():
        status = "✅ PASS" if audit_result["exit_code"] == 0 else "❌ FAIL"
        print(f"{audit_name:<15} {status}")

    overall = "✅ ALL AUDITS PASSED" if total_exit == 0 else "❌ SOME AUDITS FAILED"
    print(f"\n{overall}")

    # Combined JSON report
    if args.json:
        combined = {
            "timestamp": datetime.now().isoformat(),
            "root": str(root),
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
    print("  - models.json")
    print("  - deps.json")
    print("  - migrations.json")

    return total_exit


if __name__ == "__main__":
    sys.exit(main())
