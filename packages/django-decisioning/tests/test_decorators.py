"""Tests for @idempotent decorator."""
import pytest
from unittest.mock import MagicMock, patch
from django.db import transaction

from django_decisioning.decorators import idempotent
from django_decisioning.models import IdempotencyKey
from django_decisioning.exceptions import DuplicateRequestError


@pytest.mark.django_db
class TestIdempotentDecorator:
    """Test suite for @idempotent decorator."""

    def test_first_call_executes_function(self):
        """First call should execute the wrapped function."""
        call_count = 0

        @idempotent(scope="test")
        def my_operation(key):
            nonlocal call_count
            call_count += 1
            return {"result": "success", "key": key}

        result = my_operation(key="unique-key-1")

        assert call_count == 1
        assert result == {"result": "success", "key": "unique-key-1"}

    def test_retry_returns_cached_result(self):
        """Retry with same key should return cached result without re-executing."""
        call_count = 0

        @idempotent(scope="test")
        def my_operation(key):
            nonlocal call_count
            call_count += 1
            return {"result": "success", "count": call_count}

        # First call
        result1 = my_operation(key="same-key")
        # Second call with same key
        result2 = my_operation(key="same-key")

        assert call_count == 1  # Function only called once
        assert result1 == result2  # Same result returned

    def test_different_keys_execute_separately(self):
        """Different keys should execute the function separately."""
        call_count = 0

        @idempotent(scope="test")
        def my_operation(key):
            nonlocal call_count
            call_count += 1
            return {"key": key, "count": call_count}

        result1 = my_operation(key="key-a")
        result2 = my_operation(key="key-b")

        assert call_count == 2
        assert result1["key"] == "key-a"
        assert result2["key"] == "key-b"

    def test_failed_call_allows_retry(self):
        """Failed operations should allow retry."""
        call_count = 0

        @idempotent(scope="test")
        def my_operation(key, should_fail=False):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise ValueError("Intentional failure")
            return {"success": True}

        # First call fails
        with pytest.raises(ValueError):
            my_operation(key="retry-key", should_fail=True)

        # Second call with same key should be allowed to retry
        result = my_operation(key="retry-key", should_fail=False)

        assert call_count == 2  # Function called twice
        assert result == {"success": True}

    def test_key_derivation_from_args(self):
        """key_from lambda should derive key from function arguments."""
        call_count = 0

        @idempotent(scope="basket_commit", key_from=lambda basket_id, user: str(basket_id))
        def commit_basket(basket_id, user):
            nonlocal call_count
            call_count += 1
            return {"basket_id": basket_id}

        # Same basket_id = same key
        result1 = commit_basket(basket_id=123, user="alice")
        result2 = commit_basket(basket_id=123, user="bob")  # Different user, same basket

        assert call_count == 1  # Only one execution
        assert result1 == result2

    def test_key_from_default_uses_first_arg(self):
        """Without key_from, should use first argument as key."""
        call_count = 0

        @idempotent(scope="test")
        def my_operation(key, extra_arg=None):
            nonlocal call_count
            call_count += 1
            return {"key": key}

        result1 = my_operation("same-key", extra_arg="a")
        result2 = my_operation("same-key", extra_arg="b")

        assert call_count == 1

    def test_creates_idempotency_key_record(self):
        """Decorator should create IdempotencyKey record in database."""
        @idempotent(scope="test_scope")
        def my_operation(key):
            return {"done": True}

        my_operation(key="track-me")

        idem = IdempotencyKey.objects.get(scope="test_scope", key="track-me")
        assert idem.state == IdempotencyKey.State.SUCCEEDED
        assert idem.response_snapshot == {"done": True}

    def test_atomic_transaction_wraps_function(self):
        """Operations should be wrapped in a transaction."""
        @idempotent(scope="test")
        def my_operation(key):
            # Verify we're in a transaction
            assert transaction.get_connection().in_atomic_block
            return {"in_transaction": True}

        result = my_operation(key="atomic-test")
        assert result == {"in_transaction": True}

    def test_scope_is_required(self):
        """Decorator should require scope parameter."""
        with pytest.raises(TypeError):
            @idempotent()  # No scope
            def my_operation(key):
                pass

    def test_stores_error_on_failure(self):
        """Failed operations should store error details."""
        @idempotent(scope="test")
        def failing_operation(key):
            raise ValueError("Test error message")

        with pytest.raises(ValueError):
            failing_operation(key="error-key")

        idem = IdempotencyKey.objects.get(scope="test", key="error-key")
        assert idem.state == IdempotencyKey.State.FAILED
        assert "ValueError" in idem.error_code
        assert "Test error message" in idem.error_message
