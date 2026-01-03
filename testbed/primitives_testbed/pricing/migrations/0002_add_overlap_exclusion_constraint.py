"""Add PostgreSQL exclusion constraint to prevent overlapping prices.

This migration enforces at the database level that for a given
(catalog_item + scope combination), effective date ranges cannot overlap.

Key design decisions:
1. Uses btree_gist extension for exclusion constraints with equality operators
2. Uses COALESCE to normalize NULLs to a sentinel UUID, because NULL != NULL
   in PostgreSQL would defeat the constraint
3. Uses tstzrange with '[)' bounds (inclusive start, exclusive end) for
   standard temporal semantics
4. NULL valid_to is treated as 'infinity' (open-ended range)

This constraint cannot be bypassed by concurrent transactions - PostgreSQL
holds an exclusive lock during the constraint check.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0001_initial"),
    ]

    operations = [
        # Enable btree_gist extension (required for exclusion constraints
        # that combine equality and range operators)
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS btree_gist;",
            reverse_sql="-- btree_gist extension kept (may be used elsewhere)",
        ),
        # Add the exclusion constraint
        #
        # Design notes:
        # - COALESCE converts NULL to sentinel UUID so NULL scopes match each other
        # - tstzrange(valid_from, valid_to, '[)') creates a half-open range
        # - '&&' operator checks if ranges overlap
        # - GIST index is used for efficient overlap checking
        #
        # This guarantees: for any (catalog_item, org, party, agreement) tuple,
        # no two price records can have overlapping [valid_from, valid_to) ranges.
        migrations.RunSQL(
            sql="""
                ALTER TABLE pricing_price
                ADD CONSTRAINT price_no_overlapping_date_ranges
                EXCLUDE USING GIST (
                    catalog_item_id WITH =,
                    COALESCE(organization_id, '00000000-0000-0000-0000-000000000000'::uuid) WITH =,
                    COALESCE(party_id, '00000000-0000-0000-0000-000000000000'::uuid) WITH =,
                    COALESCE(agreement_id, '00000000-0000-0000-0000-000000000000'::uuid) WITH =,
                    tstzrange(valid_from, valid_to, '[)') WITH &&
                );
            """,
            reverse_sql="""
                ALTER TABLE pricing_price
                DROP CONSTRAINT IF EXISTS price_no_overlapping_date_ranges;
            """,
        ),
        # Add index to support efficient constraint checking
        # The GIST index is created by the exclusion constraint, but we add
        # a B-tree index for common query patterns
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS price_scope_lookup_idx
                ON pricing_price (
                    catalog_item_id,
                    COALESCE(organization_id, '00000000-0000-0000-0000-000000000000'::uuid),
                    COALESCE(party_id, '00000000-0000-0000-0000-000000000000'::uuid),
                    COALESCE(agreement_id, '00000000-0000-0000-0000-000000000000'::uuid)
                );
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS price_scope_lookup_idx;
            """,
        ),
    ]
