"""URL configuration for primitives_testbed project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from django_cms_core.urls import api_urlpatterns as cms_api_urlpatterns
from django_cms_core.urls import page_urlpatterns as cms_page_urlpatterns

from . import views
from .impersonation import ImpersonateStartView, ImpersonateStopView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Health check
    path("health/", views.health_check, name="health_check"),

    # User impersonation (staff only)
    path("impersonate/<int:user_id>/", ImpersonateStartView.as_view(), name="impersonate-start"),
    path("impersonate/stop/", ImpersonateStopView.as_view(), name="impersonate-stop"),

    # Testbed modules
    path("clinic/", include("primitives_testbed.clinic.urls")),
    path("pricing/", include("primitives_testbed.pricing.urls")),
    path("invoicing/", include("primitives_testbed.invoicing.urls")),

    # Authentication
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Staff portal
    path("staff/", RedirectView.as_view(url="/staff/diveops/", permanent=False), name="staff-index"),
    path("staff/diveops/", include("primitives_testbed.diveops.staff_urls")),

    # Customer portal (authenticated customers)
    path("portal/", include("primitives_testbed.diveops.customer_urls", namespace="portal")),

    # Public agreement signing (no login required)
    path("sign/", include("primitives_testbed.diveops.public_urls")),

    # Store (public catalog + logged-in cart/checkout)
    path("shop/", include("primitives_testbed.store.urls", namespace="store")),

    # User profile (all authenticated users)
    path("profile/", include("primitives_testbed.profile.urls", namespace="profile")),

    # CMS API (before catch-all)
    path("api/cms/", include((cms_api_urlpatterns, "cms"), namespace="cms-api")),

    # CMS public pages (MUST BE LAST - catch-all)
    path("", include((cms_page_urlpatterns, "cms"), namespace="cms")),
]

# Serve media/document files in development
if settings.DEBUG:
    urlpatterns += static('/documents/', document_root=settings.BASE_DIR / 'documents')
