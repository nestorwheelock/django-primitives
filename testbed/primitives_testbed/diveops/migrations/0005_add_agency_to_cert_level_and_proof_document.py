"""Add agency to CertificationLevel and proof_document to DiverCertification.

This migration:
1. Removes the old unique constraint on CertificationLevel.code
2. Adds agency FK to CertificationLevel
3. Adds max_depth_m to CertificationLevel
4. Adds new unique constraint on (agency, code)
5. Renames DiverCertification fields: certification_number -> card_number, certified_on -> issued_on
6. Removes DiverCertification.agency (now derived from level.agency)
7. Adds proof_document FK to DiverCertification
8. Updates constraints
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("django_parties", "0001_initial"),
        ("django_documents", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("diveops", "0004_alter_diverprofile_certification_agency"),
    ]

    operations = [
        # =====================================================================
        # CertificationLevel changes
        # =====================================================================

        # Remove old unique constraint on code
        migrations.RemoveConstraint(
            model_name="certificationlevel",
            name="diveops_cert_level_rank_gt_zero",
        ),

        # Remove unique on code field
        migrations.AlterField(
            model_name="certificationlevel",
            name="code",
            field=models.SlugField(
                max_length=20,
                help_text="Short code like 'ow', 'aow', 'dm' (unique per agency)",
            ),
        ),

        # Add agency FK
        migrations.AddField(
            model_name="certificationlevel",
            name="agency",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="certification_levels",
                to="django_parties.organization",
                help_text="Certification agency that defines this level (PADI, SSI, etc.)",
                null=True,  # Temporarily nullable for migration
            ),
        ),

        # Add max_depth_m
        migrations.AddField(
            model_name="certificationlevel",
            name="max_depth_m",
            field=models.PositiveSmallIntegerField(
                null=True,
                blank=True,
                help_text="Maximum depth in meters for this level (optional)",
            ),
        ),

        # Change ordering
        migrations.AlterModelOptions(
            name="certificationlevel",
            options={"ordering": ["agency", "rank"]},
        ),

        # Add new constraints for CertificationLevel
        migrations.AddConstraint(
            model_name="certificationlevel",
            constraint=models.UniqueConstraint(
                fields=["agency", "code"],
                condition=models.Q(deleted_at__isnull=True),
                name="diveops_unique_agency_level_code",
            ),
        ),
        migrations.AddConstraint(
            model_name="certificationlevel",
            constraint=models.CheckConstraint(
                condition=models.Q(rank__gt=0),
                name="diveops_cert_level_rank_gt_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="certificationlevel",
            constraint=models.CheckConstraint(
                condition=models.Q(max_depth_m__isnull=True) | models.Q(max_depth_m__gt=0),
                name="diveops_cert_level_depth_gt_zero",
            ),
        ),

        # =====================================================================
        # DiverCertification changes
        # =====================================================================

        # Remove old constraints
        migrations.RemoveConstraint(
            model_name="divercertification",
            name="diveops_unique_active_certification",
        ),
        migrations.RemoveConstraint(
            model_name="divercertification",
            name="diveops_cert_expires_after_certified",
        ),

        # Rename certification_number -> card_number
        migrations.RenameField(
            model_name="divercertification",
            old_name="certification_number",
            new_name="card_number",
        ),

        # Rename certified_on -> issued_on
        migrations.RenameField(
            model_name="divercertification",
            old_name="certified_on",
            new_name="issued_on",
        ),

        # Make issued_on nullable (was required before)
        migrations.AlterField(
            model_name="divercertification",
            name="issued_on",
            field=models.DateField(
                null=True,
                blank=True,
                help_text="Date certification was issued",
            ),
        ),

        # Make card_number blank=True
        migrations.AlterField(
            model_name="divercertification",
            name="card_number",
            field=models.CharField(
                max_length=100,
                blank=True,
                help_text="Certification card number",
            ),
        ),

        # Remove agency FK (now derived from level.agency)
        migrations.RemoveField(
            model_name="divercertification",
            name="agency",
        ),

        # Add proof_document FK
        migrations.AddField(
            model_name="divercertification",
            name="proof_document",
            field=models.ForeignKey(
                blank=True,
                help_text="Primary proof document (certification card photo/scan)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="certification_proofs",
                to="django_documents.document",
            ),
        ),

        # Update level field help_text
        migrations.AlterField(
            model_name="divercertification",
            name="level",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="diver_certifications",
                to="diveops.certificationlevel",
                help_text="Certification level (determines agency)",
            ),
        ),

        # Change ordering
        migrations.AlterModelOptions(
            name="divercertification",
            options={"ordering": ["-level__rank", "-issued_on"]},
        ),

        # Add new constraints for DiverCertification
        migrations.AddConstraint(
            model_name="divercertification",
            constraint=models.UniqueConstraint(
                fields=["diver", "level"],
                condition=models.Q(deleted_at__isnull=True),
                name="diveops_unique_active_certification",
            ),
        ),
        migrations.AddConstraint(
            model_name="divercertification",
            constraint=models.CheckConstraint(
                condition=models.Q(expires_on__isnull=True) | models.Q(issued_on__isnull=True) | models.Q(expires_on__gt=models.F("issued_on")),
                name="diveops_cert_expires_after_issued",
            ),
        ),
    ]
