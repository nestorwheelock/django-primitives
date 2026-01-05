"""Tests for dive plan validation.

Tests DivePlanValidator which enforces safe dive planning rules:
- MOD (Maximum Operating Depth) for nitrox mixes
- NDL (No-Decompression Limit) from PADI RDP tables
- Certification depth limits
- Safety stop requirements
- Ascent rate validation
"""

import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model

from primitives_testbed.diveops.models import (
    CertificationLevel,
    ExcursionType,
    ExcursionTypeDive,
)
from primitives_testbed.diveops.validators import (
    DivePlanValidator,
    ValidationResult,
    validate_dive_template,
)

from django_parties.models import Organization


User = get_user_model()


@pytest.fixture
def padi(db):
    """Create PADI certification agency."""
    return Organization.objects.create(
        name="PADI",
        org_type="certification_agency",
    )


@pytest.fixture
def open_water(db, padi):
    """Create Open Water certification (18m limit)."""
    return CertificationLevel.objects.create(
        agency=padi,
        code="ow",
        name="Open Water Diver",
        rank=1,
        max_depth_m=18,
    )


@pytest.fixture
def advanced_ow(db, padi):
    """Create Advanced Open Water certification (30m limit)."""
    return CertificationLevel.objects.create(
        agency=padi,
        code="aow",
        name="Advanced Open Water",
        rank=2,
        max_depth_m=30,
    )


@pytest.fixture
def deep_diver(db, padi):
    """Create Deep Diver specialty (40m limit)."""
    return CertificationLevel.objects.create(
        agency=padi,
        code="deep",
        name="Deep Diver",
        rank=3,
        max_depth_m=40,
    )


@pytest.fixture
def excursion_type(db, open_water):
    """Create a basic excursion type."""
    return ExcursionType.objects.create(
        name="Test Dive",
        slug="test-dive",
        dive_mode="boat",
        max_depth_meters=18,
        base_price=Decimal("100.00"),
        min_certification_level=open_water,
    )


@pytest.fixture
def valid_template(db, excursion_type, open_water):
    """Create a valid dive template."""
    return ExcursionTypeDive.objects.create(
        excursion_type=excursion_type,
        sequence=1,
        name="Reef Dive",
        planned_depth_meters=18,
        planned_duration_minutes=45,
        gas="air",
        min_certification_level=open_water,
    )


# =============================================================================
# MOD (Maximum Operating Depth) Tests
# =============================================================================


@pytest.mark.django_db
class TestMODValidation:
    """Tests for Maximum Operating Depth validation."""

    def test_air_no_mod_limit(self, excursion_type):
        """Air has no practical MOD limit for recreational diving."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Deep Air Dive",
            planned_depth_meters=40,
            gas="air",
        )
        result = validate_dive_template(template)

        # Air MOD is not a concern (narcosis is, but that's separate)
        mod_errors = [e for e in result.errors if "MOD" in e]
        assert len(mod_errors) == 0

    def test_ean32_within_mod(self, excursion_type):
        """EAN32 at 33m is within MOD (PO2 1.4 limit = 34m)."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Nitrox Dive",
            planned_depth_meters=33,
            gas="ean32",
        )
        result = validate_dive_template(template)

        mod_errors = [e for e in result.errors if "MOD" in e]
        assert len(mod_errors) == 0

    def test_ean32_exceeds_mod(self, excursion_type):
        """EAN32 at 40m exceeds MOD (PO2 1.4 limit = 34m)."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Too Deep Nitrox",
            planned_depth_meters=40,
            gas="ean32",
        )
        result = validate_dive_template(template)

        assert not result.is_valid
        mod_errors = [e for e in result.errors if "MOD" in e]
        assert len(mod_errors) == 1
        assert "34m" in mod_errors[0]  # Should mention the MOD limit

    def test_ean36_mod_limit(self, excursion_type):
        """EAN36 has MOD of 29m at PO2 1.4."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="EAN36 Dive",
            planned_depth_meters=32,
            gas="ean36",
        )
        result = validate_dive_template(template)

        assert not result.is_valid
        mod_errors = [e for e in result.errors if "MOD" in e]
        assert len(mod_errors) == 1


# =============================================================================
# NDL (No-Decompression Limit) Tests
# =============================================================================


