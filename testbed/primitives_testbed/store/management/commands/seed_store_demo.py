"""Seed command for store and CMS demo data.

Creates:
1. CMS settings with entitlement checker hook
2. Public CMS pages (home, courses)
3. Portal CMS page (help - authenticated)
4. Paywalled CMS page (open-water-courseware - requires entitlement)
5. Store catalog item with price and entitlement mapping
6. Demo customer user

Usage:
    python manage.py seed_store_demo
    python manage.py seed_store_demo --force  # Recreate existing data
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from django_catalog.models import CatalogItem
from django_cms_core.models import CMSSettings, ContentPage, AccessLevel, PageStatus
from django_cms_core.services import create_page, add_block, publish_page

from primitives_testbed.pricing.models import Price
from primitives_testbed.store.models import CatalogItemEntitlement

User = get_user_model()


class Command(BaseCommand):
    help = "Seed store and CMS demo data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate existing data",
        )

    def handle(self, *args, **options):
        force = options["force"]

        self.stdout.write("Seeding store and CMS demo data...")

        # 1. Configure CMS settings
        self.setup_cms_settings()

        # 2. Create demo user
        demo_user = self.create_demo_user(force)

        # 3. Create store catalog item
        catalog_item = self.create_store_item(force)

        # 4. Create CMS pages
        self.create_cms_pages(demo_user, force)

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded successfully!"))
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("DEMO WALKTHROUGH")
        self.stdout.write("=" * 60)
        self.stdout.write("""
1. PUBLIC PAGES (no login required):
   - Home page: http://localhost:8000/
   - Courses page: http://localhost:8000/courses/
   - Shop: http://localhost:8000/shop/

2. LOGIN AS DEMO USER:
   - URL: http://localhost:8000/accounts/login/
   - Email: demo@example.com
   - Password: demo1234

3. BROWSE AND PURCHASE:
   - Go to Shop: http://localhost:8000/shop/
   - Add "Open Water Courseware" to cart
   - Checkout and create order
   - Click "Mark as Paid (Demo)" to simulate payment

4. ACCESS PAYWALLED CONTENT:
   - Go to Portal: http://localhost:8000/portal/
   - Your entitlements should now include "content:owd-courseware"
   - Access courseware: http://localhost:8000/portal/content/open-water-courseware/

5. VERIFY ENTITLEMENT-GATED PAGE:
   - Try accessing courseware BEFORE purchase - should get 404
   - After purchase and payment - content is accessible
