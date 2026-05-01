"""EvalObserver child stream isolation and child assertion ownership."""

from __future__ import annotations

import pytest
from runsight_core.block_io import BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.observer import CompositeObserver
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from sqlmodel import Session

from runsight_api.domain.entities.run import RunNode, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.services.execution_runtime import build_assertion_configs
from eval_observer_helpers import (
    EVAL_BLOCK_ID,
    EVAL_BLOCK_TYPE,
    EVAL_WORKFLOW_ID,
    assertion_configs_for,
    import_eval_observer,
    make_eval_observer_engine,
    make_eval_soul,
    make_eval_sse_queue,
    make_eval_state,
    seed_eval_run,
    seed_eval_run_node,
)


def test_clone_for_child_run_uses_distinct_sse_queue() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run(engine)
    sse_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    parent = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=sse_queue,
        assertion_configs=assertion_configs_for(value="x"),
    )

    child = parent.clone_for_child_run(child_run_id="child-eval-run")

    assert child.run_id == "child-eval-run"
    assert child.sse_queue is not parent.sse_queue, (
        "Child eval observers must own a dedicated SSE queue so child eval traffic cannot "
        "bleed into the parent's live stream."
    )


@pytest.mark.asyncio
async def test_child_eval_events_stay_off_parent_queue() -> None:
    engine = make_eval_observer_engine()
    parent_run_id = seed_eval_run(
        engine,
        run_id="parent-eval-run",
        workflow_id="parent-eval-workflow",
        workflow_name="Parent Eval Workflow",
        status=RunStatus.running,
    )
    child_run_id = seed_eval_run(
        engine,
        run_id="child-eval-run",
        workflow_id="child-eval-workflow",
        workflow_name="Child Eval Workflow",
        status=RunStatus.running,
    )
    seed_eval_run_node(engine, run_id=child_run_id)
    parent_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    parent = EvalObserver(
        engine=engine,
        run_id=parent_run_id,
        sse_queue=parent_queue,
        assertion_configs=assertion_configs_for(),
    )
    child = parent.clone_for_child_run(child_run_id=child_run_id)

    child.on_block_complete(
        "child-eval-workflow",
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(),
        soul=make_eval_soul(),
    )

    assert parent_queue.empty(), (
        "A child run's node_eval_complete event must not be enqueued onto the parent's "
        "live stream queue."
    )
    event = child.sse_queue.get_nowait()
    assert event["event"] == "node_eval_complete"
    assert event["data"]["node_id"] == EVAL_BLOCK_ID


@pytest.mark.asyncio
async def test_sibling_child_eval_events_do_not_bleed_across_child_queues() -> None:
    engine = make_eval_observer_engine()
    parent_run_id = seed_eval_run(
        engine,
        run_id="parent-sibling-eval-run",
        workflow_id="parent-eval-workflow",
        workflow_name="parent-eval-workflow",
        status=RunStatus.running,
    )
    child_a_run_id = seed_eval_run(
        engine,
        run_id="child-a-eval-run",
        workflow_id="child-a-eval-workflow",
        workflow_name="child-a-eval-workflow",
        status=RunStatus.running,
    )
    child_b_run_id = seed_eval_run(
        engine,
        run_id="child-b-eval-run",
        workflow_id="child-b-eval-workflow",
        workflow_name="child-b-eval-workflow",
        status=RunStatus.running,
    )
    seed_eval_run_node(engine, run_id=child_a_run_id)
    seed_eval_run_node(engine, run_id=child_b_run_id)
    parent_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    parent = EvalObserver(
        engine=engine,
        run_id=parent_run_id,
        sse_queue=parent_queue,
        assertion_configs=assertion_configs_for(),
    )
    child_a = parent.clone_for_child_run(child_run_id=child_a_run_id)
    child_b = parent.clone_for_child_run(child_run_id=child_b_run_id)

    child_a.on_block_complete(
        "child-a-eval-workflow",
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(),
        soul=make_eval_soul(),
    )

    assert parent_queue.empty(), (
        "Sibling child eval events must not bleed back into the parent queue."
    )
    assert child_b.sse_queue.empty(), (
        "An eval event emitted for child A must not appear on child B's queue."
    )
    event = child_a.sse_queue.get_nowait()
    assert event["event"] == "node_eval_complete"
    assert event["data"]["node_id"] == EVAL_BLOCK_ID


