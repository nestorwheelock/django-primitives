"""Staff portal views for diveops."""

from django.contrib import messages
from django.db.models import Prefetch
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView, View

from django_portal_ui.mixins import StaffPortalMixin

from django_catalog.models import CatalogItem

from .forms import AgreementForm, AgreementTemplateForm, AgreementTerminateForm, CatalogItemForm, DiverCertificationForm, DiverForm, DiveSiteForm, ExcursionTypeDiveForm, ExcursionTypeForm, PriceForm, SignatureForm, SitePriceAdjustmentForm, VendorInvoiceForm, VendorPaymentForm
from .models import AgreementTemplate, Booking, CertificationLevel, DiverCertification, DiverProfile, DiveLog, DiveSite, Excursion, ExcursionType, ExcursionTypeDive, SitePriceAdjustment
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
        """Return dive templates, grouped by excursion type."""
        return ExcursionTypeDive.objects.select_related(
            "excursion_type", "dive_site"
        ).order_by("excursion_type__name", "sequence")

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
            DiveSite.objects.select_related("place", "min_certification_level"),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        """Add page title, price adjustments, dive plans, and excursion types to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.name
        # Get price adjustments for this site
        context["price_adjustments"] = self.object.price_adjustments.all().order_by("kind")
        # Get dive plans (ExcursionTypeDive) for this site
        context["dive_plans"] = self.object.dive_plan_templates.select_related(
            "excursion_type"
        ).order_by("excursion_type__name", "sequence")
        # Get excursion types where this site is in suitable_sites
        context["excursion_types"] = self.object.excursion_types.filter(
            is_active=True
        ).order_by("name")
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
                queryset=ExcursionTypeDive.objects.select_related("excursion_type").order_by("excursion_type__name"),
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
                "excursion_type", "min_certification_level", "min_certification_level__agency"
            ),
            pk=kwargs["pk"],
        )
        self.excursion_type = self.dive_template.excursion_type
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
        return HttpResponseRedirect(
            reverse("diveops:excursion-type-detail", kwargs={"pk": self.excursion_type.pk})
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        context["page_title"] = f"Edit Dive {self.dive_template.sequence}: {self.dive_template.name}"
        context["excursion_type"] = self.excursion_type
        context["dive_template"] = self.dive_template
        return context


class ExcursionTypeDiveDeleteView(StaffPortalMixin, View):
    """Delete a dive template from an excursion type."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show delete confirmation page."""
        dive_template = get_object_or_404(
            ExcursionTypeDive.objects.select_related("excursion_type"),
            pk=pk,
        )
        return self.render_confirmation(request, dive_template)

    def post(self, request, pk):
        """Perform hard delete using service layer."""
        from .services import delete_dive_template

        dive_template = get_object_or_404(
            ExcursionTypeDive.objects.select_related("excursion_type"),
            pk=pk,
        )
        excursion_type = dive_template.excursion_type
        template_name = dive_template.name

        delete_dive_template(actor=request.user, dive_template=dive_template)

        messages.success(request, f"Dive template '{template_name}' has been deleted.")
        return HttpResponseRedirect(
            reverse("diveops:excursion-type-detail", kwargs={"pk": excursion_type.pk})
        )

    def render_confirmation(self, request, dive_template):
        """Render delete confirmation template."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "diveops/staff/excursion_type_dive_confirm_delete.html",
            {
                "dive_template": dive_template,
                "excursion_type": dive_template.excursion_type,
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
        """Add page title and prices to context."""
        from primitives_testbed.pricing.models import Price

        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.display_name
        context["prices"] = Price.objects.filter(
            catalog_item=self.object, deleted_at__isnull=True
        ).order_by("-priority", "-valid_from")[:5]
        context["price_count"] = Price.objects.filter(
            catalog_item=self.object, deleted_at__isnull=True
        ).count()
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
            ExcursionTypeDive.objects.select_related(
                "excursion_type", "dive_site", "min_certification_level"
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        """Add page title to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Dive Plan: {self.object.name}"
        return context


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
            ExcursionTypeDive.objects.select_related("excursion_type"),
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
        context["excursion_type"] = self.dive_plan.excursion_type
        return context


class DivePlanDeleteView(StaffPortalMixin, View):
    """Delete a dive plan template."""

    http_method_names = ["get", "post"]

    def get(self, request, pk):
        """Show delete confirmation page."""
        dive_plan = get_object_or_404(
            ExcursionTypeDive.objects.select_related("excursion_type"),
            pk=pk,
        )
        return self.render_confirmation(request, dive_plan)

    def post(self, request, pk):
        """Perform hard delete using service layer."""
        from .services import delete_dive_template

        dive_plan = get_object_or_404(
            ExcursionTypeDive.objects.select_related("excursion_type"),
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
                "excursion_type": dive_plan.excursion_type,
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
            deleted_at__isnull=True,
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
# Agreement Template Management (Paperwork)
# =============================================================================


class AgreementTemplateListView(StaffPortalMixin, ListView):
    """List all agreement templates (paperwork forms)."""

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
        context["page_title"] = "Paperwork Templates"
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
        """Add context data."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Template: {self.object.name}"
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
