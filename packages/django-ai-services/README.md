# django-ai-services

AI service integration for Django with audit trails, cost tracking, and reliability.

## Installation

```bash
pip install django-ai-services
```

Add to INSTALLED_APPS:

```python
INSTALLED_APPS = [
    ...,
    "django_singleton",
    "django_ai_services",
]
```

Run migrations:

```bash
python manage.py migrate django_ai_services
```

## Usage

```python
from django_ai_services import AIService

service = AIService(user=request.user)
response = service.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    operation="chat",
)
print(response.content)
```

## Features

- **AIServiceConfig**: Singleton configuration with API key management
- **AIUsageLog**: Immutable audit trail of all AI API calls
- **Cost tracking**: Automatic cost estimation and tracking
- **Provider abstraction**: OpenRouter, Ollama support
- **Circuit breaker**: Automatic provider health management
- **Retry logic**: Exponential backoff with jitter

## License

MIT
