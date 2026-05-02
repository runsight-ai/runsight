"""HTTP POST /api/runs to execution persistence smoke coverage."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.core.secrets import SecretsEnvLoader
from runsight_api.domain.entities.run import Run, RunNode, RunStatus


_PROVIDER_SECRET_ENV_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)
_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "run_creation_execution"


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    workflow_dir = base_dir / "custom" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / ".canvas").mkdir(parents=True, exist_ok=True)
    (workflow_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


def _write_provider_file(base_dir: Path) -> None:
    provider_dir = base_dir / "custom" / "providers"
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / "openai.yaml").write_text(
        "id: openai\n"
        "kind: provider\n"
        "name: openai\n"
        "type: openai\n"
        "api_key: ${OPENAI_API_KEY}\n"
        "is_active: true\n"
        "models:\n"
        "  - gpt-4o\n",
        encoding="utf-8",
    )


def _write_secrets_file(base_dir: Path) -> None:
    secrets_dir = base_dir / ".runsight"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "secrets.env").write_text(
        "# Managed by Runsight\nOPENAI_API_KEY=dummy-fake-test-key\n",
        encoding="utf-8",
    )


def _git_service_for(base_dir: Path) -> Mock:
    git_service = Mock()
    git_service.read_file.side_effect = lambda workflow_path, branch: (
        base_dir / workflow_path
    ).read_text(encoding="utf-8")
    git_service.get_sha.return_value = "6" * 40
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


@pytest.fixture(autouse=True)
def _clear_provider_secret_env(monkeypatch):
    for name in _PROVIDER_SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    base = tmp_path / "run-creation-execution-workspace"
    _write_workflow_file(
        base,
        "simple-workflow",
        (_FIXTURE_ROOT / "simple-workflow.yaml").read_text(encoding="utf-8"),
    )
    _write_provider_file(base)
    _write_secrets_file(base)
    return base


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


@pytest.mark.asyncio
async def test_post_run_executes_workflow_and_persists_node_smoke(
    app_with_real_services,
    db_engine,
) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app_with_real_services),
        base_url="http://localhost",
    ) as client:
        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("Analysis complete."),
        ):
            response = await client.post(
                "/api/runs",
                json={"workflow_id": "simple-workflow", "branch": "main", "inputs": {}},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            run = await _wait_for_run_terminal(db_engine, payload["id"])

    with Session(db_engine) as session:
        nodes = session.exec(select(RunNode).where(RunNode.run_id == run.id)).all()

    assert payload["workflow_id"] == "simple-workflow"
    assert run.status == RunStatus.completed
    assert any(node.node_id == "analyze" and node.status == "completed" for node in nodes)
