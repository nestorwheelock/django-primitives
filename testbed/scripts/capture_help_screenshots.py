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


# Map help articles to their corresponding application URLs
# Format: (section_slug, article_slug) -> (url_path, description)
ARTICLE_TO_APP_URL = {
    # Getting Started
    ("getting-started", "dashboard-overview"): {
        "url": "/staff/diveops/",
        "description": "Staff dashboard overview",
    },
    ("getting-started", "navigation-guide"): {
        "url": "/staff/diveops/",
        "description": "Navigation sidebar",
    },

    # Divers
    ("divers", "creating-profiles"): {
        "url": "/staff/diveops/divers/",
        "description": "Diver list page",
    },
    ("divers", "managing-certifications"): {
        "url": "/staff/diveops/divers/",
        "description": "Diver certifications",
    },
    ("divers", "emergency-contacts"): {
        "url": "/staff/diveops/divers/",
        "description": "Diver emergency contacts",
    },
    ("divers", "diver-categories"): {
        "url": "/staff/diveops/divers/",
        "description": "Diver categories",
    },

    # Bookings & Excursions
    ("bookings", "scheduling-excursions"): {
        "url": "/staff/diveops/excursions/",
        "description": "Excursion list",
    },
    ("bookings", "managing-bookings"): {
        "url": "/staff/diveops/excursions/",
        "description": "Managing bookings",
    },
    ("bookings", "check-in-process"): {
        "url": "/staff/diveops/excursions/",
        "description": "Check-in process",
    },
    ("bookings", "recurring-series"): {
        "url": "/staff/diveops/excursion-series/",
        "description": "Recurring excursion series",
    },
    ("bookings", "cancellations-refunds"): {
        "url": "/staff/diveops/excursions/",
        "description": "Cancellations and refunds",
    },

    # Agreements & Waivers
    ("agreements", "creating-agreements"): {
        "url": "/staff/diveops/agreements/",
        "description": "Agreements list",
    },
    ("agreements", "sending-for-signature"): {
        "url": "/staff/diveops/agreements/",
        "description": "Sending agreements",
    },
    ("agreements", "tracking-status"): {
        "url": "/staff/diveops/agreements/",
        "description": "Agreement status tracking",
    },
    ("agreements", "voiding-agreements"): {
        "url": "/staff/diveops/agreements/",
        "description": "Voiding agreements",
    },

    # Medical Records
    ("medical", "medical-questionnaires"): {
        "url": "/staff/diveops/medical/",
        "description": "Medical questionnaires list",
    },
    ("medical", "reviewing-responses"): {
        "url": "/staff/diveops/medical/",
        "description": "Reviewing medical responses",
    },
    ("medical", "clearance-process"): {
        "url": "/staff/diveops/medical/",
        "description": "Medical clearance process",
    },
    ("medical", "retention-policies"): {
        "url": "/staff/diveops/medical/",
        "description": "Medical retention policies",
    },

    # Protected Areas
    ("protected-areas", "managing-permits"): {
        "url": "/staff/diveops/protected-areas/",
        "description": "Protected areas list",
    },
    ("protected-areas", "fee-schedules"): {
        "url": "/staff/diveops/protected-areas/",
        "description": "Fee schedules",
    },
    ("protected-areas", "zone-rules"): {
        "url": "/staff/diveops/protected-areas/",
        "description": "Zone rules",
    },

    # System
    ("system", "document-management"): {
        "url": "/staff/diveops/documents/",
        "description": "Document browser",
    },
    ("system", "audit-log"): {
        "url": "/staff/diveops/audit-log/",
        "description": "Audit log",
    },
    ("system", "ai-settings"): {
        "url": "/staff/diveops/ai-settings/",
        "description": "AI settings",
    },
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

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

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

        # Track unique URLs to avoid duplicate screenshots
        captured_urls = {}
        screenshots_taken = 0

        print(f"\nCapturing application screenshots for help documentation...\n")

        for (section_slug, article_slug), config in ARTICLE_TO_APP_URL.items():
            url_path = config["url"]
            description = config["description"]
            full_url = f"{base_url}{url_path}"

            # Generate filename
            filename = f"{section_slug}-{article_slug}.png"
            filepath = output_dir / filename

            # Check if we already captured this URL
            if url_path in captured_urls:
                # Create a symlink or copy reference
                print(f"  [{section_slug}/{article_slug}] -> (same as {captured_urls[url_path]})")
                continue

            print(f"  [{section_slug}/{article_slug}] {description}")
            print(f"    URL: {url_path}")

            try:
                page.goto(full_url)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)  # Wait for animations

                page.screenshot(path=str(filepath), full_page=True)
                print(f"    Saved: {filename}")

                captured_urls[url_path] = f"{section_slug}/{article_slug}"
                screenshots_taken += 1

            except Exception as e:
                print(f"    ERROR: {e}")

        browser.close()

    print(f"\nDone! {screenshots_taken} screenshots saved to: {output_dir}")


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
