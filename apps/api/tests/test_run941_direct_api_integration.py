"""Integration coverage for RUN-941 Direct API workflow invocation.

The versioned asset graph coverage here uses the stable no-network runtime path
currently available to backend integration tests: committed workflow YAML plus a
referenced committed child workflow. Provider/soul/custom-tool metadata snapshot
coverage still needs a stable Direct API fixture that exercises those runtime
assets without crossing into external model/provider calls.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.run import Run, RunNode, RunStatus


WORKFLOW_ID = "run941-direct"
PARENT_WORKFLOW_ID = "run941-parent"
CHILD_WORKFLOW_ID = "run941-child"
SECRET = "run941-secret-plain-text-must-never-echo"
IDEMPOTENCY_SECRET = "run941-idempotency-key-not-a-contract"
DIRTY_MARKER = "run941-dirty-working-tree-marker"


DIRECT_WORKFLOW_YAML = """\
id: run941-direct
kind: workflow
version: "1.0"
enabled: true
inputs:
  query:
    type: string
  api_token:
    type: string
    sensitive: true
  limit:
    type: number
    required: false
    default: 7
config: {}
blocks:
  echo:
    type: code
    timeout_seconds: 5
    inputs:
      query:
        from: workflow.query
      limit:
        from: workflow.limit
      token:
        from: workflow.api_token
    code: |
      def main(data):
          return {
              "query": data["query"],
              "limit": data["limit"],
              "token_echo": data["token"],
              "asset_marker": "committed-direct",
          }
workflow:
  name: Run941 Committed Direct
  entry: echo
  transitions:
    - from: echo
      to: null
"""


DIRTY_DIRECT_WORKFLOW_YAML = f"""\
id: run941-direct
kind: workflow
version: "1.0"
inputs:
  query:
    type: number
  dirty_required:
    type: string
config: {{}}
blocks:
  echo:
    type: code
    code: |
      def main(data):
          return {{"asset_marker": "{DIRTY_MARKER}"}}
workflow:
  name: Run941 Dirty Direct
  entry: echo
  transitions:
    - from: echo
      to: null
"""


PARENT_WORKFLOW_YAML = """\
id: run941-parent
kind: workflow
version: "1.0"
enabled: true
inputs:
  query:
    type: string
  api_token:
    type: string
    sensitive: true
config: {}
blocks:
  invoke_child:
    type: workflow
    workflow_ref: run941-child
    inputs:
      child_query: workflow.query
      child_token: workflow.api_token
workflow:
  name: Run941 Committed Parent
  entry: invoke_child
  transitions:
    - from: invoke_child
      to: null
"""


CHILD_WORKFLOW_YAML = """\
id: run941-child
kind: workflow
version: "1.0"
enabled: true
inputs:
  child_query:
    type: string
  child_token:
    type: string
    sensitive: true
config: {}
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
      def main(data):
          return {
              "child_query": data["query"],
              "child_token_echo": data["token"],
              "asset_marker": "committed-child",
          }
workflow:
  name: Run941 Committed Child
  entry: child_echo
  transitions:
    - from: child_echo
      to: null
"""


DIRTY_CHILD_WORKFLOW_YAML = f"""\
id: run941-child
kind: workflow
version: "1.0"
inputs:
  child_query:
    type: number
  dirty_child_only:
    type: string
config: {{}}
blocks:
  child_echo:
    type: code
    code: |
      def main(data):
          return {{"asset_marker": "{DIRTY_MARKER}"}}
workflow:
  name: Run941 Dirty Child
  entry: child_echo
  transitions:
    - from: child_echo
      to: null
