"""Staff portal views for diveops."""

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, View

from django_portal_ui.mixins import StaffPortalMixin

from .models import Booking, DiverProfile, DiveTrip, TripRoster
from .selectors import get_trip_with_roster, list_upcoming_trips


class TripListView(StaffPortalMixin, ListView):
    """List upcoming dive trips for staff."""

    model = DiveTrip
    template_name = "diveops/staff/trip_list.html"
    context_object_name = "trips"

    def get_queryset(self):
        """Return upcoming trips with booking counts."""
        return list_upcoming_trips()


class TripDetailView(StaffPortalMixin, DetailView):
    """View trip details with roster and bookings."""

    model = DiveTrip
    template_name = "diveops/staff/trip_detail.html"
    context_object_name = "trip"

    def get_object(self, queryset=None):
        """Get trip with prefetched related data."""
        pk = self.kwargs.get("pk")
        trip = get_trip_with_roster(pk)
        if trip is None:
            from django.http import Http404
            raise Http404("Trip not found")
        return trip

    def get_context_data(self, **kwargs):
        """Add bookings and roster to context."""
        context = super().get_context_data(**kwargs)
        trip = self.object

        # Get bookings for this trip
        context["bookings"] = trip.bookings.select_related(
            "diver__person"
        ).order_by("-created_at")

        # Get roster entries
        context["roster"] = trip.roster.select_related(
            "diver__person", "booking"
        ).order_by("checked_in_at")

        return context


class BookDiverView(StaffPortalMixin, FormView):
    """Book a diver on a trip (placeholder - see T-003)."""

    template_name = "diveops/staff/book_diver.html"

    def get_success_url(self):
        return reverse("diveops:trip-detail", kwargs={"pk": self.kwargs["trip_pk"]})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["trip"] = get_object_or_404(DiveTrip, pk=self.kwargs["trip_pk"])
        return context

    def get_form_class(self):
        # Placeholder - will be implemented in T-003
        from django import forms

        class PlaceholderForm(forms.Form):
            pass

        return PlaceholderForm


class CheckInView(StaffPortalMixin, View):
    """Check in a booking (POST only - placeholder for T-004)."""

    http_method_names = ["post"]

    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        messages.info(request, "Check-in functionality coming in T-004")
        return HttpResponseRedirect(
            reverse("diveops:trip-detail", kwargs={"pk": booking.trip.pk})
        )


class StartTripView(StaffPortalMixin, View):
    """Start a trip (POST only - placeholder for T-004)."""

    http_method_names = ["post"]

    def post(self, request, pk):
        trip = get_object_or_404(DiveTrip, pk=pk)
        messages.info(request, "Start trip functionality coming in T-004")
        return HttpResponseRedirect(
            reverse("diveops:trip-detail", kwargs={"pk": trip.pk})
        )


class CompleteTripView(StaffPortalMixin, View):
    """Complete a trip (POST only - placeholder for T-004)."""

    http_method_names = ["post"]

    def post(self, request, pk):
        trip = get_object_or_404(DiveTrip, pk=pk)
        messages.info(request, "Complete trip functionality coming in T-004")
        return HttpResponseRedirect(
            reverse("diveops:trip-detail", kwargs={"pk": trip.pk})
        )
