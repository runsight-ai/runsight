"""Red tests for RUN-772: fail closed when the execution runtime is unavailable.

POST /api/runs must not create a durable pending run when the execution
runtime is missing, and it must surface failed launch outcomes instead of
returning the stale pending response.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.run_service import RunService
from runsight_api.main import app
from runsight_api.transport.deps import get_execution_service, get_run_service

client = TestClient(app)


def assert_runsight_error_shape(response, expected_status: int):
    """Verify the response uses the RunsightError envelope."""
    assert response.status_code == expected_status
    body = response.json()
    assert "error" in body
    assert "error_code" in body
    assert "status_code" in body
    assert "detail" not in body
    return body


def _make_mock_run(run_id: str = "run_772"):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "Test Workflow"
    mock_run.status = RunStatus.pending
    mock_run.error = None
    mock_run.started_at = None
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 123.0
    mock_run.branch = "main"
    mock_run.source = "manual"
    mock_run.commit_sha = None
    mock_run.run_number = None
    mock_run.eval_pass_pct = None
    mock_run.regression_count = None
    mock_run.parent_run_id = None
    mock_run.root_run_id = None
    mock_run.depth = 0
    return mock_run


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def workflow_repo():
    workflow = Mock()
    workflow.id = "wf_1"
    workflow.name = "Test Workflow"
    repo = Mock()
    repo.get_by_id.return_value = workflow
    return repo


@pytest.fixture()
def run_service(db_engine, workflow_repo):
    session = Session(db_engine)
    service = RunService(RunRepository(session), workflow_repo)
    try:
        yield service
    finally:
        session.close()


class TestFailClosedRunCreation:
    def test_post_runs_without_execution_runtime_returns_service_unavailable(self):
        """POST /api/runs must fail before creating a run when execution is unavailable."""
        mock_run_service = Mock()
        mock_run_service.create_run.return_value = _make_mock_run()

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: None
        try:
            response = client.post(
                "/api/runs",
                json={"workflow_id": "wf_1", "task_data": {"instruction": "go"}},
            )

            body = assert_runsight_error_shape(response, 503)
            assert body["error_code"] == "SERVICE_UNAVAILABLE"
            mock_run_service.create_run.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_post_runs_launch_exception_marks_created_run_failed(self, db_engine, run_service):
        """A launch exception must not leave the created run pending."""

        mock_exec_service = Mock()
        mock_exec_service.launch_execution = AsyncMock(
            side_effect=RuntimeError("launch failed after run creation")
        )

        app.dependency_overrides[get_run_service] = lambda: run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service
        try:
            response = client.post(
                "/api/runs",
                json={"workflow_id": "wf_1", "task_data": {"instruction": "go"}},
            )

            body = assert_runsight_error_shape(response, 500)
            assert body["error_code"] == "RUN_FAILED"

            with Session(db_engine) as session:
                run = session.exec(select(Run)).one()
                assert run.status == RunStatus.failed
                assert run.completed_at is not None
                assert run.error is not None
        finally:
            app.dependency_overrides.clear()

    def test_post_runs_detects_failed_lifecycle_outcome(self, db_engine, run_service):
        """If launch marks the run failed without raising, the route must return a failure."""

        async def _mark_failed(run_id, workflow_id, task_data, branch="main"):
            with Session(db_engine) as session:
                run = session.get(Run, run_id)
                run.status = RunStatus.failed
                run.error = "workflow failed during launch"
                run.completed_at = time.time()
                session.add(run)
                session.commit()

        mock_exec_service = Mock()
        mock_exec_service.launch_execution = AsyncMock(side_effect=_mark_failed)

        app.dependency_overrides[get_run_service] = lambda: run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service
        try:
            response = client.post(
                "/api/runs",
                json={"workflow_id": "wf_1", "task_data": {"instruction": "go"}},
            )

            body = assert_runsight_error_shape(response, 500)
            assert body["error_code"] == "RUN_FAILED"

            with Session(db_engine) as session:
                run = session.exec(select(Run)).one()
                assert run.status == RunStatus.failed
                assert run.completed_at is not None
                assert run.error == "workflow failed during launch"
        finally:
            app.dependency_overrides.clear()
