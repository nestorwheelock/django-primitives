"""Dive plan validation algorithms.

Implements recreational dive planning safety rules:
- MOD (Maximum Operating Depth) for nitrox mixes at PO2 1.4
- NDL (No-Decompression Limit) from PADI RDP tables
- Certification depth limits
- Safety stop requirements
- Ascent rate validation

These algorithms ensure dive templates represent safe, executable plans.
"""

from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ExcursionTypeDive


# =============================================================================
# Dive Planning Constants
# =============================================================================

# Maximum Operating Depth (MOD) at PO2 1.4 (recreational limit)
# Formula: MOD = (PO2 / FO2 - 1) * 10 meters
# At PO2 1.4:
#   Air (21%): MOD = (1.4/0.21 - 1) * 10 = 56.7m (not practically limited)
#   EAN32: MOD = (1.4/0.32 - 1) * 10 = 33.75m ≈ 34m
#   EAN36: MOD = (1.4/0.36 - 1) * 10 = 28.9m ≈ 29m
MOD_LIMITS = {
    "air": None,  # No practical MOD limit for recreational depths
    "ean32": 34,  # meters at PO2 1.4
    "ean36": 29,  # meters at PO2 1.4
    "trimix": None,  # Varies by mix, requires advanced calculation
}

# No-Decompression Limits (NDL) from PADI Recreational Dive Planner
# Conservative single-dive limits (in minutes) for air/nitrox planned on air
# Depths in meters, times in minutes
PADI_NDL_TABLE = {
    10: 219,  # Essentially unlimited for practical purposes
    12: 147,
    14: 98,
    16: 72,
    18: 56,
    20: 45,
    22: 37,
    24: 29,
    25: 26,
    27: 22,  # Interpolated
    28: 20,
    30: 16,
    32: 13,
    34: 11,
    35: 10,
    38: 9,
    40: 8,
    42: 7,  # Technical diving territory
}

# Certification depth limits (meters)
# These are general guidelines - actual limits vary by agency and specialty
CERT_DEPTH_LIMITS = {
    "ow": 18,       # Open Water Diver
    "aow": 30,      # Advanced Open Water
    "rescue": 30,   # Rescue Diver
    "dm": 40,       # Divemaster
    "deep": 40,     # Deep Diver Specialty
    "eanx": 40,     # Enriched Air (limited by MOD)
}

# Maximum safe ascent rate (meters per minute)
MAX_ASCENT_RATE = 9  # 9 m/min = 30 ft/min (PADI standard)

# Depth threshold for requiring safety stop (meters)
SAFETY_STOP_DEPTH_THRESHOLD = 10


# =============================================================================
# Validation Result
# =============================================================================


@dataclass
class ValidationResult:
    """Result of dive plan validation.

    Attributes:
        is_valid: True if no errors (warnings are OK)
        errors: Critical issues that make the plan unsafe
        warnings: Issues that should be reviewed but aren't critical
        info: Informational messages about the plan
    """
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error and mark as invalid."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning (doesn't affect validity)."""
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        """Add an info message."""
        self.info.append(message)


# =============================================================================
# Dive Plan Validator
# =============================================================================


