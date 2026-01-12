# Data migration to backfill last_inbound_at and last_outbound_at

from django.db import migrations


def backfill_timestamps(apps, schema_editor):
    """Backfill last_inbound_at and last_outbound_at from existing messages."""
    # Use raw SQL for efficiency on large tables
    schema_editor.execute("""
        UPDATE django_communication_conversation c SET
            last_inbound_at = (
                SELECT MAX(m.created_at)
                FROM django_communication_message m
                WHERE m.conversation_id = c.id
                  AND m.direction = 'inbound'
            ),
            last_outbound_at = (
                SELECT MAX(m.created_at)
                FROM django_communication_message m
                WHERE m.conversation_id = c.id
                  AND m.direction = 'outbound'
            )
        WHERE c.deleted_at IS NULL;
    """)


def reverse_backfill(apps, schema_editor):
    """Reverse: set timestamps to NULL."""
    schema_editor.execute("""
        UPDATE django_communication_conversation
        SET last_inbound_at = NULL, last_outbound_at = NULL;
    """)


class Migration(migrations.Migration):

    dependencies = [
        ("django_communication", "0009_add_conversation_direction_timestamps"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE django_communication_conversation c SET
                    last_inbound_at = (
                        SELECT MAX(m.created_at)
                        FROM django_communication_message m
                        WHERE m.conversation_id = c.id
                          AND m.direction = 'inbound'
                    ),
                    last_outbound_at = (
                        SELECT MAX(m.created_at)
                        FROM django_communication_message m
                        WHERE m.conversation_id = c.id
                          AND m.direction = 'outbound'
                    )
                WHERE c.deleted_at IS NULL;
            """,
            reverse_sql="""
                UPDATE django_communication_conversation
                SET last_inbound_at = NULL, last_outbound_at = NULL;
            """,
        ),
    ]
