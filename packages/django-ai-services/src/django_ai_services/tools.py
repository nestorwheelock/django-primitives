"""Tool Registry for AI function calling."""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AITool:
    """Definition of a callable AI tool."""

    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable[..., Any]
    permission_level: str = "public"  # public, authenticated, staff, admin
    requires_confirmation: bool = False
    module: str = "core"
    tags: list[str] = field(default_factory=list)


class ToolRegistry:
    """
    Central registry for AI-callable tools.
    Provides infrastructure only - apps register their own tools.
    """

    _tools: dict[str, AITool] = {}

    PERMISSION_LEVELS = {
        "public": 0,
        "authenticated": 1,
        "staff": 2,
        "admin": 3,
    }

    @classmethod
    def register(cls, tool: AITool):
        """Register a tool."""
        cls._tools[tool.name] = tool

    @classmethod
    def unregister(cls, name: str):
        """Unregister a tool."""
        cls._tools.pop(name, None)

    @classmethod
    def get(cls, name: str) -> AITool | None:
        """Get a tool by name."""
        return cls._tools.get(name)

    @classmethod
    def get_tools_for_user(cls, user=None) -> list[AITool]:
        """Get tools available for user's permission level."""
        if user is None:
            user_level = 0
        elif getattr(user, "is_superuser", False):
            user_level = 3
        elif getattr(user, "is_staff", False):
            user_level = 2
        elif getattr(user, "is_authenticated", True):
            user_level = 1
        else:
            user_level = 0

        return [
            tool
            for tool in cls._tools.values()
            if cls.PERMISSION_LEVELS.get(tool.permission_level, 0) <= user_level
        ]

    @classmethod
    def get_openai_tools(cls, user=None) -> list[dict]:
        """Get tools in OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in cls.get_tools_for_user(user)
        ]

    @classmethod
    def execute_tool(
        cls,
        name: str,
        arguments: dict,
        user=None,
        require_confirmation_callback: Callable[[], bool] | None = None,
    ) -> Any:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments
            user: User for permission check
            require_confirmation_callback: Called if tool.requires_confirmation is True.
                                           Must return True to proceed.
        """
        tool = cls._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        # Permission check
        available = cls.get_tools_for_user(user)
        if tool not in available:
            raise PermissionError(f"User not authorized for tool: {name}")

        # Confirmation check
        if tool.requires_confirmation and require_confirmation_callback:
            if not require_confirmation_callback():
                raise PermissionError(f"Tool execution not confirmed: {name}")

        return tool.handler(**arguments)

    @classmethod
    def clear(cls):
        """Clear all registered tools (for testing)."""
        cls._tools.clear()


def tool(
    name: str,
    description: str,
    parameters: dict,
    permission: str = "public",
    requires_confirmation: bool = False,
    module: str = "core",
    tags: list[str] | None = None,
):
    """Decorator to register a function as an AI tool."""

    def decorator(func):
        ToolRegistry.register(
            AITool(
                name=name,
                description=description,
                parameters=parameters,
                handler=func,
                permission_level=permission,
                requires_confirmation=requires_confirmation,
                module=module,
                tags=tags or [],
            )
        )
        return func

    return decorator
