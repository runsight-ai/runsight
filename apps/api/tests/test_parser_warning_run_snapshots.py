"""Integration coverage for parser warnings across workflow/run API flows.

These tests verify:
1) Workflow warnings are returned in canonical v1 shape (message/source/context)
2) Run creation snapshots workflow warnings immutably
3) Declared tools with corrupt metadata produce warnings while execution continues
4) Child runs do not inherit parent warning snapshots through API responses
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session, select

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from tests.fixtures.parser_warning_run_snapshots.helpers import fixture_text
from tests.fixtures.parser_warning_run_snapshots.helpers import git_service_for
from tests.fixtures.parser_warning_run_snapshots.helpers import make_achat_response
from tests.fixtures.parser_warning_run_snapshots.helpers import prepared_inputs
from tests.fixtures.parser_warning_run_snapshots.helpers import wait_for_run_terminal
from tests.fixtures.parser_warning_run_snapshots.helpers import warning_workflow_yaml
from tests.fixtures.parser_warning_run_snapshots.helpers import write_corrupt_custom_tool
from tests.fixtures.parser_warning_run_snapshots.helpers import write_openai_provider
from tests.fixtures.parser_warning_run_snapshots.helpers import write_warning_soul

pytest_plugins = ["tests.fixtures.parser_warning_run_snapshots.helpers"]


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
        mock_secrets.resolve = Mock(return_value="dummy-fake-parser-warning")
        git_service = git_service_for(base_dir)
        execution_session = Session(db_engine)
        execution_service = ExecutionService(
            run_repo=RunRepository(execution_session),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
            secrets=mock_secrets,
            git_service=git_service,
            settings_repo=None,
        )
        app.state.execution_service = execution_service
        app.state.execution_session = execution_session

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
    write_openai_provider(base_dir)
    app = _build_app(db_engine, base_dir, include_execution=True)
    yield app
    app.dependency_overrides.clear()
    execution_session = getattr(app.state, "execution_session", None)
    if execution_session is not None:
        execution_session.close()


@pytest.mark.asyncio
async def test_workflow_warning_shape_run_snapshot_and_immutability(
    app_without_execution, base_dir
):
    from httpx import ASGITransport, AsyncClient
    from runsight_api.transport.deps import get_execution_service

    soul_key = "parser_warning_soul"
    write_warning_soul(base_dir, soul_key)

    warning_yaml = warning_workflow_yaml(soul_key, declare_http=False)
    fixed_yaml = warning_workflow_yaml(soul_key, declare_http=True)
    fake_execution = Mock()
    prepared = prepared_inputs({})
    fake_execution.prepare_run_inputs.return_value = prepared
    fake_execution.launch_execution = AsyncMock()
    app_without_execution.dependency_overrides[get_execution_service] = lambda request=None: (
        fake_execution
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_without_execution),
        base_url="http://localhost",
    ) as client:
        create_workflow = await client.post(
            "/api/workflows",
            json={
                "name": "Parser warning workflow",
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
                "branch": "main",
                "inputs": {},
            },
        )
        assert create_run.status_code == 200
        run_data = create_run.json()
        run_id = run_data["id"]
        assert run_data["warnings"] == warnings
        fake_execution.launch_execution.assert_called_once()
        args = fake_execution.launch_execution.call_args.args
        assert args[:3] == (run_id, workflow_id, prepared)

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

    write_corrupt_custom_tool(base_dir, "lookup_profile")

    async with AsyncClient(
        transport=ASGITransport(app=app_with_execution),
        base_url="http://localhost",
    ) as client:
        create_workflow = await client.post(
            "/api/workflows",
            json={
                "name": "Bind-loop warning workflow",
                "yaml": fixture_text("bind-loop-warning-workflow.yaml"),
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
            return_value=make_achat_response("Execution continued despite warning."),
        ):
            create_run = await client.post(
                "/api/runs",
                json={
                    "workflow_id": workflow_id,
                    "branch": "main",
                    "inputs": {},
                },
            )

            assert create_run.status_code == 200
            run_payload = create_run.json()
            run_id = run_payload["id"]
            assert run_payload["warnings"] == workflow_data["warnings"]

            terminal_run = await wait_for_run_terminal(db_engine, run_id, timeout=10.0)
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

    parent_run_id = "parser_warning_parent"
    parent_warning = {
        "message": "Parent warning should not propagate",
        "source": "tool_governance",
        "context": "parent_soul",
    }

    with Session(db_engine) as session:
        session.add(
            Run(
                id=parent_run_id,
                workflow_id="wf_parent_warning",
                workflow_name="Parent workflow",
                status=RunStatus.running,
                task_json="{}",
                branch="main",
                warnings_json=[parent_warning],
            )
        )
        session.commit()

    observer = ExecutionObserver(engine=db_engine, run_id=parent_run_id)
    observer.on_block_start(
        "Parent workflow",
        "invoke_child",
        "workflow",
        child_workflow_id="wf_child_warning",
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
        base_url="http://localhost",
    ) as client:
        child_response = await client.get(f"/api/runs/{child_run_id}")
        assert child_response.status_code == 200
        assert child_response.json()["warnings"] == []
