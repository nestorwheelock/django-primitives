"""Dive profile utilities for Subsurface integration.

This module provides utilities for working with dive profiles.
Actual decompression validation is delegated to Subsurface running
headless on the server, which implements proper Bühlmann ZHL-16C.

The route_segments JSONField stores structured dive profiles that can
be exported to Subsurface for validation.
"""

from dataclasses import dataclass


@dataclass
class DiveProfileCalculator:
    """Basic dive profile metrics calculator.

    For actual NDL/decompression validation, use Subsurface integration.
    This class only provides simple metrics like total time and max depth.

    Segment schema:
        {
            "phase": "descent|bottom|ascent|safety_stop",
            "depth_m": 26,       # depth in meters
            "duration_min": 5,   # time at this depth
            "description": "..."  # optional
        }
    """

    segments: list[dict]
    gas: str = "air"

    def total_time(self) -> int:
        """Return total dive time across all segments."""
        return sum(s.get("duration_min", 0) for s in self.segments)

    def max_depth(self) -> int:
        """Return maximum depth reached in any segment."""
        if not self.segments:
            return 0
        return max(s.get("depth_m", 0) for s in self.segments)


# =============================================================================
# Subsurface Integration (TODO)
# =============================================================================
#
# Subsurface can run headless and validate dive plans using proper
# Bühlmann ZHL-16C decompression algorithms.
#
# Integration approach:
# 1. Export route_segments to Subsurface XML format
# 2. Run subsurface --cloud-timeout=0 --import <file>
# 3. Parse validation results
#
# See: https://subsurface-divelog.org/
# =============================================================================