@pytest.mark.django_db
class TestNDLValidation:
    """Tests for No-Decompression Limit validation."""

    def test_within_ndl_shallow(self, excursion_type):
        """18m for 45 min is well within NDL (56 min)."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Shallow Dive",
            planned_depth_meters=18,
            planned_duration_minutes=45,
            gas="air",
        )
        result = validate_dive_template(template)

        ndl_errors = [e for e in result.errors if "NDL" in e]
        assert len(ndl_errors) == 0

    def test_exceeds_ndl(self, excursion_type):
        """30m for 25 min exceeds NDL (20 min at 30m)."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Too Long Deep",
            planned_depth_meters=30,
            planned_duration_minutes=25,
            gas="air",
        )
        result = validate_dive_template(template)

        assert not result.is_valid
        ndl_errors = [e for e in result.errors if "NDL" in e]
        assert len(ndl_errors) == 1

    def test_at_ndl_limit_warning(self, excursion_type):
        """Being at exactly NDL should produce a warning."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="At Limit",
            planned_depth_meters=24,
            planned_duration_minutes=29,  # NDL at 24m is 29 min
            gas="air",
        )
        result = validate_dive_template(template)

        # Should be valid but with warning
        assert result.is_valid
        assert len(result.warnings) > 0

    def test_ndl_at_40m(self, excursion_type):
        """40m has NDL of only 8 min."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Very Deep",
            planned_depth_meters=40,
            planned_duration_minutes=15,
            gas="air",
        )
        result = validate_dive_template(template)

        assert not result.is_valid
        ndl_errors = [e for e in result.errors if "NDL" in e]
        assert len(ndl_errors) == 1


# =============================================================================
# Certification Depth Limit Tests
# =============================================================================


@pytest.mark.django_db
class TestCertificationDepthValidation:
    """Tests for certification-based depth limits."""

    def test_within_cert_limit(self, excursion_type, open_water):
        """18m dive with OW cert (18m limit) is valid."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="OW Dive",
            planned_depth_meters=18,
            min_certification_level=open_water,
        )
        result = validate_dive_template(template)

        cert_errors = [e for e in result.errors if "certification" in e.lower()]
        assert len(cert_errors) == 0

    def test_exceeds_cert_limit(self, excursion_type, open_water):
        """25m dive with OW cert (18m limit) should fail."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Too Deep for OW",
            planned_depth_meters=25,
            min_certification_level=open_water,
        )
        result = validate_dive_template(template)

        assert not result.is_valid
        cert_errors = [e for e in result.errors if "certification" in e.lower()]
        assert len(cert_errors) == 1

    def test_aow_depth_limit(self, excursion_type, advanced_ow):
        """30m dive with AOW cert (30m limit) is valid."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="AOW Dive",
            planned_depth_meters=30,
            min_certification_level=advanced_ow,
        )
        result = validate_dive_template(template)

        cert_errors = [e for e in result.errors if "certification" in e.lower()]
        assert len(cert_errors) == 0

    def test_no_cert_specified_warning(self, excursion_type):
        """Deep dive without cert requirement should warn."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="No Cert Specified",
            planned_depth_meters=25,
            min_certification_level=None,
        )
        result = validate_dive_template(template)

        # Should warn about missing cert for deep dive
        assert len(result.warnings) > 0


# =============================================================================
# Safety Stop Tests
# =============================================================================


