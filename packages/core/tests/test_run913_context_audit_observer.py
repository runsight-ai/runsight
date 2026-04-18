"""
RED tests for RUN-913: emit context audit events through workflow observers.

RUN-907 through RUN-912 produce ContextAuditEventV1 data during context
resolution. RUN-913 must publish that event through the observer chain without
global state, and without changing the least-privilege input contract.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from runsight_core.block_io import BlockOutput, build_block_context
from runsight_core.context_governance import ContextAuditEventV1
from runsight_core.isolation.wrapper import IsolatedBlockWrapper
from runsight_core.observer import CompositeObserver, WorkflowObserver
from runsight_core.primitives import Soul, Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block


class RecordingObserver:
    def __init__(self) -> None:
        self.context_events: list[ContextAuditEventV1] = []
        self.started: list[str] = []
        self.completed: list[str] = []

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        pass

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        **_: Any,
    ) -> None:
        self.started.append(block_id)

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        **_: Any,
    ) -> None:
        self.completed.append(block_id)

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        pass

    def on_workflow_complete(
        self,
        workflow_name: str,
        state: WorkflowState,
        duration_s: float,
    ) -> None:
        pass

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: Any,
    ) -> None:
        pass

    def on_workflow_error(
        self,
        workflow_name: str,
        error: Exception,
        duration_s: float,
    ) -> None:
        pass

    def on_context_resolution(self, event: ContextAuditEventV1) -> None:
        self.context_events.append(event)


class BrokenContextObserver(RecordingObserver):
    def on_context_resolution(self, event: ContextAuditEventV1) -> None:
        raise RuntimeError("context observer failed")


class EchoBlock:
    block_id = "summarize"
    context_access = "declared"
    declared_inputs = {"summary": "draft.summary", "owner": "metadata.owner.name"}

    async def execute(self, ctx: Any) -> BlockOutput:
        return BlockOutput(output=json.dumps(ctx.inputs))


def _state() -> WorkflowState:
    return WorkflowState(
        results={
            "draft": BlockResult(
                output=json.dumps(
                    {
                        "summary": "short version",
                        "secret": "raw secret should never be emitted",
                    }
                )
            ),
            "other": BlockResult(output="unrelated"),
        },
        metadata={
            "run_id": "run_913",
            "workflow_name": "context_audit_observer",
            "owner": {"name": "Ada", "api_key": "super-secret-api-key"},
        },
        shared_memory={"secret": "shared secret"},
    )


def _execution_context(observer: RecordingObserver | CompositeObserver) -> BlockExecutionContext:
    block = EchoBlock()
    return BlockExecutionContext(
        workflow_name="context_audit_observer",
        blocks={block.block_id: block},
        call_stack=[],
        workflow_registry=None,
        observer=observer,
    )


def test_workflow_observer_protocol_exposes_context_resolution_hook() -> None:
    """All workflow observers must share a public context-resolution hook."""
    assert hasattr(WorkflowObserver, "on_context_resolution")
    assert isinstance(RecordingObserver(), WorkflowObserver)


def test_build_block_context_emits_one_context_resolution_event_with_all_records() -> None:
    """Two declared inputs produce one observer event containing two audit records."""
    observer = RecordingObserver()
    block = EchoBlock()

    ctx = build_block_context(block, _state(), observer=observer)

    assert ctx.inputs == {"summary": "short version", "owner": "Ada"}
    assert len(observer.context_events) == 1
    event = observer.context_events[0]
    assert event.event == "context_resolution"
    assert event.node_id == "summarize"
    assert event.run_id == "run_913"
    assert event.workflow_name == "context_audit_observer"
    assert [record.input_name for record in event.records] == ["summary", "owner"]
    assert event.resolved_count == 2
    assert "raw secret should never be emitted" not in event.model_dump_json()
    assert "super-secret-api-key" not in event.model_dump_json()


@pytest.mark.asyncio
async def test_execute_block_hands_context_audit_to_execution_observer() -> None:
    """execute_block must pass ctx.observer into context building for plain blocks."""
    observer = RecordingObserver()
    block = EchoBlock()
    ctx = BlockExecutionContext(
        workflow_name="context_audit_observer",
        blocks={block.block_id: block},
        call_stack=[],
        workflow_registry=None,
        observer=observer,
    )

    result_state = await execute_block(block, _state(), ctx)

    assert result_state.results["summarize"].output == json.dumps(
        {"summary": "short version", "owner": "Ada"}
    )
    assert len(observer.context_events) == 1
    assert observer.context_events[0].node_id == "summarize"


@pytest.mark.asyncio
async def test_step_execute_hands_execution_context_observer_to_context_build() -> None:
    """Step-wrapped blocks must emit audit through execution_context.observer."""
    observer = RecordingObserver()
    block = EchoBlock()
    step = Step(
        block=block,
        declared_inputs={"summary": "draft.summary", "owner": "metadata.owner.name"},
    )
    ctx = BlockExecutionContext(
        workflow_name="context_audit_observer",
        blocks={block.block_id: block},
        call_stack=[],
        workflow_registry=None,
        observer=observer,
    )

    result_state = await step.execute(_state(), execution_context=ctx)

    assert result_state.results["summarize"].output == json.dumps(
        {"summary": "short version", "owner": "Ada"}
    )
    assert len(observer.context_events) == 1
    assert observer.context_events[0].node_id == "summarize"


def test_composite_observer_broadcasts_context_resolution_and_isolates_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Context audit events use the same safe broadcast policy as lifecycle events."""
    good = RecordingObserver()
    composite = CompositeObserver(BrokenContextObserver(), good)
    block = EchoBlock()

    with caplog.at_level(logging.WARNING):
        ctx = build_block_context(block, _state(), observer=composite)

    assert ctx.inputs == {"summary": "short version", "owner": "Ada"}
    assert len(good.context_events) == 1
    assert good.context_events[0].node_id == "summarize"
    assert "BrokenContextObserver" in caplog.text


@pytest.mark.asyncio
async def test_isolated_wrapper_emits_context_audit_once_to_active_observer() -> None:
    """Isolation envelope audit is forwarded once, not duplicated by wrapper execution."""
    from runsight_core.isolation.envelope import ResultEnvelope

    observer = RecordingObserver()
    soul = Soul(
        id="analyst",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="Analyze only declared context.",
        model_name="gpt-4o",
    )
    inner = EchoBlock()
    inner.soul = soul
    inner.stateful = False
    wrapper = IsolatedBlockWrapper("summarize", inner)
    wrapper.context_access = "declared"
    wrapper.declared_inputs = {"summary": "draft.summary", "owner": "metadata.owner.name"}

    async def _capture(_: Any) -> ResultEnvelope:
        return ResultEnvelope(
            block_id="summarize",
            output="ok",
            exit_handle="done",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

    wrapper._run_in_subprocess = _capture
    ctx = _execution_context(observer)

    await execute_block(wrapper, _state(), ctx)

    assert len(observer.context_events) == 1
    assert observer.context_events[0].node_id == "summarize"
    assert len(observer.context_events[0].records) == 2
