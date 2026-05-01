"""Integration coverage for HTTP POST /api/runs -> execution service -> mocked LLM -> DB state.

Gap being closed: all API-layer tests mock the execution service, and all core-layer
tests skip the API layer.  No existing test covers the full path:

    HTTP POST /api/runs  ->  RunService.create_run  ->  ExecutionService.launch_execution
        ->  workflow engine  ->  mocked LLM  ->  ExecutionObserver writes Run/RunNode to DB

These tests exercise that full path with:
- FastAPI app with in-process ASGI transport
- In-memory SQLite DB with schema created via SQLModel.metadata.create_all
- Actual ExecutionService, engine, and observers
- ONLY the LLM is mocked (LiteLLMClient.achat)
"""

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    """Create a workflow YAML file at custom/workflows/<workflow_id>.yaml."""
    wf_dir = base_dir / "custom" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    canvas_dir = wf_dir / ".canvas"
    canvas_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


def _read_workflow_fixture(file_name: str) -> str:
    return (_FIXTURE_ROOT / file_name).read_text(encoding="utf-8")


def _write_provider_file(base_dir: Path) -> None:
    """Create an isolated provider fixture that LiteLLM can classify.

    The OpenAI provider type is behavior-bearing here: the core runner uses
    LiteLLM provider detection before the mocked LLM call is reached.
    """
    provider_dir = base_dir / "custom" / "providers"
    provider_dir.mkdir(parents=True, exist_ok=True)
    provider_content = (
        "id: openai\n"
        "kind: provider\n"
        "name: openai\n"
        "type: openai\n"
        "api_key: ${OPENAI_API_KEY}\n"
        "is_active: true\n"
        "models:\n"
        "  - gpt-4o\n"
    )
    (provider_dir / "openai.yaml").write_text(provider_content, encoding="utf-8")


def _write_secrets_file(base_dir: Path) -> None:
    """Create an isolated secrets.env at .runsight/secrets.env with a dummy test key."""
    secrets_dir = base_dir / ".runsight"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "secrets.env").write_text(
        "# Managed by Runsight\nOPENAI_API_KEY=dummy-fake-test-key-for-integration\n",
        encoding="utf-8",
    )


def _git_service_for(base_dir: Path) -> Mock:
    git_service = Mock()

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
        del branch
        path = Path(workflow_path)
        if not path.is_absolute():
            path = base_dir / workflow_path
        return path.read_text(encoding="utf-8")

    git_service.read_file.side_effect = _read_file
    git_service.get_sha.side_effect = lambda branch, workflow_path: "6" * 40
    git_service.list_files.side_effect = _list_files
    return git_service


def _make_achat_response(content: str, cost_usd: float = 0.001, total_tokens: int = 100):
    """Build a dict matching LiteLLMClient.achat return shape."""
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
    """Poll DB until the run reaches a terminal status or timeout expires.

    The execution service launches workflow execution as a background asyncio
    task, so the HTTP response returns before execution completes.  We need
    to wait for the background task to finish and the observer to write the
    final status.
    """
    terminal = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run and run.status in terminal:
                return run
        await asyncio.sleep(0.1)
    # Final attempt
    with Session(engine) as session:
        run = session.get(Run, run_id)
    return run


