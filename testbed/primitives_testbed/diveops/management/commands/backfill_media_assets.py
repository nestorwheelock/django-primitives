"""Backfill MediaAsset records for existing image documents."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create MediaAsset records for existing image documents that don't have one"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        from django_documents.models import Document, MediaAsset
        from django_documents.media_service import process_image_upload, generate_renditions

        dry_run = options["dry_run"]

        # Find all image documents without a MediaAsset
        image_docs = Document.objects.filter(
            content_type__startswith="image/",
            deleted_at__isnull=True,
        ).exclude(
            pk__in=MediaAsset.objects.values_list("document_id", flat=True)
        )

        total = image_docs.count()
        self.stdout.write(f"Found {total} image documents without MediaAsset records")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run - no changes will be made"))
            for doc in image_docs[:10]:
                self.stdout.write(f"  Would process: {doc.filename} (pk={doc.pk})")
            if total > 10:
                self.stdout.write(f"  ... and {total - 10} more")
            return

        created = 0
        errors = 0

        for doc in image_docs:
            try:
                asset = process_image_upload(doc)
                generate_renditions(asset)
                created += 1
                self.stdout.write(f"  Created MediaAsset for: {doc.filename}")
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"  Error processing {doc.filename}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"\nDone! Created {created} MediaAssets, {errors} errors")
        )
