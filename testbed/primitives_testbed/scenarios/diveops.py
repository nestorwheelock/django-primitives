"""DiveOps scenario: ExcursionType, SitePriceAdjustment seed data."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_geo.models import Place
from django_parties.models import Organization

from primitives_testbed.diveops.models import (
    CertificationLevel,
    DiveSite,
    ExcursionType,
    ExcursionTypeDive,
    SitePriceAdjustment,
)

User = get_user_model()


def seed():
    """Create sample excursion types and price adjustments."""
    count = 0

    # First, ensure we have a certification agency
    padi, created = Organization.objects.get_or_create(
        name="PADI",
        org_type="certification_agency",
    )
    if created:
        count += 1

    # Ensure we have certification levels with agency
    open_water, created = CertificationLevel.objects.get_or_create(
        agency=padi,
        code="ow",
        defaults={
            "name": "Open Water Diver",
            "rank": 1,
        }
    )
    if created:
        count += 1

    advanced_ow, created = CertificationLevel.objects.get_or_create(
        agency=padi,
        code="aow",
        defaults={
            "name": "Advanced Open Water",
            "rank": 2,
        }
    )
    if created:
        count += 1

    rescue, created = CertificationLevel.objects.get_or_create(
        agency=padi,
        code="rescue",
        defaults={
            "name": "Rescue Diver",
            "rank": 3,
        }
    )
    if created:
        count += 1

    divemaster, created = CertificationLevel.objects.get_or_create(
        agency=padi,
        code="dm",
        defaults={
            "name": "Divemaster",
            "rank": 4,
        }
    )
    if created:
        count += 1

    # Create standard excursion types
    morning_boat, created = ExcursionType.objects.get_or_create(
        slug="morning-2-tank-boat",
        defaults={
            "name": "Morning 2-Tank Boat Dive",
            "description": "Standard morning boat dive with two tank dives at local sites.",
            "dive_mode": "boat",
            "time_of_day": "day",
            "max_depth_meters": 18,
            "typical_duration_minutes": 240,
            "dives_per_excursion": 2,
            "base_price": Decimal("120.00"),
            "currency": "USD",
            "requires_cert": True,
            "min_certification_level": open_water,
            "is_training": False,
            "is_active": True,
        }
    )
    if created:
        count += 1

    afternoon_boat, created = ExcursionType.objects.get_or_create(
        slug="afternoon-2-tank-boat",
        defaults={
            "name": "Afternoon 2-Tank Boat Dive",
            "description": "Afternoon boat dive with two tank dives. Great for late sleepers!",
            "dive_mode": "boat",
            "time_of_day": "day",
            "max_depth_meters": 18,
            "typical_duration_minutes": 240,
            "dives_per_excursion": 2,
            "base_price": Decimal("120.00"),
            "currency": "USD",
            "requires_cert": True,
            "min_certification_level": open_water,
            "is_training": False,
            "is_active": True,
        }
    )
    if created:
        count += 1

    night_dive, created = ExcursionType.objects.get_or_create(
        slug="night-dive-boat",
        defaults={
            "name": "Night Boat Dive",
            "description": "Experience the reef come alive after dark. Includes dive light rental.",
            "dive_mode": "boat",
            "time_of_day": "night",
            "max_depth_meters": 18,
            "typical_duration_minutes": 180,
            "dives_per_excursion": 1,
            "base_price": Decimal("95.00"),
            "currency": "USD",
            "requires_cert": True,
            "min_certification_level": advanced_ow,
            "is_training": False,
            "is_active": True,
        }
    )
    if created:
        count += 1

    deep_dive, created = ExcursionType.objects.get_or_create(
        slug="deep-dive-boat",
        defaults={
            "name": "Deep Dive Adventure",
            "description": "Explore deeper reef sites and wrecks. Nitrox recommended.",
            "dive_mode": "boat",
            "time_of_day": "day",
            "max_depth_meters": 40,
            "typical_duration_minutes": 240,
            "dives_per_excursion": 2,
            "base_price": Decimal("150.00"),
            "currency": "USD",
            "requires_cert": True,
            "min_certification_level": advanced_ow,
            "is_training": False,
            "is_active": True,
        }
    )
    if created:
        count += 1

    shore_dive, created = ExcursionType.objects.get_or_create(
        slug="guided-shore-dive",
        defaults={
            "name": "Guided Shore Dive",
            "description": "Explore the house reef with a guide. Perfect for relaxed diving.",
            "dive_mode": "shore",
            "time_of_day": "day",
            "max_depth_meters": 18,
            "typical_duration_minutes": 90,
            "dives_per_excursion": 1,
            "base_price": Decimal("45.00"),
            "currency": "USD",
            "requires_cert": True,
            "min_certification_level": open_water,
            "is_training": False,
            "is_active": True,
        }
    )
    if created:
        count += 1

    dsd_dive, created = ExcursionType.objects.get_or_create(
        slug="discover-scuba",
        defaults={
            "name": "Discover Scuba Diving (DSD)",
            "description": "Try scuba diving! No certification required. Pool training + one ocean dive.",
            "dive_mode": "shore",
            "time_of_day": "day",
            "max_depth_meters": 12,
            "typical_duration_minutes": 180,
            "dives_per_excursion": 1,
            "base_price": Decimal("150.00"),
            "currency": "USD",
            "requires_cert": False,
            "min_certification_level": None,
            "is_training": True,
            "is_active": True,
        }
    )
    if created:
        count += 1

    dawn_dive, created = ExcursionType.objects.get_or_create(
        slug="dawn-dive-boat",
        defaults={
            "name": "Dawn Boat Dive",
            "description": "Early morning dive to catch the reef waking up. Coffee included!",
            "dive_mode": "boat",
            "time_of_day": "dawn",
            "max_depth_meters": 18,
            "typical_duration_minutes": 180,
            "dives_per_excursion": 1,
            "base_price": Decimal("85.00"),
            "currency": "USD",
            "requires_cert": True,
            "min_certification_level": open_water,
            "is_training": False,
            "is_active": True,
        }
    )
    if created:
        count += 1

    # =========================================================================
    # Juan Escutia Wreck Dive - Puerto Morelos
    # =========================================================================

    # Create the marine park location
    puerto_morelos_park, created = Place.objects.get_or_create(
        name="Parque Nacional Arrecife de Puerto Morelos",
        defaults={
            "latitude": Decimal("20.8500"),
            "longitude": Decimal("-86.8750"),
        }
    )
    if created:
        count += 1

    # Create the Juan Escutia wreck dive site
    juan_escutia, created = DiveSite.objects.get_or_create(
        name="Juan Escutia",
        defaults={
            "place": puerto_morelos_park,
            "max_depth_meters": 27,  # 90 feet
            "difficulty": "advanced",
            "description": (
                "The Juan Escutia is a purposely sunk naval vessel in the "
                "Parque Nacional Arrecife de Puerto Morelos. The wreck sits upright "
                "with the main deck at 85 feet, offering multi-level exploration "
                "opportunities up to the bow at 45 feet. Excellent for photography "
                "and advanced divers seeking a structured wreck dive experience."
            ),
            "min_certification_level": advanced_ow,
            "dive_mode": "boat",
        }
    )
    if created:
        count += 1

    # Create Nitrox/Enriched Air specialty certification
    nitrox_cert, created = CertificationLevel.objects.get_or_create(
        agency=padi,
        code="eanx",
        defaults={
            "name": "Enriched Air Nitrox",
            "rank": 2,  # Same rank as AOW - it's a specialty, not progression
        }
    )
    if created:
        count += 1

    # Create wreck dive excursion type
    wreck_dive, created = ExcursionType.objects.get_or_create(
        slug="juan-escutia-wreck",
        defaults={
            "name": "Juan Escutia Wreck Dive",
            "description": (
                "Explore the Juan Escutia shipwreck in Puerto Morelos Marine Park. "
                "Multi-level wreck dive with structured descent profile. "
                "Nitrox (EAN32) provided. Requires Advanced Open Water AND Nitrox certifications."
            ),
            "dive_mode": "boat",
            "time_of_day": "day",
            "max_depth_meters": 27,  # 90 feet
            "typical_duration_minutes": 180,
            "dives_per_excursion": 1,
            "base_price": Decimal("175.00"),
            "currency": "USD",
            "requires_cert": True,
            "min_certification_level": advanced_ow,
            "is_training": False,
            "is_active": True,
        }
    )
    if created:
        count += 1

    # Create the dive template with full briefing content
    wreck_template, created = ExcursionTypeDive.objects.get_or_create(
        excursion_type=wreck_dive,
        sequence=1,
        defaults={
            "name": "Juan Escutia Wreck Exploration",
            "description": "Multi-level wreck dive with structured descent and ascent profile.",
            "planned_depth_meters": 27,  # 90 feet max
            "planned_duration_minutes": 45,
            "offset_minutes": 30,
            "min_certification_level": advanced_ow,
            # Briefing content fields
            "gas": "ean32",
            "equipment_requirements": {
                "required": ["dive computer", "SMB", "cutting tool"],
                "recommended": ["camera with lanyard", "nitrox analyzer"],
                "not_allowed": ["gloves"],
            },
            "skills": [
                "controlled descent",
                "depth discipline",
                "multi-level navigation",
                "team positioning",
                "photography buoyancy control",
                "safety stop discipline",
            ],
            "hazards": (
                "Depth progression with overhead-like structure. "
                "Potential entanglement hazards near railings and rigging. "
                "Narcosis risk at depth (85-90 feet). "
                "Photography task loading - maintain buddy awareness. "
                "Current possible - check conditions before descent."
            ),
            "route": (
                "Descent to wreck → meet on main deck at 85' (5 min) → "
                "ascend to 75' explore deck (8 min) → "
                "ascend to 65' explore second deck and helipad (12 min photography) → "
                "ascend to 60' meet at poop deck → "
                "swim forward at depth to bow → "
                "ascend to 45' meet at bow → "
                "controlled ascent to 30' → "
                "safety stop at 15' for 3 min → "
                "slow ascent to surface (1 min)"
            ),
            # Structured multi-level profile for NDL validation
            # Equivalent depth ~18m → NDL 56 min → 42 min total is VALID
            "route_segments": [
                {"phase": "descent", "depth_m": 26, "duration_min": 3, "description": "Descend to wreck"},
                {"phase": "bottom", "depth_m": 26, "duration_min": 5, "description": "Main deck at 85'"},
                {"phase": "ascent", "depth_m": 23, "duration_min": 8, "description": "Explore deck at 75'"},
                {"phase": "ascent", "depth_m": 20, "duration_min": 12, "description": "Second deck/helipad at 65'"},
                {"phase": "ascent", "depth_m": 18, "duration_min": 5, "description": "Poop deck at 60'"},
                {"phase": "ascent", "depth_m": 14, "duration_min": 5, "description": "Bow at 45'"},
                {"phase": "safety_stop", "depth_m": 5, "duration_min": 3, "description": "Safety stop at 15'"},
                {"phase": "ascent", "depth_m": 0, "duration_min": 1, "description": "Surface"},
            ],
            "briefing_text": (
                "GAS: We dive EAN32 on this wreck but plan the dive on air tables. "
                "The nitrox provides additional safety margin at depth, not extended bottom time. "
                "Analyze your tank before the dive.\n\n"
                "DESCENT: We will descend as a group to the wreck and meet on the main deck. "
                "Initial exploration will be at 85 feet for approximately 5 minutes.\n\n"
                "MULTI-LEVEL PROFILE: We will ascend progressively to 75 feet for deck "
                "exploration (8 minutes), followed by 65 feet to explore the second deck "
                "and helipad area with time for photography (12 minutes).\n\n"
                "REGROUP: We will regroup at 60 feet at the poop deck and swim forward at "
                "depth toward the bow. At the bow we will ascend to 45 feet and regroup again.\n\n"
                "ASCENT: The ascent will continue at approximately 30 feet per minute with a "
                "safety stop at 15 feet for 3 minutes, followed by a slow, controlled "
                "ascent to the surface over 1 minute.\n\n"
                "KEY REMINDERS:\n"
                "• Stay with your buddy at all times\n"
                "• Monitor your depth and air consumption\n"
                "• Do not enter overhead environments\n"
                "• Signal if you need to ascend early\n"
                "• Cameras must be secured with lanyards"
            ),
            # Publish lifecycle - mark as published for immediate use
            "status": "published",
            "published_at": timezone.now(),
        }
    )
    if created:
        count += 1

    # Create price adjustments for dive sites if any exist
    for site in DiveSite.objects.all()[:3]:  # First 3 sites only
        # Distance surcharge
        adj, created = SitePriceAdjustment.objects.get_or_create(
            dive_site=site,
            kind="distance",
            defaults={
                "amount": Decimal("15.00"),
                "currency": "USD",
                "applies_to_mode": "",
                "is_per_diver": True,
                "is_active": True,
            }
        )
        if created:
            count += 1

        # Park fee (per diver)
        adj, created = SitePriceAdjustment.objects.get_or_create(
            dive_site=site,
            kind="park_fee",
            defaults={
                "amount": Decimal("5.00"),
                "currency": "USD",
                "applies_to_mode": "",
                "is_per_diver": True,
                "is_active": True,
            }
        )
        if created:
            count += 1

        # Night surcharge
        adj, created = SitePriceAdjustment.objects.get_or_create(
            dive_site=site,
            kind="night",
            defaults={
                "amount": Decimal("20.00"),
                "currency": "USD",
                "applies_to_mode": "",
                "is_per_diver": True,
                "is_active": True,
            }
        )
        if created:
            count += 1

        # Boat fee (per trip, not per diver)
        adj, created = SitePriceAdjustment.objects.get_or_create(
            dive_site=site,
            kind="boat",
            defaults={
                "amount": Decimal("50.00"),
                "currency": "USD",
                "applies_to_mode": "boat",
                "is_per_diver": False,
                "is_active": True,
            }
        )
        if created:
            count += 1

    return count


def verify():
    """Verify diveops constraints with negative writes."""
    results = []

    # Test 1: ExcursionType base_price must be >= 0
    try:
        with transaction.atomic():
            ExcursionType.objects.create(
                name="Test Negative Price",
                slug="test-negative-price",
                dive_mode="boat",
                time_of_day="day",
                max_depth_meters=18,
                base_price=Decimal("-10.00"),  # Should fail
                currency="USD",
            )
        results.append(("excursiontype_base_price_gte_zero", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("excursiontype_base_price_gte_zero", True, "Correctly rejected negative price"))

    # Test 2: ExcursionType max_depth_meters must be > 0
    try:
        with transaction.atomic():
            ExcursionType.objects.create(
                name="Test Zero Depth",
                slug="test-zero-depth",
                dive_mode="boat",
                time_of_day="day",
                max_depth_meters=0,  # Should fail
                base_price=Decimal("100.00"),
                currency="USD",
            )
        results.append(("excursiontype_depth_gt_zero", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("excursiontype_depth_gt_zero", True, "Correctly rejected zero depth"))

    # Test 3: ExcursionType slug must be unique
    existing = ExcursionType.objects.first()
    if existing:
        try:
            with transaction.atomic():
                ExcursionType.objects.create(
                    name="Duplicate Slug Test",
                    slug=existing.slug,  # Duplicate - should fail
                    dive_mode="shore",
                    time_of_day="day",
                    max_depth_meters=18,
                    base_price=Decimal("100.00"),
                    currency="USD",
                )
            results.append(("excursiontype_unique_slug", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("excursiontype_unique_slug", True, "Correctly rejected duplicate slug"))
    else:
        results.append(("excursiontype_unique_slug", None, "Skipped - no existing types"))

    # Test 4: SitePriceAdjustment amount must be >= 0
    site = DiveSite.objects.first()
    if site:
        try:
            with transaction.atomic():
                SitePriceAdjustment.objects.create(
                    dive_site=site,
                    kind="distance",
                    amount=Decimal("-5.00"),  # Should fail
                    currency="USD",
                )
            results.append(("sitepriceadjustment_amount_gte_zero", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("sitepriceadjustment_amount_gte_zero", True, "Correctly rejected negative amount"))
    else:
        results.append(("sitepriceadjustment_amount_gte_zero", None, "Skipped - no dive sites"))

    return results