@pytest.fixture(autouse=True)
def _clear_provider_secret_env(monkeypatch):
    """Keep SecretsEnvLoader on this test's temp secrets.env."""
    for name in _PROVIDER_SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """Create a fresh in-memory SQLite engine with all tables."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def base_dir(tmp_path):
    """Temporary directory for workflow/soul/provider YAML files and secrets.env."""
    base = tmp_path / "run-creation-execution-workspace"
    _write_workflow_file(base, "simple-workflow", _read_workflow_fixture("simple-workflow.yaml"))
    _write_workflow_file(base, "failing-workflow", _read_workflow_fixture("failing-workflow.yaml"))
    _write_provider_file(base)
    _write_secrets_file(base)
    return base


@pytest.fixture
def app_with_real_services(db_engine, base_dir):
    """Create a FastAPI app wired with real services pointing at in-memory DB
    and temp filesystem, but no Alembic migrations (tables created via create_all).

    The execution service is fully real — only LLM calls are mocked externally.
    """
    from fastapi import FastAPI
    from sqlmodel import Session

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

    # Real provider repo — discovers the isolated provider fixture from tmp_path.
    provider_repo = FileSystemProviderRepo(base_path=str(base_dir))

    # Isolated secrets loader reads the dummy key from the temp .runsight/secrets.env.
    secrets = SecretsEnvLoader(base_path=str(base_dir))
    git_service = _git_service_for(base_dir)
    execution_session = Session(db_engine)

    # Build the real execution service
    execution_service = ExecutionService(
        run_repo=RunRepository(execution_session),
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=db_engine,
        secrets=secrets,
        git_service=git_service,
        settings_repo=None,
    )
    app.state.execution_service = execution_service

    # DI overrides for real services backed by in-memory DB
    def _get_run_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return RunService(run_repo, workflow_repo)

    def _get_execution_service(request=None):
        return execution_service

    def _get_eval_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return EvalService(run_repo)

    app.dependency_overrides[get_run_service] = _get_run_service
    app.dependency_overrides[get_execution_service] = _get_execution_service
    app.dependency_overrides[get_eval_service] = _get_eval_service

    yield app

    app.dependency_overrides.clear()
    execution_session.close()


# ---------------------------------------------------------------------------
# Successful execution: HTTP POST -> completed run with node records
# ---------------------------------------------------------------------------


class TestSuccessfulRunIntegration:
    """POST /api/runs with valid workflow YAML -> run created -> execution
    completes -> run.status = 'completed' in DB -> at least one node record
    exists for each block.
    """

    @pytest.mark.asyncio
    async def test_post_creates_run_and_returns_201_or_200(self, app_with_real_services, db_engine):
        """POST /api/runs should create a run record and return its id."""
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
                    json={
                        "workflow_id": "simple-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )

                assert response.status_code == 200, (
                    f"Expected 200, got {response.status_code}: {response.text}"
                )
                data = response.json()
                assert "id" in data, "Response must contain a run id"
                assert data["workflow_id"] == "simple-workflow"
                await _wait_for_run_terminal(db_engine, data["id"])

    @pytest.mark.asyncio
    async def test_run_reaches_completed_status_in_db(self, app_with_real_services, db_engine):
        """After execution, the run record in DB should have status='completed'."""
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
                    json={
                        "workflow_id": "simple-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )

                run_id = response.json()["id"]

                # Wait for the background task to complete
                run = await _wait_for_run_terminal(db_engine, run_id)

        assert run is not None, f"Run {run_id} not found in DB"
        assert run.status == RunStatus.completed, (
            f"Expected run status 'completed', got '{run.status}'. Error: {run.error}"
        )

    @pytest.mark.asyncio
    async def test_node_records_exist_for_each_block(self, app_with_real_services, db_engine):
        """After completed execution, at least one RunNode must exist per block."""
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
                    json={
                        "workflow_id": "simple-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )

                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

        with Session(db_engine) as session:
            nodes = session.exec(select(RunNode).where(RunNode.run_id == run_id)).all()

        assert len(nodes) >= 1, "At least one RunNode must be created for the 'analyze' block"
        node_ids = [n.node_id for n in nodes]
        assert "analyze" in node_ids, f"Expected a RunNode with node_id='analyze', got {node_ids}"

    @pytest.mark.asyncio
    async def test_node_record_has_completed_status(self, app_with_real_services, db_engine):
        """The RunNode for the 'analyze' block should have status='completed'."""
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
                    json={
                        "workflow_id": "simple-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )

                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")

        assert node is not None, "RunNode for 'analyze' block must exist"
        assert node.status == "completed", f"Expected node status 'completed', got '{node.status}'"

    @pytest.mark.asyncio
    async def test_no_external_api_keys_required(self, app_with_real_services, db_engine):
        """The test must succeed with no external API keys set in the environment.

        The secrets.env file on the temp filesystem provides the dummy key.
        External API key env vars are removed so SecretsEnvLoader falls through to
        secrets.env as the key source, and the mocked LLM completes successfully.
        """
        import os

        from httpx import ASGITransport, AsyncClient

        # Remove external API keys from os.environ so SecretsEnvLoader falls through
        # to the secrets.env file written during fixture setup.
        keys_to_remove = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
        saved = {k: os.environ.pop(k) for k in keys_to_remove if k in os.environ}
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app_with_real_services),
                base_url="http://localhost",
            ) as client:
                with patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("Result without external keys"),
                ):
                    response = await client.post(
                        "/api/runs",
                        json={
                            "workflow_id": "simple-workflow",
                            "branch": "main",
                            "inputs": {},
                        },
                    )

                    run_id = response.json()["id"]
                    run = await _wait_for_run_terminal(db_engine, run_id)
        finally:
            os.environ.update(saved)

        assert run.status == RunStatus.completed, (
            f"Run should complete with mocked LLM, no external keys. "
            f"Got status='{run.status}', error='{run.error}'"
        )


# ---------------------------------------------------------------------------
# Failing execution: HTTP POST -> failed run with error in DB
# ---------------------------------------------------------------------------


class TestFailingRunIntegration:
    """POST /api/runs with workflow containing a failing block -> run.status
    = 'failed' in DB.
    """

    @pytest.mark.asyncio
    async def test_run_reaches_failed_status_when_llm_raises(
        self, app_with_real_services, db_engine
    ):
        """When the LLM raises an exception, the run should end up as 'failed'."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://localhost",
        ) as client:
            with patch(
                "runsight_core.llm.client.LiteLLMClient.achat",
                new_callable=AsyncMock,
                side_effect=RuntimeError("LLM API connection failed"),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "failing-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )

                assert response.status_code == 200, (
                    f"POST should still succeed (run is created), got {response.status_code}"
                )
                run_id = response.json()["id"]

                run = await _wait_for_run_terminal(db_engine, run_id)

        assert run is not None, f"Run {run_id} not found in DB"
        assert run.status == RunStatus.failed, (
            f"Expected run status 'failed' when LLM raises, got '{run.status}'"
        )

    @pytest.mark.asyncio
    async def test_failed_run_has_error_message_in_db(self, app_with_real_services, db_engine):
        """The failed run record should contain an error message."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://localhost",
        ) as client:
            with patch(
                "runsight_core.llm.client.LiteLLMClient.achat",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Model overloaded, try again later"),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "failing-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )

                run_id = response.json()["id"]
                run = await _wait_for_run_terminal(db_engine, run_id)

        assert run.error is not None, "Failed run must have an error message"
        assert len(run.error) > 0, "Error message must not be empty"

    @pytest.mark.asyncio
    async def test_failed_run_has_node_record_with_error(self, app_with_real_services, db_engine):
        """Even for failed runs, a RunNode should be created for the block that failed."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://localhost",
        ) as client:
            with patch(
                "runsight_core.llm.client.LiteLLMClient.achat",
                new_callable=AsyncMock,
                side_effect=RuntimeError("LLM exploded"),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "failing-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )

                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

        with Session(db_engine) as session:
            nodes = session.exec(select(RunNode).where(RunNode.run_id == run_id)).all()

        assert len(nodes) >= 1, "At least one RunNode must be created even for a failed run"
        node_ids = [n.node_id for n in nodes]
        assert "broken_step" in node_ids, f"Expected a RunNode for 'broken_step', got {node_ids}"
        broken_node = next(n for n in nodes if n.node_id == "broken_step")
        assert broken_node.status == "failed", (
            f"Expected node status 'failed', got '{broken_node.status}'"
        )
