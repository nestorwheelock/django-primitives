"""Add time semantics fields to WorkSession model."""

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    """Add effective_at and recorded_at fields to WorkSession."""

    dependencies = [
        ('django_worklog', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='worksession',
            name='effective_at',
            field=models.DateTimeField(
                db_index=True,
                default=timezone.now,
                help_text='When the session started in business terms',
            ),
        ),
        migrations.AddField(
            model_name='worksession',
            name='recorded_at',
            field=models.DateTimeField(
                auto_now_add=True,
                default=timezone.now,
                help_text='When the system learned about this session',
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='worksession',
            index=models.Index(fields=['effective_at'], name='django_work_effecti_3f4e5a_idx'),
        ),
    ]
