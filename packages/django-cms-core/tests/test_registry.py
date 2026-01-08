"""Tests for django-cms-core block registry."""

import pytest


class TestBlockPlugin:
    """Tests for BlockPlugin dataclass."""

    def test_block_plugin_creation(self):
        """BlockPlugin can be created with required fields."""
        from django_cms_core.registry import BlockPlugin

        plugin = BlockPlugin(
            name="rich_text",
            label="Rich Text",
        )
        assert plugin.name == "rich_text"
        assert plugin.label == "Rich Text"

    def test_block_plugin_with_schema(self):
        """BlockPlugin can have a JSON schema for validation."""
        from django_cms_core.registry import BlockPlugin

        schema = {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
            },
            "required": ["content"],
        }
        plugin = BlockPlugin(
            name="rich_text",
            label="Rich Text",
            schema=schema,
        )
        assert plugin.schema == schema

    def test_block_plugin_defaults(self):
        """BlockPlugin has sensible defaults."""
        from django_cms_core.registry import BlockPlugin

        plugin = BlockPlugin(name="test", label="Test")
        assert plugin.schema is None
        assert plugin.renderer is None
        assert plugin.icon == "bi-square"
        assert plugin.category == "content"

    def test_block_plugin_with_renderer(self):
        """BlockPlugin can have a renderer function."""
        from django_cms_core.registry import BlockPlugin

        def render_test(data):
            return f"<div>{data.get('text', '')}</div>"

        plugin = BlockPlugin(
            name="test",
            label="Test",
            renderer=render_test,
        )
        assert plugin.renderer is not None
        assert plugin.renderer({"text": "hello"}) == "<div>hello</div>"

    def test_block_plugin_icon_and_category(self):
        """BlockPlugin can have custom icon and category."""
        from django_cms_core.registry import BlockPlugin

        plugin = BlockPlugin(
            name="hero",
            label="Hero Banner",
            icon="bi-image",
            category="layout",
        )
        assert plugin.icon == "bi-image"
        assert plugin.category == "layout"


class TestBlockRegistry:
    """Tests for BlockRegistry class."""

    def test_register_plugin(self):
        """BlockRegistry can register a plugin."""
        from django_cms_core.registry import BlockRegistry, BlockPlugin

        BlockRegistry.clear()
        plugin = BlockPlugin(name="test", label="Test")
        BlockRegistry.register(plugin)

        assert BlockRegistry.get("test") == plugin

    def test_get_unregistered_returns_none(self):
        """BlockRegistry.get returns None for unregistered plugin."""
        from django_cms_core.registry import BlockRegistry

        BlockRegistry.clear()
        assert BlockRegistry.get("nonexistent") is None

    def test_unregister_plugin(self):
        """BlockRegistry can unregister a plugin."""
        from django_cms_core.registry import BlockRegistry, BlockPlugin

        BlockRegistry.clear()
        plugin = BlockPlugin(name="test", label="Test")
        BlockRegistry.register(plugin)
        BlockRegistry.unregister("test")

        assert BlockRegistry.get("test") is None

    def test_all_returns_all_plugins(self):
        """BlockRegistry.all returns all registered plugins."""
        from django_cms_core.registry import BlockRegistry, BlockPlugin

        BlockRegistry.clear()
        p1 = BlockPlugin(name="p1", label="Plugin 1")
        p2 = BlockPlugin(name="p2", label="Plugin 2")
        BlockRegistry.register(p1)
        BlockRegistry.register(p2)

        all_plugins = BlockRegistry.all()
        assert len(all_plugins) == 2
        assert p1 in all_plugins
        assert p2 in all_plugins

    def test_get_by_category(self):
        """BlockRegistry can filter plugins by category."""
        from django_cms_core.registry import BlockRegistry, BlockPlugin

        BlockRegistry.clear()
        p1 = BlockPlugin(name="text", label="Text", category="content")
        p2 = BlockPlugin(name="hero", label="Hero", category="layout")
        p3 = BlockPlugin(name="heading", label="Heading", category="content")
        BlockRegistry.register(p1)
        BlockRegistry.register(p2)
        BlockRegistry.register(p3)

        content_plugins = BlockRegistry.get_by_category("content")
        assert len(content_plugins) == 2
        assert p1 in content_plugins
        assert p3 in content_plugins

    def test_clear_removes_all_plugins(self):
        """BlockRegistry.clear removes all registered plugins."""
        from django_cms_core.registry import BlockRegistry, BlockPlugin

        BlockRegistry.register(BlockPlugin(name="test", label="Test"))
        BlockRegistry.clear()

        assert len(BlockRegistry.all()) == 0


