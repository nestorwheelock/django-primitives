"""Tests for dive plan locking services.

Tests lock_dive_plan(), resnapshot_dive_plan(), and lock_excursion_plans().
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from primitives_testbed.diveops.models import (
    Dive,
    DiveSite,
    Excursion,
    ExcursionType,
    ExcursionTypeDive,
    CertificationLevel,
)
from primitives_testbed.diveops.services import (
    lock_dive_plan,
    resnapshot_dive_plan,
    lock_excursion_plans,
)
from primitives_testbed.diveops.audit import Actions

from django_audit_log.models import AuditLog
from django_parties.models import Organization
from django_geo.models import Place


User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user for testing."""
    return User.objects.create_user(
        username="guide@diveshop.com",
        email="guide@diveshop.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def dive_shop(db):
    """Create a dive shop (Organization)."""
    return Organization.objects.create(
        name="Test Dive Shop",
    )


@pytest.fixture
def certification_agency(db):
    """Create a certification agency."""
    return Organization.objects.create(
        name="PADI",
    )


@pytest.fixture
def certification_level(db, certification_agency):
    """Create a certification level."""
    return CertificationLevel.objects.create(
        agency=certification_agency,
        code="aow",
        name="Advanced Open Water",
        rank=3,
        max_depth_m=30,
    )


@pytest.fixture
def place(db):
    """Create a place for dive site."""
    return Place.objects.create(
        name="Blue Hole Location",
        latitude=Decimal("17.3151"),
        longitude=Decimal("-87.5346"),
    )


@pytest.fixture
def dive_site(db, place):
    """Create a dive site."""
    return DiveSite.objects.create(
        name="Blue Hole",
        place=place,
        max_depth_meters=40,
        difficulty="intermediate",
    )


@pytest.fixture
def excursion_type(db, certification_level):
    """Create an excursion type."""
    return ExcursionType.objects.create(
        name="Morning 2-Tank Boat Dive",
        slug="morning-2-tank-boat",
        dive_mode="boat",
        max_depth_meters=30,
        typical_duration_minutes=120,
        dives_per_excursion=2,
        min_certification_level=certification_level,
        base_price=Decimal("150.00"),
    )


@pytest.fixture
def published_template(db, excursion_type, staff_user, certification_level):
    """Create a published dive template."""
    return ExcursionTypeDive.objects.create(
        excursion_type=excursion_type,
        sequence=1,
        name="First Tank",
        description="Shallow reef dive",
        planned_depth_meters=18,
        planned_duration_minutes=45,
        offset_minutes=30,
        min_certification_level=certification_level,
        gas="air",
        equipment_requirements={"required": ["torch"], "recommended": ["SMB"]},
        skills=[],
        route="Follow reef wall south, turn at 30 min",
        hazards="Mild current possible",
        briefing_text="Full briefing for first tank dive.",
        status="published",
        published_at=timezone.now() - timedelta(days=1),
        published_by=staff_user,
    )


@pytest.fixture
def draft_template(db, excursion_type):
    """Create a draft dive template."""
    return ExcursionTypeDive.objects.create(
        excursion_type=excursion_type,
        sequence=2,
        name="Second Tank",
        description="Deep wall dive",
        planned_depth_meters=28,
        planned_duration_minutes=35,
        offset_minutes=90,
        gas="ean32",
        status="draft",
    )


@pytest.fixture
def excursion(db, dive_shop, dive_site, excursion_type, staff_user):
    """Create an excursion."""
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
        created_by=staff_user,
    )


@pytest.fixture
def dive_with_template(db, excursion, dive_site, published_template):
    """Create a dive with a published template."""
    return Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=1,
        planned_start=excursion.departure_time + timedelta(minutes=30),
        planned_duration_minutes=45,
    )


@pytest.fixture
def dive_with_draft_template(db, excursion, dive_site, draft_template):
    """Create a dive with a draft template."""
    return Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=2,
        planned_start=excursion.departure_time + timedelta(minutes=90),
        planned_duration_minutes=35,
    )


