"""Seed default dive segment types."""

from django.db import migrations


def seed_segment_types(apps, schema_editor):
    """Create default dive segment types."""
    DiveSegmentType = apps.get_model("diveops", "DiveSegmentType")

    defaults = [
        {"name": "descent", "display_name": "Descent", "is_depth_transition": True, "sort_order": 10, "color": "cyan"},
        {"name": "level", "display_name": "Level Section", "is_depth_transition": False, "sort_order": 20, "color": "blue"},
        {"name": "exploration", "display_name": "Exploration", "is_depth_transition": False, "sort_order": 30, "color": "indigo"},
        {"name": "wreck_tour", "display_name": "Wreck Tour", "is_depth_transition": False, "sort_order": 40, "color": "purple"},
        {"name": "reef_tour", "display_name": "Reef Tour", "is_depth_transition": False, "sort_order": 50, "color": "teal"},
        {"name": "wall_dive", "display_name": "Wall Dive", "is_depth_transition": False, "sort_order": 60, "color": "violet"},
        {"name": "drift", "display_name": "Drift Section", "is_depth_transition": False, "sort_order": 70, "color": "sky"},
        {"name": "safety_stop", "display_name": "Safety Stop", "is_depth_transition": False, "sort_order": 90, "color": "green"},
        {"name": "ascent", "display_name": "Ascent", "is_depth_transition": True, "sort_order": 100, "color": "amber"},
    ]

    for data in defaults:
        DiveSegmentType.objects.get_or_create(
            name=data["name"],
            defaults={
                "display_name": data["display_name"],
                "is_depth_transition": data["is_depth_transition"],
                "sort_order": data["sort_order"],
                "color": data["color"],
            }
        )


def remove_segment_types(apps, schema_editor):
    """Remove default dive segment types (reverse migration)."""
    DiveSegmentType = apps.get_model("diveops", "DiveSegmentType")
    default_names = [
        "descent", "level", "exploration", "wreck_tour", "reef_tour",
        "wall_dive", "drift", "safety_stop", "ascent"
    ]
    DiveSegmentType.objects.filter(name__in=default_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diveops", "0023_add_dive_segment_type"),
    ]

    operations = [
        migrations.RunPython(seed_segment_types, remove_segment_types),
    ]
