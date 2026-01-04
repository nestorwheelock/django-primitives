"""Staff portal views for diveops."""

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView, View

from django_portal_ui.mixins import StaffPortalMixin

from .forms import DiverForm
from .models import Booking, DiverProfile, DiveTrip, TripRoster
from .selectors import get_trip_with_roster, list_upcoming_trips


class DashboardView(StaffPortalMixin, TemplateView):
    """Staff dashboard for diveops."""

    template_name = "diveops/staff/dashboard.html"

    def get_context_data(self, **kwargs):
        """Add dashboard stats to context."""
        context = super().get_context_data(**kwargs)

        # Upcoming trips
        upcoming_trips = list_upcoming_trips(limit=5)
        context["upcoming_trips"] = upcoming_trips
        context["upcoming_trips_count"] = DiveTrip.objects.filter(
            departure_time__gt=timezone.now(),
            status__in=["scheduled", "boarding"],
        ).count()

        # Active divers
        context["diver_count"] = DiverProfile.objects.count()

        # Today's trips
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        context["todays_trips"] = DiveTrip.objects.filter(
            departure_time__gte=today_start,
            departure_time__lt=today_end,
        ).select_related("dive_site").order_by("departure_time")

        # Pending bookings
        context["pending_bookings_count"] = Booking.objects.filter(
            status="pending"
        ).count()

        return context


class DiverListView(StaffPortalMixin, ListView):
    """List all divers for staff."""

    model = DiverProfile
    template_name = "diveops/staff/diver_list.html"
    context_object_name = "divers"

    def get_queryset(self):
        """Return divers with person data."""
        return DiverProfile.objects.select_related("person").order_by(
            "person__last_name", "person__first_name"
        )


class CreateDiverView(StaffPortalMixin, FormView):
    """Create a new diver."""

    template_name = "diveops/staff/diver_form.html"
    form_class = DiverForm
    success_url = reverse_lazy("diveops:diver-list")

    def form_valid(self, form):
        diver = form.save()
        messages.success(
            self.request,
            f"Diver {diver.person.first_name} {diver.person.last_name} has been created.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = True
        context["page_title"] = "Add Diver"
        return context


class EditDiverView(StaffPortalMixin, FormView):
    """Edit an existing diver."""

    template_name = "diveops/staff/diver_form.html"
    form_class = DiverForm
    success_url = reverse_lazy("diveops:diver-list")

    def dispatch(self, request, *args, **kwargs):
        self.diver = get_object_or_404(
            DiverProfile.objects.select_related("person"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.diver
        return kwargs

    def form_valid(self, form):
        diver = form.save()
        messages.success(
            self.request,
            f"Diver {diver.person.first_name} {diver.person.last_name} has been updated.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        context["page_title"] = "Edit Diver"
        context["diver"] = self.diver
        return context


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
    """Book a diver on a trip."""

    template_name = "diveops/staff/book_diver.html"

    def dispatch(self, request, *args, **kwargs):
        self.trip = get_object_or_404(DiveTrip, pk=kwargs["trip_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("diveops:trip-detail", kwargs={"pk": self.kwargs["trip_pk"]})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["trip"] = self.trip
        return context

    def get_form_class(self):
        from .forms import BookDiverForm
        return BookDiverForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["trip"] = self.trip
        return kwargs

    def form_valid(self, form):
        from .decisioning import can_diver_join_trip
        from .services import book_trip

        diver = form.cleaned_data["diver"]

        # Check eligibility
        result = can_diver_join_trip(diver, self.trip)
        if not result.allowed:
            # Add eligibility result to context and re-render
            context = self.get_context_data(form=form)
            context["eligibility_result"] = result
            return self.render_to_response(context)

        # Book the diver
        book_trip(self.trip, diver, self.request.user)
        messages.success(
            self.request, f"{diver.person.first_name} has been booked on this trip."
        )
        return HttpResponseRedirect(self.get_success_url())


class CheckInView(StaffPortalMixin, View):
    """Check in a booking."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from .services import check_in

        booking = get_object_or_404(Booking, pk=pk)
        check_in(booking, request.user)
        messages.success(
            request, f"{booking.diver.person.first_name} has been checked in."
        )
        return HttpResponseRedirect(
            reverse("diveops:trip-detail", kwargs={"pk": booking.trip.pk})
        )


class StartTripView(StaffPortalMixin, View):
    """Start a trip."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from .services import start_trip

        trip = get_object_or_404(DiveTrip, pk=pk)
        start_trip(trip, request.user)
        messages.success(request, "Trip has been started.")
        return HttpResponseRedirect(
            reverse("diveops:trip-detail", kwargs={"pk": trip.pk})
        )


class CompleteTripView(StaffPortalMixin, View):
    """Complete a trip."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from .services import complete_trip

        trip = get_object_or_404(DiveTrip, pk=pk)
        complete_trip(trip, request.user)
        messages.success(request, "Trip has been completed.")
        return HttpResponseRedirect(
            reverse("diveops:trip-detail", kwargs={"pk": trip.pk})
        )
