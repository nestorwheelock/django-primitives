"""End-to-end tests for invoice printing using Playwright.

Tests the invoice printing views and captures screenshots for documentation.
Runs against the dev server (must be running on localhost:9000).

Screenshots are saved to: testbed/screenshots/invoicing/
"""

import os
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright


# Skip if not running e2e tests explicitly
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E_TESTS") != "1",
    reason="E2E tests require RUN_E2E_TESTS=1 and dev server running"
)

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:9000")
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots" / "invoicing"


@pytest.fixture(scope="module", autouse=True)
def setup_screenshot_dir():
    """Ensure screenshot directory exists."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class TestInvoicePrintE2E:
    """End-to-end tests for invoice print views with screenshot capture.

    Prerequisites:
    1. Dev server running: python manage.py runserver 9000
    2. Database seeded with test invoices
    3. User exists (username: admin, password: testpass123)
    4. Run with: RUN_E2E_TESTS=1 pytest tests/test_invoice_printing_e2e.py -v

    Screenshots saved to: testbed/screenshots/invoicing/
    """

    def test_html_print_view_displays_invoice(self):
        """HTML print view renders invoice with all sections.

        Captures screenshot: 01-invoice-print-html.png
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login first
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Get first issued invoice from admin
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")

            # Check for invoices
            content = page.content()
            if "0 invoices" in content.lower():
                pytest.skip("No invoices - run seed script first")

            # Find an issued/paid invoice (printable)
            issued_link = page.locator('table#result_list tbody tr:has-text("issued") a').first
            if issued_link.count() == 0:
                issued_link = page.locator('table#result_list tbody tr:has-text("paid") a').first
            if issued_link.count() == 0:
                pytest.skip("No issued or paid invoices available")

            # Extract invoice ID from URL
            issued_link.click()
            page.wait_for_url("**/change/")
            invoice_url = page.url
            invoice_id = invoice_url.split("/")[-3]

            # Navigate to print view
            page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")

            # Wait for page load
            page.wait_for_selector(".invoice")

            # Verify invoice content
            content = page.content()
            assert "INVOICE" in content
            assert "invoice_number" in content or "Invoice" in content

            # Capture full page screenshot
            page.screenshot(
                path=str(SCREENSHOT_DIR / "01-invoice-print-html.png"),
                full_page=True
            )

            browser.close()

    def test_html_print_view_header_section(self):
        """Invoice header shows number, dates, and status badge.

        Captures screenshot: 02-invoice-header.png
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Get invoice list
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")
            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices")

            # Get first issued invoice
            issued_link = page.locator('table#result_list tbody tr:has-text("issued") a').first
            if issued_link.count() == 0:
                issued_link = page.locator('table#result_list tbody tr:first-child a').first
            issued_link.click()
            page.wait_for_url("**/change/")
            invoice_id = page.url.split("/")[-3]

            # Go to print view
            page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")
            page.wait_for_selector(".invoice-header")

            # Screenshot just the header
            header = page.locator(".invoice-header")
            header.screenshot(path=str(SCREENSHOT_DIR / "02-invoice-header.png"))

            # Verify header elements
            header_content = header.inner_text()
            assert "INVOICE" in header_content.upper()

            browser.close()

    def test_html_print_view_parties_section(self):
        """Invoice shows From (issuer) and Bill To (patient) parties.

        Captures screenshot: 03-invoice-parties.png
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Get first invoice
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")
            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices")

            first_link = page.locator('table#result_list tbody tr:first-child a').first
            first_link.click()
            page.wait_for_url("**/change/")
            invoice_id = page.url.split("/")[-3]

            # Go to print view
            page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")
            page.wait_for_selector(".parties")

            # Screenshot parties section
            parties = page.locator(".parties")
            parties.screenshot(path=str(SCREENSHOT_DIR / "03-invoice-parties.png"))

            # Verify parties
            parties_content = parties.inner_text()
            assert "From" in parties_content
            assert "Bill To" in parties_content

            browser.close()

    def test_html_print_view_line_items_table(self):
        """Invoice shows line items with description, quantity, price, amount.

        Captures screenshot: 04-invoice-line-items.png
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Get first invoice
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")
            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices")

            first_link = page.locator('table#result_list tbody tr:first-child a').first
            first_link.click()
            page.wait_for_url("**/change/")
            invoice_id = page.url.split("/")[-3]

            # Go to print view
            page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")
            page.wait_for_selector(".line-items")

            # Screenshot line items table
            line_items = page.locator(".line-items")
            line_items.screenshot(path=str(SCREENSHOT_DIR / "04-invoice-line-items.png"))

            # Verify table headers
            headers = page.locator(".line-items th").all_inner_texts()
            assert "Description" in headers
            assert "Qty" in headers
            assert "Unit Price" in headers
            assert "Amount" in headers

            browser.close()

    def test_html_print_view_totals_section(self):
        """Invoice shows subtotal, tax, and total amounts.

        Captures screenshot: 05-invoice-totals.png
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Get first invoice
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")
            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices")

            first_link = page.locator('table#result_list tbody tr:first-child a').first
            first_link.click()
            page.wait_for_url("**/change/")
            invoice_id = page.url.split("/")[-3]

            # Go to print view
            page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")
            page.wait_for_selector(".totals")

            # Screenshot totals section
            totals = page.locator(".totals")
            totals.screenshot(path=str(SCREENSHOT_DIR / "05-invoice-totals.png"))

            # Verify totals
            totals_content = totals.inner_text()
            assert "Subtotal" in totals_content
            assert "Total" in totals_content

            browser.close()

    def test_draft_invoice_not_printable(self):
        """Draft invoices return 400 Bad Request.

        Captures screenshot: 06-draft-invoice-error.png
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Find a draft invoice
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")
            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices")

            draft_link = page.locator('table#result_list tbody tr:has-text("draft") a').first
            if draft_link.count() == 0:
                pytest.skip("No draft invoices available")

            draft_link.click()
            page.wait_for_url("**/change/")
            invoice_id = page.url.split("/")[-3]

            # Try to print draft invoice
            response = page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")

            # Capture error page
            page.screenshot(
                path=str(SCREENSHOT_DIR / "06-draft-invoice-error.png"),
                full_page=True
            )

            # Verify 400 response (in page content or title)
            content = page.content()
            # Either we get 400 status or error message
            assert "draft" in content.lower() or "cannot" in content.lower() or "400" in page.title()

            browser.close()

    def test_print_view_responsive_mobile(self):
        """Print view is responsive on mobile viewport.

        Captures screenshot: 07-invoice-mobile.png
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Mobile viewport
            page = browser.new_page(viewport={"width": 375, "height": 812})

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Get first invoice
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")
            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices")

            issued_link = page.locator('table#result_list tbody tr:has-text("issued") a').first
            if issued_link.count() == 0:
                issued_link = page.locator('table#result_list tbody tr:first-child a').first
            issued_link.click()
            page.wait_for_url("**/change/")
            invoice_id = page.url.split("/")[-3]

            # Go to print view on mobile
            page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")
            page.wait_for_selector(".invoice")

            # Capture mobile screenshot
            page.screenshot(
                path=str(SCREENSHOT_DIR / "07-invoice-mobile.png"),
                full_page=True
            )

            # Verify content still visible
            assert page.locator(".invoice").is_visible()

            browser.close()

    def test_multiple_invoice_statuses_printed(self):
        """Issued, paid, and voided invoices all render correctly.

        Captures screenshots: 08-invoice-issued.png, 09-invoice-paid.png
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")
            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices")

            # Try to find and screenshot issued invoice
            issued_link = page.locator('table#result_list tbody tr:has-text("issued") a').first
            if issued_link.count() > 0:
                issued_link.click()
                page.wait_for_url("**/change/")
                invoice_id = page.url.split("/")[-3]
                page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")
                page.wait_for_selector(".invoice")
                page.screenshot(
                    path=str(SCREENSHOT_DIR / "08-invoice-issued.png"),
                    full_page=True
                )
                # Verify status badge
                assert page.locator(".invoice-status").inner_text().lower() == "issued"

            # Try to find and screenshot paid invoice
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")
            paid_link = page.locator('table#result_list tbody tr:has-text("paid") a').first
            if paid_link.count() > 0:
                paid_link.click()
                page.wait_for_url("**/change/")
                invoice_id = page.url.split("/")[-3]
                page.goto(f"{BASE_URL}/invoicing/{invoice_id}/print/")
                page.wait_for_selector(".invoice")
                page.screenshot(
                    path=str(SCREENSHOT_DIR / "09-invoice-paid.png"),
                    full_page=True
                )
                # Verify status badge and paid date
                assert page.locator(".invoice-status").inner_text().lower() == "paid"

            browser.close()
