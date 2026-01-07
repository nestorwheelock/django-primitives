"""Refactor MarinePark to hierarchical ProtectedArea system.

Renames:
- MarinePark → ProtectedArea (+ adds parent FK for hierarchy)
- ParkZone → ProtectedAreaZone
- ParkRule → ProtectedAreaRule
- ParkFeeSchedule → ProtectedAreaFeeSchedule
- ParkFeeTier → ProtectedAreaFeeTier
- ParkGuideCredential → ProtectedAreaGuideCredential

Also renames FK fields (marine_park → protected_area, park_zone → protected_area_zone)
and constraint names to match new model names.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diveops", "0030_marine_park_models"),
    ]

    operations = [
        # =================================================================
        # Step 1: Add parent FK to MarinePark first (before renaming)
        # =================================================================
        migrations.AddField(
            model_name="marinepark",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="children",
                to="diveops.marinepark",
                help_text="Parent area (e.g., biosphere reserve containing parks)",
            ),
        ),

        # =================================================================
        # Step 2: Rename FK fields BEFORE renaming models
        # (to avoid FK reference issues during model rename)
        # =================================================================
        # ParkZone: marine_park → protected_area
        migrations.RenameField(
            model_name="parkzone",
            old_name="marine_park",
            new_name="protected_area",
        ),
        # ParkRule: marine_park → protected_area
        migrations.RenameField(
            model_name="parkrule",
            old_name="marine_park",
            new_name="protected_area",
        ),
        # ParkFeeSchedule: marine_park → protected_area
        migrations.RenameField(
            model_name="parkfeeschedule",
            old_name="marine_park",
            new_name="protected_area",
        ),
        # ParkGuideCredential: marine_park → protected_area
        migrations.RenameField(
            model_name="parkguidecredential",
            old_name="marine_park",
            new_name="protected_area",
        ),
        # VesselPermit: marine_park → protected_area
        migrations.RenameField(
            model_name="vesselpermit",
            old_name="marine_park",
            new_name="protected_area",
        ),
        # DiveSite: marine_park → protected_area, park_zone → protected_area_zone
        migrations.RenameField(
            model_name="divesite",
            old_name="marine_park",
            new_name="protected_area",
        ),
        migrations.RenameField(
            model_name="divesite",
            old_name="park_zone",
            new_name="protected_area_zone",
        ),

        # =================================================================
        # Step 3: Remove old constraints (before model renames)
        # =================================================================
        migrations.RemoveConstraint(
            model_name="parkzone",
            name="diveops_unique_zone_code_per_park",
        ),
        migrations.RemoveConstraint(
            model_name="parkguidecredential",
            name="diveops_unique_guide_credential_per_park",
        ),
        migrations.RemoveConstraint(
            model_name="vesselpermit",
            name="diveops_unique_permit_per_park",
        ),
        migrations.RemoveConstraint(
            model_name="divesite",
            name="diveops_site_zone_requires_park",
        ),

        # =================================================================
        # Step 4: Rename models
        # =================================================================
        migrations.RenameModel(
            old_name="MarinePark",
            new_name="ProtectedArea",
        ),
        migrations.RenameModel(
            old_name="ParkZone",
            new_name="ProtectedAreaZone",
        ),
        migrations.RenameModel(
            old_name="ParkRule",
            new_name="ProtectedAreaRule",
        ),
        migrations.RenameModel(
            old_name="ParkFeeSchedule",
            new_name="ProtectedAreaFeeSchedule",
        ),
        migrations.RenameModel(
            old_name="ParkFeeTier",
            new_name="ProtectedAreaFeeTier",
        ),
        migrations.RenameModel(
            old_name="ParkGuideCredential",
            new_name="ProtectedAreaGuideCredential",
        ),

        # =================================================================
        # Step 5: Add new constraints with updated names
        # =================================================================
        migrations.AddConstraint(
            model_name="protectedareazone",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True),
                fields=["protected_area", "code"],
                name="diveops_unique_zone_code_per_area",
            ),
        ),
        migrations.AddConstraint(
            model_name="protectedareaguidecredential",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True),
                fields=["protected_area", "diver"],
                name="diveops_unique_guide_credential_per_area",
            ),
        ),
        migrations.AddConstraint(
            model_name="vesselpermit",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True),
                fields=["protected_area", "permit_number"],
                name="diveops_unique_permit_per_area",
            ),
        ),
        migrations.AddConstraint(
            model_name="divesite",
            constraint=models.CheckConstraint(
                condition=models.Q(protected_area_zone__isnull=True) | models.Q(protected_area__isnull=False),
                name="diveops_site_zone_requires_area",
            ),
        ),

        # =================================================================
        # Step 6: Add index on parent field
        # =================================================================
        migrations.AddIndex(
            model_name="protectedarea",
            index=models.Index(fields=["parent"], name="diveops_pro_parent__3b8e5a_idx"),
        ),
    ]
