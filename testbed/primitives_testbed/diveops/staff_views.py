"""Staff portal views for diveops."""

from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView, View

from django_portal_ui.mixins import StaffPortalMixin

from django_catalog.models import CatalogItem

from .forms import (
    AgreementForm,
    AgreementTemplateForm,
    AgreementTerminateForm,
    CatalogItemComponentForm,
    CatalogItemForm,
    DiverCertificationForm,
    DiverForm,
    DiveSiteForm,
    DivingPermitForm,
    ExcursionTypeDiveForm,
    ExcursionTypeForm,
    GuidePermitForm,
    PhotographyPermitForm,
    PriceForm,
    ProtectedAreaFeeScheduleForm,
    ProtectedAreaFeeTierForm,
    ProtectedAreaForm,
    ProtectedAreaRuleForm,
    ProtectedAreaZoneForm,
    SignatureForm,
    SitePriceAdjustmentForm,
    VendorInvoiceForm,
    VendorPaymentForm,
    VesselPermitFormNew,
)
from .models import (
    AgreementTemplate,
    AISettings,
    Booking,
    CertificationLevel,
    DiverCertification,
    DiverProfile,
    DiveLog,
    DiveSite,
    Excursion,
    ExcursionType,
    ExcursionTypeDive,
    GuidePermitDetails,
    ProtectedArea,
    ProtectedAreaFeeSchedule,
    ProtectedAreaFeeTier,
    ProtectedAreaPermit,
    ProtectedAreaRule,
    ProtectedAreaZone,
    SitePriceAdjustment,
)
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
        # Get guide permits for this diver (consistent with detail page)
        context["permits"] = ProtectedAreaPermit.objects.filter(
            diver=self.diver,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            deleted_at__isnull=True
        ).select_related("protected_area").order_by("protected_area__name")
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
        """Add certifications, permits, and medical status to context."""
        context = super().get_context_data(**kwargs)
        context["certifications"] = self.object.certifications.filter(
            deleted_at__isnull=True
        ).select_related("level__agency")
        # Add unified permits (guide permits for this diver)
        context["permits"] = ProtectedAreaPermit.objects.filter(
            diver=self.object,
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            deleted_at__isnull=True
        ).select_related("protected_area").prefetch_related("guide_details").order_by("protected_area__name")
        # Add medical status
        try:
            from .medical.services import get_diver_medical_status
            context["medical_status"] = get_diver_medical_status(self.object).value
        except ImportError:
            context["medical_status"] = None
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


class DiveLogListView(StaffPortalMixin, ListView):
    """View dive log entries across all divers."""

    model = DiveLog
    template_name = "diveops/staff/dive_log_list.html"
    context_object_name = "dive_logs"
    paginate_by = 25

    def get_queryset(self):
        """Return dive logs, newest first."""
        return DiveLog.objects.select_related(
            "diver", "dive", "dive__dive_site", "dive__excursion"
        ).order_by("-created_at")

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Dive Logs"
        return context


