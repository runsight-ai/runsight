"""Runtime startup tests for ghost-run cleanup ownership."""

from __future__ import annotations

import time
import uuid
from unittest.mock import Mock

from sqlalchemy.pool import StaticPool
import pytest
from sqlmodel import SQLModel, Session, create_engine
from starlette.testclient import TestClient

from runsight_api.domain.entities.run import Run, RunStatus


def _make_run(*, status: RunStatus, **overrides) -> Run:
    defaults = dict(
        id=f"run_{uuid.uuid4().hex[:8]}",
        workflow_id="startup-cleanup-workflow",
        workflow_name="Startup Cleanup Workflow",
        task_json="{}",
        branch="main",
        created_at=time.time(),
        updated_at=time.time(),
    )
    defaults.update(overrides)
    return Run(status=status, **defaults)


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
def seed_runs(db_engine):
    def _seed(runs: list[Run]) -> list[Run]:
        with Session(db_engine) as session:
            for run in runs:
                session.add(run)
            session.commit()
            for run in runs:
                session.refresh(run)
        return runs

    return _seed


class TestStartupGhostRunCleanupOwnership:
    def test_lifespan_uses_execution_collaborator_to_clean_stale_runs(
        self, monkeypatch, tmp_path, db_engine, seed_runs
    ):
        from runsight_api import main as main_module

        stale_runs = seed_runs(
            [
                _make_run(status=RunStatus.pending),
                _make_run(status=RunStatus.running),
            ]
        )
        cleanup_called = False

        class FakeExecutionService:
            def __init__(self, *args, **kwargs):
                pass

            def fail_ghost_runs(self) -> None:
                nonlocal cleanup_called
                cleanup_called = True
                with Session(db_engine) as session:
                    for run in stale_runs:
                        stored = session.get(Run, run.id)
                        stored.status = RunStatus.failed
                        stored.error = "API server restarted during execution"
                        stored.completed_at = time.time()
                        session.add(stored)
                    session.commit()

        monkeypatch.setattr(main_module, "engine", db_engine)
        monkeypatch.setattr(main_module, "ExecutionService", FakeExecutionService)
        monkeypatch.setattr(main_module.app_settings, "base_path", str(tmp_path))
        monkeypatch.setattr(main_module, "_build_alembic_config", lambda: Mock())
        monkeypatch.setattr(main_module.alembic_command, "upgrade", lambda *args, **kwargs: None)
        monkeypatch.setattr(main_module, "_ensure_sqlite_columns", lambda engine: None)

        app = main_module.create_app()

        with TestClient(app):
            pass

        assert cleanup_called, (
            "Startup should route stale-run cleanup through the execution "
            "collaborator during lifespan initialization."
        )
        with Session(db_engine) as session:
            for run in stale_runs:
                recovered = session.get(Run, run.id)
                assert recovered.status == RunStatus.failed
                assert recovered.error == "API server restarted during execution"
                assert recovered.completed_at is not None

    def test_recover_stale_runs_fails_active_runs_and_preserves_terminal_runs(
        self,
        db_engine,
        seed_runs,
    ):
        from runsight_api.main import _recover_stale_runs

        original_completed_at = time.time() - 3600
        pending = _make_run(status=RunStatus.pending)
        running = _make_run(status=RunStatus.running)
        completed = _make_run(status=RunStatus.completed, completed_at=original_completed_at)
        failed = _make_run(
            status=RunStatus.failed,
            error="original failure",
            completed_at=original_completed_at,
        )
        seed_runs([pending, running, completed, failed])

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            recovered_pending = session.get(Run, pending.id)
            recovered_running = session.get(Run, running.id)
            untouched_completed = session.get(Run, completed.id)
            untouched_failed = session.get(Run, failed.id)

            assert recovered_pending.status == RunStatus.failed
            assert recovered_pending.error == "API server restarted during execution"
            assert recovered_pending.completed_at is not None
            assert abs(recovered_pending.completed_at - time.time()) < 10

            assert recovered_running.status == RunStatus.failed
            assert recovered_running.error == "API server restarted during execution"
            assert recovered_running.completed_at is not None
            assert abs(recovered_running.completed_at - time.time()) < 10

            assert untouched_completed.status == RunStatus.completed
            assert untouched_completed.error is None
            assert untouched_completed.completed_at == original_completed_at

            assert untouched_failed.status == RunStatus.failed
            assert untouched_failed.error == "original failure"
            assert untouched_failed.completed_at == original_completed_at
