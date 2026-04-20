"""Purple integration tests for RUN-929 workflow input snapshots and redaction."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunNode, RunStatus


DIRECT_QUERY = "run929-user-query"
CHILD_QUERY = "run929-child-query"
SECRET = "run929-sensitive-plain-text-never-persist"
REDACTED = "[redacted]"


DIRECT_WORKFLOW_YAML = """\
id: run929-direct
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
  limit:
    type: number
    required: false
    default: 5
  api_token:
    type: string
    sensitive: true
config:
  model_name: gpt-4o
souls:
  bootstrap:
    id: bootstrap
    kind: soul
    name: Bootstrap
    role: Bootstrap
    system_prompt: Parser bootstrap model holder.
    provider: openai
    model_name: gpt-4o
blocks:
  expose:
    type: code
    timeout_seconds: 5
    inputs:
      query:
        from: workflow.query
      token:
        from: workflow.api_token
    code: |
      import time
      def main(data):
          time.sleep(0.25)
          return {"ok": True, "echoed_token": data["token"]}
workflow:
  name: run929_direct
  entry: expose
  transitions:
    - from: expose
      to: null
"""


FAILING_WORKFLOW_YAML = """\
id: run929-failing
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
  api_token:
    type: string
    sensitive: true
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: Check the request.
    provider: openai
    model_name: gpt-4o
blocks:
  fail_with_secret:
    type: linear
    soul_ref: analyst
    inputs:
      token:
        from: workflow.api_token
workflow:
  name: run929_failing
  entry: fail_with_secret
  transitions:
    - from: fail_with_secret
      to: null
"""


PARENT_WORKFLOW_YAML = """\
id: run929-parent
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
  api_token:
    type: string
    sensitive: true
config:
  model_name: gpt-4o
souls:
  bootstrap:
    id: bootstrap
    kind: soul
    name: Bootstrap
    role: Bootstrap
    system_prompt: Parser bootstrap model holder.
    provider: openai
    model_name: gpt-4o
blocks:
  invoke_child:
    type: workflow
    workflow_ref: run929-child
    inputs:
      child_query: workflow.query
      child_token: workflow.api_token
workflow:
  name: run929_parent
  entry: invoke_child
  transitions:
    - from: invoke_child
      to: null
"""


CHILD_WORKFLOW_YAML = """\
id: run929-child
kind: workflow
version: "1.0"
inputs:
  child_query:
    type: string
  child_mode:
    type: string
    required: false
    default: summary
  child_token:
    type: string
    sensitive: true
config:
  model_name: gpt-4o
souls:
  bootstrap:
    id: bootstrap
    kind: soul
    name: Bootstrap
    role: Bootstrap
    system_prompt: Parser bootstrap model holder.
    provider: openai
    model_name: gpt-4o
blocks:
  child_echo:
    type: code
    timeout_seconds: 5
    inputs:
      query:
        from: workflow.child_query
      token:
        from: workflow.child_token
    code: |
      import time
      def main(data):
          time.sleep(0.25)
          return {
              "child_query": data["query"],
              "child_token_echo": data["token"],
          }
workflow:
  name: run929_child
  entry: child_echo
  transitions:
    - from: child_echo
      to: null