""")

    def setup_cms_settings(self):
        """Configure CMS settings with entitlement checker hook."""
        self.stdout.write("  Setting up CMS settings...")

        settings = CMSSettings.get_instance()
        settings.site_name = "Blue Water Dive Shop"
        settings.entitlement_checker_path = (
            "primitives_testbed.diveops.entitlements.cms_checker.cms_entitlement_checker"
        )
        settings.default_seo_title_suffix = " | Blue Water Dive Shop"
        settings.save()

        self.stdout.write(self.style.SUCCESS("    CMS settings configured"))

    def create_demo_user(self, force=False):
        """Create demo customer user."""
        self.stdout.write("  Creating demo user...")

        email = "demo@example.com"
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": "demo",
                "is_active": True,
            },
        )

        if created or force:
            user.set_password("demo1234")
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"    Created user: {email}"))
        else:
            self.stdout.write(f"    User exists: {email}")

        return user

    def create_store_item(self, force=False):
        """Create store catalog item with price and entitlement mapping."""
        self.stdout.write("  Creating store catalog item...")

        # Create or get catalog item
        item_name = "Open Water Courseware"
        item, created = CatalogItem.objects.get_or_create(
            display_name=item_name,
            defaults={
                "kind": "service",
                "service_category": "other",
                "is_billable": True,
                "active": True,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"    Created catalog item: {item_name}"))
        else:
            self.stdout.write(f"    Catalog item exists: {item_name}")

        # Create or update price (global scope = all scope FKs are NULL)
        # Need to get or create by user for created_by
        from django.utils import timezone

        existing_price = Price.objects.filter(
            catalog_item=item,
            organization__isnull=True,
            party__isnull=True,
            agreement__isnull=True,
        ).first()

        if existing_price:
            price = existing_price
            price.amount = Decimal("99.00")
            price.save()
            price_created = False
        else:
            price = Price.objects.create(
                catalog_item=item,
                amount=Decimal("99.00"),
                currency="USD",
                valid_from=timezone.now(),
                created_by=User.objects.filter(is_superuser=True).first() or User.objects.first(),
                reason="Store demo price",
            )
            price_created = True

        if price_created:
            self.stdout.write(self.style.SUCCESS(f"    Created price: ${price.amount}"))
        else:
            self.stdout.write(f"    Price exists: ${price.amount}")

        # Create or update entitlement mapping
        entitlement, ent_created = CatalogItemEntitlement.objects.update_or_create(
            catalog_item=item,
            defaults={
                "entitlement_codes": ["content:owd-courseware"],
            },
        )

        if ent_created:
            self.stdout.write(
                self.style.SUCCESS(f"    Created entitlement mapping: {entitlement.entitlement_codes}")
            )
        else:
            self.stdout.write(f"    Entitlement mapping exists: {entitlement.entitlement_codes}")

        return item

    def create_cms_pages(self, user, force=False):
        """Create CMS pages for demo."""
        self.stdout.write("  Creating CMS pages...")

        pages_to_create = [
            {
                "slug": "home",
                "title": "Welcome to Blue Water Dive Shop",
                "access_level": AccessLevel.PUBLIC,
                "blocks": [
                    {
                        "type": "hero",
                        "data": {
                            "title": "Discover the Underwater World",
                            "subtitle": "Professional dive training and unforgettable dive experiences in crystal-clear Caribbean waters.",
                            "cta_text": "Browse Courses",
                            "cta_url": "/shop/",
                        },
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": """
                            <h2>Why Choose Blue Water?</h2>
                            <p>With over 20 years of experience, we offer world-class diving instruction
                            and guided dive experiences. Our certified instructors are passionate about
                            sharing the beauty of the underwater world.</p>
                            <ul>
                                <li>Small class sizes for personalized attention</li>
                                <li>State-of-the-art equipment</li>
                                <li>Access to pristine dive sites</li>
                                <li>Online courseware for flexible learning</li>
                            </ul>
                            """,
                        },
                    },
                    {
                        "type": "cta",
                        "data": {
                            "text": "View All Courses",
                            "url": "/courses/",
                        },
                    },
                ],
            },
            {
                "slug": "courses",
                "title": "Our Courses",
                "access_level": AccessLevel.PUBLIC,
                "blocks": [
                    {
                        "type": "heading",
                        "data": {"level": "1", "text": "Dive Courses & Certifications"},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": """
                            <p>We offer a full range of diving courses from beginner to professional level.</p>

                            <h3>Open Water Diver</h3>
                            <p>Your entry into the world of scuba diving. Learn the fundamentals and earn
                            your certification to dive up to 18 meters/60 feet.</p>
                            <p><strong>Includes online courseware access!</strong></p>

                            <h3>Advanced Open Water</h3>
                            <p>Expand your skills with 5 adventure dives. Increase your depth limit to
                            30 meters/100 feet.</p>

                            <h3>Rescue Diver</h3>
                            <p>Learn to prevent and manage problems in the water. A challenging but
                            rewarding course.</p>
                            """,
                        },
                    },
                    {
                        "type": "cta",
                        "data": {
                            "text": "Browse Our Shop",
                            "url": "/shop/",
                        },
                    },
                ],
            },
            {
                "slug": "help",
                "title": "Help Center",
                "access_level": AccessLevel.AUTHENTICATED,
                "blocks": [
                    {
                        "type": "heading",
                        "data": {"level": "1", "text": "Help Center"},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": """
                            <h2>Frequently Asked Questions</h2>

                            <h3>How do I access my courseware?</h3>
                            <p>After purchasing a course, go to your Dashboard and click on "My Courseware"
                            to access your learning materials.</p>

                            <h3>How long do I have access to courseware?</h3>
                            <p>Once purchased, you have lifetime access to your courseware materials.</p>

                            <h3>Need more help?</h3>
                            <p>Contact us at support@bluewaterdiveshop.com</p>
                            """,
                        },
                    },
                ],
            },
            {
                "slug": "open-water-courseware",
                "title": "Open Water Diver Courseware",
                "access_level": AccessLevel.ENTITLEMENT,
                "required_entitlements": ["content:owd-courseware"],
                "blocks": [
                    {
                        "type": "hero",
                        "data": {
                            "title": "Open Water Diver Course",
                            "subtitle": "Welcome to your diving journey!",
                        },
                    },
                    {
                        "type": "heading",
                        "data": {"level": "2", "text": "Module 1: Introduction to Scuba"},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": """
                            <p><strong>Congratulations on starting your Open Water Diver course!</strong></p>

                            <p>In this module, you'll learn:</p>
                            <ul>
                                <li>The basic principles of scuba diving</li>
                                <li>How pressure affects divers underwater</li>
                                <li>Essential safety rules and buddy system</li>
                                <li>Overview of scuba equipment</li>
                            </ul>

                            <h3>Video: Welcome to Diving</h3>
                            <p>[Video placeholder - actual course would have embedded video]</p>

                            <h3>Reading Material</h3>
                            <p>Download the Module 1 PDF from your student portal to begin studying.
                            Complete the knowledge review questions before your first confined water session.</p>

                            <h3>Next Steps</h3>
                            <p>After completing this module, proceed to Module 2: Dive Equipment.</p>
                            """,
                        },
                    },
                    {
                        "type": "divider",
                        "data": {},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": """
                            <p><em>This is premium content available only to enrolled students.
                            If you're seeing this page, your purchase was successful!</em></p>
                            """,
                        },
                    },
                ],
            },
        ]

        for page_data in pages_to_create:
            slug = page_data["slug"]
            existing = ContentPage.objects.filter(slug=slug, deleted_at__isnull=True).first()

            if existing and not force:
                self.stdout.write(f"    Page exists: /{slug}/")
                continue

            if existing and force:
                existing.delete()  # Soft delete

            # Create page
            page = create_page(
                slug=slug,
                title=page_data["title"],
                user=user,
                access_level=page_data["access_level"],
                required_entitlements=page_data.get("required_entitlements", []),
            )

            # Add blocks
            for block_data in page_data["blocks"]:
                add_block(
                    page=page,
                    block_type=block_data["type"],
                    data=block_data["data"],
                )

            # Publish
            publish_page(page, user)

            self.stdout.write(
                self.style.SUCCESS(f"    Created and published: /{slug}/ ({page_data['access_level']})")
            )
