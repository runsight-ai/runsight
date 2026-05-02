"""End-to-end workflow input redaction smoke coverage."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunNode, RunStatus


DIRECT_QUERY = "input-redaction-user-query"
SECRET = "input-redaction-sensitive-plain-text-never-persist"
REDACTED = "[redacted]"

_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "workflow_input_redaction"


def _fixture_text(relative_path: str) -> str:
    return (_FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")


def _write_workflow_fixture(base_dir: Path, workflow_id: str) -> None:
    workflows_dir = base_dir / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / ".canvas").mkdir(parents=True, exist_ok=True)
    (workflows_dir / f"{workflow_id}.yaml").write_text(
        _fixture_text(f"custom/workflows/{workflow_id}.yaml"),
        encoding="utf-8",
    )


def _write_provider_file(base_dir: Path) -> None:
    provider_dir = base_dir / "custom" / "providers"
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / "input-redaction-fixture-provider.yaml").write_text(
        _fixture_text("custom/providers/input-redaction-fixture-provider.yaml"),
        encoding="utf-8",
    )


def _git_service_for(base_dir: Path) -> Mock:
    git_service = Mock()
    git_service.repo_path = str(base_dir)
    git_service.read_file.side_effect = lambda workflow_path, branch: (
        base_dir / workflow_path
    ).read_text(encoding="utf-8")
    git_service.get_sha.return_value = "9" * 40
    git_service.list_files.return_value = []
    return git_service


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
def base_dir(tmp_path: Path) -> Path:
    base = tmp_path / "workflow-input-redaction-workspace"
    _write_workflow_fixture(base, "input-redaction-direct")
    _write_provider_file(base)
    return base


@pytest.fixture
def app_with_real_services(db_engine, base_dir):
    from fastapi import FastAPI

    from runsight_api.core.secrets import SecretsEnvLoader
    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.data.repositories.run_repo import RunRepository
    from runsight_api.domain.errors import RunsightError
    from runsight_api.logic.services.eval_service import EvalService
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.run_service import RunService
    from runsight_api.transport.deps import (
        get_eval_service,
        get_execution_service,
        get_run_service,
    )
    from runsight_api.transport.middleware.error_handler import global_exception_handler
    from runsight_api.transport.routers import runs

    app = FastAPI()
    app.add_exception_handler(RunsightError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(runs.router, prefix="/api")

    workflow_repo = WorkflowRepository(str(base_dir))
    execution_session = Session(db_engine)
    execution_service = ExecutionService(
        run_repo=RunRepository(execution_session),
        workflow_repo=workflow_repo,
        provider_repo=FileSystemProviderRepo(base_path=str(base_dir)),
        engine=db_engine,
        secrets=SecretsEnvLoader(base_path=str(base_dir)),
        git_service=_git_service_for(base_dir),
        settings_repo=None,
    )
    app.state.execution_service = execution_service

    app.dependency_overrides[get_run_service] = lambda: RunService(
        RunRepository(Session(db_engine)), workflow_repo
    )
    app.dependency_overrides[get_execution_service] = lambda request=None: execution_service
    app.dependency_overrides[get_eval_service] = lambda: EvalService(
        RunRepository(Session(db_engine))
    )

    yield app

    app.dependency_overrides.clear()
    execution_session.close()


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
    events: list[dict[str, Any]] = []
    async for event in execution_service.subscribe_stream(run_id):
        events.append(event)
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
        "run": {field: getattr(run, field) for field in Run.model_fields},
        "nodes": [
            {
                "id": node.id,
                "output": node.output,
                "error": node.error,
                "error_traceback": node.error_traceback,
                "eval_results": node.eval_results,
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


@pytest.mark.asyncio
async def test_direct_run_redacts_sensitive_input_across_db_api_and_stream_smoke(
    app_with_real_services,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app_with_real_services),
        base_url="http://localhost",
    ) as client:
        response = await client.post(
            "/api/runs",
            json={
                "workflow_id": "input-redaction-direct",
                "branch": "main",
                "inputs": {"query": DIRECT_QUERY, "api_token": SECRET},
            },
        )
        assert response.status_code == 200, response.text
        create_payload = response.json()
        run_id = create_payload["id"]
        stream_events = await _collect_stream_events(
            app_with_real_services.state.execution_service,
            run_id,
        )
        run = await _wait_for_run_terminal(db_engine, run_id)
        public_payloads = {
            "create": create_payload,
            **await _api_payloads(client, run_id),
        }

    assert run.status == RunStatus.completed
    assert run.workflow_inputs is not None
    _assert_direct_snapshot(run.workflow_inputs)
    _assert_direct_snapshot(public_payloads["create"]["workflow_inputs"])
    _assert_direct_snapshot(public_payloads["detail"]["workflow_inputs"])

    assert run.results_json is not None
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
