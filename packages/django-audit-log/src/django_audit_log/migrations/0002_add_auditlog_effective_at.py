"""Add effective_at field to AuditLog model for time semantics."""

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    """Add effective_at field to AuditLog for backdating events."""

    dependencies = [
        ('django_audit_log', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditlog',
            name='effective_at',
            field=models.DateTimeField(
                db_index=True,
                default=timezone.now,
                help_text='When the logged event happened (can differ from created_at for backdated events)',
            ),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['effective_at'], name='django_audi_effecti_9f8e7d_idx'),
        ),
    ]
