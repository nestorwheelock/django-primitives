"""Decorators for decisioning operations."""
import functools
import json
from django.db import models, transaction
from django.utils import timezone


def _serialize_result(result):
    """Serialize result for JSON storage, converting Django models to PKs."""
    if result is None:
        return None

    if isinstance(result, models.Model):
        return {'__model__': True, 'pk': str(result.pk)}

    if isinstance(result, (list, tuple)):
        serialized = []
        for item in result:
            if isinstance(item, models.Model):
                serialized.append({'__model__': True, 'pk': str(item.pk)})
            else:
                serialized.append(item)
        return serialized

    if isinstance(result, dict):
        serialized = {}
        for k, v in result.items():
            if isinstance(v, models.Model):
                serialized[k] = {'__model__': True, 'pk': str(v.pk)}
            else:
                serialized[k] = v
        return serialized

    return result


def idempotent(scope, key_from=None, timeout=None):
    """
    Decorator for idempotent operations.

    Ensures the decorated function executes at most once for a given key.
    Retries return the cached result. Failed operations can be retried.

    Args:
        scope: The scope for the idempotency key (e.g., 'basket_commit')
               REQUIRED - raises TypeError if not provided
        key_from: Function to derive key from args
                  (e.g., lambda basket, user: str(basket.id))
                  If not provided, uses the first positional arg or 'key' kwarg
        timeout: Lock timeout in seconds for stale lock detection (not yet implemented)

    Usage:
        @idempotent(scope='basket_commit', key_from=lambda basket, user: str(basket.id))
        def commit_basket(basket, user):
            # This will only execute once per basket
            return create_work_items(basket)

    Note: If the function returns Django model instances, they will be serialized
    as PKs in the cache. On retry, the cached PKs are returned (not model instances).
    Callers should query the database if they need the actual objects.

    Returns:
        Decorated function that ensures idempotent execution
    """
    if scope is None:
        raise TypeError("idempotent() requires 'scope' parameter")

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from django_decisioning.models import IdempotencyKey

            # Derive the idempotency key
            if key_from is not None:
                key = key_from(*args, **kwargs)
            elif args:
                key = str(args[0])
            elif 'key' in kwargs:
                key = str(kwargs['key'])
            else:
                raise ValueError("Cannot derive idempotency key: no key_from provided and no arguments")

            # Phase 1: Acquire/check idempotency key
            with transaction.atomic():
                idem, created = IdempotencyKey.objects.select_for_update().get_or_create(
                    scope=scope,
                    key=key,
                    defaults={
                        'state': IdempotencyKey.State.PROCESSING,
                        'locked_at': timezone.now()
                    }
                )

                if not created:
                    # Record exists - check state
                    if idem.state == IdempotencyKey.State.SUCCEEDED:
                        # Return cached result
                        return idem.response_snapshot

                    elif idem.state == IdempotencyKey.State.FAILED:
                        # Failed - allow retry by resetting state
                        idem.state = IdempotencyKey.State.PROCESSING
                        idem.locked_at = timezone.now()
                        idem.error_code = ''
                        idem.error_message = ''
                        idem.save()

                    elif idem.state == IdempotencyKey.State.PROCESSING:
                        # In-flight - for now, allow retry (could add timeout logic)
                        idem.locked_at = timezone.now()
                        idem.save()

                    elif idem.state == IdempotencyKey.State.PENDING:
                        # Pending - transition to processing
                        idem.state = IdempotencyKey.State.PROCESSING
                        idem.locked_at = timezone.now()
                        idem.save()

            # Phase 2: Execute function in its own transaction
            try:
                with transaction.atomic():
                    result = func(*args, **kwargs)

                # Phase 3: Mark success (separate transaction)
                with transaction.atomic():
                    idem.refresh_from_db()
                    idem.state = IdempotencyKey.State.SUCCEEDED
                    # Serialize result for JSON storage
                    idem.response_snapshot = _serialize_result(result)
                    idem.save()

                return result

            except Exception as e:
                # Phase 4: Mark failure (separate transaction so it persists)
                with transaction.atomic():
                    idem.refresh_from_db()
                    idem.state = IdempotencyKey.State.FAILED
                    idem.error_code = type(e).__name__
                    idem.error_message = str(e)
                    idem.save()
                raise

        return wrapper
    return decorator
