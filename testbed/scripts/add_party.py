#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     PARTY REGISTRATION TERMINAL v1.0                          ║
║                        DJANGO PRIMITIVES BANK SYSTEM                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Standalone CLI for party registration with retro bank terminal aesthetics.
"""

import os
import sys
import time

# Configure Django before importing models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'primitives_testbed.settings')

import django
django.setup()

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

# Bank terminal green
TERMINAL_GREEN = "green"
TERMINAL_DIM = "dim green"
TERMINAL_BRIGHT = "bold bright_green"
TERMINAL_ERROR = "bold red"
TERMINAL_WARN = "bold yellow"

console = Console()


def clear_screen():
    """Clear terminal screen."""
    console.clear()


def print_header():
    """Print the bank terminal header."""
    header = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ██████╗  █████╗ ██████╗ ████████╗██╗   ██╗    ███████╗██╗   ██╗███████╗    ║
║   ██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝╚██╗ ██╔╝    ██╔════╝╚██╗ ██╔╝██╔════╝    ║
║   ██████╔╝███████║██████╔╝   ██║    ╚████╔╝     ███████╗ ╚████╔╝ ███████╗    ║
║   ██╔═══╝ ██╔══██║██╔══██╗   ██║     ╚██╔╝      ╚════██║  ╚██╔╝  ╚════██║    ║
║   ██║     ██║  ██║██║  ██║   ██║      ██║       ███████║   ██║   ███████║    ║
║   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝      ╚═╝       ╚══════╝   ╚═╝   ╚══════╝    ║
║                                                                               ║
║                    PARTY REGISTRATION TERMINAL v1.0                           ║
║                         AUTHORIZED ACCESS ONLY                                ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""
    console.print(header, style=TERMINAL_GREEN)


def print_separator():
    """Print a separator line."""
    console.print("─" * 79, style=TERMINAL_DIM)


def typing_effect(text, delay=0.02):
    """Print text with typewriter effect."""
    for char in text:
        console.print(char, end="", style=TERMINAL_GREEN)
        time.sleep(delay)
    console.print()


def processing_animation(message="PROCESSING", duration=1.5):
    """Show a processing animation."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + duration
    i = 0
    while time.time() < end_time:
        console.print(f"\r  {frames[i % len(frames)]} {message}...", end="", style=TERMINAL_GREEN)
        time.sleep(0.1)
        i += 1
    console.print(f"\r  ✓ {message}... COMPLETE", style=TERMINAL_BRIGHT)


def print_transaction_id():
    """Print a fake transaction ID."""
    import random
    txn_id = f"TXN-{random.randint(100000, 999999)}-{random.randint(1000, 9999)}"
    console.print(f"\n  TRANSACTION ID: {txn_id}", style=TERMINAL_DIM)


def print_status(message, status="OK"):
    """Print a status message."""
    if status == "OK":
        console.print(f"  [{status}] {message}", style=TERMINAL_BRIGHT)
    elif status == "ERROR":
        console.print(f"  [{status}] {message}", style=TERMINAL_ERROR)
    else:
        console.print(f"  [{status}] {message}", style=TERMINAL_WARN)


def print_record_table(record_type, data):
    """Print record details in a table."""
    table = Table(
        box=box.DOUBLE,
        border_style=TERMINAL_GREEN,
        header_style=TERMINAL_BRIGHT,
        show_header=True,
    )
    table.add_column("FIELD", style=TERMINAL_DIM)
    table.add_column("VALUE", style=TERMINAL_GREEN)

    for key, value in data.items():
        table.add_row(key.upper(), str(value) if value else "N/A")

    console.print()
    console.print(f"  ┌─ {record_type} RECORD ─┐", style=TERMINAL_GREEN)
    console.print(table)


def confirm_prompt(message):
    """Show a confirmation prompt."""
    console.print(f"\n  {message} (Y/N): ", end="", style=TERMINAL_WARN)
    response = input().strip().upper()
    return response == "Y"


@click.group()
def cli():
    """PARTY REGISTRATION TERMINAL - Django Primitives Bank System"""
    pass


