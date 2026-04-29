"""Integration tests for workflow input snapshots and redaction."""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunNode, RunStatus


DIRECT_QUERY = "input-redaction-user-query"
CHILD_QUERY = "input-redaction-child-query"
CONFLICT_QUERY = "input-redaction-conflicting-results-workflow-query"
CONFLICT_SUBMITTED_QUERY = "input-redaction-workflow-state-source-query"
SECRET = "input-redaction-sensitive-plain-text-never-persist"
INVALID_QUERY_MARKER = "input-redaction-invalid-query-echo"
REDACTED = "[redacted]"


_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "workflow_input_redaction"


def _fixture_text(relative_path: str) -> str:
    return (_FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")


DIRECT_WORKFLOW_YAML = _fixture_text("custom/workflows/input-redaction-direct.yaml")
FAILING_WORKFLOW_YAML = _fixture_text("custom/workflows/input-redaction-failing.yaml")
PARENT_WORKFLOW_YAML = _fixture_text("custom/workflows/input-redaction-parent.yaml")
CHILD_WORKFLOW_YAML = _fixture_text("custom/workflows/input-redaction-child.yaml")
CONFLICTING_WORKFLOW_RESULT_YAML = _fixture_text(
    "custom/workflows/input-redaction-conflicting-workflow-result.yaml"
)
CONFLICT_SEED_WORKFLOW_YAML = _fixture_text("custom/workflows/input-redaction-conflict-seed.yaml")
LEGACY_INTERFACE_TARGET_YAML = _fixture_text(
    "custom/workflows/input-redaction-legacy-interface.yaml"
)
OPENAI_PROVIDER_YAML = _fixture_text("custom/providers/openai.yaml")


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    workflows_dir = base_dir / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / ".canvas").mkdir(parents=True, exist_ok=True)
    (workflows_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


def _write_provider_file(base_dir: Path) -> None:
    provider_dir = base_dir / "custom" / "providers"
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / "openai.yaml").write_text(OPENAI_PROVIDER_YAML, encoding="utf-8")


def _write_secrets_file(base_dir: Path) -> None:
    secrets_dir = base_dir / ".runsight"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "secrets.env").write_text(
        "OPENAI_API_KEY=sk-input-redaction-fake-test-key\n",
        encoding="utf-8",
    )


def _git_service_for(base_dir: Path) -> Mock:
    git_service = Mock()
    git_service.repo_path = str(base_dir)

    def _list_files(branch: str, path_prefix: str) -> list[str]:
        del branch
        root = base_dir / path_prefix.rstrip("/")
        if not root.exists():
            return []
        return sorted(
            path.relative_to(base_dir).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".yaml", ".yml"}
        )

    def _read_file(workflow_path: str, branch: str) -> str:
        path = Path(workflow_path)
        if not path.is_absolute():
            path = base_dir / workflow_path
        return path.read_text(encoding="utf-8")

    git_service.list_files.side_effect = _list_files
    git_service.read_file.side_effect = _read_file
    git_service.get_sha.side_effect = lambda branch, workflow_path: "9" * 40
    return git_service


