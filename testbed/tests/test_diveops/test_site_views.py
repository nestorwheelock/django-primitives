"""Tests for DiveSite staff views.

Tests for:
- DiveSiteListView: List of dive sites with staff auth
- DiveSiteDetailView: Site detail with map
- DiveSiteCreateView: Form + map creates site via service
- DiveSiteUpdateView: Form + map updates site via service
- DiveSiteDeleteView: POST-only soft delete via service
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from primitives_testbed.diveops.models import CertificationLevel, DiveSite

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        username="staffuser",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    """Create a regular (non-staff) user."""
    return User.objects.create_user(
        username="regularuser",
        email="regular@example.com",
        password="testpass123",
        is_staff=False,
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


@pytest.fixture
def dive_site(db, staff_user):
    """Create a dive site via service."""
    from primitives_testbed.diveops.services import create_dive_site

    return create_dive_site(
        actor=staff_user,
        name="Test Reef",
        latitude=Decimal("20.5000"),
        longitude=Decimal("-87.0000"),
        max_depth_meters=25,
        difficulty="intermediate",
        description="A test dive site",
        rating=4,
        tags=["reef", "coral"],
    )


@pytest.mark.django_db
class TestDiveSiteListView:
    """Tests for DiveSiteListView."""

    def test_requires_staff_auth(self, client, regular_user):
        """Non-staff users cannot access site list."""
        client.force_login(regular_user)
        url = reverse("diveops:staff-site-list")
        response = client.get(url)
        # Should redirect to login or return 403
        assert response.status_code in [302, 403]

    def test_staff_can_access(self, client, staff_user):
        """Staff users can access site list."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-list")
        response = client.get(url)
        assert response.status_code == 200

    def test_lists_dive_sites(self, client, staff_user, dive_site):
        """Site list shows dive sites."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-list")
        response = client.get(url)
        assert response.status_code == 200
        assert dive_site.name in response.content.decode()

    def test_excludes_soft_deleted_sites(self, client, staff_user, dive_site):
        """Soft deleted sites are not shown in list."""
        from primitives_testbed.diveops.services import delete_dive_site

        delete_dive_site(actor=staff_user, site=dive_site)

        client.force_login(staff_user)
        url = reverse("diveops:staff-site-list")
        response = client.get(url)
        assert response.status_code == 200
        assert dive_site.name not in response.content.decode()


@pytest.mark.django_db
class TestDiveSiteDetailView:
    """Tests for DiveSiteDetailView."""

    def test_requires_staff_auth(self, client, regular_user, dive_site):
        """Non-staff users cannot access site detail."""
        client.force_login(regular_user)
        url = reverse("diveops:staff-site-detail", kwargs={"pk": dive_site.pk})
        response = client.get(url)
        assert response.status_code in [302, 403]

    def test_staff_can_access(self, client, staff_user, dive_site):
        """Staff users can access site detail."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-detail", kwargs={"pk": dive_site.pk})
        response = client.get(url)
        assert response.status_code == 200

    def test_shows_site_details(self, client, staff_user, dive_site):
        """Detail view shows site information."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-detail", kwargs={"pk": dive_site.pk})
        response = client.get(url)
        content = response.content.decode()
        assert dive_site.name in content
        assert str(dive_site.max_depth_meters) in content


@pytest.mark.django_db
class TestDiveSiteCreateView:
    """Tests for DiveSiteCreateView."""

    def test_requires_staff_auth(self, client, regular_user):
        """Non-staff users cannot access create form."""
        client.force_login(regular_user)
        url = reverse("diveops:staff-site-create")
        response = client.get(url)
        assert response.status_code in [302, 403]

    def test_staff_can_access_form(self, client, staff_user):
        """Staff users can access create form."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-create")
        response = client.get(url)
        assert response.status_code == 200

    def test_create_site_via_form(self, client, staff_user):
        """Submitting form creates site via service."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-create")

        data = {
            "name": "New Dive Site",
            "description": "A new dive site",
            "latitude": "20.3500",
            "longitude": "-87.0300",
            "max_depth_meters": "30",
            "difficulty": "advanced",
            "rating": "5",
            "tags": "reef,wall,deep",
        }

        response = client.post(url, data)

        # Should redirect on success
        assert response.status_code == 302

        # Site should be created
        site = DiveSite.objects.get(name="New Dive Site")
        assert site.max_depth_meters == 30
        assert site.difficulty == "advanced"
        assert site.rating == 5
        assert site.place.latitude == Decimal("20.3500")

    def test_create_site_with_certification_level(self, client, staff_user, cert_level_ow):
        """Form can set min_certification_level."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-create")

        data = {
            "name": "Advanced Site",
            "latitude": "20.3500",
            "longitude": "-87.0300",
            "max_depth_meters": "25",
            "difficulty": "intermediate",
            "min_certification_level": str(cert_level_ow.pk),
        }

        response = client.post(url, data)
        assert response.status_code == 302

        site = DiveSite.objects.get(name="Advanced Site")
        assert site.min_certification_level == cert_level_ow

    def test_create_emits_audit_event(self, client, staff_user):
        """Creating site emits audit event."""
        from django_audit_log.models import AuditLog

        client.force_login(staff_user)
        url = reverse("diveops:staff-site-create")

        initial_count = AuditLog.objects.count()

        data = {
            "name": "Audited Site",
            "latitude": "20.3500",
            "longitude": "-87.0300",
            "max_depth_meters": "20",
            "difficulty": "beginner",
        }

        client.post(url, data)

        assert AuditLog.objects.count() > initial_count
        audit = AuditLog.objects.order_by("-created_at").first()
        assert audit.action == "dive_site_created"


