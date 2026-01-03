"""Tests for terminal UI formatters."""

import pytest
from uuid import uuid4


class TestShortUUID:
    """Tests for UUID shortening helper."""

    def test_short_uuid_shortens_to_8_chars(self):
        """Short UUID returns first 8 characters."""
        from primitives_testbed.terminal_ui.formatters import short_uuid

        full_uuid = uuid4()
        result = short_uuid(full_uuid)

        assert len(result) == 8
        assert result == str(full_uuid)[:8]

    def test_short_uuid_handles_string(self):
        """Short UUID handles string input."""
        from primitives_testbed.terminal_ui.formatters import short_uuid

        uuid_str = "12345678-1234-1234-1234-123456789abc"
        result = short_uuid(uuid_str)

        assert result == "12345678"

    def test_short_uuid_handles_none(self):
        """Short UUID handles None input."""
        from primitives_testbed.terminal_ui.formatters import short_uuid

        result = short_uuid(None)

        assert result == "-"


class TestFormatPartiesTable:
    """Tests for parties table formatter."""

    def test_format_parties_table_returns_rich_table(self):
        """Format parties returns a Rich Table."""
        from rich.table import Table

        from primitives_testbed.terminal_ui.formatters import format_parties_table

        result = format_parties_table([])

        assert isinstance(result, Table)

    def test_format_parties_table_has_expected_columns(self):
        """Format parties table has ID, Type, Name columns."""
        from primitives_testbed.terminal_ui.formatters import format_parties_table

        result = format_parties_table([])

        column_names = [col.header for col in result.columns]
        assert "ID" in column_names
        assert "Type" in column_names
        assert "Name" in column_names

    @pytest.mark.django_db
    def test_format_parties_table_shows_person(self):
        """Format parties table shows Person records."""
        from django_parties.models import Person
        from rich.console import Console
        from io import StringIO

        from primitives_testbed.terminal_ui.formatters import format_parties_table

        person = Person.objects.create(first_name="John", last_name="Doe")
        result = format_parties_table([person])

        console = Console(file=StringIO(), force_terminal=True)
        console.print(result)
        output = console.file.getvalue()

        assert "John Doe" in output
        assert "Person" in output


class TestFormatEncountersTable:
    """Tests for encounters table formatter."""

    def test_format_encounters_table_returns_rich_table(self):
        """Format encounters returns a Rich Table."""
        from rich.table import Table

        from primitives_testbed.terminal_ui.formatters import format_encounters_table

        result = format_encounters_table([])

        assert isinstance(result, Table)

    def test_format_encounters_table_has_expected_columns(self):
        """Format encounters table has expected columns."""
        from primitives_testbed.terminal_ui.formatters import format_encounters_table

        result = format_encounters_table([])

        column_names = [col.header for col in result.columns]
        assert "ID" in column_names
        assert "State" in column_names


class TestFormatBasketsTable:
    """Tests for baskets table formatter."""

    def test_format_baskets_table_returns_rich_table(self):
        """Format baskets returns a Rich Table."""
        from rich.table import Table

        from primitives_testbed.terminal_ui.formatters import format_baskets_table

        result = format_baskets_table([])

        assert isinstance(result, Table)


class TestFormatInvoicesTable:
    """Tests for invoices table formatter."""

    def test_format_invoices_table_returns_rich_table(self):
        """Format invoices returns a Rich Table."""
        from rich.table import Table

        from primitives_testbed.terminal_ui.formatters import format_invoices_table

        result = format_invoices_table([])

        assert isinstance(result, Table)

    def test_format_invoices_table_has_expected_columns(self):
        """Format invoices table has expected columns."""
        from primitives_testbed.terminal_ui.formatters import format_invoices_table

        result = format_invoices_table([])

        column_names = [col.header for col in result.columns]
        assert "ID" in column_names
        assert "Status" in column_names
        assert "Total" in column_names


class TestFormatLedgerTable:
    """Tests for ledger transactions table formatter."""

    def test_format_ledger_table_returns_rich_table(self):
        """Format ledger returns a Rich Table."""
        from rich.table import Table

        from primitives_testbed.terminal_ui.formatters import format_ledger_table

        result = format_ledger_table([])

        assert isinstance(result, Table)


class TestFormatAgreementsTable:
    """Tests for agreements table formatter."""

    def test_format_agreements_table_returns_rich_table(self):
        """Format agreements returns a Rich Table."""
        from rich.table import Table

        from primitives_testbed.terminal_ui.formatters import format_agreements_table

        result = format_agreements_table([])

        assert isinstance(result, Table)


class TestFormatPartyDetail:
    """Tests for party detail panel formatter."""

    def test_format_party_detail_returns_panel(self):
        """Format party detail returns a Rich Panel."""
        from rich.panel import Panel
        from unittest.mock import MagicMock

        from primitives_testbed.terminal_ui.formatters import format_party_detail

        party = MagicMock()
        party.pk = "12345678-1234-1234-1234-123456789abc"
        party.__class__.__name__ = "Person"
        party.first_name = "John"
        party.last_name = "Doe"
        party.email = "john@example.com"
        party.created_at = None

        result = format_party_detail(party)

        assert isinstance(result, Panel)

    @pytest.mark.django_db
    def test_format_party_detail_shows_person_info(self):
        """Format party detail shows person information."""
        from django_parties.models import Person
        from rich.console import Console
        from io import StringIO

        from primitives_testbed.terminal_ui.formatters import format_party_detail

        person = Person.objects.create(first_name="Jane", last_name="Smith")
        result = format_party_detail(person)

        console = Console(file=StringIO(), force_terminal=True)
        console.print(result)
        output = console.file.getvalue()

        assert "Jane" in output
        assert "Smith" in output


class TestFormatInvoiceDetail:
    """Tests for invoice detail panel formatter."""

    def test_format_invoice_detail_returns_panel(self):
        """Format invoice detail returns a Rich Panel."""
        from rich.panel import Panel
        from unittest.mock import MagicMock

        from primitives_testbed.terminal_ui.formatters import format_invoice_detail

        invoice = MagicMock()
        invoice.pk = "12345678-1234-1234-1234-123456789abc"
        invoice.status = "draft"
        invoice.billed_to = None
        invoice.issued_by = None
        invoice.total_amount = "100.00"
        invoice.created_at = None
        invoice.line_items = MagicMock()
        invoice.line_items.all.return_value = []

        result = format_invoice_detail(invoice)

        assert isinstance(result, Panel)


class TestFormatBasketDetail:
    """Tests for basket detail panel formatter."""

    def test_format_basket_detail_returns_panel(self):
        """Format basket detail returns a Rich Panel."""
        from rich.panel import Panel
        from unittest.mock import MagicMock

        from primitives_testbed.terminal_ui.formatters import format_basket_detail

        basket = MagicMock()
        basket.pk = "12345678-1234-1234-1234-123456789abc"
        basket.status = "open"
        basket.created_at = None
        basket.items = MagicMock()
        basket.items.all.return_value = []

        result = format_basket_detail(basket)

        assert isinstance(result, Panel)
