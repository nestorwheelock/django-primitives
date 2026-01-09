"""Staff Help Center views for DiveOps."""

from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from primitives_testbed.mixins import ImpersonationAwareStaffMixin as StaffPortalMixin

from django_cms_core.models import ContentPage, PageStatus


# Help section configuration
HELP_SECTIONS = [
    {
        "slug": "getting-started",
        "title": "Getting Started",
        "description": "Learn the basics of using the staff dashboard",
        "icon": "rocket",
        "articles": [
            {"slug": "dashboard-overview", "title": "Dashboard Overview"},
            {"slug": "navigation-guide", "title": "Navigation Guide"},
            {"slug": "your-account", "title": "Your Account"},
        ],
    },
    {
        "slug": "divers",
        "title": "Divers",
        "description": "Managing diver profiles, certifications, and contacts",
        "icon": "users",
        "articles": [
            {"slug": "creating-profiles", "title": "Creating Diver Profiles"},
            {"slug": "managing-certifications", "title": "Managing Certifications"},
            {"slug": "emergency-contacts", "title": "Emergency Contacts"},
            {"slug": "diver-categories", "title": "Diver Categories"},
        ],
    },
    {
        "slug": "bookings",
        "title": "Bookings & Excursions",
        "description": "Schedule trips, manage bookings, and handle check-ins",
        "icon": "calendar",
        "articles": [
            {"slug": "scheduling-excursions", "title": "Scheduling Excursions"},
            {"slug": "managing-bookings", "title": "Managing Bookings"},
            {"slug": "check-in-process", "title": "Check-in Process"},
            {"slug": "recurring-series", "title": "Recurring Series"},
            {"slug": "cancellations-refunds", "title": "Cancellations & Refunds"},
        ],
    },
    {
        "slug": "agreements",
        "title": "Agreements & Waivers",
        "description": "Create, send, and track liability waivers and agreements",
        "icon": "file-signature",
        "articles": [
            {"slug": "creating-agreements", "title": "Creating Agreements"},
            {"slug": "sending-for-signature", "title": "Sending for Signature"},
            {"slug": "tracking-status", "title": "Tracking Status"},
            {"slug": "voiding-agreements", "title": "Voiding Agreements"},
        ],
    },
    {
        "slug": "medical",
        "title": "Medical Records",
        "description": "Medical questionnaires, clearances, and retention",
        "icon": "heart-pulse",
        "articles": [
            {"slug": "medical-questionnaires", "title": "Medical Questionnaires"},
            {"slug": "reviewing-responses", "title": "Reviewing Responses"},
            {"slug": "clearance-process", "title": "Clearance Process"},
            {"slug": "retention-policies", "title": "Retention Policies"},
        ],
    },
    {
        "slug": "protected-areas",
        "title": "Protected Areas",
        "description": "Manage permits, fees, and zone rules",
        "icon": "shield",
        "articles": [
            {"slug": "managing-permits", "title": "Managing Permits"},
            {"slug": "fee-schedules", "title": "Fee Schedules"},
            {"slug": "zone-rules", "title": "Zone Rules"},
        ],
    },
    {
        "slug": "system",
        "title": "System",
        "description": "Documents, audit logs, and system settings",
        "icon": "settings",
        "articles": [
            {"slug": "document-management", "title": "Document Management"},
            {"slug": "audit-log", "title": "Audit Log"},
            {"slug": "ai-settings", "title": "AI Settings"},
            {"slug": "automated-documentation", "title": "Automated Documentation"},
        ],
    },
]


def get_section_by_slug(slug):
    """Get section configuration by slug."""
    for section in HELP_SECTIONS:
        if section["slug"] == slug:
            return section
    return None


def get_article_in_section(section_slug, article_slug):
    """Get article configuration within a section."""
    section = get_section_by_slug(section_slug)
    if section:
        for article in section["articles"]:
            if article["slug"] == article_slug:
                return article
    return None


class HelpCenterView(StaffPortalMixin, TemplateView):
    """Help center index - lists all help sections."""

    template_name = "diveops/staff/help/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = HELP_SECTIONS
        context["page_title"] = "Help Center"
        return context


class HelpSectionView(StaffPortalMixin, TemplateView):
    """Help section - lists articles in a category."""

    template_name = "diveops/staff/help/section.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section_slug = self.kwargs.get("section")
        section = get_section_by_slug(section_slug)

        if not section:
            context["section"] = None
            context["articles"] = []
        else:
            context["section"] = section
            context["articles"] = section["articles"]

            # Try to get CMS content for each article
            for article in context["articles"]:
                cms_slug = f"help-{section_slug}-{article['slug']}"
                try:
                    page = ContentPage.objects.get(
                        slug=cms_slug,
                        status=PageStatus.PUBLISHED,
                        deleted_at__isnull=True,
                    )
                    article["has_content"] = True
                    article["excerpt"] = self._get_excerpt(page)
                except ContentPage.DoesNotExist:
                    article["has_content"] = False
                    article["excerpt"] = ""

        context["all_sections"] = HELP_SECTIONS
        context["page_title"] = section["title"] if section else "Help"
        return context

    def _get_excerpt(self, page):
        """Extract first 150 chars of content as excerpt."""
        if page.published_snapshot:
            blocks = page.published_snapshot.get("blocks", [])
            for block in blocks:
                if block.get("type") == "rich_text":
                    content = block.get("data", {}).get("content", "")
                    # Strip HTML tags for excerpt
                    import re
                    text = re.sub(r"<[^>]+>", "", content)
                    if len(text) > 150:
                        return text[:150] + "..."
                    return text
        return ""


class HelpArticleView(StaffPortalMixin, TemplateView):
    """Individual help article from CMS."""

    template_name = "diveops/staff/help/article.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section_slug = self.kwargs.get("section")
        article_slug = self.kwargs.get("article")

        section = get_section_by_slug(section_slug)
        article_config = get_article_in_section(section_slug, article_slug)

        context["section"] = section
        context["article_config"] = article_config
        context["all_sections"] = HELP_SECTIONS

        # Try to get CMS content
        cms_slug = f"help-{section_slug}-{article_slug}"
        try:
            page = ContentPage.objects.get(
                slug=cms_slug,
                status=PageStatus.PUBLISHED,
                deleted_at__isnull=True,
            )
            context["page"] = page
            context["snapshot"] = page.published_snapshot or {}
            context["blocks"] = context["snapshot"].get("blocks", [])
            context["has_content"] = True
        except ContentPage.DoesNotExist:
            context["page"] = None
            context["snapshot"] = {}
            context["blocks"] = []
            context["has_content"] = False

        # Navigation: previous and next articles
        if section and article_config:
            articles = section["articles"]
            current_idx = next(
                (i for i, a in enumerate(articles) if a["slug"] == article_slug),
                None,
            )
            if current_idx is not None:
                context["prev_article"] = articles[current_idx - 1] if current_idx > 0 else None
                context["next_article"] = (
                    articles[current_idx + 1] if current_idx < len(articles) - 1 else None
                )

        context["page_title"] = article_config["title"] if article_config else "Help Article"
        return context
