"""Tests for AIAnalysis model and analyze_object service."""

import pytest
from unittest.mock import patch, Mock
from decimal import Decimal
import hashlib


@pytest.mark.django_db
class TestAIAnalysisModel:
    """Tests for AIAnalysis model."""

    def test_create_analysis_record(self):
        """AIAnalysis can be created with GenericFK target."""
        from django_ai_services.models import AIAnalysis
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="test")

        content_type = ContentType.objects.get_for_model(User)
        input_data = {"text": "Sample text to analyze"}
        input_hash = hashlib.sha256(str(input_data).encode()).hexdigest()

        analysis = AIAnalysis.objects.create(
            target_content_type=content_type,
            target_object_id=str(user.pk),
            analysis_type="classification",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            input_data=input_data,
            input_hash=input_hash,
            result={"category": "person", "confidence": 0.95},
            confidence=Decimal("0.95"),
        )

        assert analysis.pk is not None
        assert analysis.target == user
        assert analysis.analysis_type == "classification"
        assert analysis.result["category"] == "person"

    def test_analysis_confidence_constraint(self):
        """AIAnalysis.confidence must be between 0 and 1."""
        from django_ai_services.models import AIAnalysis
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth import get_user_model
        from django.db import IntegrityError

        User = get_user_model()
        user = User.objects.create_user(username="testuser2", password="test")
        content_type = ContentType.objects.get_for_model(User)

        # Confidence > 1 should fail
        with pytest.raises(IntegrityError):
            AIAnalysis.objects.create(
                target_content_type=content_type,
                target_object_id=str(user.pk),
                analysis_type="test",
                provider="openrouter",
                model="test",
                input_data={},
                input_hash="abc123",
                result={},
                confidence=Decimal("1.5"),  # Invalid
            )

    def test_analysis_null_confidence_allowed(self):
        """AIAnalysis.confidence can be null."""
        from django_ai_services.models import AIAnalysis
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="testuser3", password="test")
        content_type = ContentType.objects.get_for_model(User)

        analysis = AIAnalysis.objects.create(
            target_content_type=content_type,
            target_object_id=str(user.pk),
            analysis_type="summarization",
            provider="openrouter",
            model="test",
            input_data={"text": "Test"},
            input_hash="def456",
            result={"summary": "A test"},
            confidence=None,
        )

        assert analysis.confidence is None

    def test_analysis_links_to_usage_log(self):
        """AIAnalysis can link to AIUsageLog."""
        from django_ai_services.models import AIAnalysis, AIUsageLog
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="testuser4", password="test")
        content_type = ContentType.objects.get_for_model(User)

        usage_log = AIUsageLog.objects.create(
            operation="analyze",
            provider="openrouter",
            model="test",
            input_tokens=100,
            output_tokens=50,
        )

        analysis = AIAnalysis.objects.create(
            target_content_type=content_type,
            target_object_id=str(user.pk),
            analysis_type="classification",
            provider="openrouter",
            model="test",
            input_data={},
            input_hash="ghi789",
            result={},
            usage_log=usage_log,
        )

        assert analysis.usage_log == usage_log
        assert usage_log.analyses.first() == analysis

    def test_analysis_review_fields(self):
        """AIAnalysis tracks review status."""
        from django_ai_services.models import AIAnalysis
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        User = get_user_model()
        user = User.objects.create_user(username="testuser5", password="test")
        reviewer = User.objects.create_user(username="reviewer", password="test")
        content_type = ContentType.objects.get_for_model(User)

        analysis = AIAnalysis.objects.create(
            target_content_type=content_type,
            target_object_id=str(user.pk),
            analysis_type="classification",
            provider="openrouter",
            model="test",
            input_data={},
            input_hash="jkl012",
            result={},
        )

        assert analysis.is_reviewed is False
        assert analysis.reviewed_by is None

        # Mark as reviewed
        analysis.is_reviewed = True
        analysis.reviewed_by = reviewer
        analysis.reviewed_at = timezone.now()
        analysis.save()

        analysis.refresh_from_db()
        assert analysis.is_reviewed is True
        assert analysis.reviewed_by == reviewer

    def test_analysis_validation_tracking(self):
        """AIAnalysis tracks validation status and repair attempts."""
        from django_ai_services.models import AIAnalysis
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="testuser6", password="test")
        content_type = ContentType.objects.get_for_model(User)

        analysis = AIAnalysis.objects.create(
            target_content_type=content_type,
            target_object_id=str(user.pk),
            analysis_type="classification",
            provider="openrouter",
            model="test",
            input_data={},
            input_hash="mno345",
            result={},
            validation_passed=False,
            validation_errors=["Missing required field"],
            repair_attempts=2,
        )

        assert analysis.validation_passed is False
        assert len(analysis.validation_errors) == 1
        assert analysis.repair_attempts == 2


