#!/usr/bin/env python
"""Crawl the staff interface to extract UI elements and generate documentation.

This script navigates to application pages, extracts form fields, buttons,
and other UI elements, and captures cropped screenshots of specific components.

Usage:
    python scripts/crawl_interface.py [--headed] [--base-url URL]

Requirements:
    pip install playwright
    playwright install chromium
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# Add the testbed to the path for Django imports
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "primitives_testbed.settings")

import django
django.setup()

from playwright.sync_api import sync_playwright, Page


@dataclass
class FormField:
    """Represents a form field extracted from the UI."""
    name: str
    label: str
    field_type: str  # text, select, checkbox, textarea, etc.
    required: bool
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options: Optional[list] = None  # For select fields


@dataclass
class UIComponent:
    """Represents a UI component on a page."""
    component_type: str  # button, link, tab, card, table, etc.
    text: str
    selector: str
    href: Optional[str] = None


@dataclass
class PageAnalysis:
    """Complete analysis of a page's UI elements."""
    url: str
    title: str
    breadcrumbs: list
    form_fields: list
    buttons: list
    links: list
    tables: list
    tabs: list
    cards: list
    sections: list


def get_staff_session_cookie():
    """Create a Django session for staff user and return session cookie."""
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.backends.db import SessionStore
    from django.conf import settings

    User = get_user_model()
    staff_user = User.objects.filter(is_staff=True, is_active=True).first()
    if not staff_user:
        raise Exception("No staff user found. Create a staff user first.")

    session = SessionStore()
    session["_auth_user_id"] = str(staff_user.pk)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = staff_user.get_session_auth_hash()
    session.create()

    return {
        "name": settings.SESSION_COOKIE_NAME,
        "value": session.session_key,
        "domain": "localhost",
        "path": "/",
    }


def extract_form_fields(page: Page) -> list[dict]:
    """Extract all form fields from the current page."""
    fields = []

    # Extract input fields
    inputs = page.query_selector_all("input:not([type='hidden']):not([type='submit'])")
    for inp in inputs:
        name = inp.get_attribute("name") or inp.get_attribute("id") or ""
        field_type = inp.get_attribute("type") or "text"
        required = inp.get_attribute("required") is not None
        placeholder = inp.get_attribute("placeholder")

        # Find associated label
        label_text = ""
        inp_id = inp.get_attribute("id")
        if inp_id:
            label = page.query_selector(f"label[for='{inp_id}']")
            if label:
                label_text = label.inner_text().strip()

        # Find help text (common patterns)
        help_text = None
        parent = inp.evaluate("el => el.parentElement")

        fields.append({
            "name": name,
            "label": label_text,
            "field_type": field_type,
            "required": required,
            "placeholder": placeholder,
            "help_text": help_text,
        })

    # Extract select fields
    selects = page.query_selector_all("select")
    for sel in selects:
        name = sel.get_attribute("name") or sel.get_attribute("id") or ""
        required = sel.get_attribute("required") is not None

        # Find label
        label_text = ""
        sel_id = sel.get_attribute("id")
        if sel_id:
            label = page.query_selector(f"label[for='{sel_id}']")
            if label:
                label_text = label.inner_text().strip()

        # Get options
        options = []
        option_elements = sel.query_selector_all("option")
        for opt in option_elements:
            opt_text = opt.inner_text().strip()
            opt_value = opt.get_attribute("value")
            if opt_text and opt_value:
                options.append({"text": opt_text, "value": opt_value})

        fields.append({
            "name": name,
            "label": label_text,
            "field_type": "select",
            "required": required,
            "options": options,
        })

    # Extract textareas
    textareas = page.query_selector_all("textarea")
    for ta in textareas:
        name = ta.get_attribute("name") or ta.get_attribute("id") or ""
        required = ta.get_attribute("required") is not None
        placeholder = ta.get_attribute("placeholder")

        label_text = ""
        ta_id = ta.get_attribute("id")
        if ta_id:
            label = page.query_selector(f"label[for='{ta_id}']")
            if label:
                label_text = label.inner_text().strip()

        fields.append({
            "name": name,
            "label": label_text,
            "field_type": "textarea",
            "required": required,
            "placeholder": placeholder,
        })

    return fields


