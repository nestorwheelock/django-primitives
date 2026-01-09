"""Seed data for recommendations demo.

Creates:
1. PADI certification levels (progression path + specialties)
2. Courseware products with entitlements
3. Gear products for purchase
4. Prices for all items

Usage:
    python manage.py seed_recommendations_demo
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django_catalog.models import CatalogItem
from django_parties.models import Organization

from primitives_testbed.diveops.models import CertificationLevel
from primitives_testbed.pricing.models import Price
from primitives_testbed.store.models import CatalogItemEntitlement

User = get_user_model()


CERTIFICATION_LEVELS = [
    # Core progression path
    {"code": "sd", "name": "Scuba Diver", "rank": 1, "max_depth_m": 12},
    {"code": "ow", "name": "Open Water Diver", "rank": 2, "max_depth_m": 18},
    {"code": "aow", "name": "Advanced Open Water Diver", "rank": 3, "max_depth_m": 30},
    {"code": "rescue", "name": "Rescue Diver", "rank": 4, "max_depth_m": 30},
    {"code": "dm", "name": "Divemaster", "rank": 5, "max_depth_m": 40},
    # Specialties
    {"code": "ppb", "name": "Peak Performance Buoyancy", "rank": 10},
    {"code": "nitrox", "name": "Enriched Air (Nitrox) Diver", "rank": 10},
    {"code": "deep", "name": "Deep Diver", "rank": 10, "max_depth_m": 40},
    {"code": "wreck", "name": "Wreck Diver", "rank": 10},
    {"code": "night", "name": "Night Diver", "rank": 10},
    {"code": "photo", "name": "Underwater Photographer", "rank": 10},
    {"code": "cavern", "name": "Cavern Diver", "rank": 11},
]


COURSEWARE_ITEMS = [
    {
        "name": "Open Water Diver eLearning",
        "price": Decimal("179.00"),
        "entitlement": "content:owd-courseware",
    },
    {
        "name": "Advanced Open Water eLearning",
        "price": Decimal("199.00"),
        "entitlement": "content:aow-courseware",
    },
    {
        "name": "Rescue Diver eLearning",
        "price": Decimal("219.00"),
        "entitlement": "content:rescue-courseware",
    },
    {
        "name": "Enriched Air Nitrox eLearning",
        "price": Decimal("149.00"),
        "entitlement": "content:nitrox-courseware",
    },
    {
        "name": "Peak Performance Buoyancy eLearning",
        "price": Decimal("129.00"),
        "entitlement": "content:ppb-courseware",
    },
    {
        "name": "Deep Diver eLearning",
        "price": Decimal("149.00"),
        "entitlement": "content:deep-courseware",
    },
]


GEAR_ITEMS = [
    # Photography gear
    {
        "name": "Underwater Camera Housing - GoPro",
        "price": Decimal("89.00"),
        "category": "photography",
    },
    {
        "name": "Underwater Camera Housing - iPhone",
        "price": Decimal("149.00"),
        "category": "photography",
    },
    {
        "name": "Dive Light - Primary 1000 Lumens",
        "price": Decimal("129.00"),
        "category": "lighting",
    },
    {
        "name": "Dive Light - Backup 500 Lumens",
        "price": Decimal("59.00"),
        "category": "lighting",
    },
    {
        "name": "Video Light - 2500 Lumens",
        "price": Decimal("249.00"),
        "category": "photography",
    },
    # Basic gear
    {
        "name": "Dive Computer - Beginner",
        "price": Decimal("299.00"),
        "category": "basic",
    },
    {
        "name": "Dive Computer - Advanced",
        "price": Decimal("549.00"),
        "category": "basic",
    },
    {
        "name": "Scuba Mask - Low Volume",
        "price": Decimal("79.00"),
        "category": "basic",
    },
    {
        "name": "Scuba Mask - Frameless",
        "price": Decimal("99.00"),
        "category": "basic",
    },
    {
        "name": "Open Heel Fins - Travel",
        "price": Decimal("149.00"),
        "category": "basic",
    },
    {
        "name": "Full Foot Fins - Warm Water",
        "price": Decimal("89.00"),
        "category": "basic",
    },
    {
        "name": "Dive Snorkel - Folding",
        "price": Decimal("29.00"),
        "category": "basic",
    },
    # Wreck/Tech gear
    {
        "name": "Safety Reel - 150ft",
        "price": Decimal("69.00"),
        "category": "wreck",
    },
    {
        "name": "Finger Spool - 100ft",
        "price": Decimal("39.00"),
        "category": "wreck",
    },
    {
        "name": "Surface Marker Buoy (SMB)",
        "price": Decimal("49.00"),
        "category": "safety",
    },
    {
        "name": "Dive Knife - Titanium",
        "price": Decimal("79.00"),
        "category": "safety",
    },
]


class Command(BaseCommand):
    help = "Seed data for recommendations demo (certifications, courseware, gear)"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding recommendations demo data...\n")

        # Get or create admin user for prices
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.first()
        if not admin_user:
            self.stdout.write(self.style.ERROR("No users found. Create a user first."))
            return

        # 1. Get or create PADI agency
        padi = Organization.objects.filter(name="PADI").first()
        if not padi:
            padi = Organization.objects.create(name="PADI", org_type="agency")
            self.stdout.write(self.style.SUCCESS("  Created PADI agency"))
        else:
            self.stdout.write(f"  Using existing PADI agency ({padi.pk})")

        # 2. Create certification levels
        self.stdout.write("\nCertification Levels:")
        for level_data in CERTIFICATION_LEVELS:
            level, created = CertificationLevel.objects.get_or_create(
                agency=padi,
                code=level_data["code"],
                defaults={
                    "name": level_data["name"],
                    "rank": level_data["rank"],
                    "max_depth_m": level_data.get("max_depth_m"),
                    "is_active": True,
                },
            )
            status = "Created" if created else "Exists"
            self.stdout.write(f"  {status}: {level.name} (rank {level.rank})")

        # 3. Create courseware items
        self.stdout.write("\nCourseware Products:")
        for cw_data in COURSEWARE_ITEMS:
            item, created = CatalogItem.objects.get_or_create(
                display_name=cw_data["name"],
                defaults={
                    "kind": "service",
                    "service_category": "other",
                    "is_billable": True,
                    "active": True,
                },
            )

            # Create entitlement mapping
            CatalogItemEntitlement.objects.get_or_create(
                catalog_item=item,
                defaults={"entitlement_codes": [cw_data["entitlement"]]},
            )

            # Create price
            existing_price = Price.objects.filter(
                catalog_item=item,
                organization__isnull=True,
                party__isnull=True,
                agreement__isnull=True,
            ).first()

            if not existing_price:
                Price.objects.create(
                    catalog_item=item,
                    amount=cw_data["price"],
                    currency="USD",
                    valid_from=timezone.now(),
                    created_by=admin_user,
                    reason="Standard retail price",
                )

            status = "Created" if created else "Exists"
            self.stdout.write(f"  {status}: {cw_data['name']} (${cw_data['price']})")

        # 4. Create gear items
        self.stdout.write("\nGear Products:")
        for gear_data in GEAR_ITEMS:
            item, created = CatalogItem.objects.get_or_create(
                display_name=gear_data["name"],
                defaults={
                    "kind": "stock_item",
                    "is_billable": True,
                    "active": True,
                },
            )

            # Create price
            existing_price = Price.objects.filter(
                catalog_item=item,
                organization__isnull=True,
                party__isnull=True,
                agreement__isnull=True,
            ).first()

            if not existing_price:
                Price.objects.create(
                    catalog_item=item,
                    amount=gear_data["price"],
                    currency="USD",
                    valid_from=timezone.now(),
                    created_by=admin_user,
                    reason="Standard retail price",
                )

            status = "Created" if created else "Exists"
            self.stdout.write(f"  {status}: {gear_data['name']} (${gear_data['price']})")

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))
        self.stdout.write(f"  Certification levels: {CertificationLevel.objects.count()}")
        self.stdout.write(f"  Courseware products: {CatalogItem.objects.filter(kind='service').count()}")
        self.stdout.write(f"  Gear products: {CatalogItem.objects.filter(kind='stock_item').count()}")
        self.stdout.write("\nTo see recommendations, a diver needs:")
        self.stdout.write("  - At least Open Water certification for gear recommendations")
        self.stdout.write("  - Diving interest preferences for specialty gear")
        self.stdout.write("  - Run: python manage.py seed_preferences")
