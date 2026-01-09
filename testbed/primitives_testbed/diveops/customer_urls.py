"""URL routes for customer portal (authenticated customers)."""

from django.urls import path

from . import customer_views

app_name = "portal"

urlpatterns = [
    # Dashboard
    path("", customer_views.CustomerDashboardView.as_view(), name="dashboard"),
    # Profile updates
    path("update-gear-sizing/", customer_views.UpdateGearSizingView.as_view(), name="update_gear_sizing"),
    path("add-emergency-contact/", customer_views.AddEmergencyContactView.as_view(), name="add_emergency_contact"),
    # Forms (questionnaires, agreements)
    path("start-form/<uuid:template_id>/", customer_views.StartFormView.as_view(), name="start_form"),
    # Orders/Invoices
    path("orders/", customer_views.CustomerOrdersView.as_view(), name="orders"),
    path("orders/<str:order_number>/", customer_views.CustomerOrderDetailView.as_view(), name="order_detail"),
    # Preferences
    path("preferences/", customer_views.CustomerPreferencesView.as_view(), name="preferences"),
    # CMS content pages (within portal context)
    path(
        "content/<path:path>/",
        customer_views.PortalCMSPageView.as_view(),
        name="content",
    ),
]
