"""Migration for DiveSite overlay refactor - Part 1: Schema changes.

Adds new fields and prepares for data migration.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("diveops", "0007_basemodel_migration"),
        ("django_geo", "0001_initial"),
    ]

    operations = [
        # Step 1: Add new nullable fields
        migrations.AddField(
            model_name="divesite",
            name="rating",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Site rating 1-5 (null = unrated)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="divesite",
            name="tags",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Tags for categorization (e.g., ['reef', 'coral', 'wreck'])",
            ),
        ),

        # Step 2: Add new FK field for certification level (keep old field for now)
        migrations.AddField(
            model_name="divesite",
            name="min_certification_level_fk",
            field=models.ForeignKey(
                blank=True,
                help_text="Minimum certification required (null = no requirement)",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dive_sites_new",
                to="diveops.certificationlevel",
            ),
        ),

        # Step 3: Add rating constraint
        migrations.AddConstraint(
            model_name="divesite",
            constraint=models.CheckConstraint(
                condition=models.Q(rating__isnull=True) | (models.Q(rating__gte=1) & models.Q(rating__lte=5)),
                name="diveops_site_rating_1_to_5",
            ),
        ),
    ]
