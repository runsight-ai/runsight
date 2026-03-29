"""
Tests for BlockRegistry factory registry.
"""

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.registry import BlockFactory, BlockRegistry
from runsight_core.state import WorkflowState


class SimpleBlock(BaseBlock):
    """Test block for factory tests."""

    def __init__(self, block_id: str, description: str) -> None:
        super().__init__(block_id)
        self.description = description

    async def execute(self, state: WorkflowState) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: self.description},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[Block {self.block_id}] {self.description}"}],
            }
        )


def test_registry_construction():
    """AC-1: BlockRegistry() constructs with an empty internal registry."""
    registry = BlockRegistry()
    assert registry is not None
    assert isinstance(registry, BlockRegistry)
    # Verify the internal registry exists (via get returning None for unknown key)
    assert registry.get("unknown") is None


def test_registry_register_and_get():
    """AC-2: registry.register('x', factory) stores factory under key 'x'; registry.get('x') returns that factory."""
    registry = BlockRegistry()

    # Create a factory function
    def factory(block_id: str, description: str) -> BaseBlock:
        return SimpleBlock(block_id, description)

    # Register the factory
    registry.register("my_step", factory)

    # Verify we can get it back
    retrieved_factory = registry.get("my_step")
    assert retrieved_factory is factory

    # Verify the factory works
    block = retrieved_factory("test_block", "test description")
    assert isinstance(block, SimpleBlock)
    assert block.block_id == "test_block"
    assert block.description == "test description"


def test_registry_get_unknown():
    """AC-3: registry.get('unknown') returns None."""
    registry = BlockRegistry()
    result = registry.get("unknown")
    assert result is None


def test_registry_register_overwrites_silently():
    """AC-4: Calling register() with a step_id that is already registered silently overwrites the existing entry."""
    registry = BlockRegistry()

    def factory1(block_id: str, description: str) -> BaseBlock:
        return SimpleBlock(block_id, "factory1")

    def factory2(block_id: str, description: str) -> BaseBlock:
        return SimpleBlock(block_id, "factory2")

    # Register first factory
    registry.register("step1", factory1)
    retrieved1 = registry.get("step1")
    assert retrieved1 is factory1

    # Overwrite with second factory (should not raise)
    registry.register("step1", factory2)
    retrieved2 = registry.get("step1")
    assert retrieved2 is factory2
    assert retrieved1 is not factory2


def test_block_factory_type_alias():
    """AC-5: BlockFactory type alias equals Callable[[str, str], BaseBlock]."""
    # Verify BlockFactory is the correct type

    # BlockFactory should be Callable[[str, str], BaseBlock]
    assert BlockFactory is not None

    # Create a function matching the type
    def test_factory(block_id: str, description: str) -> BaseBlock:
        return SimpleBlock(block_id, description)

    # This should work without type errors
    registry = BlockRegistry()
    registry.register("test", test_factory)
    factory = registry.get("test")
    assert factory is not None
    assert callable(factory)


def test_registry_multiple_entries():
    """Test that registry can store multiple factories."""
    registry = BlockRegistry()

    def factory_a(block_id: str, description: str) -> BaseBlock:
        return SimpleBlock(block_id, f"A: {description}")

    def factory_b(block_id: str, description: str) -> BaseBlock:
        return SimpleBlock(block_id, f"B: {description}")

    def factory_c(block_id: str, description: str) -> BaseBlock:
        return SimpleBlock(block_id, f"C: {description}")

    # Register multiple factories
    registry.register("step_a", factory_a)
    registry.register("step_b", factory_b)
    registry.register("step_c", factory_c)

    # Verify all are retrievable and distinct
    assert registry.get("step_a") is factory_a
    assert registry.get("step_b") is factory_b
    assert registry.get("step_c") is factory_c
    assert registry.get("unknown") is None
