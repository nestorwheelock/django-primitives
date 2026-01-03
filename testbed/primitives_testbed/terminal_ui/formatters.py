"""Rich table and panel formatters for terminal UI."""

from typing import Any
from uuid import UUID

from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def short_uuid(uuid_val: UUID | str | None) -> str:
    """Shorten a UUID to first 8 characters for readability.

    Args:
        uuid_val: UUID object, string, or None

    Returns:
        First 8 characters of UUID, or "-" if None
    """
    if uuid_val is None:
        return "-"
    return str(uuid_val)[:8]


def format_parties_table(parties: list) -> Table:
    """Format a list of parties (Person/Organization) as a Rich table.

    Args:
        parties: List of Person and/or Organization objects

    Returns:
        Rich Table ready for display
    """
    table = Table(title="Parties")
    table.add_column("ID", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Created", style="dim")

    for party in parties:
        party_type = party.__class__.__name__
        if party_type == "Person":
            name = f"{party.first_name} {party.last_name}"
        else:
            name = party.name

        created = party.created_at.strftime("%Y-%m-%d") if party.created_at else "-"

        table.add_row(
            short_uuid(party.pk),
            party_type,
            name,
            created,
        )

    return table


def format_encounters_table(encounters: list) -> Table:
    """Format a list of encounters as a Rich table.

    Args:
        encounters: List of Encounter objects

    Returns:
        Rich Table ready for display
    """
    table = Table(title="Encounters")
    table.add_column("ID", style="dim")
    table.add_column("Definition", style="cyan")
    table.add_column("State", style="yellow")
    table.add_column("Started", style="dim")

    for enc in encounters:
        definition = enc.definition.name if enc.definition else "-"
        started = enc.started_at.strftime("%Y-%m-%d %H:%M") if enc.started_at else "-"

        table.add_row(
            short_uuid(enc.pk),
            definition,
            enc.state or "-",
            started,
        )

    return table


def format_baskets_table(baskets: list) -> Table:
    """Format a list of baskets as a Rich table.

    Args:
        baskets: List of Basket objects

    Returns:
        Rich Table ready for display
    """
    table = Table(title="Baskets")
    table.add_column("ID", style="dim")
    table.add_column("Status", style="yellow")
    table.add_column("Items", style="cyan")
    table.add_column("Created", style="dim")

    for basket in baskets:
        item_count = basket.items.count() if hasattr(basket, "items") else 0
        created = basket.created_at.strftime("%Y-%m-%d") if basket.created_at else "-"

        table.add_row(
            short_uuid(basket.pk),
            basket.status or "-",
            str(item_count),
            created,
        )

    return table


def format_invoices_table(invoices: list) -> Table:
    """Format a list of invoices as a Rich table.

    Args:
        invoices: List of Invoice objects

    Returns:
        Rich Table ready for display
    """
    table = Table(title="Invoices")
    table.add_column("ID", style="dim")
    table.add_column("Status", style="yellow")
    table.add_column("Billed To", style="cyan")
    table.add_column("Total", style="green")
    table.add_column("Created", style="dim")

    for inv in invoices:
        billed_to = str(inv.billed_to) if inv.billed_to else "-"
        total = str(inv.total_amount) if hasattr(inv, "total_amount") else "-"
        created = inv.created_at.strftime("%Y-%m-%d") if inv.created_at else "-"

        table.add_row(
            short_uuid(inv.pk),
            inv.status or "-",
            billed_to,
            total,
            created,
        )

    return table


def format_ledger_table(transactions: list) -> Table:
    """Format a list of ledger transactions as a Rich table.

    Args:
        transactions: List of Transaction objects

    Returns:
        Rich Table ready for display
    """
    table = Table(title="Ledger Transactions")
    table.add_column("ID", style="dim")
    table.add_column("Description", style="cyan")
    table.add_column("Entries", style="yellow")
    table.add_column("Posted", style="dim")

    for txn in transactions:
        entry_count = txn.entries.count() if hasattr(txn, "entries") else 0
        posted = txn.posted_at.strftime("%Y-%m-%d") if txn.posted_at else "-"

        table.add_row(
            short_uuid(txn.pk),
            txn.description or "-",
            str(entry_count),
            posted,
        )

    return table


def format_agreements_table(agreements: list) -> Table:
    """Format a list of agreements as a Rich table.

    Args:
        agreements: List of Agreement objects

    Returns:
        Rich Table ready for display
    """
    table = Table(title="Agreements")
    table.add_column("ID", style="dim")
    table.add_column("Scope Type", style="cyan")
    table.add_column("Valid From", style="yellow")
    table.add_column("Valid To", style="yellow")
    table.add_column("Created", style="dim")

    for agr in agreements:
        created = agr.created_at.strftime("%Y-%m-%d") if agr.created_at else "-"
        valid_from = agr.valid_from.strftime("%Y-%m-%d") if agr.valid_from else "-"
        valid_to = agr.valid_to.strftime("%Y-%m-%d") if agr.valid_to else "∞"

        table.add_row(
            short_uuid(agr.pk),
            agr.scope_type or "-",
            valid_from,
            valid_to,
            created,
        )

    return table


def format_party_detail(party) -> Panel:
    """Format a party (Person or Organization) as a Rich Panel.

    Args:
        party: Person or Organization object

    Returns:
        Rich Panel with party details
    """
    party_type = party.__class__.__name__
    lines = []

    lines.append(f"[bold]ID:[/bold] {party.pk}")
    lines.append(f"[bold]Type:[/bold] {party_type}")

    if party_type == "Person":
        lines.append(f"[bold]Name:[/bold] {party.first_name} {party.last_name}")
        if hasattr(party, "email") and party.email:
            lines.append(f"[bold]Email:[/bold] {party.email}")
        if hasattr(party, "phone") and party.phone:
            lines.append(f"[bold]Phone:[/bold] {party.phone}")
    else:
        lines.append(f"[bold]Name:[/bold] {party.name}")
        if hasattr(party, "website") and party.website:
            lines.append(f"[bold]Website:[/bold] {party.website}")

    if party.created_at:
        lines.append(f"[bold]Created:[/bold] {party.created_at.strftime('%Y-%m-%d %H:%M')}")

    content = "\n".join(lines)
    title = f"{party_type}: {party.first_name} {party.last_name}" if party_type == "Person" else f"{party_type}: {party.name}"

    return Panel(content, title=title, border_style="green")


def format_invoice_detail(invoice) -> Panel:
    """Format an invoice as a Rich Panel with line items.

    Args:
        invoice: Invoice object

    Returns:
        Rich Panel with invoice details and line items
    """
    lines = []

    lines.append(f"[bold]ID:[/bold] {invoice.pk}")
    lines.append(f"[bold]Status:[/bold] {invoice.status or '-'}")
    lines.append(f"[bold]Billed To:[/bold] {invoice.billed_to or '-'}")
    lines.append(f"[bold]Issued By:[/bold] {invoice.issued_by or '-'}")
    lines.append(f"[bold]Total:[/bold] {invoice.total_amount if hasattr(invoice, 'total_amount') else '-'}")

    if invoice.created_at:
        lines.append(f"[bold]Created:[/bold] {invoice.created_at.strftime('%Y-%m-%d %H:%M')}")

    if hasattr(invoice, "line_items"):
        line_items = list(invoice.line_items.all())
        if line_items:
            lines.append("")
            lines.append("[bold]Line Items:[/bold]")
            for item in line_items:
                desc = getattr(item, "description", str(item))
                qty = getattr(item, "quantity", "-")
                price = getattr(item, "unit_price", "-")
                lines.append(f"  - {desc}: {qty} x {price}")

    content = "\n".join(lines)
    return Panel(content, title=f"Invoice: {short_uuid(invoice.pk)}", border_style="cyan")


def format_basket_detail(basket) -> Panel:
    """Format a basket as a Rich Panel with items.

    Args:
        basket: Basket object

    Returns:
        Rich Panel with basket details and items
    """
    lines = []

    lines.append(f"[bold]ID:[/bold] {basket.pk}")
    lines.append(f"[bold]Status:[/bold] {basket.status or '-'}")

    if basket.created_at:
        lines.append(f"[bold]Created:[/bold] {basket.created_at.strftime('%Y-%m-%d %H:%M')}")

    if hasattr(basket, "items"):
        items = list(basket.items.all())
        lines.append(f"[bold]Item Count:[/bold] {len(items)}")
        if items:
            lines.append("")
            lines.append("[bold]Items:[/bold]")
            for item in items:
                desc = getattr(item, "description", str(item))
                qty = getattr(item, "quantity", 1)
                lines.append(f"  - {desc} (qty: {qty})")

    content = "\n".join(lines)
    return Panel(content, title=f"Basket: {short_uuid(basket.pk)}", border_style="yellow")
