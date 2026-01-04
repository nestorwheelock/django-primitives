"""Tests for diveops models and DB constraints."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone


@pytest.mark.django_db
class TestDiverProfile:
    """Tests for DiverProfile model."""

    def test_create_diver_profile(self, person, padi_agency):
        """DiverProfile can be created with valid data."""
        from primitives_testbed.diveops.models import DiverProfile

        profile = DiverProfile.objects.create(
            person=person,
            certification_level="ow",
            certification_agency=padi_agency,
            certification_number="12345",
            certification_date=date.today(),
            total_dives=0,
        )

        assert profile.pk is not None
        assert profile.person == person
        assert profile.certification_level == "ow"

    def test_one_profile_per_person_constraint(self, diver_profile, person, ssi_agency):
        """Only one DiverProfile per Person is allowed (DB constraint)."""
        from primitives_testbed.diveops.models import DiverProfile

        with pytest.raises(IntegrityError):
            DiverProfile.objects.create(
                person=person,
                certification_level="aow",
                certification_agency=ssi_agency,
                certification_number="99999",
                certification_date=date.today(),
                total_dives=0,
            )

    def test_certification_level_choices(self, person2, padi_agency):
        """Certification level must be a valid choice."""
        from primitives_testbed.diveops.models import DiverProfile

        profile = DiverProfile.objects.create(
            person=person2,
            certification_level="dm",  # Divemaster
            certification_agency=padi_agency,
            certification_number="DM123",
            certification_date=date.today(),
            total_dives=100,
        )

        assert profile.certification_level == "dm"

    def test_total_dives_non_negative_constraint(self, person2, padi_agency):
        """total_dives cannot be negative (DB constraint)."""
        from primitives_testbed.diveops.models import DiverProfile

        with pytest.raises(IntegrityError):
            DiverProfile.objects.create(
                person=person2,
                certification_level="ow",
                certification_agency=padi_agency,
                certification_number="12345",
                certification_date=date.today(),
                total_dives=-1,  # Invalid
            )

    def test_is_medical_current_property(self, diver_profile):
        """is_medical_current returns True when medical clearance is valid."""
        assert diver_profile.is_medical_current is True

    def test_is_medical_current_expired(self, person2, padi_agency):
        """is_medical_current returns False when medical clearance expired."""
        from primitives_testbed.diveops.models import DiverProfile

        profile = DiverProfile.objects.create(
            person=person2,
            certification_level="ow",
            certification_agency=padi_agency,
            certification_number="12345",
            certification_date=date.today(),
            total_dives=10,
            medical_clearance_date=date.today() - timedelta(days=400),
            medical_clearance_valid_until=date.today() - timedelta(days=35),
        )

        assert profile.is_medical_current is False


@pytest.mark.django_db
class TestDiveSite:
    """Tests for DiveSite model."""

    def test_create_dive_site(self):
        """DiveSite can be created with valid data."""
        from primitives_testbed.diveops.models import DiveSite

        site = DiveSite.objects.create(
            name="Test Site",
            max_depth_meters=20,
            min_certification_level="ow",
            difficulty="beginner",
            latitude=Decimal("20.000000"),
            longitude=Decimal("-87.000000"),
        )

        assert site.pk is not None
        assert site.name == "Test Site"

    def test_max_depth_positive_constraint(self):
        """max_depth_meters must be positive (DB constraint)."""
        from primitives_testbed.diveops.models import DiveSite

        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Invalid Site",
                max_depth_meters=0,  # Invalid
                min_certification_level="ow",
                difficulty="beginner",
                latitude=Decimal("20.000000"),
                longitude=Decimal("-87.000000"),
            )

    def test_latitude_range_constraint(self):
        """latitude must be between -90 and 90 (DB constraint)."""
        from primitives_testbed.diveops.models import DiveSite

        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Invalid Site",
                max_depth_meters=20,
                min_certification_level="ow",
                difficulty="beginner",
                latitude=Decimal("91.000000"),  # Invalid
                longitude=Decimal("-87.000000"),
            )

    def test_longitude_range_constraint(self):
        """longitude must be between -180 and 180 (DB constraint)."""
        from primitives_testbed.diveops.models import DiveSite

        with pytest.raises(IntegrityError):
            DiveSite.objects.create(
                name="Invalid Site",
                max_depth_meters=20,
                min_certification_level="ow",
                difficulty="beginner",
                latitude=Decimal("20.000000"),
                longitude=Decimal("181.000000"),  # Invalid
            )


@pytest.mark.django_db
class TestDiveTrip:
    """Tests for DiveTrip model."""

    def test_create_dive_trip(self, dive_shop, dive_site, user):
        """DiveTrip can be created with valid data."""
        from primitives_testbed.diveops.models import DiveTrip

        departure = timezone.now() + timedelta(days=1)

        trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=departure,
            return_time=departure + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        assert trip.pk is not None
        assert trip.status == "scheduled"

    def test_return_after_departure_constraint(self, dive_shop, dive_site, user):
        """return_time must be after departure_time (DB constraint)."""
        from primitives_testbed.diveops.models import DiveTrip

        departure = timezone.now() + timedelta(days=1)

        with pytest.raises(IntegrityError):
            DiveTrip.objects.create(
                dive_shop=dive_shop,
                dive_site=dive_site,
                departure_time=departure,
                return_time=departure - timedelta(hours=1),  # Before departure
                max_divers=8,
                price_per_diver=Decimal("100.00"),
                currency="USD",
                created_by=user,
            )

    def test_max_divers_positive_constraint(self, dive_shop, dive_site, user):
        """max_divers must be positive (DB constraint)."""
        from primitives_testbed.diveops.models import DiveTrip

        departure = timezone.now() + timedelta(days=1)

        with pytest.raises(IntegrityError):
            DiveTrip.objects.create(
                dive_shop=dive_shop,
                dive_site=dive_site,
                departure_time=departure,
                return_time=departure + timedelta(hours=4),
                max_divers=0,  # Invalid
                price_per_diver=Decimal("100.00"),
                currency="USD",
                created_by=user,
            )

    def test_price_non_negative_constraint(self, dive_shop, dive_site, user):
        """price_per_diver cannot be negative (DB constraint)."""
        from primitives_testbed.diveops.models import DiveTrip

        departure = timezone.now() + timedelta(days=1)

        with pytest.raises(IntegrityError):
            DiveTrip.objects.create(
                dive_shop=dive_shop,
                dive_site=dive_site,
                departure_time=departure,
                return_time=departure + timedelta(hours=4),
                max_divers=8,
                price_per_diver=Decimal("-10.00"),  # Invalid
                currency="USD",
                created_by=user,
            )

    def test_spots_available_property(self, dive_trip):
        """spots_available returns correct count."""
        assert dive_trip.spots_available == 8

    def test_spots_available_with_bookings(self, dive_trip, diver_profile, user):
        """spots_available decreases with confirmed bookings."""
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        assert dive_trip.spots_available == 7


@pytest.mark.django_db
class TestBooking:
    """Tests for Booking model."""

    def test_create_booking(self, dive_trip, diver_profile, user):
        """Booking can be created with valid data."""
        from primitives_testbed.diveops.models import Booking

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        assert booking.pk is not None
        assert booking.status == "confirmed"

    def test_unique_booking_per_diver_trip_constraint(self, dive_trip, diver_profile, user):
        """A diver can only have one booking per trip (DB constraint)."""
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        with pytest.raises(IntegrityError):
            Booking.objects.create(
                trip=dive_trip,
                diver=diver_profile,
                status="confirmed",
                booked_by=user,
            )


@pytest.mark.django_db
class TestTripRoster:
    """Tests for TripRoster model."""

    def test_create_roster_entry(self, dive_trip, diver_profile, user):
        """TripRoster entry can be created."""
        from primitives_testbed.diveops.models import Booking, TripRoster

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        roster = TripRoster.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
        )

        assert roster.pk is not None
        assert roster.checked_in_at is not None

    def test_unique_roster_per_diver_trip_constraint(self, dive_trip, diver_profile, user):
        """A diver can only appear once on a trip roster (DB constraint)."""
        from primitives_testbed.diveops.models import Booking, TripRoster

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        TripRoster.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
        )

        with pytest.raises(IntegrityError):
            TripRoster.objects.create(
                trip=dive_trip,
                diver=diver_profile,
                booking=booking,
                checked_in_by=user,
            )

    def test_roster_role_default(self, dive_trip, diver_profile, user):
        """TripRoster role defaults to DIVER."""
        from primitives_testbed.diveops.models import Booking, TripRoster

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        roster = TripRoster.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
        )

        assert roster.role == "DIVER"

    def test_roster_role_divemaster(self, dive_trip, diver_profile, user):
        """TripRoster can have DM role."""
        from primitives_testbed.diveops.models import Booking, TripRoster

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        roster = TripRoster.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
            role="DM",
        )

        assert roster.role == "DM"

    def test_roster_role_instructor(self, dive_trip, diver_profile, user):
        """TripRoster can have INSTRUCTOR role."""
        from primitives_testbed.diveops.models import Booking, TripRoster

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        roster = TripRoster.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
            role="INSTRUCTOR",
        )

        assert roster.role == "INSTRUCTOR"


@pytest.mark.django_db
class TestBookingRebooking:
    """Tests for rebooking after cancellation."""

    def test_rebook_after_cancel_allowed(self, dive_trip, diver_profile, user):
        """Diver can rebook after cancellation (conditional unique constraint)."""
        from primitives_testbed.diveops.models import Booking

        # First booking
        booking1 = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        # Cancel the booking
        booking1.status = "cancelled"
        booking1.save()

        # Rebook should succeed
        booking2 = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        assert booking2.pk is not None
        assert booking2.status == "confirmed"

    def test_duplicate_active_booking_rejected(self, dive_trip, diver_profile, user):
        """Cannot have two active bookings for same diver/trip."""
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        with pytest.raises(IntegrityError):
            Booking.objects.create(
                trip=dive_trip,
                diver=diver_profile,
                status="pending",
                booked_by=user,
            )


@pytest.mark.django_db
class TestWaiverExpiration:
    """Tests for configurable waiver expiration."""

    def test_waiver_valid_within_period(self, diver_profile):
        """Waiver is valid when signed within configured period."""
        from django.utils import timezone

        diver_profile.waiver_signed_at = timezone.now() - timedelta(days=30)
        diver_profile.save()

        # Should be valid within 365 days
        assert diver_profile.is_waiver_valid() is True

    def test_waiver_expired_after_period(self, diver_profile):
        """Waiver is expired when signed more than configured period ago."""
        from django.utils import timezone

        diver_profile.waiver_signed_at = timezone.now() - timedelta(days=400)
        diver_profile.save()

        # Should be expired after 365 days
        assert diver_profile.is_waiver_valid() is False

    def test_waiver_never_signed(self, diver_profile):
        """Waiver is not valid if never signed."""
        diver_profile.waiver_signed_at = None
        diver_profile.save()

        assert diver_profile.is_waiver_valid() is False

    def test_waiver_valid_as_of_date(self, diver_profile):
        """Waiver validity can be checked at a specific point in time."""
        from django.utils import timezone

        sign_date = timezone.now() - timedelta(days=200)
        diver_profile.waiver_signed_at = sign_date
        diver_profile.save()

        # Valid 100 days after signing
        check_date = sign_date + timedelta(days=100)
        assert diver_profile.is_waiver_valid(as_of=check_date) is True

        # Expired 400 days after signing
        expired_date = sign_date + timedelta(days=400)
        assert diver_profile.is_waiver_valid(as_of=expired_date) is False
