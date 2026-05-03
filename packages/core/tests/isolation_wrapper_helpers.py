"""Shared helpers for isolation wrapper tests."""

from __future__ import annotations

from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState


def make_soul(soul_id: str = "isolation_default_soul") -> Soul:
    return Soul(
        id=soul_id,
        kind="soul",
        name="Isolation Fixture Soul",
        role="Isolation Fixture Soul",
        system_prompt="Exercise the isolation wrapper contract.",
        model_name="fixture-isolation-model",
    )


def make_state(task_instruction: str = "Exercise isolation wrapper") -> WorkflowState:
    return WorkflowState()


def make_ctx(wrapper, state: WorkflowState) -> BlockContext:
    return build_block_context(wrapper, state)


def apply_output(state: WorkflowState, block_id: str, output: BlockOutput) -> WorkflowState:
    return apply_block_output(state, block_id, output)
