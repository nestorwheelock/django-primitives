"""URL configuration for primitives_testbed project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.index, name="index"),
    path("health/", views.health_check, name="health_check"),
    path("clinic/", include("primitives_testbed.clinic.urls")),
    path("pricing/", include("primitives_testbed.pricing.urls")),
    path("invoicing/", include("primitives_testbed.invoicing.urls")),
    # Authentication
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Staff portal - redirect /staff/ to /staff/diveops/
    path("staff/", RedirectView.as_view(url="/staff/diveops/", permanent=False), name="staff-index"),
    path("staff/diveops/", include("primitives_testbed.diveops.staff_urls")),
    # Public agreement signing (no login required)
    path("sign/", include("primitives_testbed.diveops.public_urls")),
]

# Serve media/document files in development
if settings.DEBUG:
    # Documents are stored at BASE_DIR/documents/ with upload_to='documents/%Y/%m/%d/'
    # URLs are /documents/2026/01/04/file.png
    urlpatterns += static('/documents/', document_root=settings.BASE_DIR / 'documents')
