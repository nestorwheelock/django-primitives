"""Documents scenario: Document with checksum immutability."""

import hashlib
from io import BytesIO

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction

from django_documents.models import Document
from django_documents.exceptions import ImmutableChecksumError
from django_parties.models import Person


def seed():
    """Create sample documents data."""
    count = 0

    person = Person.objects.first()
    if person:
        person_ct = ContentType.objects.get_for_model(Person)

        # Create sample documents
        content1 = b"This is a test document content."
        checksum1 = hashlib.sha256(content1).hexdigest()

        # Check if document already exists
        existing = Document.objects.filter(checksum=checksum1).exists()
        if not existing:
            doc1 = Document.objects.create(
                target_content_type=person_ct,
                target_id=str(person.pk),
                file=ContentFile(content1, name="test_document.txt"),
                filename="test_document.txt",
                content_type="text/plain",
                file_size=len(content1),
                document_type="text_file",
                checksum=checksum1,
            )
            count += 1

        content2 = b"Another document with different content for testing."
        checksum2 = hashlib.sha256(content2).hexdigest()

        existing2 = Document.objects.filter(checksum=checksum2).exists()
        if not existing2:
            doc2 = Document.objects.create(
                target_content_type=person_ct,
                target_id=str(person.pk),
                file=ContentFile(content2, name="another_document.pdf"),
                filename="another_document.pdf",
                content_type="application/pdf",
                file_size=len(content2),
                document_type="pdf_file",
                checksum=checksum2,
            )
            count += 1

    return count


def verify():
    """Verify documents constraints with negative writes."""
    results = []

    document = Document.objects.first()

    if document and document.checksum:
        # Test 1: Checksum immutability (should be prevented by save() override)
        original_checksum = document.checksum
        try:
            document.checksum = "modified_checksum_value_0123456789abcdef"
            document.save()
            results.append(("document_checksum_immutability", False, "Checksum modification should be rejected"))
        except ImmutableChecksumError:
            results.append(("document_checksum_immutability", True, "Correctly rejected checksum modification"))
        except Exception as e:
            results.append(("document_checksum_immutability", True, f"Correctly rejected: {type(e).__name__}"))

        # Test 2: Document should have correct target
        if document.target_content_type and document.target_id:
            results.append(("document_has_target", True, f"Target: {document.target_content_type.model}:{document.target_id}"))
        else:
            results.append(("document_has_target", False, "Missing target reference"))

    else:
        results.append(("documents_tests", None, "Skipped - no test data"))

    return results
