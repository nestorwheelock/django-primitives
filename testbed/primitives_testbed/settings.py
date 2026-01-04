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

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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

# Portal UI configuration
PORTAL_UI = {
    "SITE_NAME": "Primitives Testbed",
    "STAFF_NAV": [
        {
            "section": "Dive Operations",
            "label": "Trips",
            "url": "diveops:trip-list",
            "icon": "anchor",
        },
        {
            "section": "Dive Operations",
            "label": "Divers",
            "url": "diveops:diver-list",
            "icon": "users",
        },
    ],
}
