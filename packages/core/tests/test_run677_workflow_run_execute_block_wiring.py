"""Red tests for RUN-677: wire Workflow.run() through execute_block()."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.registry import BlockRegistry
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
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

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.calls += 1
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self.output),
                }
            }
        )


class FlakyChildBlock(BaseBlock):
    def __init__(self, block_id: str = "child_step") -> None:
        super().__init__(block_id)
        self.calls = 0

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("child fail once")
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output="child recovered"),
                }
            }
        )


class InjectingPlannerBlock(BaseBlock):
    def __init__(self) -> None:
        super().__init__("planner")

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output="planned injected steps"),
                },
                "metadata": {
                    **state.metadata,
                    "planner_new_steps": [
                        {"step_id": "inner_loop", "description": "Run the injected loop"},
                        {"step_id": "injected_leaf", "description": "Run the injected leaf"},
                    ],
                },
            }
        )


def _make_child_workflow(block: BaseBlock) -> Workflow:
    wf = Workflow("child_workflow")
    wf.add_block(block)
    wf.set_entry(block.block_id)
    wf.add_transition(block.block_id, None)
    return wf


def _make_parent_loop_workflow(workflow_block: WorkflowBlock, tail_block: BaseBlock) -> Workflow:
    wf = Workflow("parent_workflow")
    loop_block = LoopBlock("loop_block", inner_block_refs=[workflow_block.block_id], max_rounds=1)
    wf.add_block(loop_block)
    wf.add_block(workflow_block)
    wf.add_block(tail_block)
    wf.set_entry("loop_block")
    wf.add_transition("loop_block", tail_block.block_id)
    wf.add_transition(tail_block.block_id, None)
    return wf


@pytest.mark.asyncio
async def test_loopblock_nested_workflow_block_preserves_parent_observer_event_order():
    """WorkflowBlock nested inside LoopBlock should still emit its own block lifecycle events."""
    child_workflow = _make_child_workflow(ResultBlock("child_step", "child output"))
    invoke_child = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )
    tail = ResultBlock("tail", "tail output")
    wf = _make_parent_loop_workflow(invoke_child, tail)
    observer = RecordingObserver()

    await wf.run(WorkflowState(), observer=observer)

    assert observer.events == [
        ("workflow_start", "parent_workflow"),
        ("block_start", "parent_workflow", "loop_block", "LoopBlock"),
        ("block_start", "parent_workflow", "invoke_child", "WorkflowBlock"),
        ("block_start", "child_workflow", "child_step", "ResultBlock"),
        ("block_complete", "child_workflow", "child_step", "ResultBlock"),
        ("block_complete", "parent_workflow", "invoke_child", "WorkflowBlock"),
        ("block_complete", "parent_workflow", "loop_block", "LoopBlock"),
        ("block_start", "parent_workflow", "tail", "ResultBlock"),
        ("block_complete", "parent_workflow", "tail", "ResultBlock"),
        ("workflow_complete", "parent_workflow"),
    ]


@pytest.mark.asyncio
async def test_loopblock_nested_workflow_block_preserves_retry_config_and_multiblock_progress():
    """retry_config on a WorkflowBlock should still apply when the block is run inside LoopBlock."""
    flaky_child = FlakyChildBlock()
    child_workflow = _make_child_workflow(flaky_child)
    invoke_child = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )
    invoke_child.retry_config = RetryConfig(
        max_attempts=2,
        backoff="fixed",
        backoff_base_seconds=0.1,
    )
    tail = ResultBlock("tail", "tail output")
    wf = _make_parent_loop_workflow(invoke_child, tail)

    with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        final_state = await wf.run(WorkflowState())

    assert flaky_child.calls == 2
    assert sleep_mock.await_count == 1
    assert final_state.results["child_step"].output == "child recovered"
    assert final_state.results["invoke_child"].exit_handle == "completed"
    assert final_state.results["tail"].output == "tail output"


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
