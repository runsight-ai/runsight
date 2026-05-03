"""WorkflowRunInvoker Direct API invocation boundary coverage."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.domain.errors import InputValidationError, WorkflowNotFound
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.execution_service import (
    _prepare_run_inputs_from_schema,
    _workflow_input_schema_from_yaml,
)
from runsight_api.logic.services.run_service import RunService


WORKFLOW_ID = "direct_invocation_workflow"
COMMITTED_MAIN_SHA = "931" * 13 + "9"


def _invoker_contract():
    from runsight_api.logic.services.workflow_run_invoker import (
        WorkflowRunInvocation,
        WorkflowRunInvoker,
    )

    return WorkflowRunInvoker, WorkflowRunInvocation


def _db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _main_workflow_yaml(*, name: str = "Committed Main Workflow") -> str:
    return f"""
id: {WORKFLOW_ID}
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
  max_results:
    type: number
    required: false
    default: 10
workflow:
  name: {name}
  entry: start
  transitions:
    - from: start
      to: null
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {{"ok": True}}
"""


def _dirty_workflow_yaml() -> str:
    return f"""
id: {WORKFLOW_ID}
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
  debug:
    type: boolean
    required: false
    default: true
workflow:
  name: Dirty Live Workflow
  entry: start
  transitions:
    - from: start
      to: null
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {{"dirty": True}}
"""


def _workflow_entity(
    yaml_text: str,
    *,
    name: str,
    enabled: bool = True,
    warnings: list[dict[str, str]] | None = None,
) -> WorkflowEntity:
    return WorkflowEntity(
        kind="workflow",
        id=WORKFLOW_ID,
        name=name,
        yaml=yaml_text,
        enabled=enabled,
        valid=True,
        validation_error=None,
        warnings=warnings or [],
    )


def _prepared_inputs(yaml_text: str, inputs: dict[str, object]):
    return _prepare_run_inputs_from_schema(
        WORKFLOW_ID,
        _workflow_input_schema_from_yaml(WORKFLOW_ID, yaml_text),
        inputs,
    )


def _field(result: Any, name: str) -> Any:
    if isinstance(result, dict):
        return result.get(name)
    return getattr(result, name)


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _assert_failure_result(result: Any, *, code: str, run_id: str | None = None) -> None:
    assert _field(result, "accepted") is False
    assert _value(_field(result, "failure_code")) == code
    assert _field(result, "run_id") == run_id


def _direct_api_invocation(**overrides: Any):
    _, WorkflowRunInvocation = _invoker_contract()
    payload = {
        "workflow_id": WORKFLOW_ID,
        "inputs": {"query": "from api"},
        "source_correlation_id": "corr-direct-invocation",
        "source_metadata": {
            "entry_path": "direct_api",
            "request_path": f"/api/workflows/{WORKFLOW_ID}/runs",
            "client_request_id": "req-direct-invocation",
        },
    }
    payload.update(overrides)
    return WorkflowRunInvocation.direct_api(**payload)


@dataclass(frozen=True)
class _AdmissionDecision:
    allowed: bool
    failure_code: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class _ResolvedWorkflowSnapshot:
    workflow_id: str
    branch: str
    workflow: WorkflowEntity | None
    commit_sha: str


class _RuntimeAdmission:
    def __init__(self, *, enabled: bool = True, saturated: bool = False) -> None:
        self.enabled = enabled
        self.saturated = saturated
        self.calls: list[Any] = []

    def check_external_invocation(self, invocation: Any) -> _AdmissionDecision:
        self.calls.append(invocation)
        if not self.enabled:
            return _AdmissionDecision(False, "runtime_unavailable", "External invocation disabled")
        if self.saturated:
            return _AdmissionDecision(False, "admission_saturated", "Runtime admission saturated")
        return _AdmissionDecision(True)

    def check(self, invocation: Any) -> _AdmissionDecision:
        return self.check_external_invocation(invocation)

    def admit(self, invocation: Any) -> _AdmissionDecision:
        return self.check_external_invocation(invocation)


class _NoCallExecutionService:
    def __init__(self) -> None:
        self.prepare_calls: list[Any] = []
        self.launch_calls: list[Any] = []

    def prepare_run_inputs(self, *args: Any, **kwargs: Any) -> None:
        self.prepare_calls.append((args, kwargs))
        raise AssertionError("pre-run admission failure must not validate inputs")

    async def launch_execution(self, *args: Any, **kwargs: Any) -> None:
        self.launch_calls.append((args, kwargs))
        raise AssertionError("pre-run admission failure must not launch execution")


class _RecordingExecutionService:
    def __init__(
        self,
        *,
        prepared: Any | None = None,
        prepare_error: Exception | None = None,
        launch_error: Exception | None = None,
        committed_workflow: WorkflowEntity | None = None,
        commit_sha: str = COMMITTED_MAIN_SHA,
        run_service: Any | None = None,
    ) -> None:
        self.prepared = prepared
        self.prepare_error = prepare_error
        self.launch_error = launch_error
        self.committed_workflow = committed_workflow
        self.commit_sha = commit_sha
        self.run_service = run_service
        self.prepare_calls: list[dict[str, Any]] = []
        self.launch_calls: list[dict[str, Any]] = []
        self.snapshot_calls: list[dict[str, Any]] = []

    def resolve_workflow_run_snapshot(
        self, workflow_id: str, *, branch: str
    ) -> _ResolvedWorkflowSnapshot:
        self.snapshot_calls.append({"workflow_id": workflow_id, "branch": branch})
        if self.committed_workflow is None and self.prepare_error is None:
            raise WorkflowNotFound(f"Workflow {workflow_id!r} not found on {branch!r}")
        return _ResolvedWorkflowSnapshot(
            workflow_id=workflow_id,
            branch=branch,
            workflow=self.committed_workflow,
            commit_sha=self.commit_sha,
        )

    def prepare_run_inputs_from_snapshot(
        self, snapshot: _ResolvedWorkflowSnapshot, inputs: dict[str, Any]
    ):
        self.prepare_calls.append(
            {"workflow_id": snapshot.workflow_id, "inputs": inputs, "branch": snapshot.branch}
        )
        if self.prepare_error is not None:
            raise self.prepare_error
        return self.prepared

    async def launch_execution_from_snapshot(
        self,
        run_id: str,
        workflow_id: str,
        inputs: Any,
        *,
        snapshot: _ResolvedWorkflowSnapshot,
    ) -> None:
        self.launch_calls.append(
            {
                "run_id": run_id,
                "workflow_id": workflow_id,
                "inputs": inputs,
                "branch": snapshot.branch,
            }
        )
        if self.launch_error is not None:
            raise self.launch_error
        if self.run_service is not None:
            run = self.run_service.get_run(run_id)
            run.commit_sha = self.commit_sha
            run_repo = getattr(self.run_service, "run_repo", None)
            if run_repo is not None:
                run_repo.update_run(run)


class _RecordingRunService:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.fail_calls: list[dict[str, Any]] = []
        self.created_run: Any | None = None

    def create_run(
        self,
        workflow_id: str,
        inputs: Any,
        *,
        branch: str,
        source: str,
        source_correlation_id: str | None = None,
        source_metadata: dict[str, Any] | None = None,
        workflow_snapshot: WorkflowEntity | None = None,
    ):
        self.create_calls.append(
            {
                "workflow_id": workflow_id,
                "inputs": inputs,
                "branch": branch,
                "source": source,
                "source_correlation_id": source_correlation_id,
                "source_metadata": source_metadata,
                "workflow_snapshot": workflow_snapshot,
            }
        )
        self.created_run = Mock()
        self.created_run.id = "run_direct_invocation_created"
        self.created_run.workflow_id = workflow_id
        self.created_run.workflow_name = (
            workflow_snapshot.name if workflow_snapshot is not None else workflow_id
        )
        self.created_run.status = RunStatus.pending
        self.created_run.branch = branch
        self.created_run.source = source
        self.created_run.commit_sha = None
        self.created_run.source_correlation_id = source_correlation_id
        self.created_run.source_metadata = source_metadata or {}
        return self.created_run

    def get_run(self, run_id: str):
        assert self.created_run is not None
        assert self.created_run.id == run_id
        return self.created_run

    def refresh_run(self, run: Any):
        return run

    def fail_run(self, run_id: str, error: str):
        self.fail_calls.append({"run_id": run_id, "error": error})
        assert self.created_run is not None
        self.created_run.status = RunStatus.failed
        self.created_run.error = error
        return self.created_run


class _BlockingPreRunExecutionService(_RecordingExecutionService):
    def __init__(self, *, delay_seconds: float, prepared: Any, committed_workflow: WorkflowEntity):
        super().__init__(prepared=prepared, committed_workflow=committed_workflow)
        self.delay_seconds = delay_seconds

    def resolve_workflow_run_snapshot(
        self, workflow_id: str, *, branch: str
    ) -> _ResolvedWorkflowSnapshot:
        time.sleep(self.delay_seconds)
        return super().resolve_workflow_run_snapshot(workflow_id, branch=branch)

    def prepare_run_inputs_from_snapshot(
        self, snapshot: _ResolvedWorkflowSnapshot, inputs: dict[str, Any]
    ):
        time.sleep(self.delay_seconds)
        return super().prepare_run_inputs_from_snapshot(snapshot, inputs)


class TestWorkflowRunInvocationDirectApiContract:
    def test_direct_api_factory_owns_api_source_and_saved_main_policy(self) -> None:
        invocation = _direct_api_invocation()

        assert invocation.workflow_id == WORKFLOW_ID
        assert _value(invocation.caller) == "api"
        assert _value(invocation.source) == "api"
        assert invocation.inputs == {"query": "from api"}
        assert invocation.source_correlation_id == "corr-direct-invocation"
        assert invocation.source_metadata["entry_path"] == "direct_api"
        assert _value(getattr(invocation, "branch", "main")) == "main"
        assert getattr(invocation, "commit_sha", None) is None

    @pytest.mark.parametrize(
        "privileged_fields",
        [
            {"caller": "manual"},
            {"source": "manual"},
            {"branch": "feature/dirty"},
            {"commit_sha": "caller-selected-sha"},
            {"debug": True},
            {"simulation": True},
            {"idempotency_key": "deferred-by-run-85"},
            {"trigger_id": "trigger-931"},
            {"delivery_id": "delivery-931"},
            {"source_metadata": {"idempotency_key": "deferred-by-run-85"}},
        ],
    )
    def test_direct_api_factory_rejects_external_privileged_fields(
        self, privileged_fields: dict[str, object]
    ) -> None:
        _, WorkflowRunInvocation = _invoker_contract()

        with pytest.raises((TypeError, ValueError)):
            WorkflowRunInvocation.direct_api(
                workflow_id=WORKFLOW_ID,
                inputs={"query": "from api"},
                **privileged_fields,
            )


class TestWorkflowRunInvokerPreRunFailures:
    @pytest.mark.asyncio
    async def test_runtime_disabled_returns_typed_result_before_validation_or_run_creation(
        self,
    ) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        execution = _NoCallExecutionService()
        run_service = _RecordingRunService()
        admission = _RuntimeAdmission(enabled=False)
        invoker = WorkflowRunInvoker(
            run_service=run_service,
            execution_service=execution,
            runtime_admission=admission,
        )

        result = await invoker.invoke(_direct_api_invocation())

        _assert_failure_result(result, code="runtime_unavailable")
        assert admission.calls
        assert execution.prepare_calls == []
        assert execution.launch_calls == []
        assert run_service.create_calls == []

    @pytest.mark.asyncio
    async def test_admission_saturated_returns_typed_result_before_run_creation(self) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        execution = _NoCallExecutionService()
        run_service = _RecordingRunService()
        admission = _RuntimeAdmission(saturated=True)
        invoker = WorkflowRunInvoker(
            run_service=run_service,
            execution_service=execution,
            runtime_admission=admission,
        )

        result = await invoker.invoke(_direct_api_invocation())

        _assert_failure_result(result, code="admission_saturated")
        assert admission.calls
        assert execution.prepare_calls == []
        assert execution.launch_calls == []
        assert run_service.create_calls == []

    @pytest.mark.asyncio
    async def test_canonical_input_validation_failure_returns_typed_result_without_run(
        self,
    ) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        validation_error = InputValidationError(
            "Workflow input validation failed",
            error_code="WORKFLOW_INPUT_VALIDATION_ERROR",
            status_code=422,
            details={
                "kind": "workflow_input_validation",
                "workflow_id": WORKFLOW_ID,
                "fields": [{"field": "query", "code": "required"}],
            },
        )
        execution = _RecordingExecutionService(prepare_error=validation_error)
        run_service = _RecordingRunService()
        invoker = WorkflowRunInvoker(
            run_service=run_service,
            execution_service=execution,
            runtime_admission=_RuntimeAdmission(),
        )

        result = await invoker.invoke(_direct_api_invocation(inputs={}))

        _assert_failure_result(result, code="workflow_input_validation_failed")
        assert execution.prepare_calls == [
            {"workflow_id": WORKFLOW_ID, "inputs": {}, "branch": "main"}
        ]
        assert execution.launch_calls == []
        assert run_service.create_calls == []
        assert _field(result, "details") == validation_error.to_dict()

    @pytest.mark.asyncio
    async def test_workflow_missing_on_main_returns_typed_result_without_run(self) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        missing_error = WorkflowNotFound(f"Workflow {WORKFLOW_ID!r} not found on main")
        execution = _RecordingExecutionService(prepare_error=missing_error)
        run_service = _RecordingRunService()
        invoker = WorkflowRunInvoker(
            run_service=run_service,
            execution_service=execution,
            runtime_admission=_RuntimeAdmission(),
        )

        result = await invoker.invoke(_direct_api_invocation())

        _assert_failure_result(result, code="workflow_not_found")
        assert execution.prepare_calls == [
            {"workflow_id": WORKFLOW_ID, "inputs": {"query": "from api"}, "branch": "main"}
        ]
        assert execution.launch_calls == []
        assert run_service.create_calls == []

    @pytest.mark.asyncio
    async def test_workflow_omitting_enabled_on_main_returns_not_found_without_validation(
        self,
    ) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        omitted_enabled_workflow = WorkflowEntity(
            kind="workflow",
            id=WORKFLOW_ID,
            name="Omitted Enabled Main Workflow",
            yaml=_main_workflow_yaml(name="Omitted Enabled Main Workflow"),
        )
        execution = _RecordingExecutionService(committed_workflow=omitted_enabled_workflow)
        run_service = _RecordingRunService()
        invoker = WorkflowRunInvoker(
            run_service=run_service,
            execution_service=execution,
            runtime_admission=_RuntimeAdmission(),
        )

        result = await invoker.invoke(_direct_api_invocation())

        _assert_failure_result(result, code="workflow_not_found")
        assert execution.snapshot_calls == [{"workflow_id": WORKFLOW_ID, "branch": "main"}]
        assert execution.prepare_calls == []
        assert execution.launch_calls == []
        assert run_service.create_calls == []


class TestWorkflowRunInvokerDirectApiLaunch:
    @pytest.mark.asyncio
    async def test_success_creates_api_run_with_provenance_and_launches_saved_main(
        self,
    ) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        main_yaml = _main_workflow_yaml()
        committed_workflow = _workflow_entity(
            main_yaml,
            name="Committed Main Workflow",
            warnings=[{"code": "main-warning", "message": "from committed main"}],
        )
        prepared = _prepared_inputs(main_yaml, {"query": "from api"})
        run_service = _RecordingRunService()
        execution = _RecordingExecutionService(
            prepared=prepared,
            committed_workflow=committed_workflow,
            run_service=run_service,
        )
        invoker = WorkflowRunInvoker(
            run_service=run_service,
            execution_service=execution,
            runtime_admission=_RuntimeAdmission(),
        )

        result = await invoker.invoke(_direct_api_invocation())

        assert _field(result, "accepted") is True
        assert _field(result, "run_id") == "run_direct_invocation_created"
        assert _value(_field(result, "status")) == "pending"
        assert _field(result, "commit_sha") == COMMITTED_MAIN_SHA
        assert run_service.create_calls == [
            {
                "workflow_id": WORKFLOW_ID,
                "inputs": prepared,
                "branch": "main",
                "source": "api",
                "source_correlation_id": "corr-direct-invocation",
                "source_metadata": {
                    "entry_path": "direct_api",
                    "request_path": f"/api/workflows/{WORKFLOW_ID}/runs",
                    "client_request_id": "req-direct-invocation",
                },
                "workflow_snapshot": committed_workflow,
            }
        ]
        assert execution.prepare_calls == [
            {
                "workflow_id": WORKFLOW_ID,
                "inputs": {"query": "from api"},
                "branch": "main",
            }
        ]
        assert execution.launch_calls == [
            {
                "run_id": "run_direct_invocation_created",
                "workflow_id": WORKFLOW_ID,
                "inputs": prepared,
                "branch": "main",
            }
        ]

    @pytest.mark.asyncio
    async def test_run_metadata_schema_warnings_and_execution_use_committed_main_not_dirty_live(
        self,
    ) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        engine = _db_engine()
        main_yaml = _main_workflow_yaml(name="Committed Main Workflow")
        dirty_live = _workflow_entity(
            _dirty_workflow_yaml(),
            name="Dirty Live Workflow",
            warnings=[{"code": "dirty-warning", "message": "from live disk"}],
        )
        committed_workflow = _workflow_entity(
            main_yaml,
            name="Committed Main Workflow",
            warnings=[{"code": "main-warning", "message": "from committed main"}],
        )
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = dirty_live
        workflow_repo._get_path.return_value = f"/custom/workflows/{WORKFLOW_ID}.yaml"

        with Session(engine) as session:
            run_service = RunService(RunRepository(session), workflow_repo)
            execution = _RecordingExecutionService(
                prepared=_prepared_inputs(main_yaml, {"query": "from api"}),
                committed_workflow=committed_workflow,
                run_service=run_service,
            )
            invoker = WorkflowRunInvoker(
                run_service=run_service,
                execution_service=execution,
                runtime_admission=_RuntimeAdmission(),
            )

            result = await invoker.invoke(_direct_api_invocation())

        assert _field(result, "accepted") is True
        assert _field(result, "commit_sha") == COMMITTED_MAIN_SHA
        assert execution.prepare_calls[0]["branch"] == "main"
        assert execution.launch_calls[0]["branch"] == "main"

        with Session(engine) as session:
            runs = session.exec(select(Run)).all()

        assert len(runs) == 1
        run = runs[0]
        assert run.source == "api"
        assert run.branch == "main"
        assert run.commit_sha == COMMITTED_MAIN_SHA
        assert run.source_correlation_id == "corr-direct-invocation"
        assert run.source_metadata == {
            "entry_path": "direct_api",
            "request_path": f"/api/workflows/{WORKFLOW_ID}/runs",
            "client_request_id": "req-direct-invocation",
        }
        assert run.workflow_name == "Committed Main Workflow"
        assert run.warnings_json == [{"code": "main-warning", "message": "from committed main"}]
        assert run.workflow_input_schema is not None
        assert set(run.workflow_input_schema) == {"query", "max_results"}
        assert "debug" not in run.workflow_input_schema

    @pytest.mark.asyncio
    async def test_launch_failure_after_run_creation_returns_typed_failure_with_run_id(
        self,
    ) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        main_yaml = _main_workflow_yaml()
        run_service = _RecordingRunService()
        execution = _RecordingExecutionService(
            prepared=_prepared_inputs(main_yaml, {"query": "from api"}),
            committed_workflow=_workflow_entity(main_yaml, name="Committed Main Workflow"),
            launch_error=RuntimeError("snapshot graph failed"),
            run_service=run_service,
        )
        invoker = WorkflowRunInvoker(
            run_service=run_service,
            execution_service=execution,
            runtime_admission=_RuntimeAdmission(),
        )

        result = await invoker.invoke(_direct_api_invocation())

        _assert_failure_result(
            result,
            code="execution_launch_failed",
            run_id="run_direct_invocation_created",
        )
        assert run_service.create_calls
        assert run_service.fail_calls == [
            {"run_id": "run_direct_invocation_created", "error": "snapshot graph failed"}
        ]
        assert _value(run_service.created_run.status) == "failed"

    @pytest.mark.asyncio
    async def test_direct_api_pre_run_snapshot_work_does_not_block_event_loop(self) -> None:
        WorkflowRunInvoker, _ = _invoker_contract()
        main_yaml = _main_workflow_yaml()
        committed_workflow = _workflow_entity(main_yaml, name="Committed Main Workflow")
        prepared = _prepared_inputs(main_yaml, {"query": "from api"})
        run_service = _RecordingRunService()
        execution = _BlockingPreRunExecutionService(
            delay_seconds=0.12,
            prepared=prepared,
            committed_workflow=committed_workflow,
        )
        invoker = WorkflowRunInvoker(
            run_service=run_service,
            execution_service=execution,
            runtime_admission=_RuntimeAdmission(),
        )
        start = time.perf_counter()
        progress_at: list[float] = []

        async def record_event_loop_progress() -> None:
            await asyncio.sleep(0.01)
            progress_at.append(time.perf_counter() - start)

        invoke_task = asyncio.create_task(invoker.invoke(_direct_api_invocation()))
        progress_task = asyncio.create_task(record_event_loop_progress())

        await asyncio.gather(invoke_task, progress_task)

        assert progress_at
        assert progress_at[0] < 0.08
        assert _field(invoke_task.result(), "accepted") is True
