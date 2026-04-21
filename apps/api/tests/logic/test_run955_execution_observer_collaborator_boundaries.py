"""Red tests for RUN-955 execution observer collaborator boundaries.

These tests stay on public observer callbacks and explicit persistence
contracts:

- failures in one persistence responsibility stay non-fatal and do not block
  other observable writes that still have actionable data
- child workflow block start keeps its log path independent from child-run
  persistence
- context-audit persistence can consume serializer-produced payloads through a
  configurable seam instead of forcing serialization to stay embedded in the
  monolith
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Iterable
from unittest.mock import patch

import pytest
from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.context_governance import ContextAuditEventV1, ContextAuditRecordV1
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import NodeStatus, Run, RunNode, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver

_REAL_SESSION = Session


def _db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, *, run_id: str = "run_955", status: RunStatus = RunStatus.running) -> str:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_955",
                workflow_name="Execution Observer",
                status=status,
                task_json="{}",
                created_at=time.time(),
                updated_at=time.time(),
            )
        )
        session.commit()
    return run_id


def _seed_running_node(
    engine,
    *,
    run_id: str,
    block_id: str = "call_child",
    block_type: str = "workflow",
) -> None:
    with Session(engine) as session:
        session.add(
            RunNode(
                id=f"{run_id}:{block_id}",
                run_id=run_id,
                node_id=block_id,
                block_type=block_type,
                status=NodeStatus.running,
                started_at=time.time(),
                updated_at=time.time(),
            )
        )
        session.commit()


def _state_with_incremental_log() -> WorkflowState:
    return WorkflowState(
        total_cost_usd=1.25,
        total_tokens=321,
        execution_log=[{"role": "assistant", "content": "incremental tail"}],
        results={"call_child": BlockResult(output="child completed")},
    )


def _context_audit_event(node_id: str = "call_child") -> ContextAuditEventV1:
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


def _log_rows(engine, *, run_id: str) -> list[LogEntry]:
    with Session(engine) as session:
        return list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())


def _event_messages(rows: Iterable[LogEntry]) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for row in rows:
        try:
            parsed.append(json.loads(row.message))
        except Exception:
            continue
    return parsed


def _fail_on_session_indices(*indices: int):
    counter = {"count": 0}

    class SelectiveSession:
        def __init__(self, engine):
            counter["count"] += 1
            self._wrapped = _REAL_SESSION(engine)
            self._fail_commit = counter["count"] in indices

        def __enter__(self):
            self._wrapped.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._wrapped.__exit__(exc_type, exc, tb)

        def commit(self):
            if self._fail_commit:
                self._fail_commit = False
                raise RuntimeError("simulated observer persistence failure")
            return self._wrapped.commit()

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

    return SelectiveSession


class _SerializerDouble:
    def __init__(self, payload: str):
        self.payload = payload
        self.calls: list[object] = []

    def __call__(self, event) -> str:
        self.calls.append(event)
        return self.payload

    def serialize(self, event) -> str:
        self.calls.append(event)
        return self.payload

    def dump_json(self, event) -> str:
        self.calls.append(event)
        return self.payload


class _ExplodingAuditEvent:
    def __init__(self, *, node_id: str = "summarize"):
        self.node_id = node_id
        self.warning_count = 0
        self.records = [SimpleNamespace(severity="allow")]

    def model_dump_json(self) -> str:
        raise AssertionError("raw event serialization should not be required here")


def _observer_with_audit_serializer(engine, *, run_id: str, serializer):
    init = inspect.signature(ExecutionObserver.__init__)
    kwargs = {"engine": engine, "run_id": run_id}

    constructor_names = (
        "context_audit_serializer",
        "audit_serializer",
        "serializer",
    )
    for name in constructor_names:
        if name in init.parameters:
            kwargs[name] = serializer
            return ExecutionObserver(**kwargs)

    bundle_names = ("components", "collaborators", "persistence", "observer_components")
    for name in bundle_names:
        if name in init.parameters:
            bundle = SimpleNamespace(
                context_audit_serializer=serializer,
                audit_serializer=serializer,
                serializer=serializer,
            )
            kwargs[name] = bundle
            return ExecutionObserver(**kwargs)

    observer = ExecutionObserver(**kwargs)

    setter_names = (
        "set_context_audit_serializer",
        "configure_context_audit_serializer",
        "set_audit_serializer",
        "configure_audit_serializer",
    )
    for name in setter_names:
        setter = getattr(observer, name, None)
        if callable(setter):
            setter(serializer)
            return observer

    attr_names = (
        "context_audit_serializer",
        "_context_audit_serializer",
        "audit_serializer",
        "_audit_serializer",
        "serializer",
    )
    for name in attr_names:
        if hasattr(observer, name):
            setattr(observer, name, serializer)
            return observer

    for bundle_name in bundle_names:
        bundle = getattr(observer, bundle_name, None)
        if bundle is None:
            continue
        for name in attr_names:
            if hasattr(bundle, name):
                setattr(bundle, name, serializer)
                return observer

    raise AssertionError(
        "ExecutionObserver must expose a configurable context-audit serializer seam"
    )


def test_workflow_start_run_write_failure_still_persists_workflow_start_log() -> None:
    engine = _db_engine()
    run_id = _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id=run_id)

    with patch(
        "runsight_api.logic.observers.execution_observer.Session",
        _fail_on_session_indices(1),
    ):
        observer.on_workflow_start("wf_955", WorkflowState())

    messages = _event_messages(_log_rows(engine, run_id=run_id))
    assert any(message.get("event") == "workflow_start" for message in messages)


def test_workflow_call_block_start_failure_still_persists_block_start_log() -> None:
    engine = _db_engine()
    run_id = _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id=run_id)

    with patch(
        "runsight_api.logic.observers.execution_observer.Session",
        _fail_on_session_indices(2),
    ):
        observer.on_block_start(
            "wf_955",
            "call_child",
            "workflow",
            child_workflow_id="wf_child",
            child_workflow_name="Child Workflow",
        )

    rows = _log_rows(engine, run_id=run_id)
    messages = _event_messages(rows)
    assert any(message.get("event") == "block_start" for message in messages)

    with Session(engine) as session:
        children = list(session.exec(select(Run).where(Run.parent_run_id == run_id)).all())
        assert children == []


def test_block_complete_node_write_failure_still_persists_logs_and_trace_tail() -> None:
    engine = _db_engine()
    run_id = _seed_run(engine)
    _seed_running_node(engine, run_id=run_id)
    observer = ExecutionObserver(engine=engine, run_id=run_id)
    state = _state_with_incremental_log()

    with patch(
        "runsight_api.logic.observers.execution_observer.Session",
        _fail_on_session_indices(1),
    ):
        observer.on_block_complete("wf_955", "call_child", "workflow", 1.5, state)

    rows = _log_rows(engine, run_id=run_id)
    messages = _event_messages(rows)
    assert any(message.get("event") == "block_complete" for message in messages)
    assert any(row.level == "trace" and "incremental tail" in row.message for row in rows)


def test_block_error_node_write_failure_still_persists_block_error_log() -> None:
    engine = _db_engine()
    run_id = _seed_run(engine)
    _seed_running_node(engine, run_id=run_id)
    observer = ExecutionObserver(engine=engine, run_id=run_id)

    with patch(
        "runsight_api.logic.observers.execution_observer.Session",
        _fail_on_session_indices(1),
    ):
        observer.on_block_error("wf_955", "call_child", "workflow", 2.0, RuntimeError("boom"))

    rows = _log_rows(engine, run_id=run_id)
    messages = _event_messages(rows)
    assert any(message.get("event") == "block_error" for message in messages)
    assert any(row.level == "error" for row in rows)


def test_workflow_complete_run_write_failure_still_persists_logs_and_trace_tail() -> None:
    engine = _db_engine()
    run_id = _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id=run_id)
    state = _state_with_incremental_log()

    with patch(
        "runsight_api.logic.observers.execution_observer.Session",
        _fail_on_session_indices(1),
    ):
        observer.on_workflow_complete("wf_955", state, 8.5)

    rows = _log_rows(engine, run_id=run_id)
    messages = _event_messages(rows)
    assert any(message.get("event") == "workflow_complete" for message in messages)
    assert any(row.level == "trace" and "incremental tail" in row.message for row in rows)


@pytest.mark.parametrize(
    ("error", "expected_level"),
    [
        (asyncio.CancelledError(), "warning"),
        (
            BudgetKilledException(
                scope="block",
                block_id="call_child",
                limit_kind="cost_usd",
                limit_value=1.0,
                actual_value=2.0,
            ),
            "error",
        ),
    ],
)
def test_workflow_error_run_write_failure_still_persists_terminal_log(
    error: Exception, expected_level: str
) -> None:
    engine = _db_engine()
    run_id = _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id=run_id)

    with patch(
        "runsight_api.logic.observers.execution_observer.Session",
        _fail_on_session_indices(1),
    ):
        observer.on_workflow_error("wf_955", error, 9.0)

    rows = _log_rows(engine, run_id=run_id)
    messages = _event_messages(rows)
    assert any(message.get("event") == "workflow_error" for message in messages)
    assert any(row.level == expected_level for row in rows)


def test_context_audit_uses_configured_serializer_payload_when_available() -> None:
    engine = _db_engine()
    run_id = _seed_run(engine)
    serializer = _SerializerDouble('{"event":"context_resolution","source":"serializer"}')
    observer = _observer_with_audit_serializer(engine, run_id=run_id, serializer=serializer)

    observer.on_context_resolution(_ExplodingAuditEvent())

    rows = _log_rows(engine, run_id=run_id)
    assert any(row.message == serializer.payload for row in rows)
    assert serializer.calls, "Expected the configured serializer seam to be exercised"


def test_context_audit_sink_failure_is_best_effort_after_serializer_delegation() -> None:
    engine = _db_engine()
    run_id = _seed_run(engine)
    serializer = _SerializerDouble('{"event":"context_resolution","source":"serializer"}')
    observer = _observer_with_audit_serializer(engine, run_id=run_id, serializer=serializer)

    with patch(
        "runsight_api.logic.observers.execution_observer.Session",
        _fail_on_session_indices(1),
    ):
        observer.on_context_resolution(_ExplodingAuditEvent())

    rows = _log_rows(engine, run_id=run_id)
    assert serializer.calls, "Expected the configured serializer seam to be exercised"
    assert rows == []
