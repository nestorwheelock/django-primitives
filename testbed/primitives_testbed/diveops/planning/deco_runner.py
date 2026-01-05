"""Decompression validator binary runner.

Executes the Rust diveops-deco-validate binary via subprocess
and returns parsed JSON results.
"""

import json
import logging
import subprocess

from django.conf import settings

logger = logging.getLogger(__name__)


def run_deco_validator(input_data: dict) -> dict:
    """Run deco validator binary, return normalized result.

    Args:
        input_data: Dict with segments, gas, gf_low, gf_high

    Returns:
        Dict with validation results including:
        - tool, tool_version, model
        - ceiling_m, tts_min, ndl_min, deco_required
        - stops (list of depth_m/duration_min dicts)
        - input_hash
        - error (if validation failed)
    """
    validator_path = getattr(
        settings, "DECO_VALIDATOR_PATH", "/usr/local/bin/diveops-deco-validate"
    )
    timeout = getattr(settings, "DECO_VALIDATOR_TIMEOUT", 10)

    try:
        result = subprocess.run(
            [validator_path],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.error(f"Validator binary not found: {validator_path}")
        return {"error": "validator_not_found", "tool": "diveops-deco-validate"}
    except subprocess.TimeoutExpired:
        logger.error(f"Validator timed out after {timeout}s")
        return {"error": "timeout", "tool": "diveops-deco-validate"}
    except Exception as e:
        logger.exception(f"Validator execution failed: {e}")
        return {"error": "execution_failed", "tool": "diveops-deco-validate"}

    if result.returncode != 0:
        logger.error(f"Validator failed (exit {result.returncode}): {result.stderr}")
        return {
            "error": "validator_failed",
            "tool": "diveops-deco-validate",
            "stderr": result.stderr[:500] if result.stderr else None,
            "returncode": result.returncode,
        }

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from validator: {e}")
        return {
            "error": "invalid_json",
            "tool": "diveops-deco-validate",
            "stdout": result.stdout[:500] if result.stdout else None,
        }