@pytest.mark.django_db
class TestDiveSiteUpdateView:
    """Tests for DiveSiteUpdateView."""

    def test_requires_staff_auth(self, client, regular_user, dive_site):
        """Non-staff users cannot access update form."""
        client.force_login(regular_user)
        url = reverse("diveops:staff-site-edit", kwargs={"pk": dive_site.pk})
        response = client.get(url)
        assert response.status_code in [302, 403]

    def test_staff_can_access_form(self, client, staff_user, dive_site):
        """Staff users can access update form."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-edit", kwargs={"pk": dive_site.pk})
        response = client.get(url)
        assert response.status_code == 200

    def test_form_prepopulated(self, client, staff_user, dive_site):
        """Update form is prepopulated with site data."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-edit", kwargs={"pk": dive_site.pk})
        response = client.get(url)
        content = response.content.decode()
        assert dive_site.name in content

    def test_update_site_via_form(self, client, staff_user, dive_site):
        """Submitting form updates site via service."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-edit", kwargs={"pk": dive_site.pk})

        data = {
            "name": "Updated Name",
            "description": dive_site.description,
            "latitude": str(dive_site.place.latitude),
            "longitude": str(dive_site.place.longitude),
            "max_depth_meters": "35",
            "difficulty": "advanced",
            "rating": "5",
            "tags": "updated,tags",
        }

        response = client.post(url, data)
        assert response.status_code == 302

        dive_site.refresh_from_db()
        assert dive_site.name == "Updated Name"
        assert dive_site.max_depth_meters == 35

    def test_update_coordinates(self, client, staff_user, dive_site):
        """Updating coordinates updates Place."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-edit", kwargs={"pk": dive_site.pk})
        place_pk = dive_site.place.pk

        data = {
            "name": dive_site.name,
            "latitude": "21.0000",
            "longitude": "-88.0000",
            "max_depth_meters": str(dive_site.max_depth_meters),
            "difficulty": dive_site.difficulty,
        }

        response = client.post(url, data)
        assert response.status_code == 302

        dive_site.refresh_from_db()
        # Same place, updated coords
        assert dive_site.place.pk == place_pk
        assert dive_site.place.latitude == Decimal("21.0000")
        assert dive_site.place.longitude == Decimal("-88.0000")