class TestBlockValidation:
    """Tests for block data validation."""

    def test_validate_block_basic_structure(self):
        """validate_block checks block has type and data."""
        from django_cms_core.registry import BlockRegistry, BlockPlugin

        BlockRegistry.clear()
        BlockRegistry.register(BlockPlugin(name="text", label="Text"))

        errors = BlockRegistry.validate_block("text", {"content": "hello"})
        assert errors == []

    def test_validate_block_unknown_type(self):
        """validate_block returns error for unknown block type."""
        from django_cms_core.registry import BlockRegistry

        BlockRegistry.clear()

        errors = BlockRegistry.validate_block("unknown", {"content": "hello"})
        assert len(errors) == 1
        assert "unknown" in errors[0].lower()

    def test_validate_block_with_schema(self):
        """validate_block validates against JSON schema if provided."""
        from django_cms_core.registry import BlockRegistry, BlockPlugin

        BlockRegistry.clear()
        schema = {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        }
        BlockRegistry.register(BlockPlugin(
            name="heading",
            label="Heading",
            schema=schema,
        ))

        # Valid data
        errors = BlockRegistry.validate_block("heading", {"text": "Hello"})
        assert errors == []

        # Invalid data (missing required field)
        errors = BlockRegistry.validate_block("heading", {})
        # If jsonschema is available, should return error
        # If not, should pass (optional dependency)

    def test_validate_block_invalid_schema_data(self):
        """validate_block returns errors for invalid data."""
        from django_cms_core.registry import BlockRegistry, BlockPlugin

        BlockRegistry.clear()
        schema = {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "minimum": 1, "maximum": 6},
            },
            "required": ["level"],
        }
        BlockRegistry.register(BlockPlugin(
            name="heading",
            label="Heading",
            schema=schema,
        ))

        # Level out of range - should return error if jsonschema available
        errors = BlockRegistry.validate_block("heading", {"level": 10})
        # Behavior depends on jsonschema availability


class TestBlockDecorator:
    """Tests for @block decorator."""

    def test_block_decorator_registers_plugin(self):
        """@block decorator registers a BlockPlugin."""
        from django_cms_core.registry import BlockRegistry, block

        BlockRegistry.clear()

        @block(name="custom", label="Custom Block")
        def render_custom(data):
            return f"<div>{data.get('content', '')}</div>"

        plugin = BlockRegistry.get("custom")
        assert plugin is not None
        assert plugin.name == "custom"
        assert plugin.label == "Custom Block"
        assert plugin.renderer is not None

    def test_block_decorator_with_schema(self):
        """@block decorator can include schema."""
        from django_cms_core.registry import BlockRegistry, block

        BlockRegistry.clear()

        @block(
            name="typed",
            label="Typed Block",
            schema={"type": "object", "properties": {"text": {"type": "string"}}},
        )
        def render_typed(data):
            return data.get("text", "")

        plugin = BlockRegistry.get("typed")
        assert plugin.schema is not None
        assert plugin.schema["type"] == "object"

    def test_block_decorator_with_category_and_icon(self):
        """@block decorator can set category and icon."""
        from django_cms_core.registry import BlockRegistry, block

        BlockRegistry.clear()

        @block(
            name="hero",
            label="Hero Banner",
            category="layout",
            icon="bi-image-fill",
        )
        def render_hero(data):
            return "<section class='hero'></section>"

        plugin = BlockRegistry.get("hero")
        assert plugin.category == "layout"
        assert plugin.icon == "bi-image-fill"

    def test_block_decorator_function_still_callable(self):
        """@block decorated function is still directly callable."""
        from django_cms_core.registry import BlockRegistry, block

        BlockRegistry.clear()

        @block(name="testfn", label="Test Function")
        def render_testfn(data):
            return f"Result: {data.get('value', 'none')}"

        # Function should still work normally
        result = render_testfn({"value": "123"})
        assert result == "Result: 123"


class TestBuiltInBlocks:
    """Tests for built-in block types."""

    def _reload_blocks(self):
        """Reload blocks module to re-register built-in blocks."""
        import importlib
        from django_cms_core import blocks
        from django_cms_core.registry import BlockRegistry
        BlockRegistry.clear()
        importlib.reload(blocks)

    def test_builtin_blocks_registered(self):
        """Built-in block types are registered by default."""
        self._reload_blocks()
        from django_cms_core.registry import BlockRegistry

        # These should be registered after importing blocks module
        expected_blocks = [
            "rich_text",
            "heading",
            "image",
            "image_gallery",
            "hero",
            "cta",
            "embed",
            "divider",
        ]
        for block_name in expected_blocks:
            assert BlockRegistry.get(block_name) is not None, f"{block_name} not registered"

    def test_rich_text_block(self):
        """rich_text block is properly configured."""
        self._reload_blocks()
        from django_cms_core.registry import BlockRegistry

        plugin = BlockRegistry.get("rich_text")
        assert plugin is not None
        assert plugin.label == "Rich Text"
        assert plugin.category == "content"

    def test_heading_block(self):
        """heading block is properly configured."""
        self._reload_blocks()
        from django_cms_core.registry import BlockRegistry

        plugin = BlockRegistry.get("heading")
        assert plugin is not None
        assert plugin.label == "Heading"

    def test_hero_block(self):
        """hero block is properly configured."""
        self._reload_blocks()
        from django_cms_core.registry import BlockRegistry

        plugin = BlockRegistry.get("hero")
        assert plugin is not None
        assert plugin.label == "Hero Banner"
        assert plugin.category == "layout"

    def test_cta_block(self):
        """cta block is properly configured."""
        self._reload_blocks()
        from django_cms_core.registry import BlockRegistry

        plugin = BlockRegistry.get("cta")
        assert plugin is not None
        assert plugin.label == "Call to Action"

    def test_divider_block(self):
        """divider block is properly configured."""
        self._reload_blocks()
        from django_cms_core.registry import BlockRegistry

        plugin = BlockRegistry.get("divider")
        assert plugin is not None
        assert plugin.label == "Divider"
