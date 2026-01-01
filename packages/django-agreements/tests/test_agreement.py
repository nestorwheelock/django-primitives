"""Tests for Agreement model."""
import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone

from django_agreements.models import Agreement, AgreementVersion
from tests.models import Organization, Customer, ServiceContract


User = get_user_model()


@pytest.mark.django_db
class TestAgreementModel:
    """Test suite for Agreement model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    def test_agreement_has_party_a_generic_fk(self, org, customer, user):
        """Agreement should have party_a via GenericFK."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.party_a == org

    def test_agreement_has_party_b_generic_fk(self, org, customer, user):
        """Agreement should have party_b via GenericFK."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.party_b == customer

    def test_agreement_party_ids_are_charfield(self, org, customer, user):
        """Agreement party IDs should be CharField for UUID support."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert isinstance(agreement.party_a_id, str)
        assert isinstance(agreement.party_b_id, str)

    def test_agreement_has_scope_type(self, org, customer, user):
        """Agreement should have scope_type classification."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='subscription',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.scope_type == 'subscription'

    def test_agreement_has_optional_scope_ref(self, org, customer, user):
        """Agreement can have optional scope reference."""
        contract = ServiceContract.objects.create(title="Test Contract", customer=customer)

        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            scope_ref=contract,
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.scope_ref == contract

    def test_agreement_scope_ref_is_nullable(self, org, customer, user):
        """Agreement scope_ref should be nullable."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='consent',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.scope_ref is None

    def test_agreement_has_terms_json_field(self, org, customer, user):
        """Agreement should have terms JSONField."""
        terms = {
            "duration": "12 months",
            "value": 10000,
            "currency": "USD",
            "auto_renew": True,
        }
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms=terms,
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.terms == terms

    def test_agreement_has_valid_from(self, org, customer, user):
        """Agreement should have valid_from datetime."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.valid_from is not None

    def test_agreement_valid_from_defaults_to_agreed_at(self, org, customer, user):
        """Agreement valid_from should default to agreed_at."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=now,
            agreed_by=user,
        )
        # valid_from defaults via model save
        assert agreement.valid_from is not None

    def test_agreement_has_valid_to_nullable(self, org, customer, user):
        """Agreement should have nullable valid_to datetime."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
            valid_to=None,
        )
        assert agreement.valid_to is None

    def test_agreement_has_agreed_at(self, org, customer, user):
        """Agreement should have agreed_at datetime."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.agreed_at == now

    def test_agreement_has_agreed_by(self, org, customer, user):
        """Agreement should have agreed_by user FK."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.agreed_by == user

    def test_agreement_has_version_field(self, org, customer, user):
        """Agreement should have version field for optimistic locking."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.version == 1

    def test_agreement_has_timestamps(self, org, customer, user):
        """Agreement should have created_at and updated_at."""
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        assert agreement.created_at is not None
        assert agreement.updated_at is not None