class DivePlanListView(StaffPortalMixin, ListView):
    """View dive plan templates (ExcursionTypeDive with route segments)."""

    model = ExcursionTypeDive
    template_name = "diveops/staff/dive_plan_list.html"
    context_object_name = "dive_plans"
    paginate_by = 25

    def get_queryset(self):
        """Return dive templates (dive plans)."""
        return ExcursionTypeDive.objects.select_related(
            "dive_site", "catalog_item", "min_certification_level"
        ).prefetch_related("excursion_types").order_by("name", "sequence")

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Dive Plans"
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
            DiveSite.objects.select_related(
                "place",
                "min_certification_level",
                "min_certification_level__agency",
                "protected_area",
                "protected_area_zone",
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        """Add page title, price adjustments, dive plans, and excursion types to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.name
        # Get price adjustments for this site
        context["price_adjustments"] = self.object.price_adjustments.all().order_by("kind")
        # Get dive plans (ExcursionTypeDive) for this site
        context["dive_plans"] = self.object.dive_plan_templates.prefetch_related(
            "excursion_types"
        ).order_by("name", "sequence")
        # Get excursion types where this site is in suitable_sites
        context["excursion_types"] = self.object.excursion_types.filter(
            is_active=True
        ).order_by("name")
        # Get recent excursions to this site
        context["recent_excursions"] = Excursion.objects.filter(
            dive_site=self.object,
            deleted_at__isnull=True,
        ).select_related("dive_shop", "excursion_type").order_by("-departure_time")[:10]
        # Get zone rules if site is in a protected area zone
        if self.object.protected_area_zone:
            context["zone_rules"] = ProtectedAreaRule.objects.filter(
                Q(zone=self.object.protected_area_zone) | Q(zone__isnull=True, protected_area=self.object.protected_area),
                protected_area=self.object.protected_area,
                is_active=True,
                deleted_at__isnull=True,
            ).order_by("subject")
        elif self.object.protected_area:
            # Area-wide rules (no specific zone)
            context["zone_rules"] = ProtectedAreaRule.objects.filter(
                protected_area=self.object.protected_area,
                zone__isnull=True,
                is_active=True,
                deleted_at__isnull=True,
            ).order_by("subject")
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
        context["protected_areas"] = ProtectedArea.objects.filter(
            is_active=True
        ).order_by("name")
        context["protected_area_zones"] = ProtectedAreaZone.objects.filter(
            is_active=True
        ).select_related("protected_area").order_by("protected_area__name", "name")
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
        context["protected_areas"] = ProtectedArea.objects.filter(
            is_active=True
        ).order_by("name")
        context["protected_area_zones"] = ProtectedAreaZone.objects.filter(
            is_active=True
        ).select_related("protected_area").order_by("protected_area__name", "name")
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


# =============================================================================
# Excursion Calendar Views
# =============================================================================


class ExcursionCalendarView(StaffPortalMixin, TemplateView):
    """Calendar view for excursions with daily/weekly/monthly options."""

    template_name = "diveops/staff/calendar.html"

    def get_context_data(self, **kwargs):
        """Add calendar data to context."""
        from calendar import monthcalendar
        from datetime import date, timedelta

        context = super().get_context_data(**kwargs)

        # Determine view mode (default to weekly)
        view_mode = self.request.GET.get("view", "weekly")
        context["view_mode"] = view_mode

        # Get date from URL params or default to today
        date_str = self.request.GET.get("date")
        if date_str:
            try:
                current_date = date.fromisoformat(date_str)
            except ValueError:
                current_date = date.today()
        else:
            current_date = date.today()

        context["current_date"] = current_date

        if view_mode == "daily":
            context.update(self._get_daily_context(current_date))
        elif view_mode == "weekly":
            context.update(self._get_weekly_context(current_date))
        else:  # monthly
            context.update(self._get_monthly_context(current_date))

        return context

    def _get_daily_context(self, current_date):
        """Get context for daily view."""
        from datetime import timedelta

        day_start = timezone.make_aware(
            timezone.datetime.combine(current_date, timezone.datetime.min.time())
        )
        day_end = day_start + timedelta(days=1)

        excursions = Excursion.objects.filter(
            departure_time__gte=day_start,
            departure_time__lt=day_end,
        ).select_related("dive_site", "dive_shop").order_by("departure_time")

        return {
            "excursions": excursions,
            "prev_date": current_date - timedelta(days=1),
            "next_date": current_date + timedelta(days=1),
            "period_label": current_date.strftime("%B %d, %Y"),
        }

    def _get_weekly_context(self, current_date):
        """Get context for weekly view."""
        from datetime import timedelta

        # Get Sunday of current week (weekday() returns 0=Mon, 6=Sun)
        days_since_sunday = (current_date.weekday() + 1) % 7
        week_start = current_date - timedelta(days=days_since_sunday)
        week_end = week_start + timedelta(days=7)

        # Generate days of the week
        week_days = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_start = timezone.make_aware(
                timezone.datetime.combine(day, timezone.datetime.min.time())
            )
            day_end = day_start + timedelta(days=1)

            day_excursions = Excursion.objects.filter(
                departure_time__gte=day_start,
                departure_time__lt=day_end,
            ).select_related("dive_site", "dive_shop").order_by("departure_time")

            week_days.append({
                "date": day,
                "excursions": day_excursions,
                "is_today": day == timezone.now().date(),
            })

        return {
            "week_days": week_days,
            "week_start": week_start,
            "week_end": week_end - timedelta(days=1),
            "prev_date": week_start - timedelta(weeks=1),
            "next_date": week_start + timedelta(weeks=1),
            "period_label": f"Week of {week_start.strftime('%B %d, %Y')}",
        }

    def _get_monthly_context(self, current_date):
        """Get context for monthly view."""
        from calendar import Calendar
        from datetime import date, timedelta

        year = current_date.year
        month = current_date.month

        # Get first and last day of month
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        # Get month calendar with Sunday as first day (firstweekday=6)
        cal = Calendar(firstweekday=6)
        month_days = cal.monthdatescalendar(year, month)

        # Fetch all excursions for the visible range (includes days from prev/next month)
        visible_start = month_days[0][0]
        visible_end = month_days[-1][-1] + timedelta(days=1)

        month_start = timezone.make_aware(
            timezone.datetime.combine(visible_start, timezone.datetime.min.time())
        )
        month_end = timezone.make_aware(
            timezone.datetime.combine(visible_end, timezone.datetime.min.time())
        )

        excursions = Excursion.objects.filter(
            departure_time__gte=month_start,
            departure_time__lt=month_end,
        ).select_related("dive_site", "dive_shop").order_by("departure_time")

        # Group excursions by date
        excursions_by_date = {}
        for exc in excursions:
            exc_date = exc.departure_time.date()
            if exc_date not in excursions_by_date:
                excursions_by_date[exc_date] = []
            excursions_by_date[exc_date].append(exc)

        # Build weeks with excursions
        calendar_weeks = []
        today = timezone.now().date()
        for week in month_days:
            week_data = []
            for day_date in week:
                week_data.append({
                    "date": day_date,
                    "excursions": excursions_by_date.get(day_date, []),
                    "is_today": day_date == today,
                    "in_month": day_date.month == month,
                })
            calendar_weeks.append(week_data)

        # Calculate prev/next month
        if month == 1:
            prev_month = date(year - 1, 12, 1)
        else:
            prev_month = date(year, month - 1, 1)

        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        return {
            "calendar_weeks": calendar_weeks,
            "month": first_day,
            "prev_date": prev_month,
            "next_date": next_month,
            "period_label": first_day.strftime("%B %Y"),
        }


class ExcursionCreateView(StaffPortalMixin, FormView):
    """Create a new excursion."""

    template_name = "diveops/staff/excursion_form.html"
    success_url = reverse_lazy("diveops:calendar")

    def get_form_class(self):
        from .forms import ExcursionForm
        return ExcursionForm

    def form_valid(self, form):
        from .services import create_excursion

        excursion = create_excursion(
            actor=self.request.user,
            dive_site=form.cleaned_data["dive_site"],
            dive_shop=form.cleaned_data["dive_shop"],
            departure_time=form.cleaned_data["departure_time"],
            return_time=form.cleaned_data["return_time"],
            max_divers=form.cleaned_data["max_divers"],
            price_per_diver=form.cleaned_data.get("price_per_diver"),
            currency=form.cleaned_data.get("currency", "USD"),
            excursion_type=form.cleaned_data.get("excursion_type"),
        )
        messages.success(
            self.request,
            f"Excursion to {excursion.dive_site.name} has been created.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = True
        context["page_title"] = "Create Excursion"
        context["excursion_types"] = ExcursionType.objects.filter(is_active=True).order_by("name")
        return context


class ExcursionUpdateView(StaffPortalMixin, FormView):
    """Edit an existing excursion."""

    template_name = "diveops/staff/excursion_form.html"
    success_url = reverse_lazy("diveops:calendar")

    def dispatch(self, request, *args, **kwargs):
        self.excursion = get_object_or_404(
            Excursion.objects.select_related("dive_site", "dive_shop"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        from .forms import ExcursionForm
        return ExcursionForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.excursion
        return kwargs

    def form_valid(self, form):
        from .services import update_excursion

        update_excursion(
            actor=self.request.user,
            excursion=self.excursion,
            dive_site=form.cleaned_data["dive_site"],
            departure_time=form.cleaned_data["departure_time"],
            return_time=form.cleaned_data["return_time"],
            max_divers=form.cleaned_data["max_divers"],
            price_per_diver=form.cleaned_data.get("price_per_diver"),
            currency=form.cleaned_data.get("currency"),
            excursion_type=form.cleaned_data.get("excursion_type"),
        )
        messages.success(
            self.request,
            f"Excursion to {self.excursion.dive_site.name} has been updated.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        context["page_title"] = f"Edit Excursion - {self.excursion.dive_site.name}"
        context["excursion"] = self.excursion
        context["excursion_types"] = ExcursionType.objects.filter(is_active=True).order_by("name")
        return context


class ExcursionCancelView(StaffPortalMixin, View):
    """Cancel an excursion (soft delete)."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show cancel confirmation page."""
        excursion = get_object_or_404(Excursion, pk=pk)
        return self.render_confirmation(request, excursion)

    def post(self, request, pk):
        """Perform cancellation."""
        from .services import cancel_excursion

        excursion = get_object_or_404(Excursion, pk=pk)
        site_name = excursion.dive_site.name

        try:
            cancel_excursion(excursion=excursion, actor=request.user)
            messages.success(request, f"Excursion to {site_name} has been cancelled.")
        except Exception as e:
            messages.error(request, str(e))

        return HttpResponseRedirect(reverse("diveops:calendar"))

    def render_confirmation(self, request, excursion):
        """Render cancel confirmation template."""
        from django.template.response import TemplateResponse

        booking_count = excursion.bookings.exclude(status="cancelled").count()
        return TemplateResponse(
            request,
            "diveops/staff/excursion_confirm_cancel.html",
            {
                "excursion": excursion,
                "page_title": "Cancel Excursion",
                "booking_count": booking_count,
            },
        )


class DiveCreateView(StaffPortalMixin, FormView):
    """Create a new dive within an excursion."""

    template_name = "diveops/staff/dive_form.html"

    def dispatch(self, request, *args, **kwargs):
        """Get the excursion before processing request."""
        from .models import Excursion

        self.excursion = get_object_or_404(Excursion, pk=kwargs["excursion_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        """Return form with excursion context."""
        from .forms import DiveForm

        return DiveForm(
            data=self.request.POST or None,
            excursion=self.excursion,
        )

    def get_context_data(self, **kwargs):
        """Add excursion to context."""
        context = super().get_context_data(**kwargs)
        context["excursion"] = self.excursion
        context["page_title"] = "Add Dive"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Create the dive using service layer."""
        from .services import create_dive

        dive = create_dive(
            actor=self.request.user,
            excursion=self.excursion,
            dive_site=form.cleaned_data["dive_site"],
            sequence=form.cleaned_data["sequence"],
            planned_start=form.cleaned_data["planned_start"],
            planned_duration_minutes=form.cleaned_data.get("planned_duration_minutes"),
            max_depth_meters=form.cleaned_data.get("max_depth_meters"),
            notes=form.cleaned_data.get("notes", ""),
        )
        messages.success(
            self.request,
            f"Dive {dive.sequence} at {dive.dive_site.name} has been added.",
        )
        return HttpResponseRedirect(
            reverse("diveops:excursion-detail", kwargs={"pk": self.excursion.pk})
        )


class DiveUpdateView(StaffPortalMixin, FormView):
    """Edit an existing dive."""

    template_name = "diveops/staff/dive_form.html"

    def dispatch(self, request, *args, **kwargs):
        """Get the dive before processing request."""
        from .models import Dive

        self.dive = get_object_or_404(Dive, pk=kwargs["pk"])
        self.excursion = self.dive.excursion
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        """Return form with dive instance."""
        from .forms import DiveForm

        return DiveForm(
            data=self.request.POST or None,
            excursion=self.excursion,
            instance=self.dive,
        )

    def get_context_data(self, **kwargs):
        """Add dive and excursion to context."""
        context = super().get_context_data(**kwargs)
        context["dive"] = self.dive
        context["excursion"] = self.excursion
        context["page_title"] = "Edit Dive"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Update the dive using service layer."""
        from .services import update_dive

        dive = update_dive(
            actor=self.request.user,
            dive=self.dive,
            dive_site=form.cleaned_data["dive_site"],
            sequence=form.cleaned_data["sequence"],
            planned_start=form.cleaned_data["planned_start"],
            planned_duration_minutes=form.cleaned_data.get("planned_duration_minutes"),
            max_depth_meters=form.cleaned_data.get("max_depth_meters"),
            notes=form.cleaned_data.get("notes", ""),
        )

        messages.success(
            self.request,
            f"Dive {dive.sequence} has been updated.",
        )
        return HttpResponseRedirect(
            reverse("diveops:excursion-detail", kwargs={"pk": self.excursion.pk})
        )


# =============================================================================
# Excursion Type Views
# =============================================================================


class ExcursionTypeListView(StaffPortalMixin, ListView):
    """List all excursion types for staff."""

    model = ExcursionType
    template_name = "diveops/staff/excursion_type_list.html"
    context_object_name = "excursion_types"

    def get_queryset(self):
        """Return excursion types with related data."""
        return ExcursionType.objects.select_related(
            "min_certification_level", "min_certification_level__agency"
        ).order_by("name")

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Excursion Types"
        return context


class ExcursionTypeDetailView(StaffPortalMixin, DetailView):
    """View excursion type details."""

    model = ExcursionType
    template_name = "diveops/staff/excursion_type_detail.html"
    context_object_name = "excursion_type"

    def get_object(self, queryset=None):
        """Get excursion type with related data."""
        return get_object_or_404(
            ExcursionType.objects.select_related(
                "min_certification_level", "min_certification_level__agency"
            ).prefetch_related(
                "suitable_sites",
                "dive_templates",
                "dive_templates__min_certification_level",
                "dive_templates__min_certification_level__agency",
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        """Add page title and dive templates to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.name
        context["dive_templates"] = self.object.dive_templates.all().order_by("sequence")
        # Available dives that can be added (not already in this excursion type)
        current_dive_ids = self.object.dive_templates.values_list("id", flat=True)
        context["available_dives"] = (
            ExcursionTypeDive.objects.exclude(id__in=current_dive_ids)
            .select_related("dive_site")
            .order_by("name")
        )
        return context


class ExcursionTypeCreateView(StaffPortalMixin, FormView):
    """Create a new excursion type."""

    template_name = "diveops/staff/excursion_type_form.html"
    form_class = ExcursionTypeForm
    success_url = reverse_lazy("diveops:excursion-type-list")

    def form_valid(self, form):
        excursion_type = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Excursion type '{excursion_type.name}' has been created.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = True
        context["page_title"] = "Add Excursion Type"
        return context


class ExcursionTypeUpdateView(StaffPortalMixin, FormView):
    """Edit an existing excursion type."""

    template_name = "diveops/staff/excursion_type_form.html"
    form_class = ExcursionTypeForm
    success_url = reverse_lazy("diveops:excursion-type-list")

    def dispatch(self, request, *args, **kwargs):
        self.excursion_type = get_object_or_404(
            ExcursionType.objects.select_related(
                "min_certification_level", "min_certification_level__agency"
            ),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.excursion_type
        return kwargs

    def form_valid(self, form):
        excursion_type = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Excursion type '{excursion_type.name}' has been updated.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        context["page_title"] = f"Edit {self.excursion_type.name}"
        context["object"] = self.excursion_type
        return context


class ExcursionTypeDeleteView(StaffPortalMixin, View):
    """Soft delete an excursion type."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show delete confirmation page."""
        excursion_type = get_object_or_404(ExcursionType, pk=pk)
        return self.render_confirmation(request, excursion_type)

    def post(self, request, pk):
        """Perform soft delete."""
        from .services import delete_excursion_type

        excursion_type = get_object_or_404(ExcursionType, pk=pk)
        type_name = excursion_type.name

        delete_excursion_type(actor=request.user, excursion_type=excursion_type)

        messages.success(request, f"Excursion type '{type_name}' has been deleted.")
        return HttpResponseRedirect(reverse("diveops:excursion-type-list"))

    def render_confirmation(self, request, excursion_type):
        """Render delete confirmation template."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "diveops/staff/excursion_type_confirm_delete.html",
            {"excursion_type": excursion_type, "page_title": f"Delete {excursion_type.name}"},
        )


class ExcursionTypeAddSiteView(StaffPortalMixin, View):
    """Quick add a site to an excursion type's suitable_sites."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show form to select sites to add."""
        from django.template.response import TemplateResponse

        excursion_type = get_object_or_404(ExcursionType, pk=pk)
        # Get sites not already in suitable_sites, with their dive plans
        current_site_ids = excursion_type.suitable_sites.values_list("pk", flat=True)
        available_sites = DiveSite.objects.filter(is_active=True).exclude(
            pk__in=current_site_ids
        ).prefetch_related(
            Prefetch(
                "dive_plan_templates",
                queryset=ExcursionTypeDive.objects.prefetch_related("excursion_types").order_by("name"),
            )
        ).order_by("name")

        return TemplateResponse(
            request,
            "diveops/staff/excursion_type_add_site.html",
            {
                "excursion_type": excursion_type,
                "available_sites": available_sites,
                "page_title": f"Add Sites to {excursion_type.name}",
            },
        )

    def post(self, request, pk):
        """Add selected sites to suitable_sites."""
        excursion_type = get_object_or_404(ExcursionType, pk=pk)
        site_ids = request.POST.getlist("sites")

        if site_ids:
            sites = DiveSite.objects.filter(pk__in=site_ids, is_active=True)
            excursion_type.suitable_sites.add(*sites)
            count = len(site_ids)
            messages.success(request, f"Added {count} site{'s' if count > 1 else ''} to {excursion_type.name}.")
        else:
            messages.warning(request, "No sites selected.")

        return HttpResponseRedirect(reverse("diveops:excursion-type-detail", kwargs={"pk": pk}))


class ExcursionTypeRemoveSiteView(StaffPortalMixin, View):
    """Remove a site from an excursion type's suitable_sites."""

    http_method_names = ["post"]

    def post(self, request, pk, site_pk):
        """Remove site from suitable_sites."""
        excursion_type = get_object_or_404(ExcursionType, pk=pk)
        site = get_object_or_404(DiveSite, pk=site_pk)

        excursion_type.suitable_sites.remove(site)
        messages.success(request, f"Removed '{site.name}' from suitable sites.")

        return HttpResponseRedirect(reverse("diveops:excursion-type-detail", kwargs={"pk": pk}))


# =============================================================================
# Excursion Type Dive Template Views
# =============================================================================


class ExcursionTypeDiveCreateView(StaffPortalMixin, FormView):
    """Create a new dive template for an excursion type."""

    template_name = "diveops/staff/excursion_type_dive_form.html"
    form_class = ExcursionTypeDiveForm

    def dispatch(self, request, *args, **kwargs):
        self.excursion_type = get_object_or_404(
            ExcursionType.objects.select_related(
                "min_certification_level", "min_certification_level__agency"
            ),
            pk=kwargs["type_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["excursion_type"] = self.excursion_type
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        site_pk = self.request.GET.get("site")
        if site_pk:
            try:
                site = DiveSite.objects.get(pk=site_pk)
                initial["dive_site"] = site
            except (DiveSite.DoesNotExist, ValueError):
                pass
        return initial

    def form_valid(self, form):
        dive_template = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Dive template '{dive_template.name}' has been added.",
        )
        return HttpResponseRedirect(
            reverse("diveops:excursion-type-detail", kwargs={"pk": self.excursion_type.pk})
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = True
        context["excursion_type"] = self.excursion_type
        # Pass the pre-selected site to context for display
        site_pk = self.request.GET.get("site")
        if site_pk:
            try:
                preselected_site = DiveSite.objects.get(pk=site_pk)
                context["preselected_site"] = preselected_site
                context["page_title"] = f"Add Dive Plan for {preselected_site.name}"
            except (DiveSite.DoesNotExist, ValueError):
                context["page_title"] = "Add Dive Template"
        else:
            context["page_title"] = "Add Dive Template"
        return context


class ExcursionTypeDiveUpdateView(StaffPortalMixin, FormView):
    """Edit an existing dive template."""

    template_name = "diveops/staff/excursion_type_dive_form.html"
    form_class = ExcursionTypeDiveForm

    def dispatch(self, request, *args, **kwargs):
        self.dive_template = get_object_or_404(
            ExcursionTypeDive.objects.select_related(
                "min_certification_level", "min_certification_level__agency"
            ).prefetch_related("excursion_types"),
            pk=kwargs["pk"],
        )
        # Get first excursion type for backwards compat (dive plans can have multiple types)
        self.excursion_type = self.dive_template.excursion_types.first()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.dive_template
        return kwargs

    def form_valid(self, form):
        dive_template = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Dive template '{dive_template.name}' has been updated.",
        )
        # Redirect to excursion type detail if one exists, else to dive plan list
        if self.excursion_type:
            return HttpResponseRedirect(
                reverse("diveops:excursion-type-detail", kwargs={"pk": self.excursion_type.pk})
            )
        return HttpResponseRedirect(reverse("diveops:dive-plan-list"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        context["page_title"] = f"Edit Dive {self.dive_template.sequence}: {self.dive_template.name}"
        context["excursion_type"] = self.excursion_type
        context["dive_template"] = self.dive_template
        return context


class ExcursionTypeLinkDiveView(StaffPortalMixin, View):
    """Link an existing dive plan to an excursion type."""

    http_method_names = ["post"]

    def post(self, request, type_pk, dive_pk):
        """Add the dive to the excursion type."""
        excursion_type = get_object_or_404(ExcursionType, pk=type_pk)
        dive_template = get_object_or_404(ExcursionTypeDive, pk=dive_pk)

        # Add to the excursion type
        dive_template.excursion_types.add(excursion_type)

        messages.success(
            request,
            f"Dive '{dive_template.name}' has been added to '{excursion_type.name}'.",
        )
        return HttpResponseRedirect(
            reverse("diveops:excursion-type-detail", kwargs={"pk": type_pk})
        )


class ExcursionTypeDiveDeleteView(StaffPortalMixin, View):
    """Delete a dive template from an excursion type."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show delete confirmation page."""
        dive_template = get_object_or_404(
            ExcursionTypeDive.objects.prefetch_related("excursion_types"),
            pk=pk,
        )
        return self.render_confirmation(request, dive_template)

    def post(self, request, pk):
        """Perform hard delete using service layer."""
        from .services import delete_dive_template

        dive_template = get_object_or_404(
            ExcursionTypeDive.objects.prefetch_related("excursion_types"),
            pk=pk,
        )
        excursion_type = dive_template.excursion_types.first()
        template_name = dive_template.name

        delete_dive_template(actor=request.user, dive_template=dive_template)

        messages.success(request, f"Dive template '{template_name}' has been deleted.")
        if excursion_type:
            return HttpResponseRedirect(
                reverse("diveops:excursion-type-detail", kwargs={"pk": excursion_type.pk})
            )
        return HttpResponseRedirect(reverse("diveops:dive-plan-list"))

    def render_confirmation(self, request, dive_template):
        """Render delete confirmation template."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "diveops/staff/excursion_type_dive_confirm_delete.html",
            {
                "dive_template": dive_template,
                "excursion_type": dive_template.excursion_types.first(),
                "page_title": f"Delete Dive {dive_template.sequence}",
            },
        )


# =============================================================================
# Site Price Adjustment Views
# =============================================================================


class SitePriceAdjustmentCreateView(StaffPortalMixin, FormView):
    """Create a new price adjustment for a dive site."""

    template_name = "diveops/staff/price_adjustment_form.html"
    form_class = SitePriceAdjustmentForm

    def dispatch(self, request, *args, **kwargs):
        self.site = get_object_or_404(DiveSite, pk=kwargs["site_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("diveops:staff-site-detail", kwargs={"pk": self.site.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["dive_site"] = self.site
        return kwargs

    def form_valid(self, form):
        adjustment = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Price adjustment '{adjustment.get_kind_display()}' has been added.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site"] = self.site
        context["is_create"] = True
        context["page_title"] = f"Add Price Adjustment - {self.site.name}"
        return context


class SitePriceAdjustmentUpdateView(StaffPortalMixin, FormView):
    """Edit an existing price adjustment."""

    template_name = "diveops/staff/price_adjustment_form.html"
    form_class = SitePriceAdjustmentForm

    def dispatch(self, request, *args, **kwargs):
        self.adjustment = get_object_or_404(
            SitePriceAdjustment.objects.select_related("dive_site"),
            pk=kwargs["pk"],
        )
        self.site = self.adjustment.dive_site
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("diveops:staff-site-detail", kwargs={"pk": self.site.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.adjustment
        return kwargs

    def form_valid(self, form):
        adjustment = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Price adjustment '{adjustment.get_kind_display()}' has been updated.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site"] = self.site
        context["adjustment"] = self.adjustment
        context["is_create"] = False
        context["page_title"] = f"Edit Price Adjustment - {self.site.name}"
        return context


class SitePriceAdjustmentDeleteView(StaffPortalMixin, View):
    """Soft delete a price adjustment."""

    http_method_names = ["post"]

    def post(self, request, pk):
        from .services import delete_site_price_adjustment

        adjustment = get_object_or_404(
            SitePriceAdjustment.objects.select_related("dive_site"),
            pk=pk,
        )
        site_pk = adjustment.dive_site.pk
        kind_display = adjustment.get_kind_display()

        delete_site_price_adjustment(actor=request.user, adjustment=adjustment)

        messages.success(request, f"Price adjustment '{kind_display}' has been deleted.")
        return HttpResponseRedirect(reverse("diveops:staff-site-detail", kwargs={"pk": site_pk}))


# =============================================================================
# API Endpoints
# =============================================================================


class CompatibleSitesAPIView(StaffPortalMixin, View):
    """API endpoint to get dive sites compatible with an excursion type.

    Returns JSON list of sites filtered by dive mode and certification requirements.
    """

    def get(self, request):
        from django.http import JsonResponse

        from .services import get_compatible_sites

        excursion_type_id = request.GET.get("excursion_type")

        if excursion_type_id:
            try:
                excursion_type = ExcursionType.objects.select_related(
                    "min_certification_level"
                ).get(pk=excursion_type_id)
            except ExcursionType.DoesNotExist:
                return JsonResponse({"error": "Excursion type not found"}, status=404)
        else:
            excursion_type = None

        sites = get_compatible_sites(excursion_type)

        data = [
            {
                "id": str(site.pk),
                "name": site.name,
                "dive_mode": site.dive_mode,
                "difficulty": site.difficulty,
                "max_depth_meters": site.max_depth_meters,
                "min_certification": (
                    site.min_certification_level.name
                    if site.min_certification_level
                    else None
                ),
            }
            for site in sites
        ]

        return JsonResponse({"sites": data})


# =============================================================================
# Catalog Item Views
# =============================================================================


class CatalogItemListView(StaffPortalMixin, ListView):
    """List all catalog items for staff."""

    model = CatalogItem
    template_name = "diveops/staff/catalog_item_list.html"
    context_object_name = "items"

    def get_queryset(self):
        """Return catalog items with optional filters."""
        qs = CatalogItem.objects.filter(deleted_at__isnull=True).order_by("display_name")

        # Filter by kind
        kind = self.request.GET.get("kind")
        if kind:
            qs = qs.filter(kind=kind)

        # Filter by active status
        show_inactive = self.request.GET.get("show_inactive")
        if not show_inactive:
            qs = qs.filter(active=True)

        return qs

    def get_context_data(self, **kwargs):
        """Add page title and filter info to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Catalog Items"
        context["current_kind"] = self.request.GET.get("kind", "")
        context["show_inactive"] = self.request.GET.get("show_inactive", "")
        return context


class CatalogItemDetailView(StaffPortalMixin, DetailView):
    """View catalog item details."""

    model = CatalogItem
    template_name = "diveops/staff/catalog_item_detail.html"
    context_object_name = "item"

    def get_object(self, queryset=None):
        """Get catalog item."""
        return get_object_or_404(CatalogItem, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        """Add page title, prices, and components to context."""
        from primitives_testbed.pricing.models import Price
        from django_catalog.models import CatalogItemComponent

        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.display_name

        # Pricing
        context["prices"] = Price.objects.filter(
            catalog_item=self.object
        ).order_by("-priority", "-valid_from")[:5]
        context["price_count"] = Price.objects.filter(
            catalog_item=self.object
        ).count()

        # Components (items in this assembly)
        context["components"] = CatalogItemComponent.objects.filter(
            parent=self.object,
            deleted_at__isnull=True,
        ).select_related("component").order_by("sequence", "component__display_name")
        context["component_count"] = context["components"].count()

        # Used in assemblies (where this item is a component)
        context["used_in"] = CatalogItemComponent.objects.filter(
            component=self.object,
            deleted_at__isnull=True,
        ).select_related("parent").order_by("parent__display_name")
        context["used_in_count"] = context["used_in"].count()

        return context


class CatalogItemCreateView(StaffPortalMixin, FormView):
    """Create a new catalog item."""

    template_name = "diveops/staff/catalog_item_form.html"
    form_class = CatalogItemForm
    success_url = reverse_lazy("diveops:catalog-item-list")

    def form_valid(self, form):
        item = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Catalog item '{item.display_name}' has been created.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = True
        context["page_title"] = "Add Catalog Item"
        return context


class CatalogItemUpdateView(StaffPortalMixin, FormView):
    """Edit an existing catalog item."""

    template_name = "diveops/staff/catalog_item_form.html"
    form_class = CatalogItemForm
    success_url = reverse_lazy("diveops:catalog-item-list")

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(CatalogItem, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.item
        return kwargs

    def form_valid(self, form):
        item = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Catalog item '{item.display_name}' has been updated.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        context["page_title"] = f"Edit {self.item.display_name}"
        context["object"] = self.item
        return context


class CatalogItemDeleteView(StaffPortalMixin, View):
    """Soft delete a catalog item."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show delete confirmation page."""
        item = get_object_or_404(CatalogItem, pk=pk)
        return self.render_confirmation(request, item)

    def post(self, request, pk):
        """Perform soft delete."""
        from .services import delete_catalog_item

        item = get_object_or_404(CatalogItem, pk=pk)
        item_name = item.display_name

        delete_catalog_item(actor=request.user, item=item)

        messages.success(request, f"Catalog item '{item_name}' has been deleted.")
        return HttpResponseRedirect(reverse("diveops:catalog-item-list"))

    def render_confirmation(self, request, item):
        """Render delete confirmation template."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "diveops/staff/catalog_item_confirm_delete.html",
            {"item": item, "page_title": f"Delete {item.display_name}"},
        )


# =============================================================================
# Dive Plan Views (Full CRUD for ExcursionTypeDive templates)
# =============================================================================


class DivePlanDetailView(StaffPortalMixin, DetailView):
    """View dive plan (ExcursionTypeDive) details."""

    model = ExcursionTypeDive
    template_name = "diveops/staff/dive_plan_detail.html"
    context_object_name = "dive_plan"

    def get_object(self, queryset=None):
        """Get dive plan with related data."""
        return get_object_or_404(
            ExcursionTypeDive.objects.prefetch_related(
                "excursion_types",
            ).select_related(
                "dive_site",
                "dive_site__place",
                "dive_site__min_certification_level",
                "dive_site__min_certification_level__agency",
                "min_certification_level",
                "min_certification_level__agency",
                "catalog_item",
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        """Add page title and related excursions to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Dive Plan: {self.object.name}"

        # Get excursions that use any of this dive plan's excursion types
        # (the template can be used for multiple excursion types)
        excursion_type_ids = self.object.excursion_types.values_list("pk", flat=True)
        context["excursions"] = Excursion.objects.filter(
            excursion_type_id__in=excursion_type_ids
        ).select_related("dive_shop").order_by("-departure_time")[:10]

        return context


class DiveSegmentTypesAPIView(StaffPortalMixin, View):
    """Return segment types as JSON for the dive plan form."""

    def get(self, request):
        from .models import DiveSegmentType

        segment_types = DiveSegmentType.objects.filter(is_active=True).order_by("sort_order")

        # If no segment types exist, return defaults
        if not segment_types.exists():
            return JsonResponse({
                "segment_types": DiveSegmentType.get_default_types()
            })

        return JsonResponse({
            "segment_types": [
                {
                    "name": st.name,
                    "display_name": st.display_name,
                    "is_depth_transition": st.is_depth_transition,
                    "color": st.color,
                }
                for st in segment_types
            ]
        })


class DivePlanCreateView(StaffPortalMixin, FormView):
    """Create a new dive plan template.

    Accepts query parameters:
    - type: Pre-select excursion type
    - site: Pre-select dive site
    """

    template_name = "diveops/staff/dive_plan_form.html"
    form_class = ExcursionTypeDiveForm
    success_url = reverse_lazy("diveops:dive-plan-list")

    def dispatch(self, request, *args, **kwargs):
        """Load pre-selected site and excursion type from query params."""
        self.preset_site = None
        self.preset_excursion_type = None

        # Load dive site from query param
        site_pk = request.GET.get("site")
        if site_pk:
            try:
                self.preset_site = DiveSite.objects.get(pk=site_pk)
            except (DiveSite.DoesNotExist, ValueError):
                pass

        # Load excursion type from query param
        type_pk = request.GET.get("type")
        if type_pk:
            try:
                self.preset_excursion_type = ExcursionType.objects.get(pk=type_pk)
            except (ExcursionType.DoesNotExist, ValueError):
                pass

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.preset_excursion_type:
            kwargs["excursion_type"] = self.preset_excursion_type
        return kwargs

    def get_form(self, form_class=None):
        """Return form, adding excursion_type field if not preset and pre-filling site."""
        form = super().get_form(form_class)

        # Add excursion_type selector if not pre-selected
        if not self.preset_excursion_type:
            from django import forms as django_forms
            form.fields["excursion_type"] = django_forms.ModelChoiceField(
                queryset=ExcursionType.objects.filter(is_active=True).order_by("name"),
                label="Excursion Type",
                help_text="Select which excursion type this dive plan belongs to",
            )

        # Pre-fill dive site if provided
        if self.preset_site:
            form.fields["dive_site"].initial = self.preset_site
            # Update help text to show the pre-selected site
            form.fields["dive_site"].help_text = f"Pre-selected: {self.preset_site.name}"

        return form

    def form_valid(self, form):
        # If excursion_type was in form, get it from cleaned_data
        if "excursion_type" in form.cleaned_data:
            form.excursion_type = form.cleaned_data["excursion_type"]
        dive_plan = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Dive plan '{dive_plan.name}' has been created.",
        )

        # Redirect back to site detail if we came from there
        if self.preset_site:
            return redirect("diveops:staff-site-detail", pk=self.preset_site.pk)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = True
        context["page_title"] = "Add Dive Plan"
        context["excursion_type"] = self.preset_excursion_type
        context["dive_site"] = self.preset_site
        return context


class DivePlanUpdateView(StaffPortalMixin, FormView):
    """Edit an existing dive plan template."""

    template_name = "diveops/staff/dive_plan_form.html"
    form_class = ExcursionTypeDiveForm
    success_url = reverse_lazy("diveops:dive-plan-list")

    def dispatch(self, request, *args, **kwargs):
        self.dive_plan = get_object_or_404(
            ExcursionTypeDive.objects.prefetch_related("excursion_types"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.dive_plan
        return kwargs

    def form_valid(self, form):
        dive_plan = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Dive plan '{dive_plan.name}' has been updated.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        context["page_title"] = f"Edit {self.dive_plan.name}"
        context["dive_plan"] = self.dive_plan
        context["excursion_types"] = self.dive_plan.excursion_types.all()
        return context


class DivePlanDeleteView(StaffPortalMixin, View):
    """Delete a dive plan template."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show delete confirmation page."""
        dive_plan = get_object_or_404(
            ExcursionTypeDive.objects.prefetch_related("excursion_types"),
            pk=pk,
        )
        return self.render_confirmation(request, dive_plan)

    def post(self, request, pk):
        """Perform hard delete using service layer."""
        from .services import delete_dive_template

        dive_plan = get_object_or_404(
            ExcursionTypeDive.objects.prefetch_related("excursion_types"),
            pk=pk,
        )
        plan_name = dive_plan.name

        delete_dive_template(actor=request.user, dive_template=dive_plan)

        messages.success(request, f"Dive plan '{plan_name}' has been deleted.")
        return HttpResponseRedirect(reverse("diveops:dive-plan-list"))

    def render_confirmation(self, request, dive_plan):
        """Render delete confirmation template."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "diveops/staff/dive_plan_confirm_delete.html",
            {
                "dive_plan": dive_plan,
                "excursion_types": dive_plan.excursion_types.all(),
                "page_title": f"Delete {dive_plan.name}",
            },
        )


# =============================================================================
# Price Rule Views (Pricing for Catalog Items)
# =============================================================================


class PriceListView(StaffPortalMixin, ListView):
    """List price rules for a catalog item."""

    template_name = "diveops/staff/price_list.html"
    context_object_name = "prices"
    paginate_by = 25

    def get_queryset(self):
        """Get prices for the catalog item."""
        from primitives_testbed.pricing.models import Price

        self.catalog_item = get_object_or_404(CatalogItem, pk=self.kwargs["item_pk"])

        return Price.objects.filter(
            catalog_item=self.catalog_item,
        ).select_related(
            "organization", "party", "agreement", "created_by"
        ).order_by("-priority", "-valid_from")

    def get_context_data(self, **kwargs):
        """Add catalog item to context."""
        context = super().get_context_data(**kwargs)
        context["catalog_item"] = self.catalog_item
        context["page_title"] = f"Pricing Rules: {self.catalog_item.display_name}"
        return context


class PriceCreateView(StaffPortalMixin, FormView):
    """Create a new price rule for a catalog item."""

    template_name = "diveops/staff/price_form.html"
    form_class = PriceForm

    def get_catalog_item(self):
        """Get the catalog item from URL."""
        if not hasattr(self, "_catalog_item"):
            self._catalog_item = get_object_or_404(CatalogItem, pk=self.kwargs["item_pk"])
        return self._catalog_item

    def get_form_kwargs(self):
        """Pass catalog item to form."""
        kwargs = super().get_form_kwargs()
        kwargs["catalog_item"] = self.get_catalog_item()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add catalog item to context."""
        context = super().get_context_data(**kwargs)
        context["catalog_item"] = self.get_catalog_item()
        context["page_title"] = f"Add Price Rule: {self.get_catalog_item().display_name}"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Save price rule and redirect."""
        price = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Price rule created: {price.amount} {price.currency}",
        )
        return HttpResponseRedirect(
            reverse("diveops:price-list", kwargs={"item_pk": self.get_catalog_item().pk})
        )


class PriceUpdateView(StaffPortalMixin, FormView):
    """Edit an existing price rule."""

    template_name = "diveops/staff/price_form.html"
    form_class = PriceForm

    def get_price(self):
        """Get the price from URL."""
        from primitives_testbed.pricing.models import Price

        if not hasattr(self, "_price"):
            self._price = get_object_or_404(
                Price.objects.select_related("catalog_item", "organization", "party", "agreement"),
                pk=self.kwargs["pk"],
                deleted_at__isnull=True,
            )
        return self._price

    def get_form_kwargs(self):
        """Pass existing price to form."""
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_price()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add price and catalog item to context."""
        context = super().get_context_data(**kwargs)
        price = self.get_price()
        context["price"] = price
        context["catalog_item"] = price.catalog_item
        context["page_title"] = f"Edit Price Rule: {price.catalog_item.display_name}"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save price rule and redirect."""
        price = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Price rule updated: {price.amount} {price.currency}",
        )
        return HttpResponseRedirect(
            reverse("diveops:price-list", kwargs={"item_pk": price.catalog_item.pk})
        )


class PriceDeleteView(StaffPortalMixin, View):
    """Soft delete a price rule."""

    http_method_names = ["get", "post"]

    def get_price(self):
        """Get the price from URL."""
        from primitives_testbed.pricing.models import Price

        if not hasattr(self, "_price"):
            self._price = get_object_or_404(
                Price.objects.select_related("catalog_item"),
                pk=self.kwargs["pk"],
                deleted_at__isnull=True,
            )
        return self._price

    def get(self, request, pk):
        """Show delete confirmation page."""
        price = self.get_price()
        return self.render_confirmation(request, price)

    def post(self, request, pk):
        """Perform soft delete."""
        from .services import delete_price_rule

        price = self.get_price()
        catalog_item = price.catalog_item

        delete_price_rule(actor=request.user, price=price, reason="Deleted via staff portal")

        messages.success(request, f"Price rule deleted.")
        return HttpResponseRedirect(
            reverse("diveops:price-list", kwargs={"item_pk": catalog_item.pk})
        )

    def render_confirmation(self, request, price):
        """Render delete confirmation template."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "diveops/staff/price_confirm_delete.html",
            {
                "price": price,
                "catalog_item": price.catalog_item,
                "page_title": f"Delete Price Rule",
            },
        )


# =============================================================================
# Catalog Item Component Views (Assembly/BOM Management)
# =============================================================================


class CatalogItemComponentCreateView(StaffPortalMixin, FormView):
    """Add a component to a catalog item (assembly)."""

    template_name = "diveops/staff/component_form.html"
    form_class = CatalogItemComponentForm

    def get_parent_item(self):
        """Get the parent catalog item from URL."""
        if not hasattr(self, "_parent_item"):
            self._parent_item = get_object_or_404(CatalogItem, pk=self.kwargs["item_pk"])
        return self._parent_item

    def get_form_kwargs(self):
        """Pass parent item to form."""
        kwargs = super().get_form_kwargs()
        kwargs["parent_item"] = self.get_parent_item()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add parent item to context."""
        context = super().get_context_data(**kwargs)
        context["catalog_item"] = self.get_parent_item()
        context["page_title"] = f"Add Component: {self.get_parent_item().display_name}"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Save component and redirect."""
        component = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Added component: {component.component.display_name} (qty: {component.quantity})",
        )
        return HttpResponseRedirect(
            reverse("diveops:catalog-item-detail", kwargs={"pk": self.get_parent_item().pk})
        )


class CatalogItemComponentUpdateView(StaffPortalMixin, FormView):
    """Edit an existing component relationship."""

    template_name = "diveops/staff/component_form.html"
    form_class = CatalogItemComponentForm

    def get_component(self):
        """Get the component from URL."""
        from django_catalog.models import CatalogItemComponent

        if not hasattr(self, "_component"):
            self._component = get_object_or_404(
                CatalogItemComponent.objects.select_related("parent", "component"),
                pk=self.kwargs["pk"],
                deleted_at__isnull=True,
            )
        return self._component

    def get_form_kwargs(self):
        """Pass existing component to form."""
        kwargs = super().get_form_kwargs()
        component = self.get_component()
        kwargs["parent_item"] = component.parent
        kwargs["instance"] = component
        return kwargs

    def get_context_data(self, **kwargs):
        """Add component and catalog item to context."""
        context = super().get_context_data(**kwargs)
        component = self.get_component()
        context["component"] = component
        context["catalog_item"] = component.parent
        context["page_title"] = f"Edit Component: {component.component.display_name}"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save component and redirect."""
        component = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Updated component: {component.component.display_name}",
        )
        return HttpResponseRedirect(
            reverse("diveops:catalog-item-detail", kwargs={"pk": component.parent.pk})
        )


class CatalogItemComponentDeleteView(StaffPortalMixin, View):
    """Remove a component from an assembly (soft delete)."""

    http_method_names = ["get", "post"]

    def get_component(self):
        """Get the component from URL."""
        from django_catalog.models import CatalogItemComponent

        if not hasattr(self, "_component"):
            self._component = get_object_or_404(
                CatalogItemComponent.objects.select_related("parent", "component"),
                pk=self.kwargs["pk"],
                deleted_at__isnull=True,
            )
        return self._component

    def get(self, request, pk):
        """Show delete confirmation page."""
        component = self.get_component()
        return self.render_confirmation(request, component)

    def post(self, request, pk):
        """Perform soft delete."""
        from django.utils import timezone
        from .audit import Actions, log_event

        component = self.get_component()
        parent_item = component.parent

        # Soft delete
        component.deleted_at = timezone.now()
        component.save(update_fields=["deleted_at", "updated_at"])

        log_event(
            action=Actions.CATALOG_COMPONENT_REMOVED,
            actor=request.user,
            target=component,
            data={
                "parent": str(parent_item.pk),
                "parent_name": parent_item.display_name,
                "component": str(component.component.pk),
                "component_name": component.component.display_name,
            },
        )

        messages.success(request, f"Removed component: {component.component.display_name}")
        return HttpResponseRedirect(
            reverse("diveops:catalog-item-detail", kwargs={"pk": parent_item.pk})
        )

    def render_confirmation(self, request, component):
        """Render delete confirmation template."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "diveops/staff/component_confirm_delete.html",
            {
                "component": component,
                "catalog_item": component.parent,
                "page_title": f"Remove Component",
            },
        )


# =============================================================================
# Agreement Views (Vendor Agreements, Waivers, Training Agreements)
# =============================================================================


class AgreementListView(StaffPortalMixin, ListView):
    """List all agreements with filtering by type."""

    template_name = "diveops/staff/agreement_list.html"
    context_object_name = "agreements"
    paginate_by = 25

    def get_queryset(self):
        """Get agreements with filtering."""
        from django_agreements.models import Agreement

        queryset = Agreement.objects.all().order_by("-created_at")

        # Filter by scope_type if provided
        scope_type = self.request.GET.get("type")
        if scope_type:
            queryset = queryset.filter(scope_type=scope_type)

        # Filter by active status
        show_all = self.request.GET.get("show_all")
        if not show_all:
            queryset = queryset.current()

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Agreements"
        context["scope_type_filter"] = self.request.GET.get("type", "")
        context["show_all"] = self.request.GET.get("show_all", "")
        context["scope_type_choices"] = AgreementForm.SCOPE_TYPE_CHOICES
        return context


class AgreementCreateView(StaffPortalMixin, FormView):
    """Create a new agreement with optional signature capture."""

    template_name = "diveops/staff/agreement_form.html"
    form_class = AgreementForm
    success_url = reverse_lazy("diveops:agreement-list")

    def form_valid(self, form):
        """Save agreement and redirect."""
        agreement = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Agreement created: {agreement.scope_type}",
        )
        return HttpResponseRedirect(
            reverse("diveops:agreement-detail", kwargs={"pk": agreement.pk})
        )

    def get_context_data(self, **kwargs):
        """Add context for template."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Agreement"
        context["is_create"] = True
        return context


class AgreementDetailView(StaffPortalMixin, DetailView):
    """View agreement details including signatures."""

    template_name = "diveops/staff/agreement_detail.html"
    context_object_name = "agreement"

    def get_object(self, queryset=None):
        """Get agreement."""
        from django_agreements.models import Agreement

        return get_object_or_404(Agreement, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        """Add signature status and party info to context."""
        context = super().get_context_data(**kwargs)
        agreement = self.object
        context["page_title"] = f"Agreement: {agreement.scope_type}"

        # Check signature status
        terms = agreement.terms or {}
        context["has_party_a_signature"] = bool(terms.get("signature_party_a"))
        context["has_party_b_signature"] = bool(terms.get("signature_party_b"))

        # For vendor agreements, both signatures are needed
        context["needs_dual_signature"] = agreement.scope_type == "vendor_agreement"

        # Determine which signatures are still needed
        if context["needs_dual_signature"]:
            context["signatures_complete"] = (
                context["has_party_a_signature"] and context["has_party_b_signature"]
            )
        else:
            # For waivers/training, only party_b signature needed
            context["signatures_complete"] = context["has_party_b_signature"]

        # Get versions for audit trail
        context["versions"] = agreement.versions.all().order_by("-version")

        return context


class AgreementTerminateView(StaffPortalMixin, FormView):
    """Terminate an agreement."""

    template_name = "diveops/staff/agreement_terminate.html"
    form_class = AgreementTerminateForm

    def get_agreement(self):
        """Get the agreement from URL."""
        from django_agreements.models import Agreement

        if not hasattr(self, "_agreement"):
            self._agreement = get_object_or_404(Agreement, pk=self.kwargs["pk"])
        return self._agreement

    def get_form_kwargs(self):
        """Pass agreement to form."""
        kwargs = super().get_form_kwargs()
        kwargs["agreement"] = self.get_agreement()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add agreement to context."""
        context = super().get_context_data(**kwargs)
        context["agreement"] = self.get_agreement()
        context["page_title"] = "Terminate Agreement"
        return context

    def form_valid(self, form):
        """Terminate agreement and redirect."""
        agreement = form.save(actor=self.request.user)
        messages.success(
            self.request,
            "Agreement has been terminated.",
        )
        return HttpResponseRedirect(
            reverse("diveops:agreement-detail", kwargs={"pk": agreement.pk})
        )


class AgreementSignView(StaffPortalMixin, FormView):
    """Capture a signature for an agreement.

    Allows collecting signatures from party_a or party_b separately.
    Vendor agreements need both; waivers only need party_b.
    """

    template_name = "diveops/staff/agreement_sign.html"
    form_class = SignatureForm

    def get_agreement(self):
        """Get the agreement from URL."""
        from django_agreements.models import Agreement

        if not hasattr(self, "_agreement"):
            self._agreement = get_object_or_404(Agreement, pk=self.kwargs["pk"])
        return self._agreement

    def get_signing_party(self):
        """Determine which party is signing from query param."""
        return self.request.GET.get("party", "party_b")

    def get_form_kwargs(self):
        """Pass agreement and signing party to form."""
        kwargs = super().get_form_kwargs()
        kwargs["agreement"] = self.get_agreement()
        kwargs["signing_party"] = self.get_signing_party()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add agreement and signing info to context."""
        context = super().get_context_data(**kwargs)
        agreement = self.get_agreement()
        signing_party = self.get_signing_party()

        context["agreement"] = agreement
        context["signing_party"] = signing_party
        context["page_title"] = f"Sign Agreement - {signing_party.replace('_', ' ').title()}"

        # Get party name for display
        if signing_party == "party_a":
            context["party_label"] = "Party A (Shop/Organization)"
        else:
            context["party_label"] = "Party B (Vendor/Diver)"

        return context

    def form_valid(self, form):
        """Save signature and redirect."""
        agreement = form.save(actor=self.request.user)
        messages.success(
            self.request,
            "Signature captured successfully.",
        )
        return HttpResponseRedirect(
            reverse("diveops:agreement-detail", kwargs={"pk": agreement.pk})
        )


# =============================================================================
# Payables Views (Vendor Invoice & Payment Management)
# =============================================================================


class PayablesSummaryView(StaffPortalMixin, TemplateView):
    """Dashboard showing open payables grouped by vendor."""

    template_name = "diveops/staff/payables_summary.html"

    def get_context_data(self, **kwargs):
        """Get vendor payables summary."""
        from .services import get_vendor_payables_summary

        context = super().get_context_data(**kwargs)
        context["page_title"] = "Vendor Payables"

        # Get summary of open payables by vendor
        context["payables"] = get_vendor_payables_summary()

        # Calculate totals by currency
        totals = {}
        for item in context["payables"]:
            currency = item["currency"]
            if currency not in totals:
                totals[currency] = 0
            totals[currency] += item["balance"]
        context["totals"] = totals

        return context


class VendorPayablesDetailView(StaffPortalMixin, TemplateView):
    """Show transactions for a specific vendor."""

    template_name = "diveops/staff/vendor_payables_detail.html"

    def get_context_data(self, **kwargs):
        """Get vendor transactions."""
        from django_parties.models import Organization

        from .services import get_vendor_payables_summary, get_vendor_transactions

        context = super().get_context_data(**kwargs)

        # Get vendor
        vendor = get_object_or_404(Organization, pk=self.kwargs["vendor_pk"])
        context["vendor"] = vendor
        context["page_title"] = f"Payables: {vendor.name}"

        # Get transactions for this vendor
        currency = self.request.GET.get("currency")
        context["transactions"] = get_vendor_transactions(vendor, currency=currency)
        context["currency_filter"] = currency

        # Get balance from summary
        summary = get_vendor_payables_summary()
        vendor_balances = [
            item for item in summary
            if item["vendor_id"] == str(vendor.pk)
        ]
        context["balances"] = vendor_balances

        return context


class RecordVendorInvoiceView(StaffPortalMixin, FormView):
    """Record a vendor invoice."""

    template_name = "diveops/staff/record_invoice_form.html"
    form_class = VendorInvoiceForm
    success_url = reverse_lazy("diveops:payables-summary")

    def form_valid(self, form):
        """Save invoice and redirect."""
        from .accounts import AccountConfigurationError

        try:
            tx = form.save(actor=self.request.user)
        except AccountConfigurationError as e:
            # Show clear error to user with guidance
            form.add_error("shop", str(e))
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Vendor invoice recorded: {form.cleaned_data['amount']} {form.cleaned_data['currency']}",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Add context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Record Vendor Invoice"
        return context


class RecordVendorPaymentView(StaffPortalMixin, FormView):
    """Record a payment to a vendor."""

    template_name = "diveops/staff/record_payment_form.html"
    form_class = VendorPaymentForm
    success_url = reverse_lazy("diveops:payables-summary")

    def form_valid(self, form):
        """Save payment and redirect."""
        from .accounts import AccountConfigurationError

        try:
            tx = form.save(actor=self.request.user)
        except AccountConfigurationError as e:
            # Show clear error to user with guidance
            form.add_error("shop", str(e))
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Payment recorded: {form.cleaned_data['amount']} {form.cleaned_data['currency']}",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Add context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Record Vendor Payment"

        # Pre-select vendor if coming from vendor detail page
        vendor_pk = self.request.GET.get("vendor")
        if vendor_pk:
            from django_parties.models import Organization

            try:
                context["preselected_vendor"] = Organization.objects.get(pk=vendor_pk)
            except Organization.DoesNotExist:
                pass

        return context


# =============================================================================
# Account Management Views
# =============================================================================


class AccountListView(StaffPortalMixin, TemplateView):
    """List all ledger accounts for the organization."""

    template_name = "diveops/staff/account_list.html"
    paginate_by = 50

    # Valid sort options
    SORT_OPTIONS = {
        "number": "account_number",
        "-number": "-account_number",
        "name": "name",
        "-name": "-name",
        "type": "account_type",
        "-type": "-account_type",
        "currency": "currency",
        "-currency": "-currency",
    }

    def get_context_data(self, **kwargs):
        """Get accounts grouped by type with pagination, search, and sorting."""
        from django.core.paginator import Paginator
        from django.db.models import Q

        from .accounts import list_accounts

        context = super().get_context_data(**kwargs)
        context["page_title"] = "Chart of Accounts"

        # Get filter parameters
        shop_pk = self.request.GET.get("shop")
        currency = self.request.GET.get("currency")
        account_type = self.request.GET.get("type")
        status = self.request.GET.get("status", "")  # "", "active", "inactive"
        search = self.request.GET.get("q", "").strip()
        sort = self.request.GET.get("sort", "number")

        # Get shop if filtered
        shop = None
        if shop_pk:
            from django_parties.models import Organization
            shop = Organization.objects.filter(pk=shop_pk).first()

        # List accounts with filters (returns QuerySet)
        accounts_qs = list_accounts(shop=shop, currency=currency, account_type=account_type)

        # Filter by status (active/inactive)
        if status == "active":
            accounts_qs = accounts_qs.filter(is_active=True)
        elif status == "inactive":
            accounts_qs = accounts_qs.filter(is_active=False)

        # Search by name or account number
        if search:
            accounts_qs = accounts_qs.filter(
                Q(name__icontains=search) | Q(account_number__icontains=search)
            )

        # Apply sorting
        sort_field = self.SORT_OPTIONS.get(sort, "account_number")
        accounts_qs = accounts_qs.order_by(sort_field, "account_type", "name")

        # Paginate
        paginator = Paginator(accounts_qs, self.paginate_by)
        page_number = self.request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        context["accounts"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        context["total_count"] = paginator.count

        # Group current page accounts by type for display
        accounts_by_type = {}
        for account in page_obj.object_list:
            if account.account_type not in accounts_by_type:
                accounts_by_type[account.account_type] = []
            accounts_by_type[account.account_type].append(account)
        context["accounts_by_type"] = accounts_by_type

        # Get available shops for filter
        from django_parties.models import Organization
        context["shops"] = Organization.objects.filter(
            org_type__in=["company", "dive_shop"]
        ).order_by("name")
        context["selected_shop"] = shop
        context["selected_currency"] = currency
        context["selected_type"] = account_type
        context["selected_status"] = status
        context["search_query"] = search
        context["current_sort"] = sort

        return context


class AccountCreateView(StaffPortalMixin, FormView):
    """Create a new ledger account."""

    template_name = "diveops/staff/account_form.html"
    success_url = reverse_lazy("diveops:account-list")

    def get_form_class(self):
        from .forms import AccountForm
        return AccountForm

    def form_valid(self, form):
        """Save account and redirect."""
        account = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Account '{account.name}' created successfully.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Add context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Account"
        context["is_create"] = True
        return context


class AccountUpdateView(StaffPortalMixin, FormView):
    """Edit an existing ledger account."""

    template_name = "diveops/staff/account_form.html"
    success_url = reverse_lazy("diveops:account-list")

    def dispatch(self, request, *args, **kwargs):
        from django_ledger.models import Account
        self.account = get_object_or_404(Account, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        from .forms import AccountForm
        return AccountForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.account
        return kwargs

    def form_valid(self, form):
        """Save account and redirect."""
        account = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Account '{account.name}' updated successfully.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Add context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Account: {self.account.name}"
        context["account"] = self.account
        context["is_create"] = False
        return context


class AccountSeedView(StaffPortalMixin, FormView):
    """Seed standard chart of accounts for a dive shop."""

    template_name = "diveops/staff/account_seed.html"
    success_url = reverse_lazy("diveops:account-list")

    def get_form_class(self):
        from .forms import AccountSeedForm
        return AccountSeedForm

    def form_valid(self, form):
        """Seed accounts and redirect."""
        account_set = form.save(actor=self.request.user)
        shop = form.cleaned_data["shop"]
        currency = form.cleaned_data["currency"]
        messages.success(
            self.request,
            f"Chart of accounts seeded for {shop.name} ({currency}). "
            f"All required accounts are now available.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Add context."""
        from .accounts import ACCOUNT_TYPES, REQUIRED_ACCOUNT_KEYS

        context = super().get_context_data(**kwargs)
        context["page_title"] = "Seed Chart of Accounts"

        # Show what accounts will be created
        context["account_types"] = ACCOUNT_TYPES
        context["required_keys"] = REQUIRED_ACCOUNT_KEYS

        return context


class AccountDeactivateView(StaffPortalMixin, TemplateView):
    """Deactivate an account (accounts cannot be deleted)."""

    template_name = "diveops/staff/account_confirm_deactivate.html"

    def dispatch(self, request, *args, **kwargs):
        from django_ledger.models import Account
        self.account = get_object_or_404(Account, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add context."""
        from .accounts import can_deactivate_account

        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Deactivate Account: {self.account.name}"
        context["account"] = self.account

        can_deactivate, warning = can_deactivate_account(self.account)
        context["can_deactivate"] = can_deactivate
        context["warning"] = warning

        return context

    def post(self, request, *args, **kwargs):
        """Handle deactivation."""
        from .accounts import deactivate_account

        deactivate_account(self.account, actor=request.user)
        messages.success(
            request,
            f"Account '{self.account.name}' has been deactivated. "
            f"It will no longer accept new transactions.",
        )
        return redirect("diveops:account-list")


class AccountReactivateView(StaffPortalMixin, View):
    """Reactivate a previously deactivated account."""

    def post(self, request, pk):
        from django_ledger.models import Account
        from .accounts import reactivate_account

        account = get_object_or_404(Account, pk=pk)
        reactivate_account(account, actor=request.user)
        messages.success(
            request,
            f"Account '{account.name}' has been reactivated.",
        )
        return redirect("diveops:account-list")

    def get(self, request, pk):
        """Show confirmation page."""
        from django_ledger.models import Account

        account = get_object_or_404(Account, pk=pk)
        return render(
            request,
            "diveops/staff/account_confirm_reactivate.html",
            {
                "page_title": f"Reactivate Account: {account.name}",
                "account": account,
            },
        )


# =============================================================================
# Agreement Template Management
# =============================================================================


class AgreementTemplateListView(StaffPortalMixin, ListView):
    """List all agreement templates for waivers, releases, and other documents."""

    model = AgreementTemplate
    template_name = "diveops/staff/agreement_template_list.html"
    context_object_name = "templates"
    paginate_by = 25

    def get_queryset(self):
        """Get templates with optional filtering."""
        queryset = AgreementTemplate.objects.select_related("dive_shop").order_by(
            "template_type", "-created_at"
        )

        # Filter by type if provided
        template_type = self.request.GET.get("type")
        if template_type:
            queryset = queryset.filter(template_type=template_type)

        # Filter by status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)
        else:
            # By default, show non-archived templates
            queryset = queryset.exclude(status="archived")

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Agreement Templates"
        context["template_type_filter"] = self.request.GET.get("type", "")
        context["status_filter"] = self.request.GET.get("status", "")
        context["template_type_choices"] = AgreementTemplate.TemplateType.choices
        context["status_choices"] = AgreementTemplate.Status.choices
        return context


class AgreementTemplateCreateView(StaffPortalMixin, CreateView):
    """Create a new agreement template."""

    model = AgreementTemplate
    form_class = AgreementTemplateForm
    template_name = "diveops/staff/agreement_template_form.html"
    success_url = reverse_lazy("diveops:agreement-template-list")

    def form_valid(self, form):
        """Save template and redirect."""
        template = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Agreement template '{template.name}' created successfully.",
        )
        return redirect("diveops:agreement-template-detail", pk=template.pk)

    def get_context_data(self, **kwargs):
        """Add context for template."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Agreement Template"
        context["is_create"] = True
        return context


class AgreementTemplateDetailView(StaffPortalMixin, DetailView):
    """View agreement template details."""

    model = AgreementTemplate
    template_name = "diveops/staff/agreement_template_detail.html"
    context_object_name = "template"

    def get_context_data(self, **kwargs):
        """Add context data including rendered preview with sample variables."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Template: {self.object.name}"

        # Provide sample data for template variable substitution in preview
        today = timezone.now().date()
        sample_variables = {
            # Diver/Participant info
            "{{ diver_name }}": "John Doe",
            "{{ participant_name }}": "John Doe",
            "{{ diver_full_name }}": "John Doe",
            "{{ first_name }}": "John",
            "{{ last_name }}": "Doe",
            "{{ email }}": "john.doe@example.com",
            # Dates
            "{{ date }}": today.strftime("%B %d, %Y"),
            "{{ current_date }}": today.strftime("%B %d, %Y"),
            "{{ today }}": today.strftime("%B %d, %Y"),
            # Dive shop info
            "{{ dive_shop_name }}": self.object.dive_shop.name,
            "{{ shop_name }}": self.object.dive_shop.name,
            "{{ operator_name }}": self.object.dive_shop.name,
        }

        # Render the preview by substituting variables
        rendered_content = self.object.content
        for placeholder, value in sample_variables.items():
            rendered_content = rendered_content.replace(placeholder, value)

        context["rendered_content"] = rendered_content
        context["sample_variables"] = sample_variables
        return context


class AgreementTemplatePreviewView(StaffPortalMixin, DetailView):
    """Preview agreement template in a clean, printable format."""

    model = AgreementTemplate
    template_name = "diveops/staff/agreement_template_preview.html"
    context_object_name = "template"

    def get_context_data(self, **kwargs):
        """Add context data with rendered content using sample variables."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Preview: {self.object.name}"

        # Sample data for template variable substitution
        today = timezone.now().date()
        sample_variables = {
            # Diver/Participant info
            "{{ diver_name }}": "John Doe",
            "{{ participant_name }}": "John Doe",
            "{{ diver_full_name }}": "John Doe",
            "{{ first_name }}": "John",
            "{{ last_name }}": "Doe",
            "{{ email }}": "john.doe@example.com",
            # Dates
            "{{ date }}": today.strftime("%B %d, %Y"),
            "{{ current_date }}": today.strftime("%B %d, %Y"),
            "{{ today }}": today.strftime("%B %d, %Y"),
            # Dive shop info
            "{{ dive_shop_name }}": self.object.dive_shop.name,
            "{{ shop_name }}": self.object.dive_shop.name,
            "{{ operator_name }}": self.object.dive_shop.name,
        }

        # Render the preview by substituting variables
        rendered_content = self.object.content
        for placeholder, value in sample_variables.items():
            rendered_content = rendered_content.replace(placeholder, value)

        context["rendered_content"] = rendered_content
        context["sample_variables"] = sample_variables
        return context


class AgreementTemplateUpdateView(StaffPortalMixin, UpdateView):
    """Edit an agreement template."""

    model = AgreementTemplate
    form_class = AgreementTemplateForm
    template_name = "diveops/staff/agreement_template_form.html"

    def get_success_url(self):
        return reverse("diveops:agreement-template-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """Save template and redirect."""
        template = form.save(actor=self.request.user)
        messages.success(
            self.request,
            f"Agreement template '{template.name}' updated successfully.",
        )
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        """Add context for template."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit: {self.object.name}"
        context["is_create"] = False
        return context


class AgreementTemplatePublishView(StaffPortalMixin, View):
    """Publish an agreement template."""

    def post(self, request, pk):
        """Handle publish action."""
        from .audit import Actions, log_event

        template = get_object_or_404(AgreementTemplate, pk=pk)
        template.publish(user=request.user)

        log_event(
            action=Actions.AGREEMENT_TEMPLATE_PUBLISHED,
            actor=request.user,
            target=template,
            data={"version": template.version},
        )

        messages.success(
            request,
            f"Template '{template.name}' has been published. "
            f"Any previous published version has been archived.",
        )
        return redirect("diveops:agreement-template-detail", pk=pk)


class AgreementTemplateArchiveView(StaffPortalMixin, View):
    """Archive an agreement template."""

    def post(self, request, pk):
        """Handle archive action."""
        from .audit import Actions, log_event

        template = get_object_or_404(AgreementTemplate, pk=pk)
        template.status = AgreementTemplate.Status.ARCHIVED
        template.save(update_fields=["status", "updated_at"])

        log_event(
            action=Actions.AGREEMENT_TEMPLATE_ARCHIVED,
            actor=request.user,
            target=template,
            data={"version": template.version},
        )

        messages.success(
            request,
            f"Template '{template.name}' has been archived.",
        )
        return redirect("diveops:agreement-template-list")


class AgreementTemplateSendView(StaffPortalMixin, View):
    """Send an agreement template to a party for signing."""

    def _get_parties_for_template(self, template):
        """Get appropriate parties based on template's target_party_type."""
        from django_parties.models import Organization, PartyRelationship, Person

        target_type = template.target_party_type
        dive_shop = template.dive_shop

        if target_type == AgreementTemplate.TargetPartyType.DIVER:
            # Divers: Persons who have a DiverProfile
            diver_person_ids = DiverProfile.objects.filter(
                deleted_at__isnull=True
            ).values_list("person_id", flat=True)
            parties = Person.objects.filter(
                pk__in=diver_person_ids,
                deleted_at__isnull=True,
            ).order_by("last_name", "first_name")[:100]
            party_type_label = "Diver"
            is_organization = False

        elif target_type == AgreementTemplate.TargetPartyType.EMPLOYEE:
            # Employees: Persons with employee relationship to dive shop
            employee_person_ids = PartyRelationship.objects.filter(
                to_organization=dive_shop,
                relationship_type="employee",
                is_active=True,
                deleted_at__isnull=True,
            ).values_list("from_person_id", flat=True)
            parties = Person.objects.filter(
                pk__in=employee_person_ids,
                deleted_at__isnull=True,
            ).order_by("last_name", "first_name")[:100]
            party_type_label = "Employee"
            is_organization = False

        elif target_type == AgreementTemplate.TargetPartyType.VENDOR:
            # Vendors: Organizations with vendor relationship to dive shop
            vendor_org_ids = PartyRelationship.objects.filter(
                to_organization=dive_shop,
                relationship_type="vendor",
                is_active=True,
                deleted_at__isnull=True,
            ).values_list("from_organization_id", flat=True)
            parties = Organization.objects.filter(
                pk__in=vendor_org_ids,
                deleted_at__isnull=True,
            ).order_by("name")[:100]
            party_type_label = "Vendor"
            is_organization = True

        else:  # ANY - show all persons
            parties = Person.objects.filter(
                deleted_at__isnull=True
            ).order_by("last_name", "first_name")[:100]
            party_type_label = "Person"
            is_organization = False

        return parties, party_type_label, is_organization

    def get(self, request, pk):
        """Show form to select party and delivery method."""
        template = get_object_or_404(AgreementTemplate, pk=pk)

        # Only published templates can be sent
        if template.status != AgreementTemplate.Status.PUBLISHED:
            messages.error(request, "Only published templates can be sent.")
            return redirect("diveops:agreement-template-detail", pk=pk)

        # Get filtered parties based on template's target_party_type
        parties, party_type_label, is_organization = self._get_parties_for_template(template)

        return render(
            request,
            "diveops/staff/agreement_template_send.html",
            {
                "page_title": f"Send: {template.name}",
                "template": template,
                "parties": parties,
                "party_type_label": party_type_label,
                "is_organization": is_organization,
                "delivery_methods": [
                    ("email", "Send via Email"),
                    ("link", "Generate Link"),
                    ("in_person", "In-Person Signing"),
                ],
            },
        )

    def post(self, request, pk):
        """Create SignableAgreement and send to party."""
        from django_parties.models import Organization, Person

        from .services import create_agreement_from_template, send_agreement

        template = get_object_or_404(AgreementTemplate, pk=pk)

        # Only published templates can be sent
        if template.status != AgreementTemplate.Status.PUBLISHED:
            messages.error(request, "Only published templates can be sent.")
            return redirect("diveops:agreement-template-detail", pk=pk)

        # Get selected party
        party_id = request.POST.get("party_id")
        if not party_id:
            messages.error(request, "Please select a party to send the agreement to.")
            return redirect("diveops:agreement-template-send", pk=pk)

        # Fetch the party - Organization for vendors, Person for others
        target_type = template.target_party_type
        if target_type == AgreementTemplate.TargetPartyType.VENDOR:
            party = get_object_or_404(Organization, pk=party_id)
            party_display_name = party.name
        else:
            party = get_object_or_404(Person, pk=party_id)
            party_display_name = f"{party.first_name} {party.last_name}"

        # Get delivery method
        delivery_method = request.POST.get("delivery_method", "link")
        if delivery_method not in ("email", "link", "in_person"):
            delivery_method = "link"

        # Get expiration days
        try:
            expires_in_days = int(request.POST.get("expires_in_days", 30))
        except ValueError:
            expires_in_days = 30

        # Create the SignableAgreement
        agreement = create_agreement_from_template(
            template=template,
            party_a=party,
            actor=request.user,
        )

        # Send it (generates token)
        agreement, token = send_agreement(
            agreement=agreement,
            delivery_method=delivery_method,
            expires_in_days=expires_in_days,
            actor=request.user,
        )

        # Build the signing URL
        signing_url = request.build_absolute_uri(f"/sign/{token}/")

        if delivery_method == "email":
            # In production, this would send an email
            # For now, show the link to the user
            messages.success(
                request,
                f"Agreement sent to {party_display_name}. "
                f"(Email sending not yet implemented - use this link: {signing_url})"
            )
        elif delivery_method == "link":
            messages.success(
                request,
                f"Signing link generated for {party_display_name}. "
                f"Share this link: {signing_url}"
            )
        else:  # in_person
            messages.success(
                request,
                f"Agreement ready for in-person signing with {party_display_name}. "
                f"Use this link: {signing_url}"
            )

        return redirect("diveops:signable-agreement-detail", pk=agreement.pk)


class AgreementTemplateDeleteView(StaffPortalMixin, View):
    """Delete an agreement template (soft delete)."""

    def get(self, request, pk):
        """Show confirmation page."""
        template = get_object_or_404(AgreementTemplate, pk=pk)
        return render(
            request,
            "diveops/staff/agreement_template_confirm_delete.html",
            {
                "page_title": f"Delete: {template.name}",
                "template": template,
            },
        )

    def post(self, request, pk):
        """Handle delete action."""
        from .audit import Actions, log_event

        template = get_object_or_404(AgreementTemplate, pk=pk)
        template_name = template.name

        # Soft delete
        template.deleted_at = timezone.now()
        template.save(update_fields=["deleted_at", "updated_at"])

        log_event(
            action=Actions.AGREEMENT_TEMPLATE_DELETED,
            actor=request.user,
            target=template,
            data={"name": template_name},
        )

        messages.success(
            request,
            f"Template '{template_name}' has been deleted.",
        )
        return redirect("diveops:agreement-template-list")


class AgreementTemplateExtractTextView(StaffPortalMixin, View):
    """Extract text from uploaded document for agreement template content.

    Accepts PDF, Word documents, or images and extracts text using OCR/parsing.
    Returns JSON with extracted text to pre-populate the template content field.
    """

    def post(self, request):
        """Handle file upload and extract text."""
        import json
        import mimetypes
        import tempfile
        import os
        from django.http import JsonResponse
        from django_documents.extraction import extract_text, extract_text_from_pdf

        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"success": False, "error": "No file uploaded"}, status=400)

        # Determine content type
        content_type = file.content_type
        if not content_type or content_type == "application/octet-stream":
            # Try to guess from filename
            guessed_type, _ = mimetypes.guess_type(file.name)
            if guessed_type:
                content_type = guessed_type

        # Check supported types
        supported_types = {
            "application/pdf",
            "image/png", "image/jpeg", "image/jpg", "image/tiff",
            "text/plain", "text/html",
            # Word documents - will need special handling
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

        if content_type not in supported_types:
            return JsonResponse({
                "success": False,
                "error": f"Unsupported file type: {content_type}. Supported: PDF, images, text, Word documents."
            }, status=400)

        # Save to temp file for processing
        try:
            suffix = os.path.splitext(file.name)[1] if file.name else ""
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            extracted_text = ""
            method = ""

            # Handle Word documents
            if content_type in (
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                try:
                    import docx
                    doc = docx.Document(tmp_path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    extracted_text = "\n\n".join(paragraphs)
                    method = "python-docx"
                except ImportError:
                    # Fall back to textract if docx not available
                    try:
                        import textract
                        extracted_text = textract.process(tmp_path).decode("utf-8")
                        method = "textract"
                    except ImportError:
                        return JsonResponse({
                            "success": False,
                            "error": "Word document support requires python-docx. Install with: pip install python-docx"
                        }, status=500)
                except Exception as e:
                    return JsonResponse({
                        "success": False,
                        "error": f"Failed to extract text from Word document: {str(e)}"
                    }, status=500)
            else:
                # Use django-documents extraction for PDF, images, text
                result = extract_text(tmp_path, content_type)
                if result.success:
                    extracted_text = result.text
                    method = result.method
                else:
                    # Clean up temp file
                    os.unlink(tmp_path)
                    return JsonResponse({
                        "success": False,
                        "error": result.error or "Failed to extract text from document"
                    }, status=500)

            # Clean up temp file
            os.unlink(tmp_path)

            if not extracted_text.strip():
                return JsonResponse({
                    "success": False,
                    "error": "No text could be extracted from the document. It may be a scanned image - try uploading a higher quality scan."
                }, status=400)

            # AI Enhancement: Use service layer for clean separation
            from .services import enhance_extracted_text
            enhanced = enhance_extracted_text(extracted_text, method)

            return JsonResponse({
                "success": True,
                "text": enhanced.content,
                "method": enhanced.method,
                "word_count": len(enhanced.content.split()),
                "filename": file.name,
                "suggested_title": enhanced.suggested_title,
            })

        except Exception as e:
            # Clean up temp file if it exists
            if "tmp_path" in locals():
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            return JsonResponse({
                "success": False,
                "error": f"Error processing file: {str(e)}"
            }, status=500)


# =============================================================================
# Tissue Loading API (EPHEMERAL - No Persistence)
# =============================================================================


class ExcursionTypeTissueCalculationView(StaffPortalMixin, View):
    """Return tissue loading calculations as JSON for chart rendering.

    WARNING: This returns EPHEMERAL planning data. Results are NOT stored.
    Recalculate fresh each time - tissue state should never be persisted.

    Returns JSON with:
    - version: Tissue payload version for validation
    - excursion_type_id: The excursion type UUID
    - dive_results: List of dive results with loading percentages
    - surface_intervals: List of surface interval results
    - final_loading_percent: Final tissue loading after all dives
    """

    def get(self, request, pk):
        """Calculate and return tissue loading profile."""
        from dataclasses import asdict

        from .services import DEFAULT_GF_HIGH, DEFAULT_GF_LOW, calculate_excursion_tissue_loading

        excursion_type = get_object_or_404(ExcursionType, pk=pk)

        # Get gradient factors from query params (default to no conservatism)
        try:
            gf_low = int(request.GET.get("gf_low", DEFAULT_GF_LOW))
            gf_low = max(30, min(100, gf_low))  # Clamp to valid range
        except (ValueError, TypeError):
            gf_low = DEFAULT_GF_LOW

        try:
            gf_high = int(request.GET.get("gf_high", DEFAULT_GF_HIGH))
            gf_high = max(30, min(100, gf_high))  # Clamp to valid range
        except (ValueError, TypeError):
            gf_high = DEFAULT_GF_HIGH

        # Ensure gf_low <= gf_high
        if gf_low > gf_high:
            gf_low = gf_high

        # Calculate tissue profile (EPHEMERAL - not stored)
        profile = calculate_excursion_tissue_loading(
            excursion_type,
            gf_low=gf_low,
            gf_high=gf_high,
        )

        # Convert dataclasses to dicts for JSON serialization
        result = {
            "version": profile.version,
            "excursion_type_id": profile.excursion_type_id,
            "excursion_type_name": excursion_type.name,
            "dive_results": [asdict(d) for d in profile.dive_results],
            "surface_intervals": [asdict(si) for si in profile.surface_intervals],
            "final_loading_percent": round(profile.final_loading_percent, 1),
            "gf_low": profile.gf_low,
            "gf_high": profile.gf_high,
        }

        return JsonResponse(result)


# =============================================================================
# Protected Area Views
# =============================================================================


class AreaScopedMixin:
    """Mixin for views that require area_pk in URL."""

    def get_protected_area(self):
        """Get the protected area from URL kwargs."""
        if not hasattr(self, "_protected_area"):
            self._protected_area = get_object_or_404(
                ProtectedArea, pk=self.kwargs["area_pk"]
            )
        return self._protected_area

    def get_context_data(self, **kwargs):
        """Add protected area to context."""
        context = super().get_context_data(**kwargs)
        context["protected_area"] = self.get_protected_area()
        return context

    def get_success_url(self):
        """Redirect to protected area detail after success."""
        return reverse(
            "diveops:protected-area-detail", kwargs={"pk": self.kwargs["area_pk"]}
        )


class ProtectedAreaListView(StaffPortalMixin, ListView):
    """List all protected areas with hierarchy."""

    model = ProtectedArea
    template_name = "diveops/staff/protected_area_list.html"
    context_object_name = "areas"

    def get_queryset(self):
        """Return areas ordered for hierarchy display."""
        return ProtectedArea.objects.select_related("parent", "place").prefetch_related(
            "zones", "rules", "fee_schedules"
        ).order_by("parent__name", "name")

    def get_context_data(self, **kwargs):
        """Add hierarchy-aware areas to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Protected Areas"
        return context


class ProtectedAreaDetailView(StaffPortalMixin, DetailView):
    """Detail view for a protected area - the hub for all nested entities."""

    model = ProtectedArea
    template_name = "diveops/staff/protected_area_detail.html"
    context_object_name = "area"

    def get_queryset(self):
        """Prefetch related data for performance."""
        return ProtectedArea.objects.select_related("parent", "place").prefetch_related(
            "children",
            "zones__dive_sites",
            "rules__zone",
            "fee_schedules__zone",
            "fee_schedules__tiers",
            "permits__diver__person",
            "permits__organization",
            "permits__guide_details",
            "dive_sites",
        )

    def get_context_data(self, **kwargs):
        """Add nested entities to context."""
        context = super().get_context_data(**kwargs)
        area = self.object
        context["page_title"] = area.name
        # Annotate zones with rule counts for display
        context["zones"] = area.zones.filter(deleted_at__isnull=True).annotate(
            rule_count=Count("rules", filter=Q(rules__deleted_at__isnull=True))
        ).order_by("name")
        context["rules"] = area.rules.filter(deleted_at__isnull=True).order_by(
            "-effective_start", "subject"
        )
        context["fee_schedules"] = area.fee_schedules.filter(
            deleted_at__isnull=True
        ).prefetch_related("tiers").order_by("-effective_start", "name")
        # Get all permits (unified: guide + vessel) using ProtectedAreaPermit model
        all_permits = area.permits.filter(deleted_at__isnull=True).select_related(
            "diver__person", "organization"
        ).prefetch_related("guide_details").order_by("permit_type", "permit_number")
        context["permits"] = all_permits
        # Split by type for template convenience
        context["guide_permits"] = [p for p in all_permits if p.permit_type == ProtectedAreaPermit.PermitType.GUIDE]
        context["vessel_permits"] = [p for p in all_permits if p.permit_type == ProtectedAreaPermit.PermitType.VESSEL]
        context["photography_permits"] = [p for p in all_permits if p.permit_type == ProtectedAreaPermit.PermitType.PHOTOGRAPHY]
        context["diving_permits"] = [p for p in all_permits if p.permit_type == ProtectedAreaPermit.PermitType.DIVING]
        context["children"] = area.children.filter(deleted_at__isnull=True).order_by("name")
        context["dive_sites"] = area.dive_sites.filter(deleted_at__isnull=True).order_by("name")
        return context


class ProtectedAreaCreateView(StaffPortalMixin, CreateView):
    """Create a new protected area."""

    model = ProtectedArea
    form_class = ProtectedAreaForm
    template_name = "diveops/staff/protected_area_form.html"

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Protected Area"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        messages.success(self.request, f"Protected area '{self.object.name}' created.")
        return response

    def get_success_url(self):
        """Redirect to the new area's detail page."""
        return reverse("diveops:protected-area-detail", kwargs={"pk": self.object.pk})


class ProtectedAreaUpdateView(StaffPortalMixin, UpdateView):
    """Update an existing protected area."""

    model = ProtectedArea
    form_class = ProtectedAreaForm
    template_name = "diveops/staff/protected_area_form.html"

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        messages.success(self.request, f"Protected area '{self.object.name}' updated.")
        return response

    def get_success_url(self):
        """Redirect to the area's detail page."""
        return reverse("diveops:protected-area-detail", kwargs={"pk": self.object.pk})


class ProtectedAreaDeleteView(StaffPortalMixin, DeleteView):
    """Delete a protected area."""

    model = ProtectedArea
    template_name = "diveops/staff/protected_area_confirm_delete.html"
    success_url = reverse_lazy("diveops:protected-area-list")

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete {self.object.name}"
        return context

    def form_valid(self, form):
        """Soft delete and show success message."""
        area = self.object
        area.deleted_at = timezone.now()
        area.save(update_fields=["deleted_at", "updated_at"])
        messages.success(self.request, f"Protected area '{area.name}' deleted.")
        return HttpResponseRedirect(self.get_success_url())


# =============================================================================
# Protected Area Zone Views (Area-Scoped)
# =============================================================================


class ProtectedAreaZoneCreateView(StaffPortalMixin, AreaScopedMixin, CreateView):
    """Create a new zone within a protected area."""

    model = ProtectedAreaZone
    form_class = ProtectedAreaZoneForm
    template_name = "diveops/staff/protected_area_zone_form.html"

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Zone"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Set protected area before saving."""
        form.instance.protected_area = self.get_protected_area()
        response = super().form_valid(form)
        messages.success(self.request, f"Zone '{self.object.name}' created.")
        return response


class ProtectedAreaZoneDetailView(StaffPortalMixin, AreaScopedMixin, DetailView):
    """Detail view for a zone showing its rules."""

    model = ProtectedAreaZone
    template_name = "diveops/staff/protected_area_zone_detail.html"
    context_object_name = "zone"

    def get_queryset(self):
        """Filter to zones belonging to the area."""
        return ProtectedAreaZone.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add rules for this zone to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.name
        # Get rules specific to this zone
        context["zone_rules"] = ProtectedAreaRule.objects.filter(
            zone=self.object,
            deleted_at__isnull=True,
        ).order_by("rule_type", "subject")
        # Get area-wide rules (that also apply to this zone)
        context["area_rules"] = ProtectedAreaRule.objects.filter(
            protected_area=self.object.protected_area,
            zone__isnull=True,
            deleted_at__isnull=True,
        ).order_by("rule_type", "subject")
        return context


class ProtectedAreaZoneUpdateView(StaffPortalMixin, AreaScopedMixin, UpdateView):
    """Update an existing zone."""

    model = ProtectedAreaZone
    form_class = ProtectedAreaZoneForm
    template_name = "diveops/staff/protected_area_zone_form.html"

    def get_queryset(self):
        """Filter to zones belonging to the area."""
        return ProtectedAreaZone.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Zone: {self.object.name}"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        messages.success(self.request, f"Zone '{self.object.name}' updated.")
        return response


class ProtectedAreaZoneDeleteView(StaffPortalMixin, AreaScopedMixin, DeleteView):
    """Delete a zone."""

    model = ProtectedAreaZone
    template_name = "diveops/staff/protected_area_zone_confirm_delete.html"

    def get_queryset(self):
        """Filter to zones belonging to the area."""
        return ProtectedAreaZone.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete Zone: {self.object.name}"
        return context

    def form_valid(self, form):
        """Soft delete and show success message."""
        zone = self.object
        zone.deleted_at = timezone.now()
        zone.save(update_fields=["deleted_at", "updated_at"])
        messages.success(self.request, f"Zone '{zone.name}' deleted.")
        return HttpResponseRedirect(self.get_success_url())


# =============================================================================
# Protected Area Rule Views (Area-Scoped)
# =============================================================================


class ProtectedAreaRuleCreateView(StaffPortalMixin, AreaScopedMixin, CreateView):
    """Create a new rule within a protected area."""

    model = ProtectedAreaRule
    form_class = ProtectedAreaRuleForm
    template_name = "diveops/staff/protected_area_rule_form.html"

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Rule"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Set protected area before saving."""
        form.instance.protected_area = self.get_protected_area()
        response = super().form_valid(form)
        messages.success(self.request, f"Rule '{self.object.subject}' created.")
        return response


class ZoneRuleCreateView(StaffPortalMixin, AreaScopedMixin, CreateView):
    """Create a new rule for a specific zone."""

    model = ProtectedAreaRule
    form_class = ProtectedAreaRuleForm
    template_name = "diveops/staff/protected_area_rule_form.html"

    def get_zone(self):
        """Get the zone from URL."""
        return get_object_or_404(
            ProtectedAreaZone,
            pk=self.kwargs["zone_pk"],
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title and zone to context."""
        context = super().get_context_data(**kwargs)
        zone = self.get_zone()
        context["zone"] = zone
        context["page_title"] = f"Add Rule for {zone.name}"
        context["is_create"] = True
        return context

    def get_initial(self):
        """Pre-select the zone."""
        initial = super().get_initial()
        initial["zone"] = self.get_zone()
        return initial

    def form_valid(self, form):
        """Set protected area and zone before saving."""
        form.instance.protected_area = self.get_protected_area()
        form.instance.zone = self.get_zone()
        response = super().form_valid(form)
        messages.success(self.request, f"Rule '{self.object.subject}' created for {self.get_zone().name}.")
        return response

    def get_success_url(self):
        """Return to zone detail page."""
        return reverse("diveops:protected-area-zone-detail", kwargs={
            "area_pk": self.kwargs["area_pk"],
            "pk": self.kwargs["zone_pk"],
        })


class ProtectedAreaRuleUpdateView(StaffPortalMixin, AreaScopedMixin, UpdateView):
    """Update an existing rule."""

    model = ProtectedAreaRule
    form_class = ProtectedAreaRuleForm
    template_name = "diveops/staff/protected_area_rule_form.html"

    def get_queryset(self):
        """Filter to rules belonging to the area."""
        return ProtectedAreaRule.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Rule: {self.object.subject}"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        messages.success(self.request, f"Rule '{self.object.subject}' updated.")
        return response


class ProtectedAreaRuleDeleteView(StaffPortalMixin, AreaScopedMixin, DeleteView):
    """Delete a rule."""

    model = ProtectedAreaRule
    template_name = "diveops/staff/protected_area_rule_confirm_delete.html"

    def get_queryset(self):
        """Filter to rules belonging to the area."""
        return ProtectedAreaRule.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete Rule: {self.object.subject}"
        return context

    def form_valid(self, form):
        """Soft delete and show success message."""
        rule = self.object
        rule.deleted_at = timezone.now()
        rule.save(update_fields=["deleted_at", "updated_at"])
        messages.success(self.request, f"Rule '{rule.subject}' deleted.")
        return HttpResponseRedirect(self.get_success_url())


# =============================================================================
# Protected Area Fee Schedule Views (Area-Scoped)
# =============================================================================


class ProtectedAreaFeeScheduleCreateView(StaffPortalMixin, AreaScopedMixin, CreateView):
    """Create a new fee schedule within a protected area."""

    model = ProtectedAreaFeeSchedule
    form_class = ProtectedAreaFeeScheduleForm
    template_name = "diveops/staff/protected_area_fee_form.html"

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Fee Schedule"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Set protected area before saving."""
        form.instance.protected_area = self.get_protected_area()
        response = super().form_valid(form)
        messages.success(self.request, f"Fee schedule '{self.object.name}' created.")
        return response


class ProtectedAreaFeeScheduleUpdateView(StaffPortalMixin, AreaScopedMixin, UpdateView):
    """Update an existing fee schedule."""

    model = ProtectedAreaFeeSchedule
    form_class = ProtectedAreaFeeScheduleForm
    template_name = "diveops/staff/protected_area_fee_form.html"

    def get_queryset(self):
        """Filter to fee schedules belonging to the area."""
        return ProtectedAreaFeeSchedule.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Fee Schedule: {self.object.name}"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        messages.success(self.request, f"Fee schedule '{self.object.name}' updated.")
        return response


class ProtectedAreaFeeScheduleDeleteView(StaffPortalMixin, AreaScopedMixin, DeleteView):
    """Delete a fee schedule."""

    model = ProtectedAreaFeeSchedule
    template_name = "diveops/staff/protected_area_fee_confirm_delete.html"

    def get_queryset(self):
        """Filter to fee schedules belonging to the area."""
        return ProtectedAreaFeeSchedule.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete Fee Schedule: {self.object.name}"
        return context

    def form_valid(self, form):
        """Soft delete and show success message."""
        schedule = self.object
        schedule.deleted_at = timezone.now()
        schedule.save(update_fields=["deleted_at", "updated_at"])
        messages.success(self.request, f"Fee schedule '{schedule.name}' deleted.")
        return HttpResponseRedirect(self.get_success_url())


# =============================================================================
# Protected Area Fee Tier Views (Area + Schedule Scoped)
# =============================================================================


class ScheduleScopedMixin(AreaScopedMixin):
    """Mixin for views that require both area_pk and schedule_pk."""

    def get_fee_schedule(self):
        """Get the fee schedule, ensuring it belongs to the area."""
        if not hasattr(self, "_fee_schedule"):
            self._fee_schedule = get_object_or_404(
                ProtectedAreaFeeSchedule,
                pk=self.kwargs["schedule_pk"],
                protected_area_id=self.kwargs["area_pk"],
                deleted_at__isnull=True,
            )
        return self._fee_schedule

    def get_context_data(self, **kwargs):
        """Add fee schedule to context."""
        context = super().get_context_data(**kwargs)
        context["fee_schedule"] = self.get_fee_schedule()
        return context


class ProtectedAreaFeeTierCreateView(StaffPortalMixin, ScheduleScopedMixin, CreateView):
    """Create a new fee tier within a fee schedule."""

    model = ProtectedAreaFeeTier
    form_class = ProtectedAreaFeeTierForm
    template_name = "diveops/staff/protected_area_tier_form.html"

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Fee Tier"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Set fee schedule before saving."""
        form.instance.schedule = self.get_fee_schedule()
        response = super().form_valid(form)
        messages.success(self.request, f"Fee tier '{self.object.label}' created.")
        return response


class ProtectedAreaFeeTierUpdateView(StaffPortalMixin, ScheduleScopedMixin, UpdateView):
    """Update an existing fee tier."""

    model = ProtectedAreaFeeTier
    form_class = ProtectedAreaFeeTierForm
    template_name = "diveops/staff/protected_area_tier_form.html"

    def get_queryset(self):
        """Filter to tiers belonging to the schedule within the area."""
        return ProtectedAreaFeeTier.objects.filter(
            schedule_id=self.kwargs["schedule_pk"],
            schedule__protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Fee Tier: {self.object.label}"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        messages.success(self.request, f"Fee tier '{self.object.label}' updated.")
        return response


class ProtectedAreaFeeTierDeleteView(StaffPortalMixin, ScheduleScopedMixin, DeleteView):
    """Delete a fee tier."""

    model = ProtectedAreaFeeTier
    template_name = "diveops/staff/protected_area_tier_confirm_delete.html"

    def get_queryset(self):
        """Filter to tiers belonging to the schedule within the area."""
        return ProtectedAreaFeeTier.objects.filter(
            schedule_id=self.kwargs["schedule_pk"],
            schedule__protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete Fee Tier: {self.object.label}"
        return context

    def form_valid(self, form):
        """Soft delete and show success message."""
        tier = self.object
        tier.deleted_at = timezone.now()
        tier.save(update_fields=["deleted_at", "updated_at"])
        messages.success(self.request, f"Fee tier '{tier.label}' deleted.")
        return HttpResponseRedirect(self.get_success_url())


# =============================================================================
# Unified Permit Views (Area-Scoped) - Using ProtectedAreaPermit
# =============================================================================


class GuidePermitCreateView(StaffPortalMixin, AreaScopedMixin, CreateView):
    """Create a new guide permit within a protected area."""

    model = ProtectedAreaPermit
    form_class = GuidePermitForm
    template_name = "diveops/staff/permit_form.html"

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Guide Permit"
        context["permit_type"] = "guide"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Set protected area before saving."""
        form.instance.protected_area = self.get_protected_area()
        response = super().form_valid(form)
        diver_name = self.object.diver.person.get_full_name() if self.object.diver else "Unknown"
        messages.success(self.request, f"Guide permit for '{diver_name}' created.")
        return response


class GuidePermitUpdateView(StaffPortalMixin, AreaScopedMixin, UpdateView):
    """Update an existing guide permit."""

    model = ProtectedAreaPermit
    form_class = GuidePermitForm
    template_name = "diveops/staff/permit_form.html"

    def get_queryset(self):
        """Filter to guide permits belonging to the area."""
        return ProtectedAreaPermit.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            permit_type=ProtectedAreaPermit.PermitType.GUIDE,
            deleted_at__isnull=True,
        )

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        diver_name = self.object.diver.person.get_full_name() if self.object.diver else "Unknown"
        context["page_title"] = f"Edit Guide Permit: {diver_name}"
        context["permit_type"] = "guide"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        diver_name = self.object.diver.person.get_full_name() if self.object.diver else "Unknown"
        messages.success(self.request, f"Guide permit for '{diver_name}' updated.")
        return response


class VesselPermitCreateViewNew(StaffPortalMixin, AreaScopedMixin, CreateView):
    """Create a new vessel permit within a protected area (using unified model)."""

    model = ProtectedAreaPermit
    form_class = VesselPermitFormNew
    template_name = "diveops/staff/permit_form.html"

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Vessel Permit"
        context["permit_type"] = "vessel"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Set protected area before saving."""
        form.instance.protected_area = self.get_protected_area()
        response = super().form_valid(form)
        messages.success(self.request, f"Vessel permit for '{self.object.vessel_name}' created.")
        return response


class VesselPermitUpdateViewNew(StaffPortalMixin, AreaScopedMixin, UpdateView):
    """Update an existing vessel permit (using unified model)."""

    model = ProtectedAreaPermit
    form_class = VesselPermitFormNew
    template_name = "diveops/staff/permit_form.html"

    def get_queryset(self):
        """Filter to vessel permits belonging to the area."""
        return ProtectedAreaPermit.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            permit_type=ProtectedAreaPermit.PermitType.VESSEL,
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Vessel Permit: {self.object.vessel_name}"
        context["permit_type"] = "vessel"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        messages.success(self.request, f"Vessel permit for '{self.object.vessel_name}' updated.")
        return response


class PermitDeleteView(StaffPortalMixin, AreaScopedMixin, DeleteView):
    """Delete any permit (guide or vessel)."""

    model = ProtectedAreaPermit
    template_name = "diveops/staff/permit_confirm_delete.html"

    def get_queryset(self):
        """Filter to permits belonging to the area."""
        return ProtectedAreaPermit.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        permit = self.object
        if permit.permit_type == ProtectedAreaPermit.PermitType.GUIDE:
            diver_name = permit.diver.person.get_full_name() if permit.diver else "Unknown"
            context["page_title"] = f"Delete Guide Permit: {diver_name}"
            context["permit_description"] = f"Guide permit for {diver_name}"
        elif permit.permit_type == ProtectedAreaPermit.PermitType.VESSEL:
            context["page_title"] = f"Delete Vessel Permit: {permit.vessel_name}"
            context["permit_description"] = f"Vessel permit for {permit.vessel_name}"
        elif permit.permit_type == ProtectedAreaPermit.PermitType.PHOTOGRAPHY:
            diver_name = permit.diver.person.get_full_name() if permit.diver else "Unknown"
            context["page_title"] = f"Delete Photography Permit: {diver_name}"
            context["permit_description"] = f"Photography permit for {diver_name}"
        elif permit.permit_type == ProtectedAreaPermit.PermitType.DIVING:
            holder = permit.diver.person.get_full_name() if permit.diver else (permit.organization.name if permit.organization else "Unknown")
            context["page_title"] = f"Delete Ojo de Agua Permit: {holder}"
            context["permit_description"] = f"Ojo de Agua permit for {holder}"
        else:
            context["page_title"] = f"Delete Permit: {permit.permit_number}"
            context["permit_description"] = f"Permit {permit.permit_number}"
        context["permit_type"] = permit.permit_type
        return context

    def form_valid(self, form):
        """Soft delete and show success message."""
        permit = self.object
        permit.deleted_at = timezone.now()
        permit.save(update_fields=["deleted_at", "updated_at"])
        if permit.permit_type == ProtectedAreaPermit.PermitType.GUIDE:
            diver_name = permit.diver.person.get_full_name() if permit.diver else "Unknown"
            messages.success(self.request, f"Guide permit for '{diver_name}' deleted.")
        elif permit.permit_type == ProtectedAreaPermit.PermitType.VESSEL:
            messages.success(self.request, f"Vessel permit for '{permit.vessel_name}' deleted.")
        elif permit.permit_type == ProtectedAreaPermit.PermitType.PHOTOGRAPHY:
            diver_name = permit.diver.person.get_full_name() if permit.diver else "Unknown"
            messages.success(self.request, f"Photography permit for '{diver_name}' deleted.")
        elif permit.permit_type == ProtectedAreaPermit.PermitType.DIVING:
            holder = permit.diver.person.get_full_name() if permit.diver else (permit.organization.name if permit.organization else "Unknown")
            messages.success(self.request, f"Ojo de Agua permit for '{holder}' deleted.")
        else:
            messages.success(self.request, f"Permit '{permit.permit_number}' deleted.")
        return HttpResponseRedirect(self.get_success_url())


class PhotographyPermitCreateView(StaffPortalMixin, AreaScopedMixin, CreateView):
    """Create a new photography permit within a protected area."""

    model = ProtectedAreaPermit
    form_class = PhotographyPermitForm
    template_name = "diveops/staff/permit_form.html"

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Photography Permit"
        context["permit_type"] = "photography"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Set protected area before saving."""
        form.instance.protected_area = self.get_protected_area()
        response = super().form_valid(form)
        diver_name = self.object.diver.person.get_full_name() if self.object.diver else "Unknown"
        messages.success(self.request, f"Photography permit for '{diver_name}' created.")
        return response


class PhotographyPermitUpdateView(StaffPortalMixin, AreaScopedMixin, UpdateView):
    """Update an existing photography permit."""

    model = ProtectedAreaPermit
    form_class = PhotographyPermitForm
    template_name = "diveops/staff/permit_form.html"

    def get_queryset(self):
        """Filter to photography permits belonging to the area."""
        return ProtectedAreaPermit.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            permit_type=ProtectedAreaPermit.PermitType.PHOTOGRAPHY,
            deleted_at__isnull=True,
        )

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        diver_name = self.object.diver.person.get_full_name() if self.object.diver else "Unknown"
        context["page_title"] = f"Edit Photography Permit: {diver_name}"
        context["permit_type"] = "photography"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        diver_name = self.object.diver.person.get_full_name() if self.object.diver else "Unknown"
        messages.success(self.request, f"Photography permit for '{diver_name}' updated.")
        return response


class DivingPermitCreateView(StaffPortalMixin, AreaScopedMixin, CreateView):
    """Create a new diving permit within a protected area."""

    model = ProtectedAreaPermit
    form_class = DivingPermitForm
    template_name = "diveops/staff/permit_form.html"

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add Ojo de Agua Permit"
        context["permit_type"] = "diving"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        """Set protected area before saving."""
        form.instance.protected_area = self.get_protected_area()
        response = super().form_valid(form)
        if self.object.diver:
            holder = self.object.diver.person.get_full_name()
        elif self.object.organization:
            holder = self.object.organization.name
        else:
            holder = "Unknown"
        messages.success(self.request, f"Ojo de Agua permit for '{holder}' created.")
        return response


class DivingPermitUpdateView(StaffPortalMixin, AreaScopedMixin, UpdateView):
    """Update an existing diving permit."""

    model = ProtectedAreaPermit
    form_class = DivingPermitForm
    template_name = "diveops/staff/permit_form.html"

    def get_queryset(self):
        """Filter to diving permits belonging to the area."""
        return ProtectedAreaPermit.objects.filter(
            protected_area_id=self.kwargs["area_pk"],
            permit_type=ProtectedAreaPermit.PermitType.DIVING,
            deleted_at__isnull=True,
        )

    def get_form_kwargs(self):
        """Pass protected area to form."""
        kwargs = super().get_form_kwargs()
        kwargs["protected_area"] = self.get_protected_area()
        return kwargs

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        if self.object.diver:
            holder = self.object.diver.person.get_full_name()
        elif self.object.organization:
            holder = self.object.organization.name
        else:
            holder = "Unknown"
        context["page_title"] = f"Edit Ojo de Agua Permit: {holder}"
        context["permit_type"] = "diving"
        context["is_create"] = False
        return context

    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        if self.object.diver:
            holder = self.object.diver.person.get_full_name()
        elif self.object.organization:
            holder = self.object.organization.name
        else:
            holder = "Unknown"
        messages.success(self.request, f"Ojo de Agua permit for '{holder}' updated.")
        return response


# =============================================================================
# SignableAgreement Views (Waiver Signing Workflow)
# =============================================================================


class SignableAgreementListView(StaffPortalMixin, ListView):
    """List all signable agreements with filtering by status."""

    template_name = "diveops/staff/signable_agreement_list.html"
    context_object_name = "agreements"
    paginate_by = 25

    def get_queryset(self):
        """Get signable agreements with filtering."""
        from .models import SignableAgreement

        queryset = SignableAgreement.objects.select_related(
            "template",
            "party_a_content_type",
            "sent_by",
            "signed_document",
        ).order_by("-created_at")

        # Filter by status if provided
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Filter by template if provided
        template_id = self.request.GET.get("template")
        if template_id:
            queryset = queryset.filter(template_id=template_id)

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options and medical documents to context."""
        from .models import AgreementTemplate, SignableAgreement
        from django_documents.models import Document
        from django.contrib.contenttypes.models import ContentType

        context = super().get_context_data(**kwargs)
        context["page_title"] = "Signable Agreements"
        context["status_filter"] = self.request.GET.get("status", "")
        context["template_filter"] = self.request.GET.get("template", "")
        context["status_choices"] = SignableAgreement.Status.choices
        context["templates"] = AgreementTemplate.objects.filter(
            deleted_at__isnull=True
        ).order_by("name")

        # Add signed medical questionnaire documents
        # These are attached to DiverProfile and have document_type="signed_medical_questionnaire"
        from .models import DiverProfile
        diver_ct = ContentType.objects.get_for_model(DiverProfile)
        context["medical_documents"] = Document.objects.filter(
            target_content_type=diver_ct,
            document_type="signed_medical_questionnaire",
            deleted_at__isnull=True,
        ).select_related("target_content_type").order_by("-created_at")[:50]

        return context


class SignableAgreementCreateView(StaffPortalMixin, View):
    """Create a new signable agreement from a template."""

    template_name = "diveops/staff/signable_agreement_create.html"

    def get(self, request):
        """Show the create form with template and party selection."""
        from .models import AgreementTemplate, DiverProfile

        templates = AgreementTemplate.objects.filter(
            deleted_at__isnull=True,
            status=AgreementTemplate.Status.PUBLISHED,
        ).order_by("name")

        divers = DiverProfile.objects.select_related("person").order_by(
            "person__last_name", "person__first_name"
        )

        # Check for pre-selected values from query params
        selected_template = request.GET.get("template")
        selected_diver = request.GET.get("diver")

        context = {
            "page_title": "New Agreement",
            "templates": templates,
            "divers": divers,
            "selected_template": selected_template,
            "selected_diver": selected_diver,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """Create the agreement and optionally send it."""
        from . import services
        from .models import AgreementTemplate, DiverProfile

        template_id = request.POST.get("template")
        diver_id = request.POST.get("diver")
        action = request.POST.get("action", "draft")  # draft or send
        delivery_method = request.POST.get("delivery_method", "link")
        expires_in_days = int(request.POST.get("expires_in_days", 30))

        errors = []

        if not template_id:
            errors.append("Please select an agreement template.")
        if not diver_id:
            errors.append("Please select a diver.")

        if errors:
            templates = AgreementTemplate.objects.filter(
                deleted_at__isnull=True,
                status=AgreementTemplate.Status.PUBLISHED,
            ).order_by("name")
            divers = DiverProfile.objects.select_related("person").order_by(
                "person__last_name", "person__first_name"
            )
            context = {
                "page_title": "New Agreement",
                "templates": templates,
                "divers": divers,
                "errors": errors,
                "selected_template": template_id,
                "selected_diver": diver_id,
            }
            return render(request, self.template_name, context)

        try:
            template = AgreementTemplate.objects.get(pk=template_id)
            diver = DiverProfile.objects.select_related("person").get(pk=diver_id)

            # Create the agreement - pass the person as party_a
            agreement = services.create_agreement_from_template(
                template=template,
                party_a=diver.person,
                actor=request.user,
            )

            # If action is send, send it immediately
            if action == "send":
                agreement, raw_token = services.send_agreement(
                    agreement=agreement,
                    delivery_method=delivery_method,
                    expires_in_days=expires_in_days,
                    actor=request.user,
                )
                signing_url = request.build_absolute_uri(f"/sign/{raw_token}/")
                messages.success(
                    request,
                    f"Agreement created and sent. Signing URL: {signing_url}",
                )
            else:
                messages.success(request, "Agreement created as draft.")

            return redirect("diveops:signable-agreement-detail", pk=agreement.pk)

        except AgreementTemplate.DoesNotExist:
            errors.append("Selected template not found.")
        except DiverProfile.DoesNotExist:
            errors.append("Selected diver not found.")
        except Exception as e:
            errors.append(str(e))

        templates = AgreementTemplate.objects.filter(
            deleted_at__isnull=True,
            status=AgreementTemplate.Status.PUBLISHED,
        ).order_by("name")
        divers = DiverProfile.objects.select_related("person").order_by(
            "person__last_name", "person__first_name"
        )
        context = {
            "page_title": "New Agreement",
            "templates": templates,
            "divers": divers,
            "errors": errors,
            "selected_template": template_id,
            "selected_diver": diver_id,
        }
        return render(request, self.template_name, context)


class SignableAgreementDetailView(StaffPortalMixin, DetailView):
    """View details of a signable agreement."""

    template_name = "diveops/staff/signable_agreement_detail.html"
    context_object_name = "agreement"

    def get_queryset(self):
        """Get signable agreement with related data."""
        from .models import SignableAgreement

        return SignableAgreement.objects.select_related(
            "template",
            "party_a_content_type",
            "sent_by",
            "ledger_agreement",
            "signed_document",
        ).prefetch_related("revisions")

    def get_context_data(self, **kwargs):
        """Add context data."""
        context = super().get_context_data(**kwargs)
        agreement = self.object

        # Get party_a display name
        party_a = agreement.party_a
        if party_a:
            if hasattr(party_a, "first_name") and hasattr(party_a, "last_name"):
                party_name = f"{party_a.first_name} {party_a.last_name}"
            elif hasattr(party_a, "name"):
                party_name = party_a.name
            else:
                party_name = str(party_a)
        else:
            party_name = "Unknown"

        context["page_title"] = f"Agreement: {agreement.template.name}"
        context["party_name"] = party_name

        # Build signing URL if token is available
        if agreement.access_token and agreement.status == "sent":
            context["signing_url"] = self.request.build_absolute_uri(
                f"/sign/{agreement.access_token}/"
            )

        return context


class SignableAgreementPrintView(StaffPortalMixin, DetailView):
    """Printable view of a signable agreement.

    For signed agreements with a PDF, redirects to the PDF.
    For unsigned agreements, shows HTML print view.
    """

    template_name = "diveops/staff/signable_agreement_print.html"
    context_object_name = "agreement"

    def get_queryset(self):
        """Get signable agreement with related data."""
        from .models import SignableAgreement

        return SignableAgreement.objects.select_related(
            "template",
            "party_a_content_type",
            "signed_document",
        )

    def get(self, request, *args, **kwargs):
        """Redirect to signed PDF if available, otherwise show HTML print view."""
        self.object = self.get_object()

        # If signed and has PDF, redirect to it
        if (self.object.status == "signed" and
            self.object.signed_document and
            self.object.signed_document.file):
            return redirect(self.object.signed_document.file.url)

        # Otherwise show HTML print view
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Add context data for printing."""
        context = super().get_context_data(**kwargs)
        agreement = self.object

        # Get party_a display name
        party_a = agreement.party_a
        if party_a:
            if hasattr(party_a, "first_name") and hasattr(party_a, "last_name"):
                party_name = f"{party_a.first_name} {party_a.last_name}"
            elif hasattr(party_a, "name"):
                party_name = party_a.name
            else:
                party_name = str(party_a)
        else:
            party_name = "Unknown"

        context["party_name"] = party_name

        return context


class SignableAgreementEditView(StaffPortalMixin, View):
    """Edit a signable agreement's content."""

    def _get_party_name(self, agreement):
        """Get display name for party_a."""
        party_a = agreement.party_a
        if party_a:
            if hasattr(party_a, "first_name") and hasattr(party_a, "last_name"):
                return f"{party_a.first_name} {party_a.last_name}"
            elif hasattr(party_a, "name"):
                return party_a.name
            else:
                return str(party_a)
        return "Unknown"

    def get(self, request, pk):
        """Show edit form."""
        from .models import SignableAgreement

        agreement = get_object_or_404(SignableAgreement, pk=pk)

        # Can only edit draft or sent agreements
        if agreement.status not in ("draft", "sent"):
            messages.error(
                request,
                "Only draft or sent agreements can be edited.",
            )
            return redirect("diveops:signable-agreement-detail", pk=pk)

        return render(
            request,
            "diveops/staff/signable_agreement_edit.html",
            {
                "agreement": agreement,
                "party_name": self._get_party_name(agreement),
                "page_title": f"Edit: {agreement.template.name}",
            },
        )

    def post(self, request, pk):
        """Save edited agreement."""
        from .models import SignableAgreement
        from .services import edit_agreement

        agreement = get_object_or_404(SignableAgreement, pk=pk)

        # Can only edit draft or sent agreements
        if agreement.status not in ("draft", "sent"):
            messages.error(
                request,
                "Only draft or sent agreements can be edited.",
            )
            return redirect("diveops:signable-agreement-detail", pk=pk)

        new_content = request.POST.get("content", "").strip()
        change_note = request.POST.get("change_note", "").strip()

        if not change_note:
            messages.error(request, "Change note is required when editing an agreement.")
            return render(
                request,
                "diveops/staff/signable_agreement_edit.html",
                {
                    "agreement": agreement,
                    "party_name": self._get_party_name(agreement),
                    "page_title": f"Edit: {agreement.template.name}",
                    "content": new_content,
                    "error": "Change note is required.",
                },
            )

        try:
            edit_agreement(
                agreement=agreement,
                new_content=new_content,
                change_note=change_note,
                actor=request.user,
            )
            messages.success(request, "Agreement updated successfully.")
        except Exception as e:
            messages.error(request, f"Failed to update agreement: {e}")

        return redirect("diveops:signable-agreement-detail", pk=pk)


class SignableAgreementResendView(StaffPortalMixin, View):
    """Resend a signable agreement (generates new token)."""

    def _get_party_name(self, agreement):
        """Get display name for party_a."""
        party_a = agreement.party_a
        if party_a:
            if hasattr(party_a, "first_name") and hasattr(party_a, "last_name"):
                return f"{party_a.first_name} {party_a.last_name}"
            elif hasattr(party_a, "name"):
                return party_a.name
            else:
                return str(party_a)
        return "Unknown"

    def get(self, request, pk):
        """Show confirmation page."""
        from .models import SignableAgreement

        agreement = get_object_or_404(SignableAgreement, pk=pk)

        # Can only resend sent agreements
        if agreement.status != "sent":
            messages.error(
                request,
                "Only sent agreements can be resent.",
            )
            return redirect("diveops:signable-agreement-detail", pk=pk)

        return render(
            request,
            "diveops/staff/signable_agreement_resend.html",
            {
                "agreement": agreement,
                "party_name": self._get_party_name(agreement),
                "page_title": f"Resend: {agreement.template.name}",
                "delivery_methods": [
                    ("email", "Send via Email"),
                    ("link", "Generate Link"),
                    ("in_person", "In-Person Signing"),
                ],
            },
        )

    def post(self, request, pk):
        """Resend the agreement with a new token."""
        from .models import SignableAgreement
        from .services import resend_agreement

        agreement = get_object_or_404(SignableAgreement, pk=pk)

        # Can only resend sent agreements
        if agreement.status != "sent":
            messages.error(
                request,
                "Only sent agreements can be resent.",
            )
            return redirect("diveops:signable-agreement-detail", pk=pk)

        # Get delivery method
        delivery_method = request.POST.get("delivery_method", "link")
        if delivery_method not in ("email", "link", "in_person"):
            delivery_method = "link"

        # Get expiration days
        try:
            expires_in_days = int(request.POST.get("expires_in_days", 30))
        except ValueError:
            expires_in_days = 30

        try:
            agreement, token = resend_agreement(
                agreement=agreement,
                delivery_method=delivery_method,
                expires_in_days=expires_in_days,
                actor=request.user,
            )

            # Build the signing URL
            signing_url = request.build_absolute_uri(f"/sign/{token}/")
            party_name = self._get_party_name(agreement)

            messages.success(
                request,
                f"Agreement resent to {party_name}. New signing link: {signing_url}"
            )
        except Exception as e:
            messages.error(request, f"Failed to resend agreement: {e}")

        return redirect("diveops:signable-agreement-detail", pk=pk)


class SignableAgreementVoidView(StaffPortalMixin, View):
    """Void a signable agreement."""

    def get(self, request, pk):
        """Show confirmation page."""
        from .models import SignableAgreement

        agreement = get_object_or_404(SignableAgreement, pk=pk)

        # Get party name for display
        party_a = agreement.party_a
        if party_a:
            if hasattr(party_a, "first_name") and hasattr(party_a, "last_name"):
                party_name = f"{party_a.first_name} {party_a.last_name}"
            elif hasattr(party_a, "name"):
                party_name = party_a.name
            else:
                party_name = str(party_a)
        else:
            party_name = "Unknown"

        return render(
            request,
            "diveops/staff/signable_agreement_void.html",
            {
                "agreement": agreement,
                "party_name": party_name,
                "page_title": f"Void Agreement: {agreement.template.name}",
            },
        )

    def post(self, request, pk):
        """Void the agreement."""
        from .models import SignableAgreement
        from .services import void_agreement

        agreement = get_object_or_404(SignableAgreement, pk=pk)
        reason = request.POST.get("reason", "").strip()

        if not reason:
            messages.error(request, "Reason is required to void an agreement.")
            return HttpResponseRedirect(
                reverse("diveops:signable-agreement-void", kwargs={"pk": pk})
            )

        try:
            void_agreement(agreement=agreement, reason=reason, actor=request.user)
            messages.success(request, f"Agreement voided: {agreement.template.name}")
        except Exception as e:
            messages.error(request, f"Error voiding agreement: {e}")
            return HttpResponseRedirect(
                reverse("diveops:signable-agreement-void", kwargs={"pk": pk})
            )

        return HttpResponseRedirect(reverse("diveops:signable-agreement-list"))


class SignableAgreementRevisionDiffView(StaffPortalMixin, View):
    """View the diff between agreement revisions."""

    def get(self, request, pk, revision_pk):
        """Return diff HTML for a specific revision."""
        import difflib

        from .models import SignableAgreement, SignableAgreementRevision

        agreement = get_object_or_404(SignableAgreement, pk=pk)
        revision = get_object_or_404(
            SignableAgreementRevision,
            pk=revision_pk,
            agreement=agreement,
        )

        # Get the "before" content
        content_before = revision.content_before or ""

        # Get the "after" content
        # If this is the latest revision, use current content_snapshot
        # Otherwise, use the next revision's content_before
        next_revision = agreement.revisions.filter(
            revision_number__gt=revision.revision_number
        ).order_by("revision_number").first()

        if next_revision and next_revision.content_before:
            content_after = next_revision.content_before
        else:
            # This is the latest revision, use current content
            content_after = agreement.content_snapshot or ""

        # Generate unified diff
        before_lines = content_before.splitlines(keepends=True)
        after_lines = content_after.splitlines(keepends=True)

        diff = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"Revision {revision.revision_number - 1}" if revision.revision_number > 1 else "Original",
            tofile=f"Revision {revision.revision_number}",
            lineterm="",
        )
        diff_text = "".join(diff)

        # Also generate HTML diff for side-by-side view
        differ = difflib.HtmlDiff(wrapcolumn=80)
        html_diff = differ.make_table(
            before_lines,
            after_lines,
            fromdesc=f"Before (Rev {revision.revision_number - 1})" if revision.revision_number > 1 else "Original",
            todesc=f"After (Rev {revision.revision_number})",
            context=True,
            numlines=3,
        )

        return render(
            request,
            "diveops/staff/signable_agreement_revision_diff.html",
            {
                "agreement": agreement,
                "revision": revision,
                "diff_text": diff_text,
                "html_diff": html_diff,
                "page_title": f"Revision {revision.revision_number} Diff",
            },
        )


# =============================================================================
# AI Settings Configuration
# =============================================================================


class AISettingsView(StaffPortalMixin, TemplateView):
    """View and edit AI settings configuration."""

    template_name = "diveops/staff/ai_settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = AISettings.get_instance()
        context["settings"] = settings
        context["page_title"] = "AI Settings"

        # Get value sources for display
        context["openrouter_source"] = settings.get_value_source("openrouter_api_key")
        context["openai_source"] = settings.get_value_source("openai_api_key")

        # Check if AI is configured
        context["is_configured"] = settings.is_configured()

        return context

    def post(self, request, *args, **kwargs):
        settings = AISettings.get_instance()

        # Update API keys (only if provided, preserves existing if blank)
        openrouter_key = request.POST.get("openrouter_api_key", "").strip()
        openai_key = request.POST.get("openai_api_key", "").strip()

        # Allow clearing by sending empty string with explicit clear flag
        if request.POST.get("clear_openrouter"):
            settings.openrouter_api_key = ""
        elif openrouter_key:
            settings.openrouter_api_key = openrouter_key

        if request.POST.get("clear_openai"):
            settings.openai_api_key = ""
        elif openai_key:
            settings.openai_api_key = openai_key

        # Update model settings
        settings.default_model = request.POST.get("default_model", settings.default_model)

        # Update feature flags
        settings.ocr_enhancement_enabled = request.POST.get("ocr_enhancement_enabled") == "on"
        settings.auto_extract_enabled = request.POST.get("auto_extract_enabled") == "on"

        settings.save()

        messages.success(request, "AI settings saved successfully.")
        return redirect("diveops:ai-settings")


# ============================================================================
# Medical Questionnaire Views
# ============================================================================


class MedicalQuestionnaireListView(StaffPortalMixin, ListView):
    """List all medical questionnaire instances."""

    template_name = "diveops/staff/medical/questionnaire_list.html"
    context_object_name = "instances"
    paginate_by = 25

    def get_queryset(self):
        from django_questionnaires.models import QuestionnaireInstance, InstanceStatus
        from django.utils import timezone
        from datetime import timedelta

        queryset = QuestionnaireInstance.objects.filter(
            definition__slug="rstc-medical",
            deleted_at__isnull=True,
        ).select_related(
            "definition",
            "respondent_content_type",
            "cleared_by",
        )

        # Filter by status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Filter by expiration
        expiration_filter = self.request.GET.get("expiration")
        now = timezone.now()
        if expiration_filter == "expired":
            queryset = queryset.filter(expires_at__lt=now)
        elif expiration_filter == "expiring_soon":
            # Expiring within 30 days
            queryset = queryset.filter(
                expires_at__gte=now,
                expires_at__lte=now + timedelta(days=30)
            )
        elif expiration_filter == "expiring_90":
            # Expiring within 90 days
            queryset = queryset.filter(
                expires_at__gte=now,
                expires_at__lte=now + timedelta(days=90)
            )
        elif expiration_filter == "valid":
            queryset = queryset.filter(expires_at__gte=now)

        # Sorting
        sort = self.request.GET.get("sort", "-created_at")
        valid_sorts = ["expires_at", "-expires_at", "created_at", "-created_at", "status"]
        if sort in valid_sorts:
            queryset = queryset.order_by(sort)
        else:
            queryset = queryset.order_by("-created_at")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django_questionnaires.models import InstanceStatus
        context["status_choices"] = InstanceStatus.choices
        context["current_status"] = self.request.GET.get("status", "")
        context["current_expiration"] = self.request.GET.get("expiration", "")
        context["current_sort"] = self.request.GET.get("sort", "-created_at")
        context["expiration_choices"] = [
            ("", "All"),
            ("valid", "Valid (Not Expired)"),
            ("expiring_soon", "Expiring in 30 days"),
            ("expiring_90", "Expiring in 90 days"),
            ("expired", "Expired"),
        ]
        context["sort_choices"] = [
            ("-created_at", "Newest First"),
            ("created_at", "Oldest First"),
            ("expires_at", "Expiring Soonest"),
            ("-expires_at", "Expiring Latest"),
        ]
        return context


class MedicalQuestionnaireDetailView(StaffPortalMixin, DetailView):
    """View medical questionnaire details and responses."""

    template_name = "diveops/staff/medical/questionnaire_detail.html"
    context_object_name = "instance"

    def get_object(self):
        from django_questionnaires.models import QuestionnaireInstance
        return get_object_or_404(
            QuestionnaireInstance,
            pk=self.kwargs["pk"],
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django_questionnaires.services import get_flagged_questions

        instance = self.object

        # Get all questions with their responses
        questions = list(instance.definition.questions.all())
        responses = {r.question_id: r for r in instance.responses.all()}

        # Build question-response pairs
        context["questions_responses"] = [
            {
                "question": q,
                "response": responses.get(q.id),
            }
            for q in questions
        ]

        # Get flagged questions
        context["flagged_questions"] = get_flagged_questions(instance)

        # Get diver if respondent is a DiverProfile
        if instance.respondent_content_type.model == "diverprofile":
            context["diver"] = instance.respondent

        # Get PDF document if available
        if instance.metadata and instance.metadata.get("pdf_document_id"):
            from django_documents.models import Document
            try:
                context["pdf_document"] = Document.objects.get(
                    pk=instance.metadata["pdf_document_id"]
                )
            except Document.DoesNotExist:
                pass

        return context


class MedicalQuestionnairePDFDownloadView(StaffPortalMixin, View):
    """Download the stored PDF for a completed medical questionnaire."""

    def get(self, request, pk):
        from django.http import HttpResponse, Http404, FileResponse
        from django_questionnaires.models import QuestionnaireInstance
        from django_documents.models import Document

        instance = get_object_or_404(
            QuestionnaireInstance,
            pk=pk,
            deleted_at__isnull=True,
        )

        # Only allow PDF download for completed, flagged, or cleared questionnaires
        if instance.status not in ('completed', 'flagged', 'cleared'):
            raise Http404("PDF not available for pending questionnaires")

        # Get the stored PDF document
        pdf_document_id = instance.metadata.get('pdf_document_id') if instance.metadata else None
        if not pdf_document_id:
            raise Http404("No PDF document found for this questionnaire")

        try:
            document = Document.objects.get(pk=pdf_document_id, deleted_at__isnull=True)
        except Document.DoesNotExist:
            raise Http404("PDF document not found")

        # Serve the stored file
        response = FileResponse(
            document.file.open('rb'),
            content_type='application/pdf',
            as_attachment=True,
            filename=document.filename,
        )
        return response


class MedicalClearanceUploadView(StaffPortalMixin, View):
    """Upload physician clearance for a flagged questionnaire."""

    template_name = "diveops/staff/medical/clearance_upload.html"

    def get(self, request, pk):
        from django_questionnaires.models import QuestionnaireInstance, InstanceStatus

        instance = get_object_or_404(
            QuestionnaireInstance,
            pk=pk,
            deleted_at__isnull=True,
        )

        if instance.status != InstanceStatus.FLAGGED:
            messages.error(request, "This questionnaire is not flagged and cannot be cleared.")
            return redirect("diveops:medical-detail", pk=pk)

        return render(request, self.template_name, {"instance": instance})

    def post(self, request, pk):
        from django_questionnaires.models import QuestionnaireInstance, InstanceStatus
        from .medical.services import upload_physician_clearance

        instance = get_object_or_404(
            QuestionnaireInstance,
            pk=pk,
            deleted_at__isnull=True,
        )

        if instance.status != InstanceStatus.FLAGGED:
            messages.error(request, "This questionnaire is not flagged and cannot be cleared.")
            return redirect("diveops:medical-detail", pk=pk)

        notes = request.POST.get("notes", "")

        # Handle file upload if provided
        document = None
        if "clearance_document" in request.FILES:
            from django_documents.services import upload_document, get_or_create_folder

            file = request.FILES["clearance_document"]
            folder = get_or_create_folder("Medical Clearances")

            document = upload_document(
                file=file,
                folder=folder,
                title=f"Physician Clearance - {instance.respondent}",
                actor=request.user,
            )

        # Clear the instance
        upload_physician_clearance(
            instance=instance,
            document=document,
            cleared_by=request.user,
            notes=notes,
        )

        messages.success(request, "Medical questionnaire cleared successfully.")
        return redirect("diveops:medical-detail", pk=pk)


class DiverMedicalStatusView(StaffPortalMixin, DetailView):
    """View a diver's medical status and history."""

    template_name = "diveops/staff/medical/diver_medical_status.html"
    model = DiverProfile
    context_object_name = "diver"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django_questionnaires.models import QuestionnaireInstance
        from .medical.services import get_diver_medical_status, MedicalStatus

        diver = self.object

        # Get current medical status
        context["medical_status"] = get_diver_medical_status(diver)
        context["MedicalStatus"] = MedicalStatus

        # Get all medical questionnaire instances for this diver
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(diver)

        context["medical_instances"] = QuestionnaireInstance.objects.filter(
            definition__slug="rstc-medical",
            respondent_content_type=content_type,
            respondent_object_id=str(diver.pk),
            deleted_at__isnull=True,
        ).select_related("definition", "cleared_by").order_by("-created_at")

        return context


class SendMedicalQuestionnaireView(StaffPortalMixin, View):
    """Send a medical questionnaire to a diver."""

    template_name = "diveops/staff/medical/send_questionnaire.html"

    def get(self, request, diver_pk):
        diver = get_object_or_404(DiverProfile, pk=diver_pk)
        return render(request, self.template_name, {
            "diver": diver,
            "default_expires_days": 365,
        })

    def post(self, request, diver_pk):
        from .medical.services import send_medical_questionnaire

        diver = get_object_or_404(DiverProfile, pk=diver_pk)

        # Get custom expiration days (default to 365)
        try:
            expires_in_days = int(request.POST.get("expires_in_days", 365))
            if expires_in_days < 1:
                expires_in_days = 365
            if expires_in_days > 730:  # Max 2 years
                expires_in_days = 730
        except (ValueError, TypeError):
            expires_in_days = 365

        try:
            instance = send_medical_questionnaire(
                diver=diver,
                expires_in_days=expires_in_days,
                actor=request.user,
            )
            messages.success(
                request,
                f"Medical questionnaire sent to {diver}. Expires in {expires_in_days} days."
            )
        except Exception as e:
            messages.error(request, f"Error sending questionnaire: {e}")

        return redirect("diveops:diver-medical-status", pk=diver_pk)


class SendMedicalQuestionnaireCreateView(StaffPortalMixin, View):
    """Create and send a new medical questionnaire - with diver picker."""

    template_name = "diveops/staff/medical/send_questionnaire_create.html"

    def get(self, request):
        """Show the create form with diver selection."""
        from .models import DiverProfile

        divers = DiverProfile.objects.select_related("person").order_by(
            "person__last_name", "person__first_name"
        )

        # Check for pre-selected diver from query params
        selected_diver = request.GET.get("diver")

        context = {
            "page_title": "Send Medical Questionnaire",
            "divers": divers,
            "selected_diver": selected_diver,
            "default_expires_days": 365,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """Create and send the questionnaire."""
        from .medical.services import send_medical_questionnaire
        from .models import DiverProfile

        diver_id = request.POST.get("diver")
        expires_in_days = request.POST.get("expires_in_days", 365)

        try:
            expires_in_days = int(expires_in_days)
            if expires_in_days < 1:
                expires_in_days = 365
            if expires_in_days > 730:
                expires_in_days = 730
        except (ValueError, TypeError):
            expires_in_days = 365

        if not diver_id:
            divers = DiverProfile.objects.select_related("person").order_by(
                "person__last_name", "person__first_name"
            )
            context = {
                "page_title": "Send Medical Questionnaire",
                "divers": divers,
                "errors": ["Please select a diver."],
                "selected_diver": diver_id,
                "default_expires_days": expires_in_days,
            }
            return render(request, self.template_name, context)

        try:
            diver = DiverProfile.objects.select_related("person").get(pk=diver_id)

            instance = send_medical_questionnaire(
                diver=diver,
                expires_in_days=expires_in_days,
                actor=request.user,
            )

            # Build the public URL for the questionnaire
            public_url = request.build_absolute_uri(
                reverse("diveops_public:medical-questionnaire", kwargs={"instance_id": instance.pk})
            )

            messages.success(
                request,
                f"Medical questionnaire sent to {diver}. Link: {public_url}"
            )
            return redirect("diveops:medical-list")

        except DiverProfile.DoesNotExist:
            messages.error(request, "Diver not found.")
            return redirect("diveops:medical-list")
        except Exception as e:
            messages.error(request, f"Error sending questionnaire: {e}")
            return redirect("diveops:medical-list")