def _init_git_repo(base_dir: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=base_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@runsight.dev"],
        cwd=base_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Runsight Tests"],
        cwd=base_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=base_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed workflows"],
        cwd=base_dir,
        check=True,
        capture_output=True,
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
        _write_workflow_file(base, "input-redaction-direct", DIRECT_WORKFLOW_YAML)
        _write_workflow_file(base, "input-redaction-failing", FAILING_WORKFLOW_YAML)
        _write_workflow_file(base, "input-redaction-parent", PARENT_WORKFLOW_YAML)
        _write_workflow_file(base, "input-redaction-child", CHILD_WORKFLOW_YAML)
        _write_workflow_file(
            base,
            "input-redaction-conflicting-workflow-result",
            CONFLICTING_WORKFLOW_RESULT_YAML,
        )
        _write_workflow_file(base, "input-redaction-conflict-seed", CONFLICT_SEED_WORKFLOW_YAML)
        _write_provider_file(base)
        _write_secrets_file(base)
        _init_git_repo(base)
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
    git_service = _git_service_for(base_dir)
    execution_session = Session(db_engine)
    execution_service = ExecutionService(
        run_repo=RunRepository(execution_session),
        workflow_repo=workflow_repo,
        provider_repo=FileSystemProviderRepo(base_path=str(base_dir)),
        engine=db_engine,
        secrets=SecretsEnvLoader(base_path=str(base_dir)),
        git_service=git_service,
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
    deadline = asyncio.get_event_loop().time() + 2.0
    while execution_service._streams.get(run_id) is None:
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


def _decoded_output(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _assert_secret_absent(label: str, value: Any) -> None:
    payload = value if isinstance(value, str) else _json(value)
    assert SECRET not in payload, f"{label} leaked sensitive plaintext: {payload}"


def _db_surfaces(engine, run_id: str) -> dict[str, Any]:
    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run is not None
        run_surface = {field: getattr(run, field) for field in Run.model_fields}
        nodes = list(session.exec(select(RunNode).where(RunNode.run_id == run_id)).all())
        logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())

    return {
        "run": run_surface,
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


def _assert_parent_snapshot(workflow_inputs: dict[str, Any]) -> None:
    assert workflow_inputs["query"] == {
        "type": "string",
        "sensitive": False,
        "source": "provided",
        "value": CHILD_QUERY,
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
                    "workflow_id": "input-redaction-failing",
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
                "workflow_id": "input-redaction-parent",
                "branch": "main",
                "inputs": {"query": CHILD_QUERY, "api_token": SECRET},
            },
        )
        assert response.status_code == 200, response.text
        parent_create_payload = response.json()
        parent_run_id = parent_create_payload["id"]
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

        parent_payloads = {
            "create": parent_create_payload,
            **await _api_payloads(client, parent_run_id),
        }
        child_payloads = await _api_payloads(client, child_run_id)

    assert parent_run.status == RunStatus.completed
    _assert_parent_snapshot(parent_payloads["create"]["workflow_inputs"])
    _assert_parent_snapshot(parent_payloads["detail"]["workflow_inputs"])
    assert child_run.status == RunStatus.completed
    assert child_run.workflow_id == "input-redaction-child"
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
async def test_workflow_input_resolution_ignores_conflicting_results_workflow_facade(
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
                "workflow_id": "input-redaction-conflicting-workflow-result",
                "branch": "main",
                "inputs": {"query": CONFLICT_SUBMITTED_QUERY, "api_token": SECRET},
            },
        )
        assert response.status_code == 200, response.text
        create_payload = response.json()
        run_id = create_payload["id"]
        run = await _wait_for_run_terminal(db_engine, run_id)
        public_payloads = {
            "create": create_payload,
            **await _api_payloads(client, run_id),
        }

    assert run.status == RunStatus.completed
    assert run.results_json is not None
    results = json.loads(run.results_json)

    workflow_result = _decoded_output(results["workflow"]["output"])
    assert workflow_result["query"] == CONFLICT_QUERY

    consumed = _decoded_output(results["consume"]["output"])
    assert consumed == {
        "source": "workflow_inputs",
        "observed": CONFLICT_SUBMITTED_QUERY,
    }
    assert consumed["observed"] != workflow_result["query"]

    assert results["workflow"]["output"] != json.dumps(
        {"query": CONFLICT_SUBMITTED_QUERY, "api_token": SECRET},
        sort_keys=True,
    )
    for label, surface in {
        "database persistence": _db_surfaces(db_engine, run_id),
        "public API payloads": public_payloads,
    }.items():
        _assert_secret_absent(label, surface)


@pytest.mark.asyncio
async def test_legacy_interface_target_yaml_returns_422_before_run_creation(
    app_with_real_services,
    base_dir,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    _write_workflow_file(base_dir, "input-redaction-legacy-interface", LEGACY_INTERFACE_TARGET_YAML)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_real_services),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/runs",
            json={
                "workflow_id": "input-redaction-legacy-interface",
                "branch": "main",
                "inputs": {"query": DIRECT_QUERY, "api_token": SECRET},
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
    assert payload["details"]["workflow_id"] == "input-redaction-legacy-interface"
    assert "legacy workflow interface is unsupported" in _json(payload)
    _assert_secret_absent("legacy interface rejection response", payload)
    assert DIRECT_QUERY not in _json(payload)

    with Session(db_engine) as session:
        runs = list(session.exec(select(Run)).all())

    assert runs == []


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
                "workflow_id": "input-redaction-direct",
                "branch": "main",
                "inputs": {
                    "query": {"marker": INVALID_QUERY_MARKER},
                    "api_token": SECRET,
                },
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
    assert payload["details"]["workflow_id"] == "input-redaction-direct"
    assert payload["details"]["fields"][0]["field"] == "query"
    assert payload["details"]["fields"][0]["code"] == "type_mismatch"
    assert payload["details"]["fields"][0]["expected_type"] == "string"
    assert payload["details"]["fields"][0]["actual_type"] == "json"
    validation_payload = _json(payload)
    assert SECRET not in validation_payload
    assert INVALID_QUERY_MARKER not in validation_payload

    with Session(db_engine) as session:
        runs = list(session.exec(select(Run)).all())

    assert runs == []
