"""Forms for diveops staff portal."""

from django import forms

from .models import Booking, DiverProfile, DiveTrip


class BookDiverForm(forms.Form):
    """Form to book a diver on a trip.

    Displays available divers (those not already booked on this trip).
    """

    diver = forms.ModelChoiceField(
        queryset=DiverProfile.objects.none(),
        label="Select Diver",
        help_text="Choose a diver to book on this trip.",
    )

    def __init__(self, *args, trip: DiveTrip, **kwargs):
        super().__init__(*args, **kwargs)
        self.trip = trip

        # Get divers already booked on this trip (excluding cancelled)
        booked_diver_ids = Booking.objects.filter(
            trip=trip,
            status__in=["pending", "confirmed", "checked_in"],
        ).values_list("diver_id", flat=True)

        # Show all divers except those already booked
        self.fields["diver"].queryset = DiverProfile.objects.select_related(
            "person"
        ).exclude(pk__in=booked_diver_ids)
