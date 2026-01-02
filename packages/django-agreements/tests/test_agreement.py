"""Tests for Agreement models and services."""
import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from django_agreements.models import Agreement, AgreementVersion
from django_agreements.services import (
    create_agreement,
    amend_agreement,
    terminate_agreement,
    get_terms_as_of,
    InvalidTerminationError,
)
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

    def test_agreement_has_uuid_pk(self, org, customer, user):
        """Agreement should have UUID primary key from BaseModel."""
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
        # UUID is a 36-char string representation
        assert len(str(agreement.id)) == 36
        assert '-' in str(agreement.id)

    def test_agreement_has_party_a_generic_fk(self, org, customer, user):
        """Agreement should have party_a via GenericFK."""
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
        assert agreement.party_a == org

    def test_agreement_has_party_b_generic_fk(self, org, customer, user):
        """Agreement should have party_b via GenericFK."""
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
        assert agreement.party_b == customer

    def test_agreement_party_ids_are_charfield(self, org, customer, user):
        """Agreement party IDs should be CharField for UUID support."""
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
        assert isinstance(agreement.party_a_id, str)
        assert isinstance(agreement.party_b_id, str)

    def test_agreement_has_scope_type(self, org, customer, user):
        """Agreement should have scope_type classification."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='subscription',
            terms={"term": "value"},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.scope_type == 'subscription'

    def test_agreement_has_optional_scope_ref(self, org, customer, user):
        """Agreement can have optional scope reference."""
        now = timezone.now()
        contract = ServiceContract.objects.create(title="Test Contract", customer=customer)

        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            scope_ref=contract,
            terms={"term": "value"},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.scope_ref == contract

    def test_agreement_scope_ref_is_nullable(self, org, customer, user):
        """Agreement scope_ref should be nullable."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='consent',
            terms={"term": "value"},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
            valid_to=None,
        )
        assert agreement.scope_ref is None

    def test_agreement_has_terms_json_field(self, org, customer, user):
        """Agreement should have terms JSONField."""
        now = timezone.now()
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
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.terms == terms

    def test_agreement_valid_from_is_required(self, org, customer, user):
        """Agreement valid_from should be required (no default)."""
        now = timezone.now()
        # This should work with valid_from
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.valid_from == now

    def test_agreement_has_valid_to_nullable(self, org, customer, user):
        """Agreement should have nullable valid_to datetime."""
        now = timezone.now()
        agreement = Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"term": "value"},
            valid_from=now,
            agreed_at=now,
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
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )
        assert agreement.agreed_at == now

    def test_agreement_has_agreed_by(self, org, customer, user):
        """Agreement should have agreed_by user FK."""
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
        assert agreement.agreed_by == user

    def test_agreement_has_current_version_field(self, org, customer, user):
        """Agreement should have current_version field."""
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
        assert agreement.current_version == 1

    def test_agreement_has_timestamps(self, org, customer, user):
        """Agreement should have created_at and updated_at from BaseModel."""
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
        assert agreement.created_at is not None
        assert agreement.updated_at is not None

    def test_agreement_has_soft_delete(self, org, customer, user):
        """Agreement should have soft delete from BaseModel."""
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
        assert agreement.deleted_at is None

        # Soft delete
        agreement.delete()
        agreement.refresh_from_db()
        assert agreement.deleted_at is not None

        # Should be excluded from default manager
        assert Agreement.objects.filter(pk=agreement.pk).count() == 0
        # But accessible via all_objects
        assert Agreement.all_objects.filter(pk=agreement.pk).count() == 1

    def test_valid_to_must_be_after_valid_from(self, org, customer, user):
        """Database constraint should prevent valid_to <= valid_from."""
        now = timezone.now()
        with pytest.raises(IntegrityError):
            Agreement.objects.create(
                party_a=org,
                party_b=customer,
                scope_type='service_contract',
                terms={"term": "value"},
                valid_from=now,
                valid_to=now - timedelta(days=1),  # Before valid_from
                agreed_at=now,
                agreed_by=user,
            )