@pytest.mark.django_db
class TestAnalyzeObjectService:
    """Tests for analyze_object service method."""

    def test_analyze_object_creates_analysis(self):
        """analyze_object creates AIAnalysis record."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIAnalysis
        from django_ai_services.providers import AIResponse
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="analyzeuser1", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content='{"category": "user", "tags": ["active"]}',
                model="test",
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            result = service.analyze_object(
                obj=user,
                analysis_type="user_profile",
                prompt="Analyze this user profile",
            )

            assert result is not None
            assert isinstance(result, AIResponse)
            assert result.content is not None

        # Verify AIAnalysis was created
        analysis = AIAnalysis.objects.filter(
            target_object_id=str(user.pk),
            analysis_type="user_profile",
        ).first()
        assert analysis is not None

    def test_analyze_object_idempotent(self):
        """analyze_object returns cached result for same input."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIAnalysis
        from django_ai_services.providers import AIResponse
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="analyzeuser2", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()
        call_count = 0

        def mock_chat(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return AIResponse(
                content='{"result": "analysis"}',
                model="test",
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.001,
                raw_response={},
            )

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.side_effect = mock_chat
            mock_get.return_value = mock_provider

            # First call
            result1 = service.analyze_object(
                obj=user,
                analysis_type="profile_analysis",
                prompt="Analyze this user",
            )

            # Second call with same input - should be cached
            result2 = service.analyze_object(
                obj=user,
                analysis_type="profile_analysis",
                prompt="Analyze this user",
            )

            # Only one AI call should have been made
            assert call_count == 1
            # Both results should be equivalent
            assert AIAnalysis.objects.filter(
                target_object_id=str(user.pk),
                analysis_type="profile_analysis",
            ).count() == 1

    def test_analyze_object_different_input_not_cached(self):
        """analyze_object makes new call for different input."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIAnalysis
        from django_ai_services.providers import AIResponse
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="analyzeuser3", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()
        call_count = 0

        def mock_chat(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return AIResponse(
                content=f'{{"result": "analysis_{call_count}"}}',
                model="test",
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.001,
                raw_response={},
            )

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.side_effect = mock_chat
            mock_get.return_value = mock_provider

            # First call
            service.analyze_object(
                obj=user,
                analysis_type="profile_analysis",
                prompt="Analyze this user",
            )

            # Second call with different prompt
            service.analyze_object(
                obj=user,
                analysis_type="profile_analysis",
                prompt="Analyze this user differently",
            )

            # Two AI calls should have been made
            assert call_count == 2
            assert AIAnalysis.objects.filter(
                target_object_id=str(user.pk),
                analysis_type="profile_analysis",
            ).count() == 2

    def test_analyze_object_stores_input_hash(self):
        """analyze_object computes and stores input hash."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIAnalysis
        from django_ai_services.providers import AIResponse
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="analyzeuser4", password="test")

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content='{"result": "test"}',
                model="test",
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.analyze_object(
                obj=user,
                analysis_type="hash_test",
                prompt="Test prompt",
            )

        analysis = AIAnalysis.objects.get(
            target_object_id=str(user.pk),
            analysis_type="hash_test",
        )
        assert analysis.input_hash
        assert len(analysis.input_hash) == 64  # SHA-256 hex