@pytest.mark.asyncio
async def test_nested_child_workflow_uses_its_own_assertions_without_mutating_parent_surface() -> (
    None
):
    engine = make_eval_observer_engine()
    parent_run_id = seed_eval_run(
        engine,
        run_id="nested-parent-eval-run",
        workflow_id="parent-eval-workflow",
        workflow_name="parent-eval-workflow",
        status=RunStatus.running,
    )
    block_id = "asserted_block"

    class AssertionEchoBlock(BaseBlock):
        def __init__(self, block_id: str, output: str, assertions: list[dict[str, object]]):
            super().__init__(block_id)
            self.output = output
            self.assertions = assertions

        async def execute(self, ctx):
            return BlockOutput(output=self.output, cost_usd=0.0, total_tokens=0)

    child_wf = Workflow(name="child-eval-workflow")
    child_wf.add_block(
        AssertionEchoBlock(
            block_id,
            "CHILD signal",
            [{"type": "contains", "value": "CHILD", "weight": 1.0}],
        )
    )
    child_wf.set_entry(block_id)
    child_wf.add_transition(block_id, None)

    parent_wf = Workflow(name="parent-eval-workflow")
    parent_wf.add_block(
        AssertionEchoBlock(
            block_id,
            "ROOT signal",
            [{"type": "contains", "value": "ROOT", "weight": 1.0}],
        )
    )
    parent_wf.add_block(
        WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={},
            outputs={},
            workflow_ref="child-eval-workflow",
        )
    )
    parent_wf.set_entry(block_id)
    parent_wf.add_transition(block_id, "invoke_child")
    parent_wf.add_transition("invoke_child", None)

    EvalObserver = import_eval_observer()
    observer = CompositeObserver(
        ExecutionObserver(engine=engine, run_id=parent_run_id),
        EvalObserver(
            engine=engine,
            run_id=parent_run_id,
            sse_queue=make_eval_sse_queue(),
            assertion_configs=build_assertion_configs(parent_wf),
        ),
    )

    await parent_wf.run(WorkflowState(), observer=observer)

    with Session(engine) as session:
        parent_node = session.get(RunNode, f"{parent_run_id}:{block_id}")
        invoke_child_node = session.get(RunNode, f"{parent_run_id}:invoke_child")
        assert invoke_child_node is not None
        assert invoke_child_node.child_run_id is not None
        child_node = session.get(RunNode, f"{invoke_child_node.child_run_id}:{block_id}")

    assert parent_node is not None
    assert child_node is not None
    assert parent_node.eval_passed is True, (
        "The parent/root assertion surface must still evaluate the root block on the real "
        "nested workflow path."
    )
    assert child_node.eval_passed is True, (
        "Nested child workflows must evaluate using the child workflow's own assertion configs "
        "on the real WorkflowBlock + CompositeObserver path."
    )


@pytest.mark.asyncio
async def test_child_clone_can_receive_child_specific_assertion_configs() -> None:
    engine = make_eval_observer_engine()
    parent_run_id = seed_eval_run(engine, run_id="parent-child-specific-config-run")
    child_run_id = seed_eval_run(engine, run_id="child-specific-config-run")
    seed_eval_run_node(engine, run_id=child_run_id, output="child-only output")
    parent_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    parent = EvalObserver(
        engine=engine,
        run_id=parent_run_id,
        sse_queue=parent_queue,
        assertion_configs=assertion_configs_for(value="parent-only"),
    )
    child = parent.clone_for_child_run(
        child_run_id=child_run_id,
        assertion_configs=assertion_configs_for(value="child-only"),
    )

    child.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(output="child-only output"),
        soul=make_eval_soul(),
    )

    with Session(engine) as session:
        child_node = session.get(RunNode, f"{child_run_id}:{EVAL_BLOCK_ID}")
    assert parent_queue.empty()
    assert child_node.eval_passed is True
