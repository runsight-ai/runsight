"""Regression coverage for execution transport seams.

These tests stay on public HTTP seams while exercising the real execution
service and stream wiring:

- POST /api/runs can be cancelled while launch preparation is still blocked
- GET /api/runs/{id}/stream replays persisted execution logs after a real run
"""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.domain.entities.run import RunStatus
from runsight_api.logic.services.execution_service import ExecutionService
from tests.fixtures.execution_transport.helpers import PROVIDER_SECRET_ENV_NAMES
from tests.fixtures.execution_transport.helpers import build_app
from tests.fixtures.execution_transport.helpers import cancel_latest_run
from tests.fixtures.execution_transport.helpers import make_achat_response
from tests.fixtures.execution_transport.helpers import parse_sse_events
from tests.fixtures.execution_transport.helpers import wait_for_run_terminal

pytest_plugins = ["tests.fixtures.execution_transport.helpers"]


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


@pytest.fixture(autouse=True)
def _clear_provider_secret_env(monkeypatch):
    """Keep SecretsEnvLoader on this test's temp secrets.env."""
    for name in PROVIDER_SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.asyncio
async def test_post_run_cancel_during_prepare_returns_cancelled_without_scheduling_execution(
    db_engine,
    base_dir: Path,
    simple_workflow_yaml: str,
):
    from httpx import ASGITransport, AsyncClient

    read_started = Event()
    read_calls = {"count": 0}
    git_service = Mock()
    workflow_repo = WorkflowRepository(str(base_dir))

    def _blocked_read_file(*_args, **_kwargs):
        read_calls["count"] += 1
        if read_calls["count"] == 1:
            return simple_workflow_yaml
        read_started.set()
        cancel_latest_run(db_engine, workflow_repo)
        return simple_workflow_yaml

    git_service.read_file.side_effect = _blocked_read_file
    git_service.get_sha.return_value = "a" * 40

    app, execution_service = build_app(
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

    run = await wait_for_run_terminal(db_engine, run_id)
    assert run is not None
    assert run.status == RunStatus.cancelled
    assert run.commit_sha == "a" * 40
    assert run_id not in execution_service._runtime.running_tasks


@pytest.mark.asyncio
async def test_post_run_then_stream_replays_persisted_execution_logs(
    db_engine,
    base_dir: Path,
    simple_workflow_yaml: str,
):
    from httpx import ASGITransport, AsyncClient

    git_service = Mock()
    git_service.read_file.return_value = simple_workflow_yaml
    git_service.get_sha.return_value = "a" * 40

    app, _execution_service = build_app(
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
            return_value=make_achat_response("Analysis complete."),
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

            run = await wait_for_run_terminal(db_engine, run_id)
            assert run is not None
            assert run.status == RunStatus.completed

            async with client.stream("GET", f"/api/runs/{run_id}/stream") as stream_response:
                assert stream_response.status_code == 200
                body = (await stream_response.aread()).decode()

    events = parse_sse_events(body)
    replay_payloads = [
        event["data"]
        for event in events
        if event["event"] == "replay" and isinstance(event.get("data"), dict)
    ]

    assert any(payload.get("event") == "workflow_start" for payload in replay_payloads)
    assert any(payload.get("event") == "block_start" for payload in replay_payloads)
    assert any(payload.get("event") == "block_complete" for payload in replay_payloads)
    assert any(payload.get("event") == "workflow_complete" for payload in replay_payloads)
