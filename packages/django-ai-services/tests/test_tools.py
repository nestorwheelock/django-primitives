"""Tests for ToolRegistry and tool registration."""

import pytest
from unittest.mock import Mock


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def setup_method(self):
        """Clear registry before each test."""
        from django_ai_services.tools import ToolRegistry
        ToolRegistry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        from django_ai_services.tools import ToolRegistry
        ToolRegistry.clear()

    def test_register_tool(self):
        """Tool can be registered."""
        from django_ai_services.tools import ToolRegistry, AITool

        def my_handler(x: int) -> int:
            return x * 2

        tool = AITool(
            name="double",
            description="Doubles a number",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
            handler=my_handler,
        )

        ToolRegistry.register(tool)

        assert ToolRegistry.get("double") is not None
        assert ToolRegistry.get("double").name == "double"

    def test_unregister_tool(self):
        """Tool can be unregistered."""
        from django_ai_services.tools import ToolRegistry, AITool

        tool = AITool(
            name="temp",
            description="Temporary tool",
            parameters={},
            handler=lambda: None,
        )

        ToolRegistry.register(tool)
        assert ToolRegistry.get("temp") is not None

        ToolRegistry.unregister("temp")
        assert ToolRegistry.get("temp") is None

    def test_tool_decorator(self):
        """@tool decorator registers function."""
        from django_ai_services.tools import tool, ToolRegistry

        @tool(
            name="greet",
            description="Greets a person",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        )
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        registered = ToolRegistry.get("greet")
        assert registered is not None
        assert registered.description == "Greets a person"

        # Handler should still work
        result = greet("World")
        assert result == "Hello, World!"

    def test_tool_permission_levels(self):
        """Tools filtered by user permission level."""
        from django_ai_services.tools import ToolRegistry, AITool

        public_tool = AITool(
            name="public_tool",
            description="Public",
            parameters={},
            handler=lambda: "public",
            permission_level="public",
        )
        auth_tool = AITool(
            name="auth_tool",
            description="Authenticated",
            parameters={},
            handler=lambda: "auth",
            permission_level="authenticated",
        )
        staff_tool = AITool(
            name="staff_tool",
            description="Staff",
            parameters={},
            handler=lambda: "staff",
            permission_level="staff",
        )
        admin_tool = AITool(
            name="admin_tool",
            description="Admin",
            parameters={},
            handler=lambda: "admin",
            permission_level="admin",
        )

        ToolRegistry.register(public_tool)
        ToolRegistry.register(auth_tool)
        ToolRegistry.register(staff_tool)
        ToolRegistry.register(admin_tool)

        # Anonymous user - only public
        anon_tools = ToolRegistry.get_tools_for_user(None)
        assert len(anon_tools) == 1
        assert anon_tools[0].name == "public_tool"

        # Authenticated user
        auth_user = Mock(is_authenticated=True, is_staff=False, is_superuser=False)
        auth_tools = ToolRegistry.get_tools_for_user(auth_user)
        assert len(auth_tools) == 2
        names = {t.name for t in auth_tools}
        assert names == {"public_tool", "auth_tool"}

        # Staff user
        staff_user = Mock(is_authenticated=True, is_staff=True, is_superuser=False)
        staff_tools = ToolRegistry.get_tools_for_user(staff_user)
        assert len(staff_tools) == 3
        names = {t.name for t in staff_tools}
        assert names == {"public_tool", "auth_tool", "staff_tool"}

        # Admin/superuser
        admin_user = Mock(is_authenticated=True, is_staff=True, is_superuser=True)
        admin_tools = ToolRegistry.get_tools_for_user(admin_user)
        assert len(admin_tools) == 4

    def test_get_openai_tools_format(self):
        """Tools exported in OpenAI function calling format."""
        from django_ai_services.tools import ToolRegistry, AITool

        tool = AITool(
            name="calculate",
            description="Performs calculation",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
                "required": ["x", "y"],
            },
            handler=lambda x, y: x + y,
        )

        ToolRegistry.register(tool)

        openai_tools = ToolRegistry.get_openai_tools()
        assert len(openai_tools) == 1

        t = openai_tools[0]
        assert t["type"] == "function"
        assert t["function"]["name"] == "calculate"
        assert t["function"]["description"] == "Performs calculation"
        assert "properties" in t["function"]["parameters"]

    def test_execute_tool(self):
        """Tool can be executed by name."""
        from django_ai_services.tools import ToolRegistry, AITool

        def add(a: int, b: int) -> int:
            return a + b

        tool = AITool(
            name="add",
            description="Adds two numbers",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
            handler=add,
        )

        ToolRegistry.register(tool)

        result = ToolRegistry.execute_tool("add", {"a": 5, "b": 3})
        assert result == 8

    def test_execute_tool_permission_denied(self):
        """Tool execution denied for insufficient permissions."""
        from django_ai_services.tools import ToolRegistry, AITool

        tool = AITool(
            name="admin_only",
            description="Admin only tool",
            parameters={},
            handler=lambda: "secret",
            permission_level="admin",
        )

        ToolRegistry.register(tool)

        # Regular user should not be able to execute
        regular_user = Mock(is_authenticated=True, is_staff=False, is_superuser=False)

        with pytest.raises(PermissionError, match="not authorized"):
            ToolRegistry.execute_tool("admin_only", {}, user=regular_user)

    def test_execute_tool_requires_confirmation(self):
        """Tool requiring confirmation calls callback."""
        from django_ai_services.tools import ToolRegistry, AITool

        tool = AITool(
            name="dangerous",
            description="Dangerous operation",
            parameters={},
            handler=lambda: "done",
            requires_confirmation=True,
        )

        ToolRegistry.register(tool)

        # Without confirmation callback returning True
        with pytest.raises(PermissionError, match="not confirmed"):
            ToolRegistry.execute_tool(
                "dangerous",
                {},
                require_confirmation_callback=lambda: False,
            )

        # With confirmation
        result = ToolRegistry.execute_tool(
            "dangerous",
            {},
            require_confirmation_callback=lambda: True,
        )
        assert result == "done"

    def test_execute_unknown_tool(self):
        """Error raised for unknown tool."""
        from django_ai_services.tools import ToolRegistry

        with pytest.raises(ValueError, match="Unknown tool"):
            ToolRegistry.execute_tool("nonexistent", {})

    def test_tool_with_tags_and_module(self):
        """Tool can have tags and module metadata."""
        from django_ai_services.tools import tool, ToolRegistry

        @tool(
            name="tagged_tool",
            description="Tool with tags",
            parameters={},
            module="inventory",
            tags=["read", "search"],
        )
        def tagged_handler():
            return "tagged"

        registered = ToolRegistry.get("tagged_tool")
        assert registered.module == "inventory"
        assert registered.tags == ["read", "search"]
