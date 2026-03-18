"""Red tests for RUN-145: Stale run recovery on API startup.

When the API crashes mid-execution, Run records with status=running become
zombie runs. On startup the lifespan handler must scan for these stale runs
and mark them as failed.

These tests target a `_recover_stale_runs(engine)` function that does NOT
exist yet — every test should FAIL until the implementation is written.
"""

import time
import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(*, status: RunStatus, **overrides) -> Run:
    """Build a Run with sensible defaults."""
    defaults = dict(
        id=f"run_{uuid.uuid4().hex[:8]}",
        workflow_id="wf_test",
        workflow_name="Test Workflow",
        task_json="{}",
        created_at=time.time(),
        updated_at=time.time(),
    )
    defaults.update(overrides)
    return Run(status=status, **defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine():
    """In-memory SQLite engine with Run table created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def seed_runs(db_engine):
    """Helper that inserts a list of Run objects and returns them."""

    def _seed(runs: list[Run]) -> list[Run]:
        with Session(db_engine) as session:
            for run in runs:
                session.add(run)
            session.commit()
            # Refresh so we get DB-assigned defaults
            for run in runs:
                session.refresh(run)
        return runs

    return _seed


# ---------------------------------------------------------------------------
# Import the function under test.  It does NOT exist yet, so every test
# that calls it will fail with ImportError — exactly what Red phase wants.
# ---------------------------------------------------------------------------


def _recover_stale_runs(engine):
    """Proxy that imports and delegates to the real implementation."""
    from runsight_api.main import _recover_stale_runs as impl

    impl(engine)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStaleRunRecovery:
    """Suite for _recover_stale_runs(engine)."""

    # -- Core behaviour ----------------------------------------------------

    def test_running_run_is_marked_failed(self, db_engine, seed_runs):
        """A single running run must transition to failed."""
        runs = seed_runs([_make_run(status=RunStatus.running)])

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            recovered = session.get(Run, runs[0].id)
            assert recovered.status == RunStatus.failed

    def test_error_message_is_set(self, db_engine, seed_runs):
        """The error field must contain the canonical restart message."""
        runs = seed_runs([_make_run(status=RunStatus.running)])

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            recovered = session.get(Run, runs[0].id)
            assert recovered.error == "API process restarted during execution"

    def test_completed_at_is_set(self, db_engine, seed_runs):
        """completed_at must be populated (epoch float) after recovery."""
        runs = seed_runs([_make_run(status=RunStatus.running, completed_at=None)])

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            recovered = session.get(Run, runs[0].id)
            assert recovered.completed_at is not None
            # Must be a recent epoch timestamp (within last 10 seconds)
            assert abs(recovered.completed_at - time.time()) < 10

    # -- Non-running statuses must be untouched ----------------------------

    def test_pending_run_is_not_modified(self, db_engine, seed_runs):
        """Pending runs must remain unchanged."""
        runs = seed_runs([_make_run(status=RunStatus.pending)])

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            run = session.get(Run, runs[0].id)
            assert run.status == RunStatus.pending
            assert run.error is None

    def test_completed_run_is_not_modified(self, db_engine, seed_runs):
        """Already-completed runs must remain unchanged."""
        runs = seed_runs([_make_run(status=RunStatus.completed, completed_at=time.time())])

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            run = session.get(Run, runs[0].id)
            assert run.status == RunStatus.completed
            assert run.error is None

    def test_failed_run_is_not_modified(self, db_engine, seed_runs):
        """Already-failed runs must not be overwritten."""
        original_error = "original failure reason"
        original_completed = time.time() - 3600  # 1 hour ago
        runs = seed_runs(
            [
                _make_run(
                    status=RunStatus.failed,
                    error=original_error,
                    completed_at=original_completed,
                )
            ]
        )

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            run = session.get(Run, runs[0].id)
            assert run.status == RunStatus.failed
            assert run.error == original_error
            assert run.completed_at == original_completed

    # -- Bulk & edge cases -------------------------------------------------

    def test_multiple_stale_runs_all_recovered(self, db_engine, seed_runs):
        """When several runs are stuck in running, all must be recovered."""
        runs = seed_runs(
            [
                _make_run(status=RunStatus.running),
                _make_run(status=RunStatus.running),
                _make_run(status=RunStatus.running),
            ]
        )

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            for run in runs:
                recovered = session.get(Run, run.id)
                assert recovered.status == RunStatus.failed
                assert recovered.error == "API process restarted during execution"
                assert recovered.completed_at is not None

    def test_no_running_runs_is_noop(self, db_engine, seed_runs):
        """When there are no running runs, the function must not error."""
        seed_runs(
            [
                _make_run(status=RunStatus.pending),
                _make_run(status=RunStatus.completed, completed_at=time.time()),
                _make_run(status=RunStatus.failed, error="prev", completed_at=time.time()),
            ]
        )

        # Should not raise
        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            # Verify nothing changed
            all_runs = session.query(Run).all()
            for run in all_runs:
                assert run.status != RunStatus.running

    def test_empty_database_is_noop(self, db_engine):
        """An empty database must not cause errors."""
        _recover_stale_runs(db_engine)  # should not raise

    def test_mixed_statuses_only_running_affected(self, db_engine, seed_runs):
        """In a mixed set, only running runs are modified; others stay intact."""
        pending = _make_run(status=RunStatus.pending)
        running = _make_run(status=RunStatus.running)
        completed = _make_run(status=RunStatus.completed, completed_at=time.time())
        failed = _make_run(status=RunStatus.failed, error="boom", completed_at=time.time())

        seed_runs([pending, running, completed, failed])

        _recover_stale_runs(db_engine)

        with Session(db_engine) as session:
            assert session.get(Run, pending.id).status == RunStatus.pending
            assert session.get(Run, running.id).status == RunStatus.failed
            assert session.get(Run, running.id).error == "API process restarted during execution"
            assert session.get(Run, completed.id).status == RunStatus.completed
            assert session.get(Run, failed.id).status == RunStatus.failed
            assert session.get(Run, failed.id).error == "boom"  # original, not overwritten
