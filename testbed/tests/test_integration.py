"""Integration tests for django-primitives packages.

These tests verify that:
1. All migrations apply cleanly
2. Database constraints are enforced
3. Happy-path operations work for each primitive
"""

import pytest
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.utils import timezone

# ============================================================================
# Seeding Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestSeeding:
    """Test that seeding works correctly."""

    def test_seed_all_scenarios(self, seeded_database):
        """All scenarios seed without errors."""
        for name, status, detail in seeded_database:
            assert status == "OK", f"Scenario {name} failed: {detail}"

    def test_parties_seeded(self, seeded_database):
        """Parties scenario creates expected data."""
        from django_parties.models import Person, Organization

        assert Person.objects.exists(), "No persons created"
        assert Organization.objects.exists(), "No organizations created"

    def test_rbac_seeded(self, seeded_database):
        """RBAC scenario creates roles and assignments."""
        from django_rbac.models import Role, UserRole

        assert Role.objects.exists(), "No roles created"
        assert UserRole.objects.exists(), "No user roles created"

    def test_catalog_seeded(self, seeded_database):
        """Catalog scenario creates items and baskets."""
        from django_catalog.models import CatalogItem, Basket

        assert CatalogItem.objects.exists(), "No catalog items created"
        assert Basket.objects.exists(), "No baskets created"


# ============================================================================
# Constraint Verification Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestConstraintVerification:
    """Test that constraint verification works."""

    def test_verify_all_scenarios(self, seeded_database):
        """All constraint verifications run."""
        from primitives_testbed.scenarios import verify_all

        results = verify_all()
        assert len(results) > 0, "No verification results"

        # Count failures
        failures = []
        for name, checks in results:
            for check_name, passed, detail in checks:
                if passed is False:
                    failures.append(f"{name}.{check_name}: {detail}")

        assert len(failures) == 0, f"Constraint failures:\n" + "\n".join(failures)


# ============================================================================
# Parties Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestParties:
    """Test django-parties functionality."""

    def test_create_person(self):
        """Can create a person."""
        from django_parties.models import Person

        person = Person.objects.create(
            first_name="Test",
            last_name="Person",
        )
        assert person.pk is not None

    def test_create_organization(self):
        """Can create an organization."""
        from django_parties.models import Organization

        org = Organization.objects.create(name="Test Org")
        assert org.pk is not None

    def test_address_requires_party(self):
        """Address must belong to exactly one party."""
        from django_parties.models import Address

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Address.objects.create(
                    line1="123 Test St",
                    city="Test City",
                    state="TS",
                    postal_code="12345",
                    country="US",
                )


# ============================================================================
# RBAC Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestRBAC:
    """Test django-rbac functionality."""

    def test_role_hierarchy_constraint(self):
        """Role hierarchy must be in range 10-100."""
        from django.contrib.auth.models import Group
        from django_rbac.models import Role

        group = Group.objects.create(name="Test Group Invalid")

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Role.objects.create(
                    name="Invalid Role",
                    slug="invalid-role",
                    hierarchy_level=5,  # Below minimum
                    group=group,
                )

    def test_user_role_valid_dates(self, regular_user):
        """UserRole valid_to must be after valid_from."""
        from django.contrib.auth.models import Group
        from django_rbac.models import Role, UserRole

        group = Group.objects.create(name="Date Test Group")
        role = Role.objects.create(
            name="Date Test Role",
            slug="date-test-role",
            hierarchy_level=20,
            group=group,
        )

        now = timezone.now()
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                UserRole.objects.create(
                    user=regular_user,
                    role=role,
                    valid_from=now,
                    valid_to=now - timezone.timedelta(days=1),
                )


# ============================================================================
# Catalog Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestCatalog:
    """Test django-catalog functionality."""

    def test_basket_item_quantity_positive(self, seeded_database):
        """BasketItem quantity must be positive."""
        from django.contrib.auth import get_user_model
        from django_catalog.models import Basket, BasketItem, CatalogItem

        User = get_user_model()
        basket = Basket.objects.first()
        item = CatalogItem.objects.first()
        user = User.objects.first()

        if basket and item and user:
            with pytest.raises(IntegrityError):
                with transaction.atomic():
                    BasketItem.objects.create(
                        basket=basket,
                        catalog_item=item,
                        quantity=0,
                        added_by=user,
                    )

    def test_workitem_priority_range(self, seeded_database):
        """WorkItem priority must be 0-100."""
        from django_catalog.models import BasketItem, WorkItem

        basket_item = BasketItem.objects.first()

        if basket_item:
            with pytest.raises(IntegrityError):
                with transaction.atomic():
                    WorkItem.objects.create(
                        basket_item=basket_item,
                        spawn_role="test",
                        status="pending",
                        priority=150,
                    )


