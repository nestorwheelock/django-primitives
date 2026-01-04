"""Tests for DiveSite service layer.

Tests for:
- create_dive_site: Creates Place + DiveSite atomically, emits audit
- update_dive_site: Updates site (and Place coords if changed), emits audit
- delete_dive_site: Soft deletes site, emits audit
- Service-only write path (no direct model creation in views)
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from primitives_testbed.diveops.models import CertificationLevel, DiveSite

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user for audit tracking."""
    return User.objects.create_user(
        username="siteadmin",
        email="siteadmin@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def padi_agency(db):
    """Create PADI certification agency."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="PADI",
        org_type="certification_agency",
    )


@pytest.fixture
def cert_level_ow(db, padi_agency):
    """Create Open Water certification level."""
    return CertificationLevel.objects.create(
        agency=padi_agency,
        code="ow",
        name="Open Water Diver",
        rank=2,
        max_depth_m=18,
    )


@pytest.mark.django_db
class TestCreateDiveSite:
    """Tests for create_dive_site service."""

    def test_creates_place_and_site_atomically(self, staff_user):
        """create_dive_site creates both Place and DiveSite."""
        from primitives_testbed.diveops.services import create_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Palancar Reef",
            latitude=Decimal("20.3500"),
            longitude=Decimal("-87.0300"),
            max_depth_meters=25,
            difficulty="intermediate",
            description="Famous Cozumel reef",
        )

        assert site.pk is not None
        assert site.name == "Palancar Reef"
        assert site.place is not None
        assert site.place.latitude == Decimal("20.3500")
        assert site.place.longitude == Decimal("-87.0300")
        assert site.max_depth_meters == 25
        assert site.difficulty == "intermediate"

    def test_creates_site_with_certification_level(self, staff_user, cert_level_ow):
        """create_dive_site can set min_certification_level FK."""
        from primitives_testbed.diveops.services import create_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Columbia Wall",
            latitude=Decimal("20.3100"),
            longitude=Decimal("-87.0500"),
            max_depth_meters=30,
            difficulty="advanced",
            min_certification_level=cert_level_ow,
        )

        assert site.min_certification_level == cert_level_ow
        assert site.min_certification_level.code == "ow"

    def test_creates_site_with_rating(self, staff_user):
        """create_dive_site can set rating."""
        from primitives_testbed.diveops.services import create_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Paradise Reef",
            latitude=Decimal("20.4000"),
            longitude=Decimal("-87.0100"),
            max_depth_meters=15,
            difficulty="beginner",
            rating=5,
        )

        assert site.rating == 5

    def test_creates_site_with_tags(self, staff_user):
        """create_dive_site can set tags."""
        from primitives_testbed.diveops.services import create_dive_site

        tags = ["reef", "coral", "tropical"]
        site = create_dive_site(
            actor=staff_user,
            name="Tormentos Reef",
            latitude=Decimal("20.3800"),
            longitude=Decimal("-87.0200"),
            max_depth_meters=18,
            difficulty="intermediate",
            tags=tags,
        )

        assert site.tags == tags

    def test_emits_audit_event(self, staff_user):
        """create_dive_site emits audit event."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.services import create_dive_site

        initial_count = AuditLog.objects.count()

        site = create_dive_site(
            actor=staff_user,
            name="Chankanaab",
            latitude=Decimal("20.4200"),
            longitude=Decimal("-86.9900"),
            max_depth_meters=12,
            difficulty="beginner",
        )

        # Should have created audit entry
        assert AuditLog.objects.count() > initial_count
        audit = AuditLog.objects.order_by("-created_at").first()
        assert audit.action == "dive_site_created"
        assert audit.actor_user == staff_user
        # Metadata should include site info
        assert str(site.pk) in str(audit.metadata) or site.name in str(audit.metadata)


@pytest.mark.django_db
class TestUpdateDiveSite:
    """Tests for update_dive_site service."""

    def test_updates_basic_fields(self, staff_user):
        """update_dive_site updates basic site fields."""
        from primitives_testbed.diveops.services import create_dive_site, update_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Old Name",
            latitude=Decimal("20.3500"),
            longitude=Decimal("-87.0300"),
            max_depth_meters=20,
            difficulty="beginner",
        )

        updated = update_dive_site(
            actor=staff_user,
            site=site,
            name="New Name",
            max_depth_meters=25,
            difficulty="intermediate",
        )

        assert updated.name == "New Name"
        assert updated.max_depth_meters == 25
        assert updated.difficulty == "intermediate"

    def test_updates_place_coordinates(self, staff_user):
        """update_dive_site updates Place coords if changed."""
        from primitives_testbed.diveops.services import create_dive_site, update_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Test Site",
            latitude=Decimal("20.0000"),
            longitude=Decimal("-87.0000"),
            max_depth_meters=20,
            difficulty="beginner",
        )
        place_pk = site.place.pk

        updated = update_dive_site(
            actor=staff_user,
            site=site,
            latitude=Decimal("20.5000"),
            longitude=Decimal("-87.5000"),
        )

        # Same place should be updated (not a new one created)
        assert updated.place.pk == place_pk
        assert updated.place.latitude == Decimal("20.5000")
        assert updated.place.longitude == Decimal("-87.5000")

    def test_updates_certification_level(self, staff_user, cert_level_ow):
        """update_dive_site can update min_certification_level."""
        from primitives_testbed.diveops.services import create_dive_site, update_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Test Site",
            latitude=Decimal("20.0000"),
            longitude=Decimal("-87.0000"),
            max_depth_meters=20,
            difficulty="beginner",
        )

        updated = update_dive_site(
            actor=staff_user,
            site=site,
            min_certification_level=cert_level_ow,
        )

        assert updated.min_certification_level == cert_level_ow

    def test_updates_rating_and_tags(self, staff_user):
        """update_dive_site can update rating and tags."""
        from primitives_testbed.diveops.services import create_dive_site, update_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Test Site",
            latitude=Decimal("20.0000"),
            longitude=Decimal("-87.0000"),
            max_depth_meters=20,
            difficulty="beginner",
        )

        updated = update_dive_site(
            actor=staff_user,
            site=site,
            rating=4,
            tags=["updated", "new-tags"],
        )

        assert updated.rating == 4
        assert updated.tags == ["updated", "new-tags"]

    def test_emits_audit_event(self, staff_user):
        """update_dive_site emits audit event."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.services import create_dive_site, update_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Test Site",
            latitude=Decimal("20.0000"),
            longitude=Decimal("-87.0000"),
            max_depth_meters=20,
            difficulty="beginner",
        )

        initial_count = AuditLog.objects.count()

        update_dive_site(
            actor=staff_user,
            site=site,
            name="Updated Name",
        )

        assert AuditLog.objects.count() > initial_count
        audit = AuditLog.objects.order_by("-created_at").first()
        assert audit.action == "dive_site_updated"
        assert audit.actor_user == staff_user


@pytest.mark.django_db
class TestDeleteDiveSite:
    """Tests for delete_dive_site service."""

    def test_soft_deletes_site(self, staff_user):
        """delete_dive_site soft deletes the site."""
        from primitives_testbed.diveops.services import create_dive_site, delete_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="To Delete",
            latitude=Decimal("20.0000"),
            longitude=Decimal("-87.0000"),
            max_depth_meters=20,
            difficulty="beginner",
        )
        site_pk = site.pk

        delete_dive_site(actor=staff_user, site=site)

        # Should be excluded from default queryset
        assert not DiveSite.objects.filter(pk=site_pk).exists()
        # But still in all_objects
        assert DiveSite.all_objects.filter(pk=site_pk).exists()

    def test_emits_audit_event(self, staff_user):
        """delete_dive_site emits audit event."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.services import create_dive_site, delete_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="To Delete",
            latitude=Decimal("20.0000"),
            longitude=Decimal("-87.0000"),
            max_depth_meters=20,
            difficulty="beginner",
        )

        initial_count = AuditLog.objects.count()

        delete_dive_site(actor=staff_user, site=site)

        assert AuditLog.objects.count() > initial_count
        audit = AuditLog.objects.order_by("-created_at").first()
        assert audit.action == "dive_site_deleted"
        assert audit.actor_user == staff_user


