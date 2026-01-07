"""Management command to purge expired documents from Trash.

This command enforces data retention policies by:
1. Finding documents in Trash folder older than retention period
2. Checking for legal holds (documents with active holds are skipped)
3. Applying document-type specific retention policies
4. Permanently deleting eligible documents
5. Logging all deletions to audit log for compliance

Default retention: 30 days in Trash (configurable via DocumentRetentionPolicy).

Run daily via cron:
    0 2 * * * /path/to/manage.py purge_trash

Options:
    --dry-run: Show what would be deleted without deleting
    --force: Delete even if no policy matches (use default)
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django_audit_log.api import log
from django_documents.models import Document, DocumentFolder

from primitives_testbed.diveops.models import (
    DocumentLegalHold,
    DocumentRetentionPolicy,
)


# Default trash retention if no policy defined
DEFAULT_TRASH_RETENTION_DAYS = 30


class Command(BaseCommand):
    help = "Purge expired documents from Trash based on retention policies"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete documents even if no specific policy matches (use default 30 days)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output for each document",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        verbose = options["verbose"]

        self.stdout.write(self.style.NOTICE("Document Trash Purge"))
        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No documents will be deleted"))

        # Get Trash folder
        trash_folder = DocumentFolder.objects.filter(
            slug="trash",
            parent__isnull=True,
        ).first()

        if not trash_folder:
            self.stdout.write(self.style.ERROR("Trash folder not found"))
            return

        # Load retention policies into a lookup dict
        policies = {
            p.document_type: p
            for p in DocumentRetentionPolicy.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
            )
        }

        # Get all documents in Trash
        trash_documents = Document.objects.filter(folder=trash_folder)
        total_count = trash_documents.count()

        self.stdout.write(f"Found {total_count} document(s) in Trash")

        # Process each document
        deleted_count = 0
        skipped_hold = 0
        skipped_not_expired = 0
        skipped_no_policy = 0
        errors = 0

        now = timezone.now()

        for doc in trash_documents:
            try:
                result = self._process_document(
                    doc, policies, now, dry_run, force, verbose
                )
                if result == "deleted":
                    deleted_count += 1
                elif result == "hold":
                    skipped_hold += 1
                elif result == "not_expired":
                    skipped_not_expired += 1
                elif result == "no_policy":
                    skipped_no_policy += 1
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"Error processing {doc.filename}: {e}")
                )

        # Summary
        self.stdout.write("")
        self.stdout.write("=" * 50)
        self.stdout.write(self.style.SUCCESS(f"Summary:"))
        action = "Would delete" if dry_run else "Deleted"
        self.stdout.write(f"  {action}: {deleted_count}")
        self.stdout.write(f"  Skipped (legal hold): {skipped_hold}")
        self.stdout.write(f"  Skipped (not expired): {skipped_not_expired}")
        if not force:
            self.stdout.write(f"  Skipped (no policy): {skipped_no_policy}")
        if errors:
            self.stdout.write(self.style.ERROR(f"  Errors: {errors}"))

    def _process_document(self, doc, policies, now, dry_run, force, verbose):
        """Process a single document for potential deletion.

        Returns:
            'deleted' - document was deleted
            'hold' - skipped due to legal hold
            'not_expired' - retention period not yet expired
            'no_policy' - no policy and force not specified
        """
        # Check for legal hold
        if DocumentLegalHold.document_has_active_hold(doc):
            if verbose:
                self.stdout.write(
                    self.style.WARNING(f"  HOLD: {doc.filename} - has active legal hold")
                )
            return "hold"

        # Get deletion timestamp from metadata
        metadata = doc.metadata or {}
        deleted_at_str = metadata.get("deleted_at")

        if not deleted_at_str:
            # No deletion timestamp - use created_at as fallback
            deleted_at = doc.created_at
        else:
            # Parse ISO timestamp
            from datetime import datetime
            try:
                deleted_at = datetime.fromisoformat(deleted_at_str.replace("Z", "+00:00"))
                if deleted_at.tzinfo is None:
                    deleted_at = timezone.make_aware(deleted_at)
            except (ValueError, TypeError):
                deleted_at = doc.created_at

        # Determine retention period
        policy = policies.get(doc.document_type)
        if policy:
            retention_days = policy.trash_retention_days
        elif force:
            retention_days = DEFAULT_TRASH_RETENTION_DAYS
        else:
            if verbose:
                self.stdout.write(
                    f"  SKIP: {doc.filename} - no policy for type '{doc.document_type}'"
                )
            return "no_policy"

        # Check if retention period expired
        expiry_date = deleted_at + timedelta(days=retention_days)
        if now < expiry_date:
            days_left = (expiry_date - now).days
            if verbose:
                self.stdout.write(
                    f"  WAIT: {doc.filename} - {days_left} days until expiry"
                )
            return "not_expired"

        # Document is eligible for deletion
        days_in_trash = (now - deleted_at).days
        policy_info = f"policy: {policy.document_type}" if policy else "default: 30 days"

        if dry_run:
            self.stdout.write(
                f"  DELETE: {doc.filename} ({days_in_trash} days in trash, {policy_info})"
            )
            return "deleted"

        # Actually delete
        with transaction.atomic():
            # Log to audit before deletion
            log(
                action="retention_purge",
                obj=doc,
                metadata={
                    "reason": "Automatic trash purge - retention period expired",
                    "days_in_trash": days_in_trash,
                    "retention_policy": policy.document_type if policy else "default",
                    "retention_days": retention_days,
                    "original_folder": metadata.get("original_folder_name"),
                    "deleted_by_user": metadata.get("deleted_by"),
                },
                sensitivity="high",
                is_system=True,
            )

            # Hard delete
            doc.hard_delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"  PURGED: {doc.filename} ({days_in_trash} days, {policy_info})"
            )
        )
        return "deleted"
