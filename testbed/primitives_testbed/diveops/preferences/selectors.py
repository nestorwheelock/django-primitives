"""Selectors for preference queries.

Read-only queries for preference status and data retrieval.
"""

from collections import defaultdict

from django.db.models import Q

from .models import PreferenceDefinition, PartyPreference, Sensitivity


def get_diver_preference_status(diver):
    """Get preference completion status for a diver.

    Args:
        diver: DiverProfile instance

    Returns:
        Dict with:
        - total_definitions: Total active preference definitions
        - collected_count: Number of preferences collected
        - missing_count: Number of preferences not collected
        - completion_percent: Percentage complete (0-100)
        - categories: Dict of category status
        - needs_intake_survey: Bool if intake survey needed
    """
    person = diver.person

    # Get all active preference definitions grouped by category
    definitions = PreferenceDefinition.objects.filter(
        is_active=True
    ).values("pk", "key", "category")

    definitions_list = list(definitions)
    total = len(definitions_list)

    if total == 0:
        return {
            "total_definitions": 0,
            "collected_count": 0,
            "missing_count": 0,
            "completion_percent": 100,
            "categories": {},
            "needs_intake_survey": False,
        }

    # Get collected preference keys
    collected_keys = set(
        PartyPreference.objects.filter(
            person=person
        ).values_list("definition__key", flat=True)
    )

    # Group definitions by category
    category_stats = defaultdict(lambda: {"total": 0, "collected": 0})
    for defn in definitions_list:
        cat = defn["category"]
        category_stats[cat]["total"] += 1
        if defn["key"] in collected_keys:
            category_stats[cat]["collected"] += 1

    # Add complete flag
    categories = {}
    for cat, stats in category_stats.items():
        categories[cat] = {
            "total": stats["total"],
            "collected": stats["collected"],
            "complete": stats["collected"] == stats["total"],
        }

    collected_count = len(collected_keys & {d["key"] for d in definitions_list})
    missing_count = total - collected_count
    completion_percent = round((collected_count / total) * 100) if total > 0 else 100

    return {
        "total_definitions": total,
        "collected_count": collected_count,
        "missing_count": missing_count,
        "completion_percent": completion_percent,
        "categories": categories,
        "needs_intake_survey": missing_count > 0,
    }


def list_diver_preferences_by_category(diver, include_sensitive=False):
    """Get diver's preferences grouped by category.

    Args:
        diver: DiverProfile instance
        include_sensitive: If True, include sensitive preferences (default False)

    Returns:
        Dict with category keys containing lists of preference data:
        {
            "diving": [
                {"key": "diving.interests", "label": "...", "value": [...], ...},
            ],
            ...
        }
    """
    person = diver.person

    # Build query
    qs = PartyPreference.objects.filter(
        person=person
    ).select_related("definition").order_by(
        "definition__category", "definition__sort_order"
    )

    if not include_sensitive:
        qs = qs.exclude(definition__sensitivity=Sensitivity.SENSITIVE)

    # Group by category
    result = defaultdict(list)
    for pref in qs:
        defn = pref.definition
        result[defn.category].append({
            "key": defn.key,
            "label": defn.label,
            "value": pref.get_value(),
            "value_type": defn.value_type,
            "sensitivity": defn.sensitivity,
            "collected_at": pref.collected_at,
        })

    return dict(result)


# Mapping of preference values to specialty certification codes
INTEREST_TO_SPECIALTY = {
    "Wrecks": "wreck",
    "Night diving": "night",
    "Cenotes": "cavern",
    "Caves": "cavern",
    "Macro photography": "photo",
    "Wide-angle photography": "photo",
}

# Progression path (in order): sd -> ow -> aow -> rescue -> dm
PROGRESSION_PATH = ["sd", "ow", "aow", "rescue", "dm"]

# Specialties that are commonly recommended for beginners
BEGINNER_SPECIALTIES = ["ppb", "nitrox"]

# Minimum certification rank required for certain specialties
SPECIALTY_REQUIREMENTS = {
    "cavern": 3,  # Requires AOW
    "deep": 3,    # Requires AOW
}


