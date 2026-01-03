"""Management command to clean up expired idempotency keys."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from django_decisioning.models import IdempotencyKey


class Command(BaseCommand):
    help = 'Delete expired idempotency keys to prevent unbounded table growth'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete keys older than this many days (default: 7)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show count of keys that would be deleted without actually deleting'
        )
        parser.add_argument(
            '--include-processing',
            action='store_true',
            help='Also delete stale processing keys (may cause duplicate operations)'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        include_processing = options['include_processing']
        cutoff = timezone.now() - timedelta(days=days)

        # Build query: keys older than cutoff OR past their expires_at
        qs = IdempotencyKey.objects.filter(
            Q(created_at__lt=cutoff) | Q(expires_at__lt=timezone.now())
        )

        # By default, exclude processing keys (they might be in-flight)
        if not include_processing:
            qs = qs.exclude(state=IdempotencyKey.State.PROCESSING)

        count = qs.count()

        if dry_run:
            self.stdout.write(
                f'Would delete {count} idempotency keys '
                f'(older than {days} days or past expires_at)'
            )
            # Show breakdown by state
            for state in IdempotencyKey.State:
                state_count = qs.filter(state=state).count()
                if state_count > 0:
                    self.stdout.write(f'  - {state.label}: {state_count}')
        else:
            deleted, _ = qs.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Deleted {deleted} expired idempotency keys')
            )
