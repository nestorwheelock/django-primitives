"""Migration for DiveSite overlay refactor - Part 2: Data migration.

Migrates existing data and removes old fields.
"""

from django.db import migrations, models
import django.db.models.deletion


def create_places_for_dive_sites(apps, schema_editor):
    """Create Place for each DiveSite from existing lat/lon."""
    DiveSite = apps.get_model("diveops", "DiveSite")
    Place = apps.get_model("django_geo", "Place")

    for site in DiveSite.objects.filter(place__isnull=True):
        # Create owned Place from existing coordinates
        place = Place.objects.create(
            name=f"{site.name} Location",
            latitude=site.latitude,
            longitude=site.longitude,
        )
        site.place = place
        site.save(update_fields=["place"])


def reverse_create_places(apps, schema_editor):
    """Reverse: copy Place coords back to DiveSite (for rollback)."""
    DiveSite = apps.get_model("diveops", "DiveSite")

    for site in DiveSite.objects.filter(place__isnull=False):
        site.latitude = site.place.latitude
        site.longitude = site.place.longitude
        site.save(update_fields=["latitude", "longitude"])


def convert_certification_charfield_to_fk(apps, schema_editor):
    """Convert min_certification_level CharField to FK lookup."""
    DiveSite = apps.get_model("diveops", "DiveSite")
    CertificationLevel = apps.get_model("diveops", "CertificationLevel")

    # Build lookup table: code -> CertificationLevel (first match)
    cert_lookup = {}
    for cert in CertificationLevel.objects.filter(deleted_at__isnull=True):
        if cert.code not in cert_lookup:
            cert_lookup[cert.code] = cert

    for site in DiveSite.objects.exclude(min_certification_level=""):
        old_code = site.min_certification_level
        if old_code in cert_lookup:
            site.min_certification_level_fk = cert_lookup[old_code]
            site.save(update_fields=["min_certification_level_fk"])


def reverse_certification_fk_to_charfield(apps, schema_editor):
    """Reverse: copy FK code back to CharField."""
    DiveSite = apps.get_model("diveops", "DiveSite")

    for site in DiveSite.objects.filter(min_certification_level_fk__isnull=False):
        site.min_certification_level = site.min_certification_level_fk.code
        site.save(update_fields=["min_certification_level"])


class Migration(migrations.Migration):

    dependencies = [
        ("diveops", "0008_divesite_overlay_refactor"),
    ]

    operations = [
        # Step 1: Data migration - create Place from lat/lon
        migrations.RunPython(
            create_places_for_dive_sites,
            reverse_create_places,
        ),

        # Step 2: Data migration - convert CharFieldto FK
        migrations.RunPython(
            convert_certification_charfield_to_fk,
            reverse_certification_fk_to_charfield,
        ),
    ]