def get_recommended_certifications(diver, limit=5):
    """Get recommended certifications based on progression and preferences.

    Recommends:
    1. Next level in progression path (highest priority)
    2. Specialties based on diving interests preferences
    3. Common specialties for skill development (PPB, Nitrox)

    Args:
        diver: DiverProfile instance
        limit: Maximum number of recommendations to return

    Returns:
        List of dicts with:
        - level: CertificationLevel instance
        - reason: String explaining why this is recommended
        - priority: Integer score (higher = more recommended)
    """
    from datetime import date
    from django.db.models import Q

    from ..models import CertificationLevel, DiverCertification

    recommendations = []

    # Get diver's current certifications
    current_cert_codes = set(
        DiverCertification.objects.filter(
            diver=diver,
            deleted_at__isnull=True,
        ).filter(
            Q(expires_on__isnull=True) | Q(expires_on__gt=date.today())
        ).values_list("level__code", flat=True)
    )

    # Get all certification levels
    all_levels = {
        level.code: level
        for level in CertificationLevel.objects.filter(
            is_active=True, deleted_at__isnull=True
        ).select_related("agency")
    }

    # Determine highest progression level
    current_progression_rank = 0
    for code in PROGRESSION_PATH:
        if code in current_cert_codes:
            level = all_levels.get(code)
            if level and level.rank > current_progression_rank:
                current_progression_rank = level.rank

    # 1. Recommend next progression level (highest priority)
    # For uncertified divers, recommend OW (rank 2) directly - SD is a stepping stone
    # For certified divers, recommend the next level in progression
    next_progression = None
    target_rank = current_progression_rank + 1 if current_progression_rank > 0 else 2
    for code in PROGRESSION_PATH:
        level = all_levels.get(code)
        if level and code not in current_cert_codes:
            if level.rank == target_rank:
                next_progression = level
                break

    if next_progression:
        reason = "Next step in your diving journey"
        if next_progression.code == "ow":
            reason = "Your first open water certification"
        elif next_progression.code == "aow":
            reason = "Expand your skills and dive deeper"
        elif next_progression.code == "rescue":
            reason = "Learn to help others and become a safer diver"
        elif next_progression.code == "dm":
            reason = "Take the first step toward professional diving"

        recommendations.append({
            "level": next_progression,
            "reason": reason,
            "priority": 100,
        })

    # 2. Recommend specialties based on preferences (if OW or higher)
    if current_progression_rank >= 2:  # At least OW
        # Get diver's interests preference
        interests_pref = PartyPreference.objects.filter(
            person=diver.person,
            definition__key="diving.interests",
        ).first()

        if interests_pref and interests_pref.value_json:
            for interest in interests_pref.value_json:
                specialty_code = INTEREST_TO_SPECIALTY.get(interest)
                if specialty_code and specialty_code not in current_cert_codes:
                    level = all_levels.get(specialty_code)
                    if level:
                        # Check minimum requirements
                        min_rank = SPECIALTY_REQUIREMENTS.get(specialty_code, 2)
                        if current_progression_rank >= min_rank:
                            recommendations.append({
                                "level": level,
                                "reason": f"Based on your interest in {interest}",
                                "priority": 50,
                            })

        # Check photography preference
        photo_pref = PartyPreference.objects.filter(
            person=diver.person,
            definition__key="diving.likes_photography",
        ).first()

        if photo_pref and photo_pref.value_bool and "photo" not in current_cert_codes:
            level = all_levels.get("photo")
            if level:
                recommendations.append({
                    "level": level,
                    "reason": "Based on your interest in underwater photography",
                    "priority": 50,
                })

        # Check depth comfort for deep diver recommendation
        depth_pref = PartyPreference.objects.filter(
            person=diver.person,
            definition__key="diving.depth_comfort",
        ).first()

        if depth_pref and depth_pref.value_text:
            if "30-40m" in depth_pref.value_text or "40m+" in depth_pref.value_text:
                if "deep" not in current_cert_codes and current_progression_rank >= 3:
                    level = all_levels.get("deep")
                    if level:
                        recommendations.append({
                            "level": level,
                            "reason": "Expand your depth range safely",
                            "priority": 45,
                        })

    # 3. Recommend common beginner specialties (if OW or higher)
    if current_progression_rank >= 2:
        for code in BEGINNER_SPECIALTIES:
            if code not in current_cert_codes:
                level = all_levels.get(code)
                if level:
                    reason = "Master your buoyancy control" if code == "ppb" else "Extend your bottom time with enriched air"
                    recommendations.append({
                        "level": level,
                        "reason": reason,
                        "priority": 30,
                    })

    # Remove duplicates (keep highest priority)
    seen_codes = set()
    unique_recommendations = []
    for rec in sorted(recommendations, key=lambda r: -r["priority"]):
        if rec["level"].code not in seen_codes:
            seen_codes.add(rec["level"].code)
            unique_recommendations.append(rec)

    # Sort by priority and limit
    return unique_recommendations[:limit]


