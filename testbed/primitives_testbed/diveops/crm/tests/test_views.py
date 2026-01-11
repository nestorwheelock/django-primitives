"""Tests for CRM lead views.

Tests cover:
- List view filters (status, source, search, combined)
- Detail view (timeline, notes)
- Status update view (POST status changes)
- Add note view (POST notes)
- Convert to diver view (GET confirmation, POST conversion)
"""

import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from django_parties.models import Person, LeadStatusEvent, LeadNote
from ...models import DiverProfile

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user for testing."""
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def staff_client(staff_user):
    """Create a logged-in staff client."""
    client = Client()
    client.login(username="staff", password="testpass123")
    return client


@pytest.fixture
def leads(db):
    """Create a set of leads with various statuses and sources."""
    leads = []

    # New leads from different sources
    leads.append(Person.objects.create(
        first_name="Alice",
        last_name="New",
        email="alice@example.com",
        phone="+1111111111",
        lead_status="new",
        lead_source="website",
    ))
    leads.append(Person.objects.create(
        first_name="Bob",
        last_name="Fresh",
        email="bob@example.com",
        phone="+2222222222",
        lead_status="new",
        lead_source="referral",
    ))

    # Contacted leads
    leads.append(Person.objects.create(
        first_name="Carol",
        last_name="Contacted",
        email="carol@example.com",
        phone="+3333333333",
        lead_status="contacted",
        lead_source="website",
    ))

    # Qualified lead
    leads.append(Person.objects.create(
        first_name="David",
        last_name="Qualified",
        email="david@example.com",
        phone="+4444444444",
        lead_status="qualified",
        lead_source="walk_in",
    ))

    # Converted lead
    leads.append(Person.objects.create(
        first_name="Eve",
        last_name="Converted",
        email="eve@example.com",
        lead_status="converted",
        lead_source="website",
    ))

    # Lost lead
    leads.append(Person.objects.create(
        first_name="Frank",
        last_name="Lost",
        email="frank@example.com",
        lead_status="lost",
        lead_source="partner",
        lead_lost_reason="Not interested",
    ))

    return leads


@pytest.fixture
def non_lead(db):
    """Create a non-lead Person (no lead_status)."""
    return Person.objects.create(
        first_name="Regular",
        last_name="Person",
        email="regular@example.com",
    )


class TestLeadListStatusFilter:
    """Tests for status filter on lead list."""

    def test_filter_by_new_status(self, staff_client, leads):
        """Filter shows only new leads."""
        url = reverse("diveops:lead-list") + "?status=new"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 2
        for lead in result_leads:
            assert lead.lead_status == "new"

    def test_filter_by_contacted_status(self, staff_client, leads):
        """Filter shows only contacted leads."""
        url = reverse("diveops:lead-list") + "?status=contacted"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].lead_status == "contacted"

    def test_filter_by_qualified_status(self, staff_client, leads):
        """Filter shows only qualified leads."""
        url = reverse("diveops:lead-list") + "?status=qualified"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].lead_status == "qualified"

    def test_filter_by_converted_status(self, staff_client, leads):
        """Filter shows only converted leads."""
        url = reverse("diveops:lead-list") + "?status=converted"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].lead_status == "converted"

    def test_filter_by_lost_status(self, staff_client, leads):
        """Filter shows only lost leads."""
        url = reverse("diveops:lead-list") + "?status=lost"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].lead_status == "lost"

    def test_no_status_filter_shows_all(self, staff_client, leads):
        """No status filter shows all leads."""
        url = reverse("diveops:lead-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 6


class TestLeadListSourceFilter:
    """Tests for source filter on lead list."""

    def test_filter_by_website_source(self, staff_client, leads):
        """Filter shows only leads from website."""
        url = reverse("diveops:lead-list") + "?source=website"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 3
        for lead in result_leads:
            assert lead.lead_source == "website"

    def test_filter_by_referral_source(self, staff_client, leads):
        """Filter shows only leads from referrals."""
        url = reverse("diveops:lead-list") + "?source=referral"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].lead_source == "referral"

    def test_filter_by_walk_in_source(self, staff_client, leads):
        """Filter shows only walk-in leads."""
        url = reverse("diveops:lead-list") + "?source=walk_in"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].lead_source == "walk_in"


class TestLeadListSearchFilter:
    """Tests for search filter on lead list."""

    def test_search_by_first_name(self, staff_client, leads):
        """Search finds leads by first name."""
        url = reverse("diveops:lead-list") + "?q=Alice"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].first_name == "Alice"

    def test_search_by_last_name(self, staff_client, leads):
        """Search finds leads by last name."""
        url = reverse("diveops:lead-list") + "?q=Qualified"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].last_name == "Qualified"

    def test_search_by_email(self, staff_client, leads):
        """Search finds leads by email."""
        url = reverse("diveops:lead-list") + "?q=carol@"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].email == "carol@example.com"

    def test_search_by_phone(self, staff_client, leads):
        """Search finds leads by phone number."""
        url = reverse("diveops:lead-list") + "?q=4444"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].phone == "+4444444444"

    def test_search_case_insensitive(self, staff_client, leads):
        """Search is case insensitive."""
        url = reverse("diveops:lead-list") + "?q=ALICE"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].first_name == "Alice"

    def test_search_no_results(self, staff_client, leads):
        """Search with no matches returns empty list."""
        url = reverse("diveops:lead-list") + "?q=nonexistent"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 0


class TestLeadListCombinedFilters:
    """Tests for combining multiple filters."""

    def test_status_and_source_combined(self, staff_client, leads):
        """Status + source filter combined."""
        url = reverse("diveops:lead-list") + "?status=new&source=website"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].lead_status == "new"
        assert result_leads[0].lead_source == "website"

    def test_status_and_search_combined(self, staff_client, leads):
        """Status + search filter combined."""
        url = reverse("diveops:lead-list") + "?status=new&q=Alice"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1
        assert result_leads[0].first_name == "Alice"
        assert result_leads[0].lead_status == "new"

    def test_all_filters_combined(self, staff_client, leads):
        """All filters combined."""
        url = reverse("diveops:lead-list") + "?status=new&source=website&q=Alice"
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 1


class TestLeadListContext:
    """Tests for context data in lead list view."""

    def test_context_includes_status_choices(self, staff_client, leads):
        """Context includes status choices for dropdown."""
        url = reverse("diveops:lead-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "status_choices" in response.context
        choices = dict(response.context["status_choices"])
        assert "new" in choices
        assert "contacted" in choices
        assert "qualified" in choices

    def test_context_includes_source_choices(self, staff_client, leads):
        """Context includes source choices for dropdown."""
        url = reverse("diveops:lead-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "source_choices" in response.context

    def test_context_includes_current_filters(self, staff_client, leads):
        """Context includes current filter values."""
        url = reverse("diveops:lead-list") + "?status=new&source=website&q=test"
        response = staff_client.get(url)

        assert response.status_code == 200
        assert response.context["current_status"] == "new"
        assert response.context["current_source"] == "website"
        assert response.context["search_query"] == "test"

    def test_context_includes_summary_counts(self, staff_client, leads):
        """Context includes summary counts by status."""
        url = reverse("diveops:lead-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert response.context["total_leads"] == 6
        assert response.context["new_leads"] == 2
        assert response.context["contacted_leads"] == 1
        assert response.context["qualified_leads"] == 1
        assert response.context["converted_leads"] == 1
        assert response.context["lost_leads"] == 1


class TestLeadListExclusion:
    """Tests for proper exclusion of non-leads and deleted records."""

    def test_excludes_non_leads(self, staff_client, leads, non_lead):
        """List excludes persons without lead_status."""
        url = reverse("diveops:lead-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 6
        assert non_lead not in result_leads

    def test_excludes_deleted_leads(self, staff_client, leads):
        """List excludes soft-deleted leads."""
        from django.utils import timezone

        # Soft delete one lead
        leads[0].deleted_at = timezone.now()
        leads[0].save()

        url = reverse("diveops:lead-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        result_leads = list(response.context["leads"])
        assert len(result_leads) == 5
        assert leads[0] not in result_leads


class TestLeadListAccess:
    """Tests for access control on lead list."""

    def test_anonymous_user_redirected(self, db, leads):
        """Anonymous users are redirected to login."""
        client = Client()
        url = reverse("diveops:lead-list")
        response = client.get(url)

        assert response.status_code == 302
        assert "/accounts/login/" in response.url or "/login/" in response.url

    def test_staff_user_has_access(self, staff_client, leads):
        """Staff users can access the list."""
        url = reverse("diveops:lead-list")
        response = staff_client.get(url)

        assert response.status_code == 200


class TestLeadDetailView:
    """Tests for lead detail view."""

    def test_detail_view_shows_lead(self, staff_client, leads):
        """Detail view shows lead information."""
        lead = leads[0]
        url = reverse("diveops:lead-detail", kwargs={"pk": lead.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert response.context["lead"] == lead

    def test_detail_view_includes_timeline(self, staff_client, leads, staff_user):
        """Detail view includes timeline with status events and notes."""
        from ..services import set_lead_status, add_lead_note

        lead = leads[0]
        set_lead_status(lead, "contacted", actor=staff_user)
        add_lead_note(lead, "Test note", author=staff_user)

        url = reverse("diveops:lead-detail", kwargs={"pk": lead.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "timeline" in response.context
        assert len(response.context["timeline"]) == 2

    def test_detail_view_404_for_non_lead(self, staff_client, non_lead):
        """Detail view returns 404 for non-lead person."""
        url = reverse("diveops:lead-detail", kwargs={"pk": non_lead.pk})
        response = staff_client.get(url)

        assert response.status_code == 404

    def test_detail_view_404_for_deleted_lead(self, staff_client, leads):
        """Detail view returns 404 for deleted lead."""
        from django.utils import timezone

        lead = leads[0]
        lead.deleted_at = timezone.now()
        lead.save()

        url = reverse("diveops:lead-detail", kwargs={"pk": lead.pk})
        response = staff_client.get(url)

        assert response.status_code == 404


class TestLeadStatusUpdateView:
    """Tests for lead status update view."""

    def test_status_update_changes_status(self, staff_client, leads):
        """POST updates the lead status."""
        lead = leads[0]  # new status
        url = reverse("diveops:lead-status-update", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"status": "contacted"})

        assert response.status_code == 302  # redirect
        lead.refresh_from_db()
        assert lead.lead_status == "contacted"

    def test_status_update_creates_event(self, staff_client, leads, staff_user):
        """Status update creates LeadStatusEvent."""
        lead = leads[0]
        url = reverse("diveops:lead-status-update", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"status": "contacted"})

        assert response.status_code == 302
        event = LeadStatusEvent.objects.filter(person=lead).first()
        assert event is not None
        assert event.from_status == "new"
        assert event.to_status == "contacted"

    def test_status_update_with_note(self, staff_client, leads):
        """Status update can include a note."""
        lead = leads[0]
        url = reverse("diveops:lead-status-update", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {
            "status": "contacted",
            "note": "Left voicemail"
        })

        assert response.status_code == 302
        event = LeadStatusEvent.objects.filter(person=lead).first()
        assert event.note == "Left voicemail"

    def test_status_update_lost_saves_reason(self, staff_client, leads):
        """Setting status to lost saves the lost reason."""
        lead = leads[0]
        url = reverse("diveops:lead-status-update", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {
            "status": "lost",
            "note": "Not interested in diving"
        })

        assert response.status_code == 302
        lead.refresh_from_db()
        assert lead.lead_status == "lost"
        assert lead.lead_lost_reason == "Not interested in diving"

    def test_status_update_redirects_to_detail(self, staff_client, leads):
        """Status update redirects back to lead detail."""
        lead = leads[0]
        url = reverse("diveops:lead-status-update", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"status": "contacted"})

        assert response.status_code == 302
        assert f"/crm/leads/{lead.pk}/" in response.url

    def test_status_update_invalid_status_shows_error(self, staff_client, leads):
        """Invalid status shows error message."""
        lead = leads[0]
        url = reverse("diveops:lead-status-update", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"status": "invalid_status"}, follow=True)

        assert response.status_code == 200
        # Status should remain unchanged
        lead.refresh_from_db()
        assert lead.lead_status == "new"


class TestLeadAddNoteView:
    """Tests for add note view."""

    def test_add_note_creates_note(self, staff_client, leads, staff_user):
        """POST creates a note for the lead."""
        lead = leads[0]
        url = reverse("diveops:lead-add-note", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"body": "Called customer today"})

        assert response.status_code == 302
        note = LeadNote.objects.filter(person=lead).first()
        assert note is not None
        assert note.body == "Called customer today"

    def test_add_note_sets_author(self, staff_client, leads, staff_user):
        """Note author is set to current user."""
        lead = leads[0]
        url = reverse("diveops:lead-add-note", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"body": "Test note"})

        assert response.status_code == 302
        note = LeadNote.objects.filter(person=lead).first()
        assert note.author == staff_user

    def test_add_note_redirects_to_detail(self, staff_client, leads):
        """Add note redirects back to lead detail."""
        lead = leads[0]
        url = reverse("diveops:lead-add-note", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"body": "Test note"})

        assert response.status_code == 302
        assert f"/crm/leads/{lead.pk}/" in response.url

    def test_add_note_empty_body_rejected(self, staff_client, leads):
        """Empty note body is rejected."""
        lead = leads[0]
        url = reverse("diveops:lead-add-note", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"body": ""}, follow=True)

        assert response.status_code == 200
        assert LeadNote.objects.filter(person=lead).count() == 0

    def test_add_note_whitespace_only_rejected(self, staff_client, leads):
        """Whitespace-only note body is rejected."""
        lead = leads[0]
        url = reverse("diveops:lead-add-note", kwargs={"pk": lead.pk})
        response = staff_client.post(url, {"body": "   "}, follow=True)

        assert response.status_code == 200
        assert LeadNote.objects.filter(person=lead).count() == 0


class TestConvertLeadToDiverView:
    """Tests for convert lead to diver view."""

    def test_convert_get_shows_confirmation(self, staff_client, leads):
        """GET shows confirmation page."""
        lead = leads[0]
        url = reverse("diveops:lead-convert", kwargs={"pk": lead.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert response.context["lead"] == lead

    def test_convert_post_creates_diver_profile(self, staff_client, leads):
        """POST creates DiverProfile."""
        lead = leads[0]
        url = reverse("diveops:lead-convert", kwargs={"pk": lead.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        diver = DiverProfile.objects.filter(person=lead).first()
        assert diver is not None

    def test_convert_post_sets_status_to_converted(self, staff_client, leads):
        """POST sets lead_status to converted."""
        lead = leads[0]
        url = reverse("diveops:lead-convert", kwargs={"pk": lead.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        lead.refresh_from_db()
        assert lead.lead_status == "converted"

    def test_convert_post_sets_converted_timestamp(self, staff_client, leads):
        """POST sets lead_converted_at timestamp."""
        lead = leads[0]
        assert lead.lead_converted_at is None

        url = reverse("diveops:lead-convert", kwargs={"pk": lead.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        lead.refresh_from_db()
        assert lead.lead_converted_at is not None

    def test_convert_post_creates_status_event(self, staff_client, leads):
        """POST creates LeadStatusEvent for conversion."""
        lead = leads[0]
        url = reverse("diveops:lead-convert", kwargs={"pk": lead.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        event = LeadStatusEvent.objects.filter(
            person=lead, to_status="converted"
        ).first()
        assert event is not None

    def test_convert_post_redirects_to_diver_detail(self, staff_client, leads):
        """POST redirects to diver detail page."""
        lead = leads[0]
        url = reverse("diveops:lead-convert", kwargs={"pk": lead.pk})
        response = staff_client.post(url)

        assert response.status_code == 302
        diver = DiverProfile.objects.get(person=lead)
        assert f"/divers/{diver.pk}/" in response.url

    def test_convert_existing_diver_redirects(self, staff_client, leads):
        """Converting already-converted lead redirects to existing diver."""
        lead = leads[0]
        # First conversion
        diver = DiverProfile.objects.create(person=lead)

        url = reverse("diveops:lead-convert", kwargs={"pk": lead.pk})
        response = staff_client.get(url)

        assert response.status_code == 302
        assert f"/divers/{diver.pk}/" in response.url

    def test_convert_non_lead_404(self, staff_client, non_lead):
        """Converting non-lead returns 404."""
        url = reverse("diveops:lead-convert", kwargs={"pk": non_lead.pk})
        response = staff_client.get(url)

        assert response.status_code == 404