@pytest.mark.django_db
class TestAgreementProperties:
    """Test suite for Agreement properties."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
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
        """is_active should return True when valid_to is None."""
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
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def customer2(self, org):
        return Customer.objects.create(name="Customer 2", org=org)

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="testpass")

    def test_for_party_returns_agreements_as_party_a(self, org, customer, user):
        """for_party() should return agreements where object is party_a."""
        now = timezone.now()
        Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )

        agreements = Agreement.objects.for_party(org)
        assert agreements.count() == 1

    def test_for_party_returns_agreements_as_party_b(self, org, customer, user):
        """for_party() should return agreements where object is party_b."""
        now = timezone.now()
        Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )

        agreements = Agreement.objects.for_party(customer)
        assert agreements.count() == 1

    def test_for_party_returns_both_directions(self, org, customer, customer2, user):
        """for_party() should return agreements in both directions."""
        now = timezone.now()
        Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='contract',
            terms={},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )
        Agreement.objects.create(
            party_a=customer,
            party_b=org,
            scope_type='contract',
            terms={},
            valid_from=now,
            agreed_at=now,
            agreed_by=user,
        )

        org_agreements = Agreement.objects.for_party(org)
        assert org_agreements.count() == 2

    def test_current_returns_active_agreements(self, org, customer, user):
        """current() should return currently valid agreements."""
        now = timezone.now()

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

        as_of_past = Agreement.objects.as_of(past)
        assert as_of_past.count() == 1
        assert past_agreement in as_of_past


@pytest.mark.django_db
class TestAgreementVersionModel:
    """Test suite for AgreementVersion model."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def agreement(self, org, customer, user):
        now = timezone.now()
        return Agreement.objects.create(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            valid_from=now,
            agreed_at=now,
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

    def test_version_unique_constraint(self, agreement, user):
        """Agreement + version should be unique."""
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


@pytest.mark.django_db
class TestCreateAgreementService:
    """Test suite for create_agreement service."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="testpass")

    def test_create_agreement_returns_agreement(self, org, customer, user):
        """create_agreement should return an Agreement instance."""
        now = timezone.now()
        agreement = create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=now,
        )
        assert isinstance(agreement, Agreement)
        assert agreement.pk is not None

    def test_create_agreement_creates_version_1(self, org, customer, user):
        """create_agreement should create initial AgreementVersion."""
        now = timezone.now()
        agreement = create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=now,
        )
        assert agreement.versions.count() == 1
        version = agreement.versions.first()
        assert version.version == 1
        assert version.terms == {"value": 10000}
        assert version.reason == "Initial agreement"

    def test_create_agreement_sets_current_version(self, org, customer, user):
        """create_agreement should set current_version to 1."""
        now = timezone.now()
        agreement = create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=now,
        )
        assert agreement.current_version == 1

    def test_create_agreement_defaults_agreed_at_to_now(self, org, customer, user):
        """create_agreement should default agreed_at to now."""
        before = timezone.now()
        agreement = create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=before,
        )
        after = timezone.now()
        assert before <= agreement.agreed_at <= after

    def test_create_agreement_rejects_invalid_dates(self, org, customer, user):
        """create_agreement should reject valid_to <= valid_from."""
        now = timezone.now()
        with pytest.raises(ValueError, match="valid_to must be after valid_from"):
            create_agreement(
                party_a=org,
                party_b=customer,
                scope_type='service_contract',
                terms={"value": 10000},
                agreed_by=user,
                valid_from=now,
                valid_to=now - timedelta(days=1),
            )


@pytest.mark.django_db
class TestAmendAgreementService:
    """Test suite for amend_agreement service."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def agreement(self, org, customer, user):
        return create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=timezone.now(),
        )

    def test_amend_agreement_increments_version(self, agreement, user):
        """amend_agreement should increment current_version."""
        updated = amend_agreement(
            agreement=agreement,
            new_terms={"value": 12000},
            reason="Price increase",
            amended_by=user,
        )
        assert updated.current_version == 2

    def test_amend_agreement_updates_terms_projection(self, agreement, user):
        """amend_agreement should update Agreement.terms."""
        updated = amend_agreement(
            agreement=agreement,
            new_terms={"value": 12000, "notes": "Extended"},
            reason="Price increase",
            amended_by=user,
        )
        assert updated.terms == {"value": 12000, "notes": "Extended"}

    def test_amend_agreement_creates_version_record(self, agreement, user):
        """amend_agreement should create new AgreementVersion."""
        amend_agreement(
            agreement=agreement,
            new_terms={"value": 12000},
            reason="Price increase",
            amended_by=user,
        )
        assert agreement.versions.count() == 2
        latest = agreement.versions.first()
        assert latest.version == 2
        assert latest.terms == {"value": 12000}
        assert latest.reason == "Price increase"

    def test_amend_agreement_preserves_original_version(self, agreement, user):
        """amend_agreement should preserve original version in ledger."""
        original_terms = agreement.terms.copy()
        amend_agreement(
            agreement=agreement,
            new_terms={"value": 12000},
            reason="Price increase",
            amended_by=user,
        )
        v1 = agreement.versions.get(version=1)
        assert v1.terms == original_terms


