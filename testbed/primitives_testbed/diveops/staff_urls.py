"""Staff portal URL patterns for diveops."""

from django.urls import path

from . import document_views, staff_views

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
    # Dive Site Photos
    path("sites/<uuid:pk>/photos/", staff_views.DiveSitePhotoManageView.as_view(), name="site-photo-manage"),
    path("sites/<uuid:pk>/photos/upload/", staff_views.DiveSitePhotoUploadView.as_view(), name="site-photo-upload"),
    path("sites/<uuid:pk>/photos/clear-profile/", staff_views.DiveSiteClearProfilePhotoView.as_view(), name="site-clear-profile-photo"),
    path("sites/<uuid:pk>/photos/<uuid:photo_pk>/set-profile/", staff_views.DiveSiteSetProfilePhotoView.as_view(), name="site-photo-set-profile"),
    path("sites/<uuid:pk>/photos/<uuid:photo_pk>/set-featured/", staff_views.DiveSiteSetFeaturedPhotoView.as_view(), name="site-photo-set-featured"),
    path("sites/<uuid:pk>/photos/<uuid:photo_pk>/unfeature/", staff_views.DiveSiteUnfeaturePhotoView.as_view(), name="site-photo-unfeature"),
    path("sites/<uuid:pk>/photos/<uuid:photo_pk>/remove/", staff_views.DiveSiteRemovePhotoView.as_view(), name="site-photo-remove"),
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
    path("excursions/<uuid:pk>/make-recurring/", staff_views.ExcursionMakeRecurringView.as_view(), name="excursion-make-recurring"),
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
    path("excursion-types/<uuid:type_pk>/dives/<uuid:dive_pk>/link/", staff_views.ExcursionTypeLinkDiveView.as_view(), name="excursion-type-dive-link"),
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
    # Segment types API (for dive plan form)
    path("api/segment-types/", staff_views.DiveSegmentTypesAPIView.as_view(), name="segment-types-api"),
    # Price management (nested under catalog items)
    path("catalog/<uuid:item_pk>/prices/", staff_views.PriceListView.as_view(), name="price-list"),
    path("catalog/<uuid:item_pk>/prices/add/", staff_views.PriceCreateView.as_view(), name="price-create"),
    path("prices/<uuid:pk>/edit/", staff_views.PriceUpdateView.as_view(), name="price-edit"),
    path("prices/<uuid:pk>/delete/", staff_views.PriceDeleteView.as_view(), name="price-delete"),
    # Component management (nested under catalog items for assemblies)
    path("catalog/<uuid:item_pk>/components/add/", staff_views.CatalogItemComponentCreateView.as_view(), name="component-create"),
    path("components/<uuid:pk>/edit/", staff_views.CatalogItemComponentUpdateView.as_view(), name="component-edit"),
    path("components/<uuid:pk>/delete/", staff_views.CatalogItemComponentDeleteView.as_view(), name="component-delete"),
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
    # SignableAgreement management (waiver signing workflow)
    path("signable-agreements/", staff_views.SignableAgreementListView.as_view(), name="signable-agreement-list"),
    path("signable-agreements/create/", staff_views.SignableAgreementCreateView.as_view(), name="signable-agreement-create"),
    path("signable-agreements/<uuid:pk>/", staff_views.SignableAgreementDetailView.as_view(), name="signable-agreement-detail"),
    path("signable-agreements/<uuid:pk>/print/", staff_views.SignableAgreementPrintView.as_view(), name="signable-agreement-print"),
    path("signable-agreements/<uuid:pk>/edit/", staff_views.SignableAgreementEditView.as_view(), name="signable-agreement-edit"),
    path("signable-agreements/<uuid:pk>/resend/", staff_views.SignableAgreementResendView.as_view(), name="signable-agreement-resend"),
    path("signable-agreements/<uuid:pk>/void/", staff_views.SignableAgreementVoidView.as_view(), name="signable-agreement-void"),
    path("signable-agreements/<uuid:pk>/revisions/<uuid:revision_pk>/diff/", staff_views.SignableAgreementRevisionDiffView.as_view(), name="signable-agreement-revision-diff"),
    # Agreement Template management (formerly Paperwork)
    path("agreements/templates/", staff_views.AgreementTemplateListView.as_view(), name="agreement-template-list"),
    path("agreements/templates/add/", staff_views.AgreementTemplateCreateView.as_view(), name="agreement-template-create"),
    path("agreements/templates/<uuid:pk>/", staff_views.AgreementTemplateDetailView.as_view(), name="agreement-template-detail"),
    path("agreements/templates/<uuid:pk>/preview/", staff_views.AgreementTemplatePreviewView.as_view(), name="agreement-template-preview"),
    path("agreements/templates/<uuid:pk>/edit/", staff_views.AgreementTemplateUpdateView.as_view(), name="agreement-template-edit"),
    path("agreements/templates/<uuid:pk>/publish/", staff_views.AgreementTemplatePublishView.as_view(), name="agreement-template-publish"),
    path("agreements/templates/<uuid:pk>/archive/", staff_views.AgreementTemplateArchiveView.as_view(), name="agreement-template-archive"),
    path("agreements/templates/<uuid:pk>/send/", staff_views.AgreementTemplateSendView.as_view(), name="agreement-template-send"),
    path("agreements/templates/<uuid:pk>/delete/", staff_views.AgreementTemplateDeleteView.as_view(), name="agreement-template-delete"),
    path("agreements/templates/extract-text/", staff_views.AgreementTemplateExtractTextView.as_view(), name="agreement-template-extract-text"),
    # Protected Area Management
    path("protected-areas/", staff_views.ProtectedAreaListView.as_view(), name="protected-area-list"),
    path("protected-areas/add/", staff_views.ProtectedAreaCreateView.as_view(), name="protected-area-create"),
    path("protected-areas/<uuid:pk>/", staff_views.ProtectedAreaDetailView.as_view(), name="protected-area-detail"),
    path("protected-areas/<uuid:pk>/edit/", staff_views.ProtectedAreaUpdateView.as_view(), name="protected-area-edit"),
    path("protected-areas/<uuid:pk>/delete/", staff_views.ProtectedAreaDeleteView.as_view(), name="protected-area-delete"),
    # Protected Area Zones (area-scoped)
    path("protected-areas/<uuid:area_pk>/zones/add/", staff_views.ProtectedAreaZoneCreateView.as_view(), name="protected-area-zone-create"),
    path("protected-areas/<uuid:area_pk>/zones/<uuid:pk>/", staff_views.ProtectedAreaZoneDetailView.as_view(), name="protected-area-zone-detail"),
    path("protected-areas/<uuid:area_pk>/zones/<uuid:pk>/edit/", staff_views.ProtectedAreaZoneUpdateView.as_view(), name="protected-area-zone-edit"),
    path("protected-areas/<uuid:area_pk>/zones/<uuid:pk>/delete/", staff_views.ProtectedAreaZoneDeleteView.as_view(), name="protected-area-zone-delete"),
    # Zone-scoped rules (create rule for specific zone)
    path("protected-areas/<uuid:area_pk>/zones/<uuid:zone_pk>/rules/add/", staff_views.ZoneRuleCreateView.as_view(), name="zone-rule-create"),
    # Protected Area Rules (area-scoped)
    path("protected-areas/<uuid:area_pk>/rules/add/", staff_views.ProtectedAreaRuleCreateView.as_view(), name="protected-area-rule-create"),
    path("protected-areas/<uuid:area_pk>/rules/<uuid:pk>/edit/", staff_views.ProtectedAreaRuleUpdateView.as_view(), name="protected-area-rule-edit"),
    path("protected-areas/<uuid:area_pk>/rules/<uuid:pk>/delete/", staff_views.ProtectedAreaRuleDeleteView.as_view(), name="protected-area-rule-delete"),
    # Protected Area Fee Schedules (area-scoped)
    path("protected-areas/<uuid:area_pk>/fees/add/", staff_views.ProtectedAreaFeeScheduleCreateView.as_view(), name="protected-area-fee-create"),
    path("protected-areas/<uuid:area_pk>/fees/<uuid:pk>/edit/", staff_views.ProtectedAreaFeeScheduleUpdateView.as_view(), name="protected-area-fee-edit"),
    path("protected-areas/<uuid:area_pk>/fees/<uuid:pk>/delete/", staff_views.ProtectedAreaFeeScheduleDeleteView.as_view(), name="protected-area-fee-delete"),
    # Protected Area Fee Tiers (area + schedule scoped)
    path("protected-areas/<uuid:area_pk>/fees/<uuid:schedule_pk>/tiers/add/", staff_views.ProtectedAreaFeeTierCreateView.as_view(), name="protected-area-tier-create"),
    path("protected-areas/<uuid:area_pk>/fees/<uuid:schedule_pk>/tiers/<uuid:pk>/edit/", staff_views.ProtectedAreaFeeTierUpdateView.as_view(), name="protected-area-tier-edit"),
    path("protected-areas/<uuid:area_pk>/fees/<uuid:schedule_pk>/tiers/<uuid:pk>/delete/", staff_views.ProtectedAreaFeeTierDeleteView.as_view(), name="protected-area-tier-delete"),
    # Unified Permits (area-scoped) - NEW using ProtectedAreaPermit model
    path("protected-areas/<uuid:area_pk>/permits/guide/add/", staff_views.GuidePermitCreateView.as_view(), name="guide-permit-create"),
    path("protected-areas/<uuid:area_pk>/permits/guide/<uuid:pk>/edit/", staff_views.GuidePermitUpdateView.as_view(), name="guide-permit-edit"),
    path("protected-areas/<uuid:area_pk>/permits/vessel/add/", staff_views.VesselPermitCreateViewNew.as_view(), name="vessel-permit-create-new"),
    path("protected-areas/<uuid:area_pk>/permits/vessel/<uuid:pk>/edit/", staff_views.VesselPermitUpdateViewNew.as_view(), name="vessel-permit-edit-new"),
    path("protected-areas/<uuid:area_pk>/permits/photography/add/", staff_views.PhotographyPermitCreateView.as_view(), name="photography-permit-create"),
    path("protected-areas/<uuid:area_pk>/permits/photography/<uuid:pk>/edit/", staff_views.PhotographyPermitUpdateView.as_view(), name="photography-permit-edit"),
    path("protected-areas/<uuid:area_pk>/permits/diving/add/", staff_views.DivingPermitCreateView.as_view(), name="diving-permit-create"),
    path("protected-areas/<uuid:area_pk>/permits/diving/<uuid:pk>/edit/", staff_views.DivingPermitUpdateView.as_view(), name="diving-permit-edit"),
    path("protected-areas/<uuid:area_pk>/permits/<uuid:pk>/delete/", staff_views.PermitDeleteView.as_view(), name="permit-delete"),
    # Document Management
    path("documents/", document_views.DocumentBrowserView.as_view(), name="document-browser"),
    path("documents/folders/<uuid:pk>/", document_views.FolderDetailView.as_view(), name="folder-detail"),
    path("documents/folders/add/", document_views.FolderCreateView.as_view(), name="folder-create"),
    path("documents/folders/<uuid:parent_pk>/add/", document_views.FolderCreateView.as_view(), name="subfolder-create"),
    path("documents/folders/<uuid:pk>/edit/", document_views.FolderUpdateView.as_view(), name="folder-edit"),
    path("documents/folders/<uuid:pk>/delete/", document_views.FolderDeleteView.as_view(), name="folder-delete"),
    path("documents/folders/<uuid:pk>/upload/", document_views.DocumentUploadView.as_view(), name="document-upload"),
    path("documents/<uuid:pk>/", document_views.DocumentDetailView.as_view(), name="document-detail"),
    path("documents/<uuid:pk>/download/", document_views.DocumentDownloadView.as_view(), name="document-download"),
    path("documents/<uuid:pk>/preview/", document_views.DocumentPreviewView.as_view(), name="document-preview"),
    path("documents/<uuid:pk>/move/", document_views.DocumentMoveView.as_view(), name="document-move"),
    path("documents/<uuid:pk>/delete/", document_views.DocumentDeleteView.as_view(), name="document-delete"),
    path("documents/<uuid:pk>/restore/", document_views.DocumentRestoreView.as_view(), name="document-restore"),
    path("documents/<uuid:pk>/permanent-delete/", document_views.DocumentPermanentDeleteView.as_view(), name="document-permanent-delete"),
    path("documents/<uuid:pk>/extract/", document_views.DocumentExtractView.as_view(), name="document-extract"),
    path("documents/trash/empty/", document_views.EmptyTrashView.as_view(), name="empty-trash"),
    path("documents/folders/<uuid:pk>/permissions/", document_views.FolderPermissionListView.as_view(), name="folder-permissions"),
    path("documents/folders/<uuid:pk>/permissions/add/", document_views.FolderPermissionCreateView.as_view(), name="folder-permission-add"),
    path("documents/permissions/<uuid:pk>/delete/", document_views.FolderPermissionDeleteView.as_view(), name="folder-permission-delete"),
    path("documents/access-logs/", document_views.DocumentAccessLogView.as_view(), name="document-access-logs"),
    # Retention Policies
    path("documents/retention-policies/", document_views.RetentionPolicyListView.as_view(), name="retention-policy-list"),
    path("documents/retention-policies/add/", document_views.RetentionPolicyCreateView.as_view(), name="retention-policy-create"),
    path("documents/retention-policies/<uuid:pk>/edit/", document_views.RetentionPolicyUpdateView.as_view(), name="retention-policy-edit"),
    path("documents/retention-policies/<uuid:pk>/delete/", document_views.RetentionPolicyDeleteView.as_view(), name="retention-policy-delete"),
    # Legal Holds
    path("documents/legal-holds/", document_views.LegalHoldListView.as_view(), name="legal-hold-list"),
    path("documents/legal-holds/<uuid:pk>/", document_views.LegalHoldDetailView.as_view(), name="legal-hold-detail"),
    path("documents/legal-holds/<uuid:pk>/release/", document_views.LegalHoldReleaseView.as_view(), name="legal-hold-release"),
    path("documents/<uuid:document_pk>/legal-hold/", document_views.LegalHoldCreateView.as_view(), name="legal-hold-create"),
    # Backup / Export
    path("documents/backup/", document_views.DocumentBackupView.as_view(), name="document-backup"),
    path("documents/backup/download/", document_views.DocumentBackupDownloadView.as_view(), name="document-backup-download"),
    path("documents/backup/s3-sync/", document_views.DocumentS3SyncView.as_view(), name="document-s3-sync"),
    # Notes and Metadata
    path("documents/<uuid:pk>/add-note/", document_views.DocumentAddNoteView.as_view(), name="document-add-note"),
    path("documents/<uuid:pk>/notes/<uuid:note_pk>/delete/", document_views.DocumentDeleteNoteView.as_view(), name="document-delete-note"),
    path("documents/<uuid:pk>/extract-metadata/", document_views.DocumentExtractMetadataView.as_view(), name="document-extract-metadata"),
    path("documents/<uuid:pk>/convert-pdf/", document_views.DocumentConvertToPdfView.as_view(), name="document-convert-pdf"),
    path("documents/<uuid:pk>/preview-pdf/", document_views.DocumentPreviewPdfView.as_view(), name="document-preview-pdf"),
    # Photo Tagging (Divers)
    path("documents/<uuid:pk>/tag-diver/", document_views.PhotoTagAddView.as_view(), name="photo-tag-add"),
    path("documents/<uuid:pk>/untag/<uuid:tag_pk>/", document_views.PhotoTagRemoveView.as_view(), name="photo-tag-remove"),
    # Photo Tagging (Dive Sites)
    path("documents/<uuid:pk>/tag-dive-site/", document_views.DiveSitePhotoTagAddView.as_view(), name="dive-site-tag-add"),
    path("documents/<uuid:pk>/untag-dive-site/<uuid:tag_pk>/", document_views.DiveSitePhotoTagRemoveView.as_view(), name="dive-site-tag-remove"),
    # Configuration
    path("settings/ai/", staff_views.AISettingsView.as_view(), name="ai-settings"),
    # Medical Questionnaires
    path("medical/", staff_views.MedicalQuestionnaireListView.as_view(), name="medical-list"),
    path("medical/send/", staff_views.SendMedicalQuestionnaireCreateView.as_view(), name="medical-send-create"),
    path("medical/<uuid:pk>/", staff_views.MedicalQuestionnaireDetailView.as_view(), name="medical-detail"),
    path("medical/<uuid:pk>/clear/", staff_views.MedicalClearanceUploadView.as_view(), name="medical-clearance"),
    path("medical/<uuid:pk>/void/", staff_views.MedicalQuestionnaireVoidView.as_view(), name="medical-void"),
    path("medical/<uuid:pk>/pdf/", staff_views.MedicalQuestionnairePDFDownloadView.as_view(), name="medical-pdf-download"),
    path("divers/<uuid:pk>/medical/", staff_views.DiverMedicalStatusView.as_view(), name="diver-medical-status"),
    path("divers/<uuid:diver_pk>/medical/send/", staff_views.SendMedicalQuestionnaireView.as_view(), name="send-medical-questionnaire"),
    # Diver Notes (using django-notes primitive)
    path("divers/<uuid:diver_pk>/notes/add/", staff_views.DiverAddNoteView.as_view(), name="diver-add-note"),
    path("divers/<uuid:diver_pk>/notes/<uuid:note_pk>/delete/", staff_views.DiverDeleteNoteView.as_view(), name="diver-delete-note"),
    # Diver Documents (using django-documents primitive)
    path("divers/<uuid:diver_pk>/documents/upload/", staff_views.DiverUploadDocumentView.as_view(), name="diver-upload-document"),
    path("divers/<uuid:diver_pk>/documents/<uuid:doc_pk>/delete/", staff_views.DiverDeleteDocumentView.as_view(), name="diver-delete-document"),
    # Diver Profile Photo
    path("divers/<uuid:diver_pk>/profile-photo/<uuid:photo_pk>/set/", staff_views.DiverSetProfilePhotoView.as_view(), name="diver-set-profile-photo"),
    path("divers/<uuid:diver_pk>/profile-photo/remove/", staff_views.DiverRemoveProfilePhotoView.as_view(), name="diver-remove-profile-photo"),
    # Diver Photo ID
    path("divers/<uuid:diver_pk>/photo-id/upload/", staff_views.DiverUploadPhotoIdView.as_view(), name="diver-upload-photo-id"),
    # Emergency Contacts
    path("divers/<uuid:diver_pk>/emergency-contacts/add/", staff_views.EmergencyContactAddView.as_view(), name="emergency-contact-add"),
    # Diver Inline Gear Update
    path("divers/<uuid:pk>/update-gear/", staff_views.DiverUpdateGearView.as_view(), name="diver-update-gear"),
    # Media Library
    path("media/", staff_views.MediaLibraryView.as_view(), name="media-library"),
    path("media/upload/", staff_views.MediaUploadView.as_view(), name="media-upload"),
    path("media/<uuid:pk>/", staff_views.MediaDetailView.as_view(), name="media-detail"),
    # Media Photo Tagging (Divers)
    path("media/<uuid:pk>/tag/", staff_views.MediaPhotoTagAddView.as_view(), name="media-tag-add"),
    path("media/<uuid:pk>/tag/<uuid:tag_pk>/remove/", staff_views.MediaPhotoTagRemoveView.as_view(), name="media-tag-remove"),
    # Media Photo Tagging (Dive Sites)
    path("media/<uuid:pk>/tag-dive-site/", staff_views.MediaDiveSiteTagAddView.as_view(), name="media-dive-site-tag-add"),
    path("media/<uuid:pk>/tag-dive-site/<uuid:tag_pk>/remove/", staff_views.MediaDiveSiteTagRemoveView.as_view(), name="media-dive-site-tag-remove"),
    # Media Linking (Generic)
    path("media/<uuid:pk>/link-excursion/", staff_views.MediaLinkExcursionView.as_view(), name="media-link-excursion"),
    path("media/<uuid:pk>/unlink-excursion/", staff_views.MediaUnlinkExcursionView.as_view(), name="media-unlink-excursion"),
    path("media/<uuid:pk>/metadata/", staff_views.MediaMetadataUpdateView.as_view(), name="media-metadata"),
    # Excursion Series (Recurring Excursions)
    path("series/", staff_views.ExcursionSeriesListView.as_view(), name="series-list"),
    path("series/add/", staff_views.ExcursionSeriesCreateView.as_view(), name="series-create"),
    path("series/<uuid:pk>/", staff_views.ExcursionSeriesDetailView.as_view(), name="series-detail"),
    path("series/<uuid:pk>/edit/", staff_views.ExcursionSeriesUpdateView.as_view(), name="series-edit"),
    path("series/<uuid:pk>/delete/", staff_views.ExcursionSeriesDeleteView.as_view(), name="series-delete"),
    path("series/<uuid:pk>/sync/", staff_views.ExcursionSeriesSyncView.as_view(), name="series-sync"),
    path("series/<uuid:pk>/pause/", staff_views.ExcursionSeriesPauseView.as_view(), name="series-pause"),
    path("series/<uuid:pk>/activate/", staff_views.ExcursionSeriesActivateView.as_view(), name="series-activate"),
]
