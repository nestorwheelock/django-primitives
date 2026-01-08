"""Clean up legacy thumbnail Documents.

The old thumbnail system created separate Document records for each thumbnail.
The new system uses MediaRendition attached to MediaAsset.

This command removes:
1. Documents with filenames starting with 'thumb_'
2. Their associated MediaAsset records (if any)
3. The legacy Photos/resized folder structure
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Remove legacy thumbnail Documents and their MediaAssets"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without making changes",
        )

    def handle(self, *args, **options):
        from django_documents.models import Document, MediaAsset, DocumentFolder

        dry_run = options["dry_run"]

        # Find legacy thumbnail documents
        thumb_docs = Document.objects.filter(
            filename__startswith="thumb_",
        )

        # Find signature documents (operational, shouldn't be MediaAssets)
        sig_docs = Document.objects.filter(
            filename__startswith="signature_",
        )

        # Find signed agreement PDFs
        agreement_pdfs = Document.objects.filter(
            filename__startswith="signed_agreement_",
        )

        thumb_count = thumb_docs.count()
        sig_count = sig_docs.count()
        pdf_count = agreement_pdfs.count()

        self.stdout.write(f"Found {thumb_count} legacy thumbnail Documents")
        self.stdout.write(f"Found {sig_count} signature Documents")
        self.stdout.write(f"Found {pdf_count} signed agreement PDFs")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run - no changes will be made"))

            # Show some examples
            self.stdout.write("\nSample thumbnail documents:")
            for doc in thumb_docs[:10]:
                self.stdout.write(f"  - {doc.filename} (pk={doc.pk})")

            # Count MediaAssets that would be affected
            thumb_assets = MediaAsset.objects.filter(
                document__filename__startswith="thumb_"
            ).count()
            sig_assets = MediaAsset.objects.filter(
                document__filename__startswith="signature_"
            ).count()
            pdf_assets = MediaAsset.objects.filter(
                document__filename__startswith="signed_agreement_"
            ).count()

            self.stdout.write(f"\nMediaAssets that would be deleted:")
            self.stdout.write(f"  - {thumb_assets} thumbnail MediaAssets")
            self.stdout.write(f"  - {sig_assets} signature MediaAssets")
            self.stdout.write(f"  - {pdf_assets} signed agreement MediaAssets")

            # Check for resized folders
            try:
                photos_folder = DocumentFolder.objects.get(name="Photos", parent=None)
                resized_folder = DocumentFolder.objects.filter(
                    name="resized", parent=photos_folder
                ).first()
                if resized_folder:
                    self.stdout.write(f"\nLegacy folder structure found: Photos/resized/")
            except DocumentFolder.DoesNotExist:
                pass

            return

        # Delete in transaction
        with transaction.atomic():
            # Delete MediaAssets first (due to FK constraints)
            deleted_assets = MediaAsset.objects.filter(
                document__filename__startswith="thumb_"
            ).delete()[0]
            self.stdout.write(f"Deleted {deleted_assets} thumbnail MediaAssets")

            deleted_sig_assets = MediaAsset.objects.filter(
                document__filename__startswith="signature_"
            ).delete()[0]
            self.stdout.write(f"Deleted {deleted_sig_assets} signature MediaAssets")

            deleted_pdf_assets = MediaAsset.objects.filter(
                document__filename__startswith="signed_agreement_"
            ).delete()[0]
            self.stdout.write(f"Deleted {deleted_pdf_assets} signed agreement MediaAssets")

            # Delete the Documents (soft delete to preserve history)
            from django.utils import timezone
            now = timezone.now()

            # Hard delete thumbnails (they're generated, not original content)
            thumb_docs.delete()
            self.stdout.write(f"Deleted {thumb_count} thumbnail Documents")

            # Note: We don't delete signature or agreement documents,
            # just their MediaAssets. Those documents are operational records.

            # Clean up empty resized folders
            try:
                photos_folder = DocumentFolder.objects.get(name="Photos", parent=None)
                resized_folder = DocumentFolder.objects.filter(
                    name="resized", parent=photos_folder
                ).first()
                if resized_folder:
                    # Delete size subfolders
                    for size_folder in DocumentFolder.objects.filter(parent=resized_folder):
                        if not Document.objects.filter(folder=size_folder).exists():
                            size_folder.delete()
                            self.stdout.write(f"  Deleted empty folder: {size_folder.name}")
                    # Delete resized folder if empty
                    if not DocumentFolder.objects.filter(parent=resized_folder).exists():
                        resized_folder.delete()
                        self.stdout.write("  Deleted empty folder: resized")
            except DocumentFolder.DoesNotExist:
                pass

        self.stdout.write(self.style.SUCCESS("\nCleanup complete!"))
