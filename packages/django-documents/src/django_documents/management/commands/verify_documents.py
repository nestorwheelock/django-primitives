"""
Management command to verify document blob integrity.

Scans DocumentVersion records and checks filesystem blobs for:
- Missing files
- Corrupted files (hash mismatch)
"""

import json

from django.core.management.base import BaseCommand

from django_documents.models import DocumentVersion
from django_documents.services import verify_blob


class Command(BaseCommand):
    help = "Verify document blob integrity against database records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample",
            type=int,
            default=None,
            help="Limit scan to N random versions (for large datasets)",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json", "csv"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show details of each file checked",
        )

    def handle(self, *args, **options):
        sample_size = options["sample"]
        output_format = options["format"]
        verbose = options["verbose"]

        # Get versions to check
        versions = DocumentVersion.objects.all()

        if sample_size:
            versions = versions.order_by("?")[:sample_size]

        # Count results
        ok_count = 0
        missing_count = 0
        corrupt_count = 0
        missing_files = []
        corrupt_files = []

        for version in versions:
            result = verify_blob(version)

            if result == "ok":
                ok_count += 1
                if verbose:
                    self.stdout.write(f"OK: {version.blob_path}")
            elif result == "missing":
                missing_count += 1
                missing_files.append(version.blob_path)
                if verbose:
                    self.stdout.write(self.style.WARNING(f"MISSING: {version.blob_path}"))
            elif result == "corrupt":
                corrupt_count += 1
                corrupt_files.append(version.blob_path)
                if verbose:
                    self.stdout.write(self.style.ERROR(f"CORRUPT: {version.blob_path}"))

        total_scanned = ok_count + missing_count + corrupt_count

        # Output results
        if output_format == "json":
            self.stdout.write(json.dumps({
                "ok": ok_count,
                "missing": missing_count,
                "corrupt": corrupt_count,
                "scanned": total_scanned,
                "missing_files": missing_files if verbose else [],
                "corrupt_files": corrupt_files if verbose else [],
            }))
        elif output_format == "csv":
            self.stdout.write("status,count")
            self.stdout.write(f"ok,{ok_count}")
            self.stdout.write(f"missing,{missing_count}")
            self.stdout.write(f"corrupt,{corrupt_count}")
            self.stdout.write(f"scanned,{total_scanned}")
        else:
            # Text format
            self.stdout.write("\nDocument Verification Results")
            self.stdout.write("=" * 30)
            self.stdout.write(f"Scanned: {total_scanned}")
            self.stdout.write(self.style.SUCCESS(f"OK: {ok_count}"))
            if missing_count > 0:
                self.stdout.write(self.style.WARNING(f"MISSING: {missing_count}"))
            else:
                self.stdout.write(f"MISSING: {missing_count}")
            if corrupt_count > 0:
                self.stdout.write(self.style.ERROR(f"CORRUPT: {corrupt_count}"))
            else:
                self.stdout.write(f"CORRUPT: {corrupt_count}")

            if missing_files and verbose:
                self.stdout.write("\nMissing files:")
                for f in missing_files:
                    self.stdout.write(f"  - {f}")

            if corrupt_files and verbose:
                self.stdout.write("\nCorrupt files:")
                for f in corrupt_files:
                    self.stdout.write(f"  - {f}")