@pytest.mark.django_db
class TestAgreementProperties:
    """Test suite for Agreement properties."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    def test_is_active_returns_true_when_valid(self, org, customer, user):
        """is_active should return True when agreement is currently valid."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=30),
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.is_active is True

    def test_is_active_returns_false_when_expired(self, org, customer, user):
        """is_active should return False when agreement has expired."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            valid_from=now - timedelta(days=60),
            valid_to=now - timedelta(days=1),
            agreed_at=now - timedelta(days=60),
            agreed_by=user,
        )
        assert agreement.is_active is False

    def test_is_active_returns_false_when_not_yet_valid(self, org, customer, user):
        """is_active should return False when agreement is not yet valid."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            valid_from=now + timedelta(days=7),
            valid_to=now + timedelta(days=30),
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.is_active is False

    def test_is_active_returns_true_when_no_end_date(self, org, customer, user):
        """is_active should return True when valid_to is None (no expiration)."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            valid_from=now - timedelta(days=1),
            valid_to=None,
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.is_active is True


@pytest.mark.django_db
class TestAgreementQuerySet:
    """Test suite for Agreement queryset methods."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def customer2(self, org):
        """Create another test customer."""
        return Customer.objects.create(name="Customer 2", org=org)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    def test_for_party_returns_agreements_as_party_a(self, org, customer, user):
        """for_party() should return agreements where object is party_a."""
        Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            agreed_at=timezone.now(),
            agreed_by=user,
        )

        agreements = Agreement.objects.for_party(org)
        assert agreements.count() == 1

    def test_for_party_returns_agreements_as_party_b(self, org, customer, user):
        """for_party() should return agreements where object is party_b."""
        Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            agreed_at=timezone.now(),
            agreed_by=user,
        )

        agreements = Agreement.objects.for_party(customer)
        assert agreements.count() == 1

    def test_for_party_returns_both_directions(self, org, customer, customer2, user):
        """for_party() should return agreements in both directions."""
        # Org is party_a
        Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            agreed_at=timezone.now(),
            agreed_by=user,
        )
        # Customer is party_a, org is party_b
        Agreement.objects.create(
            party_a=customer,
            party_b=org,
            scope_type='contract',
            terms={},
            agreed_at=timezone.now(),
            agreed_by=user,
        )

        org_agreements = Agreement.objects.for_party(org)
        assert org_agreements.count() == 2

    def test_current_returns_active_agreements(self, org, customer, user):
        """current() should return currently valid agreements."""
        now = timezone.now()

        # Active agreement
        active = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=30),
            agreed_at=now,
            agreed_by=user,
        )

        # Expired agreement
        Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            valid_from=now - timedelta(days=60),
            valid_to=now - timedelta(days=1),
            agreed_at=now - timedelta(days=60),
            agreed_by=user,
        )

        current = Agreement.objects.current()
        assert current.count() == 1
        assert active in current

    def test_as_of_returns_agreements_valid_at_date(self, org, customer, user):
        """as_of() should return agreements valid at a specific date."""
        now = timezone.now()
        past = now - timedelta(days=30)

        # Agreement valid in the past
        past_agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            valid_from=past - timedelta(days=10),
            valid_to=past + timedelta(days=10),
            agreed_at=past - timedelta(days=10),
            agreed_by=user,
        )

        # Agreement valid now
        Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            valid_from=now - timedelta(days=5),
            valid_to=now + timedelta(days=30),
            agreed_at=now - timedelta(days=5),
            agreed_by=user,
        )

        # Query as of past date
        as_of_past = Agreement.objects.as_of(past)
        assert as_of_past.count() == 1
        assert past_agreement in as_of_past


@pytest.mark.django_db
class TestAgreementVersionModel:
    """Test suite for AgreementVersion model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def agreement(self, org, customer, user):
        """Create a test agreement."""
        return Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_at=timezone.now(),
            agreed_by=user,
        )

    def test_version_has_agreement_fk(self, agreement, user):
        """AgreementVersion should have agreement FK."""
        version = AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms={"value": 10000},
            created_by=user,
            reason="Initial agreement",
        )
        assert version.agreement == agreement

    def test_version_has_version_number(self, agreement, user):
        """AgreementVersion should have version number."""
        version = AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms={"value": 10000},
            created_by=user,
            reason="Initial",
        )
        assert version.version == 1

    def test_version_has_terms_snapshot(self, agreement, user):
        """AgreementVersion should store terms snapshot."""
        terms = {"value": 12000, "duration": "24 months"}
        version = AgreementVersion.objects.create(
            agreement=agreement,
            version=2,
            terms=terms,
            created_by=user,
            reason="Extended contract",
        )
        assert version.terms == terms

    def test_version_has_created_by(self, agreement, user):
        """AgreementVersion should track who created it."""
        version = AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms={"value": 10000},
            created_by=user,
            reason="Initial",
        )
        assert version.created_by == user

    def test_version_has_reason(self, agreement, user):
        """AgreementVersion should have reason for amendment."""
        version = AgreementVersion.objects.create(
            agreement=agreement,
            version=2,
            terms={"value": 12000},
            created_by=user,
            reason="Price increase due to scope expansion",
        )
        assert version.reason == "Price increase due to scope expansion"

    def test_version_has_created_at(self, agreement, user):
        """AgreementVersion should have created_at timestamp."""
        version = AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms={"value": 10000},
            created_by=user,
            reason="Initial",
        )
        assert version.created_at is not None

    def test_version_unique_constraint(self, agreement, user):
        """Agreement + version should be unique."""
        from django.db import IntegrityError

        AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms={"value": 10000},
            created_by=user,
            reason="Initial",
        )

        with pytest.raises(IntegrityError):
            AgreementVersion.objects.create(
                agreement=agreement,
                version=1,
                terms={"value": 11000},
                created_by=user,
                reason="Duplicate version",
            )

    def test_versions_ordered_by_version_desc(self, agreement, user):
        """AgreementVersion should be ordered by version descending."""
        AgreementVersion.objects.create(
            agreement=agreement, version=1, terms={}, created_by=user, reason="v1"
        )
        AgreementVersion.objects.create(
            agreement=agreement, version=2, terms={}, created_by=user, reason="v2"
        )
        AgreementVersion.objects.create(
            agreement=agreement, version=3, terms={}, created_by=user, reason="v3"
        )

        versions = list(agreement.versions.all())
        assert versions[0].version == 3
        assert versions[1].version == 2
        assert versions[2].version == 1