# Mapping of certification codes to courseware entitlement patterns
CERT_TO_COURSEWARE_PATTERN = {
    "ow": "owd",  # Open Water Diver
    "aow": "aow",  # Advanced Open Water
    "rescue": "rescue",
    "dm": "dm",
    "nitrox": "nitrox",
    "deep": "deep",
    "wreck": "wreck",
    "night": "night",
    "ppb": "ppb",
    "photo": "photo",
    "cavern": "cavern",
}


def get_recommended_courseware(diver, limit=5):
    """Get recommended courseware based on certification recommendations.

    Recommends eLearning courseware for:
    1. Next certification in progression path (highest priority)
    2. Specialty certifications based on interests
    3. Common specialties like Nitrox

    Excludes courseware the user already has entitlements for.

    Args:
        diver: DiverProfile instance
        limit: Maximum number of recommendations to return

    Returns:
        List of dicts with:
        - item: CatalogItem instance
        - price: Decimal price amount (or None)
        - reason: String explaining why this is recommended
        - priority: Integer score (higher = more recommended)
    """
    from django.utils import timezone

    from django_catalog.models import CatalogItem

    from primitives_testbed.diveops.entitlements.services import get_user_entitlements
    from primitives_testbed.pricing.models import Price
    from primitives_testbed.store.models import CatalogItemEntitlement

    recommendations = []

    # Get certification recommendations
    cert_recommendations = get_recommended_certifications(diver, limit=10)

    # Get user's current entitlements
    user = getattr(diver.person, 'user', None)
    user_entitlements = set()
    if user:
        user_entitlements = set(get_user_entitlements(user))

    # Get all active courseware items (services with entitlements)
    courseware_items = CatalogItem.objects.filter(
        kind="service",
        active=True,
        deleted_at__isnull=True,
    ).select_related('store_entitlement')

    # Build lookup of entitlement patterns to catalog items
    entitlement_to_item = {}
    for item in courseware_items:
        try:
            ent = item.store_entitlement
            if ent and ent.entitlement_codes:
                for code in ent.entitlement_codes:
                    entitlement_to_item[code] = item
        except CatalogItemEntitlement.DoesNotExist:
            pass

    # Match certification recommendations to courseware
    for cert_rec in cert_recommendations:
        cert_code = cert_rec["level"].code
        pattern = CERT_TO_COURSEWARE_PATTERN.get(cert_code)

        if not pattern:
            continue

        # Look for matching courseware entitlement
        entitlement_code = f"content:{pattern}-courseware"

        # Skip if user already has this entitlement
        if entitlement_code in user_entitlements:
            continue

        # Find the courseware item
        item = entitlement_to_item.get(entitlement_code)
        if not item:
            continue

        # Get current price
        price = Price.objects.filter(
            catalog_item=item,
            valid_from__lte=timezone.now(),
            organization__isnull=True,
            party__isnull=True,
            agreement__isnull=True,
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=timezone.now())
        ).order_by('-priority', '-valid_from').first()

        recommendations.append({
            "item": item,
            "price": price.amount if price else None,
            "reason": f"Prepare for your {cert_rec['level'].name} certification",
            "priority": cert_rec["priority"],
        })

    # Remove duplicates (keep highest priority)
    seen_items = set()
    unique_recommendations = []
    for rec in sorted(recommendations, key=lambda r: -r["priority"]):
        if rec["item"].pk not in seen_items:
            seen_items.add(rec["item"].pk)
            unique_recommendations.append(rec)

    return unique_recommendations[:limit]


