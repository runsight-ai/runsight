"""Red tests for RUN-678: wire LoopBlock.execute() through execute_block()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow


async def _exec(block, state, **extra_inputs):
    ctx = build_block_context(block, state)
    if extra_inputs:
        ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **extra_inputs}})
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[tuple[str, ...]] = []

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.events.append(("workflow_start", workflow_name))

    def on_block_start(self, workflow_name: str, block_id: str, block_type: str, **kwargs) -> None:
        self.events.append(("block_start", workflow_name, block_id, block_type))

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        **kwargs,
    ) -> None:
        self.events.append(("block_complete", workflow_name, block_id, block_type))

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self.events.append(("block_error", workflow_name, block_id, block_type, str(error)))

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        self.events.append(("workflow_complete", workflow_name))

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self.events.append(("workflow_error", workflow_name, str(error)))


class ExitHandleBlock(BaseBlock):
    def __init__(self, block_id: str, exit_handle: str, threshold: int) -> None:
        super().__init__(block_id)
        self._exit_handle = exit_handle
        self._threshold = threshold

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        state = ctx.state_snapshot
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        handle = self._exit_handle if len(calls) >= self._threshold else None
        return BlockOutput(
            output=f"{self.block_id}_round_{len(calls)}",
            exit_handle=handle,
            shared_memory_updates={f"{self.block_id}_calls": calls},
        )


class KwargsProbeBlock(BaseBlock):
    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)
        self.captured_kwargs: list[dict[str, object]] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.captured_kwargs.append(dict(ctx.inputs))
        return BlockOutput(output=f"{self.block_id}_ok")


def _make_linear_block(block_id: str, output: str) -> LinearBlock:
    runner = MagicMock()
    runner.model_name = "gpt-4o-mini"
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="task-1",
            soul_id=f"{block_id}_soul",
            output=output,
            cost_usd=0.01,
            total_tokens=10,
        )
    )
    soul = Soul(
        id=f"{block_id}_soul",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt=f"Handle {block_id}.",
        model_name="gpt-4o-mini",
    )
    return LinearBlock(block_id, soul, runner)


def _make_state() -> WorkflowState:
    return WorkflowState()


def _make_workflow(name: str, loop: LoopBlock, *inner_blocks: BaseBlock) -> Workflow:
    wf = Workflow(name)
    wf.add_block(loop)
    for block in inner_blocks:
        wf.add_block(block)
    wf.set_entry(loop.block_id)
    wf.add_transition(loop.block_id, None)
    return wf


def _events_for(
    observer: RecordingObserver, workflow_name: str, block_ids: set[str]
) -> list[tuple[str, ...]]:
    return [
        event
        for event in observer.events
        if len(event) >= 4 and event[1] == workflow_name and event[2] in block_ids
    ]


@pytest.mark.asyncio
async def test_loopblock_inner_linear_blocks_emit_observer_events_every_round():
    """Inner LinearBlocks should inherit execute_block lifecycle when LoopBlock has ctx."""
    writer = _make_linear_block("writer", "writer output")
    critic = _make_linear_block("critic", "critic output")
    loop = LoopBlock("loop_block", inner_block_refs=["writer", "critic"], max_rounds=3)
    workflow = _make_workflow("loop_linear_observer_wf", loop, writer, critic)
    observer = RecordingObserver()

    final_state = await workflow.run(_make_state(), observer=observer)

    assert _events_for(observer, workflow.name, {"writer", "critic"}) == [
        ("block_start", workflow.name, "writer", "LinearBlock"),
        ("block_complete", workflow.name, "writer", "LinearBlock"),
        ("block_start", workflow.name, "critic", "LinearBlock"),
        ("block_complete", workflow.name, "critic", "LinearBlock"),
        ("block_start", workflow.name, "writer", "LinearBlock"),
        ("block_complete", workflow.name, "writer", "LinearBlock"),
        ("block_start", workflow.name, "critic", "LinearBlock"),
        ("block_complete", workflow.name, "critic", "LinearBlock"),
        ("block_start", workflow.name, "writer", "LinearBlock"),
        ("block_complete", workflow.name, "writer", "LinearBlock"),
        ("block_start", workflow.name, "critic", "LinearBlock"),
        ("block_complete", workflow.name, "critic", "LinearBlock"),
    ]
    assert writer.runner.execute.await_count == 3
    assert critic.runner.execute.await_count == 3
    assert final_state.results["writer"].output == "writer output"
    assert final_state.results["critic"].output == "critic output"
    assert final_state.results["loop_block"].output == "completed_3_rounds"


@pytest.mark.asyncio
async def test_loopblock_direct_execute_without_ctx_stays_backward_compatible():
    """LoopBlock.execute(ctx) with blocks in ctx.inputs should work correctly."""
    probe = KwargsProbeBlock("probe")
    loop = LoopBlock("loop_block", inner_block_refs=["probe"], max_rounds=1)
    blocks = {"probe": probe, "loop_block": loop}

    result_state = await _exec(loop, WorkflowState(), blocks=blocks)

    assert probe.captured_kwargs == [{"blocks": blocks}]
    assert result_state.results["probe"].output == "probe_ok"
    assert result_state.results["loop_block"].output == "completed_1_rounds"


@pytest.mark.asyncio
async def test_loopblock_break_on_exit_keeps_observer_events_until_break_point():
    """break_on_exit should stop after the matching round without dropping inner lifecycle events."""
    worker = _make_linear_block("worker", "worker output")
    gate = ExitHandleBlock("gate", exit_handle="pass", threshold=2)
    loop = LoopBlock(
        "loop_block",
        inner_block_refs=["worker", "gate"],
        max_rounds=5,
        break_on_exit="pass",
    )
    workflow = _make_workflow("loop_break_observer_wf", loop, worker, gate)
    observer = RecordingObserver()

    final_state = await workflow.run(_make_state(), observer=observer)

    assert _events_for(observer, workflow.name, {"worker", "gate"}) == [
        ("block_start", workflow.name, "worker", "LinearBlock"),
        ("block_complete", workflow.name, "worker", "LinearBlock"),
        ("block_start", workflow.name, "gate", "ExitHandleBlock"),
        ("block_complete", workflow.name, "gate", "ExitHandleBlock"),
        ("block_start", workflow.name, "worker", "LinearBlock"),
        ("block_complete", workflow.name, "worker", "LinearBlock"),
        ("block_start", workflow.name, "gate", "ExitHandleBlock"),
        ("block_complete", workflow.name, "gate", "ExitHandleBlock"),
    ]
    assert final_state.shared_memory["__loop__loop_block"] == {
        "rounds_completed": 2,
        "broke_early": True,
        "break_reason": "exit_handle 'pass' matched break_on_exit",
    }
    assert final_state.results["gate"].exit_handle == "pass"


@pytest.mark.asyncio
async def test_nested_loopblock_propagates_ctx_to_inner_loop_and_leaf_blocks():
    """Nested loops should wrap both the child loop and its inner LinearBlock via execute_block."""
    leaf = _make_linear_block("leaf", "leaf output")
    inner_loop = LoopBlock("inner_loop", inner_block_refs=["leaf"], max_rounds=2)
    outer_loop = LoopBlock("outer_loop", inner_block_refs=["inner_loop"], max_rounds=2)
    workflow = _make_workflow("nested_loop_ctx_wf", outer_loop, inner_loop, leaf)
    observer = RecordingObserver()

    final_state = await workflow.run(_make_state(), observer=observer)

    assert _events_for(observer, workflow.name, {"inner_loop", "leaf"}) == [
        ("block_start", workflow.name, "inner_loop", "LoopBlock"),
        ("block_start", workflow.name, "leaf", "LinearBlock"),
        ("block_complete", workflow.name, "leaf", "LinearBlock"),
        ("block_start", workflow.name, "leaf", "LinearBlock"),
        ("block_complete", workflow.name, "leaf", "LinearBlock"),
        ("block_complete", workflow.name, "inner_loop", "LoopBlock"),
        ("block_start", workflow.name, "inner_loop", "LoopBlock"),
        ("block_start", workflow.name, "leaf", "LinearBlock"),
        ("block_complete", workflow.name, "leaf", "LinearBlock"),
        ("block_start", workflow.name, "leaf", "LinearBlock"),
        ("block_complete", workflow.name, "leaf", "LinearBlock"),
        ("block_complete", workflow.name, "inner_loop", "LoopBlock"),
    ]
    assert leaf.runner.execute.await_count == 4
    assert final_state.results["leaf"].output == "leaf output"
    assert final_state.results["inner_loop"].output == "completed_2_rounds"
    assert final_state.results["outer_loop"].output == "completed_2_rounds"
