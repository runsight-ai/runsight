"""YAML parser and standard-library block coverage.

This module tests:
- BlockTypeRegistry completeness.
- Valid YAML parsing scenarios.
- Error paths that raise ValueError.
- Soul resolution and merging with built-ins.
- YAML schema version validation.
"""

from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY


class TestBlockTypeRegistry:
    """Tests for BlockTypeRegistry completeness."""

    def test_block_type_registry_has_all_7_types(self):
        """Verify BLOCK_TYPE_REGISTRY contains all 7 block types."""
        expected_types = {
            "linear",
            "dispatch",
            "synthesize",
            "loop",
            "gate",
            "code",
            "workflow",
        }
        assert set(BLOCK_TYPE_REGISTRY.keys()) == expected_types
        assert len(BLOCK_TYPE_REGISTRY) == 7

    def test_all_block_builders_are_callable(self):
        """Verify all builders in registry are callable."""
        for block_type, builder in BLOCK_TYPE_REGISTRY.items():
            assert callable(builder), f"Builder for {block_type} is not callable"
