"""Red tests for RUN-953 using facade-blackout ownership guards.

Each test reuses a workflow-runtime behavior already covered elsewhere, then
poisons the current legacy ownership point inside ``runsight_core.workflow``.
The public surface should keep working once those concerns are delegated out of
the facade, but it fails today because the workflow module still owns them.
"""

from __future__ import annotations

import asyncio
import inspect
import json

import pytest
import runsight_core.workflow as workflow_module
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.conditions.engine import Case, Condition, ConditionGroup
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import WorkflowLimitsDef


def _blackout_workflow_method(
    monkeypatch: pytest.MonkeyPatch, method_name: str, message: str
) -> None:
    method = getattr(Workflow, method_name, None)
    if method is None:
        return

    if inspect.iscoroutinefunction(method):

        async def _poison(*args, **kwargs):
            for value in list(args) + list(kwargs.values()):
                if inspect.iscoroutine(value):
                    value.close()
            raise AssertionError(message)

        monkeypatch.setattr(Workflow, method_name, _poison)
        return

    def _poison(*args, **kwargs):
        raise AssertionError(message)

    monkeypatch.setattr(Workflow, method_name, _poison)


def _blackout_workflow_alias(
    monkeypatch: pytest.MonkeyPatch, alias_name: str, message: str
) -> None:
    def _poison(*args, **kwargs):
        raise AssertionError(message)

    monkeypatch.setattr(workflow_module, alias_name, _poison)


class _ResultBlock(BaseBlock):
    def __init__(self, block_id: str, output: str) -> None:
        super().__init__(block_id)
        self.output = output
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        return BlockOutput(output=self.output)


class _JsonStatusBlock(BaseBlock):
    def __init__(self, block_id: str, status: str) -> None:
        super().__init__(block_id)
        self.status = status
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        return BlockOutput(output=json.dumps({"status": self.status}))


class _SlowBlock(BaseBlock):
    def __init__(self, block_id: str, sleep_seconds: float) -> None:
        super().__init__(block_id)
        self.sleep_seconds = sleep_seconds
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        await asyncio.sleep(self.sleep_seconds)
        return BlockOutput(output="slow done")


class _RecordingObserver:
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


def _make_cycle_workflow() -> Workflow:
    workflow = Workflow("cyclic_wf")
    workflow.add_block(_ResultBlock("a", "A"))
    workflow.add_block(_ResultBlock("b", "B"))
    workflow.add_block(_ResultBlock("c", "C"))
    workflow.add_transition("a", "b")
    workflow.add_transition("b", "c")
    workflow.add_transition("c", "a")
    workflow.set_entry("a")
    return workflow


def _make_nested_observer_workflow() -> Workflow:
    child_workflow = Workflow("child_workflow")
    child_step = _ResultBlock("child_step", "child output")
    child_workflow.add_block(child_step)
    child_workflow.set_entry("child_step")
    child_workflow.add_transition("child_step", None)

    invoke_child = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )
    tail = _ResultBlock("tail", "tail output")

    workflow = Workflow("parent_workflow")
    loop_block = LoopBlock("loop_block", inner_block_refs=[invoke_child.block_id], max_rounds=1)
    workflow.add_block(loop_block)
    workflow.add_block(invoke_child)
    workflow.add_block(tail)
    workflow.set_entry("loop_block")
    workflow.add_transition("loop_block", "tail")
    workflow.add_transition("tail", None)
    return workflow


def test_validation_blackout_still_reports_cycle_via_public_validate(
    monkeypatch: pytest.MonkeyPatch,
):
    _blackout_workflow_method(
        monkeypatch,
        "_detect_cycle",
        "legacy validation ownership inside Workflow should be blacked out for RUN-953",
    )
    workflow = _make_cycle_workflow()

    errors = workflow.validate()

    assert len(errors) == 1
    assert "Cycle detected" in errors[0]


@pytest.mark.asyncio
async def test_routing_blackout_still_takes_output_condition_branch(
    monkeypatch: pytest.MonkeyPatch,
):
    _blackout_workflow_method(
        monkeypatch,
        "_resolve_next",
        "legacy routing ownership inside Workflow should be blacked out for RUN-953",
    )

    router = _JsonStatusBlock("router", "ok")
    approved = _ResultBlock("approved", "approved output")
    fallback = _ResultBlock("fallback", "fallback output")

    workflow = Workflow("routing_blackout")
    workflow.add_block(router)
    workflow.add_block(approved)
    workflow.add_block(fallback)
    workflow.set_entry("router")
    workflow.set_output_conditions(
        "router",
        [
            Case(
                case_id="approved",
                condition_group=ConditionGroup(
                    conditions=[
                        Condition(eval_key="status", operator="equals", value="ok"),
                    ],
                    combinator="and",
                ),
            )
        ],
        default="fallback",
    )
    workflow.add_conditional_transition(
        "router",
        {
            "approved": "approved",
            "fallback": "fallback",
            "default": "fallback",
        },
    )
    workflow.add_transition("approved", None)
    workflow.add_transition("fallback", None)

    final_state = await workflow.run(WorkflowState())

    assert router.calls == 1
    assert final_state.results["router"].exit_handle == "approved"
    assert approved.calls == 1
    assert fallback.calls == 0
    assert final_state.results["approved"].output == "approved output"


@pytest.mark.asyncio
async def test_dispatch_and_observer_blackout_still_preserves_nested_event_order(
    monkeypatch: pytest.MonkeyPatch,
):
    _blackout_workflow_alias(
        monkeypatch,
        "build_block_context",
        "legacy dispatch ownership inside runsight_core.workflow should be blacked out",
    )
    _blackout_workflow_alias(
        monkeypatch,
        "apply_block_output",
        "legacy dispatch ownership inside runsight_core.workflow should be blacked out",
    )
    _blackout_workflow_method(
        monkeypatch,
        "_notify_observers",
        "legacy observer ownership inside Workflow should be blacked out for RUN-953",
    )

    workflow = _make_nested_observer_workflow()
    observer = _RecordingObserver()

    final_state = await workflow.run(WorkflowState(), observer=observer)

    assert final_state.results["tail"].output == "tail output"
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
async def test_timeout_blackout_still_raises_workflow_budget_timeout(
    monkeypatch: pytest.MonkeyPatch,
):
    _blackout_workflow_method(
        monkeypatch,
        "_run_with_timeout",
        "legacy timeout ownership inside Workflow should be blacked out for RUN-953",
    )

    workflow = Workflow("timeout_blackout")
    workflow.add_block(_SlowBlock("slow", sleep_seconds=1.1))
    workflow.set_entry("slow")
    workflow.add_transition("slow", None)
    workflow.limits = WorkflowLimitsDef(max_duration_seconds=1)

    with pytest.raises(BudgetKilledException) as exc_info:
        await workflow.run(WorkflowState())

    assert exc_info.value.scope == "workflow"
    assert exc_info.value.limit_kind == "timeout"
    assert exc_info.value.limit_value == 1
