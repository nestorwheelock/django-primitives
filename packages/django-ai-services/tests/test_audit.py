"""Tests for django-audit-log integration."""

import pytest
from unittest.mock import patch, Mock


@pytest.mark.django_db
class TestAuditLogIntegration:
    """Tests for audit log integration with AI operations."""

    def test_analyze_object_creates_audit_log(self):
        """analyze_object creates audit log entry on success."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse
        from django.contrib.auth import get_user_model
        from django_audit_log.models import AuditLog

        User = get_user_model()
        user = User.objects.create_user(username="audituser1", password="test")
        target_user = User.objects.create_user(username="targetuser1", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        initial_audit_count = AuditLog.objects.count()

        service = AIService(user=user)

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content='{"category": "user", "confidence": 0.9}',
                model="test",
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.analyze_object(
                obj=target_user,
                analysis_type="user_classification",
                prompt="Classify this user",
            )

        # Check audit log was created
        assert AuditLog.objects.count() == initial_audit_count + 1
        audit = AuditLog.objects.latest("effective_at")
        assert "ai_" in audit.action
        assert audit.actor_user == user

    def test_analyze_object_audit_includes_model_and_cost(self):
        """Audit log metadata includes model and cost information."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse
        from django.contrib.auth import get_user_model
        from django_audit_log.models import AuditLog

        User = get_user_model()
        user = User.objects.create_user(username="audituser2", password="test")
        target_user = User.objects.create_user(username="targetuser2", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService(user=user)

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content='{"result": "test"}',
                model="test-model-v1",
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.0025,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.analyze_object(
                obj=target_user,
                analysis_type="test_analysis",
                prompt="Test prompt",
            )

        audit = AuditLog.objects.latest("effective_at")
        assert audit.metadata.get("model") == "test-model-v1"
        assert "cost_usd" in audit.metadata

    def test_failed_analysis_no_audit_log(self):
        """Failed analysis does not create audit log (only success logs)."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.exceptions import ProviderError
        from django.contrib.auth import get_user_model
        from django_audit_log.models import AuditLog

        User = get_user_model()
        user = User.objects.create_user(username="audituser3", password="test")
        target_user = User.objects.create_user(username="targetuser3", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.fallback_provider = ""
        config.save()

        initial_audit_count = AuditLog.objects.count()

        service = AIService(user=user)

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.side_effect = Exception("API Error")
            mock_get.return_value = mock_provider

            with pytest.raises(ProviderError):
                service.analyze_object(
                    obj=target_user,
                    analysis_type="test_analysis",
                    prompt="Test prompt",
                )

        # No audit log should be created for failed operations
        assert AuditLog.objects.count() == initial_audit_count

    def test_chat_without_target_no_audit_log(self):
        """Regular chat() without target_obj does not create audit log."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse
        from django.contrib.auth import get_user_model
        from django_audit_log.models import AuditLog

        User = get_user_model()
        user = User.objects.create_user(username="audituser4", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        initial_audit_count = AuditLog.objects.count()

        service = AIService(user=user)

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content="response",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": "test"}],
                skip_budget_check=True,
            )

        # No audit log for chat without target
        assert AuditLog.objects.count() == initial_audit_count

    def test_chat_with_target_obj_creates_audit_log(self):
        """chat() with target_obj creates audit log."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse
        from django.contrib.auth import get_user_model
        from django_audit_log.models import AuditLog

        User = get_user_model()
        user = User.objects.create_user(username="audituser5", password="test")
        target = User.objects.create_user(username="targetuser5", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        initial_audit_count = AuditLog.objects.count()

        service = AIService(user=user)

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content="response",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": "test"}],
                target_obj=target,
                skip_budget_check=True,
            )

        # Audit log created when target_obj provided
        assert AuditLog.objects.count() == initial_audit_count + 1
