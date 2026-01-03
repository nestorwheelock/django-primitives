"""Management command to verify database integrity constraints."""

from django.core.management.base import BaseCommand

from primitives_testbed.scenarios import SCENARIOS


class Command(BaseCommand):
    help = "Run negative write tests to verify database constraints are enforced"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            type=str,
            help="Verify only a specific scenario (e.g., parties, rbac, catalog)",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List available scenarios",
        )
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed output for each check",
        )

    def handle(self, *args, **options):
        if options["list"]:
            self.stdout.write(self.style.NOTICE("\nAvailable scenarios:"))
            for name, _, _ in SCENARIOS:
                self.stdout.write(f"  - {name}")
            self.stdout.write("")
            return

        specific = options.get("scenario")
        detailed = options.get("detailed", False)

        self.stdout.write(self.style.NOTICE("\n" + "=" * 70))
        self.stdout.write(self.style.NOTICE("Django Primitives Testbed - Integrity Verification"))
        self.stdout.write(self.style.NOTICE("=" * 70 + "\n"))

        total_pass = 0
        total_fail = 0
        total_skip = 0
        all_results = []

        for name, _, verify_fn in SCENARIOS:
            if specific and name != specific:
                continue

            self.stdout.write(self.style.NOTICE(f"\n[{name.upper()}]"))
            self.stdout.write("-" * 50)

            try:
                checks = verify_fn()
                for check_name, passed, detail in checks:
                    if passed is True:
                        total_pass += 1
                        status = self.style.SUCCESS("PASS")
                    elif passed is False:
                        total_fail += 1
                        status = self.style.ERROR("FAIL")
                    else:  # None = skipped
                        total_skip += 1
                        status = self.style.WARNING("SKIP")

                    self.stdout.write(f"  {status} {check_name}")
                    if detailed and detail:
                        self.stdout.write(f"       {detail}")

                    all_results.append((name, check_name, passed, detail))

            except Exception as e:
                total_fail += 1
                self.stdout.write(self.style.ERROR(f"  ERROR: {e}"))
                all_results.append((name, "scenario_error", False, str(e)))

        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.NOTICE("SUMMARY"))
        self.stdout.write("=" * 70)

        self.stdout.write(f"\n  {self.style.SUCCESS('PASS')}: {total_pass}")
        self.stdout.write(f"  {self.style.ERROR('FAIL')}: {total_fail}")
        self.stdout.write(f"  {self.style.WARNING('SKIP')}: {total_skip}")
        self.stdout.write(f"  TOTAL: {total_pass + total_fail + total_skip}\n")

        if total_fail == 0:
            self.stdout.write(self.style.SUCCESS("All integrity checks passed!"))
        else:
            self.stdout.write(self.style.ERROR(f"{total_fail} check(s) failed!"))
            self.stdout.write("\nFailed checks:")
            for name, check, passed, detail in all_results:
                if passed is False:
                    self.stdout.write(self.style.ERROR(f"  - {name}.{check}: {detail}"))

        self.stdout.write("")

        # Exit with non-zero if any failures
        if total_fail > 0:
            raise SystemExit(1)
