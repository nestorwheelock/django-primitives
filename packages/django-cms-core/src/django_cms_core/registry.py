"""Block Registry for CMS content blocks.

Provides infrastructure for registering and validating block types.
Apps register their own custom blocks; this package provides built-in blocks.
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class BlockPlugin:
    """Definition of a content block type.

    Attributes:
        name: Unique identifier for the block type
        label: Human-readable display name
        schema: Optional JSON Schema for data validation
        renderer: Optional function to render block to HTML
        icon: Icon class for UI (default: bi-square)
        category: Grouping category (default: content)
    """

    name: str
    label: str
    schema: dict | None = None
    renderer: Callable[[dict], str] | None = None
    icon: str = "bi-square"
    category: str = "content"


class BlockRegistry:
    """Central registry for content block types.

    Provides infrastructure for block registration, lookup, and validation.
    Apps register their own blocks; this registry provides the mechanism.
    """

    _plugins: dict[str, BlockPlugin] = {}

    @classmethod
    def register(cls, plugin: BlockPlugin) -> None:
        """Register a block plugin."""
        cls._plugins[plugin.name] = plugin

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a block plugin by name."""
        cls._plugins.pop(name, None)

    @classmethod
    def get(cls, name: str) -> BlockPlugin | None:
        """Get a block plugin by name."""
        return cls._plugins.get(name)

    @classmethod
    def all(cls) -> list[BlockPlugin]:
        """Get all registered plugins."""
        return list(cls._plugins.values())

    @classmethod
    def get_by_category(cls, category: str) -> list[BlockPlugin]:
        """Get all plugins in a category."""
        return [p for p in cls._plugins.values() if p.category == category]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered plugins (for testing)."""
        cls._plugins.clear()

    @classmethod
    def validate_block(cls, block_type: str, data: dict) -> list[str]:
        """Validate block data against its schema.

        Args:
            block_type: The block type name
            data: The block data to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        plugin = cls.get(block_type)
        if plugin is None:
            errors.append(f"Unknown block type: {block_type}")
            return errors

        # If plugin has a schema and jsonschema is available, validate
        if plugin.schema is not None:
            try:
                import jsonschema

                try:
                    jsonschema.validate(instance=data, schema=plugin.schema)
                except jsonschema.ValidationError as e:
                    errors.append(str(e.message))
            except ImportError:
                # jsonschema not available, skip validation
                pass

        return errors


def block(
    name: str,
    label: str,
    schema: dict | None = None,
    icon: str = "bi-square",
    category: str = "content",
):
    """Decorator to register a function as a block renderer.

    The decorated function becomes the block's renderer.

    Args:
        name: Unique block type identifier
        label: Human-readable display name
        schema: Optional JSON Schema for validation
        icon: Icon class for UI
        category: Grouping category

    Example:
        @block(name="quote", label="Quote")
        def render_quote(data):
            return f"<blockquote>{data.get('text', '')}</blockquote>"
    """

    def decorator(func: Callable[[dict], str]) -> Callable[[dict], str]:
        BlockRegistry.register(
            BlockPlugin(
                name=name,
                label=label,
                schema=schema,
                renderer=func,
                icon=icon,
                category=category,
            )
        )
        return func

    return decorator
