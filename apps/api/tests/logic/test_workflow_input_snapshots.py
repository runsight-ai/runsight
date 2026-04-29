"""Persist normalized workflow input snapshots on runs."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.execution_service import (
    _prepare_run_inputs_from_schema,
    _workflow_input_schema_from_yaml,
)
from runsight_api.logic.services.run_service import RunService


def _db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _workflow_yaml_v1() -> str:
    return """
id: workflow_input_snapshot
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
  max_results:
    type: number
    required: false
    default: 10
  api_token:
    type: string
    sensitive: true
  payload:
    type: json
    required: false
  tags:
    type: array
    required: false
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: workflow_input_snapshot
  entry: start
  transitions:
    - from: start
      to: null
"""


def _workflow_yaml_v2() -> str:
    return """
id: workflow_input_snapshot
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
  max_results:
    type: number
    required: false
    default: 25
  api_token:
    type: string
    sensitive: true
  payload:
    type: json
    required: false
  tags:
    type: array
    required: false
  debug:
    type: boolean
    required: false
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: workflow_input_snapshot
  entry: start
  transitions:
    - from: start
      to: null
"""


def _workflow_entity(yaml_text: str) -> WorkflowEntity:
    return WorkflowEntity(
        kind="workflow",
        id="workflow_input_snapshot",
        name="workflow_input_snapshot",
        yaml=yaml_text,
        valid=True,
        validation_error=None,
    )


def _service(session: Session, workflow_entity: WorkflowEntity) -> RunService:
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = workflow_entity
    workflow_repo._get_path.return_value = "/custom/workflows/workflow_input_snapshot.yaml"
    return RunService(RunRepository(session), workflow_repo)


def _prepared_inputs(yaml_text: str, inputs: dict[str, object]):
    return _prepare_run_inputs_from_schema(
        "workflow_input_snapshot",
        _workflow_input_schema_from_yaml("workflow_input_snapshot", yaml_text),
        inputs,
    )


def _expected_workflow_inputs() -> dict[str, dict[str, object]]:
    return {
        "query": {
            "type": "string",
            "sensitive": False,
            "source": "provided",
            "value": "search runs",
        },
        "max_results": {
            "type": "number",
            "sensitive": False,
            "source": "defaulted",
            "value": 10,
        },
        "api_token": {
            "type": "string",
            "sensitive": True,
            "source": "provided",
        },
        "payload": {
            "type": "json",
            "sensitive": False,
            "source": "provided",
            "value": {"region": "eu", "filters": [{"name": "tier", "value": 1}]},
        },
        "tags": {
            "type": "array",
            "sensitive": False,
            "source": "provided",
            "value": ["support", "vip"],
        },
    }


def _expected_workflow_input_schema() -> dict[str, dict[str, object]]:
    return {
        "query": {
            "type": "string",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": False,
        },
        "max_results": {
            "type": "number",
            "required": False,
            "default": 10,
            "description": None,
            "sensitive": False,
        },
        "api_token": {
            "type": "string",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": True,
        },
        "payload": {
            "type": "json",
            "required": False,
            "default": None,
            "description": None,
            "sensitive": False,
        },
        "tags": {
            "type": "array",
            "required": False,
            "default": None,
            "description": None,
            "sensitive": False,
        },
    }


class TestRunServiceWorkflowInputSnapshots:
    def test_create_run_persists_defaulted_non_sensitive_and_sensitive_input_snapshot(self):
        engine = _db_engine()
        workflow_entity = _workflow_entity(_workflow_yaml_v1())
        raw_inputs = {
            "query": "search runs",
            "api_token": "secret-token-snapshot",
            "payload": {"region": "eu", "filters": [{"name": "tier", "value": 1}]},
            "tags": ["support", "vip"],
        }
        prepared_inputs = _prepared_inputs(workflow_entity.yaml, raw_inputs)

        with Session(engine) as session:
            service = _service(session, workflow_entity)
            run = service.create_run(
                "workflow_input_snapshot", prepared_inputs, source="manual", branch="main"
            )

        assert getattr(run, "workflow_inputs", None) == _expected_workflow_inputs()
        assert getattr(run, "workflow_input_schema", None) == _expected_workflow_input_schema()
        assert "redacted" not in getattr(run, "workflow_inputs", {}).get("api_token", {})
        assert "value" not in getattr(run, "workflow_inputs", {}).get("api_token", {})

        with Session(engine) as session:
            loaded = session.get(Run, run.id)

        assert loaded is not None
        assert getattr(loaded, "workflow_inputs", None) == _expected_workflow_inputs()
        assert getattr(loaded, "workflow_input_schema", None) == _expected_workflow_input_schema()

    def test_persisted_workflow_input_schema_stays_fixed_after_yaml_changes(self):
        engine = _db_engine()
        workflow_entity = _workflow_entity(_workflow_yaml_v1())
        raw_inputs = {
            "query": "search runs",
            "api_token": "secret-token-snapshot",
            "payload": {"region": "eu", "filters": [{"name": "tier", "value": 1}]},
            "tags": ["support", "vip"],
        }
        prepared_inputs = _prepared_inputs(workflow_entity.yaml, raw_inputs)

        with Session(engine) as session:
            service = _service(session, workflow_entity)
            run = service.create_run(
                "workflow_input_snapshot", prepared_inputs, source="manual", branch="main"
            )

        workflow_entity.yaml = _workflow_yaml_v2()

        with Session(engine) as session:
            loaded = session.get(Run, run.id)

        assert loaded is not None
        schema_snapshot = getattr(loaded, "workflow_input_schema", None)
        assert schema_snapshot == _expected_workflow_input_schema()
        assert schema_snapshot is not None
        assert schema_snapshot["max_results"]["default"] == 10
        assert "debug" not in schema_snapshot
        assert getattr(loaded, "workflow_inputs", None)["max_results"]["value"] == 10

    def test_create_run_rejects_raw_mapping_inputs_instead_of_reconstructing_snapshots(self):
        engine = _db_engine()
        workflow_entity = _workflow_entity(_workflow_yaml_v1())

        with Session(engine) as session:
            service = _service(session, workflow_entity)
            with pytest.raises(TypeError, match="PreparedRunInputs"):
                service.create_run(
                    "workflow_input_snapshot",
                    {"query": "search runs", "api_token": "secret-token-snapshot"},
                    source="manual",
                    branch="main",
                )

        with Session(engine) as session:
            assert session.exec(select(Run)).all() == []
