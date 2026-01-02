"""
Query count tests for django-parties.

These tests enforce query budgets to prevent N+1 regressions.
Run with: pytest tests/test_query_counts.py -v
"""
import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection


class TestQueryBudgets:
    """Enforce query count limits on critical paths."""


    @pytest.mark.django_db
    def test_get_full_name_query_count(self):
        """Verify get_full_name stays within query budget."""
        # TODO: Set up test data
        # records = [Model.objects.create(...) for _ in range(10)]

        with CaptureQueriesContext(connection) as context:
            # TODO: Call the function under test
            # result = get_full_name(...)
            pass

        # TODO: Set expected query count
        expected_queries = 2  # 1 for main query + 1 for prefetch
        assert len(context) <= expected_queries, (
            f"Query budget exceeded: {len(context)} > {expected_queries}\n"
            f"Queries:\n" + "\n".join(q['sql'] for q in context)
        )

    @pytest.mark.django_db
    def test_get_short_name_query_count(self):
        """Verify get_short_name stays within query budget."""
        # TODO: Set up test data
        # records = [Model.objects.create(...) for _ in range(10)]

        with CaptureQueriesContext(connection) as context:
            # TODO: Call the function under test
            # result = get_short_name(...)
            pass

        # TODO: Set expected query count
        expected_queries = 2  # 1 for main query + 1 for prefetch
        assert len(context) <= expected_queries, (
            f"Query budget exceeded: {len(context)} > {expected_queries}\n"
            f"Queries:\n" + "\n".join(q['sql'] for q in context)
        )

    @pytest.mark.django_db
    def test_get_person_by_id_query_count(self):
        """Verify get_person_by_id stays within query budget."""
        # TODO: Set up test data
        # records = [Model.objects.create(...) for _ in range(10)]

        with CaptureQueriesContext(connection) as context:
            # TODO: Call the function under test
            # result = get_person_by_id(...)
            pass

        # TODO: Set expected query count
        expected_queries = 2  # 1 for main query + 1 for prefetch
        assert len(context) <= expected_queries, (
            f"Query budget exceeded: {len(context)} > {expected_queries}\n"
            f"Queries:\n" + "\n".join(q['sql'] for q in context)
        )

    @pytest.mark.django_db
    def test_get_person_by_email_query_count(self):
        """Verify get_person_by_email stays within query budget."""
        # TODO: Set up test data
        # records = [Model.objects.create(...) for _ in range(10)]

        with CaptureQueriesContext(connection) as context:
            # TODO: Call the function under test
            # result = get_person_by_email(...)
            pass

        # TODO: Set expected query count
        expected_queries = 2  # 1 for main query + 1 for prefetch
        assert len(context) <= expected_queries, (
            f"Query budget exceeded: {len(context)} > {expected_queries}\n"
            f"Queries:\n" + "\n".join(q['sql'] for q in context)
        )

    @pytest.mark.django_db
    def test_get_active_people_query_count(self):
        """Verify get_active_people stays within query budget."""
        # TODO: Set up test data
        # records = [Model.objects.create(...) for _ in range(10)]

        with CaptureQueriesContext(connection) as context:
            # TODO: Call the function under test
            # result = get_active_people(...)
            pass

        # TODO: Set expected query count
        expected_queries = 2  # 1 for main query + 1 for prefetch
        assert len(context) <= expected_queries, (
            f"Query budget exceeded: {len(context)} > {expected_queries}\n"
            f"Queries:\n" + "\n".join(q['sql'] for q in context)
        )
