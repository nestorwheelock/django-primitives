"""Seed command for RSTC Medical Questionnaire.

Imports the RSTC medical questionnaire template from JSON and publishes it.
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from django_questionnaires.services import import_definition_from_json, publish_definition
from django_questionnaires.models import QuestionnaireDefinition, DefinitionStatus


class Command(BaseCommand):
    help = "Seed the RSTC Medical Questionnaire from template file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-import even if already exists",
        )
        parser.add_argument(
            "--draft-only",
            action="store_true",
            help="Import as draft only, do not publish",
        )

    def handle(self, *args, **options):
        json_path = (
            Path(__file__).parent.parent.parent
            / "medical"
            / "templates"
            / "rstc_medical_v1.json"
        )

        if not json_path.exists():
            self.stderr.write(
                self.style.ERROR(f"Template file not found: {json_path}")
            )
            return

        # Check if already exists
        slug = "rstc-medical"
        existing = QuestionnaireDefinition.objects.filter(
            slug=slug,
            deleted_at__isnull=True,
        ).exclude(status=DefinitionStatus.ARCHIVED).first()

        if existing and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Definition '{slug}' already exists (v{existing.version}, "
                    f"status: {existing.status}). Use --force to re-import."
                )
            )
            return

        if existing and options["force"]:
            self.stdout.write(f"Archiving existing definition: {existing}")
            existing.status = DefinitionStatus.ARCHIVED
            existing.save()

        # Import from JSON
        definition = import_definition_from_json(json_path, actor=None)
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported: {definition.name} v{definition.version} "
                f"({definition.questions.count()} questions)"
            )
        )

        # Publish if not draft-only
        if not options["draft_only"]:
            publish_definition(definition, actor=None)
            self.stdout.write(
                self.style.SUCCESS(f"Published: {definition.slug}")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"Keeping as draft: {definition.slug}")
            )

        self.stdout.write(self.style.SUCCESS("Done!"))
