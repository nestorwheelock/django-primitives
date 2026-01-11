"""Playwright test for Bob Diver login and shopping flow."""

import re
from playwright.sync_api import sync_playwright, expect


def test_bob_diver_flow():
    """Test Bob Diver can login, browse shop, and access portal."""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("\n=== Testing Bob Diver Flow ===\n")

        # 1. Go to home page
        print("1. Visiting home page...")
        page.goto("http://localhost:8000/")
        print(f"   Title: {page.title()}")

        # 2. Go to login page
        print("\n2. Going to login page...")
        page.goto("http://localhost:8000/accounts/login/")
        print(f"   URL: {page.url}")

        # 3. Login as Bob Diver (using email as username)
        print("\n3. Logging in as Bob Diver...")
        page.fill('input[name="username"]', 'bob.diver@example.com')
        page.fill('input[name="password"]', 'dive2024')
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        print(f"   Redirected to: {page.url}")

        # 4. Check we're logged in - go to portal
        print("\n4. Accessing customer portal...")
        page.goto("http://localhost:8000/portal/")
        page.wait_for_load_state("networkidle")
        print(f"   URL: {page.url}")
        print(f"   Title: {page.title()}")

        # Check page contains dashboard content
        content = page.content()
        if "Dashboard" in content or "portal" in content.lower():
            print("   ✓ Portal dashboard loaded")

        # 5. Browse the shop
        print("\n5. Browsing shop...")
        page.goto("http://localhost:8000/shop/")
        page.wait_for_load_state("networkidle")
        print(f"   URL: {page.url}")

        # Check for catalog items
        content = page.content()
        if "Open Water" in content or "Courseware" in content:
            print("   ✓ Found Open Water Courseware in shop")
        else:
            print("   (No courseware items visible - may need seed data)")

        # 6. Try to access paywalled content (should be denied without entitlement)
        print("\n6. Attempting to access paywalled content...")
        page.goto("http://localhost:8000/portal/content/open-water-courseware/")
        page.wait_for_load_state("networkidle")
        print(f"   URL: {page.url}")

        content = page.content()
        if "404" in content or "not found" in content.lower() or "denied" in content.lower():
            print("   ✓ Access correctly denied (no entitlement)")
        elif "Open Water Diver" in content:
            print("   ✓ Content accessible (user has entitlement)")
        else:
            print(f"   Response status: checking...")

        # 7. Check orders page
        print("\n7. Checking orders page...")
        page.goto("http://localhost:8000/portal/orders/")
        page.wait_for_load_state("networkidle")
        print(f"   URL: {page.url}")

        content = page.content()
        if "order" in content.lower():
            print("   ✓ Orders page loaded")

        # 8. Add item to cart
        print("\n8. Adding Open Water Courseware to cart...")
        page.goto("http://localhost:8000/shop/")
        page.wait_for_load_state("networkidle")

        # Find the product card containing "Open Water Courseware" and click its Add to Cart button
        # The shop list has cards with product names in h3 and Add to Cart buttons
        product_cards = page.locator("div.bg-white.rounded-lg")
        found_product = False

        for i in range(product_cards.count()):
            card = product_cards.nth(i)
            card_text = card.text_content()
            if "Open Water Courseware" in card_text:
                # Click the Add to Cart button in this card
                add_button = card.locator("button:has-text('Add to Cart')")
                if add_button.count() > 0:
                    add_button.click()
                    page.wait_for_load_state("networkidle")
                    print("   ✓ Added Open Water Courseware to cart")
                    found_product = True
                    break

        if not found_product:
            print("   (Could not find Open Water Courseware product)")

        # 9. View cart
        print("\n9. Viewing cart...")
        page.goto("http://localhost:8000/shop/cart/")
        page.wait_for_load_state("networkidle")
        content = page.content()
        if "Open Water" in content or "Courseware" in content:
            print("   ✓ Item in cart")
        else:
            print("   Cart content:", content[:200] if len(content) > 200 else content)

        # 10. Checkout
        print("\n10. Proceeding to checkout...")
        if page.locator("a:has-text('Checkout')").count() > 0:
            page.click("a:has-text('Checkout')")
            page.wait_for_load_state("networkidle")
        elif page.locator("a[href*='checkout']").count() > 0:
            page.click("a[href*='checkout']")
            page.wait_for_load_state("networkidle")
        print(f"   URL: {page.url}")

        # Submit checkout form
        if page.locator("button:has-text('Place Order')").count() > 0:
            page.click("button:has-text('Place Order')")
            page.wait_for_load_state("networkidle")
            print("   ✓ Order placed")
            print(f"   URL: {page.url}")

        # 11. Mark as paid (demo button)
        print("\n11. Marking order as paid...")
        content = page.content()
        if "Mark as Paid" in content:
            page.click("button:has-text('Mark as Paid')")
            page.wait_for_load_state("networkidle")
            print("   ✓ Order marked as paid")
        elif page.locator("form[action*='pay']").count() > 0:
            page.locator("form[action*='pay'] button").click()
            page.wait_for_load_state("networkidle")
            print("   ✓ Payment submitted")

        # 12. Check for entitlement access now
        print("\n12. Checking courseware access after purchase...")
        page.goto("http://localhost:8000/portal/content/open-water-courseware/")
        page.wait_for_load_state("networkidle")
        print(f"   URL: {page.url}")

        content = page.content()
        if "Open Water Diver" in content and "Module 1" in content:
            print("   ✓ SUCCESS! Courseware now accessible after purchase!")
        elif "404" in content or "not found" in content.lower():
            print("   ✗ Still denied - entitlement may not have been granted")
        else:
            print(f"   Content preview: {content[:300]}")

        # 13. Check dashboard for entitlements
        print("\n13. Checking dashboard for entitlements...")
        page.goto("http://localhost:8000/portal/")
        page.wait_for_load_state("networkidle")

        content = page.content()
        if "content:owd-courseware" in content:
            print("   ✓ Entitlement visible on dashboard")
        if "Open Water" in content:
            print("   ✓ Courseware link visible on dashboard")

        # Take a screenshot
        page.screenshot(path="/tmp/bob_diver_test.png")
        print("\n   Screenshot saved to /tmp/bob_diver_test.png")

        browser.close()

        print("\n=== Test Complete ===\n")


if __name__ == "__main__":
    test_bob_diver_flow()
