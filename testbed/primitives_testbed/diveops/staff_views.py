"""Staff portal views for diveops."""

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView, View

from django_portal_ui.mixins import StaffPortalMixin

from .forms import DiverCertificationForm, DiverForm, DiveSiteForm
from .models import Booking, CertificationLevel, DiverCertification, DiverProfile, DiveSite, Excursion
from .selectors import get_diver_with_certifications, get_excursion_with_roster, list_upcoming_excursions


class DashboardView(StaffPortalMixin, TemplateView):
    """Staff dashboard for diveops."""

    template_name = "diveops/staff/dashboard.html"

    def get_context_data(self, **kwargs):
        """Add dashboard stats to context."""
        context = super().get_context_data(**kwargs)

        # Upcoming excursions
        upcoming_excursions = list_upcoming_excursions(limit=5)
        context["upcoming_excursions"] = upcoming_excursions
        context["upcoming_excursions_count"] = Excursion.objects.filter(
            departure_time__gt=timezone.now(),
            status__in=["scheduled", "boarding"],
        ).count()

        # Active divers
        context["diver_count"] = DiverProfile.objects.count()

        # Today's excursions
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        context["todays_excursions"] = Excursion.objects.filter(
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
        diver = form.save(actor=self.request.user)
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
    """Edit an existing diver.

    Shows a simplified form (no inline certification) plus a list of
    existing certifications with an "Add Certification" button.
    """

    template_name = "diveops/staff/diver_edit.html"
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
        kwargs["is_edit"] = True  # Signal to exclude certification fields
        return kwargs

    def form_valid(self, form):
        diver = form.save(actor=self.request.user)
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
        # Get certifications for this diver
        context["certifications"] = self.diver.certifications.filter(
            deleted_at__isnull=True
        ).select_related("level", "level__agency").order_by("-level__rank")
        return context


class ExcursionListView(StaffPortalMixin, ListView):
    """List upcoming dive excursions for staff."""

    model = Excursion
    template_name = "diveops/staff/excursion_list.html"
    context_object_name = "excursions"

    def get_queryset(self):
        """Return upcoming excursions with booking counts."""
        return list_upcoming_excursions()


class ExcursionDetailView(StaffPortalMixin, DetailView):
    """View excursion details with roster and bookings."""

    model = Excursion
    template_name = "diveops/staff/excursion_detail.html"
    context_object_name = "excursion"

    def get_object(self, queryset=None):
        """Get excursion with prefetched related data."""
        pk = self.kwargs.get("pk")
        excursion = get_excursion_with_roster(pk)
        if excursion is None:
            from django.http import Http404
            raise Http404("Excursion not found")
        return excursion

    def get_context_data(self, **kwargs):
        """Add bookings and roster to context."""
        context = super().get_context_data(**kwargs)
        excursion = self.object

        # Get bookings for this excursion
        context["bookings"] = excursion.bookings.select_related(
            "diver__person"
        ).order_by("-created_at")

        # Get roster entries
        context["roster"] = excursion.roster.select_related(
            "diver__person", "booking"
        ).order_by("checked_in_at")

        # Get dives
        context["dives"] = excursion.dives.select_related(
            "dive_site"
        ).order_by("sequence")

        return context


class BookDiverView(StaffPortalMixin, FormView):
    """Book a diver on an excursion."""

    template_name = "diveops/staff/book_diver.html"

    def dispatch(self, request, *args, **kwargs):
        self.excursion = get_object_or_404(Excursion, pk=kwargs["excursion_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("diveops:excursion-detail", kwargs={"pk": self.kwargs["excursion_pk"]})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["excursion"] = self.excursion
        return context

    def get_form_class(self):
        from .forms import BookDiverForm
        return BookDiverForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["excursion"] = self.excursion
        return kwargs

    def form_valid(self, form):
        from .decisioning import can_diver_join_trip
        from .services import book_excursion

        diver = form.cleaned_data["diver"]

        # Check eligibility
        result = can_diver_join_trip(diver, self.excursion)
        if not result.allowed:
            # Add eligibility result to context and re-render
            context = self.get_context_data(form=form)
            context["eligibility_result"] = result
            return self.render_to_response(context)

        # Book the diver
        book_excursion(self.excursion, diver, self.request.user)
        messages.success(
            self.request, f"{diver.person.first_name} has been booked on this excursion."
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
            reverse("diveops:excursion-detail", kwargs={"pk": booking.excursion.pk})
        )


class StartExcursionView(StaffPortalMixin, View):
    """Start an excursion."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from .services import start_excursion

        excursion = get_object_or_404(Excursion, pk=pk)
        start_excursion(excursion, request.user)
        messages.success(request, "Excursion has been started.")
        return HttpResponseRedirect(
            reverse("diveops:excursion-detail", kwargs={"pk": excursion.pk})
        )


class CompleteExcursionView(StaffPortalMixin, View):
    """Complete an excursion."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from .services import complete_excursion

        excursion = get_object_or_404(Excursion, pk=pk)
        complete_excursion(excursion, request.user)
        messages.success(request, "Excursion has been completed.")
        return HttpResponseRedirect(
            reverse("diveops:excursion-detail", kwargs={"pk": excursion.pk})
        )


class DiverDetailView(StaffPortalMixin, DetailView):
    """View diver details with all certifications."""

    model = DiverProfile
    template_name = "diveops/staff/diver_detail.html"
    context_object_name = "diver"

    def get_object(self, queryset=None):
        """Get diver with prefetched certifications."""
        pk = self.kwargs.get("pk")
        diver = get_diver_with_certifications(pk)
        if diver is None:
            from django.http import Http404
            raise Http404("Diver not found")
        return diver

    def get_context_data(self, **kwargs):
        """Add certifications to context."""
        context = super().get_context_data(**kwargs)
        context["certifications"] = self.object.certifications.all()
        return context


class AddCertificationView(StaffPortalMixin, CreateView):
    """Add a new certification to a diver."""

    model = DiverCertification
    form_class = DiverCertificationForm
    template_name = "diveops/staff/certification_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.diver = get_object_or_404(DiverProfile, pk=kwargs["diver_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pre-set the diver
        if "initial" not in kwargs:
            kwargs["initial"] = {}
        kwargs["initial"]["diver"] = self.diver
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Hide the diver field since it's pre-set
        form.fields["diver"].widget = form.fields["diver"].hidden_widget()
        return form

    def get_success_url(self):
        return reverse("diveops:diver-detail", kwargs={"pk": self.diver.pk})

    def form_valid(self, form):
        # Ensure diver is set
        form.instance.diver = self.diver
        # Save with actor for audit logging
        self.object = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Certification {self.object.level.name} has been added.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        from django_parties.models import Organization

        context = super().get_context_data(**kwargs)
        context["diver"] = self.diver
        context["is_create"] = True
        context["page_title"] = "Add Certification"
        context["agencies"] = Organization.objects.filter(org_type="certification_agency").order_by("name")
        return context


class EditCertificationView(StaffPortalMixin, UpdateView):
    """Edit an existing certification."""

    model = DiverCertification
    form_class = DiverCertificationForm
    template_name = "diveops/staff/certification_form.html"

    def get_object(self, queryset=None):
        return get_object_or_404(
            DiverCertification.objects.select_related("diver", "level", "level__agency"),
            pk=self.kwargs["pk"],
        )

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Hide the diver field since it shouldn't be changed
        form.fields["diver"].widget = form.fields["diver"].hidden_widget()
        return form

    def get_success_url(self):
        return reverse("diveops:diver-detail", kwargs={"pk": self.object.diver.pk})

    def form_valid(self, form):
        # Save with actor for audit logging
        self.object = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Certification {self.object.level.name} has been updated.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        from django_parties.models import Organization

        context = super().get_context_data(**kwargs)
        context["diver"] = self.object.diver
        context["is_create"] = False
        context["page_title"] = "Edit Certification"
        context["agencies"] = Organization.objects.filter(org_type="certification_agency").order_by("name")
        return context


class DeleteCertificationView(StaffPortalMixin, View):
    """Soft delete a certification."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from .services import remove_certification

        cert = get_object_or_404(DiverCertification, pk=pk)
        diver_pk = cert.diver.pk
        level_name = cert.level.name

        # Soft delete via service
        remove_certification(cert, request.user)

        messages.success(request, f"Certification {level_name} has been removed.")
        return HttpResponseRedirect(
            reverse("diveops:diver-detail", kwargs={"pk": diver_pk})
        )


class VerifyCertificationView(StaffPortalMixin, View):
    """Toggle verification status of a certification."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from .exceptions import CertificationError
        from .services import unverify_certification, verify_certification

        cert = get_object_or_404(DiverCertification, pk=pk)
        diver_pk = cert.diver.pk
        level_name = cert.level.name

        try:
            if cert.is_verified:
                unverify_certification(cert, request.user)
                messages.success(request, f"Verification removed from {level_name}.")
            else:
                verify_certification(cert, request.user)
                messages.success(request, f"Certification {level_name} has been verified.")
        except CertificationError as e:
            messages.error(request, str(e))

        return HttpResponseRedirect(
            reverse("diveops:diver-detail", kwargs={"pk": diver_pk})
        )


class AuditLogView(StaffPortalMixin, ListView):
    """View audit log entries."""

    template_name = "diveops/staff/audit_log.html"
    context_object_name = "entries"
    paginate_by = 25

    def get_queryset(self):
        """Return audit log entries, newest first."""
        from django_audit_log.models import AuditLog

        return AuditLog.objects.all().order_by("-created_at")

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Audit Log"
        return context


# =============================================================================
# Dive Site Views
# =============================================================================


class DiveSiteListView(StaffPortalMixin, ListView):
    """List all dive sites for staff."""

    model = DiveSite
    template_name = "diveops/staff/site_list.html"
    context_object_name = "sites"

    def get_queryset(self):
        """Return active dive sites with related data."""
        return DiveSite.objects.select_related(
            "place", "min_certification_level"
        ).order_by("name")

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Dive Sites"
        return context


class DiveSiteDetailView(StaffPortalMixin, DetailView):
    """View dive site details."""

    model = DiveSite
    template_name = "diveops/staff/site_detail.html"
    context_object_name = "site"

    def get_object(self, queryset=None):
        """Get site with related data."""
        return get_object_or_404(
            DiveSite.objects.select_related("place", "min_certification_level"),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.name
        return context


class DiveSiteCreateView(StaffPortalMixin, FormView):
    """Create a new dive site."""

    template_name = "diveops/staff/site_form.html"
    form_class = DiveSiteForm
    success_url = reverse_lazy("diveops:staff-site-list")

    def form_valid(self, form):
        site = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Dive site '{site.name}' has been created.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = True
        context["page_title"] = "Add Dive Site"
        context["certification_levels"] = CertificationLevel.objects.filter(
            is_active=True
        ).select_related("agency").order_by("agency__name", "rank")
        return context


class DiveSiteUpdateView(StaffPortalMixin, FormView):
    """Edit an existing dive site."""

    template_name = "diveops/staff/site_form.html"
    form_class = DiveSiteForm
    success_url = reverse_lazy("diveops:staff-site-list")

    def dispatch(self, request, *args, **kwargs):
        self.site = get_object_or_404(
            DiveSite.objects.select_related("place", "min_certification_level"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.site
        return kwargs

    def form_valid(self, form):
        site = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Dive site '{site.name}' has been updated.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        context["page_title"] = f"Edit {self.site.name}"
        context["object"] = self.site
        context["certification_levels"] = CertificationLevel.objects.filter(
            is_active=True
        ).select_related("agency").order_by("agency__name", "rank")
        return context


class DiveSiteDeleteView(StaffPortalMixin, View):
    """Soft delete a dive site."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show delete confirmation page."""
        site = get_object_or_404(DiveSite, pk=pk)
        return self.render_confirmation(request, site)

    def post(self, request, pk):
        """Perform soft delete."""
        from .services import delete_dive_site

        site = get_object_or_404(DiveSite, pk=pk)
        site_name = site.name

        delete_dive_site(actor=request.user, site=site)

        messages.success(request, f"Dive site '{site_name}' has been deleted.")
        return HttpResponseRedirect(reverse("diveops:staff-site-list"))

    def render_confirmation(self, request, site):
        """Render delete confirmation template."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "diveops/staff/site_confirm_delete.html",
            {"site": site, "page_title": f"Delete {site.name}"},
        )
