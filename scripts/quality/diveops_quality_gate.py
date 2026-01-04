#!/usr/bin/env python3
"""
DiveOps Quality Gate - Comprehensive code quality checks for the diveops app.

Checks:
1. Tests: pytest execution and pass rate
2. Coverage: Line coverage percentage
3. Static: Linting violations (ruff)
4. Security: Forbidden patterns + SAST (bandit)
5. Maintainability: Complexity metrics (radon)
6. Concurrency: Required test patterns exist

Usage:
    python scripts/quality/diveops_quality_gate.py              # Full run
    python scripts/quality/diveops_quality_gate.py --gate tests # Single gate
    python scripts/quality/diveops_quality_gate.py --json       # JSON output only

Exit codes:
    0 - All gates pass
    1 - One or more gates fail
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class GateResult:
    """Result of a single quality gate."""
    name: str
    passed: bool
    score: float  # 0-100
    weight: int
    details: dict[str, Any] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        return self.score * (self.weight / 100)


@dataclass
class QualityScorecard:
    """Overall quality scorecard."""
    timestamp: str
    commit_sha: str
    branch: str
    gates: list[GateResult]
    overall_score: float
    overall_passed: bool

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "overall_score": round(self.overall_score, 2),
            "overall_passed": self.overall_passed,
            "gates": [
                {
                    "name": g.name,
                    "passed": g.passed,
                    "score": round(g.score, 2),
                    "weight": g.weight,
                    "weighted_score": round(g.weighted_score, 2),
                    "details": g.details,
                    "violations": g.violations[:10],  # Limit violations in output
                    "violation_count": len(g.violations),
                }
                for g in self.gates
            ],
        }


class DiveOpsQualityGate:
    """Quality gate runner for DiveOps app."""

    def __init__(self, root: Path, config_path: Path | None = None):
        self.root = root
        self.testbed = root / "testbed"
        self.config = self._load_config(config_path)
        self.gates: list[GateResult] = []

    def _load_config(self, config_path: Path | None) -> dict:
        """Load configuration from TOML file."""
        if config_path is None:
            config_path = self.root / "scripts" / "quality" / "diveops_quality.toml"

        if not config_path.exists():
            # Return defaults if config doesn't exist
            return {
                "thresholds": {"coverage_percent": 95, "max_complexity": 10},
                "gates": {
                    "tests": 30, "coverage": 25, "static": 15,
                    "security": 15, "maintainability": 10, "concurrency": 5
                },
                "paths": {
                    "source": "primitives_testbed/diveops",
                    "tests": "tests/test_diveops"
                },
            }

        with open(config_path, "rb") as f:
            return tomllib.load(f)

    def _run_command(self, cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.testbed,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)

    def _get_git_info(self) -> tuple[str, str]:
        """Get current commit SHA and branch."""
        sha = os.environ.get("GITHUB_SHA", "")
        branch = os.environ.get("GITHUB_REF_NAME", "")

        if not sha:
            code, stdout, _ = self._run_command(["git", "rev-parse", "HEAD"], self.root)
            sha = stdout.strip()[:8] if code == 0 else "unknown"

        if not branch:
            code, stdout, _ = self._run_command(["git", "branch", "--show-current"], self.root)
            branch = stdout.strip() if code == 0 else "unknown"

        return sha, branch

    # =========================================================================
    # Gate: Tests
    # =========================================================================
    def run_tests_gate(self) -> GateResult:
        """Run pytest and check pass rate."""
        weight = self.config["gates"].get("tests", 30)
        test_path = self.config["paths"].get("tests", "tests/test_diveops")

        cmd = [
            "pytest", test_path,
            "-v", "--tb=short",
            "--junit-xml=test-results.xml",
            "-q"
        ]

        code, stdout, stderr = self._run_command(cmd)

        # Parse test results
        passed = failed = errors = 0
        for line in (stdout + stderr).splitlines():
            if "passed" in line or "failed" in line or "error" in line:
                match = re.search(r"(\d+) passed", line)
                if match:
                    passed = int(match.group(1))
                match = re.search(r"(\d+) failed", line)
                if match:
                    failed = int(match.group(1))
                match = re.search(r"(\d+) error", line)
                if match:
                    errors = int(match.group(1))

        total = passed + failed + errors
        pass_rate = (passed / total * 100) if total > 0 else 0

        violations = []
        if failed > 0:
            violations.append(f"{failed} test(s) failed")
        if errors > 0:
            violations.append(f"{errors} test(s) errored")

        return GateResult(
            name="tests",
            passed=code == 0 and failed == 0 and errors == 0,
            score=pass_rate,
            weight=weight,
            details={"passed": passed, "failed": failed, "errors": errors, "total": total},
            violations=violations,
        )

    # =========================================================================
    # Gate: Coverage
    # =========================================================================
    def run_coverage_gate(self) -> GateResult:
        """Run coverage and check percentage."""
        weight = self.config["gates"].get("coverage", 25)
        threshold = self.config["thresholds"].get("coverage_percent", 95)
        source_path = self.config["paths"].get("source", "primitives_testbed/diveops")
        test_path = self.config["paths"].get("tests", "tests/test_diveops")

        cmd = [
            "pytest", test_path,
            f"--cov={source_path}",
            "--cov-report=term-missing",
            "--cov-report=json:coverage.json",
            "-q"
        ]

        code, stdout, stderr = self._run_command(cmd)

        # Parse coverage from JSON if available
        coverage_json = self.testbed / "coverage.json"
        coverage_pct = 0.0
        uncovered_lines = 0

        if coverage_json.exists():
            try:
                with open(coverage_json) as f:
                    cov_data = json.load(f)
                coverage_pct = cov_data.get("totals", {}).get("percent_covered", 0)
                uncovered_lines = cov_data.get("totals", {}).get("missing_lines", 0)
            except (json.JSONDecodeError, KeyError):
                pass
        else:
            # Fallback: parse from stdout
            for line in stdout.splitlines():
                if "TOTAL" in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith("%"):
                            try:
                                coverage_pct = float(part.rstrip("%"))
                            except ValueError:
                                pass

        violations = []
        if coverage_pct < threshold:
            violations.append(f"Coverage {coverage_pct:.1f}% below threshold {threshold}%")

        # Score: 100 if >= threshold, scaled down otherwise
        score = min(100, (coverage_pct / threshold) * 100) if threshold > 0 else 100

        return GateResult(
            name="coverage",
            passed=coverage_pct >= threshold,
            score=score,
            weight=weight,
            details={
                "coverage_percent": round(coverage_pct, 2),
                "threshold": threshold,
                "uncovered_lines": uncovered_lines,
            },
            violations=violations,
        )

    # =========================================================================
    # Gate: Static Analysis (Ruff)
    # =========================================================================
    def run_static_gate(self) -> GateResult:
        """Run ruff linter on source code."""
        weight = self.config["gates"].get("static", 15)
        source_path = self.testbed / self.config["paths"].get("source", "primitives_testbed/diveops")

        # Check if ruff is available
        code, _, _ = self._run_command(["ruff", "--version"])
        if code != 0:
            return GateResult(
                name="static",
                passed=True,
                score=100,
                weight=weight,
                details={"skipped": True, "reason": "ruff not installed"},
                violations=["ruff not installed - install with: pip install ruff"],
            )

        cmd = ["ruff", "check", str(source_path), "--output-format=json"]
        code, stdout, _ = self._run_command(cmd, self.root)

        violations = []
        error_count = 0
        warning_count = 0

        try:
            issues = json.loads(stdout) if stdout.strip() else []
            for issue in issues:
                if issue.get("code", "").startswith("E"):
                    error_count += 1
                else:
                    warning_count += 1
                loc = f"{issue.get('filename', '?')}:{issue.get('location', {}).get('row', '?')}"
                violations.append(f"{issue.get('code', '?')}: {issue.get('message', '?')} at {loc}")
        except json.JSONDecodeError:
            pass

        total_issues = error_count + warning_count
        # Score: 100 if no issues, decreases with issues
        score = max(0, 100 - (error_count * 10) - (warning_count * 2))

        return GateResult(
            name="static",
            passed=error_count == 0,
            score=score,
            weight=weight,
            details={"errors": error_count, "warnings": warning_count, "total": total_issues},
            violations=violations,
        )

    # =========================================================================
    # Gate: Security (Bandit + Pattern Checks)
    # =========================================================================
    def run_security_gate(self) -> GateResult:
        """Run security checks: bandit SAST + forbidden pattern grep."""
        weight = self.config["gates"].get("security", 15)
        source_path = self.testbed / self.config["paths"].get("source", "primitives_testbed/diveops")

        violations = []
        high_severity = 0
        medium_severity = 0

        # Run bandit if available
        code, _, _ = self._run_command(["bandit", "--version"])
        if code == 0:
            cmd = ["bandit", "-r", str(source_path), "-f", "json", "-ll"]
            code, stdout, _ = self._run_command(cmd, self.root)

            try:
                bandit_result = json.loads(stdout) if stdout.strip() else {}
                for issue in bandit_result.get("results", []):
                    sev = issue.get("issue_severity", "").upper()
                    if sev == "HIGH":
                        high_severity += 1
                    elif sev == "MEDIUM":
                        medium_severity += 1
                    violations.append(
                        f"[{sev}] {issue.get('issue_text', '?')} at "
                        f"{issue.get('filename', '?')}:{issue.get('line_number', '?')}"
                    )
            except json.JSONDecodeError:
                pass

        # Check forbidden patterns
        forbidden = self.config.get("security", {}).get("forbidden_patterns", {})
        for name, pattern in forbidden.items():
            for py_file in source_path.rglob("*.py"):
                if "migrations" in str(py_file) or "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text()
                    matches = re.findall(pattern, content)
                    if matches:
                        high_severity += len(matches)
                        violations.append(f"Forbidden pattern '{name}' in {py_file.name}")
                except Exception:
                    pass

        # Score based on severity
        score = max(0, 100 - (high_severity * 25) - (medium_severity * 10))

        return GateResult(
            name="security",
            passed=high_severity == 0,
            score=score,
            weight=weight,
            details={"high_severity": high_severity, "medium_severity": medium_severity},
            violations=violations,
        )

    # =========================================================================
    # Gate: Maintainability (Radon Complexity)
    # =========================================================================
    def run_maintainability_gate(self) -> GateResult:
        """Run complexity analysis with radon."""
        weight = self.config["gates"].get("maintainability", 10)
        max_complexity = self.config["thresholds"].get("max_complexity", 10)
        source_path = self.testbed / self.config["paths"].get("source", "primitives_testbed/diveops")

        # Check if radon is available
        code, _, _ = self._run_command(["radon", "--version"])
        if code != 0:
            return GateResult(
                name="maintainability",
                passed=True,
                score=100,
                weight=weight,
                details={"skipped": True, "reason": "radon not installed"},
                violations=["radon not installed - install with: pip install radon"],
            )

        cmd = ["radon", "cc", str(source_path), "-j", "-s"]
        code, stdout, _ = self._run_command(cmd, self.root)

        violations = []
        high_complexity_count = 0
        total_functions = 0
        max_found = 0

        try:
            cc_data = json.loads(stdout) if stdout.strip() else {}
            for filepath, functions in cc_data.items():
                for func in functions:
                    total_functions += 1
                    complexity = func.get("complexity", 0)
                    max_found = max(max_found, complexity)
                    if complexity > max_complexity:
                        high_complexity_count += 1
                        violations.append(
                            f"{func.get('name', '?')} has complexity {complexity} "
                            f"(max: {max_complexity}) in {Path(filepath).name}"
                        )
        except json.JSONDecodeError:
            pass

        # Score: penalize for high complexity functions
        if total_functions > 0:
            good_ratio = (total_functions - high_complexity_count) / total_functions
            score = good_ratio * 100
        else:
            score = 100

        return GateResult(
            name="maintainability",
            passed=high_complexity_count == 0,
            score=score,
            weight=weight,
            details={
                "max_complexity_found": max_found,
                "threshold": max_complexity,
                "high_complexity_functions": high_complexity_count,
                "total_functions": total_functions,
            },
            violations=violations,
        )

    # =========================================================================
    # Gate: Concurrency Robustness
    # =========================================================================
    def run_concurrency_gate(self) -> GateResult:
        """Check that required concurrency tests exist."""
        weight = self.config["gates"].get("concurrency", 5)
        test_path = self.testbed / self.config["paths"].get("tests", "tests/test_diveops")
        source_path = self.testbed / self.config["paths"].get("source", "primitives_testbed/diveops")

        violations = []
        required_patterns = self.config.get("concurrency", {}).get("required_tests", {})

        # Gather all test function names
        test_functions = []
        for py_file in test_path.rglob("test_*.py"):
            try:
                content = py_file.read_text()
                test_functions.extend(re.findall(r"def (test_\w+)", content))
            except Exception:
                pass

        # Check required patterns exist
        patterns_found = 0
        patterns_required = len(required_patterns)

        for name, pattern in required_patterns.items():
            found = False
            for func in test_functions:
                if re.search(pattern, func, re.IGNORECASE):
                    found = True
                    break
            if found:
                patterns_found += 1
            else:
                violations.append(f"Missing concurrency test pattern: {name} ({pattern})")

        # Check that services use select_for_update where needed
        services_file = source_path / "services.py"
        if services_file.exists():
            content = services_file.read_text()

            # Check required patterns in services
            required_service = self.config.get("security", {}).get("required_patterns", {})

            if "select_for_update" in required_service:
                if "select_for_update" not in content:
                    violations.append("services.py missing select_for_update() for locking")

            if "atomic_decorator" in required_service:
                if "transaction.atomic" not in content and "@transaction.atomic" not in content:
                    violations.append("services.py missing transaction.atomic for atomicity")

        # Score based on pattern coverage
        if patterns_required > 0:
            score = (patterns_found / patterns_required) * 100
        else:
            score = 100 if not violations else 50

        return GateResult(
            name="concurrency",
            passed=len(violations) == 0,
            score=score,
            weight=weight,
            details={
                "patterns_found": patterns_found,
                "patterns_required": patterns_required,
                "test_functions_scanned": len(test_functions),
            },
            violations=violations,
        )

    # =========================================================================
    # Run All Gates
    # =========================================================================
    def run_all_gates(self, single_gate: str | None = None) -> QualityScorecard:
        """Run all quality gates and produce scorecard."""
        sha, branch = self._get_git_info()

        gate_runners = {
            "tests": self.run_tests_gate,
            "coverage": self.run_coverage_gate,
            "static": self.run_static_gate,
            "security": self.run_security_gate,
            "maintainability": self.run_maintainability_gate,
            "concurrency": self.run_concurrency_gate,
        }

        if single_gate:
            if single_gate not in gate_runners:
                print(f"Unknown gate: {single_gate}")
                print(f"Available: {', '.join(gate_runners.keys())}")
                sys.exit(1)
            self.gates = [gate_runners[single_gate]()]
        else:
            self.gates = [runner() for runner in gate_runners.values()]

        overall_score = sum(g.weighted_score for g in self.gates)
        overall_passed = all(g.passed for g in self.gates)

        return QualityScorecard(
            timestamp=datetime.now(timezone.utc).isoformat(),
            commit_sha=sha,
            branch=branch,
            gates=self.gates,
            overall_score=overall_score,
            overall_passed=overall_passed,
        )

    def print_report(self, scorecard: QualityScorecard) -> None:
        """Print human-readable report."""
        print("=" * 70)
        if scorecard.overall_passed:
            print("DIVEOPS QUALITY GATE: PASSED")
        else:
            print("DIVEOPS QUALITY GATE: FAILED")
        print("=" * 70)
        print(f"Commit: {scorecard.commit_sha} on {scorecard.branch}")
        print(f"Time: {scorecard.timestamp}")
        print(f"Overall Score: {scorecard.overall_score:.1f}/100")
        print()

        # Gate summary table
        print(f"{'Gate':<20} {'Status':<8} {'Score':<10} {'Weight':<8} {'Weighted':<10}")
        print("-" * 70)

        for gate in scorecard.gates:
            status = "PASS" if gate.passed else "FAIL"
            print(
                f"{gate.name:<20} {status:<8} {gate.score:>6.1f}    "
                f"{gate.weight:>5}%   {gate.weighted_score:>7.1f}"
            )

        print("-" * 70)
        print(f"{'TOTAL':<20} {'':<8} {'':<10} {'100%':<8} {scorecard.overall_score:>7.1f}")
        print()

        # Violations
        failed_gates = [g for g in scorecard.gates if not g.passed]
        if failed_gates:
            print("VIOLATIONS:")
            print("-" * 70)
            for gate in failed_gates:
                print(f"\n{gate.name.upper()}:")
                for v in gate.violations[:5]:
                    print(f"  - {v}")
                if len(gate.violations) > 5:
                    print(f"  ... and {len(gate.violations) - 5} more")

        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="DiveOps Quality Gate")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--gate", help="Run single gate: tests, coverage, static, security, maintainability, concurrency")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument("--output", help="Write scorecard JSON to file")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config_path = Path(args.config) if args.config else None

    gate = DiveOpsQualityGate(root, config_path)
    scorecard = gate.run_all_gates(args.gate)

    # Output
    if args.json:
        print(json.dumps(scorecard.to_dict(), indent=2))
    else:
        gate.print_report(scorecard)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(scorecard.to_dict(), f, indent=2)
        if not args.json:
            print(f"Scorecard written to: {args.output}")

    return 0 if scorecard.overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
