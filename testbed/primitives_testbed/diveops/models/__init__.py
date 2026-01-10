"""DiveOps models package.

Re-exports all models for backward compatibility.
Import from diveops.models as before:
    from diveops.models import DiverProfile, Booking

This package structure allows the monolithic models.py to be split
into logical modules while maintaining import compatibility.
"""

# Import all models from the original models.py file
# During migration, models will be moved to individual files
# and imports will be updated to use those files instead

# For now, import from the _models_all module which contains the original code
from ._models_all import (
    # Constants
    DIVEOPS_WAIVER_VALIDITY_DAYS,
    # Certifications
    CertificationLevel,
    DiverCertification,
    # Diver
    DiverProfile,
    DiverEligibilityProof,
    # Relationships
    EmergencyContact,
    DiverRelationship,
    DiverRelationshipMeta,
    # Sites
    DiveSite,
    DiveSitePhoto,
    SitePriceAdjustment,
    # Excursions
    Trip,
    Excursion,
    ExcursionRequirement,
    ExcursionType,
    ExcursionTypeDive,
    RecurrenceRule,
    RecurrenceException,
    ExcursionSeries,
    Dive,
    DiveSegmentType,
    DiveAssignment,
    # Bookings
    Booking,
    EligibilityOverride,
    # Roster
    ExcursionRoster,
    # Agreements
    AgreementTemplate,
    SignableAgreement,
    SignableAgreementRevision,
    # Protected Areas
    ProtectedArea,
    ProtectedAreaZone,
    ProtectedAreaRule,
    ProtectedAreaFeeSchedule,
    ProtectedAreaFeeTier,
    ProtectedAreaPermit,
    GuidePermitDetails,
    # Documents
    DocumentRetentionPolicy,
    DocumentLegalHold,
    # Photos
    PhotoTagQuerySet,
    PhotoTag,
    DiveSitePhotoTagQuerySet,
    DiveSitePhotoTag,
    # Media
    MediaLinkSource,
    MediaLinkQuerySet,
    MediaLink,
    # Settings
    AISettings,
    # Medical
    MedicalProviderProfile,
    MedicalProviderLocation,
    MedicalProviderRelationship,
    # Contacts
    Contact,
    # Buddies/Teams
    BuddyIdentity,
    DiveTeam,
    DiveTeamMember,
    DiveBuddy,
    # Settlements
    SettlementRecord,
    CommissionRule,
    SettlementRun,
    # Logs
    DiveLog,
)

# Backwards compatibility aliases
DiveTrip = Excursion
TripRequirement = ExcursionRequirement

__all__ = [
    # Constants
    "DIVEOPS_WAIVER_VALIDITY_DAYS",
    # Certifications
    "CertificationLevel",
    "DiverCertification",
    # Diver
    "DiverProfile",
    "DiverEligibilityProof",
    # Relationships
    "EmergencyContact",
    "DiverRelationship",
    "DiverRelationshipMeta",
    # Sites
    "DiveSite",
    "DiveSitePhoto",
    "SitePriceAdjustment",
    # Excursions
    "Trip",
    "Excursion",
    "ExcursionRequirement",
    "ExcursionType",
    "ExcursionTypeDive",
    "RecurrenceRule",
    "RecurrenceException",
    "ExcursionSeries",
    "Dive",
    "DiveSegmentType",
    "DiveAssignment",
    # Bookings
    "Booking",
    "EligibilityOverride",
    # Roster
    "ExcursionRoster",
    # Agreements
    "AgreementTemplate",
    "SignableAgreement",
    "SignableAgreementRevision",
    # Protected Areas
    "ProtectedArea",
    "ProtectedAreaZone",
    "ProtectedAreaRule",
    "ProtectedAreaFeeSchedule",
    "ProtectedAreaFeeTier",
    "ProtectedAreaPermit",
    "GuidePermitDetails",
    # Documents
    "DocumentRetentionPolicy",
    "DocumentLegalHold",
    # Photos
    "PhotoTagQuerySet",
    "PhotoTag",
    "DiveSitePhotoTagQuerySet",
    "DiveSitePhotoTag",
    # Media
    "MediaLinkSource",
    "MediaLinkQuerySet",
    "MediaLink",
    # Settings
    "AISettings",
    # Medical
    "MedicalProviderProfile",
    "MedicalProviderLocation",
    "MedicalProviderRelationship",
    # Contacts
    "Contact",
    # Buddies/Teams
    "BuddyIdentity",
    "DiveTeam",
    "DiveTeamMember",
    "DiveBuddy",
    # Settlements
    "SettlementRecord",
    "CommissionRule",
    "SettlementRun",
    # Logs
    "DiveLog",
    # Backwards compatibility
    "DiveTrip",
    "TripRequirement",
]