# Mapping of diving interests to gear keywords
INTEREST_TO_GEAR_KEYWORDS = {
    "Macro photography": ["Camera", "Housing", "Strobe", "Light"],
    "Wide-angle photography": ["Camera", "Housing", "Wide", "Dome"],
    "Night diving": ["Light", "Torch", "Night"],
    "Wrecks": ["Reel", "Line", "Light", "Torch"],
    "Cenotes": ["Reel", "Light", "Line"],
    "Caves": ["Reel", "Light", "Line"],
}

# Basic gear keywords for new divers
BASIC_GEAR_KEYWORDS = ["Computer", "Mask", "Fins", "Snorkel"]


def get_recommended_gear(diver, limit=5):
    """Get recommended gear based on diving interests and experience level.

    Recommends gear for:
    1. Interest-based recommendations (photography gear, night diving lights)
    2. Basic gear for new OW divers (computer, mask, fins)

    Args:
        diver: DiverProfile instance
        limit: Maximum number of recommendations to return

    Returns:
        List of dicts with:
        - item: CatalogItem instance
        - price: Decimal price amount (or None)
        - reason: String explaining why this is recommended
        - priority: Integer score (higher = more recommended)
    """
    from datetime import date

    from django.utils import timezone

    from django_catalog.models import CatalogItem

    from primitives_testbed.pricing.models import Price

    from ..models import DiverCertification

    recommendations = []

    # Check diver's certification level
    current_certs = DiverCertification.objects.filter(
        diver=diver,
        deleted_at__isnull=True,
    ).filter(
        Q(expires_on__isnull=True) | Q(expires_on__gt=date.today())
    ).select_related("level")

    # Determine highest rank
    highest_rank = 0
    for cert in current_certs:
        if cert.level.rank > highest_rank and cert.level.rank < 10:  # Exclude specialties
            highest_rank = cert.level.rank

    # Get all active gear items (stock_items)
    gear_items = CatalogItem.objects.filter(
        kind="stock_item",
        active=True,
        deleted_at__isnull=True,
    )

    # Build a mapping of item to price
    item_prices = {}
    for item in gear_items:
        price = Price.objects.filter(
            catalog_item=item,
            valid_from__lte=timezone.now(),
            organization__isnull=True,
            party__isnull=True,
            agreement__isnull=True,
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=timezone.now())
        ).order_by('-priority', '-valid_from').first()
        item_prices[item.pk] = price.amount if price else None

    # Only recommend gear for certified divers (at least OW)
    if highest_rank < 2:
        return []

    # Get diver's interests from preferences
    interests_pref = PartyPreference.objects.filter(
        person=diver.person,
        definition__key="diving.interests",
    ).first()

    user_interests = []
    if interests_pref and interests_pref.value_json:
        user_interests = interests_pref.value_json

    # Check for photography preference
    photo_pref = PartyPreference.objects.filter(
        person=diver.person,
        definition__key="diving.likes_photography",
    ).first()

    if photo_pref and photo_pref.value_bool:
        if "Macro photography" not in user_interests:
            user_interests.append("Macro photography")

    # Interest-based gear recommendations
    for interest in user_interests:
        keywords = INTEREST_TO_GEAR_KEYWORDS.get(interest, [])
        for keyword in keywords:
            for item in gear_items:
                if keyword.lower() in item.display_name.lower():
                    recommendations.append({
                        "item": item,
                        "price": item_prices.get(item.pk),
                        "reason": f"Great for {interest.lower()}",
                        "priority": 50,
                    })

    # Basic gear for new OW divers (rank 2)
    if highest_rank == 2:
        for keyword in BASIC_GEAR_KEYWORDS:
            for item in gear_items:
                if keyword.lower() in item.display_name.lower():
                    recommendations.append({
                        "item": item,
                        "price": item_prices.get(item.pk),
                        "reason": "Essential gear for new divers",
                        "priority": 30,
                    })

    # Remove duplicates (keep highest priority)
    seen_items = set()
    unique_recommendations = []
    for rec in sorted(recommendations, key=lambda r: -r["priority"]):
        if rec["item"].pk not in seen_items:
            seen_items.add(rec["item"].pk)
            unique_recommendations.append(rec)

    return unique_recommendations[:limit]
