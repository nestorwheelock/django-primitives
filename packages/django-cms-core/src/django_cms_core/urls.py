"""URL configuration for django-cms-core.

Provides:
- api_urlpatterns: JSON API endpoints (mount at /api/cms/ or similar)
- page_urlpatterns: Catch-all page view (mount at end of urlpatterns)

Example usage in project urls.py:

    from django.urls import path, include

    urlpatterns = [
        # ... other routes ...

        # CMS API
        path("api/cms/", include("django_cms_core.urls.api_urlpatterns")),

        # CMS public pages (MUST BE LAST - catch-all)
        path("", include("django_cms_core.urls.page_urlpatterns")),
    ]
"""

from django.urls import path, re_path

from .views import CMSPageView, CMSPageAPIView, CMSPageListAPIView


# API patterns - mount at /api/cms/ or similar
api_urlpatterns = [
    path("pages/", CMSPageListAPIView.as_view(), name="page-list"),
    path("pages/<path:path>/", CMSPageAPIView.as_view(), name="page-detail"),
]

# Page patterns - mount as catch-all at end of urlpatterns
page_urlpatterns = [
    # Root page (home)
    path("", CMSPageView.as_view(), name="home"),
    # Path-based pages (supports nested paths like courses/open-water)
    re_path(r"^(?P<path>.+)/$", CMSPageView.as_view(), name="page"),
]

# Combined patterns for simple include
urlpatterns = api_urlpatterns
