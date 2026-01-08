"""Management command to seed CMS content."""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from django_cms_core.models import CMSSettings, ContentPage, AccessLevel, PageStatus
from django_cms_core.services import create_page, add_block, publish_page


User = get_user_model()


class Command(BaseCommand):
    help = "Seed CMS settings and initial pages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing pages and recreate",
        )

    def handle(self, *args, **options):
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR("No superuser found. Create one first."))
            return

        settings = CMSSettings.get_instance()
        settings.site_name = "Blue Water Dive Shop"
        settings.default_seo_title_suffix = " | Blue Water Dive Shop"
        settings.save()
        self.stdout.write(self.style.SUCCESS("CMSSettings configured"))

        pages_config = [
            {
                "slug": "home",
                "title": "Welcome to Blue Water Dive Shop",
                "access_level": AccessLevel.PUBLIC,
                "blocks": [
                    {
                        "type": "hero",
                        "data": {
                            "title": "Discover the Underwater World",
                            "subtitle": "Professional dive training, guided excursions, and equipment rentals",
                            "cta_text": "Book a Dive",
                            "cta_url": "/staff/diveops/",
                        },
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": "<p>Welcome to Blue Water Dive Shop, your gateway to underwater adventure. Whether you're a beginner looking to get certified or an experienced diver seeking new thrills, we have something for everyone.</p>",
                        },
                    },
                    {
                        "type": "heading",
                        "data": {"text": "Our Services", "level": 2},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": "<ul><li><strong>Certification Courses</strong> - From Open Water to Divemaster</li><li><strong>Guided Excursions</strong> - Daily boat trips to local reefs</li><li><strong>Equipment Rental</strong> - Full gear packages available</li><li><strong>Air Fills</strong> - Nitrox and standard air</li></ul>",
                        },
                    },
                ],
            },
            {
                "slug": "courses",
                "title": "Dive Courses",
                "access_level": AccessLevel.PUBLIC,
                "blocks": [
                    {
                        "type": "heading",
                        "data": {"text": "Learn to Dive with Us", "level": 1},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": "<p>We offer a full range of PADI and SSI certification courses, from beginner to professional levels.</p>",
                        },
                    },
                    {
                        "type": "heading",
                        "data": {"text": "Beginner Courses", "level": 2},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": "<ul><li><strong>Discover Scuba</strong> - Try diving in a pool</li><li><strong>Open Water Diver</strong> - Your first certification</li><li><strong>Advanced Open Water</strong> - Expand your skills</li></ul>",
                        },
                    },
                ],
            },
            {
                "slug": "about",
                "title": "About Us",
                "access_level": AccessLevel.PUBLIC,
                "blocks": [
                    {
                        "type": "heading",
                        "data": {"text": "Our Story", "level": 1},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": "<p>Blue Water Dive Shop has been serving divers since 2010. Located in the heart of the Caribbean, we offer world-class diving experiences for all skill levels.</p>",
                        },
                    },
                    {
                        "type": "heading",
                        "data": {"text": "Our Team", "level": 2},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": "<p>Our team of experienced instructors and divemasters are passionate about sharing the underwater world with you. We prioritize safety while ensuring you have an unforgettable experience.</p>",
                        },
                    },
                ],
            },
            {
                "slug": "contact",
                "title": "Contact Us",
                "access_level": AccessLevel.PUBLIC,
                "blocks": [
                    {
                        "type": "heading",
                        "data": {"text": "Get in Touch", "level": 1},
                    },
                    {
                        "type": "rich_text",
                        "data": {
                            "content": "<p><strong>Address:</strong> 123 Ocean Drive, Cozumel, Mexico</p><p><strong>Phone:</strong> +52 987 869 1234</p><p><strong>Email:</strong> info@bluewaterdive.shop</p><p><strong>Hours:</strong> Mon-Sat 8:00 AM - 6:00 PM</p>",
                        },
                    },
                    {
                        "type": "divider",
                        "data": {},
                    },
                    {
                        "type": "cta",
                        "data": {
                            "text": "Book Your Dive Today",
                            "url": "/staff/diveops/",
                        },
                    },
                ],
            },
        ]

        for config in pages_config:
            slug = config["slug"]

            existing = ContentPage.objects.filter(slug=slug, deleted_at__isnull=True).first()

            if existing:
                if options["force"]:
                    existing.delete()
                    self.stdout.write(f"  Deleted existing page: {slug}")
                else:
                    self.stdout.write(f"  Skipping existing page: {slug}")
                    continue

            page = create_page(
                slug=slug,
                title=config["title"],
                user=admin_user,
                access_level=config["access_level"],
            )

            for block_config in config["blocks"]:
                add_block(page, block_config["type"], block_config["data"])

            publish_page(page, admin_user)

            self.stdout.write(self.style.SUCCESS(f"  Created and published: {slug}"))

        self.stdout.write(self.style.SUCCESS("\nCMS seed complete!"))
