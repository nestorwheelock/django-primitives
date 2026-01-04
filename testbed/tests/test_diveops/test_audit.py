"""Tests for diveops audit logging.

These tests verify that ALL mutation paths emit audit events.
This is a MANDATORY requirement - no mutations without audit trails.
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from django_audit_log.models import AuditLog
from primitives_testbed.diveops.audit import Actions
from primitives_testbed.diveops.models import (
    Booking,
    DiverCertification,
    DiverProfile,
    DiveTrip,
    TripRoster,
)

User = get_user_model()


@pytest.fixture
def audit_user(db):
    """User for audit actor tracking."""
    return User.objects.create_user(
        username="audit_actor",
        email="audit@example.com",
        password="testpass123",
    )


@pytest.fixture
def clear_audit_log(db):
    """Clear audit log before each test."""
    AuditLog.objects.all().delete()
    yield
    # Clean up after test too
    AuditLog.objects.all().delete()


# =============================================================================
# Booking Audit Tests
# =============================================================================


@pytest.mark.django_db
class TestBookingAudit:
    """Tests for booking-related audit events."""

    def test_book_trip_emits_audit_event(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """book_trip() MUST emit BOOKING_CREATED audit event."""
        from primitives_testbed.diveops.services import book_trip

        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )

        # Verify audit event was emitted
        audit_entry = AuditLog.objects.filter(action=Actions.BOOKING_CREATED).first()
        assert audit_entry is not None, "BOOKING_CREATED audit event not emitted"
        assert str(audit_entry.object_id) == str(booking.pk)
        assert audit_entry.actor_user == audit_user

    def test_book_trip_audit_contains_required_metadata(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """book_trip() audit event MUST contain trip_id and diver_id in metadata."""
        from primitives_testbed.diveops.services import book_trip

        book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )

        audit_entry = AuditLog.objects.get(action=Actions.BOOKING_CREATED)
        metadata = audit_entry.metadata

        assert "trip_id" in metadata, "trip_id missing from audit metadata"
        assert "diver_id" in metadata, "diver_id missing from audit metadata"
        assert metadata["trip_id"] == str(dive_trip.pk)
        assert metadata["diver_id"] == str(diver_profile.pk)

    def test_cancel_booking_emits_audit_event(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """cancel_booking() MUST emit BOOKING_CANCELLED audit event."""
        from primitives_testbed.diveops.services import book_trip, cancel_booking

        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )

        # Clear the booking created event
        AuditLog.objects.filter(action=Actions.BOOKING_CREATED).delete()

        cancel_booking(booking, audit_user)

        audit_entry = AuditLog.objects.filter(action=Actions.BOOKING_CANCELLED).first()
        assert audit_entry is not None, "BOOKING_CANCELLED audit event not emitted"
        assert str(audit_entry.object_id) == str(booking.pk)


# =============================================================================
# Check-in Audit Tests
# =============================================================================


@pytest.mark.django_db
class TestCheckInAudit:
    """Tests for check-in audit events."""

    def test_check_in_emits_audit_event(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """check_in() MUST emit DIVER_CHECKED_IN audit event."""
        from primitives_testbed.diveops.services import book_trip, check_in

        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )

        # Clear booking audit events
        AuditLog.objects.all().delete()

        roster = check_in(booking, audit_user)

        audit_entry = AuditLog.objects.filter(action=Actions.DIVER_CHECKED_IN).first()
        assert audit_entry is not None, "DIVER_CHECKED_IN audit event not emitted"
        assert str(audit_entry.object_id) == str(roster.pk)

    def test_check_in_audit_contains_metadata(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """check_in() audit event MUST contain trip_id, diver_id, booking_id."""
        from primitives_testbed.diveops.services import book_trip, check_in

        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )

        AuditLog.objects.all().delete()
        check_in(booking, audit_user)

        audit_entry = AuditLog.objects.get(action=Actions.DIVER_CHECKED_IN)
        metadata = audit_entry.metadata

        assert "trip_id" in metadata
        assert "diver_id" in metadata
        assert "booking_id" in metadata


# =============================================================================
# Trip State Audit Tests
# =============================================================================


@pytest.mark.django_db
class TestTripStateAudit:
    """Tests for trip state transition audit events."""

    def test_start_trip_emits_audit_event(
        self, dive_trip, audit_user, clear_audit_log
    ):
        """start_trip() MUST emit TRIP_STARTED audit event."""
        from primitives_testbed.diveops.services import start_trip

        start_trip(dive_trip, audit_user)

        audit_entry = AuditLog.objects.filter(action=Actions.TRIP_STARTED).first()
        assert audit_entry is not None, "TRIP_STARTED audit event not emitted"
        assert str(audit_entry.object_id) == str(dive_trip.pk)

    def test_complete_trip_emits_trip_completed_event(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """complete_trip() MUST emit TRIP_COMPLETED audit event."""
        from primitives_testbed.diveops.services import (
            book_trip,
            check_in,
            complete_trip,
            start_trip,
        )

        # Setup: book, check-in, start
        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )
        check_in(booking, audit_user)
        start_trip(dive_trip, audit_user)

        # Clear previous audit events
        AuditLog.objects.all().delete()

        complete_trip(dive_trip, audit_user)

        audit_entry = AuditLog.objects.filter(action=Actions.TRIP_COMPLETED).first()
        assert audit_entry is not None, "TRIP_COMPLETED audit event not emitted"
        assert str(audit_entry.object_id) == str(dive_trip.pk)

    def test_complete_trip_emits_diver_completed_events(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """complete_trip() MUST emit DIVER_COMPLETED_TRIP for each roster entry."""
        from primitives_testbed.diveops.services import (
            book_trip,
            check_in,
            complete_trip,
            start_trip,
        )

        # Setup: book, check-in, start
        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )
        roster = check_in(booking, audit_user)
        start_trip(dive_trip, audit_user)

        # Clear previous audit events
        AuditLog.objects.all().delete()

        complete_trip(dive_trip, audit_user)

        diver_completed_events = AuditLog.objects.filter(
            action=Actions.DIVER_COMPLETED_TRIP
        )
        assert diver_completed_events.count() >= 1, (
            "DIVER_COMPLETED_TRIP audit event not emitted"
        )


# =============================================================================
# Certification Audit Tests (verify existing implementation)
# =============================================================================


@pytest.mark.django_db
class TestCertificationAudit:
    """Tests for certification audit events."""

    def test_add_certification_emits_audit_event(
        self, diver_profile, padi_open_water, audit_user, clear_audit_log
    ):
        """add_certification() MUST emit CERTIFICATION_ADDED audit event."""
        from primitives_testbed.diveops.services import add_certification

        cert = add_certification(
            diver=diver_profile,
            level=padi_open_water,
            added_by=audit_user,
            card_number="TEST123",
        )

        audit_entry = AuditLog.objects.filter(action=Actions.CERTIFICATION_ADDED).first()
        assert audit_entry is not None, "CERTIFICATION_ADDED audit event not emitted"
        assert str(audit_entry.object_id) == str(cert.pk)

    def test_remove_certification_emits_audit_event(
        self, diver_profile, padi_open_water, audit_user, clear_audit_log
    ):
        """remove_certification() MUST emit CERTIFICATION_REMOVED audit event."""
        from primitives_testbed.diveops.services import (
            add_certification,
            remove_certification,
        )

        cert = add_certification(
            diver=diver_profile,
            level=padi_open_water,
            added_by=audit_user,
        )

        # Clear the added event
        AuditLog.objects.filter(action=Actions.CERTIFICATION_ADDED).delete()

        remove_certification(cert, audit_user)

        audit_entry = AuditLog.objects.filter(action=Actions.CERTIFICATION_REMOVED).first()
        assert audit_entry is not None, "CERTIFICATION_REMOVED audit event not emitted"

    def test_verify_certification_emits_audit_event(
        self, diver_profile, padi_open_water, audit_user, clear_audit_log
    ):
        """verify_certification() MUST emit CERTIFICATION_VERIFIED audit event."""
        from primitives_testbed.diveops.services import (
            add_certification,
            verify_certification,
        )

        cert = add_certification(
            diver=diver_profile,
            level=padi_open_water,
            added_by=audit_user,
        )

        AuditLog.objects.all().delete()

        verify_certification(cert, audit_user)

        audit_entry = AuditLog.objects.filter(action=Actions.CERTIFICATION_VERIFIED).first()
        assert audit_entry is not None, "CERTIFICATION_VERIFIED audit event not emitted"

    def test_update_certification_emits_audit_event_with_changes(
        self, diver_profile, padi_open_water, audit_user, clear_audit_log
    ):
        """update_certification() MUST emit CERTIFICATION_UPDATED with changes dict."""
        from primitives_testbed.diveops.services import (
            add_certification,
            update_certification,
        )

        cert = add_certification(
            diver=diver_profile,
            level=padi_open_water,
            added_by=audit_user,
            card_number="OLD123",
        )

        AuditLog.objects.all().delete()

        update_certification(cert, audit_user, card_number="NEW456")

        audit_entry = AuditLog.objects.filter(action=Actions.CERTIFICATION_UPDATED).first()
        assert audit_entry is not None, "CERTIFICATION_UPDATED audit event not emitted"
        assert "card_number" in audit_entry.changes
        assert audit_entry.changes["card_number"]["old"] == "OLD123"
        assert audit_entry.changes["card_number"]["new"] == "NEW456"


# =============================================================================
# Audit Completeness Tests
# =============================================================================


# =============================================================================
# Audit Selector Tests
# =============================================================================


@pytest.mark.django_db
class TestAuditSelectors:
    """Tests for audit selectors (read-only)."""

    def test_diver_audit_feed_returns_diver_events(
        self, dive_trip, diver_profile, padi_open_water, audit_user, clear_audit_log
    ):
        """diver_audit_feed() returns all audit events related to a diver."""
        from primitives_testbed.diveops.selectors import diver_audit_feed
        from primitives_testbed.diveops.services import add_certification, book_trip

        # Create diver-related events
        add_certification(diver_profile, padi_open_water, audit_user)
        book_trip(dive_trip, diver_profile, audit_user, skip_eligibility_check=True)

        feed = diver_audit_feed(diver_profile)

        assert len(feed) >= 2
        assert all(str(diver_profile.pk) in str(e.metadata) for e in feed)

    def test_diver_audit_feed_ordered_newest_first(
        self, dive_trip, diver_profile, padi_open_water, audit_user, clear_audit_log
    ):
        """diver_audit_feed() returns events ordered newest first."""
        from primitives_testbed.diveops.selectors import diver_audit_feed
        from primitives_testbed.diveops.services import add_certification, book_trip

        add_certification(diver_profile, padi_open_water, audit_user)
        book_trip(dive_trip, diver_profile, audit_user, skip_eligibility_check=True)

        feed = diver_audit_feed(diver_profile)

        # Should be ordered by created_at descending
        dates = [e.created_at for e in feed]
        assert dates == sorted(dates, reverse=True)

    def test_trip_audit_feed_returns_trip_events(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """trip_audit_feed() returns all audit events related to a trip."""
        from primitives_testbed.diveops.selectors import trip_audit_feed
        from primitives_testbed.diveops.services import book_trip, check_in, start_trip

        # Create trip-related events
        booking = book_trip(
            dive_trip, diver_profile, audit_user, skip_eligibility_check=True
        )
        check_in(booking, audit_user)
        start_trip(dive_trip, audit_user)

        feed = trip_audit_feed(dive_trip)

        assert len(feed) >= 3  # booking, check_in, start_trip
        assert all(str(dive_trip.pk) in str(e.metadata) for e in feed)

    def test_trip_audit_feed_ordered_newest_first(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """trip_audit_feed() returns events ordered newest first."""
        from primitives_testbed.diveops.selectors import trip_audit_feed
        from primitives_testbed.diveops.services import book_trip, start_trip

        book_trip(dive_trip, diver_profile, audit_user, skip_eligibility_check=True)
        start_trip(dive_trip, audit_user)

        feed = trip_audit_feed(dive_trip)

        dates = [e.created_at for e in feed]
        assert dates == sorted(dates, reverse=True)


@pytest.mark.django_db
class TestAuditCompleteness:
    """Tests ensuring NO mutation escapes audit logging."""

    def test_full_booking_lifecycle_produces_complete_audit_trail(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """Full booking lifecycle MUST produce complete audit trail."""
        from primitives_testbed.diveops.services import (
            book_trip,
            check_in,
            complete_trip,
            start_trip,
        )

        # Execute full lifecycle
        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )
        check_in(booking, audit_user)
        start_trip(dive_trip, audit_user)
        complete_trip(dive_trip, audit_user)

        # Verify all expected events exist
        audit_actions = list(AuditLog.objects.values_list("action", flat=True))

        assert Actions.BOOKING_CREATED in audit_actions
        assert Actions.DIVER_CHECKED_IN in audit_actions
        assert Actions.TRIP_STARTED in audit_actions
        assert Actions.TRIP_COMPLETED in audit_actions
        assert Actions.DIVER_COMPLETED_TRIP in audit_actions

    def test_cancelled_booking_produces_audit_trail(
        self, dive_trip, diver_profile, audit_user, clear_audit_log
    ):
        """Cancelled booking MUST produce audit trail."""
        from primitives_testbed.diveops.services import book_trip, cancel_booking

        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=audit_user,
            skip_eligibility_check=True,
        )
        cancel_booking(booking, audit_user)

        audit_actions = list(AuditLog.objects.values_list("action", flat=True))
        assert Actions.BOOKING_CREATED in audit_actions
        assert Actions.BOOKING_CANCELLED in audit_actions
