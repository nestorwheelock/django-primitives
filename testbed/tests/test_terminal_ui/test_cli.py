"""Tests for primitivesctl CLI commands."""

import pytest
from click.testing import CliRunner
from django.core.management import call_command
from io import StringIO


class TestPrimitivesctlManagementCommand:
    """Tests for the Django management command entry point."""

    def test_primitivesctl_help_shows_usage(self, capsys):
        """Management command shows help text when called with --help."""
        try:
            call_command("primitivesctl", "--help")
        except SystemExit as e:
            # --help causes SystemExit(0), which is expected
            assert e.code == 0

        captured = capsys.readouterr()
        assert "primitivesctl" in captured.out.lower() or "usage" in captured.out.lower()

    def test_primitivesctl_is_discoverable(self):
        """Management command is registered and callable."""
        from django.core.management import get_commands

        commands = get_commands()
        assert "primitivesctl" in commands


class TestCliCommandGroup:
    """Tests for the Click CLI command groups."""

    def test_cli_has_list_command(self):
        """CLI has a list command group."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_list_parties_command_exists(self):
        """List parties command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "parties", "--help"])

        assert result.exit_code == 0
        assert "--limit" in result.output

    def test_list_encounters_command_exists(self):
        """List encounters command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "encounters", "--help"])

        assert result.exit_code == 0
        assert "--state" in result.output

    def test_list_baskets_command_exists(self):
        """List baskets command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "baskets", "--help"])

        assert result.exit_code == 0
        assert "--status" in result.output

    def test_list_invoices_command_exists(self):
        """List invoices command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "invoices", "--help"])

        assert result.exit_code == 0
        assert "--status" in result.output

    def test_list_ledger_command_exists(self):
        """List ledger command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "ledger", "--help"])

        assert result.exit_code == 0

    def test_list_agreements_command_exists(self):
        """List agreements command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "agreements", "--help"])

        assert result.exit_code == 0

    def test_cli_has_show_command(self):
        """CLI has a show command group."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["show", "--help"])

        assert result.exit_code == 0

    def test_cli_has_workflow_command(self):
        """CLI has a workflow command group."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["workflow", "--help"])

        assert result.exit_code == 0

    def test_cli_has_seed_command(self):
        """CLI has a seed command."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["seed", "--help"])

        assert result.exit_code == 0

    def test_cli_has_verify_command(self):
        """CLI has a verify command."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["verify", "--help"])

        assert result.exit_code == 0

    def test_show_party_command_exists(self):
        """Show party command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["show", "party", "--help"])

        assert result.exit_code == 0

    def test_show_encounter_command_exists(self):
        """Show encounter command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["show", "encounter", "--help"])

        assert result.exit_code == 0

    def test_show_basket_command_exists(self):
        """Show basket command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["show", "basket", "--help"])

        assert result.exit_code == 0

    def test_show_invoice_command_exists(self):
        """Show invoice command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["show", "invoice", "--help"])

        assert result.exit_code == 0

    def test_show_agreement_command_exists(self):
        """Show agreement command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["show", "agreement", "--help"])

        assert result.exit_code == 0


@pytest.mark.django_db
class TestShowCommands:
    """Tests for show command execution."""

    def test_show_party_displays_person(self):
        """Show party command displays person details."""
        from django_parties.models import Person

        from primitives_testbed.terminal_ui.cli import cli

        person = Person.objects.create(first_name="Test", last_name="User")

        runner = CliRunner()
        result = runner.invoke(cli, ["show", "party", str(person.pk)])

        assert result.exit_code == 0
        assert "Test" in result.output

    def test_show_party_invalid_id_shows_error(self):
        """Show party with invalid ID shows error."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["show", "party", "12345678-1234-1234-1234-123456789abc"])

        assert "not found" in result.output.lower()


class TestInvoicePrintCommand:
    """Tests for invoice print command."""

    def test_invoice_print_command_exists(self):
        """Invoice print command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["invoice", "--help"])

        assert result.exit_code == 0
        assert "print" in result.output.lower()

    def test_invoice_print_help_shows_format_option(self):
        """Invoice print help shows format option."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["invoice", "print", "--help"])

        assert result.exit_code == 0
        assert "--format" in result.output

    @pytest.mark.django_db
    def test_invoice_print_invalid_id_shows_error(self):
        """Invoice print with invalid ID shows error."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["invoice", "print", "12345678-1234-1234-1234-123456789abc"])

        assert "not found" in result.output.lower()
