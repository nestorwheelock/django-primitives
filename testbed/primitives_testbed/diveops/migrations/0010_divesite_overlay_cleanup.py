"""Migration for DiveSite overlay refactor - Part 3: Cleanup.

Removes old fields after data migration.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("diveops", "0009_divesite_overlay_data_migration"),
    ]

    operations = [
        # Step 1: Remove old lat/lon constraints
        migrations.RemoveConstraint(
            model_name="divesite",
            name="diveops_site_valid_latitude",
        ),
        migrations.RemoveConstraint(
            model_name="divesite",
            name="diveops_site_valid_longitude",
        ),

        # Step 2: Make place required (after data migration populated it)
        migrations.AlterField(
            model_name="divesite",
            name="place",
            field=models.ForeignKey(
                help_text="Location (owned per site, not shared)",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dive_sites",
                to="django_geo.place",
            ),
        ),

        # Step 3: Remove latitude, longitude fields
        migrations.RemoveField(
            model_name="divesite",
            name="latitude",
        ),
        migrations.RemoveField(
            model_name="divesite",
            name="longitude",
        ),

        # Step 4: Remove old index on min_certification_level
        migrations.RemoveIndex(
            model_name="divesite",
            name="diveops_div_min_cer_93bfae_idx",
        ),

        # Step 5: Remove old CharField min_certification_level
        migrations.RemoveField(
            model_name="divesite",
            name="min_certification_level",
        ),

        # Step 6: Rename FK field to final name
        migrations.RenameField(
            model_name="divesite",
            old_name="min_certification_level_fk",
            new_name="min_certification_level",
        ),

        # Step 7: Update related_name after rename
        migrations.AlterField(
            model_name="divesite",
            name="min_certification_level",
            field=models.ForeignKey(
                blank=True,
                help_text="Minimum certification required (null = no requirement)",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dive_sites",
                to="diveops.certificationlevel",
            ),
        ),
    ]
