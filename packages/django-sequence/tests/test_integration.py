"""Integration tests for django-sequence."""
import pytest
from datetime import date

from django_sequence.models import Sequence
from django_sequence.services import next_sequence
from tests.models import Organization


@pytest.mark.django_db
class TestRealWorldUsage:
    """Integration tests simulating real-world usage patterns."""

    def test_invoice_numbering_workflow(self):
        """Test complete invoice numbering workflow."""
        org = Organization.objects.create(name="Acme Corp")

        # Create first invoice
        inv1 = next_sequence('invoice', org=org, prefix='INV-')

        # Create more invoices
        inv2 = next_sequence('invoice', org=org)
        inv3 = next_sequence('invoice', org=org)

        # Verify sequential numbering
        year = date.today().year
        assert inv1 == f"INV-{year}-000001"
        assert inv2 == f"INV-{year}-000002"
        assert inv3 == f"INV-{year}-000003"

    def test_multi_tenant_invoice_isolation(self):
        """Test that each organization has independent invoice numbers."""
        acme = Organization.objects.create(name="Acme Corp")
        globex = Organization.objects.create(name="Globex Corp")

        # Acme creates 5 invoices
        acme_invoices = [
            next_sequence('invoice', org=acme, prefix='INV-', include_year=False)
            for _ in range(5)
        ]

        # Globex creates 3 invoices
        globex_invoices = [
            next_sequence('invoice', org=globex, prefix='INV-', include_year=False)
            for _ in range(3)
        ]

        # Verify isolation
        assert acme_invoices == ['INV-000001', 'INV-000002', 'INV-000003', 'INV-000004', 'INV-000005']
        assert globex_invoices == ['INV-000001', 'INV-000002', 'INV-000003']

        # More Acme invoices continue from 5
        acme_inv6 = next_sequence('invoice', org=acme, include_year=False)
        assert acme_inv6 == 'INV-000006'

    def test_multiple_sequence_types_per_org(self):
        """Test that org can have multiple independent sequence types."""
        org = Organization.objects.create(name="Test Org")

        # Create different document types
        invoice = next_sequence('invoice', org=org, prefix='INV-', include_year=False)
        order = next_sequence('order', org=org, prefix='ORD-', include_year=False)
        ticket = next_sequence('ticket', org=org, prefix='TKT-', include_year=False, pad_width=4)

        # Each starts at 1
        assert invoice == 'INV-000001'
        assert order == 'ORD-000001'
        assert ticket == 'TKT-0001'

        # Get more of each
        invoice2 = next_sequence('invoice', org=org)
        order2 = next_sequence('order', org=org)

        assert invoice2 == 'INV-000002'
        assert order2 == 'ORD-000002'

    def test_predefined_sequence_configuration(self):
        """Test using predefined sequence with custom settings."""
        org = Organization.objects.create(name="Test Org")

        # Admin pre-configures sequence with specific settings
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Organization)
        Sequence.objects.create(
            scope='purchase_order',
            org_content_type=ct,
            org_id=str(org.pk),
            prefix='PO-',
            current_value=1000,  # Start at 1000
            pad_width=8,
            include_year=True,
        )

        # Application uses the predefined sequence
        po1 = next_sequence('purchase_order', org=org)
        po2 = next_sequence('purchase_order', org=org)

        year = date.today().year
        assert po1 == f"PO-{year}-00001001"
        assert po2 == f"PO-{year}-00001002"

    def test_year_rollover_behavior(self):
        """Test sequence behavior across year boundaries."""
        org = Organization.objects.create(name="Test Org")

        # Get a sequence
        inv = next_sequence('yearly', org=org, prefix='YR-')

        # Verify year is included
        current_year = date.today().year
        assert str(current_year) in inv

        # Note: Actual year rollover would require mocking date.today()
        # This test just verifies year is included in current format

    def test_sequence_for_django_model_integration(self):
        """Test how sequences would be used in a Django model."""
        org = Organization.objects.create(name="Test Org")

        # Simulate what would happen in a model's save() method
        class MockInvoice:
            def __init__(self, org):
                self.org = org
                self.number = None

            def save(self):
                if not self.number:
                    self.number = next_sequence('invoice', org=self.org, prefix='INV-')

        # Create invoices
        inv1 = MockInvoice(org)
        inv1.save()

        inv2 = MockInvoice(org)
        inv2.save()

        year = date.today().year
        assert inv1.number == f"INV-{year}-000001"
        assert inv2.number == f"INV-{year}-000002"

    def test_global_sequence_for_system_wide_numbering(self):
        """Test global sequences (no org) for system-wide numbering."""
        # Global ticket counter for support system
        ticket1 = next_sequence('support_ticket', org=None, prefix='SUPP-', include_year=False)
        ticket2 = next_sequence('support_ticket', org=None, prefix='SUPP-', include_year=False)

        assert ticket1 == 'SUPP-000001'
        assert ticket2 == 'SUPP-000002'

        # Different orgs can still use the same global sequence
        org1 = Organization.objects.create(name="Org 1")
        org2 = Organization.objects.create(name="Org 2")

        # But if they need their own, they get independent sequences
        org1_ticket = next_sequence('org_ticket', org=org1, prefix='TKT-', include_year=False)
        org2_ticket = next_sequence('org_ticket', org=org2, prefix='TKT-', include_year=False)

        assert org1_ticket == 'TKT-000001'
        assert org2_ticket == 'TKT-000001'  # Independent


@pytest.mark.django_db
class TestConcurrencySafety:
    """
    Tests for concurrency safety.

    Note: True concurrency testing requires PostgreSQL since SQLite
    treats select_for_update() as a no-op. These tests verify the
    code structure is correct for production use.
    """

    def test_service_uses_atomic_transaction(self):
        """Verify next_sequence uses transaction.atomic."""
        import inspect
        from django_sequence.services import next_sequence

        source = inspect.getsource(next_sequence)
        assert 'transaction.atomic' in source

    def test_service_uses_select_for_update(self):
        """Verify next_sequence uses select_for_update for locking."""
        import inspect
        from django_sequence.services import next_sequence

        source = inspect.getsource(next_sequence)
        assert 'select_for_update' in source

    def test_sequence_increment_is_persistent(self):
        """Verify that sequence increments are immediately persisted."""
        org = Organization.objects.create(name="Test Org")

        # Get first sequence
        result1 = next_sequence('persistent', org=org, prefix='P-', include_year=False)

        # Verify in database
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Organization)
        seq = Sequence.objects.get(scope='persistent', org_id=str(org.pk))
        assert seq.current_value == 1

        # Get second sequence
        result2 = next_sequence('persistent', org=org)

        # Verify updated in database
        seq.refresh_from_db()
        assert seq.current_value == 2

        assert result1 == 'P-000001'
        assert result2 == 'P-000002'
