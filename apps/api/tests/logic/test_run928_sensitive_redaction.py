"""RED tests for RUN-928 API sensitive-input redaction boundaries."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import SQLModel, Session, create_engine, select

from runsight_api.domain.errors import InputValidationError
from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.observers.streaming_observer import StreamingObserver
from runsight_api.logic.services.execution_service import ExecutionService


SENSITIVE_VALUE = "orchid-928-sensitive-value"
PUBLIC_VALUE = "orchid-928-public-value"
REDACTED = "[redacted]"


def _redactor(*values: object):
    from runsight_core.redaction import SensitiveValueRedactor

    redactor = SensitiveValueRedactor()
    for value in values:
        redactor.register(value)
    return redactor


def _workflow_yaml_with_sensitive_inputs() -> str:
    return """
id: run928_inputs
kind: workflow
version: "1.0"
inputs:
  private_note:
    type: string
    sensitive: true
  api_token:
    type: string
  optional_payload:
    type: json
    required: false
    default:
      mode: public
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: run928_inputs
  entry: start
  transitions:
    - from: start
      to: null
"""


def _workflow_yaml_with_sensitive_default_input() -> str:
    return """
id: run928_inputs
kind: workflow
version: "1.0"
inputs:
  private_note:
    type: string
    sensitive: true
    default: orchid-928-sensitive-value
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: run928_inputs
  entry: start
  transitions:
    - from: start
      to: null
