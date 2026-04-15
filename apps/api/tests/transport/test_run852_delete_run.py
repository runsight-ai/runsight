"""Red tests for RUN-852: DELETE /api/runs/{id} endpoint.

These tests are expected to FAIL until the endpoint, service method, and
repository method are implemented.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.run_service import RunService
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

client = TestClient(app)


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
    workflow.id = "wf_852"
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


def _create_run_via_repo(db_engine) -> str:
    """Insert a minimal Run record directly and return its id."""
    run_id = "run_852_test"
    with Session(db_engine) as session:
        run = Run(
            id=run_id,
            workflow_id="wf_852",
            workflow_name="Test Workflow",
            status=RunStatus.completed,
            task_json="{}",
        )
        session.add(run)
        session.commit()
    return run_id


def _create_active_run_via_repo(db_engine, status: RunStatus = RunStatus.running) -> str:
    """Insert a minimal active Run record directly and return its id."""
    run_id = "run_852_active"
    with Session(db_engine) as session:
        run = Run(
            id=run_id,
            workflow_id="wf_852",
            workflow_name="Test Workflow",
            status=status,
            task_json="{}",
        )
        session.add(run)
        session.commit()
    return run_id


class TestDeleteRunEndpoint:
    def test_delete_run_returns_200_with_id_and_deleted(self, db_engine, run_service):
        """DELETE /api/runs/{id} must return 200 with {id, deleted: true}."""
        run_id = _create_run_via_repo(db_engine)

        app.dependency_overrides[get_run_service] = lambda: run_service
        try:
            response = client.delete(f"/api/runs/{run_id}")

            assert response.status_code == 200
            body = response.json()
            assert body["id"] == run_id
            assert body["deleted"] is True
        finally:
            app.dependency_overrides.clear()

    def test_delete_run_404_for_nonexistent(self, run_service):
        """DELETE /api/runs/{id} must return 404 when run does not exist."""
        app.dependency_overrides[get_run_service] = lambda: run_service
        try:
            response = client.delete("/api/runs/run_does_not_exist_852")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_delete_run_soft_deletes_from_database(self, db_engine, run_service):
        """After DELETE, the run is soft-deleted (deleted_at set) and not returned by get_run."""
        run_id = _create_run_via_repo(db_engine)

        app.dependency_overrides[get_run_service] = lambda: run_service
        try:
            delete_response = client.delete(f"/api/runs/{run_id}")
            assert delete_response.status_code == 200

            # The run record still exists in DB but has deleted_at set
            with Session(db_engine) as session:
                row = session.get(Run, run_id)
            assert row is not None, "Soft-deleted run must still exist in DB"
            assert row.deleted_at is not None, "deleted_at must be set after soft delete"

            # But the repository's get_run filters it out
            result = run_service.get_run(run_id)
            assert result is None, "get_run must not return soft-deleted runs"
        finally:
            app.dependency_overrides.clear()

    def test_delete_run_response_shape(self, db_engine, run_service):
        """DELETE response must contain exactly 'id' and 'deleted' keys — no extra fields."""
        run_id = _create_run_via_repo(db_engine)

        app.dependency_overrides[get_run_service] = lambda: run_service
        try:
            response = client.delete(f"/api/runs/{run_id}")

            assert response.status_code == 200
            body = response.json()
            assert set(body.keys()) == {"id", "deleted"}
        finally:
            app.dependency_overrides.clear()

    def test_delete_run_rejects_active_run(self, db_engine, run_service):
        """DELETE must not remove pending/running runs; cancel first to preserve execution state."""
        run_id = _create_active_run_via_repo(db_engine)

        app.dependency_overrides[get_run_service] = lambda: run_service
        try:
            response = client.delete(f"/api/runs/{run_id}")

            assert response.status_code == 409
            with Session(db_engine) as session:
                active = session.get(Run, run_id)
            assert active is not None
            assert active.status == RunStatus.running
        finally:
            app.dependency_overrides.clear()