def extract_buttons(page: Page) -> list[dict]:
    """Extract all buttons from the current page."""
    buttons = []

    # Button elements
    btn_elements = page.query_selector_all("button")
    for btn in btn_elements:
        text = btn.inner_text().strip()
        btn_type = btn.get_attribute("type") or "button"
        classes = btn.get_attribute("class") or ""

        # Determine button style (primary, secondary, danger, etc.)
        style = "default"
        if "bg-blue" in classes or "btn-primary" in classes:
            style = "primary"
        elif "bg-red" in classes or "btn-danger" in classes:
            style = "danger"
        elif "bg-green" in classes or "btn-success" in classes:
            style = "success"

        if text:
            buttons.append({
                "text": text,
                "type": btn_type,
                "style": style,
            })

    # Link-styled buttons (a tags with button classes)
    link_btns = page.query_selector_all("a.btn, a[class*='button'], a[class*='bg-blue'], a[class*='bg-indigo']")
    for lbtn in link_btns:
        text = lbtn.inner_text().strip()
        href = lbtn.get_attribute("href")
        if text:
            buttons.append({
                "text": text,
                "type": "link",
                "href": href,
            })

    return buttons


def extract_navigation_links(page: Page) -> list[dict]:
    """Extract navigation links from sidebar."""
    links = []

    # Sidebar navigation links
    nav_links = page.query_selector_all("nav a, aside a, [class*='sidebar'] a")
    for link in nav_links:
        text = link.inner_text().strip()
        href = link.get_attribute("href")
        if text and href and not href.startswith("#"):
            links.append({
                "text": text,
                "href": href,
            })

    return links


def extract_table_info(page: Page) -> list[dict]:
    """Extract table structure from the page."""
    tables = []

    table_elements = page.query_selector_all("table")
    for table in table_elements:
        headers = []
        header_cells = table.query_selector_all("thead th, thead td")
        for th in header_cells:
            headers.append(th.inner_text().strip())

        # Count rows
        row_count = len(table.query_selector_all("tbody tr"))

        tables.append({
            "headers": headers,
            "row_count": row_count,
        })

    return tables


def extract_tabs(page: Page) -> list[dict]:
    """Extract tab navigation from the page."""
    tabs = []

    # Common tab patterns
    tab_elements = page.query_selector_all("[role='tab'], .tab, [class*='tab-']")
    for tab in tab_elements:
        text = tab.inner_text().strip()
        is_active = "active" in (tab.get_attribute("class") or "")
        if text:
            tabs.append({
                "text": text,
                "is_active": is_active,
            })

    return tabs


def extract_cards_and_sections(page: Page) -> tuple[list, list]:
    """Extract card components and page sections."""
    cards = []
    sections = []

    # Cards (common Tailwind patterns)
    card_elements = page.query_selector_all("[class*='card'], [class*='bg-white'][class*='shadow'], [class*='rounded-lg'][class*='border']")
    for card in card_elements[:10]:  # Limit to first 10
        # Try to get card title
        title_el = card.query_selector("h2, h3, h4, [class*='title'], [class*='heading']")
        title = title_el.inner_text().strip() if title_el else ""
        if title:
            cards.append({"title": title})

    # Page sections (h2, h3 headings)
    headings = page.query_selector_all("main h2, main h3, [class*='content'] h2, [class*='content'] h3")
    for heading in headings:
        text = heading.inner_text().strip()
        level = heading.evaluate("el => el.tagName")
        if text:
            sections.append({
                "text": text,
                "level": level,
            })

    return cards, sections


def extract_page_title(page: Page) -> str:
    """Extract the main page title."""
    # Try common patterns
    selectors = [
        "main h1",
        "[class*='content'] h1",
        "[class*='page-title']",
        "h1",
    ]

    for selector in selectors:
        el = page.query_selector(selector)
        if el:
            return el.inner_text().strip()

    return page.title()


