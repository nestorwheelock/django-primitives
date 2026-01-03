"""Notes scenario: Note, Tag, ObjectTag for tagging parties/encounters."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction

from django_notes.models import Note, Tag, ObjectTag
from django_parties.models import Person


User = get_user_model()


def seed():
    """Create sample notes data."""
    count = 0

    user = User.objects.first()

    # Create tags
    urgent, created = Tag.objects.get_or_create(
        slug="urgent",
        defaults={"name": "Urgent", "color": "#FF0000"}
    )
    if created:
        count += 1

    followup, created = Tag.objects.get_or_create(
        slug="follow-up",
        defaults={"name": "Follow Up", "color": "#FFA500"}
    )
    if created:
        count += 1

    vip, created = Tag.objects.get_or_create(
        slug="vip",
        defaults={"name": "VIP", "color": "#FFD700"}
    )
    if created:
        count += 1

    person = Person.objects.first()
    if person:
        person_ct = ContentType.objects.get_for_model(Person)

        # Create notes attached to person
        existing1 = Note.objects.filter(
            target_content_type=person_ct,
            target_id=str(person.pk),
            content__startswith="Initial consultation",
        ).exists()
        if not existing1:
            note1 = Note.objects.create(
                target_content_type=person_ct,
                target_id=str(person.pk),
                content="Initial consultation completed. Patient reported mild symptoms.",
                author=user,
                visibility="internal",
            )
            count += 1

        existing2 = Note.objects.filter(
            target_content_type=person_ct,
            target_id=str(person.pk),
            content__startswith="Follow-up required",
        ).exists()
        if not existing2:
            note2 = Note.objects.create(
                target_content_type=person_ct,
                target_id=str(person.pk),
                content="Follow-up required in 2 weeks.",
                author=user,
                visibility="public",
            )
            count += 1

        # Apply tags to person
        ObjectTag.objects.get_or_create(
            target_content_type=person_ct,
            target_id=str(person.pk),
            tag=vip,
            defaults={"tagged_by": user}
        )
        ObjectTag.objects.get_or_create(
            target_content_type=person_ct,
            target_id=str(person.pk),
            tag=followup,
            defaults={"tagged_by": user}
        )
        count += 2

    return count


def verify():
    """Verify notes constraints with negative writes."""
    results = []

    # Test 1: Tag slug must be unique
    try:
        with transaction.atomic():
            Tag.objects.create(
                name="Duplicate Urgent",
                slug="urgent",  # Already exists
                color="#00FF00",
            )
        results.append(("tag_slug_unique", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("tag_slug_unique", True, "Correctly rejected duplicate slug"))

    # Test 2: ObjectTag unique per target + tag
    person = Person.objects.first()
    tag = Tag.objects.filter(slug="vip").first()

    if person and tag:
        person_ct = ContentType.objects.get_for_model(Person)

        # Check if tag already applied
        existing = ObjectTag.objects.filter(
            target_content_type=person_ct,
            target_id=str(person.pk),
            tag=tag,
        ).exists()

        if existing:
            try:
                with transaction.atomic():
                    ObjectTag.objects.create(
                        target_content_type=person_ct,
                        target_id=str(person.pk),
                        tag=tag,  # Duplicate
                    )
                results.append(("objecttag_unique_per_target", False, "Should have raised IntegrityError"))
            except IntegrityError:
                results.append(("objecttag_unique_per_target", True, "Correctly rejected duplicate tag"))
        else:
            results.append(("objecttag_unique_per_target", None, "Skipped - no existing tag"))
    else:
        results.append(("objecttag_unique_per_target", None, "Skipped - no test data"))

    return results
