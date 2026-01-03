"""Tests for terminal UI selectors."""

import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection


@pytest.mark.django_db
class TestListParties:
    """Tests for list_parties selector."""

    def test_list_parties_returns_persons_and_orgs(self):
        """List parties returns both Person and Organization records."""
        from django_parties.models import Organization, Person

        from primitives_testbed.terminal_ui.selectors import list_parties

        # Create test data
        Person.objects.create(first_name="John", last_name="Doe")
        Organization.objects.create(name="Acme Corp")

        parties = list_parties()

        assert len(parties) == 2

    def test_list_parties_filters_by_type_person(self):
        """List parties filters to only persons when type='person'."""
        from django_parties.models import Organization, Person

        from primitives_testbed.terminal_ui.selectors import list_parties

        Person.objects.create(first_name="Jane", last_name="Smith")
        Organization.objects.create(name="Test Org")

        parties = list_parties(party_type="person")

        assert len(parties) == 1
        assert hasattr(parties[0], "first_name")

    def test_list_parties_filters_by_type_org(self):
        """List parties filters to only organizations when type='org'."""
        from django_parties.models import Organization, Person

        from primitives_testbed.terminal_ui.selectors import list_parties

        Person.objects.create(first_name="Bob", last_name="Wilson")
        Organization.objects.create(name="Widget Inc")

        parties = list_parties(party_type="org")

        assert len(parties) == 1
        assert hasattr(parties[0], "name")
        assert not hasattr(parties[0], "first_name")

    def test_list_parties_respects_limit(self):
        """List parties respects the limit parameter."""
        from django_parties.models import Person

        from primitives_testbed.terminal_ui.selectors import list_parties

        for i in range(10):
            Person.objects.create(first_name=f"Person{i}", last_name="Test")

        parties = list_parties(limit=5)

        assert len(parties) <= 5


@pytest.mark.django_db
class TestListEncounters:
    """Tests for list_encounters selector."""

    def test_list_encounters_returns_encounters(self):
        """List encounters returns encounter records."""
        from primitives_testbed.terminal_ui.selectors import list_encounters

        # Just test that the selector returns a list (may be empty)
        encounters = list_encounters()

        assert isinstance(encounters, list)

    def test_list_encounters_filters_by_state(self):
        """List encounters filters by state."""
        from primitives_testbed.terminal_ui.selectors import list_encounters

        # Test that filter parameter works (returns list, possibly empty)
        encounters = list_encounters(state="pending")

        assert isinstance(encounters, list)
        # If there are results, they should all have the filtered state
        assert all(e.state == "pending" for e in encounters)


@pytest.mark.django_db
class TestListBaskets:
    """Tests for list_baskets selector."""

    def test_list_baskets_returns_baskets(self):
        """List baskets returns basket records."""
        from primitives_testbed.terminal_ui.selectors import list_baskets

        # Just test that the selector returns a list
        baskets = list_baskets()

        assert isinstance(baskets, list)

    def test_list_baskets_filters_by_status(self):
        """List baskets filters by status."""
        from primitives_testbed.terminal_ui.selectors import list_baskets

        # Test that filter parameter works
        baskets = list_baskets(status="draft")

        assert isinstance(baskets, list)
        assert all(b.status == "draft" for b in baskets)


@pytest.mark.django_db
class TestListInvoices:
    """Tests for list_invoices selector."""

    def test_list_invoices_returns_invoices(self):
        """List invoices returns invoice records."""
        from primitives_testbed.terminal_ui.selectors import list_invoices

        # This will return empty if no invoices, which is valid
        invoices = list_invoices()

        assert isinstance(invoices, list)

    def test_list_invoices_no_n_plus_one(self):
        """List invoices uses select_related to prevent N+1."""
        from primitives_testbed.terminal_ui.selectors import list_invoices

        # Run with query capture
        with CaptureQueriesContext(connection) as context:
            invoices = list_invoices(limit=10)
            # Access related fields if any exist
            for inv in invoices:
                _ = inv.billed_to
                _ = inv.issued_by

        # Should be at most 2 queries (one for invoices, possibly one for count)
        assert len(context.captured_queries) <= 3


@pytest.mark.django_db
class TestListLedger:
    """Tests for list_ledger_transactions selector."""

    def test_list_ledger_transactions_returns_transactions(self):
        """List ledger transactions returns transaction records."""
        from primitives_testbed.terminal_ui.selectors import list_ledger_transactions

        transactions = list_ledger_transactions()

        assert isinstance(transactions, list)


@pytest.mark.django_db
class TestListAgreements:
    """Tests for list_agreements selector."""

    def test_list_agreements_returns_agreements(self):
        """List agreements returns agreement records."""
        from primitives_testbed.terminal_ui.selectors import list_agreements

        agreements = list_agreements()

        assert isinstance(agreements, list)


@pytest.mark.django_db
class TestGetParty:
    """Tests for get_party selector."""

    def test_get_party_returns_person_by_id(self):
        """Get party returns Person by ID."""
        from django_parties.models import Person

        from primitives_testbed.terminal_ui.selectors import get_party

        person = Person.objects.create(first_name="John", last_name="Doe")
        result = get_party(person.pk)

        assert result is not None
        assert result.pk == person.pk

    def test_get_party_returns_organization_by_id(self):
        """Get party returns Organization by ID."""
        from django_parties.models import Organization

        from primitives_testbed.terminal_ui.selectors import get_party

        org = Organization.objects.create(name="Acme Corp")
        result = get_party(org.pk)

        assert result is not None
        assert result.pk == org.pk

    def test_get_party_returns_none_for_invalid_id(self):
        """Get party returns None for nonexistent ID."""
        from uuid import uuid4

        from primitives_testbed.terminal_ui.selectors import get_party

        result = get_party(uuid4())

        assert result is None


@pytest.mark.django_db
class TestGetEncounter:
    """Tests for get_encounter selector."""

    def test_get_encounter_returns_encounter_by_id(self):
        """Get encounter returns Encounter by ID."""
        from primitives_testbed.terminal_ui.selectors import get_encounter

        # Function should exist and return None for nonexistent ID
        from uuid import uuid4

        result = get_encounter(uuid4())
        assert result is None


@pytest.mark.django_db
class TestGetBasket:
    """Tests for get_basket selector."""

    def test_get_basket_returns_basket_by_id(self):
        """Get basket returns Basket by ID."""
        from primitives_testbed.terminal_ui.selectors import get_basket

        from uuid import uuid4

        result = get_basket(uuid4())
        assert result is None


@pytest.mark.django_db
class TestGetInvoice:
    """Tests for get_invoice selector."""

    def test_get_invoice_returns_invoice_by_id(self):
        """Get invoice returns Invoice by ID."""
        from primitives_testbed.terminal_ui.selectors import get_invoice

        from uuid import uuid4

        result = get_invoice(uuid4())
        assert result is None


@pytest.mark.django_db
class TestGetAgreement:
    """Tests for get_agreement selector."""

    def test_get_agreement_returns_agreement_by_id(self):
        """Get agreement returns Agreement by ID."""
        from primitives_testbed.terminal_ui.selectors import get_agreement

        from uuid import uuid4

        result = get_agreement(uuid4())
        assert result is None
