"""Tests for diveops forms."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


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