@cli.command()
@click.option('--first-name', prompt=True, help='First name')
@click.option('--last-name', prompt=True, help='Last name')
@click.option('--email', default='', help='Email address')
@click.option('--phone', default='', help='Phone number')
@click.option('--interactive/--no-interactive', '-i', default=False, help='Interactive mode')
def person(first_name, last_name, email, phone, interactive):
    """Register a new PERSON in the system."""
    from django_parties.models import Person

    clear_screen()
    print_header()

    console.print("\n  ┌─────────────────────────────────────┐", style=TERMINAL_GREEN)
    console.print("  │     PERSON REGISTRATION MODULE      │", style=TERMINAL_GREEN)
    console.print("  └─────────────────────────────────────┘", style=TERMINAL_GREEN)

    if interactive:
        console.print("\n  ENTER PARTY DETAILS:", style=TERMINAL_BRIGHT)
        print_separator()

        console.print("  FIRST NAME: ", end="", style=TERMINAL_GREEN)
        first_name = input().strip() or first_name

        console.print("  LAST NAME: ", end="", style=TERMINAL_GREEN)
        last_name = input().strip() or last_name

        console.print("  EMAIL [OPTIONAL]: ", end="", style=TERMINAL_GREEN)
        email = input().strip() or email

        console.print("  PHONE [OPTIONAL]: ", end="", style=TERMINAL_GREEN)
        phone = input().strip() or phone

    data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
    }

    print_record_table("PERSON", data)

    if not confirm_prompt("CONFIRM REGISTRATION?"):
        console.print("\n  TRANSACTION CANCELLED BY USER", style=TERMINAL_ERROR)
        return

    console.print()
    processing_animation("VALIDATING INPUT")
    processing_animation("CHECKING DUPLICATES")
    processing_animation("WRITING TO DATABASE")

    try:
        person_obj = Person.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,  # Empty string is valid
            phone=phone,  # Empty string is valid
        )

        print_transaction_id()
        console.print()
        print_status(f"PERSON CREATED SUCCESSFULLY")
        console.print(f"\n  RECORD ID: {person_obj.pk}", style=TERMINAL_BRIGHT)
        console.print(f"  SHORT ID:  {str(person_obj.pk)[:8]}", style=TERMINAL_GREEN)

        console.print("\n" + "═" * 79, style=TERMINAL_GREEN)
        console.print("  TRANSACTION COMPLETE - THANK YOU FOR USING PARTY SYS", style=TERMINAL_BRIGHT)
        console.print("═" * 79 + "\n", style=TERMINAL_GREEN)

    except Exception as e:
        print_status(f"DATABASE ERROR: {e}", status="ERROR")
        sys.exit(1)


@cli.command()
@click.option('--name', prompt=True, help='Organization name')
@click.option('--website', default='', help='Website URL')
@click.option('--interactive/--no-interactive', '-i', default=False, help='Interactive mode')
def org(name, website, interactive):
    """Register a new ORGANIZATION in the system."""
    from django_parties.models import Organization

    clear_screen()
    print_header()

    console.print("\n  ┌─────────────────────────────────────┐", style=TERMINAL_GREEN)
    console.print("  │   ORGANIZATION REGISTRATION MODULE  │", style=TERMINAL_GREEN)
    console.print("  └─────────────────────────────────────┘", style=TERMINAL_GREEN)

    if interactive:
        console.print("\n  ENTER ORGANIZATION DETAILS:", style=TERMINAL_BRIGHT)
        print_separator()

        console.print("  ORGANIZATION NAME: ", end="", style=TERMINAL_GREEN)
        name = input().strip() or name

        console.print("  WEBSITE [OPTIONAL]: ", end="", style=TERMINAL_GREEN)
        website = input().strip() or website

    data = {
        "name": name,
        "website": website,
    }

    print_record_table("ORGANIZATION", data)

    if not confirm_prompt("CONFIRM REGISTRATION?"):
        console.print("\n  TRANSACTION CANCELLED BY USER", style=TERMINAL_ERROR)
        return

    console.print()
    processing_animation("VALIDATING INPUT")
    processing_animation("CHECKING DUPLICATES")
    processing_animation("WRITING TO DATABASE")

    try:
        org_obj = Organization.objects.create(
            name=name,
            website=website,  # Empty string is valid
        )

        print_transaction_id()
        console.print()
        print_status(f"ORGANIZATION CREATED SUCCESSFULLY")
        console.print(f"\n  RECORD ID: {org_obj.pk}", style=TERMINAL_BRIGHT)
        console.print(f"  SHORT ID:  {str(org_obj.pk)[:8]}", style=TERMINAL_GREEN)

        console.print("\n" + "═" * 79, style=TERMINAL_GREEN)
        console.print("  TRANSACTION COMPLETE - THANK YOU FOR USING PARTY SYS", style=TERMINAL_BRIGHT)
        console.print("═" * 79 + "\n", style=TERMINAL_GREEN)

    except Exception as e:
        print_status(f"DATABASE ERROR: {e}", status="ERROR")
        sys.exit(1)


