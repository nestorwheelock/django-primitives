"""QuerySet helpers for time-based queries."""
from django.db import models
from django.db.models import Q
from django.utils import timezone


class EventAsOfQuerySet(models.QuerySet):
    """
    QuerySet for append-only events (AuditLog, Entry, Transition).

    Use this for facts that represent points in time.
    Query pattern: effective_at <= timestamp

    From TIME_SEMANTICS.md:
    - Events are append-only facts
    - Use effective_at <= ts to find events that were effective at a given time
    """

    def as_of(self, timestamp):
        """
        Return events where effective_at <= timestamp.

        Args:
            timestamp: The datetime to query as of

        Returns:
            QuerySet filtered to events effective at or before the timestamp
        """
        return self.filter(effective_at__lte=timestamp)


class EffectiveDatedQuerySet(models.QuerySet):
    """
    QuerySet for records with validity periods (Role assignments, Agreements).

    Use this for records that are valid for a range of time.
    Query pattern: valid_from <= ts AND (valid_to IS NULL OR valid_to > ts)

    From TIME_SEMANTICS.md:
    - Effective-dated records have a validity period
    - Use valid_from/valid_to to determine if a record was valid at a given time
    """

    def as_of(self, timestamp):
        """
        Return records that were valid at the given timestamp.

        Args:
            timestamp: The datetime to query as of

        Returns:
            QuerySet filtered to records valid at the timestamp
        """
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=timestamp)
        )

    def current(self):
        """
        Return currently valid records.

        Convenience method equivalent to as_of(timezone.now()).

        Returns:
            QuerySet filtered to records valid now
        """
        return self.as_of(timezone.now())
