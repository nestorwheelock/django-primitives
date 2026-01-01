"""Tests for Sequence model."""
import pytest
from datetime import date
from django.db import IntegrityError

from django_sequence.models import Sequence
from tests.models import Organization


@pytest.mark.django_db
class TestSequenceModel:
    """Test suite for Sequence model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    def test_sequence_has_scope_field(self, org):
        """Sequence should have a scope field."""
        seq = Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=0,
        )
        assert seq.scope == 'invoice'

    def test_sequence_has_org_field(self, org):
        """Sequence should have an org ForeignKey field."""
        seq = Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=0,
        )
        assert seq.org == org

    def test_sequence_org_nullable_for_global(self):
        """Sequence org can be null for global sequences."""
        seq = Sequence.objects.create(
            scope='global_counter',
            org=None,
            prefix='GLB-',
            current_value=0,
        )
        assert seq.org is None

    def test_sequence_has_prefix_field(self, org):
        """Sequence should have a prefix field."""
        seq = Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=0,
        )
        assert seq.prefix == 'INV-'

    def test_sequence_has_current_value_field(self, org):
        """Sequence should have a current_value field."""
        seq = Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=100,
        )
        assert seq.current_value == 100

    def test_sequence_has_pad_width_field(self, org):
        """Sequence should have a pad_width field with default."""
        seq = Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=0,
        )
        assert seq.pad_width == 6  # Default

    def test_sequence_custom_pad_width(self, org):
        """Sequence pad_width can be customized."""
        seq = Sequence.objects.create(
            scope='ticket',
            org=org,
            prefix='TKT-',
            current_value=0,
            pad_width=4,
        )
        assert seq.pad_width == 4

    def test_sequence_has_include_year_field(self, org):
        """Sequence should have include_year field with default True."""
        seq = Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=0,
        )
        assert seq.include_year is True

    def test_sequence_include_year_can_be_false(self, org):
        """Sequence include_year can be set to False."""
        seq = Sequence.objects.create(
            scope='ticket',
            org=org,
            prefix='TKT-',
            current_value=0,
            include_year=False,
        )
        assert seq.include_year is False

    def test_sequence_unique_scope_org(self, org):
        """Scope + org combination should be unique."""
        Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=0,
        )

        with pytest.raises(IntegrityError):
            Sequence.objects.create(
                scope='invoice',
                org=org,
                prefix='INV-',
                current_value=0,
            )

    def test_sequence_same_scope_different_orgs_allowed(self):
        """Same scope with different orgs should be allowed."""
        org1 = Organization.objects.create(name="Org 1")
        org2 = Organization.objects.create(name="Org 2")

        seq1 = Sequence.objects.create(
            scope='invoice',
            org=org1,
            prefix='INV-',
            current_value=0,
        )
        seq2 = Sequence.objects.create(
            scope='invoice',
            org=org2,
            prefix='INV-',
            current_value=0,
        )

        assert seq1.pk != seq2.pk

    def test_formatted_value_with_year(self, org):
        """formatted_value should include year when include_year is True."""
        seq = Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=123,
            include_year=True,
            pad_width=6,
        )
        current_year = date.today().year

        formatted = seq.formatted_value
        assert formatted == f"INV-{current_year}-000123"

    def test_formatted_value_without_year(self, org):
        """formatted_value should exclude year when include_year is False."""
        seq = Sequence.objects.create(
            scope='ticket',
            org=org,
            prefix='TKT-',
            current_value=42,
            include_year=False,
            pad_width=6,
        )

        formatted = seq.formatted_value
        assert formatted == "TKT-000042"

    def test_formatted_value_respects_pad_width(self, org):
        """formatted_value should respect custom pad_width."""
        seq = Sequence.objects.create(
            scope='order',
            org=org,
            prefix='ORD-',
            current_value=7,
            include_year=False,
            pad_width=4,
        )

        formatted = seq.formatted_value
        assert formatted == "ORD-0007"

    def test_formatted_value_large_number_exceeds_padding(self, org):
        """Large numbers should still work even if they exceed pad_width."""
        seq = Sequence.objects.create(
            scope='counter',
            org=org,
            prefix='CNT-',
            current_value=1234567,
            include_year=False,
            pad_width=4,
        )

        formatted = seq.formatted_value
        # Number exceeds pad width, should still show full number
        assert formatted == "CNT-1234567"

    def test_sequence_str_representation(self, org):
        """Sequence __str__ should be useful."""
        seq = Sequence.objects.create(
            scope='invoice',
            org=org,
            prefix='INV-',
            current_value=100,
        )

        str_repr = str(seq)
        assert 'invoice' in str_repr