def extract_breadcrumbs(page: Page) -> list[str]:
    """Extract breadcrumb navigation."""
    breadcrumbs = []

    # Common breadcrumb patterns
    bc_elements = page.query_selector_all("nav[aria-label='breadcrumb'] a, [class*='breadcrumb'] a, [class*='breadcrumb'] span")
    for bc in bc_elements:
        text = bc.inner_text().strip()
        if text and text not in ["›", "/", ">"]:
            breadcrumbs.append(text)

    return breadcrumbs


def capture_component_screenshot(page: Page, selector: str, output_path: Path) -> bool:
    """Capture a cropped screenshot of a specific component."""
    try:
        element = page.query_selector(selector)
        if element:
            element.screenshot(path=str(output_path))
            return True
    except Exception as e:
        print(f"    Could not capture {selector}: {e}")
    return False


def analyze_page(page: Page, url: str) -> dict:
    """Perform complete analysis of a page."""
    return {
        "url": url,
        "title": extract_page_title(page),
        "breadcrumbs": extract_breadcrumbs(page),
        "form_fields": extract_form_fields(page),
        "buttons": extract_buttons(page),
        "navigation_links": extract_navigation_links(page),
        "tables": extract_table_info(page),
        "tabs": extract_tabs(page),
        "cards": extract_cards_and_sections(page)[0],
        "sections": extract_cards_and_sections(page)[1],
    }


# Component selectors for cropped screenshots
COMPONENT_SELECTORS = {
    # Dashboard components
    "dashboard_stats": "dashboard > [class*='grid'], main > [class*='grid']:first-of-type",
    "dashboard_excursions": "[class*='excursion'], [class*='today']",

    # Form components
    "form_container": "form",
    "form_buttons": "form [class*='button'], form button[type='submit']",

    # List/table components
    "data_table": "table",
    "table_header": "thead",
    "pagination": "[class*='pagination'], nav[aria-label*='pagination']",

    # Detail page components
    "detail_header": "main > [class*='flex']:first-of-type, [class*='page-header']",
    "detail_tabs": "[role='tablist'], [class*='tab-list']",
    "detail_content": "[class*='card'], [class*='panel']",

    # Sidebar
    "sidebar": "aside, [class*='sidebar'], nav[class*='fixed']",
}


# Pages to crawl with component screenshot targets
PAGES_TO_CRAWL = {
    "dashboard": {
        "url": "/staff/diveops/",
        "components": ["dashboard_stats", "sidebar"],
    },
    "diver_list": {
        "url": "/staff/diveops/divers/",
        "components": ["data_table", "pagination"],
    },
    "diver_add": {
        "url": "/staff/diveops/divers/add/",
        "components": ["form_container", "form_buttons"],
    },
    "excursion_list": {
        "url": "/staff/diveops/excursions/",
        "components": ["data_table"],
    },
    "excursion_add": {
        "url": "/staff/diveops/excursions/add/",
        "components": ["form_container"],
    },
    "agreement_list": {
        "url": "/staff/diveops/signable-agreements/",
        "components": ["data_table"],
    },
    "agreement_create": {
        "url": "/staff/diveops/signable-agreements/create/",
        "components": ["form_container"],
    },
    "protected_area_list": {
        "url": "/staff/diveops/protected-areas/",
        "components": ["data_table"],
    },
    "dive_site_list": {
        "url": "/staff/diveops/sites/",
        "components": ["data_table"],
    },
    "medical_list": {
        "url": "/staff/diveops/medical/",
        "components": ["data_table"],
    },
    "excursion_type_list": {
        "url": "/staff/diveops/excursion-types/",
        "components": ["data_table"],
    },
    "agreement_template_list": {
        "url": "/staff/diveops/agreements/templates/",
        "components": ["data_table"],
    },
    "audit_log": {
        "url": "/staff/diveops/audit-log/",
        "components": ["data_table"],
    },
    "document_browser": {
        "url": "/staff/diveops/documents/",
        "components": ["data_table"],
    },
}


