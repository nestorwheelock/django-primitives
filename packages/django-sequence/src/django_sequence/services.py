"""Sequence services for atomic sequence generation."""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from django_sequence.models import Sequence
from django_sequence.exceptions import SequenceNotFoundError


def next_sequence(
    scope: str,
    org=None,
    prefix: str = '',
    pad_width: int = 6,
    include_year: bool = True,
    auto_create: bool = True,
) -> str:
    """
    Get the next sequence value atomically.

    Uses select_for_update() to prevent race conditions when multiple
    requests try to get the next value simultaneously.

    Args:
        scope: The sequence scope (e.g., 'invoice', 'order')
        org: The organization instance (None for global sequences)
        prefix: Prefix for the formatted value (used when auto-creating)
        pad_width: Zero-padding width (used when auto-creating)
        include_year: Whether to include year in formatted value (used when auto-creating)
        auto_create: If True, create sequence if it doesn't exist

    Returns:
        The formatted sequence value (e.g., "INV-2026-000001")

    Raises:
        SequenceNotFoundError: If sequence doesn't exist and auto_create is False

    Usage:
        # Get next invoice number
        invoice_number = next_sequence('invoice', org=my_org)

        # Create sequence with custom settings if it doesn't exist
        order_number = next_sequence(
            'order',
            org=my_org,
            prefix='ORD-',
            pad_width=8,
            include_year=True,
        )
    """
    # Determine org content type and ID
    if org is not None:
        org_content_type = ContentType.objects.get_for_model(org)
        org_id = str(org.pk)
    else:
        org_content_type = None
        org_id = ''

    with transaction.atomic():
        # Try to get existing sequence with lock
        try:
            seq = Sequence.objects.select_for_update().get(
                scope=scope,
                org_content_type=org_content_type,
                org_id=org_id,
            )
        except Sequence.DoesNotExist:
            if not auto_create:
                raise SequenceNotFoundError(
                    f"Sequence '{scope}' not found for org '{org_id or 'global'}'"
                )

            # Create new sequence with defaults
            seq = Sequence.objects.create(
                scope=scope,
                org_content_type=org_content_type,
                org_id=org_id,
                prefix=prefix,
                current_value=0,
                pad_width=pad_width,
                include_year=include_year,
            )

            # Lock the newly created sequence
            seq = Sequence.objects.select_for_update().get(pk=seq.pk)

        # Increment and save
        seq.current_value += 1
        seq.save(update_fields=['current_value', 'updated_at'])

        return seq.formatted_value
