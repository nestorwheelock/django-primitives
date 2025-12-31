"""Tests for WorkItem routing correctness.

These tests verify that catalog items route to the correct boards
based on kind, service_category, and stock_action.
"""

import pytest

from django_catalog.models import CatalogItem
from django_catalog.services import determine_target_board


@pytest.mark.django_db
class TestRoutingRules:
    """Routing rules are deterministic and correct."""

    # Stock item routing tests
    def test_stock_item_dispense_routes_to_pharmacy(self):
        """Stock item with dispense action routes to pharmacy board."""
        item = CatalogItem(
            kind='stock_item',
            default_stock_action='dispense',
            display_name='Medication',
        )
        assert determine_target_board(item) == 'pharmacy'

    def test_stock_item_administer_routes_to_treatment(self):
        """Stock item with administer action routes to treatment board."""
        item = CatalogItem(
            kind='stock_item',
            default_stock_action='administer',
            display_name='Injectable',
        )
        assert determine_target_board(item) == 'treatment'

    def test_stock_item_no_action_defaults_to_pharmacy(self):
        """Stock item with no action defaults to pharmacy board."""
        item = CatalogItem(
            kind='stock_item',
            default_stock_action='',
            display_name='Supply',
        )
        assert determine_target_board(item) == 'pharmacy'

    def test_stock_action_override_takes_precedence(self):
        """Override stock action takes precedence over default."""
        item = CatalogItem(
            kind='stock_item',
            default_stock_action='dispense',
            display_name='Medication',
        )
        # Default would route to pharmacy, but override to treatment
        assert determine_target_board(item, stock_action_override='administer') == 'treatment'

    # Service routing tests
    def test_service_lab_routes_to_lab(self):
        """Service with lab category routes to lab board."""
        item = CatalogItem(
            kind='service',
            service_category='lab',
            display_name='Blood Test',
        )
        assert determine_target_board(item) == 'lab'

    def test_service_imaging_routes_to_imaging(self):
        """Service with imaging category routes to imaging board."""
        item = CatalogItem(
            kind='service',
            service_category='imaging',
            display_name='X-Ray',
        )
        assert determine_target_board(item) == 'imaging'

    def test_service_procedure_routes_to_treatment(self):
        """Service with procedure category routes to treatment board."""
        item = CatalogItem(
            kind='service',
            service_category='procedure',
            display_name='Surgical Procedure',
        )
        assert determine_target_board(item) == 'treatment'

    def test_service_consult_routes_to_treatment(self):
        """Service with consult category routes to treatment board."""
        item = CatalogItem(
            kind='service',
            service_category='consult',
            display_name='Specialist Consultation',
        )
        assert determine_target_board(item) == 'treatment'

    def test_service_vaccine_routes_to_treatment(self):
        """Service with vaccine category routes to treatment board."""
        item = CatalogItem(
            kind='service',
            service_category='vaccine',
            display_name='Flu Shot',
        )
        assert determine_target_board(item) == 'treatment'

    def test_service_other_routes_to_treatment(self):
        """Service with other category routes to treatment board."""
        item = CatalogItem(
            kind='service',
            service_category='other',
            display_name='Misc Service',
        )
        assert determine_target_board(item) == 'treatment'

    def test_service_no_category_routes_to_treatment(self):
        """Service with no category defaults to treatment board."""
        item = CatalogItem(
            kind='service',
            service_category='',
            display_name='Generic Service',
        )
        assert determine_target_board(item) == 'treatment'

    # Unknown kind edge case
    def test_unknown_kind_routes_to_treatment(self):
        """Unknown kind defaults to treatment board (safe fallback)."""
        item = CatalogItem(
            kind='unknown',  # This shouldn't happen but handle gracefully
            display_name='Unknown',
        )
        assert determine_target_board(item) == 'treatment'


@pytest.mark.django_db
class TestRoutingThroughCommit:
    """Routing is correctly applied through the full commit flow."""

    @pytest.fixture
    def user(self, django_user_model):
        return django_user_model.objects.create_user(username='routetest', password='test')

    @pytest.fixture
    def encounter(self):
        from tests.testapp.models import Encounter
        return Encounter.objects.create(patient_name='Route Test')

    def test_lab_service_creates_lab_workitem(self, user, encounter):
        """Lab service creates WorkItem on lab board."""
        from django_catalog.services import (
            get_or_create_draft_basket,
            add_item_to_basket,
            commit_basket,
        )

        item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='CBC',
            active=True,
        )

        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, item, user)
        work_items = commit_basket(basket, user)

        assert work_items[0].target_board == 'lab'

    def test_pharmacy_stock_creates_pharmacy_workitem(self, user, encounter):
        """Dispense stock item creates WorkItem on pharmacy board."""
        from django_catalog.services import (
            get_or_create_draft_basket,
            add_item_to_basket,
            commit_basket,
        )

        item = CatalogItem.objects.create(
            kind='stock_item',
            default_stock_action='dispense',
            display_name='Amoxicillin',
            active=True,
        )

        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, item, user)
        work_items = commit_basket(basket, user)

        assert work_items[0].target_board == 'pharmacy'

    def test_stock_action_override_in_basket_item(self, user, encounter):
        """Stock action override in BasketItem affects routing."""
        from django_catalog.services import (
            get_or_create_draft_basket,
            add_item_to_basket,
            commit_basket,
        )

        item = CatalogItem.objects.create(
            kind='stock_item',
            default_stock_action='dispense',  # Would go to pharmacy
            display_name='Injectable Med',
            active=True,
        )

        basket = get_or_create_draft_basket(encounter, user)
        # Override to administer -> should go to treatment
        add_item_to_basket(basket, item, user, stock_action_override='administer')
        work_items = commit_basket(basket, user)

        assert work_items[0].target_board == 'treatment'

    def test_multiple_items_route_to_different_boards(self, user, encounter):
        """Multiple items in one basket route to their correct boards."""
        from django_catalog.services import (
            get_or_create_draft_basket,
            add_item_to_basket,
            commit_basket,
        )

        lab_item = CatalogItem.objects.create(
            kind='service', service_category='lab',
            display_name='Blood Test', active=True,
        )
        imaging_item = CatalogItem.objects.create(
            kind='service', service_category='imaging',
            display_name='X-Ray', active=True,
        )
        pharmacy_item = CatalogItem.objects.create(
            kind='stock_item', default_stock_action='dispense',
            display_name='Medication', active=True,
        )

        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, lab_item, user)
        add_item_to_basket(basket, imaging_item, user)
        add_item_to_basket(basket, pharmacy_item, user)
        work_items = commit_basket(basket, user)

        boards = {wi.target_board for wi in work_items}
        assert boards == {'lab', 'imaging', 'pharmacy'}
