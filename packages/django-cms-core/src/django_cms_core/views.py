"""Views for django-cms-core.

Provides:
- CMSPageView: Template-based page rendering
- CMSPageAPIView: JSON API for single page
- CMSPageListAPIView: JSON API for page listing
"""

from django.http import Http404, JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .models import ContentPage, PageStatus
from .services import check_page_access


class CMSPageView(TemplateView):
    """Render CMS pages based on URL path.

    Looks up ContentPage by slug, checks access control,
    and renders using the configured template.
    """

    template_name = "cms/page.html"

    def get(self, request, path=""):
        path = path.strip("/") or "home"

        try:
            page = ContentPage.objects.get(
                slug=path,
                status=PageStatus.PUBLISHED,
                deleted_at__isnull=True,
            )
        except ContentPage.DoesNotExist:
            raise Http404("Page not found")

        allowed, reason = check_page_access(page, request.user)

        if not allowed:
            if "authentication" in reason.lower():
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            raise Http404("Page not found")

        self.page = page
        return super().get(request, path=path)

    def get_template_names(self):
        if hasattr(self, "page") and self.page.template_key:
            return [
                f"cms/{self.page.template_key}.html",
                self.template_name,
            ]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = self.page.published_snapshot or {}
        context["page"] = self.page
        context["snapshot"] = snapshot
        context["meta"] = snapshot.get("meta", {})
        context["blocks"] = snapshot.get("blocks", [])
        return context


class CMSPageAPIView(View):
    """JSON API for CMS page data."""

    def get(self, request, path=""):
        path = path.strip("/") or "home"

        try:
            page = ContentPage.objects.get(
                slug=path,
                status=PageStatus.PUBLISHED,
                deleted_at__isnull=True,
            )
        except ContentPage.DoesNotExist:
            return JsonResponse(
                {"ok": False, "error": {"code": "PAGE_NOT_FOUND", "message": "Page not found"}},
                status=404,
            )

        allowed, reason = check_page_access(page, request.user)

        if not allowed:
            if "authentication" in reason.lower():
                return JsonResponse(
                    {"ok": False, "error": {"code": "AUTH_REQUIRED", "message": reason}},
                    status=401,
                )
            return JsonResponse(
                {"ok": False, "error": {"code": "ACCESS_DENIED", "message": reason}},
                status=403,
            )

        return JsonResponse({
            "ok": True,
            "data": {
                "page": page.published_snapshot,
            },
        })


class CMSPageListAPIView(View):
    """JSON API for listing published pages."""

    def get(self, request):
        pages = ContentPage.objects.filter(
            status=PageStatus.PUBLISHED,
            deleted_at__isnull=True,
            is_indexable=True,
        ).order_by("sort_order", "title")

        accessible_pages = []
        for page in pages:
            allowed, _ = check_page_access(page, request.user)
            if allowed:
                accessible_pages.append({
                    "slug": page.slug,
                    "title": page.title,
                    "path": f"/{page.slug}/" if page.slug != "home" else "/",
                })

        return JsonResponse({
            "ok": True,
            "data": {"pages": accessible_pages},
        })
