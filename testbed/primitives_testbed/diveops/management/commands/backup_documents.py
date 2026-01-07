"""Management command to backup documents to ZIP archive or S3.

Usage examples:
    # Backup all documents to a ZIP file
    python manage.py backup_documents --output /path/to/backup.zip

    # Backup specific folders
    python manage.py backup_documents --folders abc123 def456 --output backup.zip

    # Sync to S3
    python manage.py backup_documents --s3-bucket my-bucket --s3-prefix backups/

    # Sync specific folders to S3
    python manage.py backup_documents --folders abc123 --s3-bucket my-bucket

    # Include trash in backup
    python manage.py backup_documents --include-trash --output backup.zip
"""

from django.core.management.base import BaseCommand

from primitives_testbed.diveops.document_backup import (
    backup_documents,
    sync_to_s3,
    get_backup_stats,
)


class Command(BaseCommand):
    help = "Backup documents to ZIP archive or sync to S3"

    def add_arguments(self, parser):
        # Output options
        parser.add_argument(
            "--output", "-o",
            type=str,
            help="Output path for ZIP archive (if not using S3)",
        )

        # Selection options
        parser.add_argument(
            "--folders",
            nargs="+",
            type=str,
            help="Specific folder UUIDs to include (with all contents)",
        )
        parser.add_argument(
            "--documents",
            nargs="+",
            type=str,
            help="Specific document UUIDs to include",
        )
        parser.add_argument(
            "--include-trash",
            action="store_true",
            help="Include Trash folder in backup",
        )

        # S3 options
        parser.add_argument(
            "--s3-bucket",
            type=str,
            help="S3 bucket name for sync (requires boto3)",
        )
        parser.add_argument(
            "--s3-prefix",
            type=str,
            default="document-backup/",
            help="S3 key prefix (default: document-backup/)",
        )
        parser.add_argument(
            "--s3-delete",
            action="store_true",
            help="Delete S3 objects not in current selection (sync delete)",
        )

        # Other options
        parser.add_argument(
            "--no-manifest",
            action="store_true",
            help="Skip generating manifest.json in ZIP",
        )
        parser.add_argument(
            "--stats-only",
            action="store_true",
            help="Only show statistics, don't perform backup",
        )

    def handle(self, *args, **options):
        # Stats only mode
        if options["stats_only"]:
            stats = get_backup_stats()
            self.stdout.write(self.style.NOTICE("Document Backup Statistics"))
            self.stdout.write("=" * 50)
            self.stdout.write(f"  Total folders: {stats['total_folders']}")
            self.stdout.write(f"  Total documents: {stats['total_documents']}")
            self.stdout.write(f"  Documents in Trash: {stats['trash_documents']}")
            self.stdout.write(f"  Unfiled documents: {stats['orphan_documents']}")
            self.stdout.write(f"  Estimated size: {self._format_size(stats['estimated_size'])}")
            return

        # S3 sync mode
        if options["s3_bucket"]:
            self._handle_s3_sync(options)
            return

        # ZIP backup mode
        self._handle_zip_backup(options)

    def _handle_zip_backup(self, options):
        self.stdout.write(self.style.NOTICE("Creating ZIP backup..."))

        output_path = backup_documents(
            output_path=options["output"],
            include_trash=options["include_trash"],
            include_metadata=not options["no_manifest"],
            folder_ids=options["folders"],
            document_ids=options["documents"],
        )

        self.stdout.write(self.style.SUCCESS(f"Backup created: {output_path}"))

    def _handle_s3_sync(self, options):
        bucket = options["s3_bucket"]
        prefix = options["s3_prefix"]

        self.stdout.write(self.style.NOTICE(f"Syncing to S3: s3://{bucket}/{prefix}"))

        try:
            stats = sync_to_s3(
                bucket=bucket,
                prefix=prefix,
                include_trash=options["include_trash"],
                folder_ids=options["folders"],
                document_ids=options["documents"],
                delete_removed=options["s3_delete"],
            )

            self.stdout.write("")
            self.stdout.write("=" * 50)
            self.stdout.write(self.style.SUCCESS("S3 Sync Complete"))
            self.stdout.write(f"  Uploaded: {stats['uploaded']}")
            self.stdout.write(f"  Skipped (unchanged): {stats['skipped']}")
            if options["s3_delete"]:
                self.stdout.write(f"  Deleted: {stats['deleted']}")
            if stats["errors"]:
                self.stdout.write(self.style.ERROR(f"  Errors: {stats['errors']}"))
            self.stdout.write(f"  Total size uploaded: {self._format_size(stats['total_size'])}")

        except ImportError as e:
            self.stdout.write(self.style.ERROR(str(e)))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"S3 sync failed: {e}"))

    def _format_size(self, size_bytes):
        """Format size in human-readable form."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
