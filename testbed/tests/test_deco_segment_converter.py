"""Tests for dive planning segment converter.

Tests the conversion of route_segments to validator input format,
including ramp slicing and surface segment dropping.
"""

import pytest

from primitives_testbed.diveops.planning.segment_converter import (
    _drop_surface_segment,
    _slice_ramp,
    build_validator_input,
    segments_to_steps,
)


class TestDropSurfaceSegment:
    """Tests for _drop_surface_segment()."""

    def test_empty_list(self):
        """Empty list returns empty."""
        assert _drop_surface_segment([]) == []

    def test_single_level_segment_kept(self):
        """Level segment not at surface is kept."""
        segments = [{"phase": "level", "depth_m": 20, "duration_min": 10}]
        assert _drop_surface_segment(segments) == segments

    def test_drops_final_ascent_to_zero(self):
        """Final ascent ending at 0m is dropped."""
        segments = [
            {"phase": "level", "depth_m": 20, "duration_min": 10},
            {"phase": "ascent", "from_depth_m": 5, "to_depth_m": 0, "duration_min": 1},
        ]
        result = _drop_surface_segment(segments)
        assert len(result) == 1
        assert result[0]["phase"] == "level"

    def test_drops_surface_level_segment(self):
        """Level segment at depth_m=0 is dropped if last."""
        segments = [
            {"phase": "level", "depth_m": 20, "duration_min": 10},
            {"phase": "level", "depth_m": 0, "duration_min": 1},
        ]
        result = _drop_surface_segment(segments)
        assert len(result) == 1

    def test_keeps_non_surface_last_segment(self):
        """Last segment not at surface is kept."""
        segments = [
            {"phase": "descent", "from_depth_m": 0, "to_depth_m": 20, "duration_min": 2},
            {"phase": "level", "depth_m": 20, "duration_min": 10},
            {"phase": "safety_stop", "depth_m": 5, "duration_min": 3},
        ]
        result = _drop_surface_segment(segments)
        assert len(result) == 3


class TestSliceRamp:
    """Tests for _slice_ramp()."""

    def test_descent_slicing(self):
        """Descent is sliced into interpolated steps."""
        seg = {"phase": "descent", "from_depth_m": 0, "to_depth_m": 30, "duration_min": 3}
        steps = _slice_ramp(seg, slice_min=3, slice_max=10)
        assert len(steps) == 3
        # Each step should be 1 min duration
        for step in steps:
            assert step["duration_min"] == 1.0
        # Depths should interpolate: 10, 20, 30
        assert steps[0]["depth_m"] == 10.0
        assert steps[1]["depth_m"] == 20.0
        assert steps[2]["depth_m"] == 30.0

    def test_ascent_slicing(self):
        """Ascent is sliced correctly."""
        seg = {"phase": "ascent", "from_depth_m": 20, "to_depth_m": 5, "duration_min": 3}
        steps = _slice_ramp(seg, slice_min=3, slice_max=10)
        assert len(steps) == 3
        # Depths should interpolate: 15, 10, 5
        assert steps[0]["depth_m"] == 15.0
        assert steps[1]["depth_m"] == 10.0
        assert steps[2]["depth_m"] == 5.0

    def test_respects_slice_min(self):
        """Short duration still gets minimum slices."""
        seg = {"phase": "descent", "from_depth_m": 0, "to_depth_m": 10, "duration_min": 1}
        steps = _slice_ramp(seg, slice_min=3, slice_max=10)
        assert len(steps) == 3  # min slices even for short duration

    def test_respects_slice_max(self):
        """Long duration is capped at max slices."""
        seg = {"phase": "descent", "from_depth_m": 0, "to_depth_m": 30, "duration_min": 15}
        steps = _slice_ramp(seg, slice_min=3, slice_max=10)
        assert len(steps) == 10  # max slices

    def test_zero_duration_returns_empty(self):
        """Zero duration returns empty list."""
        seg = {"phase": "descent", "from_depth_m": 0, "to_depth_m": 30, "duration_min": 0}
        steps = _slice_ramp(seg, slice_min=3, slice_max=10)
        assert steps == []


