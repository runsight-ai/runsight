"""Regression coverage for execution transport seams.

These tests stay on public HTTP seams while exercising the real execution
service and stream wiring:

- POST /api/runs can be cancelled while launch preparation is still blocked
- GET /api/runs/{id}/stream replays persisted execution logs after a real run
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from sqlmodel import SQLModel, Session, create_engine, select

from runsight_api.core.secrets import SecretsEnvLoader
from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.data.repositories.run_read_model import RunReadModel
from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.eval_service import EvalService
from runsight_api.logic.services.execution_service import ExecutionService
from runsight_api.logic.services.run_service import RunService
from runsight_api.transport.deps import (
    get_eval_service,
    get_execution_service,
    get_run_service,
)
from runsight_api.transport.routers import runs, sse_stream

SIMPLE_WORKFLOW_YAML = """\
id: simple-workflow
kind: workflow
version: "1.0"
inputs:
  instruction:
    type: string
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: You are a careful analyst.
    provider: openai
    model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: analyst
workflow:
  name: simple_e2e_test
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    workflows_dir = base_dir / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
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
        "# Managed by Runsight\nOPENAI_API_KEY=dummy-fake-test-key-for-execution-transport\n",
        encoding="utf-8",
    )


def _make_achat_response(content: str, cost_usd: float = 0.001, total_tokens: int = 100):
    return {
        "content": content,
        "cost_usd": cost_usd,
        "prompt_tokens": 50,
        "completion_tokens": 50,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


def _build_app(*, db_engine, base_dir: Path, git_service=None):
    app = FastAPI()
    app.include_router(runs.router, prefix="/api")
    app.include_router(sse_stream.router, prefix="/api")

    workflow_repo = WorkflowRepository(str(base_dir))
    provider_repo = FileSystemProviderRepo(base_path=str(base_dir))
    secrets = SecretsEnvLoader(base_path=str(base_dir))
    execution_session = Session(db_engine)
    execution_service = ExecutionService(
        run_repo=RunRepository(execution_session),
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=db_engine,
        secrets=secrets,
        git_service=git_service,
    )
    app.state.execution_service = execution_service
    app.state.execution_session = execution_session

    def _get_run_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        run_read_model = RunReadModel(session)
        return RunService(run_repo, workflow_repo, run_read_model=run_read_model)

    def _get_execution_service(_request=None):
        return execution_service

    def _get_eval_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        run_read_model = RunReadModel(session)
        return EvalService(run_repo, run_read_model=run_read_model)

    app.dependency_overrides[get_run_service] = _get_run_service
    app.dependency_overrides[get_execution_service] = _get_execution_service
    app.dependency_overrides[get_eval_service] = _get_eval_service

    return app, execution_service


def test_execution_service_uses_supplied_persistence_repo_without_reconstructing_from_engine(
    db_engine,
):
    run = SimpleNamespace(
        id="run_ctor",
        status=RunStatus.pending,
        branch=None,
        commit_sha=None,
        updated_at=None,
    )
    updated_runs: list[object] = []
    supplied_repo = SimpleNamespace(
        list_runs=lambda: [],
        get_run=lambda run_id: run if run_id == "run_ctor" else None,
        update_run=lambda updated: updated_runs.append(updated),
    )

    service = ExecutionService(
        run_repo=supplied_repo,
        workflow_repo=Mock(),
        provider_repo=Mock(),
        engine=db_engine,
    )

    service._store_branch_and_sha("run_ctor", "feature/execution-transport", "abc123")

    assert run.branch == "feature/execution-transport"
    assert run.commit_sha == "abc123"
    assert updated_runs == [run]


def _parse_sse_events(raw: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    current_event: str | None = None
    current_data: list[str] = []

    for line in raw.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:") :].strip())
        elif line == "" and current_event is not None:
            payload = "\n".join(current_data)
            events.append(
                {
                    "event": current_event,
                    "data": json.loads(payload) if payload else None,
                }
            )
            current_event = None
            current_data = []

    return events


async def _wait_for_run_terminal(engine, run_id: str, timeout: float = 10.0) -> Run | None:
    deadline = asyncio.get_event_loop().time() + timeout
    terminal = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}

    while asyncio.get_event_loop().time() < deadline:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run is not None and run.status in terminal:
                return run
        await asyncio.sleep(0.05)

    with Session(engine) as session:
        return session.get(Run, run_id)


def _latest_run_id(engine) -> str:
    with Session(engine) as session:
        run = session.exec(select(Run).order_by(Run.created_at.desc())).first()
        assert run is not None, "expected POST /api/runs to create a run before prepare blocked"
        return run.id


def _cancel_latest_run(engine, workflow_repo: WorkflowRepository) -> str:
    run_id = _latest_run_id(engine)
    session = Session(engine)
    try:
        run_service = RunService(
            RunRepository(session),
            workflow_repo=workflow_repo,
            run_read_model=RunReadModel(session),
        )
        run_service.cancel_run(run_id)
    finally:
        session.close()
    return run_id


@pytest.fixture
def db_engine():
    db_path = Path(tempfile.mkdtemp(prefix="execution-transport-db-")) / "runsight.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def base_dir():
    with tempfile.TemporaryDirectory(prefix="execution-transport-base-") as tmpdir:
        base = Path(tmpdir)
        _write_workflow_file(base, "simple-workflow", SIMPLE_WORKFLOW_YAML)
        _write_provider_file(base)
        _write_secrets_file(base)
        yield base


@pytest.mark.asyncio
async def test_post_run_cancel_during_prepare_returns_cancelled_without_scheduling_execution(
    db_engine,
    base_dir: Path,
):
    from httpx import ASGITransport, AsyncClient

    read_started = Event()
    read_calls = {"count": 0}
    git_service = Mock()
    workflow_repo = WorkflowRepository(str(base_dir))

    def _blocked_read_file(*_args, **_kwargs):
        read_calls["count"] += 1
        if read_calls["count"] == 1:
            return SIMPLE_WORKFLOW_YAML
        read_started.set()
        _cancel_latest_run(db_engine, workflow_repo)
        return SIMPLE_WORKFLOW_YAML

    git_service.read_file.side_effect = _blocked_read_file
    git_service.get_sha.return_value = "a" * 40

    app, execution_service = _build_app(
        db_engine=db_engine,
        base_dir=base_dir,
        git_service=git_service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        create_response = await client.post(
            "/api/runs",
            json={
                "workflow_id": "simple-workflow",
                "inputs": {"instruction": "cancel during prepare"},
                "source": "simulation",
                "branch": "feature/sim",
            },
        )
    assert read_started.is_set(), "prepare never started"
    run_id = create_response.json()["id"]

    assert create_response.status_code == 200
    assert create_response.json()["status"] == "cancelled"
    assert create_response.json()["branch"] == "feature/sim"
    assert create_response.json()["source"] == "simulation"

    run = await _wait_for_run_terminal(db_engine, run_id)
    assert run is not None
    assert run.status == RunStatus.cancelled
    assert run.commit_sha == "a" * 40
    assert run_id not in execution_service._runtime.running_tasks


@pytest.mark.asyncio
async def test_post_run_then_stream_replays_persisted_execution_logs(db_engine, base_dir: Path):
    from httpx import ASGITransport, AsyncClient

    git_service = Mock()
    git_service.read_file.return_value = SIMPLE_WORKFLOW_YAML
    git_service.get_sha.return_value = "a" * 40

    app, _execution_service = _build_app(
        db_engine=db_engine,
        base_dir=base_dir,
        git_service=git_service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("Analysis complete."),
        ):
            create_response = await client.post(
                "/api/runs",
                json={
                    "workflow_id": "simple-workflow",
                    "branch": "main",
                    "inputs": {"instruction": "stream my execution"},
                },
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["id"]

            run = await _wait_for_run_terminal(db_engine, run_id)
            assert run is not None
            assert run.status == RunStatus.completed

            async with client.stream("GET", f"/api/runs/{run_id}/stream") as stream_response:
                assert stream_response.status_code == 200
                body = (await stream_response.aread()).decode()

    events = _parse_sse_events(body)
    replay_payloads = [
        event["data"]
        for event in events
        if event["event"] == "replay" and isinstance(event.get("data"), dict)
    ]

    assert any(payload.get("event") == "workflow_start" for payload in replay_payloads)
    assert any(payload.get("event") == "block_start" for payload in replay_payloads)
    assert any(payload.get("event") == "block_complete" for payload in replay_payloads)
    assert any(payload.get("event") == "workflow_complete" for payload in replay_payloads)
