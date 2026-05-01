"""Workflow.run() routes block execution through execute_block()."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.registry import BlockRegistry
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RetryConfig


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


class ResultBlock(BaseBlock):
    def __init__(self, block_id: str, output: str) -> None:
        super().__init__(block_id)
        self.output = output
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        return BlockOutput(output=self.output)


class FlakyChildBlock(BaseBlock):
    def __init__(self, block_id: str = "retry_child_step") -> None:
        super().__init__(block_id)
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("child fail once")
        return BlockOutput(output="child recovered")


class InjectingPlannerBlock(BaseBlock):
    def __init__(self) -> None:
        super().__init__("planner")

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        return BlockOutput(
            output="planned injected steps",
            metadata_updates={
                "planner_new_steps": [
                    {"step_id": "inner_loop", "description": "Run the injected loop"},
                    {"step_id": "injected_leaf", "description": "Run the injected leaf"},
                ],
            },
        )


def _make_child_workflow(
    block: BaseBlock, *, name: str = "single_block_child_workflow"
) -> Workflow:
    wf = Workflow(name)
    wf.add_block(block)
    wf.set_entry(block.block_id)
    wf.add_transition(block.block_id, None)
    return wf


def _make_parent_loop_workflow(
    workflow_block: WorkflowBlock,
    tail_block: BaseBlock,
    *,
    workflow_name: str = "loop_parent_workflow",
    loop_block_id: str = "workflow_loop_block",
) -> Workflow:
    wf = Workflow(workflow_name)
    loop_block = LoopBlock(loop_block_id, inner_block_refs=[workflow_block.block_id], max_rounds=1)
    wf.add_block(loop_block)
    wf.add_block(workflow_block)
    wf.add_block(tail_block)
    wf.set_entry(loop_block_id)
    wf.add_transition(loop_block_id, tail_block.block_id)
    wf.add_transition(tail_block.block_id, None)
    return wf


@pytest.mark.asyncio
async def test_workflow_block_exit_handle_routes_to_conditional_successor_after_execute_block():
    """Workflow.run should resolve the next step from the WorkflowBlock result returned by execute_block."""
    child_workflow = _make_child_workflow(
        ResultBlock("routing_child_step", "child output"),
        name="routing_child_workflow",
    )
    routing_workflow_block = WorkflowBlock(
        block_id="routing_child_workflow_block",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )
    completed_path = ResultBlock("completed_path", "completed output")
    fallback_path = ResultBlock("fallback_path", "fallback output")

    wf = Workflow("workflow_block_routing")
    wf.add_block(routing_workflow_block)
    wf.add_block(completed_path)
    wf.add_block(fallback_path)
    wf.set_entry(routing_workflow_block.block_id)
    wf.add_conditional_transition(
        routing_workflow_block.block_id,
        {"completed": completed_path.block_id, "default": fallback_path.block_id},
    )
    wf.add_transition(completed_path.block_id, None)
    wf.add_transition(fallback_path.block_id, None)

    final_state = await wf.run(WorkflowState())

    assert final_state.results["routing_child_workflow_block"].exit_handle == "completed"
    assert completed_path.calls == 1
    assert fallback_path.calls == 0
    assert final_state.results["completed_path"].output == "completed output"


@pytest.mark.asyncio
async def test_loopblock_nested_workflow_block_preserves_parent_observer_event_order():
    """WorkflowBlock nested inside LoopBlock should still emit its own block lifecycle events."""
    child_workflow = _make_child_workflow(
        ResultBlock("observer_child_step", "child output"),
        name="observer_child_workflow",
    )
    observer_workflow_block = WorkflowBlock(
        block_id="observer_child_workflow_block",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )
    tail = ResultBlock("observer_tail_step", "tail output")
    wf = _make_parent_loop_workflow(
        observer_workflow_block,
        tail,
        workflow_name="loop_observer_parent_workflow",
        loop_block_id="observer_loop_block",
    )
    observer = RecordingObserver()

    await wf.run(WorkflowState(), observer=observer)

    assert observer.events == [
        ("workflow_start", "loop_observer_parent_workflow"),
        ("block_start", "loop_observer_parent_workflow", "observer_loop_block", "LoopBlock"),
        (
            "block_start",
            "loop_observer_parent_workflow",
            "observer_child_workflow_block",
            "WorkflowBlock",
        ),
        ("block_start", "observer_child_workflow", "observer_child_step", "ResultBlock"),
        ("block_complete", "observer_child_workflow", "observer_child_step", "ResultBlock"),
        (
            "block_complete",
            "loop_observer_parent_workflow",
            "observer_child_workflow_block",
            "WorkflowBlock",
        ),
        ("block_complete", "loop_observer_parent_workflow", "observer_loop_block", "LoopBlock"),
        ("block_start", "loop_observer_parent_workflow", "observer_tail_step", "ResultBlock"),
        (
            "block_complete",
            "loop_observer_parent_workflow",
            "observer_tail_step",
            "ResultBlock",
        ),
        ("workflow_complete", "loop_observer_parent_workflow"),
    ]


@pytest.mark.asyncio
async def test_loopblock_nested_workflow_block_preserves_retry_config_and_multiblock_progress():
    """retry_config on a WorkflowBlock should still apply when the block is run inside LoopBlock."""
    flaky_child = FlakyChildBlock()
    child_workflow = _make_child_workflow(flaky_child, name="retry_child_workflow")
    retry_workflow_block = WorkflowBlock(
        block_id="retry_child_workflow_block",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )
    retry_workflow_block.retry_config = RetryConfig(
        max_attempts=2,
        backoff="fixed",
        backoff_base_seconds=0.1,
    )
    tail = ResultBlock("retry_tail_step", "tail output")
    wf = _make_parent_loop_workflow(
        retry_workflow_block,
        tail,
        workflow_name="loop_retry_parent_workflow",
        loop_block_id="retry_loop_block",
    )

    with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        final_state = await wf.run(WorkflowState())

    assert flaky_child.calls == 2
    assert sleep_mock.await_count == 1
    assert final_state.results["retry_child_workflow_block"].exit_handle == "completed"
    assert final_state.results["retry_tail_step"].output == "tail output"


@pytest.mark.asyncio
async def test_loopblock_nested_workflow_block_forwards_unified_context_to_child_workflow_run():
    """LoopBlock -> WorkflowBlock should forward call_stack, workflow_registry, and observer context."""
    child_workflow = AsyncMock()
    child_workflow.name = "context_child_workflow"
    child_workflow.run = AsyncMock(return_value=WorkflowState())

    context_workflow_block = WorkflowBlock(
        block_id="context_child_workflow_block",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )
    tail = ResultBlock("context_tail_step", "tail output")
    workflow = _make_parent_loop_workflow(
        context_workflow_block,
        tail,
        workflow_name="context_parent_workflow",
        loop_block_id="context_loop_block",
    )
    observer = RecordingObserver()
    registry = WorkflowRegistry()

    final_state = await workflow.run(
        WorkflowState(),
        call_stack=["root_workflow"],
        workflow_registry=registry,
        observer=observer,
    )

    call_kwargs = child_workflow.run.call_args.kwargs

    assert final_state.results["context_child_workflow_block"].exit_handle == "completed"
    assert call_kwargs["call_stack"] == [
        "root_workflow",
        "context_parent_workflow",
        "context_child_workflow",
    ]
    assert call_kwargs["workflow_registry"] is registry
    assert call_kwargs["observer"] is not None
    assert call_kwargs["observer"] is not observer


@pytest.mark.asyncio
async def test_loopblock_break_on_completed_exit_handle_from_workflow_block_stops_after_child_success():
    """WorkflowBlock success should expose exit_handle='completed' for LoopBlock.break_on_exit."""
    child_step = ResultBlock("break_child_step", "child output")
    child_workflow = _make_child_workflow(child_step, name="break_child_workflow")
    break_workflow_block = WorkflowBlock(
        block_id="break_child_workflow_block",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )
    tail = ResultBlock("break_tail_step", "tail output")

    workflow = Workflow("break_on_completed_parent_workflow")
    loop_block = LoopBlock(
        "break_on_completed_loop_block",
        inner_block_refs=[break_workflow_block.block_id],
        max_rounds=4,
        break_on_exit="completed",
    )
    workflow.add_block(loop_block)
    workflow.add_block(break_workflow_block)
    workflow.add_block(tail)
    workflow.set_entry("break_on_completed_loop_block")
    workflow.add_transition("break_on_completed_loop_block", tail.block_id)
    workflow.add_transition(tail.block_id, None)

    final_state = await workflow.run(WorkflowState())

    assert child_step.calls == 1
    assert final_state.results["break_child_workflow_block"].exit_handle == "completed"
    assert final_state.shared_memory["__loop__break_on_completed_loop_block"] == {
        "rounds_completed": 1,
        "broke_early": True,
        "break_reason": "exit_handle 'completed' matched break_on_exit",
    }
    assert tail.calls == 1
    assert final_state.results["break_tail_step"].output == "tail output"


@pytest.mark.asyncio
async def test_dynamic_injection_keeps_injected_loopblock_and_injected_leaf_in_shared_queue_context():
    """Injected LoopBlock should be able to resolve injected siblings added in the same splice."""
    registry = BlockRegistry()
    registry.register(
        "inner_loop",
        lambda step_id, description: LoopBlock(
            step_id,
            inner_block_refs=["injected_leaf"],
            max_rounds=1,
        ),
    )
    registry.register(
        "injected_leaf",
        lambda step_id, description: ResultBlock(step_id, "injected leaf output"),
    )

    wf = Workflow("injection_workflow")
    planner = InjectingPlannerBlock()
    terminal = ResultBlock("terminal", "terminal output")
    wf.add_block(planner)
    wf.add_block(terminal)
    wf.set_entry(planner.block_id)
    wf.add_transition(planner.block_id, terminal.block_id)
    wf.add_transition(terminal.block_id, None)

    final_state = await wf.run(WorkflowState(), registry=registry)

    assert final_state.results["planner"].output == "planned injected steps"
    assert final_state.results["injected_leaf"].output == "injected leaf output"
    assert final_state.results["inner_loop"].output == "completed_1_rounds"
    assert final_state.results["terminal"].output == "terminal output"