@cli.command()
def list_parties():
    """List all registered parties in the system."""
    from django_parties.models import Person, Organization

    clear_screen()
    print_header()

    console.print("\n  ┌─────────────────────────────────────┐", style=TERMINAL_GREEN)
    console.print("  │       PARTY INQUIRY TERMINAL        │", style=TERMINAL_GREEN)
    console.print("  └─────────────────────────────────────┘", style=TERMINAL_GREEN)

    processing_animation("QUERYING DATABASE")

    # Persons table
    persons = Person.objects.all()[:20]
    if persons:
        table = Table(
            title="REGISTERED PERSONS",
            box=box.DOUBLE,
            border_style=TERMINAL_GREEN,
            header_style=TERMINAL_BRIGHT,
        )
        table.add_column("ID", style=TERMINAL_DIM)
        table.add_column("FIRST NAME", style=TERMINAL_GREEN)
        table.add_column("LAST NAME", style=TERMINAL_GREEN)
        table.add_column("EMAIL", style=TERMINAL_DIM)

        for p in persons:
            table.add_row(
                str(p.pk)[:8],
                p.first_name,
                p.last_name,
                p.email or "N/A"
            )

        console.print()
        console.print(table)

    # Organizations table
    orgs = Organization.objects.all()[:20]
    if orgs:
        table = Table(
            title="REGISTERED ORGANIZATIONS",
            box=box.DOUBLE,
            border_style=TERMINAL_GREEN,
            header_style=TERMINAL_BRIGHT,
        )
        table.add_column("ID", style=TERMINAL_DIM)
        table.add_column("NAME", style=TERMINAL_GREEN)
        table.add_column("WEBSITE", style=TERMINAL_DIM)

        for o in orgs:
            table.add_row(
                str(o.pk)[:8],
                o.name,
                o.website or "N/A"
            )

        console.print()
        console.print(table)

    total = Person.objects.count() + Organization.objects.count()
    console.print(f"\n  TOTAL RECORDS: {total}", style=TERMINAL_BRIGHT)
    console.print("═" * 79 + "\n", style=TERMINAL_GREEN)


@cli.command()
def menu():
    """Interactive menu system."""
    while True:
        clear_screen()
        print_header()

        console.print("\n  ┌─────────────────────────────────────┐", style=TERMINAL_GREEN)
        console.print("  │          MAIN MENU                  │", style=TERMINAL_GREEN)
        console.print("  └─────────────────────────────────────┘", style=TERMINAL_GREEN)

        console.print("\n  SELECT OPTION:", style=TERMINAL_BRIGHT)
        console.print()
        console.print("    [1] REGISTER NEW PERSON", style=TERMINAL_GREEN)
        console.print("    [2] REGISTER NEW ORGANIZATION", style=TERMINAL_GREEN)
        console.print("    [3] LIST ALL PARTIES", style=TERMINAL_GREEN)
        console.print("    [4] EXIT SYSTEM", style=TERMINAL_GREEN)
        console.print()
        console.print("  ENTER SELECTION: ", end="", style=TERMINAL_BRIGHT)

        choice = input().strip()

        if choice == "1":
            ctx = click.Context(person)
            ctx.invoke(person, first_name="", last_name="", email="", phone="", interactive=True)
            input("\n  PRESS ENTER TO CONTINUE...")
        elif choice == "2":
            ctx = click.Context(org)
            ctx.invoke(org, name="", website="", interactive=True)
            input("\n  PRESS ENTER TO CONTINUE...")
        elif choice == "3":
            ctx = click.Context(list_parties)
            ctx.invoke(list_parties)
            input("\n  PRESS ENTER TO CONTINUE...")
        elif choice == "4":
            clear_screen()
            console.print("\n" + "═" * 79, style=TERMINAL_GREEN)
            console.print("  LOGGING OFF... SESSION TERMINATED", style=TERMINAL_BRIGHT)
            console.print("  THANK YOU FOR USING PARTY REGISTRATION SYSTEM", style=TERMINAL_GREEN)
            console.print("═" * 79 + "\n", style=TERMINAL_GREEN)
            break
        else:
            console.print("\n  INVALID SELECTION", style=TERMINAL_ERROR)
            time.sleep(1)


if __name__ == "__main__":
    cli()