@pytest.mark.django_db
class TestSafetyStopValidation:
    """Tests for safety stop requirement validation."""

    def test_deep_dive_without_safety_stop_warning(self, excursion_type):
        """Dive >10m without safety stop in route should warn."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="No Safety Stop",
            planned_depth_meters=18,
            route="Descend to 18m, explore reef, ascend directly to surface",
        )
        result = validate_dive_template(template)

        safety_warnings = [w for w in result.warnings if "safety stop" in w.lower()]
        assert len(safety_warnings) > 0

    def test_deep_dive_with_safety_stop_ok(self, excursion_type):
        """Dive with safety stop mentioned in route is valid."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="With Safety Stop",
            planned_depth_meters=18,
            route="Descend to 18m, explore reef, safety stop at 5m for 3 min, ascend",
        )
        result = validate_dive_template(template)

        safety_warnings = [w for w in result.warnings if "safety stop" in w.lower()]
        assert len(safety_warnings) == 0

    def test_shallow_dive_no_safety_stop_ok(self, excursion_type):
        """Dive <=10m without safety stop is fine."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Shallow Dive",
            planned_depth_meters=8,
            route="Shore dive to 8m max",
        )
        result = validate_dive_template(template)

        safety_warnings = [w for w in result.warnings if "safety stop" in w.lower()]
        assert len(safety_warnings) == 0


# =============================================================================
# Ascent Rate Tests
# =============================================================================


@pytest.mark.django_db
class TestAscentRateValidation:
    """Tests for ascent rate validation."""

    def test_safe_ascent_rate(self, excursion_type):
        """Route with safe ascent (<=9m/min) passes."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Safe Ascent",
            planned_depth_meters=27,
            route=(
                "Descend to 27m (3 min) → explore (20 min) → "
                "ascend to 15m (2 min) → safety stop 5m (3 min) → surface (1 min)"
            ),
        )
        result = validate_dive_template(template)

        ascent_errors = [e for e in result.errors if "ascent" in e.lower()]
        assert len(ascent_errors) == 0

    def test_warns_about_unspecified_ascent(self, excursion_type):
        """Route without ascent timing should warn."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="No Ascent Info",
            planned_depth_meters=27,
            route="Descend to wreck, explore, return to surface",
        )
        result = validate_dive_template(template)

        # Should at least warn about missing ascent rate info
        assert len(result.warnings) > 0 or len(result.info) > 0


# =============================================================================
# Overall Validation Tests
# =============================================================================


@pytest.mark.django_db
class TestOverallValidation:
    """Tests for overall validation behavior."""

    def test_valid_template_passes(self, valid_template):
        """A well-constructed template should pass validation."""
        # Add safety stop to route
        valid_template.route = "Reef dive at 18m, safety stop at 5m for 3 min"
        valid_template.save()

        result = validate_dive_template(valid_template)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_multiple_errors_collected(self, excursion_type, open_water):
        """Multiple violations should all be reported."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Multiple Problems",
            planned_depth_meters=40,  # Exceeds OW cert limit
            planned_duration_minutes=30,  # Exceeds NDL at 40m
            gas="ean32",  # Exceeds MOD at 40m
            min_certification_level=open_water,
        )
        result = validate_dive_template(template)

        assert not result.is_valid
        assert len(result.errors) >= 3  # MOD, NDL, and cert errors

    def test_validation_result_structure(self, valid_template):
        """ValidationResult has expected structure."""
        result = validate_dive_template(valid_template)

        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'info')
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    def test_validator_class_interface(self, valid_template):
        """DivePlanValidator class can be used directly."""
        validator = DivePlanValidator(valid_template)
        result = validator.validate()

        assert isinstance(result, ValidationResult)


# =============================================================================
# Multi-Level Profile Tests (Subsurface Integration Pending)
# =============================================================================


