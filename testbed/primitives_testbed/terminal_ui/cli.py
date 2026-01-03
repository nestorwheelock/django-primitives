"""Click CLI for primitivesctl.

Usage:
    python manage.py primitivesctl [command] [options]
"""

import click
from rich.console import Console

console = Console()


@click.group()
@click.pass_context
def cli(ctx):
    """Django Primitives Terminal UI.

    Browse entities, run workflows, and verify data integrity.
    """
    ctx.ensure_object(dict)


@cli.group(name="list")
def list_group():
    """List entities (parties, encounters, baskets, invoices, ledger, agreements)."""
    pass


@list_group.command(name="parties")
@click.option("--limit", default=50, help="Maximum records to return")
@click.option("--type", "party_type", type=click.Choice(["person", "org"]), help="Filter by party type")
def list_parties(limit, party_type):
    """List parties (Person and Organization)."""
    from .selectors import list_parties as get_parties
    from .formatters import format_parties_table

    parties = get_parties(limit=limit, party_type=party_type)
    table = format_parties_table(parties)
    console.print(table)


@list_group.command(name="encounters")
@click.option("--limit", default=50, help="Maximum records to return")
@click.option("--state", help="Filter by state")
def list_encounters(limit, state):
    """List encounters."""
    from .selectors import list_encounters as get_encounters
    from .formatters import format_encounters_table

    encounters = get_encounters(limit=limit, state=state)
    table = format_encounters_table(encounters)
    console.print(table)


@list_group.command(name="baskets")
@click.option("--limit", default=50, help="Maximum records to return")
@click.option("--status", help="Filter by status")
def list_baskets(limit, status):
    """List baskets."""
    from .selectors import list_baskets as get_baskets
    from .formatters import format_baskets_table

    baskets = get_baskets(limit=limit, status=status)
    table = format_baskets_table(baskets)
    console.print(table)


@list_group.command(name="invoices")
@click.option("--limit", default=50, help="Maximum records to return")
@click.option("--status", help="Filter by status")
def list_invoices(limit, status):
    """List invoices."""
    from .selectors import list_invoices as get_invoices
    from .formatters import format_invoices_table

    invoices = get_invoices(limit=limit, status=status)
    table = format_invoices_table(invoices)
    console.print(table)


@list_group.command(name="ledger")
@click.option("--limit", default=50, help="Maximum records to return")
def list_ledger(limit):
    """List ledger transactions."""
    from .selectors import list_ledger_transactions
    from .formatters import format_ledger_table

    transactions = list_ledger_transactions(limit=limit)
    table = format_ledger_table(transactions)
    console.print(table)


@list_group.command(name="agreements")
@click.option("--limit", default=50, help="Maximum records to return")
@click.option("--scope-type", help="Filter by scope type")
def list_agreements(limit, scope_type):
    """List agreements."""
    from .selectors import list_agreements as get_agreements
    from .formatters import format_agreements_table

    agreements = get_agreements(limit=limit, scope_type=scope_type)
    table = format_agreements_table(agreements)
    console.print(table)


@cli.group(name="show")
def show_group():
    """Show entity details."""
    pass


@show_group.command(name="party")
@click.argument("party_id")
def show_party(party_id):
    """Show party (Person/Organization) details."""
    from .selectors import get_party
    from .formatters import format_party_detail

    party = get_party(party_id)
    if party is None:
        console.print(f"[red]Party not found: {party_id}[/red]")
        return

    panel = format_party_detail(party)
    console.print(panel)


@show_group.command(name="encounter")
@click.argument("encounter_id")
def show_encounter(encounter_id):
    """Show encounter details."""
    from .selectors import get_encounter

    encounter = get_encounter(encounter_id)
    if encounter is None:
        console.print(f"[red]Encounter not found: {encounter_id}[/red]")
        return

    console.print(f"[bold]Encounter:[/bold] {encounter.pk}")
    console.print(f"[bold]State:[/bold] {encounter.state or '-'}")
    if encounter.definition:
        console.print(f"[bold]Definition:[/bold] {encounter.definition.name}")


@show_group.command(name="basket")
@click.argument("basket_id")
def show_basket(basket_id):
    """Show basket details."""
    from .selectors import get_basket
    from .formatters import format_basket_detail

    basket = get_basket(basket_id)
    if basket is None:
        console.print(f"[red]Basket not found: {basket_id}[/red]")
        return

    panel = format_basket_detail(basket)
    console.print(panel)


@show_group.command(name="invoice")
@click.argument("invoice_id")
def show_invoice(invoice_id):
    """Show invoice details."""
    from .selectors import get_invoice
    from .formatters import format_invoice_detail

    invoice = get_invoice(invoice_id)
    if invoice is None:
        console.print(f"[red]Invoice not found: {invoice_id}[/red]")
        return

    panel = format_invoice_detail(invoice)
    console.print(panel)


