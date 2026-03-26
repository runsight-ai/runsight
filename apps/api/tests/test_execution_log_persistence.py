"""Red tests for RUN-291: execution_log persistence via ExecutionObserver high-water mark.

ExecutionObserver must persist WorkflowState.execution_log entries to the
LogEntry table using a high-water mark (_log_hwm) so that each
on_block_complete call only inserts *new* entries since the last flush.
on_workflow_complete must do a final flush for any remaining entries.

Context-binding functions (bind_execution_context, bind_block_context, etc.)
must be called at the appropriate lifecycle points.

All tests target behaviour that does NOT exist yet — every test should FAIL
until the implementation is written.
"""

import time
import uuid
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_core.state import WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(engine, run_id: str) -> Run:
    """Insert a Run row so FK-like lookups in the observer succeed."""
    run = Run(
        id=run_id,
        workflow_id="wf_test",
        workflow_name="test-workflow",
        status=RunStatus.running,
        task_json="{}",
        created_at=time.time(),
        updated_at=time.time(),
    )
    with Session(engine) as session:
        session.add(run)
        session.commit()
    return run


def _state_with_log(entries: list[dict]) -> WorkflowState:
    """Build a WorkflowState with a pre-populated execution_log."""
    return WorkflowState(execution_log=entries)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine():
    """In-memory SQLite engine with all tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def run_id():
    return f"run_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def observer(db_engine, run_id):
    """ExecutionObserver wired to the in-memory DB."""
    _make_run(db_engine, run_id)
    return ExecutionObserver(engine=db_engine, run_id=run_id)


# ---------------------------------------------------------------------------
# Tests: _log_hwm attribute and _persist_execution_log method
# ---------------------------------------------------------------------------


class TestHighWaterMarkSetup:
    """The observer must expose _log_hwm and _persist_execution_log."""

    def test_log_hwm_initialized_to_zero(self, observer):
        """_log_hwm must start at 0."""
        assert observer._log_hwm == 0

    def test_persist_execution_log_method_exists(self, observer):
        """_persist_execution_log must be a callable method."""
        assert callable(getattr(observer, "_persist_execution_log", None))


# ---------------------------------------------------------------------------
# Tests: on_block_complete persists new execution_log entries
# ---------------------------------------------------------------------------


class TestOnBlockCompletePersistsLog:
    """on_block_complete must persist new execution_log entries as LogEntry rows."""

    def test_new_entries_persisted_on_block_complete(self, db_engine, observer, run_id):
        """After on_block_complete, new execution_log entries appear as LogEntry rows."""
        log_entries = [
            {"role": "system", "content": "Starting block"},
            {"role": "assistant", "content": "Block output"},
        ]
        state = _state_with_log(log_entries)

        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_a",
            block_type="llm",
            duration_s=1.0,
            state=state,
        )

        with Session(db_engine) as session:
            rows = session.exec(
                select(LogEntry).where(
                    LogEntry.run_id == run_id,
                    LogEntry.level == "trace",
                )
            ).all()
            assert len(rows) >= 2

    def test_persisted_entries_have_correct_run_id(self, db_engine, observer, run_id):
        """Each LogEntry row must carry the observer's run_id."""
        state = _state_with_log([{"role": "system", "content": "hello"}])

        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_a",
            block_type="llm",
            duration_s=0.5,
            state=state,
        )

        with Session(db_engine) as session:
            rows = session.exec(select(LogEntry).where(LogEntry.level == "trace")).all()
            assert len(rows) >= 1
            assert all(row.run_id == run_id for row in rows)

    def test_persisted_entries_have_correct_node_id(self, db_engine, observer, run_id):
        """Each LogEntry row must carry the block_id as node_id."""
        state = _state_with_log([{"role": "user", "content": "ping"}])

        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_b",
            block_type="llm",
            duration_s=0.3,
            state=state,
        )

        with Session(db_engine) as session:
            rows = session.exec(select(LogEntry).where(LogEntry.level == "trace")).all()
            assert len(rows) >= 1
            assert all(row.node_id == "block_b" for row in rows)

    def test_persisted_entries_have_level_trace(self, db_engine, observer, run_id):
        """LogEntry rows from execution_log must have level='trace'."""
        state = _state_with_log([{"role": "system", "content": "trace me"}])

        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_c",
            block_type="llm",
            duration_s=0.1,
            state=state,
        )

        with Session(db_engine) as session:
            rows = session.exec(
                select(LogEntry).where(
                    LogEntry.run_id == run_id,
                    LogEntry.level == "trace",
                )
            ).all()
            # At least the one execution_log entry should be trace
            assert len(rows) >= 1

    def test_persisted_entry_message_contains_log_content(self, db_engine, observer, run_id):
        """The LogEntry.message must contain the serialized execution_log entry."""
        entry = {"role": "assistant", "content": "important output"}
        state = _state_with_log([entry])

        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_d",
            block_type="llm",
            duration_s=0.2,
            state=state,
        )

        with Session(db_engine) as session:
            rows = session.exec(select(LogEntry).where(LogEntry.level == "trace")).all()
            messages = [row.message for row in rows]
            # The entry must be JSON-serialized in at least one message
            assert any("important output" in msg for msg in messages)


# ---------------------------------------------------------------------------
# Tests: high-water mark advances (no duplicates)
# ---------------------------------------------------------------------------