"""


def _write_repo_file(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_git_repo(repo: Path) -> str:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "tests@runsight.dev"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Runsight Tests"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "commit run941 assets"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo_root(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    _write_repo_file(repo, f"custom/workflows/{WORKFLOW_ID}.yaml", DIRECT_WORKFLOW_YAML)
    _write_repo_file(repo, f"custom/workflows/{PARENT_WORKFLOW_ID}.yaml", PARENT_WORKFLOW_YAML)
    _write_repo_file(repo, f"custom/workflows/{CHILD_WORKFLOW_ID}.yaml", CHILD_WORKFLOW_YAML)
    committed_sha = _init_git_repo(repo)
    return repo, committed_sha


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def direct_api_app(db_engine, repo_root: tuple[Path, str]):
    from runsight_api.core.secrets import SecretsEnvLoader
    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.data.repositories.run_read_model import RunReadModel
    from runsight_api.data.repositories.run_repo import RunRepository
    from runsight_api.domain.errors import RunsightError
    from runsight_api.logic.services.eval_service import EvalService
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.git_service import GitService
    from runsight_api.logic.services.run_service import RunService
    from runsight_api.logic.services.trigger_runtime import (
        ExternalInvocationAdmission,
        TriggerRuntimeConfig,
    )
    from runsight_api.transport.deps import (
        get_eval_service,
        get_execution_service,
        get_external_invocation_admission,
        get_run_service,
    )
    from runsight_api.transport.middleware.body_limit import BodySizeLimitMiddleware
    from runsight_api.transport.middleware.error_handler import (
        global_exception_handler,
        request_validation_exception_handler,
    )
    from runsight_api.transport.routers import runs, workflows

    repo, _ = repo_root
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=768)
    app.add_exception_handler(RunsightError, global_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(runs.router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")

    workflow_repo = WorkflowRepository(str(repo))
    execution_session = Session(db_engine)
    execution_service = ExecutionService(
        run_repo=RunRepository(execution_session),
        workflow_repo=workflow_repo,
        provider_repo=FileSystemProviderRepo(base_path=str(repo)),
        engine=db_engine,
        secrets=SecretsEnvLoader(base_path=str(repo)),
        git_service=GitService(repo),
    )
    admission = ExternalInvocationAdmission(
        TriggerRuntimeConfig(
            external_invocation_enabled=True,
            max_concurrent_runs=5,
            max_pending_external_invocations=5,
            body_limit_bytes=768,
            public_base_url=None,
        )
    )
    app.state.execution_service = execution_service
    app.state.external_invocation_admission = admission

    def _run_service() -> RunService:
        session = Session(db_engine)
        return RunService(
            RunRepository(session),
            workflow_repo,
            run_read_model=RunReadModel(session),
        )

    def _eval_service() -> EvalService:
        session = Session(db_engine)
        return EvalService(RunRepository(session), run_read_model=RunReadModel(session))

    app.dependency_overrides[get_run_service] = _run_service
    app.dependency_overrides[get_execution_service] = lambda: execution_service
    app.dependency_overrides[get_external_invocation_admission] = lambda: admission
    app.dependency_overrides[get_eval_service] = _eval_service

    yield app

    app.dependency_overrides.clear()
    execution_session.close()


async def _wait_for_terminal(engine, run_id: str, timeout: float = 5.0) -> Run:
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


def _all_runs(engine) -> list[Run]:
    with Session(engine) as session:
        return list(session.exec(select(Run).order_by(Run.created_at)).all())


def _assert_secret_absent(label: str, value: Any) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    assert SECRET not in rendered, f"{label} leaked Direct API secret: {rendered}"
    assert IDEMPOTENCY_SECRET not in rendered, f"{label} leaked idempotency header: {rendered}"


def _assert_sensitive_snapshot(snapshot: dict[str, Any], field: str) -> None:
    assert snapshot[field]["sensitive"] is True
    assert snapshot[field]["source"] == "provided"
    assert "value" not in snapshot[field]
    assert "redacted" not in snapshot[field]


def _assert_schema_field(
    schema: dict[str, Any],
    field: str,
    *,
    field_type: str,
    required: bool,
    sensitive: bool,
    default: Any = None,
) -> None:
    assert schema[field]["type"] == field_type
    assert schema[field]["required"] is required
    assert schema[field]["sensitive"] is sensitive
    if default is not None:
        assert schema[field]["default"] == default


@pytest.mark.asyncio
async def test_direct_api_uses_committed_main_for_validation_metadata_and_dirty_asset_graph(
    direct_api_app,
    db_engine,
    repo_root: tuple[Path, str],
) -> None:
    from httpx import ASGITransport, AsyncClient

    repo, committed_sha = repo_root
    _write_repo_file(repo, f"custom/workflows/{WORKFLOW_ID}.yaml", DIRTY_DIRECT_WORKFLOW_YAML)
    _write_repo_file(repo, f"custom/workflows/{CHILD_WORKFLOW_ID}.yaml", DIRTY_CHILD_WORKFLOW_YAML)

    async with AsyncClient(
        transport=ASGITransport(app=direct_api_app),
        base_url="http://test",
    ) as client:
        create = await client.post(
            f"/api/workflows/{WORKFLOW_ID}/runs",
            json={"inputs": {"query": "committed query", "api_token": SECRET}},
            headers={
                "x-request-id": "corr-run-941",
                "x-idempotency-key": IDEMPOTENCY_SECRET,
            },
        )
        assert create.status_code == 200, create.text
        create_payload = create.json()
        run = await _wait_for_terminal(db_engine, create_payload["id"])
        detail = await client.get(f"/api/runs/{run.id}")
        listing = await client.get("/api/runs", params={"source": "api"})

    assert run.status == RunStatus.completed
    assert run.source == "api"
    assert run.branch == "main"
    assert run.commit_sha == committed_sha
    assert run.workflow_name == "Run941 Committed Direct"
    assert run.source_correlation_id == "corr-run-941"
    assert run.source_metadata == {
        "entry_path": "direct_api",
        "request_path": f"/api/workflows/{WORKFLOW_ID}/runs",
    }
    assert run.workflow_input_schema is not None
    assert set(run.workflow_input_schema) == {"query", "api_token", "limit"}
    assert "dirty_required" not in run.workflow_input_schema
    _assert_schema_field(
        run.workflow_input_schema,
        "query",
        field_type="string",
        required=True,
        sensitive=False,
    )
    _assert_schema_field(
        run.workflow_input_schema,
        "api_token",
        field_type="string",
        required=True,
        sensitive=True,
    )
    _assert_schema_field(
        run.workflow_input_schema,
        "limit",
        field_type="number",
        required=False,
        sensitive=False,
        default=7,
    )
    assert run.workflow_inputs is not None
    assert run.workflow_inputs["query"]["value"] == "committed query"
    assert run.workflow_inputs["limit"]["source"] == "defaulted"
    _assert_sensitive_snapshot(run.workflow_inputs, "api_token")

    assert detail.status_code == 200, detail.text
    assert listing.status_code == 200, listing.text
    listing_items = {item["id"]: item for item in listing.json()["items"]}
    for label, payload in {
        "accepted response": create_payload,
        "detail response": detail.json(),
        "list response": listing_items[run.id],
        "database row": run.model_dump(),
    }.items():
        _assert_sensitive_snapshot(payload["workflow_inputs"], "api_token")
        _assert_secret_absent(label, payload)
        assert payload["source"] == "api"
        assert payload["commit_sha"] == committed_sha
        assert payload["source_metadata"]["entry_path"] == "direct_api"
        assert "idempotency" not in json.dumps(payload["source_metadata"]).lower()

    assert run.results_json is not None
    assert "committed-direct" in run.results_json
    assert DIRTY_MARKER not in run.results_json
    _assert_secret_absent("run results", run.results_json)


@pytest.mark.asyncio
async def test_direct_api_nested_workflow_execution_uses_committed_child_snapshot(
    direct_api_app,
    db_engine,
    repo_root: tuple[Path, str],
) -> None:
    from httpx import ASGITransport, AsyncClient

    repo, committed_sha = repo_root
    _write_repo_file(repo, f"custom/workflows/{CHILD_WORKFLOW_ID}.yaml", DIRTY_CHILD_WORKFLOW_YAML)

    async with AsyncClient(
        transport=ASGITransport(app=direct_api_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/workflows/{PARENT_WORKFLOW_ID}/runs",
            json={"inputs": {"query": "child committed query", "api_token": SECRET}},
        )
        assert response.status_code == 200, response.text
        parent_run_id = response.json()["id"]
        parent_run = await _wait_for_terminal(db_engine, parent_run_id)

    with Session(db_engine) as session:
        parent_node = session.get(RunNode, f"{parent_run_id}:invoke_child")
        assert parent_node is not None
        assert parent_node.child_run_id is not None
        child_run_id = parent_node.child_run_id

    child_run = await _wait_for_terminal(db_engine, child_run_id)

    assert parent_run.status == RunStatus.completed
    assert parent_run.commit_sha == committed_sha
    assert child_run.status == RunStatus.completed
    assert child_run.workflow_id == CHILD_WORKFLOW_ID
    assert child_run.parent_run_id == parent_run_id
    assert child_run.workflow_name == "Run941 Committed Child"
    assert child_run.workflow_input_schema is not None
    assert set(child_run.workflow_input_schema) == {"child_query", "child_token"}
    assert "dirty_child_only" not in child_run.workflow_input_schema
    _assert_schema_field(
        child_run.workflow_input_schema,
        "child_query",
        field_type="string",
        required=True,
        sensitive=False,
    )
    _assert_schema_field(
        child_run.workflow_input_schema,
        "child_token",
        field_type="string",
        required=True,
        sensitive=True,
    )
    assert child_run.workflow_inputs is not None
    assert child_run.workflow_inputs["child_query"]["value"] == "child committed query"
    _assert_sensitive_snapshot(child_run.workflow_inputs, "child_token")
    assert child_run.results_json is not None
    assert "committed-child" in child_run.results_json
    assert DIRTY_MARKER not in child_run.results_json
    _assert_secret_absent("child run", child_run.model_dump())
    _assert_secret_absent("child results", child_run.results_json)


@pytest.mark.asyncio
async def test_direct_api_rejects_privileged_body_fields_before_run_creation(
    direct_api_app,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    forbidden_fields = [
        "source",
        "branch",
        "commit_sha",
        "debug",
        "simulation",
        "idempotency_key",
        "trigger",
        "trigger_id",
        "delivery",
        "delivery_id",
        "provenance",
        "source_metadata",
    ]

    async with AsyncClient(
        transport=ASGITransport(app=direct_api_app),
        base_url="http://test",
    ) as client:
        for field in forbidden_fields:
            response = await client.post(
                f"/api/workflows/{WORKFLOW_ID}/runs",
                json={"inputs": {"query": "ok", "api_token": SECRET}, field: SECRET},
            )
            assert response.status_code == 422, (field, response.text)
            body = response.json()
            assert body["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
            assert body["details"]["fields"][0]["field"] == field
            assert body["details"]["fields"][0]["code"] == "unknown"
            _assert_secret_absent(f"rejection for {field}", body)

    assert _all_runs(db_engine) == []


@pytest.mark.asyncio
async def test_direct_api_canonical_input_validation_returns_422_before_run_creation(
    direct_api_app,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=direct_api_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/workflows/{WORKFLOW_ID}/runs",
            json={"inputs": {"query": {"not": "a string"}, "api_token": SECRET}},
        )

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
    assert body["details"]["workflow_id"] == WORKFLOW_ID
    assert body["details"]["fields"][0]["field"] == "query"
    assert body["details"]["fields"][0]["code"] == "type_mismatch"
    _assert_secret_absent("canonical validation response", body)
    assert _all_runs(db_engine) == []


@pytest.mark.asyncio
async def test_direct_api_runtime_disabled_and_saturated_fail_before_run_creation(
    direct_api_app,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    from runsight_api.logic.services.trigger_runtime import (
        ExternalInvocationAdmission,
        TriggerRuntimeConfig,
    )
    from runsight_api.transport.deps import get_external_invocation_admission

    disabled = ExternalInvocationAdmission(
        TriggerRuntimeConfig(
            external_invocation_enabled=False,
            max_concurrent_runs=1,
            max_pending_external_invocations=1,
            body_limit_bytes=768,
            public_base_url=None,
        )
    )
    saturated = ExternalInvocationAdmission(
        TriggerRuntimeConfig(
            external_invocation_enabled=True,
            max_concurrent_runs=1,
            max_pending_external_invocations=1,
            body_limit_bytes=768,
            public_base_url=None,
        ),
        pending_external_invocations=1,
    )

    async with AsyncClient(
        transport=ASGITransport(app=direct_api_app),
        base_url="http://test",
    ) as client:
        direct_api_app.dependency_overrides[get_external_invocation_admission] = lambda: disabled
        unavailable = await client.post(
            f"/api/workflows/{WORKFLOW_ID}/runs",
            json={"inputs": {"query": "ok", "api_token": SECRET}},
        )
        direct_api_app.dependency_overrides[get_external_invocation_admission] = lambda: saturated
        too_many = await client.post(
            f"/api/workflows/{WORKFLOW_ID}/runs",
            json={"inputs": {"query": "ok", "api_token": SECRET}},
        )

    assert unavailable.status_code == 503, unavailable.text
    assert unavailable.json()["error_code"] == "RUNTIME_UNAVAILABLE"
    assert too_many.status_code == 429, too_many.text
    assert too_many.json()["error_code"] == "ADMISSION_SATURATED"
    _assert_secret_absent("runtime unavailable response", unavailable.json())
    _assert_secret_absent("saturated response", too_many.json())
    assert _all_runs(db_engine) == []


@pytest.mark.asyncio
async def test_direct_api_body_too_large_returns_413_before_route_parsing_or_storage(
    direct_api_app,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=direct_api_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/workflows/{WORKFLOW_ID}/runs",
            content=b'{"inputs":{"query":"' + (b"x" * 900) + b'"}}',
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413, response.text
    assert response.json()["error_code"] == "REQUEST_BODY_TOO_LARGE"
    assert _all_runs(db_engine) == []


@pytest.mark.asyncio
async def test_direct_api_idempotency_headers_are_not_persisted_exposed_or_deduped(
    direct_api_app,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=direct_api_app),
        base_url="http://test",
    ) as client:
        first = await client.post(
            f"/api/workflows/{WORKFLOW_ID}/runs",
            json={"inputs": {"query": "first", "api_token": SECRET}},
            headers={"x-idempotency-key": IDEMPOTENCY_SECRET},
        )
        second = await client.post(
            f"/api/workflows/{WORKFLOW_ID}/runs",
            json={"inputs": {"query": "second", "api_token": SECRET}},
            headers={"x-idempotency-key": IDEMPOTENCY_SECRET},
        )
        body_rejection = await client.post(
            f"/api/workflows/{WORKFLOW_ID}/runs",
            json={
                "inputs": {"query": "third", "api_token": SECRET},
                "idempotency_key": IDEMPOTENCY_SECRET,
            },
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] != second.json()["id"]
    assert body_rejection.status_code == 422, body_rejection.text

    runs = _all_runs(db_engine)
    assert [run.id for run in runs] == [first.json()["id"], second.json()["id"]]
    assert "idempotency" not in Run.model_fields
    assert "idempotency_key" not in Run.model_fields
    for run in runs:
        assert run.source_metadata == {
            "entry_path": "direct_api",
            "request_path": f"/api/workflows/{WORKFLOW_ID}/runs",
        }
        _assert_secret_absent("idempotency run row", run.model_dump())