@pytest.mark.django_db
class TestTerminateAgreementService:
    """Test suite for terminate_agreement service."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def agreement(self, org, customer, user):
        return create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=timezone.now() - timedelta(days=30),
        )

    def test_terminate_agreement_sets_valid_to(self, agreement, user):
        """terminate_agreement should set valid_to."""
        before = timezone.now()
        terminated = terminate_agreement(
            agreement=agreement,
            terminated_by=user,
        )
        after = timezone.now()
        assert before <= terminated.valid_to <= after

    def test_terminate_agreement_creates_version_record(self, agreement, user):
        """terminate_agreement should create version record."""
        terminate_agreement(
            agreement=agreement,
            terminated_by=user,
            reason="Contract cancelled",
        )
        assert agreement.versions.count() == 2
        latest = agreement.versions.first()
        assert latest.reason == "Contract cancelled"

    def test_terminate_agreement_increments_version(self, agreement, user):
        """terminate_agreement should increment current_version."""
        terminated = terminate_agreement(
            agreement=agreement,
            terminated_by=user,
        )
        assert terminated.current_version == 2

    def test_terminate_agreement_rejects_invalid_date(self, org, customer, user):
        """terminate_agreement should reject valid_to <= valid_from."""
        now = timezone.now()
        agreement = create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=now,
        )
        with pytest.raises(InvalidTerminationError):
            terminate_agreement(
                agreement=agreement,
                terminated_by=user,
                valid_to=now - timedelta(days=1),
            )


@pytest.mark.django_db
class TestGetTermsAsOfService:
    """Test suite for get_terms_as_of service."""

    @pytest.fixture
    def org(self):
        return Organization.objects.create(name="Vendor Corp")

    @pytest.fixture
    def customer(self, org):
        return Customer.objects.create(name="Customer Inc", org=org)

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="testpass")

    def test_get_terms_as_of_returns_latest_terms(self, org, customer, user):
        """get_terms_as_of should return terms at timestamp."""
        agreement = create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=timezone.now(),
        )
        terms = get_terms_as_of(agreement, timezone.now())
        assert terms == {"value": 10000}

    def test_get_terms_as_of_returns_none_before_creation(self, org, customer, user):
        """get_terms_as_of should return None before any version exists."""
        past = timezone.now() - timedelta(days=30)
        agreement = create_agreement(
            party_a=org,
            party_b=customer,
            scope_type='service_contract',
            terms={"value": 10000},
            agreed_by=user,
            valid_from=timezone.now(),
        )
        terms = get_terms_as_of(agreement, past)
        assert terms is None
