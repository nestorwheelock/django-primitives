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
    path("preferences/survey/", customer_views.PreferencesSurveyView.as_view(), name="preferences_survey"),
    # Buddies
    path("buddies/add/", customer_views.AddBuddyView.as_view(), name="add_buddy"),
    path("buddies/<uuid:team_id>/remove/", customer_views.RemoveBuddyView.as_view(), name="remove_buddy"),
    # Messages / Conversations
    path("messages/", customer_views.CustomerMessagesInboxView.as_view(), name="messages"),
    path("messages/new/", customer_views.CustomerStartConversationView.as_view(), name="new_conversation"),
    path("messages/<uuid:conversation_id>/", customer_views.CustomerConversationDetailView.as_view(), name="conversation"),
    path("messages/<uuid:conversation_id>/send/", customer_views.CustomerSendMessageView.as_view(), name="send_message"),
    # CMS content pages (within portal context)
    path(
        "content/<path:path>/",
        customer_views.PortalCMSPageView.as_view(),
        name="content",
    ),
]
