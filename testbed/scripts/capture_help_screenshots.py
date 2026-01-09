#!/usr/bin/env python
"""Capture screenshots of application pages for help documentation.

For each help article, this script navigates to the corresponding
application page and captures a screenshot to illustrate the documentation.

Usage:
    python scripts/capture_help_screenshots.py [--headed] [--base-url URL]

Requirements:
    pip install playwright
    playwright install chromium
"""

import argparse
import os
import sys
from pathlib import Path

# Add the testbed to the path for Django imports
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "primitives_testbed.settings")

import django
django.setup()

from playwright.sync_api import sync_playwright


def get_dynamic_urls():
    """Get URLs that require database lookups for UUIDs."""
    from primitives_testbed.diveops.models import (
        Excursion, SignableAgreement, ProtectedArea, DiveSite, ExcursionSeries,
        AgreementTemplate, ExcursionType, DiverProfile
    )

    urls = {}

    # Diver detail (uses DiverProfile, not Person)
    diver = DiverProfile.objects.filter(deleted_at__isnull=True).first()
    if diver:
        urls["diver_detail"] = f"/staff/diveops/divers/{diver.pk}/"
        urls["diver_edit"] = f"/staff/diveops/divers/{diver.pk}/edit/"

    # Excursion pages
    exc = Excursion.objects.filter(deleted_at__isnull=True).first()
    if exc:
        urls["excursion_detail"] = f"/staff/diveops/excursions/{exc.pk}/"
        urls["excursion_edit"] = f"/staff/diveops/excursions/{exc.pk}/edit/"

    # Signable Agreement pages (note: URL is /signable-agreements/, not /agreements/)
    agr = SignableAgreement.objects.filter(deleted_at__isnull=True).first()
    if agr:
        urls["signable_agreement_detail"] = f"/staff/diveops/signable-agreements/{agr.pk}/"

    # Agreement template (note: URL is /agreements/templates/<pk>/, not /agreement-templates/)
    template = AgreementTemplate.objects.filter(deleted_at__isnull=True).first()
    if template:
        urls["agreement_template_detail"] = f"/staff/diveops/agreements/templates/{template.pk}/"

    # Protected Area detail
    pa = ProtectedArea.objects.filter(deleted_at__isnull=True).first()
    if pa:
        urls["protected_area_detail"] = f"/staff/diveops/protected-areas/{pa.pk}/"

    # Dive Site detail
    site = DiveSite.objects.filter(deleted_at__isnull=True).first()
    if site:
        urls["dive_site_detail"] = f"/staff/diveops/sites/{site.pk}/"

    # Series detail
    series = ExcursionSeries.objects.filter(deleted_at__isnull=True).first()
    if series:
        urls["series_detail"] = f"/staff/diveops/excursion-series/{series.pk}/"

    # Excursion Type detail
    exc_type = ExcursionType.objects.filter(deleted_at__isnull=True).first()
    if exc_type:
        urls["excursion_type_detail"] = f"/staff/diveops/excursion-types/{exc_type.pk}/"

    return urls


# Static URL mappings (pages that don't need database lookups)
STATIC_URLS = {
    # Dashboard
    "dashboard": "/staff/diveops/",

    # Diver pages
    "diver_list": "/staff/diveops/divers/",
    "diver_add": "/staff/diveops/divers/add/",

    # Excursion pages
    "excursion_list": "/staff/diveops/excursions/",
    "excursion_add": "/staff/diveops/excursions/add/",

    # Agreement pages (signable agreements)
    "signable_agreement_list": "/staff/diveops/signable-agreements/",
    "signable_agreement_add": "/staff/diveops/signable-agreements/create/",

    # Medical pages
    "medical_list": "/staff/diveops/medical/",

    # Protected Area pages
    "protected_area_list": "/staff/diveops/protected-areas/",

    # Dive Site pages
    "dive_site_list": "/staff/diveops/sites/",

    # Configuration pages
    "excursion_type_list": "/staff/diveops/excursion-types/",
    "excursion_type_add": "/staff/diveops/excursion-types/add/",
    "agreement_template_list": "/staff/diveops/agreements/templates/",
    "agreement_template_add": "/staff/diveops/agreements/templates/add/",
    "catalog_item_list": "/staff/diveops/catalog/",

    # System pages
    "document_browser": "/staff/diveops/documents/",
    "media_library": "/staff/diveops/media/",
    "audit_log": "/staff/diveops/audit-log/",

    # Planning pages
    "dive_plan_list": "/staff/diveops/dive-plans/",
    "dive_plan_add": "/staff/diveops/dive-plans/add/",
    "dive_log_list": "/staff/diveops/dive-logs/",

    # Finance pages
    "account_list": "/staff/diveops/accounts/",
    "payables_summary": "/staff/diveops/payables/",

    # Settings pages
    "ai_settings": "/staff/diveops/settings/ai/",

    # Help center
    "help_center": "/staff/diveops/help/",
}


