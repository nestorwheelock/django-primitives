"""Integration tests for terminal UI end-to-end flows."""

import pytest
from click.testing import CliRunner


@pytest.mark.django_db
class TestSeedThenListFlow:
    """Test seed then list entities flow."""

    def test_seed_then_list_parties_shows_seeded_data(self):
        """Seed command populates data that list shows."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()

        result = runner.invoke(cli, ["seed"])
        assert result.exit_code == 0

        result = runner.invoke(cli, ["list", "parties"])
        assert result.exit_code == 0
        assert "Alice" in result.output or "Bob" in result.output or "Acme" in result.output


@pytest.mark.django_db
class TestListThenShowFlow:
    """Test list then show entity flow."""

    def test_list_parties_then_show_party_works(self):
        """Can list parties then show individual party details."""
        from django_parties.models import Person

        from primitives_testbed.terminal_ui.cli import cli

        person = Person.objects.create(first_name="Integration", last_name="Test")

        runner = CliRunner()

        result = runner.invoke(cli, ["list", "parties"])
        assert result.exit_code == 0
        assert str(person.pk)[:8] in result.output

        result = runner.invoke(cli, ["show", "party", str(person.pk)])
        assert result.exit_code == 0
        assert "Integration" in result.output
        assert "Test" in result.output


@pytest.mark.django_db
class TestVerifyAfterSeedFlow:
    """Test verify after seed flow."""

    def test_verify_after_seed_passes(self):
        """Verify command shows counts after seeding."""
        from primitives_testbed.terminal_ui.cli import cli

        runner = CliRunner()

        runner.invoke(cli, ["seed"])

        result = runner.invoke(cli, ["verify"])
        assert result.exit_code == 0
        assert "check" in result.output.lower()
        assert "passed" in result.output.lower() or "complete" in result.output.lower()
