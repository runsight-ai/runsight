"""Red tests for RUN-955 execution observer collaborator boundaries.

This suite pins an explicit public seam for the observer split:

- workflow lifecycle writes delegate through an injected run writer
- block lifecycle writes and child-run lookup/clone delegate through an
  injected node writer
- incremental execution-log persistence delegates through an injected log sink
- context-audit persistence delegates through an injected audit sink

It also makes the current best-effort failure contract explicit: a failure in
one extracted collaborator must stay non-fatal and should not silently prevent
other collaborator-owned writes that still have actionable data.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, call

from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.context_governance import ContextAuditEventV1, ContextAuditRecordV1
from runsight_core.state import BlockResult, WorkflowState

from runsight_api.logic.observers.execution_observer import ExecutionObserver


def _context_audit_event(*, node_id: str = "call_child") -> ContextAuditEventV1:
    return ContextAuditEventV1(
        run_id="run_955",
        workflow_name="wf_955",
        node_id=node_id,
        block_type="workflow",
        access="declared",
        mode="strict",
        records=[
            ContextAuditRecordV1(
                input_name="api_key",
                from_ref="metadata.credentials.api_key",
                namespace="metadata",
                source="credentials",
                field_path="api_key",
                status="resolved",
                severity="allow",
                value_type="str",
                preview="sk-live-secret",
                reason=None,
            )
        ],
        resolved_count=1,
        denied_count=0,
        warning_count=0,
        emitted_at=datetime.now(timezone.utc),
    )


def _state_with_execution_log() -> WorkflowState:
    return WorkflowState(
        total_cost_usd=1.25,
        total_tokens=321,
        execution_log=[{"role": "assistant", "content": "incremental tail"}],
        results={"call_child": BlockResult(output="child completed")},
    )


def _observer(
    *,
    run_writer: Mock | None = None,
    node_writer: Mock | None = None,
    execution_log_sink: Mock | None = None,
    context_audit_sink: Mock | None = None,
) -> ExecutionObserver:
    return ExecutionObserver(
        engine=Mock(name="engine"),
        run_id="run_955",
        run_lifecycle_writer=run_writer or Mock(name="run_writer"),
        node_lifecycle_writer=node_writer or Mock(name="node_writer"),
        execution_log_sink=execution_log_sink or Mock(name="execution_log_sink"),
        context_audit_sink=context_audit_sink or Mock(name="context_audit_sink"),
    )


def test_execution_observer_routes_lifecycle_events_through_injected_collaborators() -> None:
    run_writer = Mock(name="run_writer")
    node_writer = Mock(name="node_writer")
    execution_log_sink = Mock(name="execution_log_sink")
    context_audit_sink = Mock(name="context_audit_sink")
    observer = _observer(
        run_writer=run_writer,
        node_writer=node_writer,
        execution_log_sink=execution_log_sink,
        context_audit_sink=context_audit_sink,
    )

    start_state = WorkflowState()
    state = _state_with_execution_log()
    block_error = RuntimeError("block failed")
    cancelled = asyncio.CancelledError()
    budget_error = BudgetKilledException(
        scope="block",
        block_id="call_child",
        limit_kind="cost_usd",
        limit_value=1.0,
        actual_value=2.0,
    )
    audit_event = _context_audit_event()

    observer.on_workflow_start("wf_955", start_state)
    observer.on_block_start(
        "wf_955",
        "call_child",
        "workflow",
        child_workflow_id="wf_child",
        child_workflow_name="Child Workflow",
    )
    observer.on_block_complete("wf_955", "call_child", "workflow", 1.5, state)
    observer.on_block_error("wf_955", "call_child", "workflow", 2.0, block_error)
    observer.on_workflow_complete("wf_955", state, 8.5)
    observer.on_workflow_error("wf_955", cancelled, 9.0)
    observer.on_workflow_error("wf_955", budget_error, 10.0)
    observer.on_context_resolution(audit_event)

    run_writer.on_workflow_start.assert_called_once_with("run_955", "wf_955", start_state)
    run_writer.on_workflow_complete.assert_called_once_with("run_955", "wf_955", state, 8.5)
    run_writer.on_workflow_error.assert_has_calls(
        [
            call("run_955", "wf_955", cancelled, 9.0),
            call("run_955", "wf_955", budget_error, 10.0),
        ]
    )
    node_writer.on_block_start.assert_called_once_with(
        "run_955",
        "wf_955",
        "call_child",
        "workflow",
        soul=None,
        child_workflow_id="wf_child",
        child_workflow_name="Child Workflow",
    )
    node_writer.on_block_complete.assert_called_once_with(
        "run_955",
        "wf_955",
        "call_child",
        "workflow",
        1.5,
        state,
        soul=None,
    )
    node_writer.on_block_error.assert_called_once_with(
        "run_955",
        "wf_955",
        "call_child",
        "workflow",
        2.0,
        block_error,
    )
    execution_log_sink.on_block_complete.assert_called_once_with("run_955", "call_child", state)
    execution_log_sink.on_workflow_complete.assert_called_once_with("run_955", state)
    context_audit_sink.on_context_resolution.assert_called_once_with("run_955", audit_event)


def test_child_run_lookup_and_clone_keep_using_the_injected_node_writer() -> None:
    node_writer = Mock(name="node_writer")
    node_writer.get_child_run_id_for_block.return_value = "run_955_child"
    observer = _observer(node_writer=node_writer)

    assert observer.get_child_run_id_for_block("call_child") == "run_955_child"

    child = observer.clone_for_child_run(child_run_id="run_955_child")
    child.on_block_start(
        "wf_child",
        "nested_call",
        "workflow",
        child_workflow_id="wf_grandchild",
        child_workflow_name="Grandchild Workflow",
    )

    node_writer.get_child_run_id_for_block.assert_called_once_with("run_955", "call_child")
    node_writer.on_block_start.assert_called_once_with(
        "run_955_child",
        "wf_child",
        "nested_call",
        "workflow",
        soul=None,
        child_workflow_id="wf_grandchild",
        child_workflow_name="Grandchild Workflow",
    )


def test_workflow_complete_run_writer_failure_is_nonfatal_and_still_flushes_log_sink() -> None:
    run_writer = Mock(name="run_writer")
    run_writer.on_workflow_complete.side_effect = RuntimeError("run writer down")
    execution_log_sink = Mock(name="execution_log_sink")
    observer = _observer(run_writer=run_writer, execution_log_sink=execution_log_sink)
    state = _state_with_execution_log()

    observer.on_workflow_complete("wf_955", state, 5.0)

    run_writer.on_workflow_complete.assert_called_once_with("run_955", "wf_955", state, 5.0)
    execution_log_sink.on_workflow_complete.assert_called_once_with("run_955", state)


def test_block_complete_node_writer_failure_is_nonfatal_and_still_flushes_log_sink() -> None:
    node_writer = Mock(name="node_writer")
    node_writer.on_block_complete.side_effect = RuntimeError("node writer down")
    execution_log_sink = Mock(name="execution_log_sink")
    observer = _observer(node_writer=node_writer, execution_log_sink=execution_log_sink)
    state = _state_with_execution_log()

    observer.on_block_complete("wf_955", "call_child", "workflow", 0.75, state)

    node_writer.on_block_complete.assert_called_once_with(
        "run_955",
        "wf_955",
        "call_child",
        "workflow",
        0.75,
        state,
        soul=None,
    )
    execution_log_sink.on_block_complete.assert_called_once_with("run_955", "call_child", state)


def test_execution_log_sink_failures_are_nonfatal_after_the_node_write() -> None:
    node_writer = Mock(name="node_writer")
    execution_log_sink = Mock(name="execution_log_sink")
    execution_log_sink.on_block_complete.side_effect = RuntimeError("log sink down")
    observer = _observer(node_writer=node_writer, execution_log_sink=execution_log_sink)
    state = _state_with_execution_log()

    observer.on_block_complete("wf_955", "call_child", "workflow", 0.5, state)

    node_writer.on_block_complete.assert_called_once_with(
        "run_955",
        "wf_955",
        "call_child",
        "workflow",
        0.5,
        state,
        soul=None,
    )
    execution_log_sink.on_block_complete.assert_called_once_with("run_955", "call_child", state)


def test_context_audit_sink_failures_are_nonfatal_best_effort() -> None:
    context_audit_sink = Mock(name="context_audit_sink")
    context_audit_sink.on_context_resolution.side_effect = RuntimeError("audit sink down")
    observer = _observer(context_audit_sink=context_audit_sink)
    event = _context_audit_event(node_id="summarize")

    observer.on_context_resolution(event)

    context_audit_sink.on_context_resolution.assert_called_once_with("run_955", event)
