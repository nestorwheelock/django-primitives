"""Seed chart of accounts for dive shop operations.

Creates standard ledger accounts required for:
- Revenue tracking (dive revenue, equipment rental)
- Cost tracking (excursion costs, gas, equipment)
- Asset management (cash/bank, accounts receivable)
- Liability tracking (accounts payable)

Usage:
    python manage.py seed_chart_of_accounts
    python manage.py seed_chart_of_accounts --org <shop_pk>
    python manage.py seed_chart_of_accounts --org <shop_pk> --currency MXN
    python manage.py seed_chart_of_accounts --org <shop_pk> --with-vendors
    python manage.py seed_chart_of_accounts --list  # List existing accounts
    python manage.py seed_chart_of_accounts --clear --org <shop_pk>  # Clear cache only
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from django_parties.models import Organization

from ...accounts import (
    ACCOUNT_TYPES,
    REQUIRED_ACCOUNT_KEYS,
    AccountConfigurationError,
    clear_account_cache,
    get_required_accounts,
    list_accounts,
    seed_accounts,
)


class Command(BaseCommand):
    help = "Seed standard chart of accounts for dive shop operations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--org",
            type=str,
            help="Organization (dive shop) ID to seed accounts for. If not specified, seeds for all dive shops.",
        )
        parser.add_argument(
            "--currency",
            type=str,
            default="MXN",
            choices=["USD", "MXN", "EUR"],
            help="Currency for accounts (default: MXN)",
        )
        parser.add_argument(
            "--with-vendors",
            action="store_true",
            help="Also create per-vendor payable accounts for existing vendors",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            dest="list_accounts",
            help="List existing accounts instead of seeding",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Check if required accounts exist for the specified org/currency",
        )
        parser.add_argument(
            "--clear-cache",
            action="store_true",
            help="Clear the account cache (useful after manual DB changes)",
        )

    def handle(self, *args, **options):
        # Clear cache if requested
        if options["clear_cache"]:
            clear_account_cache()
            self.stdout.write(self.style.SUCCESS("Account cache cleared."))
            return

        # List mode
        if options["list_accounts"]:
            self._list_accounts(options)
            return

        # Check mode
        if options["check"]:
            self._check_accounts(options)
            return

        # Seed mode
        self._seed_accounts(options)

    def _list_accounts(self, options):
        """List existing accounts with optional filters."""
        shop = None
        if options["org"]:
            shop = self._get_shop(options["org"])

        currency = options["currency"] if options["currency"] != "MXN" else None

        accounts = list_accounts(shop=shop, currency=currency)

        if not accounts:
            self.stdout.write(self.style.WARNING("No accounts found."))
            return

        self.stdout.write(f"\nFound {len(accounts)} accounts:\n")

        # Group by type
        by_type = {}
        for account in accounts:
            if account.account_type not in by_type:
                by_type[account.account_type] = []
            by_type[account.account_type].append(account)

        for account_type, type_accounts in sorted(by_type.items()):
            self.stdout.write(self.style.HTTP_INFO(f"\n{account_type.upper()}:"))
            for account in type_accounts:
                self.stdout.write(f"  - {account.name} ({account.currency})")
                self.stdout.write(f"    ID: {account.pk}")

    def _check_accounts(self, options):
        """Check if required accounts exist."""
        if not options["org"]:
            raise CommandError("--check requires --org to be specified")

        shop = self._get_shop(options["org"])
        currency = options["currency"]

        try:
            account_set = get_required_accounts(shop, currency, auto_create=False)
            self.stdout.write(
                self.style.SUCCESS(
                    f"All required accounts exist for {shop.name} ({currency})."
                )
            )

            # Show what exists
            self.stdout.write("\nRequired accounts found:")
            for key in REQUIRED_ACCOUNT_KEYS:
                account = getattr(account_set, key)
                if account:
                    self.stdout.write(f"  - {key}: {account.name}")

        except AccountConfigurationError as e:
            self.stdout.write(
                self.style.WARNING(
                    f"Missing required accounts for {shop.name} ({currency}):"
                )
            )
            for key in e.missing_types:
                self.stdout.write(f"  - {key}")
            self.stdout.write(
                f"\nRun 'python manage.py seed_chart_of_accounts --org {shop.pk} --currency {currency}' to create them."
            )

    @transaction.atomic
    def _seed_accounts(self, options):
        """Seed accounts for one or all dive shops."""
        currency = options["currency"]
        include_vendors = options["with_vendors"]

        # Get shops to seed
        if options["org"]:
            shops = [self._get_shop(options["org"])]
        else:
            shops = list(
                Organization.objects.filter(org_type__in=["company", "dive_shop"])
            )
            if not shops:
                raise CommandError(
                    "No dive shops found. Create an Organization with org_type='dive_shop' first."
                )

        # Get vendors if requested
        vendors = []
        if include_vendors:
            vendors = list(Organization.objects.filter(org_type="vendor"))
            self.stdout.write(f"Including {len(vendors)} vendor(s) for per-vendor AP accounts.")

        # Seed for each shop
        total_created = 0
        for shop in shops:
            self.stdout.write(f"\nSeeding accounts for {shop.name} ({currency})...")

            # Clear cache before seeding
            clear_account_cache()

            # Seed accounts
            account_set = seed_accounts(shop, currency, vendors=vendors)

            # Report what was created
            created_count = 0
            for key in ACCOUNT_TYPES:
                account = getattr(account_set, key, None)
                if account:
                    created_count += 1
                    self.stdout.write(f"  - {account.name}")

            total_created += created_count
            self.stdout.write(
                self.style.SUCCESS(f"  Created/verified {created_count} accounts.")
            )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeeding complete. {total_created} accounts created/verified across {len(shops)} shop(s)."
            )
        )

        # Show what accounts are required
        self.stdout.write("\nRequired accounts for operations:")
        for key in REQUIRED_ACCOUNT_KEYS:
            config = ACCOUNT_TYPES[key]
            self.stdout.write(f"  - {key} ({config['account_type']}): {config['description']}")

    def _get_shop(self, org_id: str) -> Organization:
        """Get organization by ID."""
        try:
            return Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization with ID '{org_id}' not found.")
        except Exception as e:
            raise CommandError(f"Invalid organization ID '{org_id}': {e}")