@pytest.mark.django_db
class TestServiceOnlyWritePath:
    """Tests that ensure service-only write path is enforced."""

    def test_create_requires_actor(self, staff_user):
        """create_dive_site requires actor parameter."""
        from primitives_testbed.diveops.services import create_dive_site

        with pytest.raises(TypeError):
            create_dive_site(
                name="No Actor",
                latitude=Decimal("20.0000"),
                longitude=Decimal("-87.0000"),
                max_depth_meters=20,
                difficulty="beginner",
            )

    def test_update_requires_actor(self, staff_user):
        """update_dive_site requires actor parameter."""
        from primitives_testbed.diveops.services import create_dive_site, update_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Test",
            latitude=Decimal("20.0000"),
            longitude=Decimal("-87.0000"),
            max_depth_meters=20,
            difficulty="beginner",
        )

        with pytest.raises(TypeError):
            update_dive_site(site=site, name="Updated")

    def test_delete_requires_actor(self, staff_user):
        """delete_dive_site requires actor parameter."""
        from primitives_testbed.diveops.services import create_dive_site, delete_dive_site

        site = create_dive_site(
            actor=staff_user,
            name="Test",
            latitude=Decimal("20.0000"),
            longitude=Decimal("-87.0000"),
            max_depth_meters=20,
            difficulty="beginner",
        )

        with pytest.raises(TypeError):
            delete_dive_site(site=site)
