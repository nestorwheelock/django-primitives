"""DiveOps models package.

Re-exports all models for backward compatibility.
Import from diveops.models as before:
    from diveops.models import DiverProfile, Booking

This package structure splits the models into logical modules:
- base.py: Constants and base utilities
- certifications.py: CertificationLevel
- diver.py: DiverProfile, DiverCertification, DiverEligibilityProof
- relationships.py: EmergencyContact, DiverRelationship, DiverRelationshipMeta
- sites.py: DiveSite, DiveSitePhoto, SitePriceAdjustment
- excursions.py: Excursion, Trip, Dive, ExcursionType, etc.
- bookings.py: Booking, EligibilityOverride
- roster.py: ExcursionRoster, DiveAssignment, DiveLog
- permits.py: ProtectedArea*, GuidePermitDetails
- agreements.py: AgreementTemplate, SignableAgreement*, DocumentRetention*
- media.py: PhotoTag, DiveSitePhotoTag, MediaLink*
- misc.py: Settlement*, AISettings, Medical*, Contact, Buddy*, DiveTeam*
"""

# Base constants
from .base import DIVEOPS_WAIVER_VALIDITY_DAYS

# Certifications
from .certifications import CertificationLevel

# Diver models
from .diver import (
    DiverCertification,
    DiverEligibilityProof,
    DiverProfile,
)

# Relationships
from .relationships import (
    DiverRelationship,
    DiverRelationshipMeta,
    EmergencyContact,
)

# Sites
from .sites import (
    DiveSite,
    DiveSitePhoto,
    SitePriceAdjustment,
)

# Excursions
from .excursions import (
    Dive,
    DiveSegmentType,
    Excursion,
    ExcursionRequirement,
    ExcursionSeries,
    ExcursionType,
    ExcursionTypeDive,
    RecurrenceException,
    RecurrenceRule,
    Trip,
)

# Bookings
from .bookings import (
    Booking,
    EligibilityOverride,
)

# Roster
from .roster import (
    DiveAssignment,
    DiveLog,
    ExcursionRoster,
)

# Permits
from .permits import (
    GuidePermitDetails,
    ProtectedArea,
    ProtectedAreaFeeSchedule,
    ProtectedAreaFeeTier,
    ProtectedAreaPermit,
    ProtectedAreaRule,
    ProtectedAreaZone,
)

# Agreements
from .agreements import (
    AgreementTemplate,
    DocumentLegalHold,
    DocumentRetentionPolicy,
    SignableAgreement,
    SignableAgreementRevision,
)

# Media
from .media import (
    DiveSitePhotoTag,
    DiveSitePhotoTagQuerySet,
    MediaLink,
    MediaLinkQuerySet,
    MediaLinkSource,
    PhotoTag,
    PhotoTagQuerySet,
)

# Misc (AI, Email, Medical, Teams, Settlement)
from .misc import (
    AISettings,
    BuddyIdentity,
    CommissionRule,
    Contact,
    DiveBuddy,
    DiveTeam,
    DiveTeamMember,
    EmailSettings,
    EmailTemplate,
    MedicalProviderLocation,
    MedicalProviderProfile,
    MedicalProviderRelationship,
    SettlementRecord,
    SettlementRun,
)

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
    # Bookings
    "Booking",
    "EligibilityOverride",
    # Roster
    "ExcursionRoster",
    "DiveAssignment",
    "DiveLog",
    # Agreements
    "AgreementTemplate",
    "SignableAgreement",
    "SignableAgreementRevision",
    # Documents
    "DocumentRetentionPolicy",
    "DocumentLegalHold",
    # Protected Areas
    "ProtectedArea",
    "ProtectedAreaZone",
    "ProtectedAreaRule",
    "ProtectedAreaFeeSchedule",
    "ProtectedAreaFeeTier",
    "ProtectedAreaPermit",
    "GuidePermitDetails",
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
    "EmailSettings",
    "EmailTemplate",
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
]
