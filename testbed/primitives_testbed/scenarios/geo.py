"""Geo scenario: Place, ServiceArea with coordinate and radius constraints."""

from decimal import Decimal

from django.db import IntegrityError, DataError, transaction

from django_geo.models import Place, ServiceArea


def seed():
    """Create sample geo data."""
    count = 0

    # Create places
    office, created = Place.objects.get_or_create(
        name="Main Office",
        defaults={
            "latitude": Decimal("40.7128"),
            "longitude": Decimal("-74.0060"),
            "address_line1": "123 Broadway",
            "city": "New York",
            "state": "NY",
            "postal_code": "10001",
        }
    )
    if created:
        count += 1

    warehouse, created = Place.objects.get_or_create(
        name="Warehouse",
        defaults={
            "latitude": Decimal("40.7580"),
            "longitude": Decimal("-73.9855"),
            "address_line1": "456 Times Square",
            "city": "New York",
            "state": "NY",
            "postal_code": "10036",
        }
    )
    if created:
        count += 1

    # Create service areas
    metro_area, created = ServiceArea.objects.get_or_create(
        code="metro-area",
        defaults={
            "name": "Metro Area",
            "center_latitude": Decimal("40.7128"),
            "center_longitude": Decimal("-74.0060"),
            "radius_km": Decimal("25.0"),
            "area_type": "coverage",
        }
    )
    if created:
        count += 1

    downtown, created = ServiceArea.objects.get_or_create(
        code="downtown-zone",
        defaults={
            "name": "Downtown Zone",
            "center_latitude": Decimal("40.7580"),
            "center_longitude": Decimal("-73.9855"),
            "radius_km": Decimal("5.0"),
            "area_type": "delivery",
        }
    )
    if created:
        count += 1

    return count


def verify():
    """Verify geo constraints with negative writes."""
    results = []

    # Test 1: Place latitude must be in range -90 to 90
    try:
        with transaction.atomic():
            Place.objects.create(
                name="Invalid High Lat",
                latitude=Decimal("95.0"),  # Above 90
                longitude=Decimal("0.0"),
                city="Test",
                state="TS",
                postal_code="12345",
            )
        results.append(("place_valid_latitude (above 90)", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("place_valid_latitude (above 90)", True, "Correctly rejected"))

    try:
        with transaction.atomic():
            Place.objects.create(
                name="Invalid Low Lat",
                latitude=Decimal("-95.0"),  # Below -90
                longitude=Decimal("0.0"),
                city="Test",
                state="TS",
                postal_code="12345",
            )
        results.append(("place_valid_latitude (below -90)", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("place_valid_latitude (below -90)", True, "Correctly rejected"))

    # Test 2: Place longitude must be in range -180 to 180
    try:
        with transaction.atomic():
            Place.objects.create(
                name="Invalid High Lon",
                latitude=Decimal("0.0"),
                longitude=Decimal("185.0"),  # Above 180
                city="Test",
                state="TS",
                postal_code="12345",
            )
        results.append(("place_valid_longitude (above 180)", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("place_valid_longitude (above 180)", True, "Correctly rejected"))

    try:
        with transaction.atomic():
            Place.objects.create(
                name="Invalid Low Lon",
                latitude=Decimal("0.0"),
                longitude=Decimal("-185.0"),  # Below -180
                city="Test",
                state="TS",
                postal_code="12345",
            )
        results.append(("place_valid_longitude (below -180)", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("place_valid_longitude (below -180)", True, "Correctly rejected"))

    # Test 3: ServiceArea center latitude must be valid
    try:
        with transaction.atomic():
            ServiceArea.objects.create(
                name="Invalid SA Lat",
                code="invalid-lat-test",
                center_latitude=Decimal("100.0"),  # Above 90
                center_longitude=Decimal("0.0"),
                radius_km=Decimal("10.0"),
            )
        results.append(("servicearea_valid_latitude", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("servicearea_valid_latitude", True, "Correctly rejected"))

    # Test 4: ServiceArea center longitude must be valid
    try:
        with transaction.atomic():
            ServiceArea.objects.create(
                name="Invalid SA Lon",
                code="invalid-lon-test",
                center_latitude=Decimal("0.0"),
                center_longitude=Decimal("200.0"),  # Above 180
                radius_km=Decimal("10.0"),
            )
        results.append(("servicearea_valid_longitude", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("servicearea_valid_longitude", True, "Correctly rejected"))

    # Test 5: ServiceArea radius must be positive
    try:
        with transaction.atomic():
            ServiceArea.objects.create(
                name="Invalid Radius Zero",
                code="zero-radius-test",
                center_latitude=Decimal("0.0"),
                center_longitude=Decimal("0.0"),
                radius_km=Decimal("0.0"),  # Zero - should fail
            )
        results.append(("servicearea_positive_radius (zero)", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("servicearea_positive_radius (zero)", True, "Correctly rejected"))

    try:
        with transaction.atomic():
            ServiceArea.objects.create(
                name="Invalid Radius Neg",
                code="neg-radius-test",
                center_latitude=Decimal("0.0"),
                center_longitude=Decimal("0.0"),
                radius_km=Decimal("-5.0"),  # Negative - should fail
            )
        results.append(("servicearea_positive_radius (negative)", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("servicearea_positive_radius (negative)", True, "Correctly rejected"))

    return results
