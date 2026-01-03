"""Tests for django-catalog models."""

import pytest

from django_catalog.models import CatalogItem, Basket, BasketItem, WorkItem


@pytest.mark.django_db
class TestCatalogItem:
    """Tests for CatalogItem model."""

    def test_create_service(self):
        """Test creating a service catalog item."""
        item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='Blood Test',
        )

        assert item.pk is not None
        assert item.kind == 'service'
        assert item.service_category == 'lab'
        assert item.active is True
        assert 'Blood Test' in str(item)

    def test_create_stock_item(self):
        """Test creating a stock item."""
        item = CatalogItem.objects.create(
            kind='stock_item',
            default_stock_action='dispense',
            display_name='Medication',
        )

        assert item.pk is not None
        assert item.kind == 'stock_item'
        assert item.default_stock_action == 'dispense'


@pytest.mark.django_db
class TestBasketUniqueActiveConstraint:
    """Tests for one active basket per encounter constraint.

    The Basket model docstring says: "One active basket per encounter at a time"
    This is enforced by a partial UniqueConstraint.
    """

    def test_cannot_create_two_draft_baskets_for_same_encounter(self, django_user_model):
        """Cannot create two draft baskets for the same encounter."""
        from django.db import IntegrityError
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='constraintuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Constraint Test')

        # First draft basket - OK
        Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='draft',
        )

        # Second draft basket - should fail
        with pytest.raises(IntegrityError):
            Basket.objects.create(
                encounter=encounter,
                created_by=user,
                status='draft',
            )

    def test_can_create_draft_after_committing_previous(self, django_user_model):
        """Can create new draft basket after committing the previous one."""
        from tests.testapp.models import Encounter
        from django.utils import timezone

        user = django_user_model.objects.create_user(
            username='commituser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Commit Test')

        # First basket - commit it
        basket1 = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='draft',
        )
        basket1.status = 'committed'
        basket1.committed_by = user
        basket1.committed_at = timezone.now()
        basket1.save()

        # Second basket - should work since first is committed
        basket2 = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='draft',
        )

        assert basket2.pk is not None
        assert basket2.status == 'draft'

    def test_can_create_draft_after_cancelling_previous(self, django_user_model):
        """Can create new draft basket after cancelling the previous one."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='canceluser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Cancel Test')

        # First basket - cancel it
        basket1 = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='draft',
        )
        basket1.status = 'cancelled'
        basket1.save()

        # Second basket - should work since first is cancelled
        basket2 = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='draft',
        )

        assert basket2.pk is not None
        assert basket2.status == 'draft'

    def test_can_create_draft_after_soft_deleting_previous(self, django_user_model):
        """Can create new draft basket after soft-deleting the previous one."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='softdeluser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Soft Delete Test')

        # First basket - soft delete it
        basket1 = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='draft',
        )
        basket1.delete()  # BaseModel soft delete

        # Second basket - should work since first is soft-deleted
        basket2 = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='draft',
        )

        assert basket2.pk is not None
        assert basket2.status == 'draft'

    def test_different_encounters_can_have_draft_baskets(self, django_user_model):
        """Different encounters can each have a draft basket."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='multiencuser',
            password='testpass'
        )
        encounter1 = Encounter.objects.create(patient_name='Patient 1')
        encounter2 = Encounter.objects.create(patient_name='Patient 2')

        # Both should work - different encounters
        basket1 = Basket.objects.create(
            encounter=encounter1,
            created_by=user,
            status='draft',
        )
        basket2 = Basket.objects.create(
            encounter=encounter2,
            created_by=user,
            status='draft',
        )

        assert basket1.pk is not None
        assert basket2.pk is not None


@pytest.mark.django_db
class TestBasket:
    """Tests for Basket model."""

    def test_create_basket(self, django_user_model):
        """Test creating a basket."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='testuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Test Patient')

        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )

        assert basket.pk is not None
        assert basket.status == 'draft'
        assert basket.is_editable is True

    def test_basket_not_editable_when_committed(self, django_user_model):
        """Test that committed baskets are not editable."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='testuser2',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Test Patient')

        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='committed',
        )

        assert basket.is_editable is False


@pytest.mark.django_db
class TestBasketTimeSemantics:
    """Tests for Basket time semantics (effective_at/recorded_at)."""

    def test_basket_has_effective_at_field(self, django_user_model):
        """Basket should have effective_at field."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='timesemuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Time Semantics Patient')

        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )

        assert hasattr(basket, 'effective_at')
        assert basket.effective_at is not None

    def test_basket_has_recorded_at_field(self, django_user_model):
        """Basket should have recorded_at field."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='recordedatuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Recorded At Patient')

        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )

        assert hasattr(basket, 'recorded_at')
        assert basket.recorded_at is not None

    def test_basket_effective_at_defaults_to_now(self, django_user_model):
        """Basket effective_at should default to now."""
        from tests.testapp.models import Encounter
        from django.utils import timezone

        user = django_user_model.objects.create_user(
            username='defaultnowuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Default Now Patient')

        before = timezone.now()
        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )
        after = timezone.now()

        assert basket.effective_at >= before
        assert basket.effective_at <= after

    def test_basket_can_be_backdated(self, django_user_model):
        """Basket effective_at can be set to past time."""
        from tests.testapp.models import Encounter
        from django.utils import timezone
        import datetime

        user = django_user_model.objects.create_user(
            username='backdateuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Backdate Patient')

        past = timezone.now() - datetime.timedelta(days=7)
        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            effective_at=past,
        )

        assert basket.effective_at == past

    def test_basket_as_of_query(self, django_user_model):
        """Basket.objects.as_of(timestamp) returns baskets effective at that time."""
        from tests.testapp.models import Encounter
        from django.utils import timezone
        import datetime

        user = django_user_model.objects.create_user(
            username='asofuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='As Of Patient')

        now = timezone.now()
        past = now - datetime.timedelta(days=7)

        # Old basket - commit it so we can create another
        old_basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='committed',  # Committed, not draft
            effective_at=past,
            committed_at=past,
            committed_by=user,
        )

        # New basket - can be draft since old one is committed
        new_basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            effective_at=now,
        )

        # Query as of 5 days ago (should only see old basket)
        five_days_ago = now - datetime.timedelta(days=5)
        baskets_then = Basket.objects.as_of(five_days_ago).filter(encounter=encounter)
        assert baskets_then.count() == 1
        assert baskets_then.first() == old_basket

        # Query as of now (should see both)
        baskets_now = Basket.objects.as_of(now).filter(encounter=encounter)
        assert baskets_now.count() == 2


@pytest.mark.django_db
class TestWorkItemTimeSemantics:
    """Tests for WorkItem time semantics (effective_at/recorded_at).

    WorkItem has effective_at for when work "happened" (distinct from started_at).
    """

    def test_workitem_has_effective_at_field(self, django_user_model):
        """WorkItem should have effective_at field."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='witimesemuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='WI Time Semantics Patient')
        catalog_item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='WI Time Test',
            active=True,
        )
        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )
        basket_item = BasketItem.objects.create(
            basket=basket,
            catalog_item=catalog_item,
            added_by=user,
        )

        work_item = WorkItem.objects.create(
            basket_item=basket_item,
            encounter=encounter,
            spawn_role='primary',
            target_board='lab',
            display_name='WI Time Test',
            kind='service',
        )

        assert hasattr(work_item, 'effective_at')
        assert work_item.effective_at is not None

    def test_workitem_has_recorded_at_field(self, django_user_model):
        """WorkItem should have recorded_at field."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='wirecordedatuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='WI Recorded At Patient')
        catalog_item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='WI Recorded Test',
            active=True,
        )
        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )
        basket_item = BasketItem.objects.create(
            basket=basket,
            catalog_item=catalog_item,
            added_by=user,
        )

        work_item = WorkItem.objects.create(
            basket_item=basket_item,
            encounter=encounter,
            spawn_role='primary',
            target_board='lab',
            display_name='WI Recorded Test',
            kind='service',
        )

        assert hasattr(work_item, 'recorded_at')
        assert work_item.recorded_at is not None

    def test_workitem_effective_at_defaults_to_now(self, django_user_model):
        """WorkItem effective_at should default to now."""
        from tests.testapp.models import Encounter
        from django.utils import timezone

        user = django_user_model.objects.create_user(
            username='widefaultnowuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='WI Default Now Patient')
        catalog_item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='WI Default Now Test',
            active=True,
        )
        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )
        basket_item = BasketItem.objects.create(
            basket=basket,
            catalog_item=catalog_item,
            added_by=user,
        )

        before = timezone.now()
        work_item = WorkItem.objects.create(
            basket_item=basket_item,
            encounter=encounter,
            spawn_role='primary',
            target_board='lab',
            display_name='WI Default Now Test',
            kind='service',
        )
        after = timezone.now()

        assert work_item.effective_at >= before
        assert work_item.effective_at <= after

    def test_workitem_can_be_backdated(self, django_user_model):
        """WorkItem effective_at can be set to past time."""
        from tests.testapp.models import Encounter
        from django.utils import timezone
        import datetime

        user = django_user_model.objects.create_user(
            username='wibackdateuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='WI Backdate Patient')
        catalog_item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='WI Backdate Test',
            active=True,
        )
        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )
        basket_item = BasketItem.objects.create(
            basket=basket,
            catalog_item=catalog_item,
            added_by=user,
        )

        past = timezone.now() - datetime.timedelta(days=7)
        work_item = WorkItem.objects.create(
            basket_item=basket_item,
            encounter=encounter,
            spawn_role='primary',
            target_board='lab',
            display_name='WI Backdate Test',
            kind='service',
            effective_at=past,
        )

        assert work_item.effective_at == past

    def test_workitem_as_of_query(self, django_user_model):
        """WorkItem.objects.as_of(timestamp) returns work items effective at that time."""
        from tests.testapp.models import Encounter
        from django.utils import timezone
        import datetime

        user = django_user_model.objects.create_user(
            username='wiasofuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='WI As Of Patient')
        catalog_item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='WI As Of Test',
            active=True,
        )
        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )
        basket_item1 = BasketItem.objects.create(
            basket=basket,
            catalog_item=catalog_item,
            added_by=user,
        )
        basket_item2 = BasketItem.objects.create(
            basket=basket,
            catalog_item=catalog_item,
            added_by=user,
        )

        now = timezone.now()
        past = now - datetime.timedelta(days=7)

        # Old work item
        old_wi = WorkItem.objects.create(
            basket_item=basket_item1,
            encounter=encounter,
            spawn_role='primary',
            target_board='lab',
            display_name='Old WI',
            kind='service',
            effective_at=past,
        )

        # New work item
        new_wi = WorkItem.objects.create(
            basket_item=basket_item2,
            encounter=encounter,
            spawn_role='primary',
            target_board='lab',
            display_name='New WI',
            kind='service',
            effective_at=now,
        )

        # Query as of 5 days ago (should only see old work item)
        five_days_ago = now - datetime.timedelta(days=5)
        wis_then = WorkItem.objects.as_of(five_days_ago).filter(encounter=encounter)
        assert wis_then.count() == 1
        assert wis_then.first() == old_wi

        # Query as of now (should see both)
        wis_now = WorkItem.objects.as_of(now).filter(encounter=encounter)
        assert wis_now.count() == 2