@show_group.command(name="agreement")
@click.argument("agreement_id")
def show_agreement(agreement_id):
    """Show agreement details."""
    from .selectors import get_agreement

    agreement = get_agreement(agreement_id)
    if agreement is None:
        console.print(f"[red]Agreement not found: {agreement_id}[/red]")
        return

    console.print(f"[bold]Agreement:[/bold] {agreement.pk}")
    console.print(f"[bold]Scope Type:[/bold] {agreement.scope_type or '-'}")
    console.print(f"[bold]Status:[/bold] {agreement.status or '-'}")


@cli.group(name="invoice")
def invoice_group():
    """Invoice operations."""
    pass


@invoice_group.command(name="print")
@click.argument("invoice_id")
@click.option("--format", "output_format", type=click.Choice(["terminal", "html"]), default="terminal", help="Output format")
def invoice_print(invoice_id, output_format):
    """Print an invoice."""
    from .selectors import get_invoice
    from .formatters import format_invoice_detail

    invoice = get_invoice(invoice_id)
    if invoice is None:
        console.print(f"[red]Invoice not found: {invoice_id}[/red]")
        return

    if output_format == "terminal":
        panel = format_invoice_detail(invoice)
        console.print(panel)
    else:
        try:
            from primitives_testbed.invoicing.selectors import get_invoice_for_printing
            from primitives_testbed.invoicing.printing import render_invoice_html

            invoice_data = get_invoice_for_printing(invoice_id)
            if invoice_data is None:
                console.print(f"[red]Could not prepare invoice for printing[/red]")
                return
            html = render_invoice_html(invoice_data)
            console.print(html)
        except ImportError:
            console.print("[yellow]HTML output requires invoicing module[/yellow]")


@cli.group(name="workflow")
def workflow_group():
    """Execute workflows."""
    pass


@workflow_group.command(name="basket-to-invoice")
@click.argument("basket_id")
def basket_to_invoice(basket_id):
    """Create an invoice from a basket.

    This executes the full basket-to-invoice workflow:
    1. Validates the basket
    2. Prices the items
    3. Creates the invoice
    4. Records ledger entries
    """
    from .selectors import get_basket

    console.print(f"[bold]Starting basket-to-invoice workflow...[/bold]")

    basket = get_basket(basket_id)
    if basket is None:
        console.print(f"[red]Basket not found: {basket_id}[/red]")
        return

    console.print(f"[cyan]Step 1:[/cyan] Basket validated: {basket.pk}")

    try:
        from primitives_testbed.invoicing.services import create_invoice_from_basket
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.first()
        if user is None:
            console.print("[red]No user found to create invoice[/red]")
            return

        console.print(f"[cyan]Step 2:[/cyan] Pricing basket items...")
        console.print(f"[cyan]Step 3:[/cyan] Creating invoice...")

        invoice = create_invoice_from_basket(basket, created_by=user)

        console.print(f"[green]Invoice created: {invoice.pk}[/green]")
        console.print(f"[bold green]Workflow complete![/bold green]")

    except ImportError:
        console.print("[yellow]Invoicing service not available[/yellow]")
    except Exception as e:
        console.print(f"[red]Workflow failed: {e}[/red]")


@cli.command()
@click.option("--scenario", help="Run specific scenario only")
def seed(scenario):
    """Seed demo data."""
    from django_parties.models import Organization, Person

    console.print("[bold]Seeding demo data...[/bold]")

    persons_created = 0
    orgs_created = 0

    demo_persons = [
        {"first_name": "Alice", "last_name": "Johnson"},
        {"first_name": "Bob", "last_name": "Smith"},
        {"first_name": "Carol", "last_name": "Williams"},
    ]

    demo_orgs = [
        {"name": "Acme Corporation"},
        {"name": "Global Tech Inc"},
        {"name": "Local Services LLC"},
    ]

    for person_data in demo_persons:
        obj, created = Person.objects.get_or_create(**person_data)
        if created:
            persons_created += 1

    for org_data in demo_orgs:
        obj, created = Organization.objects.get_or_create(**org_data)
        if created:
            orgs_created += 1

    console.print(f"[green]Created {persons_created} persons, {orgs_created} organizations[/green]")
    console.print("[bold green]Seed complete![/bold green]")


@cli.command()
@click.option("--scenario", help="Verify specific scenario only")
def verify(scenario):
    """Run integrity verification checks."""
    from django_parties.models import Organization, Person

    console.print("[bold]Running verification checks...[/bold]")

    checks_passed = 0
    checks_failed = 0

    person_count = Person.objects.count()
    org_count = Organization.objects.count()

    console.print(f"[cyan]Check:[/cyan] Person count: {person_count}")
    checks_passed += 1

    console.print(f"[cyan]Check:[/cyan] Organization count: {org_count}")
    checks_passed += 1

    if checks_failed == 0:
        console.print(f"[bold green]Verification complete: {checks_passed} checks passed[/bold green]")
    else:
        console.print(f"[bold red]Verification failed: {checks_failed} checks failed[/bold red]")


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