class DivePlanValidator:
    """Validates dive templates against safe diving rules.

    Usage:
        validator = DivePlanValidator(template)
        result = validator.validate()
        if not result.is_valid:
            for error in result.errors:
                print(f"ERROR: {error}")
    """

    def __init__(self, template: "ExcursionTypeDive"):
        self.template = template
        self.result = ValidationResult()

    def validate(self) -> ValidationResult:
        """Run all validation checks and return result."""
        self._validate_mod()

        # NDL validation
        if self.template.route_segments:
            # Multi-level profiles require Subsurface for proper validation
            self._note_subsurface_validation_pending()
        else:
            # Square profile - use PADI RDP tables
            self._validate_ndl()

        self._validate_certification_depth()
        self._validate_safety_stop()
        self._validate_ascent_rate()
        self._add_plan_info()

        return self.result

    def _validate_mod(self) -> None:
        """Validate Maximum Operating Depth for gas mix.

        If route_segments exist, checks MOD at the maximum depth in the profile.
        Otherwise uses planned_depth_meters.
        """
        gas = self.template.gas or "air"

        # Get max depth from segments if available, otherwise use planned_depth
        if self.template.route_segments:
            from .dive_profile import DiveProfileCalculator
            calc = DiveProfileCalculator(self.template.route_segments, gas)
            depth = calc.max_depth()
        else:
            depth = self.template.planned_depth_meters

        if not depth:
            return

        mod_limit = MOD_LIMITS.get(gas)

        if mod_limit is not None and depth > mod_limit:
            self.result.add_error(
                f"MOD exceeded: {gas.upper()} has maximum operating depth of "
                f"{mod_limit}m at PO2 1.4, but planned depth is {depth}m"
            )
        elif mod_limit is not None and depth > (mod_limit - 3):
            # Warn if within 3m of MOD
            self.result.add_warning(
                f"Approaching MOD: {gas.upper()} MOD is {mod_limit}m, "
                f"planned depth {depth}m leaves only {mod_limit - depth}m margin"
            )

    def _validate_ndl(self) -> None:
        """Validate No-Decompression Limit for depth/time."""
        depth = self.template.planned_depth_meters
        duration = self.template.planned_duration_minutes

        if not depth or not duration:
            return

        # Find NDL for this depth (interpolate if needed)
        ndl = self._get_ndl_for_depth(depth)

        if ndl is None:
            self.result.add_warning(
                f"Cannot determine NDL for {depth}m - verify with dive tables"
            )
            return

        if duration > ndl:
            self.result.add_error(
                f"NDL exceeded: {depth}m has no-deco limit of {ndl} minutes, "
                f"but planned duration is {duration} minutes"
            )
        elif duration >= ndl - 5:
            # Warn if within 5 minutes of NDL
            self.result.add_warning(
                f"Approaching NDL: {ndl} minutes at {depth}m, "
                f"planned {duration} minutes leaves only {ndl - duration} min margin"
            )

    def _note_subsurface_validation_pending(self) -> None:
        """Note that multi-level NDL validation requires Subsurface.

        Multi-level dive profiles require proper decompression algorithms
        (Bühlmann ZHL-16C) which are provided by Subsurface running headless.
        """
        from .dive_profile import DiveProfileCalculator

        segments = self.template.route_segments
        if not segments:
            return

        calc = DiveProfileCalculator(segments, self.template.gas or "air")

        self.result.add_info(
            f"Multi-level profile: {calc.total_time()}min total, "
            f"max depth {calc.max_depth()}m - NDL validation requires Subsurface"
        )

    def _get_ndl_for_depth(self, depth: int) -> int | None:
        """Get NDL for a given depth, interpolating if needed."""
        if depth < 10:
            return 999  # Essentially unlimited

        if depth > 42:
            return None  # Beyond recreational limits

        # Direct lookup
        if depth in PADI_NDL_TABLE:
            return PADI_NDL_TABLE[depth]

        # Interpolate between closest values
        depths = sorted(PADI_NDL_TABLE.keys())
        for i, d in enumerate(depths):
            if d > depth:
                lower_depth = depths[i - 1]
                upper_depth = d
                lower_ndl = PADI_NDL_TABLE[lower_depth]
                upper_ndl = PADI_NDL_TABLE[upper_depth]

                # Linear interpolation (conservative - rounds down)
                ratio = (depth - lower_depth) / (upper_depth - lower_depth)
                ndl = lower_ndl - int(ratio * (lower_ndl - upper_ndl))
                return ndl

        return PADI_NDL_TABLE[depths[-1]]

    def _validate_certification_depth(self) -> None:
        """Validate depth against certification limits."""
        depth = self.template.planned_depth_meters
        cert_level = self.template.min_certification_level

        if not depth:
            return

        if cert_level is None:
            if depth > 18:
                self.result.add_warning(
                    f"No certification level specified for {depth}m dive - "
                    "consider specifying required certification"
                )
            return

        # Check against certification's max_depth_m if set
        if cert_level.max_depth_m and depth > cert_level.max_depth_m:
            self.result.add_error(
                f"Depth exceeds certification limit: {cert_level.name} is limited to "
                f"{cert_level.max_depth_m}m, but planned depth is {depth}m"
            )
        # Fallback to standard limits by code
        elif cert_level.code in CERT_DEPTH_LIMITS:
            limit = CERT_DEPTH_LIMITS[cert_level.code]
            if depth > limit:
                self.result.add_error(
                    f"Depth exceeds certification limit: {cert_level.name} is typically "
                    f"limited to {limit}m, but planned depth is {depth}m"
                )

    def _validate_safety_stop(self) -> None:
        """Validate that safety stop is planned for deeper dives."""
        depth = self.template.planned_depth_meters
        route = self.template.route or ""

        if not depth or depth <= SAFETY_STOP_DEPTH_THRESHOLD:
            return  # Shallow dive, safety stop not required

        # Check if route mentions safety stop
        safety_patterns = [
            r"safety stop",
            r"safety-stop",
            r"stop at (5|15|6|20)\s*(m|ft|'|feet|meters)",
            r"(3|5)\s*min(utes?)?\s*(at|@)\s*(5|15|6|20)",
        ]

        route_lower = route.lower()
        has_safety_stop = any(
            re.search(pattern, route_lower) for pattern in safety_patterns
        )

        if not has_safety_stop:
            self.result.add_warning(
                f"Safety stop recommended: Dive to {depth}m should include "
                "3-5 minute safety stop at 5-6m (15-20ft)"
            )

    def _validate_ascent_rate(self) -> None:
        """Validate ascent rate if timing information available in route."""
        route = self.template.route or ""

        if not route:
            self.result.add_info(
                "No route specified - ensure ascent rate does not exceed "
                f"{MAX_ASCENT_RATE}m/min (30ft/min)"
            )
            return

        # Try to extract ascent timing from route
        # Look for patterns like "ascend to 15m (2 min)" or "30' per minute"
        ascent_pattern = r"ascen[dt]\s+.*?(\d+)\s*(m|ft|'|feet|meters?).*?\((\d+)\s*min"

        matches = re.findall(ascent_pattern, route.lower())

        if not matches:
            self.result.add_info(
                "Ascent timing not clearly specified in route - verify ascent rate "
                f"does not exceed {MAX_ASCENT_RATE}m/min"
            )

    def _add_plan_info(self) -> None:
        """Add informational messages about the plan."""
        gas = self.template.gas or "air"
        depth = self.template.planned_depth_meters
        duration = self.template.planned_duration_minutes

        if depth and gas != "air":
            mod = MOD_LIMITS.get(gas)
            if mod:
                self.result.add_info(
                    f"Gas: {gas.upper()} (MOD {mod}m at PO2 1.4)"
                )

        if depth and duration:
            ndl = self._get_ndl_for_depth(depth)
            if ndl:
                margin = ndl - duration
                self.result.add_info(
                    f"NDL margin: {margin} minutes remaining at {depth}m"
                )


# =============================================================================
# Convenience Function
# =============================================================================


def validate_dive_template(template: "ExcursionTypeDive") -> ValidationResult:
    """Validate a dive template against safe diving rules.

    Convenience function that creates a validator and runs all checks.

    Args:
        template: ExcursionTypeDive to validate

    Returns:
        ValidationResult with errors, warnings, and info messages
    """
    validator = DivePlanValidator(template)
    return validator.validate()
