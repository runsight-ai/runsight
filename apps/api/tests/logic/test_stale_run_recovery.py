"""Stale pending and running runs are failed on startup."""

from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.domain.entities.run import Run, RunStatus


def _make_run(*, status: RunStatus, **overrides) -> Run:
    defaults = dict(
        id=f"stale-run-{uuid.uuid4().hex[:8]}",
        workflow_id="startup-recovery-workflow",
        workflow_name="Startup Recovery Workflow",
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


def _recover_stale_runs(engine):
    from runsight_api.main import _recover_stale_runs as impl

    impl(engine)


class TestStaleRunRecovery:
    def test_pending_and_running_runs_are_failed_on_startup(self, db_engine, seed_runs):
        runs = seed_runs(
            [
                _make_run(status=RunStatus.pending),
                _make_run(status=RunStatus.running),
            ]
        )

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            for run in runs:
                recovered = session.get(Run, run.id)
                assert recovered.status == RunStatus.failed
                assert recovered.error == "API server restarted during execution"
                assert recovered.completed_at is not None
                assert abs(recovered.completed_at - time.time()) < 10