class TestSegmentsToSteps:
    """Tests for segments_to_steps()."""

    def test_level_segment(self):
        """Level segment becomes single step."""
        segments = [{"phase": "level", "depth_m": 25, "duration_min": 10}]
        steps = segments_to_steps(segments)
        assert len(steps) == 1
        assert steps[0] == {"depth_m": 25.0, "duration_min": 10.0}

    def test_safety_stop_segment(self):
        """Safety stop is treated like level segment."""
        segments = [{"phase": "safety_stop", "depth_m": 5, "duration_min": 3}]
        steps = segments_to_steps(segments)
        assert len(steps) == 1
        assert steps[0] == {"depth_m": 5.0, "duration_min": 3.0}

    def test_multi_level_profile(self):
        """Full multi-level dive profile converts correctly."""
        segments = [
            {"phase": "descent", "from_depth_m": 0, "to_depth_m": 26, "duration_min": 3},
            {"phase": "level", "depth_m": 26, "duration_min": 5},
            {"phase": "level", "depth_m": 23, "duration_min": 8},
            {"phase": "safety_stop", "depth_m": 5, "duration_min": 3},
            {"phase": "ascent", "from_depth_m": 5, "to_depth_m": 0, "duration_min": 1},
        ]
        steps = segments_to_steps(segments)

        # Final ascent to 0 should be dropped
        # Descent (3 slices) + level (1) + level (1) + safety (1) = 6 steps
        assert len(steps) == 6

        # Check level segments are preserved
        level_steps = [s for s in steps if s["depth_m"] in [26.0, 23.0, 5.0]]
        assert any(s["depth_m"] == 26.0 and s["duration_min"] == 5.0 for s in steps)
        assert any(s["depth_m"] == 23.0 and s["duration_min"] == 8.0 for s in steps)
        assert any(s["depth_m"] == 5.0 and s["duration_min"] == 3.0 for s in steps)

    def test_skips_zero_duration(self):
        """Zero duration segments are skipped."""
        segments = [
            {"phase": "level", "depth_m": 20, "duration_min": 10},
            {"phase": "level", "depth_m": 15, "duration_min": 0},  # skipped
        ]
        steps = segments_to_steps(segments)
        assert len(steps) == 1

    def test_empty_segments(self):
        """Empty segments return empty steps."""
        assert segments_to_steps([]) == []


class TestBuildValidatorInput:
    """Tests for build_validator_input()."""

    def test_basic_input(self):
        """Basic input structure is correct."""
        segments = [{"phase": "level", "depth_m": 20, "duration_min": 10}]
        result = build_validator_input(
            route_segments=segments,
            gas_o2=0.32,
            gas_he=0.0,
            gf_low=0.40,
            gf_high=0.85,
        )

        assert result["gas"] == {"o2": 0.32, "he": 0.0}
        assert result["gf_low"] == 0.40
        assert result["gf_high"] == 0.85
        assert len(result["segments"]) == 1

    def test_trimix_gas(self):
        """Trimix gas fractions are preserved."""
        segments = [{"phase": "level", "depth_m": 50, "duration_min": 15}]
        result = build_validator_input(
            route_segments=segments,
            gas_o2=0.18,
            gas_he=0.35,
        )
        assert result["gas"] == {"o2": 0.18, "he": 0.35}

    def test_default_gf_values(self):
        """Default gradient factors are applied."""
        segments = [{"phase": "level", "depth_m": 20, "duration_min": 10}]
        result = build_validator_input(route_segments=segments, gas_o2=0.21)
        assert result["gf_low"] == 0.40
        assert result["gf_high"] == 0.85

    def test_custom_gf_values(self):
        """Custom gradient factors are used."""
        segments = [{"phase": "level", "depth_m": 20, "duration_min": 10}]
        result = build_validator_input(
            route_segments=segments,
            gas_o2=0.21,
            gf_low=0.30,
            gf_high=0.70,
        )
        assert result["gf_low"] == 0.30
        assert result["gf_high"] == 0.70

    def test_no_input_hash_in_python(self):
        """Input hash is NOT computed by Python (Rust computes it)."""
        segments = [{"phase": "level", "depth_m": 20, "duration_min": 10}]
        result = build_validator_input(route_segments=segments, gas_o2=0.21)
        assert "input_hash" not in result
