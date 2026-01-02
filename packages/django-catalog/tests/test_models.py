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
        mid = now - datetime.timedelta(days=3)

        # Old basket
        old_basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            effective_at=past,
        )

        # New basket
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
