"""Assertion evaluation integration smoke coverage."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "execution_assertions"


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    workflow_dir = base_dir / "custom" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / ".canvas").mkdir(parents=True, exist_ok=True)
    (workflow_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


def _git_service_for(base_dir: Path) -> Mock:
    git_service = Mock()
    git_service.read_file.side_effect = lambda workflow_path, branch: (
        base_dir / workflow_path
    ).read_text(encoding="utf-8")
    git_service.get_sha.return_value = "7" * 40
    git_service.list_files.return_value = []
    return git_service


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


async def _wait_for_run_terminal(engine, run_id: str, timeout: float = 10.0) -> Run:
    terminal = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run and run.status in terminal:
                return run
        await asyncio.sleep(0.05)
    with Session(engine) as session:
        run = session.get(Run, run_id)
    assert run is not None, f"Run {run_id} was not created"
    return run


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    _write_workflow_file(
        tmp_path,
        "contains-assertion-workflow",
        (FIXTURE_ROOT / "contains-assertion-workflow.yaml").read_text(encoding="utf-8"),
    )
    return tmp_path


@pytest.fixture
def app_with_real_services(db_engine, base_dir):
    from fastapi import FastAPI

    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.data.repositories.run_repo import RunRepository
    from runsight_api.logic.services.eval_service import EvalService
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.run_service import RunService
    from runsight_api.transport.deps import (
        get_eval_service,
        get_execution_service,
        get_run_service,
    )
    from runsight_api.transport.routers import runs

    app = FastAPI()
    app.include_router(runs.router, prefix="/api")

    workflow_repo = WorkflowRepository(str(base_dir))
    execution_session = Session(db_engine)
    execution_service = ExecutionService(
        run_repo=RunRepository(execution_session),
        workflow_repo=workflow_repo,
        provider_repo=FileSystemProviderRepo(base_path=str(base_dir)),
        engine=db_engine,
        secrets=Mock(resolve=Mock(return_value="dummy-fake-test-key")),
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


@pytest.fixture
def mock_provider():
    provider = Mock()
    provider.id = "openai"
    provider.type = "openai"
    provider.api_key = "dummy-test"
    provider.is_active = True
    provider.models = ["gpt-4o"]
    return provider


@pytest.mark.asyncio
async def test_assertion_evaluation_integration_smoke(
    app_with_real_services,
    db_engine,
    mock_provider,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app_with_real_services),
        base_url="http://localhost",
    ) as client:
        with (
            patch(
                "runsight_core.llm.client.LiteLLMClient.achat",
                new_callable=AsyncMock,
                return_value=_make_achat_response("The answer is X, confirmed."),
            ),
            patch.object(
                app_with_real_services.state.execution_service.provider_repo,
                "list_all",
                return_value=[mock_provider],
            ),
        ):
            response = await client.post(
                "/api/runs",
                json={
                    "workflow_id": "contains-assertion-workflow",
                    "branch": "main",
                    "inputs": {},
                },
            )
            assert response.status_code == 200, response.text
            run_id = response.json()["id"]
            run = await _wait_for_run_terminal(db_engine, run_id)

        nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

    assert run.status == RunStatus.completed
    assert nodes_response.status_code == 200
    analyze_node = next(node for node in nodes_response.json() if node["node_id"] == "analyze")
    assert analyze_node["eval_passed"] is True
    assert analyze_node["eval_score"] == 1.0
    assert analyze_node["eval_results"]["assertions"][0]["passed"] is True