def get_staff_session_cookie():
    """Create a Django session for staff user and return session cookie."""
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.backends.db import SessionStore
    from django.conf import settings

    User = get_user_model()

    # Find staff user
    staff_user = User.objects.filter(is_staff=True, is_active=True).first()
    if not staff_user:
        raise Exception("No staff user found. Create a staff user first.")

    print(f"Creating session for: {staff_user.email or staff_user.username}")

    # Create a session
    session = SessionStore()
    session["_auth_user_id"] = str(staff_user.pk)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = staff_user.get_session_auth_hash()
    session.create()

    # Return cookie info
    cookie_name = settings.SESSION_COOKIE_NAME
    return {
        "name": cookie_name,
        "value": session.session_key,
        "domain": "localhost",
        "path": "/",
    }


def capture_screenshots(base_url: str, output_dir: Path, headed: bool = False):
    """Capture screenshots of application pages for help documentation."""

    # Create session cookie for authentication
    session_cookie = get_staff_session_cookie()

    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    lists_dir = output_dir / "lists"
    details_dir = output_dir / "details"
    forms_dir = output_dir / "forms"
    system_dir = output_dir / "system"

    lists_dir.mkdir(exist_ok=True)
    details_dir.mkdir(exist_ok=True)
    forms_dir.mkdir(exist_ok=True)
    system_dir.mkdir(exist_ok=True)

    # Get dynamic URLs
    print("Looking up database records for detail pages...")
    dynamic_urls = get_dynamic_urls()

    # Combine all URLs
    all_urls = {**STATIC_URLS, **dynamic_urls}

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )

        # Add session cookie for authentication
        context.add_cookies([session_cookie])
        print(f"Session cookie added: {session_cookie['name']}={session_cookie['value'][:8]}...")

        page = context.new_page()
        screenshots_taken = 0

        print(f"\nCapturing application screenshots...\n")

        for name, url_path in sorted(all_urls.items()):
            full_url = f"{base_url}{url_path}"

            # Determine output subdirectory
            if "_list" in name or name == "dashboard":
                subdir = lists_dir
            elif "_detail" in name or "_manifest" in name:
                subdir = details_dir
            elif "_create" in name or "_edit" in name:
                subdir = forms_dir
            else:
                subdir = system_dir

            filename = f"{name}.png"
            filepath = subdir / filename

            print(f"  [{name}]")
            print(f"    URL: {url_path}")

            try:
                response = page.goto(full_url)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)  # Wait for animations

                # Check if we got redirected to login (auth failed)
                if "/login" in page.url:
                    print(f"    SKIPPED: Redirected to login")
                    continue

                # Check for 404
                if response and response.status == 404:
                    print(f"    SKIPPED: 404 Not Found")
                    continue

                page.screenshot(path=str(filepath), full_page=True)
                print(f"    Saved: {subdir.name}/{filename}")
                screenshots_taken += 1

            except Exception as e:
                print(f"    ERROR: {e}")

        browser.close()

    print(f"\nDone! {screenshots_taken} screenshots saved to: {output_dir}")
    print(f"  - Lists: {lists_dir}")
    print(f"  - Details: {details_dir}")
    print(f"  - Forms: {forms_dir}")
    print(f"  - System: {system_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Capture application screenshots for help documentation"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the application (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for screenshots (default: media/help/screenshots)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (visible window)",
    )

    args = parser.parse_args()

    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        # Default to media/help/screenshots relative to testbed
        testbed_dir = Path(__file__).parent.parent
        output_dir = testbed_dir / "media" / "help" / "screenshots"

    print(f"Output directory: {output_dir}")
    print(f"Base URL: {args.base_url}")
    print(f"Headed mode: {args.headed}")

    capture_screenshots(
        base_url=args.base_url,
        output_dir=output_dir,
        headed=args.headed,
    )


if __name__ == "__main__":
    main()