@pytest.mark.django_db
class TestMultiLevelProfileValidation:
    """Tests for multi-level dive profile handling.

    Multi-level NDL validation requires Subsurface integration.
    These tests verify basic segment handling and MOD validation.
    """

    def test_multilevel_profile_notes_subsurface_pending(self, excursion_type, advanced_ow):
        """Multi-level profile should note Subsurface validation pending."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Multi-Level Wreck",
            planned_depth_meters=27,
            planned_duration_minutes=42,
            gas="ean32",
            min_certification_level=advanced_ow,
            route_segments=[
                {"phase": "descent", "depth_m": 26, "duration_min": 3},
                {"phase": "bottom", "depth_m": 26, "duration_min": 5},
                {"phase": "ascent", "depth_m": 23, "duration_min": 8},
                {"phase": "ascent", "depth_m": 20, "duration_min": 12},
                {"phase": "ascent", "depth_m": 18, "duration_min": 5},
                {"phase": "ascent", "depth_m": 14, "duration_min": 5},
                {"phase": "safety_stop", "depth_m": 5, "duration_min": 3},
                {"phase": "ascent", "depth_m": 0, "duration_min": 1},
            ],
        )
        result = validate_dive_template(template)

        # Should be valid (no NDL check for multi-level until Subsurface)
        assert result.is_valid, f"Errors: {result.errors}"
        # Should have info about Subsurface pending
        subsurface_info = [i for i in result.info if "Subsurface" in i]
        assert len(subsurface_info) >= 1

    def test_basic_profile_metrics(self, excursion_type):
        """Verify basic profile metrics (total time, max depth)."""
        from primitives_testbed.diveops.dive_profile import DiveProfileCalculator

        segments = [
            {"depth_m": 30, "duration_min": 10},
            {"depth_m": 20, "duration_min": 20},
            {"depth_m": 10, "duration_min": 10},
        ]
        calc = DiveProfileCalculator(segments)

        assert calc.total_time() == 40
        assert calc.max_depth() == 30

    def test_fallback_to_square_profile(self, excursion_type):
        """Without segments, validator uses square profile (planned_depth)."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="No Segments",
            planned_depth_meters=30,
            planned_duration_minutes=25,  # Exceeds NDL at 30m (20 min)
            gas="air",
            route_segments=[],  # Empty segments = fall back
        )
        result = validate_dive_template(template)

        # Should fail - square profile at 30m, 25 min > NDL 20 min
        assert not result.is_valid
        ndl_errors = [e for e in result.errors if "NDL" in e]
        assert len(ndl_errors) == 1

    def test_segments_validate_mod_at_max_depth(self, excursion_type):
        """MOD should be checked at maximum depth in segments."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Deep Nitrox",
            planned_depth_meters=36,
            planned_duration_minutes=20,
            gas="ean32",  # MOD 34m
            route_segments=[
                {"depth_m": 36, "duration_min": 5},  # Exceeds MOD!
                {"depth_m": 25, "duration_min": 15},
            ],
        )
        result = validate_dive_template(template)

        # Should fail - max depth 36m exceeds EAN32 MOD of 34m
        assert not result.is_valid
        mod_errors = [e for e in result.errors if "MOD" in e]
        assert len(mod_errors) == 1

    def test_empty_segments_uses_planned_fields(self, excursion_type, open_water):
        """Empty segments should use planned_depth and planned_duration."""
        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Simple Dive",
            planned_depth_meters=18,
            planned_duration_minutes=45,
            gas="air",
            min_certification_level=open_water,
            route="Reef dive at 18m, safety stop at 5m for 3 min",
            route_segments=[],
        )
        result = validate_dive_template(template)

        # Should pass - 18m for 45 min is within NDL (56 min)
        assert result.is_valid


# =============================================================================
# Juan Escutia Wreck Integration Test
# =============================================================================


@pytest.mark.django_db
class TestJuanEscutiaWreckValidation:
    """Integration test with real wreck dive template."""

    def test_juan_escutia_template_validates(self, db, advanced_ow):
        """The Juan Escutia wreck template should pass basic validation.

        Full NDL/gas validation requires Subsurface integration.
        This test verifies MOD and certification checks pass.
        """
        excursion_type = ExcursionType.objects.create(
            name="Juan Escutia Wreck",
            slug="juan-escutia-test",
            dive_mode="boat",
            max_depth_meters=27,
            base_price=Decimal("175.00"),
            min_certification_level=advanced_ow,
        )

        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            sequence=1,
            name="Juan Escutia Wreck Exploration",
            planned_depth_meters=27,  # 90 feet
            planned_duration_minutes=45,
            min_certification_level=advanced_ow,
            gas="ean32",  # Within MOD (34m limit)
            route=(
                "Descent to wreck → meet on main deck at 85' (5 min) → "
                "ascend to 75' explore deck (8 min) → "
                "ascend to 65' explore second deck (12 min) → "
                "ascend to 60' meet at poop deck → "
                "swim forward to bow → ascend to 45' → "
                "controlled ascent to 30' → "
                "safety stop at 15' for 3 min → "
                "slow ascent to surface (1 min)"
            ),
            # Multi-level profile for Subsurface validation
            route_segments=[
                {"phase": "descent", "depth_m": 26, "duration_min": 3, "description": "Descend to wreck"},
                {"phase": "bottom", "depth_m": 26, "duration_min": 5, "description": "Main deck at 85'"},
                {"phase": "ascent", "depth_m": 23, "duration_min": 8, "description": "Explore deck at 75'"},
                {"phase": "ascent", "depth_m": 20, "duration_min": 12, "description": "Second deck/helipad at 65'"},
                {"phase": "ascent", "depth_m": 18, "duration_min": 5, "description": "Poop deck at 60'"},
                {"phase": "ascent", "depth_m": 14, "duration_min": 5, "description": "Bow at 45'"},
                {"phase": "safety_stop", "depth_m": 5, "duration_min": 3, "description": "Safety stop at 15'"},
                {"phase": "ascent", "depth_m": 0, "duration_min": 1, "description": "Surface"},
            ],
        )

        result = validate_dive_template(template)

        # Should pass basic validation:
        # - EAN32 at 26m max depth is within MOD (34m limit)
        # - AOW cert covers 30m depth limit
        # Full NDL/gas planning validation requires Subsurface
        assert result.is_valid, f"Errors: {result.errors}"
        assert len(result.errors) == 0
        # Should note Subsurface validation pending
        assert any("Subsurface" in i for i in result.info)
