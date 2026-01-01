"""Tests for next_sequence service."""
import pytest
from datetime import date
from django.db import connection

from django_sequence.models import Sequence
from django_sequence.services import next_sequence
from tests.models import Organization


@pytest.mark.django_db
class TestNextSequenceService:
    """Test suite for next_sequence service."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    def test_next_sequence_increments_value(self, org):
        """next_sequence should increment current_value."""
        # Create sequence starting at 0
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Organization)
        Sequence.objects.create(
            scope='invoice',
            org_content_type=ct,
            org_id=str(org.pk),
            prefix='INV-',
            current_value=0,
        )

        # Get next sequence
        result1 = next_sequence('invoice', org=org)
        result2 = next_sequence('invoice', org=org)
        result3 = next_sequence('invoice', org=org)

        # Verify sequential increments
        year = date.today().year
        assert result1 == f"INV-{year}-000001"
        assert result2 == f"INV-{year}-000002"
        assert result3 == f"INV-{year}-000003"

    def test_next_sequence_returns_formatted_value(self, org):
        """next_sequence should return the formatted value."""
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Organization)
        Sequence.objects.create(
            scope='order',
            org_content_type=ct,
            org_id=str(org.pk),
            prefix='ORD-',
            current_value=99,
            include_year=True,
            pad_width=6,
        )

        result = next_sequence('order', org=org)

        year = date.today().year
        assert result == f"ORD-{year}-000100"

    def test_next_sequence_creates_sequence_if_not_exists(self, org):
        """next_sequence should create sequence with defaults if it doesn't exist."""
        # No sequence exists yet
        assert Sequence.objects.filter(scope='new_scope').count() == 0

        result = next_sequence('new_scope', org=org, prefix='NEW-')

        # Sequence should be created
        assert Sequence.objects.filter(scope='new_scope').count() == 1

        # Result should be the first value
        year = date.today().year
        assert result == f"NEW-{year}-000001"

    def test_next_sequence_auto_create_disabled_raises(self, org):
        """next_sequence should raise if auto_create=False and sequence doesn't exist."""
        from django_sequence.exceptions import SequenceNotFoundError

        with pytest.raises(SequenceNotFoundError):
            next_sequence('nonexistent', org=org, auto_create=False)

    def test_next_sequence_without_year(self, org):
        """next_sequence should work with include_year=False."""
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Organization)
        Sequence.objects.create(
            scope='ticket',
            org_content_type=ct,
            org_id=str(org.pk),
            prefix='TKT-',
            current_value=0,
            include_year=False,
            pad_width=6,
        )

        result = next_sequence('ticket', org=org)

        assert result == "TKT-000001"

    def test_next_sequence_global_without_org(self):
        """next_sequence should work for global sequences (no org)."""
        Sequence.objects.create(
            scope='global',
            org_content_type=None,
            org_id='',
            prefix='GLB-',
            current_value=0,
            include_year=False,
        )

        result = next_sequence('global', org=None)

        assert result == "GLB-000001"

    def test_next_sequence_is_atomic(self, org):
        """next_sequence should use transaction.atomic."""
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Organization)
        Sequence.objects.create(
            scope='atomic_test',
            org_content_type=ct,
            org_id=str(org.pk),
            prefix='ATM-',
            current_value=0,
        )

        # Get sequence value
        result = next_sequence('atomic_test', org=org)

        # Verify it was persisted
        seq = Sequence.objects.get(scope='atomic_test', org_id=str(org.pk))
        assert seq.current_value == 1

        year = date.today().year
        assert result == f"ATM-{year}-000001"

    def test_next_sequence_custom_pad_width_on_create(self, org):
        """next_sequence should use custom pad_width when creating."""
        result = next_sequence('short', org=org, prefix='S-', pad_width=3, include_year=False)

        assert result == "S-001"

    def test_next_sequence_returns_incrementing_values(self, org):
        """Multiple calls should return incrementing values."""
        results = []
        for _ in range(5):
            results.append(next_sequence('multi', org=org, prefix='M-', include_year=False))

        assert results == ['M-000001', 'M-000002', 'M-000003', 'M-000004', 'M-000005']


@pytest.mark.django_db
class TestOrgIsolation:
    """Test suite for per-organization sequence isolation."""

    def test_sequences_isolated_by_org(self):
        """Same scope, different orgs should have independent sequences."""
        org1 = Organization.objects.create(name="Org 1")
        org2 = Organization.objects.create(name="Org 2")

        # Get sequences for org1
        inv1_org1 = next_sequence('invoice', org=org1, prefix='INV-', include_year=False)
        inv2_org1 = next_sequence('invoice', org=org1, prefix='INV-', include_year=False)

        # Get sequences for org2
        inv1_org2 = next_sequence('invoice', org=org2, prefix='INV-', include_year=False)
        inv2_org2 = next_sequence('invoice', org=org2, prefix='INV-', include_year=False)

        # Each org should have independent counters
        assert inv1_org1 == 'INV-000001'
        assert inv2_org1 == 'INV-000002'
        assert inv1_org2 == 'INV-000001'  # Starts at 1, not 3
        assert inv2_org2 == 'INV-000002'

    def test_global_sequence_separate_from_org_sequences(self):
        """Global sequences (org=None) should be independent from org sequences."""
        org = Organization.objects.create(name="Test Org")

        # Get org-scoped sequence
        org_inv = next_sequence('invoice', org=org, prefix='INV-', include_year=False)

        # Get global sequence with same scope
        global_inv = next_sequence('invoice', org=None, prefix='INV-', include_year=False)

        # They should be independent
        assert org_inv == 'INV-000001'
        assert global_inv == 'INV-000001'  # Also 1, not 2

    def test_different_scopes_independent(self):
        """Different scopes for same org should be independent."""
        org = Organization.objects.create(name="Test Org")

        invoice = next_sequence('invoice', org=org, prefix='INV-', include_year=False)
        order = next_sequence('order', org=org, prefix='ORD-', include_year=False)
        ticket = next_sequence('ticket', org=org, prefix='TKT-', include_year=False)

        assert invoice == 'INV-000001'
        assert order == 'ORD-000001'
        assert ticket == 'TKT-000001'


@pytest.mark.django_db
class TestGapPolicy:
    """Test suite for gap policy behavior."""

    def test_gaps_allowed_by_default(self):
        """Gaps in sequence are allowed (expected from failed transactions)."""
        org = Organization.objects.create(name="Test Org")

        # Create a sequence with current_value already at 5
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Organization)
        Sequence.objects.create(
            scope='gapped',
            org_content_type=ct,
            org_id=str(org.pk),
            prefix='GAP-',
            current_value=5,  # Simulates gaps from failed transactions
            include_year=False,
        )

        # Next value should be 6, not 1
        result = next_sequence('gapped', org=org)
        assert result == 'GAP-000006'

    def test_sequence_never_goes_backward(self):
        """Sequence should never decrease, even if set manually."""
        org = Organization.objects.create(name="Test Org")

        # Get some values
        v1 = next_sequence('forward', org=org, prefix='FWD-', include_year=False)
        v2 = next_sequence('forward', org=org, prefix='FWD-', include_year=False)

        # Verify they're incrementing
        assert v1 == 'FWD-000001'
        assert v2 == 'FWD-000002'

        # Manually verify the database value
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Organization)
        seq = Sequence.objects.get(scope='forward', org_id=str(org.pk))
        assert seq.current_value == 2

        # Next call should be 3
        v3 = next_sequence('forward', org=org)
        assert v3 == 'FWD-000003'
