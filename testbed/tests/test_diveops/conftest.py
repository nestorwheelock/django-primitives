"""Pytest fixtures for diveops tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="divemaster",
        email="divemaster@example.com",
        password="testpass123",
    )


@pytest.fixture
def diver_user(db):
    """Create a diver user."""
    return User.objects.create_user(
        username="diver",
        email="diver@example.com",
        password="testpass123",
    )


@pytest.fixture
def person(db):
    """Create a test person (diver candidate)."""
    from django_parties.models import Person

    return Person.objects.create(
        first_name="John",
        last_name="Diver",
        email="john@example.com",
    )


@pytest.fixture
def person2(db):
    """Create a second test person."""
    from django_parties.models import Person

    return Person.objects.create(
        first_name="Jane",
        last_name="Swimmer",
        email="jane@example.com",
    )


@pytest.fixture
def dive_shop(db):
    """Create a dive shop organization."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Blue Water Dive Shop",
        org_type="company",
    )


@pytest.fixture
def dive_site(db):
    """Create a dive site."""
    from primitives_testbed.diveops.models import DiveSite

    return DiveSite.objects.create(
        name="Coral Reef Point",
        max_depth_meters=30,
        min_certification_level="ow",
        difficulty="intermediate",
        latitude=Decimal("20.123456"),
        longitude=Decimal("-87.654321"),
        description="Beautiful coral reef",
    )


@pytest.fixture
def shallow_site(db):
    """Create a shallow dive site suitable for beginners."""
    from primitives_testbed.diveops.models import DiveSite

    return DiveSite.objects.create(
        name="Shallow Bay",
        max_depth_meters=12,
        min_certification_level="ow",
        difficulty="beginner",
        latitude=Decimal("20.200000"),
        longitude=Decimal("-87.700000"),
        description="Easy dive site",
    )


@pytest.fixture
def deep_site(db):
    """Create a deep dive site requiring advanced certification."""
    from primitives_testbed.diveops.models import DiveSite

    return DiveSite.objects.create(
        name="The Abyss",
        max_depth_meters=40,
        min_certification_level="aow",
        difficulty="advanced",
        latitude=Decimal("20.300000"),
        longitude=Decimal("-87.800000"),
        description="Deep wall dive",
    )


@pytest.fixture
def diver_profile(db, person):
    """Create a certified diver profile."""
    from primitives_testbed.diveops.models import DiverProfile

    return DiverProfile.objects.create(
        person=person,
        certification_level="aow",
        certification_agency="PADI",
        certification_number="12345",
        certification_date=date.today() - timedelta(days=365),
        total_dives=50,
        medical_clearance_date=date.today() - timedelta(days=30),
        medical_clearance_valid_until=date.today() + timedelta(days=335),
    )


@pytest.fixture
def beginner_diver(db, person2):
    """Create a beginner diver profile (Open Water only)."""
    from primitives_testbed.diveops.models import DiverProfile

    return DiverProfile.objects.create(
        person=person2,
        certification_level="ow",
        certification_agency="PADI",
        certification_number="67890",
        certification_date=date.today() - timedelta(days=30),
        total_dives=4,
        medical_clearance_date=date.today() - timedelta(days=30),
        medical_clearance_valid_until=date.today() + timedelta(days=335),
    )


@pytest.fixture
def encounter_definition(db):
    """Create a dive trip encounter definition."""
    from django_encounters.models import EncounterDefinition

    return EncounterDefinition.objects.create(
        key="dive_trip",
        name="Dive Trip",
        states=["scheduled", "boarding", "in_progress", "completed", "cancelled"],
        transitions={
            "scheduled": ["boarding", "cancelled"],
            "boarding": ["in_progress", "cancelled"],
            "in_progress": ["completed"],
            "completed": [],
            "cancelled": [],
        },
        initial_state="scheduled",
        terminal_states=["completed", "cancelled"],
    )


@pytest.fixture
def dive_trip(db, dive_shop, dive_site, encounter_definition, user):
    """Create a dive trip."""
    from primitives_testbed.diveops.models import DiveTrip

    tomorrow = timezone.now() + timedelta(days=1)

    return DiveTrip.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        departure_time=tomorrow,
        return_time=tomorrow + timedelta(hours=4),
        max_divers=8,
        price_per_diver=Decimal("100.00"),
        currency="USD",
        created_by=user,
    )


@pytest.fixture
def full_trip(db, dive_shop, shallow_site, encounter_definition, user, diver_profile):
    """Create a fully booked dive trip."""
    from primitives_testbed.diveops.models import DiveTrip, Booking

    tomorrow = timezone.now() + timedelta(days=1)

    trip = DiveTrip.objects.create(
        dive_shop=dive_shop,
        dive_site=shallow_site,
        departure_time=tomorrow,
        return_time=tomorrow + timedelta(hours=4),
        max_divers=1,  # Only 1 spot
        price_per_diver=Decimal("75.00"),
        currency="USD",
        created_by=user,
    )

    # Book the only spot
    Booking.objects.create(
        trip=trip,
        diver=diver_profile,
        status="confirmed",
        booked_by=user,
    )

    return trip
