# Generated manually for lead chat feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_communication", "0008_flow_types"),
    ]

    operations = [
        # Add denormalized timestamps for efficient "awaiting reply" badge computation
        migrations.AddField(
            model_name="conversation",
            name="last_inbound_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Timestamp of last inbound (customer) message - for 'awaiting reply' badge",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="last_outbound_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Timestamp of last outbound (staff) message - for 'awaiting reply' badge",
                null=True,
            ),
        ),
        # Unique constraint: one active conversation per related object (Person)
        # Supports identity continuity: lead→account→diver uses same conversation
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("related_content_type", "related_object_id"),
                name="unique_active_conversation_per_entity",
            ),
        ),
    ]