@pytest.mark.django_db
class TestDiveSiteDeleteView:
    """Tests for DiveSiteDeleteView."""

    def test_requires_staff_auth(self, client, regular_user, dive_site):
        """Non-staff users cannot delete sites."""
        client.force_login(regular_user)
        url = reverse("diveops:staff-site-delete", kwargs={"pk": dive_site.pk})
        response = client.post(url)
        assert response.status_code in [302, 403]

    def test_get_not_allowed(self, client, staff_user, dive_site):
        """GET request should show confirmation or redirect."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-delete", kwargs={"pk": dive_site.pk})
        response = client.get(url)
        # Either shows confirmation page (200) or method not allowed (405)
        assert response.status_code in [200, 405]

    def test_post_soft_deletes_site(self, client, staff_user, dive_site):
        """POST request soft deletes the site."""
        client.force_login(staff_user)
        url = reverse("diveops:staff-site-delete", kwargs={"pk": dive_site.pk})
        site_pk = dive_site.pk

        response = client.post(url)
        assert response.status_code == 302

        # Site should be soft deleted
        assert not DiveSite.objects.filter(pk=site_pk).exists()
        assert DiveSite.all_objects.filter(pk=site_pk).exists()

    def test_delete_emits_audit_event(self, client, staff_user, dive_site):
        """Deleting site emits audit event."""
        from django_audit_log.models import AuditLog

        client.force_login(staff_user)
        url = reverse("diveops:staff-site-delete", kwargs={"pk": dive_site.pk})

        initial_count = AuditLog.objects.count()

        client.post(url)

        assert AuditLog.objects.count() > initial_count
        audit = AuditLog.objects.order_by("-created_at").first()
        assert audit.action == "dive_site_deleted"


@pytest.mark.django_db
class TestDiveSiteForm:
    """Tests for DiveSiteForm."""

    def test_form_validates_required_fields(self):
        """Form requires name, latitude, longitude, max_depth, difficulty."""
        from primitives_testbed.diveops.forms import DiveSiteForm

        form = DiveSiteForm(data={})
        assert not form.is_valid()
        assert "name" in form.errors
        assert "latitude" in form.errors
        assert "longitude" in form.errors
        assert "max_depth_meters" in form.errors
        assert "difficulty" in form.errors

    def test_form_valid_data(self):
        """Form validates with correct data."""
        from primitives_testbed.diveops.forms import DiveSiteForm

        data = {
            "name": "Test Site",
            "latitude": "20.5000",
            "longitude": "-87.0000",
            "max_depth_meters": "25",
            "difficulty": "intermediate",
        }
        form = DiveSiteForm(data=data)
        assert form.is_valid(), form.errors

    def test_form_validates_rating_range(self):
        """Rating must be 1-5 or empty."""
        from primitives_testbed.diveops.forms import DiveSiteForm

        data = {
            "name": "Test Site",
            "latitude": "20.5000",
            "longitude": "-87.0000",
            "max_depth_meters": "25",
            "difficulty": "intermediate",
            "rating": "0",  # Invalid
        }
        form = DiveSiteForm(data=data)
        assert not form.is_valid()
        assert "rating" in form.errors

    def test_form_validates_difficulty_choices(self):
        """Difficulty must be valid choice."""
        from primitives_testbed.diveops.forms import DiveSiteForm

        data = {
            "name": "Test Site",
            "latitude": "20.5000",
            "longitude": "-87.0000",
            "max_depth_meters": "25",
            "difficulty": "invalid",
        }
        form = DiveSiteForm(data=data)
        assert not form.is_valid()
        assert "difficulty" in form.errors

    def test_form_save_creates_site(self, staff_user):
        """Form.save() creates site via service."""
        from primitives_testbed.diveops.forms import DiveSiteForm

        data = {
            "name": "Form Created Site",
            "latitude": "20.5000",
            "longitude": "-87.0000",
            "max_depth_meters": "25",
            "difficulty": "intermediate",
            "description": "Created via form",
        }
        form = DiveSiteForm(data=data)
        assert form.is_valid()

        site = form.save(actor=staff_user)
        assert site.pk is not None
        assert site.name == "Form Created Site"
        assert site.place is not None

    def test_form_save_update_mode(self, staff_user, dive_site):
        """Form.save() updates existing site."""
        from primitives_testbed.diveops.forms import DiveSiteForm

        data = {
            "name": "Updated via Form",
            "latitude": str(dive_site.place.latitude),
            "longitude": str(dive_site.place.longitude),
            "max_depth_meters": "30",
            "difficulty": "advanced",
        }
        form = DiveSiteForm(data=data, instance=dive_site)
        assert form.is_valid()

        site = form.save(actor=staff_user)
        assert site.pk == dive_site.pk
        assert site.name == "Updated via Form"
        assert site.max_depth_meters == 30

    def test_form_parses_tags(self):
        """Form parses comma-separated tags."""
        from primitives_testbed.diveops.forms import DiveSiteForm

        data = {
            "name": "Tagged Site",
            "latitude": "20.5000",
            "longitude": "-87.0000",
            "max_depth_meters": "25",
            "difficulty": "intermediate",
            "tags": "reef, coral, tropical",
        }
        form = DiveSiteForm(data=data)
        assert form.is_valid()
        assert form.cleaned_data["tags"] == ["reef", "coral", "tropical"]