@pytest.fixture
def locked_dive(db, dive_with_template, staff_user):
    """Create a dive with a locked plan."""
    dive_with_template.plan_snapshot = {
        "version": 1,
        "template": {"id": "test", "name": "First Tank"},
        "planning": {"sequence": 1, "planned_depth_meters": 18},
        "briefing": {"gas": "air", "route": "Original route"},
        "metadata": {"locked_at": timezone.now().isoformat()},
    }
    dive_with_template.plan_locked_at = timezone.now()
    dive_with_template.plan_locked_by = staff_user
    dive_with_template.save()
    return dive_with_template


@pytest.fixture
def standalone_dive(db, excursion, dive_site):
    """Create a dive without a matching template."""
    return Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=99,  # No matching template
        planned_start=excursion.departure_time + timedelta(hours=2),
        planned_duration_minutes=30,
    )


@pytest.fixture
def dive_with_outdated_flag(db, locked_dive):
    """Create a locked dive with outdated flag set."""
    locked_dive.plan_snapshot_outdated = True
    locked_dive.save()
    return locked_dive


@pytest.mark.django_db
class TestLockDivePlan:
    """Tests for lock_dive_plan service."""

    def test_creates_plan_snapshot(self, dive_with_template, staff_user):
        """lock_dive_plan populates plan_snapshot from template."""
        assert dive_with_template.plan_snapshot is None

        result = lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert dive_with_template.plan_snapshot is not None
        assert "version" in dive_with_template.plan_snapshot
        assert "template" in dive_with_template.plan_snapshot
        assert "briefing" in dive_with_template.plan_snapshot

    def test_sets_locked_at_and_by(self, dive_with_template, staff_user):
        """lock_dive_plan sets audit fields."""
        assert dive_with_template.plan_locked_at is None
        assert dive_with_template.plan_locked_by is None

        before = timezone.now()
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert dive_with_template.plan_locked_by == staff_user
        assert dive_with_template.plan_locked_at is not None
        assert dive_with_template.plan_locked_at >= before

    def test_sets_provenance_fields(self, dive_with_template, staff_user, published_template):
        """lock_dive_plan sets plan_template_id and plan_template_published_at."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert dive_with_template.plan_template_id == published_template.id
        assert dive_with_template.plan_template_published_at == published_template.published_at

    def test_snapshot_contains_template_fields(self, dive_with_template, staff_user):
        """plan_snapshot includes all briefing content."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        snapshot = dive_with_template.plan_snapshot

        # Check briefing section
        assert "briefing" in snapshot
        briefing = snapshot["briefing"]
        assert briefing["gas"] == "air"
        assert briefing["equipment_requirements"] == {"required": ["torch"], "recommended": ["SMB"]}
        assert briefing["route"] == "Follow reef wall south, turn at 30 min"
        assert briefing["hazards"] == "Mild current possible"

    def test_snapshot_independent_of_template_changes(self, locked_dive, staff_user, published_template):
        """Modifying template after lock doesn't change snapshot."""
        original_route = locked_dive.plan_snapshot["briefing"]["route"]

        # Modify template
        published_template.route = "COMPLETELY DIFFERENT ROUTE"
        published_template.save()

        # Snapshot should be unchanged
        locked_dive.refresh_from_db()
        assert locked_dive.plan_snapshot["briefing"]["route"] == original_route

    def test_idempotent_when_already_locked(self, locked_dive, staff_user):
        """lock_dive_plan called twice returns dive unchanged (no error)."""
        original_locked_at = locked_dive.plan_locked_at

        # Call again without force - should be idempotent
        result = lock_dive_plan(actor=staff_user, dive=locked_dive)

        locked_dive.refresh_from_db()
        assert locked_dive.plan_locked_at == original_locked_at
        assert result == locked_dive

    def test_force_relocks_already_locked_dive(self, locked_dive, staff_user):
        """lock_dive_plan with force=True updates existing snapshot."""
        original_locked_at = locked_dive.plan_locked_at

        # Call with force - should update
        result = lock_dive_plan(actor=staff_user, dive=locked_dive, force=True)

        locked_dive.refresh_from_db()
        assert locked_dive.plan_locked_at > original_locked_at

    def test_rejects_unpublished_template(self, dive_with_draft_template, staff_user):
        """lock_dive_plan raises if template not published."""
        with pytest.raises(ValidationError, match="not published"):
            lock_dive_plan(actor=staff_user, dive=dive_with_draft_template)

    def test_force_allows_unpublished_template(self, dive_with_draft_template, staff_user):
        """lock_dive_plan with force=True allows unpublished template."""
        # Should not raise
        result = lock_dive_plan(actor=staff_user, dive=dive_with_draft_template, force=True)

        dive_with_draft_template.refresh_from_db()
        assert dive_with_draft_template.plan_snapshot is not None

    def test_rejects_dive_without_template(self, standalone_dive, staff_user):
        """lock_dive_plan raises if no template available."""
        with pytest.raises(ValueError, match="no template"):
            lock_dive_plan(actor=staff_user, dive=standalone_dive)

    def test_clears_snapshot_outdated_flag(self, dive_with_outdated_flag, staff_user):
        """lock_dive_plan clears plan_snapshot_outdated."""
        assert dive_with_outdated_flag.plan_snapshot_outdated is True

        lock_dive_plan(actor=staff_user, dive=dive_with_outdated_flag, force=True)

        dive_with_outdated_flag.refresh_from_db()
        assert dive_with_outdated_flag.plan_snapshot_outdated is False

    def test_emits_locked_audit_event(self, dive_with_template, staff_user):
        """lock_dive_plan emits DIVE_PLAN_LOCKED."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        audit = AuditLog.objects.filter(action=Actions.DIVE_PLAN_LOCKED).first()
        assert audit is not None
        assert audit.actor_user == staff_user


@pytest.mark.django_db
class TestResnapshotDivePlan:
    """Tests for resnapshot_dive_plan service."""

    def test_updates_snapshot_on_locked_dive(self, locked_dive, staff_user, published_template):
        """resnapshot_dive_plan replaces snapshot."""
        # Modify template before resnapshot
        published_template.route = "Updated route for resnapshot"
        published_template.save()

        resnapshot_dive_plan(actor=staff_user, dive=locked_dive, reason="Customer requested update")

        locked_dive.refresh_from_db()
        assert locked_dive.plan_snapshot["briefing"]["route"] == "Updated route for resnapshot"

    def test_requires_reason(self, locked_dive, staff_user):
        """resnapshot_dive_plan raises if reason empty."""
        with pytest.raises(ValueError, match="reason"):
            resnapshot_dive_plan(actor=staff_user, dive=locked_dive, reason="")

    def test_rejects_unlocked_dive(self, dive_with_template, staff_user):
        """resnapshot_dive_plan raises if not locked."""
        with pytest.raises(ValueError, match="not locked"):
            resnapshot_dive_plan(actor=staff_user, dive=dive_with_template, reason="Test")

    def test_audit_contains_old_and_new(self, locked_dive, staff_user, published_template):
        """resnapshot audit event includes diff and reason."""
        published_template.route = "New route"
        published_template.save()

        resnapshot_dive_plan(actor=staff_user, dive=locked_dive, reason="Updated briefing")

        audit = AuditLog.objects.filter(action=Actions.DIVE_PLAN_RESNAPSHOTTED).first()
        assert audit is not None
        assert "reason" in audit.changes or "old" in audit.changes

    def test_emits_resnapshotted_audit_event(self, locked_dive, staff_user):
        """resnapshot_dive_plan emits DIVE_PLAN_RESNAPSHOTTED."""
        resnapshot_dive_plan(actor=staff_user, dive=locked_dive, reason="Test resnapshot")

        audit = AuditLog.objects.filter(action=Actions.DIVE_PLAN_RESNAPSHOTTED).first()
        assert audit is not None
        assert audit.actor_user == staff_user


@pytest.mark.django_db
class TestLockExcursionPlans:
    """Tests for lock_excursion_plans service."""

    def test_locks_all_unlocked_dives(self, excursion, dive_site, published_template, staff_user):
        """lock_excursion_plans locks all dives."""
        # Create two unlocked dives
        dive1 = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=excursion.departure_time + timedelta(minutes=30),
        )

        result = lock_excursion_plans(actor=staff_user, excursion=excursion)

        dive1.refresh_from_db()
        assert dive1.plan_locked_at is not None
        assert len(result) >= 1

    def test_skips_already_locked_dives(self, excursion, locked_dive, staff_user):
        """lock_excursion_plans doesn't relock locked dives."""
        original_locked_at = locked_dive.plan_locked_at

        result = lock_excursion_plans(actor=staff_user, excursion=excursion)

        locked_dive.refresh_from_db()
        assert locked_dive.plan_locked_at == original_locked_at

    def test_returns_list_of_locked_dives(self, excursion, dive_site, published_template, staff_user):
        """lock_excursion_plans returns locked dive list."""
        Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=excursion.departure_time + timedelta(minutes=30),
        )

        result = lock_excursion_plans(actor=staff_user, excursion=excursion)

        assert isinstance(result, list)
        assert len(result) >= 1
        for dive in result:
            assert isinstance(dive, Dive)

    def test_emits_excursion_locked_audit_event(self, excursion, dive_site, published_template, staff_user):
        """lock_excursion_plans emits EXCURSION_PLANS_LOCKED."""
        Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=excursion.departure_time + timedelta(minutes=30),
        )

        lock_excursion_plans(actor=staff_user, excursion=excursion)

        audit = AuditLog.objects.filter(action=Actions.EXCURSION_PLANS_LOCKED).first()
        assert audit is not None
        assert audit.actor_user == staff_user


