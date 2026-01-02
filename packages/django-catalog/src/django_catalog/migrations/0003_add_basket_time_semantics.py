"""Add time semantics fields to Basket model."""

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    """Add effective_at and recorded_at fields to Basket."""

    dependencies = [
        ('django_catalog', '0002_add_catalogsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='basket',
            name='effective_at',
            field=models.DateTimeField(
                db_index=True,
                default=timezone.now,
                help_text='When the basket was created in business terms',
                verbose_name='effective at',
            ),
        ),
        migrations.AddField(
            model_name='basket',
            name='recorded_at',
            field=models.DateTimeField(
                auto_now_add=True,
                default=timezone.now,
                help_text='When the system learned about this basket',
                verbose_name='recorded at',
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='basket',
            index=models.Index(fields=['effective_at'], name='django_cata_effecti_1a2b3c_idx'),
        ),
    ]
