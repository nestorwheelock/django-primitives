"""Add time semantics fields to EncounterTransition model."""

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    """Add effective_at and recorded_at fields to EncounterTransition."""

    dependencies = [
        ('django_encounters', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='encountertransition',
            name='effective_at',
            field=models.DateTimeField(
                db_index=True,
                default=timezone.now,
                help_text='When the transition happened in business terms',
            ),
        ),
        migrations.AddField(
            model_name='encountertransition',
            name='recorded_at',
            field=models.DateTimeField(
                auto_now_add=True,
                default=timezone.now,
                help_text='When the system learned about this transition',
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='encountertransition',
            index=models.Index(fields=['effective_at'], name='django_enco_effecti_4g5h6i_idx'),
        ),
    ]
