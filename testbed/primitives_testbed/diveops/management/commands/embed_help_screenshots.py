"""Management command to embed screenshots into help center articles."""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from django_cms_core.models import ContentPage, ContentBlock, PageStatus


# Map help articles to their screenshot files
ARTICLE_SCREENSHOTS = {
    # Getting Started
    ("getting-started", "dashboard-overview"): "getting-started-dashboard-overview.png",
    ("getting-started", "navigation-guide"): "getting-started-dashboard-overview.png",
    ("getting-started", "your-account"): None,  # No specific page

    # Divers
    ("divers", "creating-profiles"): "divers-creating-profiles.png",
    ("divers", "managing-certifications"): "divers-creating-profiles.png",
    ("divers", "emergency-contacts"): "divers-creating-profiles.png",
    ("divers", "diver-categories"): "divers-creating-profiles.png",

    # Bookings & Excursions
    ("bookings", "scheduling-excursions"): "bookings-scheduling-excursions.png",
    ("bookings", "managing-bookings"): "bookings-scheduling-excursions.png",
    ("bookings", "check-in-process"): "bookings-scheduling-excursions.png",
    ("bookings", "recurring-series"): "bookings-recurring-series.png",
    ("bookings", "cancellations-refunds"): "bookings-scheduling-excursions.png",

    # Agreements & Waivers
    ("agreements", "creating-agreements"): "agreements-creating-agreements.png",
    ("agreements", "sending-for-signature"): "agreements-creating-agreements.png",
    ("agreements", "tracking-status"): "agreements-creating-agreements.png",
    ("agreements", "voiding-agreements"): "agreements-creating-agreements.png",

    # Medical Records
    ("medical", "medical-questionnaires"): "medical-medical-questionnaires.png",
    ("medical", "reviewing-responses"): "medical-medical-questionnaires.png",
    ("medical", "clearance-process"): "medical-medical-questionnaires.png",
    ("medical", "retention-policies"): "medical-medical-questionnaires.png",

    # Protected Areas
    ("protected-areas", "managing-permits"): "protected-areas-managing-permits.png",
    ("protected-areas", "fee-schedules"): "protected-areas-managing-permits.png",
    ("protected-areas", "zone-rules"): "protected-areas-managing-permits.png",

    # System
    ("system", "document-management"): "system-document-management.png",
    ("system", "audit-log"): "system-audit-log.png",
    ("system", "ai-settings"): "system-ai-settings.png",
}

# Captions for screenshots
SCREENSHOT_CAPTIONS = {
    "getting-started-dashboard-overview.png": "The Staff Dashboard provides an overview of your dive operations",
    "divers-creating-profiles.png": "The Divers list shows all registered divers and their status",
    "bookings-scheduling-excursions.png": "The Excursions page displays all scheduled dive trips",
    "bookings-recurring-series.png": "Recurring series allow you to schedule repeating excursions",
    "agreements-creating-agreements.png": "The Agreements page tracks all liability waivers and forms",
    "medical-medical-questionnaires.png": "Medical questionnaires help ensure diver safety",
    "protected-areas-managing-permits.png": "Protected Areas management for marine park permits",
    "system-document-management.png": "The Document Browser organizes your files and folders",
    "system-audit-log.png": "The Audit Log tracks all system activity",
    "system-ai-settings.png": "Configure AI assistance features",
}


class Command(BaseCommand):
    """Embed screenshots into help center articles."""

    help = "Add screenshot images to help center articles in the CMS"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--media-url",
            default="/media/help/screenshots/",
            help="URL prefix for screenshot images",
        )

    def handle(self, *args, **options):
        """Embed screenshots into help articles."""
        dry_run = options.get("dry_run", False)
        media_url = options.get("media_url", "/media/help/screenshots/")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made\n"))

        updated_count = 0
        skipped_count = 0

        for (section_slug, article_slug), screenshot_file in ARTICLE_SCREENSHOTS.items():
            cms_slug = f"help-{section_slug}-{article_slug}"

            # Skip articles without screenshots
            if not screenshot_file:
                self.stdout.write(f"  Skipped: {cms_slug} (no screenshot)")
                skipped_count += 1
                continue

            # Find the content page
            try:
                page = ContentPage.objects.get(
                    slug=cms_slug,
                    deleted_at__isnull=True,
                )
            except ContentPage.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"  Not found: {cms_slug}")
                )
                skipped_count += 1
                continue

            # Check if screenshot block already exists
            existing_image_block = ContentBlock.objects.filter(
                page=page,
                block_type="image",
                data__url__contains=screenshot_file,
            ).exists()

            if existing_image_block:
                self.stdout.write(f"  Already has image: {cms_slug}")
                skipped_count += 1
                continue

            # Build image URL and caption
            image_url = f"{media_url}{screenshot_file}"
            caption = SCREENSHOT_CAPTIONS.get(screenshot_file, "")

            self.stdout.write(f"  Updating: {cms_slug}")
            self.stdout.write(f"    Image: {image_url}")

            if dry_run:
                continue

            # Get existing blocks
            blocks = list(page.blocks.order_by("sequence"))

            # Shift existing blocks down
            for block in blocks:
                block.sequence += 1
                block.save(update_fields=["sequence"])

            # Create new image block at sequence 0 (top of article)
            ContentBlock.objects.create(
                page=page,
                block_type="image",
                data={
                    "url": image_url,
                    "alt": f"Screenshot of {article_slug.replace('-', ' ').title()}",
                    "caption": caption,
                },
                sequence=0,
                is_active=True,
            )

            # Update published snapshot if page is published
            if page.status == PageStatus.PUBLISHED:
                # Rebuild snapshot with new blocks
                new_blocks_data = []

                # Add image block first
                new_blocks_data.append({
                    "type": "image",
                    "data": {
                        "url": image_url,
                        "alt": f"Screenshot of {article_slug.replace('-', ' ').title()}",
                        "caption": caption,
                    },
                })

                # Add existing blocks from snapshot
                if page.published_snapshot:
                    existing_blocks = page.published_snapshot.get("blocks", [])
                    new_blocks_data.extend(existing_blocks)

                page.published_snapshot = {"blocks": new_blocks_data}
                page.published_at = timezone.now()
                page.save(update_fields=["published_snapshot", "published_at"])

            updated_count += 1

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN complete. Would update {updated_count} articles.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Done! Updated {updated_count} articles, skipped {skipped_count}.")
            )
