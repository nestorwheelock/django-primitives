"""Tests for diveops forms."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


@pytest.mark.django_db
class TestDiverForm:
    """Tests for DiverForm (creates Person + DiverProfile)."""

    def test_form_has_person_fields(self):
        """DiverForm has first_name, last_name, email fields."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm()
        assert "first_name" in form.fields
        assert "last_name" in form.fields
        assert "email" in form.fields

    def test_form_has_certification_fields(self):
        """DiverForm has certification fields."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm()
        assert "certification_level" in form.fields
        assert "certification_agency" in form.fields
        assert "certification_number" in form.fields
        assert "certification_date" in form.fields

    def test_form_has_experience_fields(self):
        """DiverForm has experience and medical fields."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm()
        assert "total_dives" in form.fields
        assert "medical_clearance_date" in form.fields
        assert "medical_clearance_valid_until" in form.fields

    def test_form_valid_with_required_fields(self, padi_agency):
        """DiverForm is valid with all required fields."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm(data={
            "first_name": "Alice",
            "last_name": "Diver",
            "email": "alice@example.com",
            "certification_level": "ow",
            "certification_agency": str(padi_agency.pk),
            "certification_number": "12345",
            "certification_date": date.today() - timedelta(days=30),
            "total_dives": 10,
        })
        assert form.is_valid(), form.errors

    def test_form_creates_person_and_profile(self, ssi_agency):
        """DiverForm.save() creates both Person and DiverProfile."""
        from django_parties.models import Person
        from primitives_testbed.diveops.forms import DiverForm
        from primitives_testbed.diveops.models import DiverProfile

        form = DiverForm(data={
            "first_name": "Bob",
            "last_name": "Swimmer",
            "email": "bob@example.com",
            "certification_level": "aow",
            "certification_agency": str(ssi_agency.pk),
            "certification_number": "98765",
            "certification_date": date.today() - timedelta(days=180),
            "total_dives": 25,
        })
        assert form.is_valid(), form.errors

        diver = form.save()

        assert isinstance(diver, DiverProfile)
        assert diver.pk is not None
        assert diver.person.first_name == "Bob"
        assert diver.person.last_name == "Swimmer"
        assert diver.person.email == "bob@example.com"
        assert diver.certification_level == "aow"
        assert diver.certification_agency == ssi_agency
        assert diver.total_dives == 25

    def test_form_email_must_be_unique(self, padi_agency):
        """DiverForm rejects duplicate email for new diver."""
        from django_parties.models import Person
        from primitives_testbed.diveops.forms import DiverForm

        # Create existing person
        Person.objects.create(
            first_name="Existing",
            last_name="Person",
            email="existing@example.com",
        )

        form = DiverForm(data={
            "first_name": "New",
            "last_name": "Person",
            "email": "existing@example.com",  # Duplicate
            "certification_level": "ow",
            "certification_agency": str(padi_agency.pk),
            "certification_number": "11111",
            "certification_date": date.today(),
            "total_dives": 0,
        })
        assert not form.is_valid()
        assert "email" in form.errors

    def test_form_edit_existing_diver(self, diver_profile, padi_agency):
        """DiverForm can edit an existing diver."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm(instance=diver_profile, data={
            "first_name": "John",
            "last_name": "Diver",
            "email": "john@example.com",
            "certification_level": "rescue",  # Upgraded
            "certification_agency": str(padi_agency.pk),
            "certification_number": "12345",
            "certification_date": diver_profile.certification_date,
            "total_dives": 75,  # More dives
        })
        assert form.is_valid(), form.errors

        diver = form.save()
        assert diver.pk == diver_profile.pk
        assert diver.certification_level == "rescue"
        assert diver.total_dives == 75

    def test_form_edit_allows_same_email(self, diver_profile, padi_agency):
        """Editing diver can keep the same email."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm(instance=diver_profile, data={
            "first_name": "John",
            "last_name": "Diver",
            "email": "john@example.com",  # Same email
            "certification_level": "aow",
            "certification_agency": str(padi_agency.pk),
            "certification_number": "12345",
            "certification_date": diver_profile.certification_date,
            "total_dives": 55,
        })
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestBookDiverForm:
    """Tests for BookDiverForm."""

    def test_form_has_diver_field(self, dive_trip):
        """BookDiverForm has a diver selection field."""
        from primitives_testbed.diveops.forms import BookDiverForm

        form = BookDiverForm(trip=dive_trip)
        assert "diver" in form.fields

    def test_form_shows_available_divers(self, dive_trip, diver_profile, beginner_diver):
        """Form shows divers who are not already booked."""
        from primitives_testbed.diveops.forms import BookDiverForm

        form = BookDiverForm(trip=dive_trip)
        diver_pks = [d.pk for d in form.fields["diver"].queryset]

        assert diver_profile.pk in diver_pks
        assert beginner_diver.pk in diver_pks

    def test_form_excludes_already_booked_divers(self, dive_trip, diver_profile, user):
        """Form excludes divers who already have an active booking."""
        from primitives_testbed.diveops.forms import BookDiverForm
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        form = BookDiverForm(trip=dive_trip)
        diver_pks = [d.pk for d in form.fields["diver"].queryset]

        assert diver_profile.pk not in diver_pks

    def test_form_includes_cancelled_booking_divers(self, dive_trip, diver_profile, user):
        """Form includes divers whose previous booking was cancelled."""
        from primitives_testbed.diveops.forms import BookDiverForm
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="cancelled",
            booked_by=user,
        )

        form = BookDiverForm(trip=dive_trip)
        diver_pks = [d.pk for d in form.fields["diver"].queryset]

        assert diver_profile.pk in diver_pks

    def test_form_valid_with_eligible_diver(self, dive_trip, diver_profile):
        """Form is valid when selecting an eligible diver."""
        from primitives_testbed.diveops.forms import BookDiverForm

        form = BookDiverForm(trip=dive_trip, data={"diver": diver_profile.pk})
        assert form.is_valid()

    def test_form_displays_diver_name_and_cert(self, dive_trip, diver_profile):
        """Form displays diver name and certification level."""
        from primitives_testbed.diveops.forms import BookDiverForm

        form = BookDiverForm(trip=dive_trip)
        choices = list(form.fields["diver"].queryset)

        # Should have at least one choice
        assert len(choices) > 0
        # The model should have __str__ that shows name and cert
        choice_str = str(choices[0])
        assert diver_profile.person.first_name in choice_str or "Advanced" in choice_str