"""


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    workflows_dir = base_dir / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / ".canvas").mkdir(parents=True, exist_ok=True)
    (workflows_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


def _write_provider_file(base_dir: Path) -> None:
    provider_dir = base_dir / "custom" / "providers"
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / "openai.yaml").write_text(
        "\n".join(
            [
                "id: openai",
                "kind: provider",
                "name: openai",
                "type: openai",
                "api_key: ${OPENAI_API_KEY}",
                "is_active: true",
                "models:",
                "  - gpt-4o",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_secrets_file(base_dir: Path) -> None:
    secrets_dir = base_dir / ".runsight"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "secrets.env").write_text(
        "OPENAI_API_KEY=sk-run929-fake-test-key\n",
        encoding="utf-8",
    )


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def base_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _write_workflow_file(base, "run929-direct", DIRECT_WORKFLOW_YAML)
        _write_workflow_file(base, "run929-failing", FAILING_WORKFLOW_YAML)
        _write_workflow_file(base, "run929-parent", PARENT_WORKFLOW_YAML)
        _write_workflow_file(base, "run929-child", CHILD_WORKFLOW_YAML)
        _write_provider_file(base)
        _write_secrets_file(base)
        yield base


@pytest.fixture
def app_with_real_services(db_engine, base_dir):
    from fastapi import FastAPI

    from runsight_api.core.secrets import SecretsEnvLoader
    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.data.repositories.run_repo import RunRepository
    from runsight_api.logic.services.eval_service import EvalService
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.run_service import RunService
    from runsight_api.domain.errors import RunsightError
    from runsight_api.transport.middleware.error_handler import global_exception_handler
    from runsight_api.transport.deps import (
        get_eval_service,
        get_execution_service,
        get_run_service,
    )
    from runsight_api.transport.routers import runs

    app = FastAPI()
    app.add_exception_handler(RunsightError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(runs.router, prefix="/api")

    workflow_repo = WorkflowRepository(str(base_dir))
    execution_service = ExecutionService(
        run_repo=None,
        workflow_repo=workflow_repo,
        provider_repo=FileSystemProviderRepo(base_path=str(base_dir)),
        engine=db_engine,
        secrets=SecretsEnvLoader(base_path=str(base_dir)),
        settings_repo=None,
    )
    app.state.execution_service = execution_service

    def _get_run_service():
        return RunService(RunRepository(Session(db_engine)), workflow_repo)

    def _get_execution_service(request=None):
        return execution_service

    def _get_eval_service():
        return EvalService(RunRepository(Session(db_engine)))

    app.dependency_overrides[get_run_service] = _get_run_service
    app.dependency_overrides[get_execution_service] = _get_execution_service
    app.dependency_overrides[get_eval_service] = _get_eval_service

    yield app

    app.dependency_overrides.clear()


async def _wait_for_run_terminal(engine, run_id: str, timeout: float = 5.0) -> Run:
    terminal = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run is not None and run.status in terminal:
                return run
        await asyncio.sleep(0.05)

    with Session(engine) as session:
        run = session.get(Run, run_id)
    assert run is not None, f"Run {run_id} was not created"
    return run


async def _collect_stream_events(execution_service: Any, run_id: str) -> list[dict[str, Any]]:
    deadline = asyncio.get_event_loop().time() + 2.0
    while run_id not in getattr(execution_service, "_observers", {}):
        if asyncio.get_event_loop().time() >= deadline:
            return []
        await asyncio.sleep(0.01)

    events: list[dict[str, Any]] = []
    try:
        async with asyncio.timeout(3.0):
            async for event in execution_service.subscribe_stream(run_id):
                events.append(event)
    except TimeoutError:
        pass
    return events


def _json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def _assert_secret_absent(label: str, value: Any) -> None:
    payload = value if isinstance(value, str) else _json(value)
    assert SECRET not in payload, f"{label} leaked sensitive plaintext: {payload}"


def _db_surfaces(engine, run_id: str) -> dict[str, Any]:
    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run is not None
        nodes = list(session.exec(select(RunNode).where(RunNode.run_id == run_id)).all())
        logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())

    return {
        "run": {
            "id": run.id,
            "workflow_inputs": run.workflow_inputs,
            "workflow_input_schema": run.workflow_input_schema,
            "results_json": run.results_json,
            "error": run.error,
            "error_traceback": run.error_traceback,
        },
        "nodes": [
            {
                "id": node.id,
                "output": node.output,
                "error": node.error,
                "error_traceback": node.error_traceback,
                "eval_results": node.eval_results,
                "child_run_id": node.child_run_id,
            }
            for node in nodes
        ],
        "logs": [{"level": log.level, "message": log.message} for log in logs],
    }


async def _api_payloads(client: Any, run_id: str) -> dict[str, Any]:
    detail = await client.get(f"/api/runs/{run_id}")
    nodes = await client.get(f"/api/runs/{run_id}/nodes")
    audit = await client.get(f"/api/runs/{run_id}/context-audit")

    assert detail.status_code == 200, detail.text
    assert nodes.status_code == 200, nodes.text
    assert audit.status_code == 200, audit.text

    return {
        "detail": detail.json(),
        "nodes": nodes.json(),
        "context_audit": audit.json(),
    }


def _assert_direct_snapshot(workflow_inputs: dict[str, Any]) -> None:
    assert workflow_inputs["query"] == {
        "type": "string",
        "sensitive": False,
        "source": "provided",
        "value": DIRECT_QUERY,
    }
    assert workflow_inputs["limit"] == {
        "type": "number",
        "sensitive": False,
        "source": "defaulted",
        "value": 5,
    }
    assert workflow_inputs["api_token"] == {
        "type": "string",
        "sensitive": True,
        "source": "provided",
    }
    assert "value" not in workflow_inputs["api_token"]
    assert "redacted" not in workflow_inputs["api_token"]


@pytest.mark.asyncio
async def test_direct_run_snapshots_inputs_without_persisting_or_streaming_plaintext(
    app_with_real_services,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app_with_real_services),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/runs",
            json={
                "workflow_id": "run929-direct",
                "inputs": {"query": DIRECT_QUERY, "api_token": SECRET},
            },
        )
        assert response.status_code == 200, response.text
        run_id = response.json()["id"]
        stream_events = await _collect_stream_events(
            app_with_real_services.state.execution_service,
            run_id,
        )
        run = await _wait_for_run_terminal(db_engine, run_id)
        public_payloads = await _api_payloads(client, run_id)

    assert run.status == RunStatus.completed
    assert run.workflow_inputs is not None
    _assert_direct_snapshot(run.workflow_inputs)
    _assert_direct_snapshot(public_payloads["detail"]["workflow_inputs"])

    assert run.results_json is not None
    results = json.loads(run.results_json)
    assert "workflow" not in results
    assert DIRECT_QUERY not in run.results_json
    assert REDACTED in run.results_json

    assert {event["event"] for event in stream_events} >= {
        "context_resolution",
        "run_completed",
    }
    for label, surface in {
        "database persistence": _db_surfaces(db_engine, run_id),
        "public API payloads": public_payloads,
        "stream events": stream_events,
    }.items():
        _assert_secret_absent(label, surface)


@pytest.mark.asyncio
async def test_failed_run_redacts_sensitive_input_across_error_surfaces(
    app_with_real_services,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async def _raise_secret_error(*args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(0.25)
        raise RuntimeError(f"provider failed with {SECRET}")

    async with AsyncClient(
        transport=ASGITransport(app=app_with_real_services),
        base_url="http://test",
    ) as client:
        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            side_effect=_raise_secret_error,
        ):
            response = await client.post(
                "/api/runs",
                json={
                    "workflow_id": "run929-failing",
                    "inputs": {"query": DIRECT_QUERY, "api_token": SECRET},
                },
            )
            assert response.status_code == 200, response.text
            run_id = response.json()["id"]
            stream_events = await _collect_stream_events(
                app_with_real_services.state.execution_service,
                run_id,
            )
            run = await _wait_for_run_terminal(db_engine, run_id)
        public_payloads = await _api_payloads(client, run_id)

    assert run.status == RunStatus.failed
    assert run.error is not None
    assert REDACTED in run.error
    assert run.error_traceback is not None
    assert REDACTED in run.error_traceback
    assert {event["event"] for event in stream_events} >= {
        "context_resolution",
        "node_failed",
        "run_failed",
    }

    with Session(db_engine) as session:
        failed_node = session.get(RunNode, f"{run_id}:fail_with_secret")
    assert failed_node is not None
    assert failed_node.error is not None and REDACTED in failed_node.error
    assert failed_node.error_traceback is not None and REDACTED in failed_node.error_traceback

    for label, surface in {
        "database persistence": _db_surfaces(db_engine, run_id),
        "public API payloads": public_payloads,
        "stream events": stream_events,
    }.items():
        _assert_secret_absent(label, surface)


@pytest.mark.asyncio
async def test_child_run_records_own_safe_snapshot_and_inherits_redaction_context(
    app_with_real_services,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app_with_real_services),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/runs",
            json={
                "workflow_id": "run929-parent",
                "inputs": {"query": CHILD_QUERY, "api_token": SECRET},
            },
        )
        assert response.status_code == 200, response.text
        parent_run_id = response.json()["id"]
        stream_events = await _collect_stream_events(
            app_with_real_services.state.execution_service,
            parent_run_id,
        )
        parent_run = await _wait_for_run_terminal(db_engine, parent_run_id)

        with Session(db_engine) as session:
            parent_node = session.get(RunNode, f"{parent_run_id}:invoke_child")
            assert parent_node is not None
            child_run_id = parent_node.child_run_id
            assert child_run_id is not None
        child_run = await _wait_for_run_terminal(db_engine, child_run_id)

        parent_payloads = await _api_payloads(client, parent_run_id)
        child_payloads = await _api_payloads(client, child_run_id)

    assert parent_run.status == RunStatus.completed
    assert child_run.status == RunStatus.completed
    assert child_run.workflow_id == "run929-child"
    assert child_run.parent_run_id == parent_run_id
    assert child_run.workflow_inputs == {
        "child_query": {
            "type": "string",
            "sensitive": False,
            "source": "provided",
            "value": CHILD_QUERY,
        },
        "child_mode": {
            "type": "string",
            "sensitive": False,
            "source": "defaulted",
            "value": "summary",
        },
        "child_token": {
            "type": "string",
            "sensitive": True,
            "source": "provided",
        },
    }
    assert child_run.workflow_input_schema is not None
    assert set(child_run.workflow_input_schema) == {
        "child_query",
        "child_mode",
        "child_token",
    }
    assert "api_token" not in child_run.workflow_inputs
    assert "value" not in child_run.workflow_inputs["child_token"]
    assert "redacted" not in child_run.workflow_inputs["child_token"]

    child_results = child_run.results_json or ""
    assert CHILD_QUERY in child_results
    assert REDACTED in child_results
    assert SECRET not in child_results

    assert any(event["event"] == "child_run_completed" for event in stream_events)
    for label, surface in {
        "parent database persistence": _db_surfaces(db_engine, parent_run_id),
        "child database persistence": _db_surfaces(db_engine, child_run.id),
        "parent public API payloads": parent_payloads,
        "child public API payloads": child_payloads,
        "stream events": stream_events,
    }.items():
        _assert_secret_absent(label, surface)


@pytest.mark.asyncio
async def test_invalid_workflow_input_returns_422_before_run_or_snapshot_creation(
    app_with_real_services,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app_with_real_services),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/runs",
            json={
                "workflow_id": "run929-direct",
                "inputs": {"query": 123, "api_token": SECRET},
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
    assert payload["details"]["workflow_id"] == "run929-direct"
    assert payload["details"]["fields"][0]["field"] == "query"
    assert payload["details"]["fields"][0]["code"] == "type_mismatch"
    _assert_secret_absent("validation response", payload)

    with Session(db_engine) as session:
        runs = list(session.exec(select(Run)).all())

    assert runs == []
