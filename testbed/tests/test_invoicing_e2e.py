"""End-to-end tests for invoicing using Playwright.

Tests the complete basket-to-invoice flow through the Django admin interface.
Runs against the dev server (must be running on localhost:9000).
"""

import os
import pytest
from playwright.sync_api import sync_playwright


# Skip if not running e2e tests explicitly
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E_TESTS") != "1",
    reason="E2E tests require RUN_E2E_TESTS=1 and dev server running"
)

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:9000")


class TestInvoicingAdminE2E:
    """End-to-end tests for invoicing admin interface.

    Prerequisites:
    1. Dev server running: python manage.py runserver 9000
    2. Database seeded with test data
    3. Admin user exists (username: admin, password: testpass123)
    4. Run with: RUN_E2E_TESTS=1 pytest tests/test_invoicing_e2e.py -v
    """

    def test_admin_login_and_view_invoices(self):
        """Admin user can login and access the invoice list."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login to admin
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')

            # Wait for redirect to admin home
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Navigate to invoice list
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")

            # Verify we're on the invoice page
            assert "invoice" in page.url.lower()
            h1_text = page.locator("h1").inner_text()
            assert "invoice" in h1_text.lower()

            browser.close()

    def test_admin_can_view_invoice_detail(self):
        """Admin can view invoice details including line items."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login to admin
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Navigate to invoice list
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")

            # Check if any invoices exist
            content = page.content()
            if "0 invoices" in content.lower():
                pytest.skip("No invoices in database - run seed_invoicing first")

            # Click on first invoice
            first_invoice_link = page.locator("table#result_list tbody tr:first-child a").first
            if first_invoice_link.count() == 0:
                pytest.skip("No invoices in database")

            first_invoice_link.click()

            # Verify invoice detail page
            page.wait_for_selector("h1")
            content = page.content()

            # Check for expected fields
            assert "Invoice number" in content or "invoice_number" in content
            assert "Status" in content or "status" in content
            assert "Total" in content or "total" in content

            browser.close()

    def test_invoice_line_items_visible(self):
        """Invoice detail shows line items inline."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Go to invoice list
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")

            # Check if invoices exist
            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices - run seed script first")

            # Click first invoice
            first_link = page.locator("table#result_list tbody tr:first-child a").first
            if first_link.count() == 0:
                pytest.skip("No invoices available")

            first_link.click()

            # Wait for form to load
            page.wait_for_selector("form#invoice_form")
            content = page.content()

            # Should have line items inline section
            assert "Invoice line items" in content or "line_items" in content or "inline-group" in content

            browser.close()

    def test_ledger_section_visible(self):
        """Admin shows ledger transaction link for issued invoices."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # Go to invoice list
            page.goto(f"{BASE_URL}/admin/invoicing/invoice/")

            if "0 invoices" in page.content().lower():
                pytest.skip("No invoices - run seed script first")

            # Click first invoice
            first_link = page.locator("table#result_list tbody tr:first-child a").first
            if first_link.count() == 0:
                pytest.skip("No invoices available")

            first_link.click()

            # Wait for form to load
            page.wait_for_selector("form#invoice_form")
            content = page.content()

            # Should show ledger transaction field
            assert "Ledger transaction" in content or "ledger_transaction" in content

            browser.close()
