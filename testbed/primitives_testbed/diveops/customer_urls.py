"""URL routes for customer portal (authenticated customers)."""

from django.urls import path

from . import customer_views

app_name = "portal"

urlpatterns = [
    # Dashboard
    path("", customer_views.CustomerDashboardView.as_view(), name="dashboard"),
    # Orders/Invoices
    path("orders/", customer_views.CustomerOrdersView.as_view(), name="orders"),
    # CMS content pages (within portal context)
    path(
        "content/<path:path>/",
        customer_views.PortalCMSPageView.as_view(),
        name="content",
    ),
]
