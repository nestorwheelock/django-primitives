"""Staff portal URL patterns for diveops."""

from django.urls import path

from . import staff_views

app_name = "diveops"

urlpatterns = [
    # Dashboard
    path("", staff_views.DashboardView.as_view(), name="dashboard"),
    # Diver management
    path("divers/", staff_views.DiverListView.as_view(), name="diver-list"),
    path("divers/add/", staff_views.CreateDiverView.as_view(), name="diver-create"),
    path("divers/<uuid:pk>/", staff_views.DiverDetailView.as_view(), name="diver-detail"),
    path("divers/<uuid:pk>/edit/", staff_views.EditDiverView.as_view(), name="diver-edit"),
    # Certification management
    path("divers/<uuid:diver_pk>/certifications/add/", staff_views.AddCertificationView.as_view(), name="certification-add"),
    path("certifications/<uuid:pk>/edit/", staff_views.EditCertificationView.as_view(), name="certification-edit"),
    path("certifications/<uuid:pk>/delete/", staff_views.DeleteCertificationView.as_view(), name="certification-delete"),
    path("certifications/<uuid:pk>/verify/", staff_views.VerifyCertificationView.as_view(), name="certification-verify"),
    # Excursion management
    path("excursions/", staff_views.ExcursionListView.as_view(), name="excursion-list"),
    path("excursions/<uuid:pk>/", staff_views.ExcursionDetailView.as_view(), name="excursion-detail"),
    path("excursions/<uuid:excursion_pk>/book/", staff_views.BookDiverView.as_view(), name="book-diver"),
    # Actions (POST only)
    path("bookings/<uuid:pk>/check-in/", staff_views.CheckInView.as_view(), name="check-in"),
    path("excursions/<uuid:pk>/start/", staff_views.StartExcursionView.as_view(), name="start-excursion"),
    path("excursions/<uuid:pk>/complete/", staff_views.CompleteExcursionView.as_view(), name="complete-excursion"),
    # Dive Site management
    path("sites/", staff_views.DiveSiteListView.as_view(), name="staff-site-list"),
    path("sites/add/", staff_views.DiveSiteCreateView.as_view(), name="staff-site-create"),
    path("sites/<uuid:pk>/", staff_views.DiveSiteDetailView.as_view(), name="staff-site-detail"),
    path("sites/<uuid:pk>/edit/", staff_views.DiveSiteUpdateView.as_view(), name="staff-site-edit"),
    path("sites/<uuid:pk>/delete/", staff_views.DiveSiteDeleteView.as_view(), name="staff-site-delete"),
    # System
    path("audit-log/", staff_views.AuditLogView.as_view(), name="audit-log"),
    # Dive Logs
    path("dive-logs/", staff_views.DiveLogListView.as_view(), name="dive-log-list"),
    # Dive Plans (templates with route segments)
    path("dive-plans/", staff_views.DivePlanListView.as_view(), name="dive-plan-list"),
    # Excursion Calendar
    path("calendar/", staff_views.ExcursionCalendarView.as_view(), name="calendar"),
    path("excursions/add/", staff_views.ExcursionCreateView.as_view(), name="excursion-create"),
    path("excursions/<uuid:pk>/edit/", staff_views.ExcursionUpdateView.as_view(), name="excursion-edit"),
    path("excursions/<uuid:pk>/cancel/", staff_views.ExcursionCancelView.as_view(), name="excursion-cancel"),
    # Dive management
    path("excursions/<uuid:excursion_pk>/dives/add/", staff_views.DiveCreateView.as_view(), name="dive-add"),
    path("dives/<uuid:pk>/edit/", staff_views.DiveUpdateView.as_view(), name="dive-edit"),
    # Excursion Type management
    path("excursion-types/", staff_views.ExcursionTypeListView.as_view(), name="excursion-type-list"),
    path("excursion-types/add/", staff_views.ExcursionTypeCreateView.as_view(), name="excursion-type-create"),
    path("excursion-types/<uuid:pk>/", staff_views.ExcursionTypeDetailView.as_view(), name="excursion-type-detail"),
    path("excursion-types/<uuid:pk>/edit/", staff_views.ExcursionTypeUpdateView.as_view(), name="excursion-type-edit"),
    path("excursion-types/<uuid:pk>/delete/", staff_views.ExcursionTypeDeleteView.as_view(), name="excursion-type-delete"),
    # Excursion Type Suitable Sites management
    path("excursion-types/<uuid:pk>/sites/add/", staff_views.ExcursionTypeAddSiteView.as_view(), name="excursion-type-add-site"),
    path("excursion-types/<uuid:pk>/sites/<uuid:site_pk>/remove/", staff_views.ExcursionTypeRemoveSiteView.as_view(), name="excursion-type-remove-site"),
    # Excursion Type Dive Templates (nested under excursion types)
    path("excursion-types/<uuid:type_pk>/dives/add/", staff_views.ExcursionTypeDiveCreateView.as_view(), name="excursion-type-dive-create"),
    path("excursion-type-dives/<uuid:pk>/edit/", staff_views.ExcursionTypeDiveUpdateView.as_view(), name="excursion-type-dive-edit"),
    path("excursion-type-dives/<uuid:pk>/delete/", staff_views.ExcursionTypeDiveDeleteView.as_view(), name="excursion-type-dive-delete"),
    # Site Price Adjustment management (nested under sites)
    path("sites/<uuid:site_pk>/adjustments/add/", staff_views.SitePriceAdjustmentCreateView.as_view(), name="site-adjustment-create"),
    path("adjustments/<uuid:pk>/edit/", staff_views.SitePriceAdjustmentUpdateView.as_view(), name="site-adjustment-edit"),
    path("adjustments/<uuid:pk>/delete/", staff_views.SitePriceAdjustmentDeleteView.as_view(), name="site-adjustment-delete"),
    # Catalog Item Management
    path("catalog/", staff_views.CatalogItemListView.as_view(), name="catalog-item-list"),
    path("catalog/add/", staff_views.CatalogItemCreateView.as_view(), name="catalog-item-create"),
    path("catalog/<uuid:pk>/", staff_views.CatalogItemDetailView.as_view(), name="catalog-item-detail"),
    path("catalog/<uuid:pk>/edit/", staff_views.CatalogItemUpdateView.as_view(), name="catalog-item-edit"),
    path("catalog/<uuid:pk>/delete/", staff_views.CatalogItemDeleteView.as_view(), name="catalog-item-delete"),
    # Dive Plan CRUD (full management)
    path("dive-plans/add/", staff_views.DivePlanCreateView.as_view(), name="dive-plan-create"),
    path("dive-plans/<uuid:pk>/", staff_views.DivePlanDetailView.as_view(), name="dive-plan-detail"),
    path("dive-plans/<uuid:pk>/edit/", staff_views.DivePlanUpdateView.as_view(), name="dive-plan-edit"),
    path("dive-plans/<uuid:pk>/delete/", staff_views.DivePlanDeleteView.as_view(), name="dive-plan-delete"),
    # Price management (nested under catalog items)
    path("catalog/<uuid:item_pk>/prices/", staff_views.PriceListView.as_view(), name="price-list"),
    path("catalog/<uuid:item_pk>/prices/add/", staff_views.PriceCreateView.as_view(), name="price-create"),
    path("prices/<uuid:pk>/edit/", staff_views.PriceUpdateView.as_view(), name="price-edit"),
    path("prices/<uuid:pk>/delete/", staff_views.PriceDeleteView.as_view(), name="price-delete"),
    # Agreement management
    path("agreements/", staff_views.AgreementListView.as_view(), name="agreement-list"),
    path("agreements/add/", staff_views.AgreementCreateView.as_view(), name="agreement-create"),
    path("agreements/<uuid:pk>/", staff_views.AgreementDetailView.as_view(), name="agreement-detail"),
    path("agreements/<uuid:pk>/terminate/", staff_views.AgreementTerminateView.as_view(), name="agreement-terminate"),
    path("agreements/<uuid:pk>/sign/", staff_views.AgreementSignView.as_view(), name="agreement-sign"),
    # Payables management
    path("payables/", staff_views.PayablesSummaryView.as_view(), name="payables-summary"),
    path("payables/vendor/<uuid:vendor_pk>/", staff_views.VendorPayablesDetailView.as_view(), name="vendor-payables-detail"),
    path("payables/record-invoice/", staff_views.RecordVendorInvoiceView.as_view(), name="record-vendor-invoice"),
    path("payables/record-payment/", staff_views.RecordVendorPaymentView.as_view(), name="record-vendor-payment"),
    # Account management (Chart of Accounts)
    path("accounts/", staff_views.AccountListView.as_view(), name="account-list"),
    path("accounts/add/", staff_views.AccountCreateView.as_view(), name="account-create"),
    path("accounts/<uuid:pk>/edit/", staff_views.AccountUpdateView.as_view(), name="account-edit"),
    path("accounts/<uuid:pk>/deactivate/", staff_views.AccountDeactivateView.as_view(), name="account-deactivate"),
    path("accounts/<uuid:pk>/reactivate/", staff_views.AccountReactivateView.as_view(), name="account-reactivate"),
    path("accounts/seed/", staff_views.AccountSeedView.as_view(), name="account-seed"),
    # API endpoints
    path("api/compatible-sites/", staff_views.CompatibleSitesAPIView.as_view(), name="api-compatible-sites"),
    path("api/excursion-types/<uuid:pk>/tissue-profile/", staff_views.ExcursionTypeTissueCalculationView.as_view(), name="api-excursion-type-tissue-profile"),
    # Agreement Template management (Paperwork)
    path("paperwork/", staff_views.AgreementTemplateListView.as_view(), name="agreement-template-list"),
    path("paperwork/add/", staff_views.AgreementTemplateCreateView.as_view(), name="agreement-template-create"),
    path("paperwork/<uuid:pk>/", staff_views.AgreementTemplateDetailView.as_view(), name="agreement-template-detail"),
    path("paperwork/<uuid:pk>/edit/", staff_views.AgreementTemplateUpdateView.as_view(), name="agreement-template-edit"),
    path("paperwork/<uuid:pk>/publish/", staff_views.AgreementTemplatePublishView.as_view(), name="agreement-template-publish"),
    path("paperwork/<uuid:pk>/archive/", staff_views.AgreementTemplateArchiveView.as_view(), name="agreement-template-archive"),
    path("paperwork/<uuid:pk>/delete/", staff_views.AgreementTemplateDeleteView.as_view(), name="agreement-template-delete"),
]
