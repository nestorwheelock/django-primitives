"""Add time semantics fields to WorkItem model."""

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    """Add effective_at and recorded_at fields to WorkItem."""

    dependencies = [
        ('django_catalog', '0003_add_basket_time_semantics'),
    ]

    operations = [
        migrations.AddField(
            model_name='workitem',
            name='effective_at',
            field=models.DateTimeField(
                db_index=True,
                default=timezone.now,
                help_text='When the work item was created in business terms',
                verbose_name='effective at',
            ),
        ),
        migrations.AddField(
            model_name='workitem',
            name='recorded_at',
            field=models.DateTimeField(
                auto_now_add=True,
                default=timezone.now,
                help_text='When the system learned about this work item',
                verbose_name='recorded at',
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='workitem',
            index=models.Index(fields=['effective_at'], name='django_cata_effecti_2d3e4f_idx'),
        ),
    ]
