"""Dive planning utilities.

This module provides:
- segment_converter: Convert route_segments to deco validator input
- deco_runner: Execute Rust validator binary
"""

from .segment_converter import build_validator_input, segments_to_steps
from .deco_runner import run_deco_validator

__all__ = ["build_validator_input", "segments_to_steps", "run_deco_validator"]
