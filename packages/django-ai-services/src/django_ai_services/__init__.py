__version__ = "0.1.0"

__all__ = [
    "AIServiceConfig",
    "AIUsageLog",
    "AIAnalysis",
    "AIService",
    "AIProvider",
    "AIResponse",
    "OpenRouterProvider",
    "OllamaProvider",
    "ToolRegistry",
    "tool",
    "AITool",
]


def __getattr__(name):
    if name == "AIServiceConfig":
        from .models import AIServiceConfig
        return AIServiceConfig
    if name == "AIUsageLog":
        from .models import AIUsageLog
        return AIUsageLog
    if name == "AIAnalysis":
        from .models import AIAnalysis
        return AIAnalysis
    if name == "AIService":
        from .services import AIService
        return AIService
    if name in ("AIProvider", "AIResponse", "OpenRouterProvider", "OllamaProvider"):
        from . import providers
        return getattr(providers, name)
    if name in ("ToolRegistry", "tool", "AITool"):
        from . import tools
        return getattr(tools, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
