"""
Django settings for primitives_testbed project.

This is a verification harness for django-primitives packages.
PostgreSQL is the only supported database.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-testbed-key-change-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = ["*"]  # Allow all hosts in development

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Django Primitives - Foundation
    "django_basemodels",
    "django_singleton",
    "django_modules",
    "django_layers",
    "django_sequence",
    # Django Primitives - Identity
    "django_parties",
    "django_rbac",
    # Django Primitives - Infrastructure
    "django_decisioning",
    "django_audit_log",
    # Django Primitives - Domain
    "django_catalog",
    "django_encounters",
    "django_worklog",
    "django_geo",
    "django_ledger",
    # Django Primitives - Content
    "django_documents",
    "django_notes",
    "django_agreements",
    "django_questionnaires",
    # Django Primitives - Value Objects
    "django_money",
    # UI Framework
    "django_portal_ui",
    # Testbed app
    "primitives_testbed",
    # Testbed modules (built on primitives)
    "primitives_testbed.pricing",
    "primitives_testbed.invoicing",
    "primitives_testbed.checkin",
    "primitives_testbed.diveops",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "primitives_testbed.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django_portal_ui.context_processors.portal_ui",
                "primitives_testbed.diveops.context_processors.diveops_context",
            ],
        },
    },
]

WSGI_APPLICATION = "primitives_testbed.wsgi.application"

# Database - PostgreSQL only
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "primitives_testbed"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "OPTIONS": {
            "connect_timeout": 10,
        },
        "TEST": {
            "NAME": os.getenv("POSTGRES_TEST_DB", "test_primitives_testbed"),
        },
    }
}

# Custom user model with RBAC mixin
AUTH_USER_MODEL = "primitives_testbed.User"

# Django Modules configuration
MODULES_ORG_MODEL = "django_parties.Organization"

# Django Catalog configuration
CATALOG_ENCOUNTER_MODEL = "django_encounters.Encounter"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files (uploaded documents, images, etc.)
# Documents are stored in BASE_DIR/documents/ with upload_to='documents/%Y/%m/%d/'
MEDIA_URL = "/"
MEDIA_ROOT = BASE_DIR

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "primitives_testbed": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Dive Operations configuration
DIVE_SHOP_NAME = "Blue Water Dive Shop"
DIVE_SHOP_TIMEZONE = "America/New_York"  # Business timezone for clock display
DIVE_SHOP_LATITUDE = 25.7617  # Miami, FL - change to your dive shop location
DIVE_SHOP_LONGITUDE = -80.1918

# Portal UI configuration
PORTAL_UI = {
    "SITE_NAME": "Primitives Testbed",
    "STAFF_NAV": [
        {
            "section": "Dive Operations",
            "label": "Excursions",
            "url": "diveops:excursion-list",
            "icon": "anchor",
        },
        {
            "section": "Dive Operations",
            "label": "Divers",
            "url": "diveops:diver-list",
            "icon": "users",
        },
        {
            "section": "Dive Operations",
            "label": "Dive Sites",
            "url": "diveops:staff-site-list",
            "icon": "map-pin",
        },
        {
            "section": "Dive Operations",
            "label": "Protected Areas",
            "url": "diveops:protected-area-list",
            "icon": "shield",
        },
        {
            "section": "Dive Operations",
            "label": "Agreements",
            "url": "diveops:signable-agreement-list",
            "icon": "file-text",
        },
        {
            "section": "Dive Operations",
            "label": "Medical Questionnaires",
            "url": "diveops:medical-list",
            "icon": "heart",
        },
        {
            "section": "Planning",
            "label": "Dive Plans",
            "url": "diveops:dive-plan-list",
            "icon": "compass",
        },
        {
            "section": "Planning",
            "label": "Dive Logs",
            "url": "diveops:dive-log-list",
            "icon": "book-open",
        },
        {
            "section": "System",
            "label": "Documents",
            "url": "diveops:document-browser",
            "icon": "folder",
        },
        {
            "section": "System",
            "label": "Media",
            "url": "diveops:media-library",
            "icon": "image",
        },
        {
            "section": "System",
            "label": "Audit Log",
            "url": "diveops:audit-log",
            "icon": "file-text",
        },
        {
            "section": "Configuration",
            "label": "Excursion Types",
            "url": "diveops:excursion-type-list",
            "icon": "package",
        },
        {
            "section": "Configuration",
            "label": "Agreement Types",
            "url": "diveops:agreement-template-list",
            "icon": "clipboard",
        },
        {
            "section": "Configuration",
            "label": "Catalog Items",
            "url": "diveops:catalog-item-list",
            "icon": "tag",
        },
        {
            "section": "Configuration",
            "label": "AI Settings",
            "url": "diveops:ai-settings",
            "icon": "cpu",
        },
        {
            "section": "Finance",
            "label": "Chart of Accounts",
            "url": "diveops:account-list",
            "icon": "book",
        },
        {
            "section": "Finance",
            "label": "Payables",
            "url": "diveops:payables-summary",
            "icon": "credit-card",
        },
    ],
}

# Medical Questionnaire Configuration
# Configure recommended medical providers for physician clearance
DIVEOPS_MEDICAL_CONFIG = {
    "instructions": {
        "title": "Instructions for Obtaining Physician Clearance",
        "intro": "Your medical questionnaire responses indicate that you require a physician evaluation before participating in scuba diving or freediving activities. Please follow these steps:",
        "steps": [
            "Print this document and take it to one of the recommended medical providers listed below, or to your personal physician.",
            "The physician will review your flagged conditions and conduct an appropriate examination.",
            "The physician must complete and sign the Medical Clearance Form (last page of this document).",
            "Return the signed clearance form to our dive shop before your scheduled activity.",
            "Clearance is valid for one year from the date of physician signature.",
        ],
        "notes": [
            "If you have a pre-existing relationship with a physician familiar with your medical history, you may use them instead of our recommended providers.",
            "For diving-specific medical questions, physicians can consult the Divers Alert Network (DAN) at dan.org or call the DAN Medical Information Line.",
            "Some conditions may require specialist evaluation. Your physician will advise if this is necessary.",
        ],
    },
    "providers": [
        {
            "name": "Cozumel Medical Center",
            "specialty": "General Practice / Diving Medicine",
            "address": "Av. 20 Sur entre Calle 1 Sur y Adolfo Rosado Salas",
            "city": "Cozumel, Quintana Roo",
            "postal_code": "77600",
            "country": "Mexico",
            "phone": "+52 987 872 1430",
            "email": "info@cozumelmedicalcenter.com",
            "hours": "Mon-Fri: 8:00 AM - 6:00 PM, Sat: 9:00 AM - 2:00 PM",
            "languages": ["English", "Spanish"],
            "notes": "Walk-ins welcome. Diving medical clearances typically same-day.",
            "map_url": "https://maps.google.com/?q=20.5068,-86.9462",
            "map_embed": "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3732.123!2d-86.9462!3d20.5068!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2sCozumel+Medical+Center!5e0!3m2!1sen!2smx!4v1234567890",
            "coordinates": {"lat": 20.5068, "lng": -86.9462},
        },
        {
            "name": "Costamed Hospital Cozumel",
            "specialty": "Full Hospital / Emergency Services",
            "address": "Calle 5 Sur #21 entre Av. Rafael Melgar y Av. 5 Sur",
            "city": "Cozumel, Quintana Roo",
            "postal_code": "77600",
            "country": "Mexico",
            "phone": "+52 987 872 9400",
            "emergency_phone": "+52 987 872 9400",
            "email": "cozumel@costamed.com.mx",
            "hours": "24/7 Emergency Services",
            "languages": ["English", "Spanish"],
            "notes": "Full hospital with hyperbaric chamber on-site. Recommended for complex medical histories.",
            "map_url": "https://maps.google.com/?q=20.5089,-86.9494",
            "map_embed": "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3732.123!2d-86.9494!3d20.5089!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2sCostamed+Hospital!5e0!3m2!1sen!2smx!4v1234567890",
            "coordinates": {"lat": 20.5089, "lng": -86.9494},
            "has_hyperbaric": True,
        },
        {
            "name": "Dr. Maria Elena Rodriguez",
            "specialty": "Diving Medicine Specialist",
            "address": "Av. Benito Juarez #315, Centro",
            "city": "Cozumel, Quintana Roo",
            "postal_code": "77600",
            "country": "Mexico",
            "phone": "+52 987 869 1234",
            "hours": "Mon-Fri: 9:00 AM - 5:00 PM, By appointment",
            "languages": ["English", "Spanish", "French"],
            "notes": "DAN-affiliated diving medicine specialist. Appointment recommended.",
            "map_url": "https://maps.google.com/?q=20.5102,-86.9478",
            "coordinates": {"lat": 20.5102, "lng": -86.9478},
            "certifications": ["DAN Diving Medicine", "UHMS Hyperbaric Medicine"],
        },
    ],
    "emergency_contacts": {
        "dan_emergency": "+1-919-684-9111",
        "dan_medical_info": "+1-919-684-2948",
        "local_emergency": "911",
        "coast_guard": "+52 987 872 0409",
    },
    "additional_resources": [
        {
            "name": "Divers Alert Network (DAN)",
            "url": "https://dan.org",
            "description": "Diving safety organization with 24/7 emergency hotline and medical information services.",
        },
        {
            "name": "RSTC Medical Guidelines",
            "url": "https://wrstc.com/medical-guidelines",
            "description": "Official recreational scuba training council medical screening guidelines.",
        },
    ],
}
