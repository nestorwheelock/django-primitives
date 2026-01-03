"""Tests for terminal UI workflows and seed commands."""

import pytest
from click.testing import CliRunner


@pytest.mark.django_db
class TestSeedCommand:
    """Tests for seed command."""

    def test_seed_command_runs_without_error(self):
        """Seed command runs without error."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["seed"])

        assert result.exit_code == 0

    def test_seed_command_shows_progress(self):
        """Seed command shows progress output."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["seed"])

        assert "seed" in result.output.lower() or "created" in result.output.lower()


@pytest.mark.django_db
class TestSeedCreatesData:
    """Tests for seed command data creation."""

    def test_seed_creates_parties(self):
        """Seed creates Person and Organization records."""
        from django_parties.models import Organization, Person

        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["seed"])

        assert result.exit_code == 0
        assert Person.objects.count() > 0 or Organization.objects.count() > 0


@pytest.mark.django_db
class TestVerifyCommand:
    """Tests for verify command."""

    def test_verify_command_runs_without_error(self):
        """Verify command runs without error."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["verify"])

        assert result.exit_code == 0

    def test_verify_command_shows_results(self):
        """Verify command shows verification results."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["verify"])

        assert "verif" in result.output.lower() or "check" in result.output.lower()


class TestBasketToInvoiceWorkflow:
    """Tests for basket-to-invoice workflow command."""

    def test_workflow_basket_to_invoice_command_exists(self):
        """Workflow basket-to-invoice command exists."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["workflow", "basket-to-invoice", "--help"])

        assert result.exit_code == 0

    @pytest.mark.django_db
    def test_workflow_basket_to_invoice_invalid_id_shows_error(self):
        """Workflow with invalid basket ID shows error."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["workflow", "basket-to-invoice", "12345678-1234-1234-1234-123456789abc"])

        assert "not found" in result.output.lower() or "error" in result.output.lower()
