"""Tests for dive template lifecycle services.

Tests publish_dive_template() and retire_dive_template() services.
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from primitives_testbed.diveops.models import (
    ExcursionType,
    ExcursionTypeDive,
    CertificationLevel,
)
from primitives_testbed.diveops.services import (
    publish_dive_template,
    retire_dive_template,
)
from primitives_testbed.diveops.audit import Actions

from django_audit_log.models import AuditLog
from django_parties.models import Organization


User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user for testing."""
    return User.objects.create_user(
        username="staff@diveshop.com",
        email="staff@diveshop.com",
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
def draft_template(db, excursion_type):
    """Create a draft dive template."""
    return ExcursionTypeDive.objects.create(
        excursion_type=excursion_type,
        sequence=1,
        name="First Tank",
        description="Shallow reef dive",
        planned_depth_meters=18,
        planned_duration_minutes=45,
        offset_minutes=30,
        # New briefing fields
        gas="air",
        equipment_requirements={"required": ["torch"], "recommended": ["SMB"]},
        skills=[],
        route="Follow reef wall south, turn at 30 min",
        hazards="Mild current possible",
        briefing_text="Full briefing for first tank dive.",
        # Lifecycle
        status="draft",
    )


@pytest.fixture
def published_template(db, excursion_type, staff_user):
    """Create a published dive template."""
    template = ExcursionTypeDive.objects.create(
        excursion_type=excursion_type,
        sequence=2,
        name="Second Tank",
        description="Deeper wall dive",
        planned_depth_meters=28,
        planned_duration_minutes=35,
        offset_minutes=90,
        gas="ean32",
        equipment_requirements={"required": ["SMB"]},
        route="Drop to 28m, wall dive",
        hazards="Watch depth at wall edge",
        briefing_text="Full briefing for deep wall dive.",
        status="published",
        published_at=timezone.now() - timedelta(days=1),
        published_by=staff_user,
    )
    return template


@pytest.fixture
def retired_template(db, excursion_type, staff_user):
    """Create a retired dive template."""
    template = ExcursionTypeDive.objects.create(
        excursion_type=excursion_type,
        sequence=3,
        name="Old Dive",
        description="No longer offered",
        planned_depth_meters=15,
        planned_duration_minutes=40,
        status="retired",
        published_at=timezone.now() - timedelta(days=30),
        published_by=staff_user,
        retired_at=timezone.now() - timedelta(days=1),
        retired_by=staff_user,
    )
    return template


@pytest.mark.django_db
class TestPublishDiveTemplate:
    """Tests for publish_dive_template service."""

    def test_publishes_draft_template(self, draft_template, staff_user):
        """publish_dive_template changes status from draft to published."""
        assert draft_template.status == "draft"

        result = publish_dive_template(actor=staff_user, dive_template=draft_template)

        draft_template.refresh_from_db()
        assert draft_template.status == "published"
        assert result.status == "published"

    def test_sets_published_at_and_by(self, draft_template, staff_user):
        """publish_dive_template sets audit fields."""
        assert draft_template.published_at is None
        assert draft_template.published_by is None

        before = timezone.now()
        publish_dive_template(actor=staff_user, dive_template=draft_template)

        draft_template.refresh_from_db()
        assert draft_template.published_by == staff_user
        assert draft_template.published_at is not None
        assert draft_template.published_at >= before

    def test_rejects_already_published(self, published_template, staff_user):
        """publish_dive_template raises if not draft."""
        with pytest.raises(ValueError, match="not in draft"):
            publish_dive_template(actor=staff_user, dive_template=published_template)

    def test_rejects_retired_template(self, retired_template, staff_user):
        """publish_dive_template raises if retired."""
        with pytest.raises(ValueError, match="not in draft"):
            publish_dive_template(actor=staff_user, dive_template=retired_template)

    def test_emits_published_audit_event(self, draft_template, staff_user):
        """publish_dive_template emits DIVE_TEMPLATE_PUBLISHED."""
        publish_dive_template(actor=staff_user, dive_template=draft_template)

        audit = AuditLog.objects.filter(action=Actions.DIVE_TEMPLATE_PUBLISHED).first()
        assert audit is not None
        assert audit.actor_user == staff_user


@pytest.mark.django_db
class TestRetireDiveTemplate:
    """Tests for retire_dive_template service."""

    def test_retires_published_template(self, published_template, staff_user):
        """retire_dive_template changes status to retired."""
        assert published_template.status == "published"

        result = retire_dive_template(actor=staff_user, dive_template=published_template)

        published_template.refresh_from_db()
        assert published_template.status == "retired"
        assert result.status == "retired"

    def test_sets_retired_at_and_by(self, published_template, staff_user):
        """retire_dive_template sets audit fields."""
        assert published_template.retired_at is None
        assert published_template.retired_by is None

        before = timezone.now()
        retire_dive_template(actor=staff_user, dive_template=published_template)

        published_template.refresh_from_db()
        assert published_template.retired_by == staff_user
        assert published_template.retired_at is not None
        assert published_template.retired_at >= before

    def test_rejects_draft_template(self, draft_template, staff_user):
        """retire_dive_template raises if not published."""
        with pytest.raises(ValueError, match="not in published"):
            retire_dive_template(actor=staff_user, dive_template=draft_template)

    def test_rejects_already_retired(self, retired_template, staff_user):
        """retire_dive_template raises if already retired."""
        with pytest.raises(ValueError, match="not in published"):
            retire_dive_template(actor=staff_user, dive_template=retired_template)

    def test_emits_retired_audit_event(self, published_template, staff_user):
        """retire_dive_template emits DIVE_TEMPLATE_RETIRED."""
        retire_dive_template(actor=staff_user, dive_template=published_template)

        audit = AuditLog.objects.filter(action=Actions.DIVE_TEMPLATE_RETIRED).first()
        assert audit is not None
        assert audit.actor_user == staff_user
