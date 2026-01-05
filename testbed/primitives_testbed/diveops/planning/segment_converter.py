"""Segment conversion for decompression validation.

Converts route_segments from dive templates into flat depth/time steps
for the Bühlmann ZHL-16C validator.
"""


def segments_to_steps(
    route_segments: list[dict], slice_min: int = 3, slice_max: int = 10
) -> list[dict]:
    """Convert route_segments to flat (depth_m, duration_min) steps.

    Drops final surface segment (ends at 0m) per locked decision #2.
    We compute ceiling BEFORE surfacing, not after.

    Args:
        route_segments: List of segment dicts with phase, depth, duration
        slice_min: Minimum slices for ramp segments
        slice_max: Maximum slices for ramp segments

    Returns:
        List of {depth_m: float, duration_min: float} dicts
    """
    # Filter out final surface segment
    filtered = _drop_surface_segment(route_segments)

    steps = []
    for seg in filtered:
        phase = seg.get("phase", "level")
        dur = float(seg.get("duration_min", 0))
        if dur <= 0:
            continue

        if phase in ("level", "safety_stop"):
            steps.append({"depth_m": float(seg["depth_m"]), "duration_min": dur})
        elif phase in ("descent", "ascent"):
            steps.extend(_slice_ramp(seg, slice_min, slice_max))

    return steps


def _drop_surface_segment(segments: list[dict]) -> list[dict]:
    """Drop final segment if it ends at surface (0m).

    We compute ceiling BEFORE surfacing, not after.
    """
    if not segments:
        return segments

    last = segments[-1]
    # Check if last segment ends at surface
    if last.get("to_depth_m") == 0 or last.get("depth_m") == 0:
        return segments[:-1]
    return segments


def _slice_ramp(seg: dict, slice_min: int, slice_max: int) -> list[dict]:
    """Slice a ramp segment into interpolated steps for tissue math.

    Ramps (descent/ascent) need to be broken into discrete depth steps
    because decompression models track tissue loading at each depth.

    Args:
        seg: Segment with from_depth_m, to_depth_m, duration_min
        slice_min: Minimum number of slices
        slice_max: Maximum number of slices

    Returns:
        List of constant-depth steps interpolated along the ramp
    """
    from_d = float(seg.get("from_depth_m", 0))
    to_d = float(seg.get("to_depth_m", 0))
    dur = float(seg.get("duration_min", 0))

    if dur <= 0:
        return []

    # Number of slices based on duration, clamped to min/max
    slices = max(slice_min, min(slice_max, int(dur)))
    dt = dur / slices

    steps = []
    for i in range(slices):
        # Use endpoint depth of each slice interval
        frac = (i + 1) / slices
        depth = from_d + (to_d - from_d) * frac
        steps.append({"depth_m": depth, "duration_min": dt})

    return steps


def build_validator_input(
    *,
    route_segments: list[dict],
    gas_o2: float,
    gas_he: float = 0.0,
    gf_low: float = 0.40,
    gf_high: float = 0.85,
) -> dict:
    """Build input for deco validator binary.

    Note: input_hash is computed by Rust binary, not here (locked decision #3).

    Args:
        route_segments: List of segment dicts from dive template
        gas_o2: Oxygen fraction (0.0-1.0)
        gas_he: Helium fraction (0.0-1.0)
        gf_low: Gradient factor low (0.0-1.0)
        gf_high: Gradient factor high (0.0-1.0)

    Returns:
        Dict ready to serialize and send to validator binary
    """
    return {
        "segments": segments_to_steps(route_segments),
        "gas": {"o2": gas_o2, "he": gas_he},
        "gf_low": gf_low,
        "gf_high": gf_high,
    }