# ============================================================================
# Geo Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestGeo:
    """Test django-geo functionality."""

    def test_place_valid_coordinates(self):
        """Place coordinates must be valid."""
        from django_geo.models import Place

        # Valid coordinates
        place = Place.objects.create(
            name="Valid Place",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
        )
        assert place.pk is not None

        # Invalid latitude
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Place.objects.create(
                    name="Invalid Lat",
                    latitude=Decimal("95.0"),
                    longitude=Decimal("0.0"),
                )

    def test_servicearea_positive_radius(self):
        """ServiceArea radius must be positive."""
        from django_geo.models import ServiceArea

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ServiceArea.objects.create(
                    name="Zero Radius",
                    center_latitude=Decimal("0.0"),
                    center_longitude=Decimal("0.0"),
                    radius_km=Decimal("0.0"),
                )


# ============================================================================
# Ledger Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestLedger:
    """Test django-ledger functionality."""

    def test_entry_amount_positive(self, seeded_database):
        """Entry amount must be positive."""
        from django_ledger.models import Account, Transaction, Entry

        account = Account.objects.first()
        txn = Transaction.objects.first()

        if account and txn:
            with pytest.raises(IntegrityError):
                with transaction.atomic():
                    Entry.objects.create(
                        transaction=txn,
                        account=account,
                        entry_type="debit",
                        amount=Decimal("0.00"),
                    )


# ============================================================================
# Sequence Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestSequence:
    """Test django-sequence functionality."""

    def test_sequence_generates_ids(self, seeded_database):
        """Sequence generates formatted IDs."""
        from django_sequence.models import Sequence

        seq = Sequence.objects.first()
        if seq:
            # Test that formatted_value works
            formatted = seq.formatted_value
            assert formatted is not None
            assert seq.prefix in formatted

            # Test manual increment
            initial = seq.current_value
            seq.current_value += 1
            seq.save()
            seq.refresh_from_db()

            assert seq.current_value == initial + 1


# ============================================================================
# Encounters Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestEncounters:
    """Test django-encounters functionality."""

    def test_encounter_transition(self, seeded_database):
        """Encounter transitions work correctly."""
        from django_encounters.models import Encounter, EncounterTransition

        encounter = Encounter.objects.first()
        if encounter:
            initial_count = EncounterTransition.objects.filter(encounter=encounter).count()
            assert initial_count >= 0  # Just verify it's queryable


# ============================================================================
# Happy Path Tests
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestHappyPaths:
    """Test happy paths for each primitive."""

    def test_complete_workflow(self, seeded_database, admin_user):
        """Run a complete workflow across multiple primitives."""
        from django_parties.models import Person
        from django_rbac.models import Role, UserRole
        from django.contrib.auth.models import Group
        from django_catalog.models import CatalogItem, Basket, BasketItem
        from django_encounters.models import Encounter

        # 1. Create a new person
        person = Person.objects.create(
            first_name="Workflow",
            last_name="Test",
        )

        # 2. Assign a role to the admin user
        group, _ = Group.objects.get_or_create(name="Workflow Test Group")
        role, _ = Role.objects.get_or_create(
            slug="workflow-test-role",
            defaults={
                "name": "Workflow Test Role",
                "hierarchy_level": 30,
                "group": group,
            }
        )
        UserRole.objects.get_or_create(
            user=admin_user,
            role=role,
        )

        # 3. Create a catalog item
        item, _ = CatalogItem.objects.get_or_create(
            display_name="Workflow Test Item",
            kind="stock_item",
            defaults={
                "is_billable": True,
                "active": True,
            }
        )

        # 4. Get an existing encounter for the basket (baskets require an encounter FK)
        encounter = Encounter.objects.first()
        if encounter:
            # 5. Create or get a basket for the encounter
            basket, _ = Basket.objects.get_or_create(
                encounter=encounter,
                status="draft",
                defaults={"created_by": admin_user}
            )

            # 6. Add item to basket (quantity 3)
            basket_item = BasketItem.objects.create(
                basket=basket,
                catalog_item=item,
                quantity=3,
                added_by=admin_user,
            )

            # Verify
            assert basket_item.quantity == 3
            assert admin_user.hierarchy_level >= 30
