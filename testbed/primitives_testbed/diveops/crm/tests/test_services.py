"""Tests for CRM lead management services.

Tests cover:
- is_lead() function
- set_lead_status() creates events and updates person
- convert_to_diver() creates DiverProfile and sets converted fields
- add_lead_note() creates notes
- get_lead_timeline() combines events and notes
"""

import pytest
from django.contrib.auth import get_user_model

from django_parties.models import Person, LeadStatusEvent, LeadNote

from ...models import DiverProfile
from ..services import (
    is_lead,
    set_lead_status,
    convert_to_diver,
    add_lead_note,
    get_lead_notes,
    get_lead_timeline,
)

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
def lead(db):
    """Create a lead (Person with lead_status)."""
    return Person.objects.create(
        first_name="Jane",
        last_name="Prospect",
        email="jane@example.com",
        lead_status="new",
        lead_source="website",
    )


@pytest.fixture
def non_lead(db):
    """Create a non-lead Person (no lead_status)."""
    return Person.objects.create(
        first_name="Regular",
        last_name="Contact",
        email="regular@example.com",
    )


class TestIsLead:
    """Tests for is_lead() function."""

    def test_is_lead_returns_true_for_lead(self, lead):
        """Person with lead_status is a lead."""
        assert is_lead(lead) is True

    def test_is_lead_returns_false_for_non_lead(self, non_lead):
        """Person without lead_status is not a lead."""
        assert is_lead(non_lead) is False

    def test_is_lead_returns_true_for_all_statuses(self, db):
        """All lead statuses return True."""
        for status, _ in Person.LEAD_STATUS_CHOICES:
            person = Person.objects.create(
                first_name="Test",
                last_name=status,
                email=f"{status}@example.com",
                lead_status=status,
            )
            assert is_lead(person) is True


class TestSetLeadStatus:
    """Tests for set_lead_status() function."""

    def test_set_lead_status_updates_person(self, lead, staff_user):
        """Status change updates person.lead_status."""
        set_lead_status(lead, "contacted", actor=staff_user)
        lead.refresh_from_db()
        assert lead.lead_status == "contacted"

    def test_set_lead_status_creates_event(self, lead, staff_user):
        """Status change creates LeadStatusEvent."""
        event = set_lead_status(lead, "contacted", actor=staff_user)

        assert event is not None
        assert event.person == lead
        assert event.from_status == "new"
        assert event.to_status == "contacted"
        assert event.actor == staff_user

    def test_set_lead_status_with_note(self, lead, staff_user):
        """Status change can include a note."""
        event = set_lead_status(
            lead,
            "contacted",
            actor=staff_user,
            note="Called and left voicemail",
        )
        assert event.note == "Called and left voicemail"

    def test_set_lead_status_lost_with_reason(self, lead, staff_user):
        """Lost status saves lost_reason."""
        set_lead_status(
            lead,
            "lost",
            actor=staff_user,
            lost_reason="Not interested in diving",
        )
        lead.refresh_from_db()
        assert lead.lead_status == "lost"
        assert lead.lead_lost_reason == "Not interested in diving"

    def test_set_lead_status_invalid_status_raises(self, lead, staff_user):
        """Invalid status raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            set_lead_status(lead, "invalid_status", actor=staff_user)
        assert "Invalid status" in str(exc_info.value)

    def test_set_lead_status_without_actor(self, lead):
        """Status can be changed without an actor (system action)."""
        event = set_lead_status(lead, "contacted")
        assert event.actor is None

    def test_set_lead_status_from_none(self, db):
        """New lead (from_status=None) works correctly."""
        person = Person.objects.create(
            first_name="New",
            last_name="Lead",
            email="new@example.com",
            lead_status=None,
        )
        # Manually set to new first
        person.lead_status = "new"
        person.save()

        event = set_lead_status(person, "contacted")
        assert event.from_status == "new"
        assert event.to_status == "contacted"


class TestConvertToDiver:
    """Tests for convert_to_diver() function."""

    def test_convert_creates_diver_profile(self, lead, staff_user):
        """Convert creates a DiverProfile."""
        diver = convert_to_diver(lead, actor=staff_user)

        assert diver is not None
        assert diver.person == lead
        assert DiverProfile.objects.filter(person=lead).exists()

    def test_convert_sets_status_to_converted(self, lead, staff_user):
        """Convert sets lead_status to 'converted'."""
        convert_to_diver(lead, actor=staff_user)
        lead.refresh_from_db()
        assert lead.lead_status == "converted"

    def test_convert_sets_converted_timestamp(self, lead, staff_user):
        """Convert sets lead_converted_at timestamp."""
        assert lead.lead_converted_at is None
        convert_to_diver(lead, actor=staff_user)
        lead.refresh_from_db()
        assert lead.lead_converted_at is not None

    def test_convert_creates_status_event(self, lead, staff_user):
        """Convert creates a LeadStatusEvent."""
        convert_to_diver(lead, actor=staff_user)

        event = LeadStatusEvent.objects.filter(
            person=lead, to_status="converted"
        ).first()
        assert event is not None
        assert event.actor == staff_user

    def test_convert_non_lead_raises(self, non_lead, staff_user):
        """Converting non-lead raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            convert_to_diver(non_lead, actor=staff_user)
        assert "not a lead" in str(exc_info.value)

    def test_convert_existing_diver_returns_existing(self, lead, staff_user):
        """Converting already-converted lead returns existing DiverProfile."""
        # First conversion
        diver1 = convert_to_diver(lead, actor=staff_user)

        # Reset status for second conversion attempt
        lead.lead_status = "qualified"
        lead.save()

        # Second conversion
        diver2 = convert_to_diver(lead, actor=staff_user)

        assert diver1.pk == diver2.pk

    def test_convert_parses_experience_from_notes(self, db, staff_user):
        """Convert parses experience level from notes."""
        person = Person.objects.create(
            first_name="Experienced",
            last_name="Diver",
            email="exp@example.com",
            lead_status="qualified",
            notes="Lead from website. Experience: 10-50 dives",
        )
        diver = convert_to_diver(person, actor=staff_user)
        assert diver.total_dives == 30  # 10-50 maps to 30


