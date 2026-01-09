"""Seed command for preference definitions.

Creates the MVP set of preference definitions for diver preference collection.
"""

from django.core.management.base import BaseCommand

from primitives_testbed.diveops.preferences.models import (
    PreferenceDefinition,
    ValueType,
    Sensitivity,
)

# MVP Preference Definitions
PREFERENCE_DEFINITIONS = [
    # Demographics
    {
        "key": "demographics.language_primary",
        "label": "Primary Language",
        "category": "demographics",
        "value_type": ValueType.CHOICE,
        "choices_json": ["English", "Spanish", "French", "German", "Italian", "Portuguese", "Chinese", "Japanese", "Korean", "Other"],
        "sensitivity": Sensitivity.INTERNAL,
        "sort_order": 1,
    },
    {
        "key": "demographics.language_secondary",
        "label": "Other Languages Spoken",
        "category": "demographics",
        "value_type": ValueType.MULTI_CHOICE,
        "choices_json": ["English", "Spanish", "French", "German", "Italian", "Portuguese", "Chinese", "Japanese", "Korean", "Other"],
        "sensitivity": Sensitivity.INTERNAL,
        "sort_order": 2,
    },
    {
        "key": "demographics.gender",
        "label": "Gender",
        "category": "demographics",
        "value_type": ValueType.CHOICE,
        "choices_json": ["Male", "Female", "Non-binary", "Prefer not to say", "Other"],
        "sensitivity": Sensitivity.SENSITIVE,
        "sort_order": 3,
    },
    # Diving Preferences
    {
        "key": "diving.experience_level_self",
        "label": "How would you describe your diving experience?",
        "category": "diving",
        "value_type": ValueType.CHOICE,
        "choices_json": ["Beginner (< 20 dives)", "Intermediate (20-100 dives)", "Experienced (100-500 dives)", "Expert (500+ dives)"],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 1,
    },
    {
        "key": "diving.preferred_dive_modes",
        "label": "Preferred Dive Types",
        "category": "diving",
        "value_type": ValueType.MULTI_CHOICE,
        "choices_json": ["Boat diving", "Shore diving", "Cenote diving", "Cavern/cave diving", "Night diving", "Drift diving"],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 2,
    },
    {
        "key": "diving.depth_comfort",
        "label": "Depth Comfort Level",
        "category": "diving",
        "value_type": ValueType.CHOICE,
        "choices_json": ["Shallow (< 18m / 60ft)", "Recreational (18-30m / 60-100ft)", "Deep recreational (30-40m / 100-130ft)", "Technical (40m+ / 130ft+)"],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 3,
    },
    {
        "key": "diving.interests",
        "label": "Diving Interests",
        "category": "diving",
        "value_type": ValueType.MULTI_CHOICE,
        "choices_json": ["Reef/coral", "Wrecks", "Marine life", "Macro photography", "Wide-angle photography", "Cenotes", "Caves", "Night diving", "Technical diving"],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 4,
    },
    {
        "key": "diving.likes_photography",
        "label": "Interested in Underwater Photography",
        "category": "diving",
        "value_type": ValueType.BOOL,
        "choices_json": [],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 5,
    },
    {
        "key": "diving.prefers_private",
        "label": "Prefers Private/Small Group Dives",
        "category": "diving",
        "value_type": ValueType.BOOL,
        "choices_json": [],
        "sensitivity": Sensitivity.INTERNAL,
        "sort_order": 6,
    },
    {
        "key": "diving.current_tolerance",
        "label": "Current Tolerance",
        "category": "diving",
        "value_type": ValueType.CHOICE,
        "choices_json": ["Calm only", "Mild current OK", "Strong current OK", "Any conditions"],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 7,
    },
    # Food Preferences
    {
        "key": "food.dietary_restrictions",
        "label": "Dietary Restrictions",
        "category": "food",
        "value_type": ValueType.MULTI_CHOICE,
        "choices_json": ["None", "Vegetarian", "Vegan", "Gluten-free", "Kosher", "Halal", "Lactose-free", "Nut-free", "Other"],
        "sensitivity": Sensitivity.INTERNAL,
        "sort_order": 1,
    },
    {
        "key": "food.allergies",
        "label": "Food Allergies",
        "category": "food",
        "value_type": ValueType.TEXT,
        "choices_json": [],
        "sensitivity": Sensitivity.SENSITIVE,
        "sort_order": 2,
    },
    # Goals
    {
        "key": "goals.next_certification",
        "label": "Next Certification Goal",
        "category": "goals",
        "value_type": ValueType.CHOICE,
        "choices_json": ["None planned", "Advanced Open Water", "Rescue Diver", "Divemaster", "Specialty course", "Technical certification", "Instructor"],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 1,
    },
    {
        "key": "goals.bucket_list_sites",
        "label": "Bucket List Dive Sites",
        "category": "goals",
        "value_type": ValueType.TEXT,
        "choices_json": [],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 2,
    },
    # Activities & Interests
    {
        "key": "activities.other_interests",
        "label": "Other Interests & Hobbies",
        "category": "activities",
        "value_type": ValueType.MULTI_CHOICE,
        "choices_json": ["Snorkeling", "Freediving", "Fishing", "Boating", "Kayaking", "Surfing", "Swimming", "Beach activities", "Hiking", "Travel", "Photography", "Wildlife watching"],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 1,
    },
    # Music (for boat music selection, social matching)
    {
        "key": "music.favorite_genres",
        "label": "Favorite Music Genres",
        "category": "music",
        "value_type": ValueType.MULTI_CHOICE,
        "choices_json": ["Rock", "Pop", "Electronic", "Jazz", "Classical", "Country", "Hip-hop", "R&B", "Latin", "Reggae", "No preference"],
        "sensitivity": Sensitivity.PUBLIC,
        "sort_order": 1,
    },
]


class Command(BaseCommand):
    help = "Seed preference definitions for diver preference collection"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update existing definitions",
        )

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for pref_data in PREFERENCE_DEFINITIONS:
            key = pref_data["key"]

            existing = PreferenceDefinition.objects.filter(key=key).first()

            if existing:
                if options["force"]:
                    # Update existing
                    for field, value in pref_data.items():
                        setattr(existing, field, value)
                    existing.save()
                    updated_count += 1
                    self.stdout.write(f"  Updated: {key}")
                else:
                    skipped_count += 1
            else:
                # Create new
                PreferenceDefinition.objects.create(**pref_data)
                created_count += 1
                self.stdout.write(f"  Created: {key}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nPreference definitions seeded: "
                f"{created_count} created, {updated_count} updated, {skipped_count} skipped"
            )
        )

        # Summary by category
        categories = {}
        for pref in PreferenceDefinition.objects.filter(is_active=True):
            cat = pref.category
            categories[cat] = categories.get(cat, 0) + 1

        self.stdout.write("\nBy category:")
        for cat, count in sorted(categories.items()):
            self.stdout.write(f"  {cat}: {count} definitions")
