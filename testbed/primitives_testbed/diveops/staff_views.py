"""Staff portal views for diveops."""

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView, View

from django_portal_ui.mixins import StaffPortalMixin

from .forms import DiverCertificationForm, DiverForm, DiveSiteForm, ExcursionTypeDiveForm, ExcursionTypeForm, SitePriceAdjustmentForm
from .models import Booking, CertificationLevel, DiverCertification, DiverProfile, DiveSite, Excursion, ExcursionType, ExcursionTypeDive, SitePriceAdjustment
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
        """Add page title and price adjustments to context."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.name
        # Get price adjustments for this site
        context["price_adjustments"] = self.object.price_adjustments.all().order_by("kind")
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
        context["page_title"] = f"Add Dive Template"
        context["excursion_type"] = self.excursion_type
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