class TestAddLeadNote:
    """Tests for add_lead_note() function."""

    def test_add_note_creates_lead_note(self, lead, staff_user):
        """add_lead_note creates a LeadNote record."""
        note = add_lead_note(lead, "Called customer, very interested", author=staff_user)

        assert note is not None
        assert note.person == lead
        assert note.body == "Called customer, very interested"
        assert note.author == staff_user

    def test_add_note_without_author(self, lead):
        """Notes can be added without an author."""
        note = add_lead_note(lead, "System generated note")
        assert note.author is None

    def test_multiple_notes_allowed(self, lead, staff_user):
        """Multiple notes can be added to same lead."""
        add_lead_note(lead, "First call", author=staff_user)
        add_lead_note(lead, "Second call", author=staff_user)
        add_lead_note(lead, "Third call", author=staff_user)

        assert LeadNote.objects.filter(person=lead).count() == 3


class TestGetLeadNotes:
    """Tests for get_lead_notes() function."""

    def test_get_notes_returns_all_notes(self, lead, staff_user):
        """get_lead_notes returns all notes for a lead."""
        add_lead_note(lead, "Note 1", author=staff_user)
        add_lead_note(lead, "Note 2", author=staff_user)

        notes = get_lead_notes(lead)
        assert notes.count() == 2

    def test_get_notes_ordered_newest_first(self, lead, staff_user):
        """Notes are returned newest first."""
        add_lead_note(lead, "First note", author=staff_user)
        add_lead_note(lead, "Second note", author=staff_user)

        notes = list(get_lead_notes(lead))
        assert notes[0].body == "Second note"
        assert notes[1].body == "First note"

    def test_get_notes_empty_for_new_lead(self, lead):
        """New lead has no notes."""
        notes = get_lead_notes(lead)
        assert notes.count() == 0


class TestGetLeadTimeline:
    """Tests for get_lead_timeline() function."""

    def test_timeline_includes_status_events(self, lead, staff_user):
        """Timeline includes status change events."""
        set_lead_status(lead, "contacted", actor=staff_user)

        timeline = get_lead_timeline(lead)
        status_events = [e for e in timeline if e["type"] == "status_change"]
        assert len(status_events) == 1

    def test_timeline_includes_notes(self, lead, staff_user):
        """Timeline includes notes."""
        add_lead_note(lead, "Test note", author=staff_user)

        timeline = get_lead_timeline(lead)
        notes = [e for e in timeline if e["type"] == "note"]
        assert len(notes) == 1

    def test_timeline_combined_and_sorted(self, lead, staff_user):
        """Timeline combines events and notes, sorted by date."""
        # Create some events and notes
        set_lead_status(lead, "contacted", actor=staff_user)
        add_lead_note(lead, "First note", author=staff_user)
        set_lead_status(lead, "qualified", actor=staff_user)
        add_lead_note(lead, "Second note", author=staff_user)

        timeline = get_lead_timeline(lead)

        # Should have 4 items total
        assert len(timeline) == 4

        # Should be sorted newest first (last item should be oldest)
        for i in range(len(timeline) - 1):
            assert timeline[i]["created_at"] >= timeline[i + 1]["created_at"]
