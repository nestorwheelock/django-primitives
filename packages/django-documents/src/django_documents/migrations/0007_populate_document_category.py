# Generated manually for data migration

from django.db import migrations


def detect_category_from_content_type(apps, schema_editor):
    """
    Detect and set category based on content_type for existing documents.

    Categories:
    - image/* -> "image"
    - video/* -> "video"
    - audio/* -> "audio"
    - everything else -> "document" (default, no change needed)
    """
    Document = apps.get_model("django_documents", "Document")

    # Update images
    Document.objects.filter(content_type__startswith="image/").update(category="image")

    # Update videos
    Document.objects.filter(content_type__startswith="video/").update(category="video")

    # Update audio
    Document.objects.filter(content_type__startswith="audio/").update(category="audio")


def reverse_category_detection(apps, schema_editor):
    """
    Reverse migration - reset all categories to default.
    """
    Document = apps.get_model("django_documents", "Document")
    Document.objects.all().update(category="document")


class Migration(migrations.Migration):

    dependencies = [
        ("django_documents", "0006_document_category_document_folder_and_more"),
    ]

    operations = [
        migrations.RunPython(
            detect_category_from_content_type,
            reverse_category_detection,
        ),
    ]