class TestHighWaterMarkAdvances:
    """Calling on_block_complete twice with a growing log must not duplicate entries."""

    def test_no_duplicate_entries_across_two_block_completes(self, db_engine, observer, run_id):
        """Two consecutive on_block_complete calls with a growing log produce no duplicates."""
        # First block: 2 log entries
        state1 = _state_with_log(
            [
                {"role": "system", "content": "entry_1"},
                {"role": "assistant", "content": "entry_2"},
            ]
        )
        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_a",
            block_type="llm",
            duration_s=0.5,
            state=state1,
        )

        # Second block: log grew to 4 entries (2 old + 2 new)
        state2 = _state_with_log(
            [
                {"role": "system", "content": "entry_1"},
                {"role": "assistant", "content": "entry_2"},
                {"role": "user", "content": "entry_3"},
                {"role": "assistant", "content": "entry_4"},
            ]
        )
        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_b",
            block_type="llm",
            duration_s=0.3,
            state=state2,
        )

        with Session(db_engine) as session:
            trace_rows = session.exec(
                select(LogEntry).where(
                    LogEntry.run_id == run_id,
                    LogEntry.level == "trace",
                )
            ).all()
            # Exactly 4 trace entries (no duplicates of entry_1, entry_2)
            assert len(trace_rows) == 4

    def test_hwm_advances_after_block_complete(self, observer):
        """_log_hwm must advance after on_block_complete."""
        state = _state_with_log(
            [
                {"role": "system", "content": "a"},
                {"role": "assistant", "content": "b"},
            ]
        )
        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_x",
            block_type="llm",
            duration_s=0.1,
            state=state,
        )
        assert observer._log_hwm == 2


# ---------------------------------------------------------------------------
# Tests: on_workflow_complete does final flush
# ---------------------------------------------------------------------------


class TestWorkflowCompleteFinalFlush:
    """on_workflow_complete must flush any remaining execution_log entries."""

    def test_final_flush_persists_remaining_entries(self, db_engine, observer, run_id):
        """Entries added after the last on_block_complete are flushed on workflow_complete."""
        # Simulate: on_block_complete saw 2 entries
        state_mid = _state_with_log(
            [
                {"role": "system", "content": "mid_1"},
                {"role": "assistant", "content": "mid_2"},
            ]
        )
        observer.on_block_complete(
            workflow_name="test-workflow",
            block_id="block_a",
            block_type="llm",
            duration_s=0.5,
            state=state_mid,
        )

        # Now workflow completes with 1 extra entry (index 2)
        state_final = _state_with_log(
            [
                {"role": "system", "content": "mid_1"},
                {"role": "assistant", "content": "mid_2"},
                {"role": "system", "content": "final_entry"},
            ]
        )
        observer.on_workflow_complete(
            workflow_name="test-workflow",
            state=state_final,
            duration_s=2.0,
        )

        with Session(db_engine) as session:
            trace_rows = session.exec(
                select(LogEntry).where(
                    LogEntry.run_id == run_id,
                    LogEntry.level == "trace",
                )
            ).all()
            # 2 from block_complete + 1 from workflow_complete final flush = 3
            assert len(trace_rows) == 3
            messages = [row.message for row in trace_rows]
            assert any("final_entry" in msg for msg in messages)


# ---------------------------------------------------------------------------
# Tests: DB failure does not raise
# ---------------------------------------------------------------------------


class TestDbFailureSwallowed:
    """A DB error during _persist_execution_log must be swallowed."""

    def test_persist_execution_log_does_not_raise_on_db_error(self, observer):
        """If the DB write fails, _persist_execution_log must not propagate the exception."""
        state = _state_with_log([{"role": "system", "content": "boom"}])

        # Patch Session to blow up on add
        with patch(
            "runsight_api.logic.observers.execution_observer.Session",
            side_effect=Exception("DB is down"),
        ):
            # Must not raise
            observer._persist_execution_log(state, node_id="block_err")


# ---------------------------------------------------------------------------
# Tests: context variable binding
# ---------------------------------------------------------------------------


class TestContextVarBinding:
    """Observer lifecycle methods must call the context binding functions."""

    def test_on_workflow_start_binds_execution_context(self, observer, run_id):
        """on_workflow_start must call bind_execution_context with run_id and workflow_name."""
        state = WorkflowState()
        with patch(
            "runsight_api.logic.observers.execution_observer.bind_execution_context"
        ) as mock_bind:
            observer.on_workflow_start(
                workflow_name="test-workflow",
                state=state,
            )
            mock_bind.assert_called_once_with(run_id=run_id, workflow_name="test-workflow")

    def test_on_block_start_binds_block_context(self, observer):
        """on_block_start must call bind_block_context with the block_id."""
        with patch(
            "runsight_api.logic.observers.execution_observer.bind_block_context"
        ) as mock_bind:
            observer.on_block_start(
                workflow_name="test-workflow",
                block_id="block_z",
                block_type="llm",
            )
            mock_bind.assert_called_once_with("block_z")

    def test_on_block_complete_clears_block_context(self, observer):
        """on_block_complete must call clear_block_context."""
        state = WorkflowState()
        with patch(
            "runsight_api.logic.observers.execution_observer.clear_block_context"
        ) as mock_clear:
            observer.on_block_complete(
                workflow_name="test-workflow",
                block_id="block_z",
                block_type="llm",
                duration_s=0.1,
                state=state,
            )
            mock_clear.assert_called_once()

    def test_on_workflow_complete_clears_execution_context(self, observer):
        """on_workflow_complete must call clear_execution_context."""
        state = WorkflowState()
        with patch(
            "runsight_api.logic.observers.execution_observer.clear_execution_context"
        ) as mock_clear:
            observer.on_workflow_complete(
                workflow_name="test-workflow",
                state=state,
                duration_s=1.0,
            )
            mock_clear.assert_called_once()