def crawl_interface(base_url: str, output_dir: Path, headed: bool = False):
    """Crawl the interface and extract UI elements."""

    session_cookie = get_staff_session_cookie()

    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    components_dir = output_dir / "components"
    components_dir.mkdir(exist_ok=True)

    all_analyses = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        context.add_cookies([session_cookie])

        page = context.new_page()

        print(f"\nCrawling interface pages...\n")

        for page_name, page_config in PAGES_TO_CRAWL.items():
            url_path = page_config["url"]
            full_url = f"{base_url}{url_path}"

            print(f"  [{page_name}]")
            print(f"    URL: {url_path}")

            try:
                response = page.goto(full_url)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)

                if "/login" in page.url:
                    print(f"    SKIPPED: Redirected to login")
                    continue

                if response and response.status == 404:
                    print(f"    SKIPPED: 404 Not Found")
                    continue

                # Analyze the page
                analysis = analyze_page(page, url_path)
                all_analyses[page_name] = analysis

                print(f"    Title: {analysis['title']}")
                print(f"    Form fields: {len(analysis['form_fields'])}")
                print(f"    Buttons: {len(analysis['buttons'])}")
                print(f"    Tables: {len(analysis['tables'])}")

                # Capture component screenshots
                components = page_config.get("components", [])
                for comp_name in components:
                    selector = COMPONENT_SELECTORS.get(comp_name)
                    if selector:
                        comp_path = components_dir / f"{page_name}_{comp_name}.png"
                        # Try multiple selectors (comma-separated)
                        for sel in selector.split(", "):
                            if capture_component_screenshot(page, sel.strip(), comp_path):
                                print(f"    Component: {comp_name} -> {comp_path.name}")
                                break

            except Exception as e:
                print(f"    ERROR: {e}")

        browser.close()

    # Save analysis to JSON
    analysis_path = output_dir / "interface_analysis.json"
    with open(analysis_path, "w") as f:
        json.dump(all_analyses, f, indent=2)

    print(f"\n\nAnalysis saved to: {analysis_path}")
    print(f"Component screenshots saved to: {components_dir}")

    return all_analyses


def generate_documentation_from_analysis(analyses: dict) -> dict:
    """Generate documentation content based on UI analysis."""
    docs = {}

    for page_name, analysis in analyses.items():
        doc = {
            "title": analysis["title"],
            "description": "",
            "form_fields": [],
            "actions": [],
            "tables": [],
        }

        # Document form fields
        for field in analysis.get("form_fields", []):
            if field.get("label"):
                field_doc = {
                    "label": field["label"],
                    "type": field["field_type"],
                    "required": field.get("required", False),
                }
                if field.get("placeholder"):
                    field_doc["placeholder"] = field["placeholder"]
                if field.get("options"):
                    field_doc["options"] = [opt["text"] for opt in field["options"]]
                doc["form_fields"].append(field_doc)

        # Document buttons/actions
        for btn in analysis.get("buttons", []):
            if btn.get("text"):
                doc["actions"].append({
                    "text": btn["text"],
                    "type": btn.get("type", "button"),
                })

        # Document tables
        for table in analysis.get("tables", []):
            if table.get("headers"):
                doc["tables"].append({
                    "columns": table["headers"],
                    "rows": table.get("row_count", 0),
                })

        docs[page_name] = doc

    return docs


def main():
    parser = argparse.ArgumentParser(
        description="Crawl staff interface to extract UI elements"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the application (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for analysis and screenshots",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (visible window)",
    )

    args = parser.parse_args()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        testbed_dir = Path(__file__).parent.parent
        output_dir = testbed_dir / "docs" / "interface_analysis"

    print(f"Output directory: {output_dir}")
    print(f"Base URL: {args.base_url}")
    print(f"Headed mode: {args.headed}")

    analyses = crawl_interface(
        base_url=args.base_url,
        output_dir=output_dir,
        headed=args.headed,
    )

    # Generate documentation from analysis
    docs = generate_documentation_from_analysis(analyses)
    docs_path = output_dir / "generated_docs.json"
    with open(docs_path, "w") as f:
        json.dump(docs, f, indent=2)
    print(f"Generated documentation saved to: {docs_path}")


if __name__ == "__main__":
    main()
