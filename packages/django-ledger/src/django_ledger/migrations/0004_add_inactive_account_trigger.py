"""Add PostgreSQL trigger to prevent entries on inactive accounts."""

from django.db import migrations


class Migration(migrations.Migration):
    """Add trigger to enforce inactive account constraint at database level."""

    dependencies = [
        ("django_ledger", "0003_add_account_is_active"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION check_account_is_active()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF NOT (SELECT is_active FROM django_ledger_account WHERE id = NEW.account_id) THEN
                        RAISE EXCEPTION 'Cannot create entry on inactive account (account_id: %)', NEW.account_id;
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER entry_check_account_active
                BEFORE INSERT ON django_ledger_entry
                FOR EACH ROW
                EXECUTE FUNCTION check_account_is_active();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS entry_check_account_active ON django_ledger_entry;
                DROP FUNCTION IF EXISTS check_account_is_active();
            """,
        ),
    ]