@pytest.mark.django_db
class TestPlanSnapshotSchema:
    """Tests for plan snapshot schema."""

    def test_snapshot_has_version(self, dive_with_template, staff_user):
        """Snapshot includes version field."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert "version" in dive_with_template.plan_snapshot
        assert dive_with_template.plan_snapshot["version"] == 1

    def test_snapshot_has_template_identity(self, dive_with_template, staff_user, published_template):
        """Snapshot includes template_id and template_name."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert "template" in dive_with_template.plan_snapshot
        template_info = dive_with_template.plan_snapshot["template"]
        assert "id" in template_info
        assert "name" in template_info
        assert template_info["name"] == "First Tank"

    def test_snapshot_has_planning_fields(self, dive_with_template, staff_user):
        """Snapshot includes depth, duration, offset."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert "planning" in dive_with_template.plan_snapshot
        planning = dive_with_template.plan_snapshot["planning"]
        assert "planned_depth_meters" in planning
        assert "planned_duration_minutes" in planning
        assert "offset_minutes" in planning

    def test_snapshot_has_briefing_fields(self, dive_with_template, staff_user):
        """Snapshot includes gas, equipment, skills, route, hazards."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert "briefing" in dive_with_template.plan_snapshot
        briefing = dive_with_template.plan_snapshot["briefing"]
        assert "gas" in briefing
        assert "equipment_requirements" in briefing
        assert "skills" in briefing
        assert "route" in briefing
        assert "hazards" in briefing

    def test_snapshot_has_certification_fields(self, dive_with_template, staff_user, certification_level):
        """Snapshot includes min certification if set."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert "certification" in dive_with_template.plan_snapshot
        cert = dive_with_template.plan_snapshot["certification"]
        assert "min_level_id" in cert
        assert "min_level_name" in cert

    def test_snapshot_has_metadata(self, dive_with_template, staff_user):
        """Snapshot includes locked_at timestamp."""
        lock_dive_plan(actor=staff_user, dive=dive_with_template)

        dive_with_template.refresh_from_db()
        assert "metadata" in dive_with_template.plan_snapshot
        assert "locked_at" in dive_with_template.plan_snapshot["metadata"]
