"""CRM service layer for lead management.

Clean domain logic for lead pipeline operations.
Views should call these functions instead of manipulating models directly.
"""

from django.db import transaction
from django.utils import timezone

from django_parties.models import Person, LeadStatusEvent

from ..models import DiverProfile


def is_lead(person: Person) -> bool:
    """Check if a Person is a lead (has lead_status set)."""
    return person.lead_status is not None


@transaction.atomic
def set_lead_status(
    person: Person,
    new_status: str,
    actor=None,
    note: str = None,
    lost_reason: str = None,
) -> LeadStatusEvent:
    """Change a lead's pipeline status.

    Args:
        person: The Person record to update
        new_status: Target status (new, contacted, qualified, converted, lost)
        actor: User making the change (optional)
        note: Optional note about the status change
        lost_reason: Reason for loss (only used when new_status='lost')

    Returns:
        The created LeadStatusEvent

    Raises:
        ValueError: If new_status is invalid
    """
    valid_statuses = dict(Person.LEAD_STATUS_CHOICES).keys()
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {list(valid_statuses)}")

    old_status = person.lead_status

    # Update person
    person.lead_status = new_status
    update_fields = ["lead_status", "updated_at"]

    if new_status == "lost" and lost_reason:
        person.lead_lost_reason = lost_reason
        update_fields.append("lead_lost_reason")

    person.save(update_fields=update_fields)

    # Create audit event
    event = LeadStatusEvent.objects.create(
        person=person,
        from_status=old_status or "",
        to_status=new_status,
        actor=actor,
        note=note or "",
    )

    return event


@transaction.atomic
def convert_to_diver(person: Person, actor=None) -> DiverProfile:
    """Convert a lead to a diver.

    Creates a DiverProfile if one doesn't exist, sets lead_status to 'converted',
    and records the conversion timestamp.

    Args:
        person: The Person record to convert
        actor: User performing the conversion (optional)

    Returns:
        The DiverProfile (created or existing)

    Raises:
        ValueError: If person is not a lead
    """
    if not is_lead(person):
        raise ValueError("Person is not a lead (lead_status is null)")

    old_status = person.lead_status

    # Create or get DiverProfile
    # Parse experience from notes if available
    total_dives = 0
    notes = person.notes or ""
    if "Never dived" in notes:
        total_dives = 0
    elif "1-10" in notes:
        total_dives = 5
    elif "10-50" in notes:
        total_dives = 30
    elif "50+" in notes:
        total_dives = 75

    diver_profile, created = DiverProfile.objects.get_or_create(
        person=person,
        defaults={"total_dives": total_dives},
    )

    # Update lead status
    person.lead_status = "converted"
    person.lead_converted_at = timezone.now()
    person.save(update_fields=["lead_status", "lead_converted_at", "updated_at"])

    # Record status event
    LeadStatusEvent.objects.create(
        person=person,
        from_status=old_status or "",
        to_status="converted",
        actor=actor,
        note=f"Converted to diver. DiverProfile {'created' if created else 'already existed'}.",
    )

    return diver_profile


def add_lead_note(person: Person, body: str, author=None):
    """Add a note to a lead.

    Args:
        person: The Person record
        body: Note text
        author: User creating the note (optional)

    Returns:
        The created LeadNote
    """
    from django_parties.models import LeadNote

    return LeadNote.objects.create(
        person=person,
        body=body,
        author=author,
    )


def get_lead_notes(person: Person):
    """Get all notes for a lead, newest first.

    Args:
        person: The Person record

    Returns:
        QuerySet of LeadNote objects
    """
    from django_parties.models import LeadNote

    return LeadNote.objects.filter(person=person).select_related("author").order_by("-created_at")


def get_lead_timeline(person: Person):
    """Get combined timeline of status events and notes for a lead.

    Args:
        person: The Person record

    Returns:
        List of events/notes sorted by created_at descending
    """
    from django_parties.models import LeadNote

    events = list(
        LeadStatusEvent.objects.filter(person=person)
        .select_related("actor")
        .order_by("-created_at")
    )
    notes = list(
        LeadNote.objects.filter(person=person)
        .select_related("author")
        .order_by("-created_at")
    )

    # Combine and sort
    timeline = []
    for event in events:
        timeline.append({
            "type": "status_change",
            "created_at": event.created_at,
            "actor": event.actor,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "note": event.note,
            "obj": event,
        })
    for note in notes:
        timeline.append({
            "type": "note",
            "created_at": note.created_at,
            "actor": note.author,
            "body": note.body,
            "obj": note,
        })

    timeline.sort(key=lambda x: x["created_at"], reverse=True)
    return timeline
