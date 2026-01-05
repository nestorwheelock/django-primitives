"""Tests for dive plan decompression validation.

Tests the validate_dive_plan service and integration with the
Rust diveops-deco-validate binary.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.utils import timezone

from primitives_testbed.diveops.services import (
    validate_dive_plan,
    _gas_o2_fraction,
    GAS_O2_MAP,
)

User = get_user_model()


def create_excursion(dive_shop, dive_site, excursion_type, created_by):
    """Helper to create an Excursion with required fields."""
    from primitives_testbed.diveops.models import Excursion
    departure = timezone.now() + timedelta(days=1)
    return Excursion.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        excursion_type=excursion_type,
        departure_time=departure,
        return_time=departure + timedelta(hours=4),
        max_divers=8,
        price_per_diver=Decimal("150.00"),
        status="scheduled",
        created_by=created_by,
    )


def create_dive(excursion, dive_site, sequence=1):
    """Helper to create a Dive with required fields."""
    from primitives_testbed.diveops.models import Dive
    return Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=sequence,
        planned_start=excursion.departure_time + timedelta(minutes=30 * sequence),
    )


@pytest.fixture
def dive_shop(db):
    """Create a dive shop (Organization)."""
    from django_parties.models import Organization
    return Organization.objects.create(name="Test Dive Shop")


@pytest.fixture
def place(db):
    """Create a place for dive site."""
    from django_geo.models import Place
    return Place.objects.create(
        name="Test Location",
        city="Cozumel",
        state="Quintana Roo",
        postal_code="77600",
        country="MX",
        latitude=Decimal("20.4318"),
        longitude=Decimal("-86.9203"),
    )


@pytest.fixture
def dive_site(db, place):
    """Create a dive site."""
    from primitives_testbed.diveops.models import DiveSite
    return DiveSite.objects.create(
        name="Test Site",
        place=place,
        max_depth_meters=30,
    )


@pytest.fixture
def excursion_type(db):
    """Create an excursion type."""
    from primitives_testbed.diveops.models import ExcursionType
    return ExcursionType.objects.create(
        name="Morning 2-Tank Dive",
        slug="morning-2-tank",
        dive_mode="boat",
        max_depth_meters=30,
        base_price=Decimal("150.00"),
    )


class TestGasO2Fraction:
    """Tests for _gas_o2_fraction helper."""

    def test_air(self):
        assert _gas_o2_fraction("air") == 0.21

    def test_ean32(self):
        assert _gas_o2_fraction("ean32") == 0.32

    def test_ean36(self):
        assert _gas_o2_fraction("ean36") == 0.36

    def test_none_defaults_to_air(self):
        assert _gas_o2_fraction(None) == 0.21

    def test_unknown_defaults_to_air(self):
        assert _gas_o2_fraction("unknown_gas") == 0.21

    def test_case_insensitive(self):
        assert _gas_o2_fraction("AIR") == 0.21
        assert _gas_o2_fraction("EAN32") == 0.32


@pytest.mark.django_db
class TestValidateDivePlan:
    """Tests for validate_dive_plan service."""

    @pytest.fixture
    def staff_user(self, db):
        """Create a staff user."""
        return User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="testpass",
            is_staff=True,
        )

    @pytest.fixture
    def locked_dive_with_segments(self, db, staff_user, dive_shop, dive_site, excursion_type):
        """Create a locked dive with route_segments."""
        from primitives_testbed.diveops.models import ExcursionTypeDive

        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            name="Wreck Dive",
            sequence=1,
            planned_depth_meters=26,
            planned_duration_minutes=40,
            gas="ean32",
            route_segments=[
                {"phase": "descent", "from_depth_m": 0, "to_depth_m": 26, "duration_min": 3},
                {"phase": "level", "depth_m": 26, "duration_min": 25},
                {"phase": "safety_stop", "depth_m": 5, "duration_min": 3},
                {"phase": "ascent", "from_depth_m": 5, "to_depth_m": 0, "duration_min": 1},
            ],
            status="published",
            published_at=timezone.now(),
        )
        excursion = create_excursion(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            created_by=staff_user,
        )
        dive = create_dive(excursion, dive_site, sequence=1)

        # Lock the dive manually with required fields
        dive.plan_snapshot = {
            "version": 1,
            "template": {"id": str(template.id), "name": template.name},
            "briefing": {
                "gas": "ean32",
                "gas_o2": 0.32,
                "gas_he": 0.0,
                "route_segments": template.route_segments,
            },
            "metadata": {"locked_at": timezone.now().isoformat()},
        }
        dive.plan_locked_at = timezone.now()
        dive.save()

        return dive

    @pytest.fixture
    def locked_dive_no_segments(self, db, staff_user, dive_shop, dive_site, excursion_type):
        """Create a locked dive without route_segments."""
        excursion = create_excursion(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            created_by=staff_user,
        )
        dive = create_dive(excursion, dive_site, sequence=1)

        # Lock without route_segments
        dive.plan_snapshot = {
            "version": 1,
            "briefing": {"gas": "air", "gas_o2": 0.21, "gas_he": 0.0},
            "metadata": {"locked_at": timezone.now().isoformat()},
        }
        dive.plan_locked_at = timezone.now()
        dive.save()

        return dive

    def test_requires_locked_plan(self, staff_user, dive_shop, dive_site, excursion_type):
        """Raises ValueError if plan_snapshot is None."""
        excursion = create_excursion(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            created_by=staff_user,
        )
        dive = create_dive(excursion, dive_site, sequence=1)

        with pytest.raises(ValueError, match="must be locked"):
            validate_dive_plan(actor=staff_user, dive=dive)

    @patch("primitives_testbed.diveops.services.getattr")
    def test_skips_when_disabled(self, mock_getattr, locked_dive_with_segments, staff_user):
        """Returns unchanged if ENABLE_DECO_VALIDATION is False."""
        # Mock settings to disable validation
        def settings_getattr(obj, attr, default=None):
            if attr == "ENABLE_DECO_VALIDATION":
                return False
            return default

        mock_getattr.side_effect = settings_getattr

        result = validate_dive_plan(actor=staff_user, dive=locked_dive_with_segments)

        # Should return without modifying validation field
        assert result.plan_snapshot.get("validation") is None

    def test_handles_no_route_segments(self, locked_dive_no_segments, staff_user):
        """Sets error when no route_segments present."""
        with patch(
            "primitives_testbed.diveops.services.getattr",
            side_effect=lambda obj, attr, default=None: (
                True if attr == "ENABLE_DECO_VALIDATION" else default
            ),
        ):
            result = validate_dive_plan(
                actor=staff_user, dive=locked_dive_no_segments
            )

            assert result.plan_snapshot["validation"]["error"] == "no_route_segments"
            assert "validated_at" in result.plan_snapshot["validation"]

    @patch("primitives_testbed.diveops.planning.deco_runner.subprocess.run")
    def test_calls_validator_with_correct_input(
        self, mock_subprocess, locked_dive_with_segments, staff_user
    ):
        """Calls validator binary with correct JSON input."""
        import json

        # Mock successful validator response
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "tool": "diveops-deco-validate",
            "tool_version": "0.1.0",
            "model": "Bühlmann ZHL-16C",
            "gf_low": 0.40,
            "gf_high": 0.85,
            "ceiling_m": 0.0,
            "tts_min": 5.0,
            "ndl_min": 15,
            "deco_required": False,
            "stops": [],
            "max_depth_m": 26.0,
            "runtime_min": 31.0,
            "input_hash": "sha256:abc123",
        })
        mock_subprocess.return_value = mock_result

        with patch(
            "primitives_testbed.diveops.services.getattr",
            side_effect=lambda obj, attr, default=None: {
                "ENABLE_DECO_VALIDATION": True,
                "DECO_GF_LOW": 0.40,
                "DECO_GF_HIGH": 0.85,
                "DECO_VALIDATOR_PATH": "/usr/local/bin/diveops-deco-validate",
                "DECO_VALIDATOR_TIMEOUT": 10,
            }.get(attr, default),
        ):
            result = validate_dive_plan(
                actor=staff_user, dive=locked_dive_with_segments
            )

            # Verify validator was called
            assert mock_subprocess.called

            # Check validation result stored
            validation = result.plan_snapshot["validation"]
            assert validation["deco_required"] is False
            assert validation["ceiling_m"] == 0.0
            assert "validated_at" in validation

    def test_skips_if_already_validated(self, locked_dive_with_segments, staff_user):
        """Skips validation if already validated (unless force=True)."""
        # Pre-populate validation
        locked_dive_with_segments.plan_snapshot["validation"] = {
            "deco_required": False,
            "validated_at": "2024-01-01T00:00:00Z",
        }
        locked_dive_with_segments.save()

        with patch(
            "primitives_testbed.diveops.services.getattr",
            side_effect=lambda obj, attr, default=None: (
                True if attr == "ENABLE_DECO_VALIDATION" else default
            ),
        ):
            result = validate_dive_plan(
                actor=staff_user, dive=locked_dive_with_segments
            )

            # Should not change existing validation
            assert result.plan_snapshot["validation"]["validated_at"] == "2024-01-01T00:00:00Z"

    @patch("primitives_testbed.diveops.planning.deco_runner.subprocess.run")
    def test_force_revalidates(
        self, mock_subprocess, locked_dive_with_segments, staff_user
    ):
        """force=True re-validates even if already validated."""
        import json

        # Pre-populate validation
        locked_dive_with_segments.plan_snapshot["validation"] = {
            "deco_required": False,
            "validated_at": "2024-01-01T00:00:00Z",
        }
        locked_dive_with_segments.save()

        # Mock new validator response
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "tool": "diveops-deco-validate",
            "deco_required": True,
            "ceiling_m": 3.0,
            "tts_min": 10.0,
            "stops": [{"depth_m": 3.0, "duration_min": 5.0}],
        })
        mock_subprocess.return_value = mock_result

        with patch(
            "primitives_testbed.diveops.services.getattr",
            side_effect=lambda obj, attr, default=None: {
                "ENABLE_DECO_VALIDATION": True,
                "DECO_GF_LOW": 0.40,
                "DECO_GF_HIGH": 0.85,
                "DECO_VALIDATOR_PATH": "/usr/local/bin/diveops-deco-validate",
                "DECO_VALIDATOR_TIMEOUT": 10,
            }.get(attr, default),
        ):
            result = validate_dive_plan(
                actor=staff_user, dive=locked_dive_with_segments, force=True
            )

            # Should have new validation
            assert result.plan_snapshot["validation"]["validated_at"] != "2024-01-01T00:00:00Z"


@pytest.mark.django_db
class TestPlanSnapshotGasFields:
    """Tests for gas_o2/gas_he in plan snapshots."""

    def test_snapshot_includes_gas_o2_for_ean32(self, dive_shop, dive_site, excursion_type):
        """Snapshot includes gas_o2=0.32 for EAN32."""
        from primitives_testbed.diveops.models import ExcursionTypeDive
        from primitives_testbed.diveops.services import lock_dive_plan

        user = User.objects.create_user(
            username="test_user", email="test@test.com", password="test"
        )

        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            name="EAN32 Dive",
            sequence=1,
            gas="ean32",
            status="published",
            published_at=timezone.now(),
        )
        excursion = create_excursion(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            created_by=user,
        )
        dive = create_dive(excursion, dive_site, sequence=1)

        result = lock_dive_plan(actor=user, dive=dive)

        assert result.plan_snapshot["briefing"]["gas"] == "ean32"
        assert result.plan_snapshot["briefing"]["gas_o2"] == 0.32
        assert result.plan_snapshot["briefing"]["gas_he"] == 0.0

    def test_snapshot_includes_gas_o2_for_air(self, dive_shop, dive_site, excursion_type):
        """Snapshot includes gas_o2=0.21 for air."""
        from primitives_testbed.diveops.models import ExcursionTypeDive
        from primitives_testbed.diveops.services import lock_dive_plan

        user = User.objects.create_user(
            username="test_user2", email="test2@test.com", password="test"
        )

        template = ExcursionTypeDive.objects.create(
            excursion_type=excursion_type,
            name="Air Dive",
            sequence=2,
            gas="air",
            status="published",
            published_at=timezone.now(),
        )
        excursion = create_excursion(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            created_by=user,
        )
        dive = create_dive(excursion, dive_site, sequence=2)

        result = lock_dive_plan(actor=user, dive=dive)

        assert result.plan_snapshot["briefing"]["gas"] == "air"
        assert result.plan_snapshot["briefing"]["gas_o2"] == 0.21
        assert result.plan_snapshot["briefing"]["gas_he"] == 0.0
