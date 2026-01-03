"""Management command to seed testbed with sample data."""

from django.core.management.base import BaseCommand

from primitives_testbed.scenarios import SCENARIOS


class Command(BaseCommand):
    help = "Seed testbed with sample data across all django-primitives packages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            type=str,
            help="Seed only a specific scenario (e.g., parties, rbac, catalog)",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List available scenarios",
        )

    def handle(self, *args, **options):
        if options["list"]:
            self.stdout.write(self.style.NOTICE("\nAvailable scenarios:"))
            for name, _, _ in SCENARIOS:
                self.stdout.write(f"  - {name}")
            self.stdout.write("")
            return

        specific = options.get("scenario")

        self.stdout.write(self.style.NOTICE("\n" + "=" * 60))
        self.stdout.write(self.style.NOTICE("Django Primitives Testbed - Seeding Data"))
        self.stdout.write(self.style.NOTICE("=" * 60 + "\n"))

        total_created = 0
        errors = []

        for name, seed_fn, _ in SCENARIOS:
            if specific and name != specific:
                continue

            self.stdout.write(f"Seeding {name}... ", ending="")
            try:
                count = seed_fn()
                total_created += count
                self.stdout.write(self.style.SUCCESS(f"OK ({count} objects)"))
            except Exception as e:
                errors.append((name, str(e)))
                self.stdout.write(self.style.ERROR(f"ERROR: {e}"))

        self.stdout.write("")
        self.stdout.write("-" * 60)
        self.stdout.write(f"Total objects created/verified: {total_created}")

        if errors:
            self.stdout.write(self.style.ERROR(f"\n{len(errors)} scenario(s) had errors:"))
            for name, error in errors:
                self.stdout.write(self.style.ERROR(f"  - {name}: {error}"))
            self.stdout.write("")

        if not errors:
            self.stdout.write(self.style.SUCCESS("\nSeeding complete! Run 'verify_integrity' to test constraints."))
        else:
            self.stdout.write(self.style.WARNING("\nSeeding completed with errors."))
