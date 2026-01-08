"""Customer portal views (authenticated customers)."""

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from django_cms_core.models import AccessLevel, ContentPage, PageStatus
from django_cms_core.services import check_page_access
from django_portal_ui.mixins import CustomerPortalMixin

from primitives_testbed.store.models import StoreOrder

from .selectors import (
    get_current_diver,
    get_diver_highest_certification,
    get_diver_with_certifications,
    list_diver_bookings,
)


class CustomerDashboardView(CustomerPortalMixin, TemplateView):
    """Customer portal dashboard showing bookings, orders, and courseware."""

    template_name = "diveops/portal/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get diver profile for current user
        diver = get_current_diver(user)
        diver_with_certs = None
        highest_cert = None
        upcoming_bookings = []
        past_bookings = []

        if diver:
            # Get full diver with certifications
            diver_with_certs = get_diver_with_certifications(diver.pk)
            highest_cert = get_diver_highest_certification(diver)
            # Get upcoming bookings (future excursions)
            upcoming_bookings = list_diver_bookings(diver, include_past=False, limit=5)
            # Get recent past bookings
            past_bookings = list_diver_bookings(diver, include_past=True, limit=5)
            # Filter to only past ones
            from django.utils import timezone
            past_bookings = [
                b for b in past_bookings
                if b.excursion.departure_time <= timezone.now()
            ][:3]

        # Get recent orders for this user
        orders = StoreOrder.objects.filter(user=user).order_by("-created_at")[:5]

        # Get user's entitlements
        from primitives_testbed.diveops.entitlements.services import get_user_entitlements

        entitlements = get_user_entitlements(user)

        # Find courseware pages user has access to
        courseware_pages = []
        if entitlements:
            pages = ContentPage.objects.filter(
                status=PageStatus.PUBLISHED,
                access_level=AccessLevel.ENTITLEMENT,
                deleted_at__isnull=True,
            )
            for page in pages:
                allowed, _ = check_page_access(page, user)
                if allowed:
                    courseware_pages.append(page)

        context.update({
            "diver": diver_with_certs or diver,
            "highest_cert": highest_cert,
            "upcoming_bookings": upcoming_bookings,
            "past_bookings": past_bookings,
            "orders": orders,
            "entitlements": entitlements,
            "courseware_pages": courseware_pages,
        })
        return context


class CustomerOrdersView(CustomerPortalMixin, TemplateView):
    """Customer view of their orders."""

    template_name = "diveops/portal/orders.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get all orders for this user
        orders = StoreOrder.objects.filter(user=user).order_by("-created_at")

        context["orders"] = orders
        return context


class PortalCMSPageView(CustomerPortalMixin, TemplateView):
    """Render CMS pages within the portal context.

    This view wraps CMS pages inside the portal layout,
    enforcing at minimum AUTHENTICATED access.
    """

    template_name = "diveops/portal/content_page.html"

    def get(self, request, path, *args, **kwargs):
        # Normalize path (remove leading/trailing slashes)
        slug = path.strip("/") or "home"

        # Get the page
        try:
            page = ContentPage.objects.get(
                slug=slug,
                status=PageStatus.PUBLISHED,
                deleted_at__isnull=True,
            )
        except ContentPage.DoesNotExist:
            raise Http404("Page not found")

        # Check access (portal forces minimum AUTHENTICATED)
        allowed, reason = check_page_access(page, request.user)
        if not allowed:
            raise Http404(reason)

        # Store page for context
        self.page = page
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.page
        snapshot = page.published_snapshot or {}

        context.update({
            "page": page,
            "page_title": page.title,
            "blocks": snapshot.get("blocks", []),
            "meta": snapshot.get("meta", {}),
        })
        return context
