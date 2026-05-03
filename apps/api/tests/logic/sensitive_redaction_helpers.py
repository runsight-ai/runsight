"""Shared sensitive-redaction test builders for API logic suites."""

from __future__ import annotations

from queue import Queue
from typing import Any
from unittest.mock import Mock

from runsight_core.redaction import SensitiveValueRedactor
from runsight_core.state import WorkflowState
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.execution_service import ExecutionService

SENSITIVE_VALUE = "orchid-sensitive-value"
PUBLIC_VALUE = "orchid-public-value"
REDACTED = "[redacted]"


def make_sensitive_redactor(*values: object) -> SensitiveValueRedactor:
    redactor = SensitiveValueRedactor()
    for value in values:
        redactor.register(value)
    return redactor


def sensitive_workflow_yaml() -> str:
    return """
id: sensitive_inputs_workflow
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
  name: sensitive_inputs_workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def sensitive_default_workflow_yaml() -> str:
    return """
id: sensitive_inputs_workflow
kind: workflow
version: "1.0"
inputs:
  private_note:
    type: string
    sensitive: true
    default: orchid-sensitive-value
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: sensitive_inputs_workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def sensitive_non_string_workflow_yaml() -> str:
    return """
id: sensitive_inputs_workflow
kind: workflow
version: "1.0"
inputs:
  private_limit:
    type: number
    sensitive: true
  private_enabled:
    type: boolean
    sensitive: true
  private_payload:
    type: json
    sensitive: true
  private_values:
    type: array
    sensitive: true
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: sensitive_inputs_workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def mixed_structured_sensitive_workflow_yaml() -> str:
    return """
id: sensitive_inputs_workflow
kind: workflow
version: "1.0"
inputs:
  credentials:
    type: json
    sensitive: true
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: sensitive_inputs_workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def make_sensitive_execution_service(yaml: str = "") -> ExecutionService:
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id="sensitive_inputs_workflow",
        name="sensitive_inputs_workflow",
        yaml=yaml or sensitive_workflow_yaml(),
        valid=True,
        validation_error=None,
    )
    workflow_repo._get_path.return_value = "/tmp/runsight-tests/sensitive_inputs_workflow.yaml"
    return ExecutionService(
        run_repo=Mock(),
        workflow_repo=workflow_repo,
        provider_repo=Mock(),
    )


def make_sensitive_db_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def make_sensitive_eval_db_engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def seed_sensitive_run(engine: Engine, run_id: str = "run_sensitive_api") -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_sensitive_redaction",
                workflow_name="redaction_api",
                status=RunStatus.running,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()


def seed_sensitive_eval_run(
    engine: Engine,
    run_id: str = "run_sensitive_eval",
    block_id: str = "block_a",
) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_sensitive_redaction",
                workflow_name="redaction_api",
                status=RunStatus.running,
                task_json="{}",
                branch="main",
            )
        )
        session.add(
            RunNode(
                id=f"{run_id}:{block_id}",
                run_id=run_id,
                node_id=block_id,
                block_type="LinearBlock",
                status="completed",
            )
        )
        session.commit()


def make_sensitive_state(
    *,
    results: dict[str, object] | None = None,
    execution_log: list[dict[str, str]] | None = None,
) -> WorkflowState:
    return WorkflowState(
        input_redactor=make_sensitive_redactor(SENSITIVE_VALUE),
        results=results or {},
        execution_log=execution_log or [],
    )


def make_sensitive_sse_queue() -> Queue[Any]:
    return Queue()


def collect_sensitive_log_messages(
    engine: Engine,
    run_id: str = "run_sensitive_api",
) -> list[str]:
    with Session(engine) as session:
        logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
    return [entry.message for entry in logs]
