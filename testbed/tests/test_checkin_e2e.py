"""End-to-end tests for patient check-in flow using Playwright.

Tests the complete consent workflow through the clinic API:
1. Schedule a patient (create visit)
2. View consent status
3. Sign each required consent
4. Verify can check in

Runs against the dev server (must be running on localhost:9000).
Screenshots are saved to tests/screenshots/checkin/
"""

import json
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
SCREENSHOT_DIR = Path(__file__).parent / "screenshots" / "checkin"


class TestPatientCheckinE2E:
    """End-to-end tests for patient consent and check-in workflow.

    Prerequisites:
    1. Dev server running: python manage.py runserver 9000
    2. Database seeded: python manage.py seed_clinic
    3. Run with: RUN_E2E_TESTS=1 pytest tests/test_checkin_e2e.py -v
    """

    @pytest.fixture(autouse=True)
    def setup_screenshot_dir(self):
        """Ensure screenshot directory exists."""
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def test_patient_checkin_consent_flow(self):
        """Complete patient check-in workflow with consent signing."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Step 1: Login to admin to ensure we have a session
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")
            page.screenshot(path=str(SCREENSHOT_DIR / "01_admin_logged_in.png"))

            # Step 2: Go to clinic dashboard
            page.goto(f"{BASE_URL}/clinic/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOT_DIR / "02_clinic_dashboard.png"))

            # Step 3: Get list of patients via API
            api_context = context.request
            patients_response = api_context.get(f"{BASE_URL}/clinic/api/patients/")
            patients_data = patients_response.json()
            patients = patients_data.get("patients", [])

            # Screenshot the API response view
            page.goto(f"{BASE_URL}/clinic/api/patients/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOT_DIR / "03_patients_api.png"))

            if not patients:
                pytest.skip("No patients in database - run seed_clinic first")

            patient_id = patients[0]["id"]
            patient_name = patients[0]["name"]
            print(f"Using patient: {patient_name} ({patient_id})")

            # Step 4: Schedule a visit for the patient (create encounter)
            visit_response = api_context.post(
                f"{BASE_URL}/clinic/api/visits/",
                data=json.dumps({"patient_id": patient_id}),
                headers={"Content-Type": "application/json"},
            )
            visit_data = visit_response.json()

            if not visit_data.get("id"):
                # Patient may already have a visit today, get existing visits
                visits_response = api_context.get(f"{BASE_URL}/clinic/api/visits/")
                visits = visits_response.json().get("visits", [])
                if visits:
                    visit_id = visits[0]["id"]
                else:
                    pytest.fail("Could not create or find a visit")
            else:
                visit_id = visit_data["id"]

            print(f"Visit ID: {visit_id}")

            # Step 5: View visit detail page
            page.goto(f"{BASE_URL}/clinic/visits/{visit_id}/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOT_DIR / "04_visit_detail.png"))

            # Step 6: Check consent status via API
            consent_response = api_context.get(f"{BASE_URL}/clinic/api/visits/{visit_id}/consents/")
            consent_data = consent_response.json()
            print(f"Consent status: {json.dumps(consent_data, indent=2)}")

            # Screenshot the consent API
            page.goto(f"{BASE_URL}/clinic/api/visits/{visit_id}/consents/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOT_DIR / "05_consent_status_before.png"))

            required_consents = consent_data.get("required_consents", [])
            unsigned_consents = [c for c in required_consents if not c["signed"]]

            # Step 7: Sign each unsigned consent
            step_num = 6
            for consent in unsigned_consents:
                consent_type = consent["type"]
                consent_name = consent["name"]
                print(f"Signing consent: {consent_name}")

                # Sign the consent via API
                sign_response = api_context.post(
                    f"{BASE_URL}/clinic/api/visits/{visit_id}/consents/sign/",
                    data=json.dumps({"consent_type": consent_type}),
                    headers={"Content-Type": "application/json"},
                )
                sign_data = sign_response.json()
                print(f"  Signed: {sign_data}")

                step_num += 1
                # View updated consent status
                page.goto(f"{BASE_URL}/clinic/api/visits/{visit_id}/consents/")
                page.wait_for_load_state("networkidle")
                page.screenshot(
                    path=str(SCREENSHOT_DIR / f"{step_num:02d}_after_signing_{consent_type}.png")
                )

            # Step 8: Final consent status check
            step_num += 1
            final_consent_response = api_context.get(f"{BASE_URL}/clinic/api/visits/{visit_id}/consents/")
            final_consent_data = final_consent_response.json()
            print(f"Final consent status: {json.dumps(final_consent_data, indent=2)}")

            page.goto(f"{BASE_URL}/clinic/api/visits/{visit_id}/consents/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOT_DIR / f"{step_num:02d}_consent_status_final.png"))

            # Verify all consents are signed
            assert final_consent_data.get("all_signed") is True, \
                f"Not all consents signed: {final_consent_data}"
            assert final_consent_data.get("can_check_in") is True, \
                f"Cannot check in: {final_consent_data}"

            # Step 9: Transition to checked_in state
            step_num += 1
            # First transition to confirmed
            transition_response = api_context.post(
                f"{BASE_URL}/clinic/api/visits/{visit_id}/transition/",
                data=json.dumps({"to_state": "confirmed"}),
                headers={"Content-Type": "application/json"},
            )
            print(f"Transition to confirmed: {transition_response.json()}")

            # Then transition to checked_in
            transition_response = api_context.post(
                f"{BASE_URL}/clinic/api/visits/{visit_id}/transition/",
                data=json.dumps({"to_state": "checked_in"}),
                headers={"Content-Type": "application/json"},
            )
            transition_data = transition_response.json()
            print(f"Transition to checked_in: {transition_data}")

            # View final visit state
            page.goto(f"{BASE_URL}/clinic/visits/{visit_id}/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOT_DIR / f"{step_num:02d}_checked_in_final.png"))

            # Verify checked in
            assert transition_data.get("state") == "checked_in", \
                f"Expected checked_in state, got: {transition_data}"

            browser.close()

            print(f"\nScreenshots saved to: {SCREENSHOT_DIR}")
            print(f"Total screenshots: {step_num}")

    def test_view_clinic_dashboard_with_visits(self):
        """View clinic dashboard showing today's visits."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # View clinic dashboard
            page.goto(f"{BASE_URL}/clinic/")
            page.wait_for_load_state("networkidle")

            # Take screenshot
            page.screenshot(
                path=str(SCREENSHOT_DIR / "dashboard_with_visits.png"),
                full_page=True
            )

            # Check page has loaded correctly
            assert "clinic" in page.url.lower()

            browser.close()

    def test_patient_list_view(self):
        """View patient list page."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Login
            page.goto(f"{BASE_URL}/admin/login/")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "testpass123")
            page.click('input[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/admin/")

            # View patient list
            page.goto(f"{BASE_URL}/clinic/patients/")
            page.wait_for_load_state("networkidle")

            # Take screenshot
            page.screenshot(
                path=str(SCREENSHOT_DIR / "patient_list.png"),
                full_page=True
            )

            browser.close()
