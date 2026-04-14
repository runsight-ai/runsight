"""E2E coverage for RUN-845 parser warnings across workflow/run API flows.

These tests verify:
1) Workflow warnings are returned in canonical v1 shape (message/source/context)
2) Run creation snapshots workflow warnings immutably
3) Declared tools with corrupt metadata produce warnings while execution continues
4) Child runs do not inherit parent warning snapshots through API responses
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver


def _write_warning_soul(base_dir: Path, soul_key: str) -> None:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{soul_key}.yaml").write_text(
        "\n".join(
            [
                f"id: {soul_key}",
                "role: Warning Soul",
                "system_prompt: You are a warning-only soul.",
                "provider: openai",
                "model_name: gpt-4o",
                "tools: [http]",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_openai_provider(base_dir: Path) -> None:
    provider_dir = base_dir / "custom" / "providers"
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / "openai.yaml").write_text(
        "\n".join(
            [
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


def _write_corrupt_custom_tool(base_dir: Path, tool_id: str) -> None:
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / f"{tool_id}.yaml").write_text(
        "\n".join(
            [
                'version: "1.0"',
                "type: custom",
                "executor: python",
                "name: Broken lookup",
                "description: Intentionally broken metadata",
                "parameters:",
                "  type: object",
                "code: |",
                "  def main(args):",
                "      return {'broken':",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _warning_workflow_yaml(soul_key: str, *, declare_http: bool) -> str:
    tools_section = "tools:\n  - http\n" if declare_http else ""
    return (
        'version: "1.0"\n'
        "config:\n"
        "  model_name: gpt-4o\n"
        f"{tools_section}"
        "blocks:\n"
        "  analyze:\n"
        "    type: linear\n"
        f"    soul_ref: {soul_key}\n"
        "workflow:\n"
        "  name: run845_parser_warning_workflow\n"
        "  entry: analyze\n"
        "  transitions:\n"
        "    - from: analyze\n"
        "      to: null\n"
    )


BIND_LOOP_WARNING_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
tools:
  - lookup_profile
souls:
  analyst:
    id: analyst
    role: Analyst
    system_prompt: Use the lookup tool if needed.
    provider: openai
    model_name: gpt-4o
    tools:
      - lookup_profile
blocks:
  analyze:
    type: linear
    soul_ref: analyst
workflow:
  name: run845_bind_loop_warning
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""


def _make_achat_response(content: str):
    return {
        "content": content,
        "cost_usd": 0.001,
        "prompt_tokens": 50,
        "completion_tokens": 50,
        "total_tokens": 100,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


async def _wait_for_run_terminal(engine, run_id: str, timeout: float = 10.0):
    deadline = asyncio.get_running_loop().time() + timeout
    terminal = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
    while asyncio.get_running_loop().time() < deadline:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run is not None and run.status in terminal:
                return run
        await asyncio.sleep(0.1)
    with Session(engine) as session:
        return session.get(Run, run_id)


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def base_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _build_app(db_engine, base_dir: Path, *, include_execution: bool):
    from fastapi import FastAPI
    from sqlmodel import Session

    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.data.repositories.run_repo import RunRepository
    from runsight_api.logic.services.eval_service import EvalService
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.run_service import RunService
    from runsight_api.logic.services.workflow_service import WorkflowService
    from runsight_api.transport.deps import (
        get_eval_service,
        get_execution_service,
        get_run_service,
        get_workflow_service,
    )
    from runsight_api.transport.routers import runs, workflows

    workflow_repo = WorkflowRepository(str(base_dir))

    app = FastAPI()
    app.include_router(workflows.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")

    def _get_workflow_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return WorkflowService(workflow_repo, run_repo, git_service=None)

    def _get_run_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return RunService(run_repo, workflow_repo)

    def _get_eval_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return EvalService(run_repo)

    app.dependency_overrides[get_workflow_service] = _get_workflow_service
    app.dependency_overrides[get_run_service] = _get_run_service
    app.dependency_overrides[get_eval_service] = _get_eval_service

    if include_execution:
        provider_repo = FileSystemProviderRepo(base_path=str(base_dir))
        mock_secrets = Mock()
        mock_secrets.resolve = Mock(return_value="sk-fake-run845")
        execution_service = ExecutionService(
            run_repo=None,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
            secrets=mock_secrets,
            settings_repo=None,
        )
        app.state.execution_service = execution_service

        def _get_execution_service(request=None):
            return execution_service

        app.dependency_overrides[get_execution_service] = _get_execution_service
    else:

        def _get_execution_service(request=None):
            return None

        app.dependency_overrides[get_execution_service] = _get_execution_service

    return app


@pytest.fixture
def app_without_execution(db_engine, base_dir):
    app = _build_app(db_engine, base_dir, include_execution=False)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def app_with_execution(db_engine, base_dir):
    _write_openai_provider(base_dir)
    app = _build_app(db_engine, base_dir, include_execution=True)
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_workflow_warning_shape_run_snapshot_and_immutability(
    app_without_execution, base_dir
):
    from httpx import ASGITransport, AsyncClient

    soul_key = "run845_warning_soul"
    _write_warning_soul(base_dir, soul_key)

    warning_yaml = _warning_workflow_yaml(soul_key, declare_http=False)
    fixed_yaml = _warning_workflow_yaml(soul_key, declare_http=True)

    async with AsyncClient(
        transport=ASGITransport(app=app_without_execution),
        base_url="http://test",
    ) as client:
        create_workflow = await client.post(
            "/api/workflows",
            json={
                "name": "RUN-845 warning workflow",
                "yaml": warning_yaml,
                "commit": False,
            },
        )
        assert create_workflow.status_code == 200
        workflow_id = create_workflow.json()["id"]

        workflow_detail = await client.get(f"/api/workflows/{workflow_id}")
        assert workflow_detail.status_code == 200
        workflow_data = workflow_detail.json()
        assert workflow_data["valid"] is True

        warnings = workflow_data["warnings"]
        assert len(warnings) == 1
        warning = warnings[0]
        assert set(warning.keys()) == {"message", "source", "context"}
        assert isinstance(warning["message"], str)
        assert warning["context"] is None or isinstance(warning["context"], str)
        assert warning["source"] is None or isinstance(warning["source"], str)
        assert "undeclared tool" in warning["message"].lower()
        assert "code" not in warning
        assert not isinstance(warning["context"], dict)

        create_run = await client.post(
            "/api/runs",
            json={
                "workflow_id": workflow_id,
                "task_data": {},
            },
        )
        assert create_run.status_code == 200
        run_data = create_run.json()
        run_id = run_data["id"]
        assert run_data["warnings"] == warnings

        run_detail_before_fix = await client.get(f"/api/runs/{run_id}")
        assert run_detail_before_fix.status_code == 200
        assert run_detail_before_fix.json()["warnings"] == warnings

        update_workflow = await client.put(
            f"/api/workflows/{workflow_id}",
            json={"yaml": fixed_yaml},
        )
        assert update_workflow.status_code == 200

        workflow_detail_after_fix = await client.get(f"/api/workflows/{workflow_id}")
        assert workflow_detail_after_fix.status_code == 200
        assert workflow_detail_after_fix.json()["warnings"] == []

        run_detail_after_fix = await client.get(f"/api/runs/{run_id}")
        assert run_detail_after_fix.status_code == 200
        assert run_detail_after_fix.json()["warnings"] == warnings


@pytest.mark.asyncio
async def test_bind_loop_warning_from_corrupt_metadata_does_not_block_execution(
    app_with_execution, base_dir, db_engine
):
    from httpx import ASGITransport, AsyncClient

    _write_corrupt_custom_tool(base_dir, "lookup_profile")

    async with AsyncClient(
        transport=ASGITransport(app=app_with_execution),
        base_url="http://test",
    ) as client:
        create_workflow = await client.post(
            "/api/workflows",
            json={
                "name": "RUN-845 bind-loop warning workflow",
                "yaml": BIND_LOOP_WARNING_YAML,
                "commit": False,
            },
        )
        assert create_workflow.status_code == 200
        workflow_id = create_workflow.json()["id"]

        workflow_detail = await client.get(f"/api/workflows/{workflow_id}")
        assert workflow_detail.status_code == 200
        workflow_data = workflow_detail.json()
        assert workflow_data["valid"] is True
        assert workflow_data["warnings"], "Expected warning from corrupt custom tool metadata"
        first_warning = workflow_data["warnings"][0]
        assert first_warning["source"] == "tool_definitions"
        assert first_warning["context"] == "lookup_profile"

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("Execution continued despite warning."),
        ):
            create_run = await client.post(
                "/api/runs",
                json={
                    "workflow_id": workflow_id,
                    "task_data": {"instruction": "Run with warning-only tool metadata"},
                },
            )

            assert create_run.status_code == 200
            run_payload = create_run.json()
            run_id = run_payload["id"]
            assert run_payload["warnings"] == workflow_data["warnings"]

            terminal_run = await _wait_for_run_terminal(db_engine, run_id, timeout=10.0)
            assert terminal_run is not None
            assert terminal_run.status == RunStatus.completed

            run_detail = await client.get(f"/api/runs/{run_id}")
            assert run_detail.status_code == 200
            run_data = run_detail.json()
            assert run_data["warnings"] == workflow_data["warnings"]
            assert run_data["status"] == RunStatus.completed.value


@pytest.mark.asyncio
async def test_child_run_warnings_do_not_inherit_parent_snapshot(app_without_execution, db_engine):
    from httpx import ASGITransport, AsyncClient

    parent_run_id = "run845_parent"
    parent_warning = {
        "message": "Parent warning should not propagate",
        "source": "tool_governance",
        "context": "parent_soul",
    }

    with Session(db_engine) as session:
        session.add(
            Run(
                id=parent_run_id,
                workflow_id="wf_parent_845",
                workflow_name="Parent workflow",
                status=RunStatus.running,
                task_json="{}",
                warnings_json=[parent_warning],
            )
        )
        session.commit()

    observer = ExecutionObserver(engine=db_engine, run_id=parent_run_id)
    observer.on_block_start(
        "Parent workflow",
        "invoke_child",
        "workflow",
        child_workflow_id="wf_child_845",
        child_workflow_name="Child workflow",
    )

    with Session(db_engine) as session:
        children = list(session.exec(select(Run).where(Run.parent_run_id == parent_run_id)).all())
        assert len(children) == 1
        child = children[0]
        assert child.warnings_json is None
        child_run_id = child.id

    async with AsyncClient(
        transport=ASGITransport(app=app_without_execution),
        base_url="http://test",
    ) as client:
        child_response = await client.get(f"/api/runs/{child_run_id}")
        assert child_response.status_code == 200
        assert child_response.json()["warnings"] == []