"""


def _service(yaml: str = "") -> ExecutionService:
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id="run928_inputs",
        name="run928_inputs",
        yaml=yaml or _workflow_yaml_with_sensitive_inputs(),
        valid=True,
        validation_error=None,
    )
    workflow_repo._get_path.return_value = "/custom/workflows/run928_inputs.yaml"
    return ExecutionService(
        run_repo=Mock(),
        workflow_repo=workflow_repo,
        provider_repo=Mock(),
    )


def _db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str = "run_928_api") -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_928",
                workflow_name="redaction_api",
                status=RunStatus.running,
                task_json="{}",
            )
        )
        session.commit()


def _state_with_redactor(
    *,
    results: dict[str, object] | None = None,
    execution_log: list[dict[str, str]] | None = None,
) -> WorkflowState:
    return WorkflowState(
        input_redactor=_redactor(SENSITIVE_VALUE),
        results=results or {},
        execution_log=execution_log or [],
    )


def _log_messages(engine, run_id: str = "run_928_api") -> list[str]:
    with Session(engine) as session:
        logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
    return [entry.message for entry in logs]


def test_prepare_run_inputs_returns_values_and_runtime_redactor_for_sensitive_inputs() -> None:
    service = _service()

    prepared = service.prepare_run_inputs(
        "run928_inputs",
        {
            "private_note": SENSITIVE_VALUE,
            "api_token": PUBLIC_VALUE,
        },
        branch="main",
    )

    assert prepared.normalized_inputs == {
        "private_note": SENSITIVE_VALUE,
        "api_token": PUBLIC_VALUE,
        "optional_payload": {"mode": "public"},
    }
    assert set(prepared.normalized_inputs) == {
        "private_note",
        "api_token",
        "optional_payload",
    }
    assert not hasattr(prepared, "redacted")
    assert prepared.input_redactor.redact(
        {"private_note": SENSITIVE_VALUE, "api_token": PUBLIC_VALUE}
    ) == {"private_note": REDACTED, "api_token": PUBLIC_VALUE}


def test_secret_like_names_are_not_registered_without_sensitive_true() -> None:
    service = _service()

    prepared = service.prepare_run_inputs(
        "run928_inputs",
        {
            "private_note": SENSITIVE_VALUE,
            "api_token": PUBLIC_VALUE,
        },
        branch="main",
    )

    redacted = prepared.input_redactor.redact(
        {"private_note": SENSITIVE_VALUE, "api_token": PUBLIC_VALUE}
    )

    assert redacted["private_note"] == REDACTED
    assert redacted["api_token"] == PUBLIC_VALUE


def test_prepare_run_inputs_rejects_sensitive_defaults_before_normalization() -> None:
    service = _service(yaml=_workflow_yaml_with_sensitive_default_input())

    with pytest.raises(
        InputValidationError, match="sensitive workflow inputs cannot declare a default"
    ):
        service.prepare_run_inputs("run928_inputs", {}, branch="main")


@pytest.mark.asyncio
async def test_launch_execution_keeps_prepared_redactor_for_plain_mapping_inputs() -> None:
    service = _service()
    prepared = service.prepare_run_inputs(
        "run928_inputs",
        {
            "private_note": SENSITIVE_VALUE,
            "api_token": PUBLIC_VALUE,
        },
        branch="main",
    )
    captured: dict[str, object] = {}

    async def _capture_state(state, **kwargs):
        captured["state"] = state
        captured["inputs"] = kwargs["inputs"]
        return state

    mock_wf = Mock()
    mock_wf.run = AsyncMock(side_effect=_capture_state)

    with patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse:
        mock_parse.return_value = mock_wf

        try:
            await service.launch_execution(
                "run_928_launch",
                "run928_inputs",
                dict(prepared.normalized_inputs),
                branch="main",
            )
        except (TypeError, ValueError) as exc:
            assert "PreparedRunInputs" in str(exc) or "prepared" in str(exc)
            return

        await asyncio.sleep(0.1)

    assert "state" in captured
    assert captured["inputs"] == prepared.normalized_inputs
    sample = {"private_note": SENSITIVE_VALUE, "api_token": PUBLIC_VALUE}
    assert captured["state"].input_redactor.redact(sample) == prepared.input_redactor.redact(sample)


def test_execution_observer_redacts_node_output_and_execution_log_before_persisting() -> None:
    engine = _db_engine()
    _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_928_api")
    observer.on_block_start("wf", "emit_secret", "CodeBlock")
    state = _state_with_redactor(
        results={
            "emit_secret": BlockResult(
                output=json.dumps(
                    {
                        "private_note": SENSITIVE_VALUE,
                        "public_note": PUBLIC_VALUE,
                    }
                )
            )
        },
        execution_log=[{"role": "system", "content": f"raw execution detail: {SENSITIVE_VALUE}"}],
    )

    observer.on_block_complete("wf", "emit_secret", "CodeBlock", 0.1, state)

    with Session(engine) as session:
        node = session.get(RunNode, "run_928_api:emit_secret")
    assert node is not None
    assert SENSITIVE_VALUE not in node.output
    assert REDACTED in node.output
    assert PUBLIC_VALUE in node.output
    assert SENSITIVE_VALUE not in "\n".join(_log_messages(engine))


def test_execution_observer_redacts_results_serialization_before_run_persistence() -> None:
    engine = _db_engine()
    _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_928_api")
    state = _state_with_redactor(
        results={
            "final": BlockResult(
                output=json.dumps(
                    {
                        "private_note": SENSITIVE_VALUE,
                        "public_note": PUBLIC_VALUE,
                    }
                )
            )
        }
    )

    observer.on_workflow_complete("wf", state, 0.2)

    with Session(engine) as session:
        run = session.get(Run, "run_928_api")
    assert run is not None
    assert run.results_json is not None
    assert SENSITIVE_VALUE not in run.results_json
    assert REDACTED in run.results_json
    assert PUBLIC_VALUE in run.results_json


def test_execution_observer_redacts_error_and_traceback_when_state_is_available() -> None:
    engine = _db_engine()
    _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_928_api")
    observer.on_block_start("wf", "fail_secret", "CodeBlock")
    state = _state_with_redactor()

    try:
        raise RuntimeError(f"failed while handling {SENSITIVE_VALUE}")
    except RuntimeError as exc:
        observer.on_block_error("wf", "fail_secret", "CodeBlock", 0.1, exc, state=state)

    with Session(engine) as session:
        node = session.get(RunNode, "run_928_api:fail_secret")
    assert node is not None
    assert SENSITIVE_VALUE not in (node.error or "")
    assert SENSITIVE_VALUE not in (node.error_traceback or "")
    assert REDACTED in (node.error or "")
    assert REDACTED in (node.error_traceback or "")
    assert SENSITIVE_VALUE not in "\n".join(_log_messages(engine))


def test_streaming_observer_redacts_error_sse_payload_when_state_is_available() -> None:
    observer = StreamingObserver(run_id="run_928_api")
    state = _state_with_redactor()

    observer.on_block_error(
        "wf",
        "fail_secret",
        "CodeBlock",
        0.1,
        RuntimeError(f"failed with {SENSITIVE_VALUE}"),
        state=state,
    )

    queued = observer.queue.get_nowait()
    payload = json.dumps(queued, default=str)
    assert queued["event"] == "node_failed"
    assert SENSITIVE_VALUE not in payload
    assert REDACTED in payload


def test_streaming_observer_redacts_workflow_error_sse_payload_when_state_is_available() -> None:
    observer = StreamingObserver(run_id="run_928_api")
    state = _state_with_redactor()

    observer.on_workflow_error(
        "wf",
        RuntimeError(f"workflow failed with {SENSITIVE_VALUE}"),
        0.2,
        state=state,
    )

    queued = observer.queue.get_nowait()
    payload = json.dumps(queued, default=str)
    assert queued["event"] == "run_failed"
    assert SENSITIVE_VALUE not in payload
    assert REDACTED in payload
