"""
BlockRegistry: instance-based factory registry for dynamic block resolution.
"""

from typing import Callable, Dict, Optional

from runsight_core.blocks.base import BaseBlock

# Canonical factory type: receives (block_id, description) → BaseBlock
BlockFactory = Callable[[str, str], BaseBlock]


class BlockRegistry:
    """
    Instance-based registry mapping step_id strings to block factory callables.

    Usage:
        registry = BlockRegistry()
        registry.register("my_step", lambda sid, desc: MyBlock(sid, desc))
        # Pass to Workflow.run(state, registry=registry)
    """

    def __init__(self) -> None:
        self._registry: Dict[str, BlockFactory] = {}

    def register(self, step_id: str, factory: BlockFactory) -> None:
        """
        Register a factory under step_id.

        Args:
            step_id: Key matching metadata item's "step_id" value.
            factory: Callable[[str, str], BaseBlock] — receives (block_id, description).

        Note: Overwrites silently if step_id already registered.
        """
        self._registry[step_id] = factory

    def get(self, step_id: str) -> Optional[BlockFactory]:
        """
        Return factory for step_id, or None if not registered.

        Args:
            step_id: Key to look up.

        Returns:
            Factory callable, or None.
        """
        return self._registry.get(step_id)
