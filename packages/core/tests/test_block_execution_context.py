"""Red tests for RUN-675: BlockExecutionContext dataclass."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.observer import WorkflowObserver
from runsight_core.workflow import BlockExecutionContext
from runsight_core.yaml.registry import WorkflowRegistry


class DummyBlock(BaseBlock):
    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)

    async def execute(self, state, **kwargs):  # pragma: no cover - helper for construction only
        return state


class TestBlockExecutionContext:
    def test_fields_round_trip_values(self) -> None:
        """Stores all constructor values and exposes them through field access."""
        blocks = {"writer": DummyBlock("writer")}
        registry = WorkflowRegistry()
        observer = MagicMock(spec=WorkflowObserver)

        ctx = BlockExecutionContext(
            workflow_name="review_pipeline",
            blocks=blocks,
            call_stack=["parent_workflow"],
            workflow_registry=registry,
            observer=observer,
        )

        assert ctx.workflow_name == "review_pipeline"
        assert ctx.blocks is blocks
        assert ctx.call_stack == ["parent_workflow"]
        assert ctx.workflow_registry is registry
        assert ctx.observer is observer

    def test_is_frozen(self) -> None:
        """Mutating any field raises because the dataclass is frozen."""
        ctx = BlockExecutionContext(
            workflow_name="root_workflow",
            blocks={},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        with pytest.raises((AttributeError, TypeError)):
            ctx.workflow_name = "mutated"

    def test_none_fields_are_valid(self) -> None:
        """observer=None and workflow_registry=None are both valid construction values."""
        ctx = BlockExecutionContext(
            workflow_name="headless_workflow",
            blocks={},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        assert ctx.workflow_registry is None
        assert ctx.observer is None
        assert ctx.call_stack == []
