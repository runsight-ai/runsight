"""Red tests for RUN-128: ExecutionObserver — core WorkflowObserver → API DB persistence.

Tests target ExecutionObserver at:
  apps/api/src/runsight_api/logic/observers/execution_observer.py

All tests should FAIL until the implementation exists.
"""

import asyncio
import json
import time
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.domain.entities.log import LogEntry
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.observer import WorkflowObserver


# ---------------------------------------------------------------------------
# Deferred import helper (module does not exist yet)
# ---------------------------------------------------------------------------


def _import_execution_observer():
    from runsight_api.logic.observers.execution_observer import ExecutionObserver

    return ExecutionObserver


# ---------------------------------------------------------------------------
# 1. Class existence and protocol conformance
# ---------------------------------------------------------------------------


class TestExecutionObserverExists:
    def test_implements_workflow_observer_protocol(self):
        """ExecutionObserver satisfies the WorkflowObserver runtime_checkable protocol."""
        ExecutionObserver = _import_execution_observer()
        engine = create_engine("sqlite:///:memory:")
        obs = ExecutionObserver(engine=engine, run_id="run_1")
        assert isinstance(obs, WorkflowObserver)

    def test_accepts_engine_and_run_id(self):
        """Constructor accepts engine and run_id positional/keyword args."""
        ExecutionObserver = _import_execution_observer()
        engine = create_engine("sqlite:///:memory:")
        obs = ExecutionObserver(engine=engine, run_id="run_test")
        assert obs.run_id == "run_test"


# ---------------------------------------------------------------------------
# Shared DB fixture — in-memory SQLite with Run/RunNode/LogEntry tables
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine with all needed tables."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def seed_run(db_engine):
    """Insert a pending Run record and return (engine, run_id)."""
    run_id = "run_test_128"
    with Session(db_engine) as session:
        run = Run(
            id=run_id,
            workflow_id="wf_1",
            workflow_name="test_workflow",
            status=RunStatus.running,
            task_json="{}",
        )
        session.add(run)
        session.commit()
    return db_engine, run_id


@pytest.fixture
def observer(seed_run):
    """Create an ExecutionObserver pointing at the seeded DB."""
    engine, run_id = seed_run
    ExecutionObserver = _import_execution_observer()
    return ExecutionObserver(engine=engine, run_id=run_id), engine, run_id


# ---------------------------------------------------------------------------
# 2. on_workflow_start
# ---------------------------------------------------------------------------


class TestOnWorkflowStart:
    def test_updates_run_status_to_running(self, observer):
        """on_workflow_start UPDATEs Run.status to 'running'."""
        obs, engine, run_id = observer
        state = WorkflowState()
        obs.on_workflow_start("test_workflow", state)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.running

    def test_sets_started_at(self, observer):
        """on_workflow_start sets Run.started_at to current time."""
        obs, engine, run_id = observer
        before = time.time()
        obs.on_workflow_start("test_workflow", WorkflowState())
        after = time.time()

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.started_at is not None
            assert before <= run.started_at <= after


# ---------------------------------------------------------------------------
# 3. on_block_start
# ---------------------------------------------------------------------------


class TestOnBlockStart:
    def test_inserts_run_node_with_running_status(self, observer):
        """on_block_start INSERTs a RunNode with status='running'."""
        obs, engine, run_id = observer
        obs.on_block_start("test_workflow", "block_a", "LinearBlock")

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node is not None
            assert node.status == "running"
            assert node.block_type == "LinearBlock"
            assert node.run_id == run_id
            assert node.node_id == "block_a"

    def test_inserts_log_entry(self, observer):
        """on_block_start INSERTs a LogEntry for the block start event."""
        obs, engine, run_id = observer
        obs.on_block_start("test_workflow", "block_a", "LinearBlock")

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            assert len(logs) >= 1
            # Log message should be structured JSON
            msg = json.loads(logs[0].message)
            assert msg["event"] == "block_start"
            assert msg["block_id"] == "block_a"

    def test_sets_started_at_on_node(self, observer):
        """on_block_start sets RunNode.started_at."""
        obs, engine, run_id = observer
        before = time.time()
        obs.on_block_start("test_workflow", "block_a", "LinearBlock")

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.started_at is not None
            assert node.started_at >= before


# ---------------------------------------------------------------------------
# 4. on_block_complete
# ---------------------------------------------------------------------------


class TestOnBlockComplete:
    def _start_and_complete(self, obs, engine, run_id, cost=0.05, tokens=1500):
        """Helper: start then complete a block."""
        obs.on_block_start("wf", "block_a", "LinearBlock")
        state = WorkflowState(total_cost_usd=cost, total_tokens=tokens)
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, state)
        return state

    def test_updates_node_status_to_completed(self, observer):
        """on_block_complete UPDATEs RunNode.status to 'completed'."""
        obs, engine, run_id = observer
        self._start_and_complete(obs, engine, run_id)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.status == "completed"

    def test_sets_duration(self, observer):
        """on_block_complete stores duration_s on RunNode."""
        obs, engine, run_id = observer
        self._start_and_complete(obs, engine, run_id)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.duration_s is not None
            assert node.duration_s == pytest.approx(2.5, abs=0.1)

    def test_stores_cost_delta(self, observer):
        """on_block_complete computes cost_delta from cumulative state cost."""
        obs, engine, run_id = observer
        # First block: cumulative cost = 0.05
        obs.on_block_start("wf", "block_a", "LinearBlock")
        state1 = WorkflowState(total_cost_usd=0.05, total_tokens=500)
        obs.on_block_complete("wf", "block_a", "LinearBlock", 1.0, state1)

        # Second block: cumulative cost = 0.12 → delta = 0.07
        obs.on_block_start("wf", "block_b", "LinearBlock")
        state2 = WorkflowState(total_cost_usd=0.12, total_tokens=1200)
        obs.on_block_complete("wf", "block_b", "LinearBlock", 1.5, state2)

        with Session(engine) as session:
            node_a = session.get(RunNode, f"{run_id}:block_a")
            node_b = session.get(RunNode, f"{run_id}:block_b")
            assert node_a.cost_usd == pytest.approx(0.05, abs=0.001)
            assert node_b.cost_usd == pytest.approx(0.07, abs=0.001)

    def test_stores_token_breakdown(self, observer):
        """on_block_complete stores token info in RunNode.tokens."""
        obs, engine, run_id = observer
        self._start_and_complete(obs, engine, run_id, cost=0.05, tokens=1500)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.tokens is not None
            assert node.tokens.get("total", 0) > 0

    def test_stores_output(self, observer):
        """on_block_complete stores block output from state.results in RunNode.output."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_a", "LinearBlock")
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=500,
            results={"block_a": BlockResult(output="The analysis is complete.")},
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 1.0, state)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.output is not None
            assert "analysis" in node.output

    def test_inserts_log_entry(self, observer):
        """on_block_complete INSERTs a LogEntry with structured JSON message."""
        obs, engine, run_id = observer
        self._start_and_complete(obs, engine, run_id)

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            complete_logs = [entry for entry in logs if "block_complete" in entry.message]
            assert len(complete_logs) >= 1
            msg = json.loads(complete_logs[0].message)
            assert msg["event"] == "block_complete"
            assert msg["block_id"] == "block_a"

    def test_zero_cost_block_still_writes_node(self, observer):
        """Block with zero cost still creates RunNode with cost_delta=0."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_zero", "LinearBlock")
        state = WorkflowState(total_cost_usd=0.0, total_tokens=0)
        obs.on_block_complete("wf", "block_zero", "LinearBlock", 0.1, state)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_zero")
            assert node is not None
            assert node.status == "completed"
            assert node.cost_usd == 0.0

    def test_completed_at_set(self, observer):
        """on_block_complete sets RunNode.completed_at."""
        obs, engine, run_id = observer
        self._start_and_complete(obs, engine, run_id)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.completed_at is not None


# ---------------------------------------------------------------------------
# 5. on_block_error
# ---------------------------------------------------------------------------


class TestOnBlockError:
    def test_updates_node_status_to_failed(self, observer):
        """on_block_error UPDATEs RunNode.status to 'failed'."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_err", "LinearBlock")
        err = RuntimeError("LLM call failed")
        obs.on_block_error("wf", "block_err", "LinearBlock", 1.0, err)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_err")
            assert node.status == "failed"

    def test_stores_error_message(self, observer):
        """on_block_error stores error string in RunNode.error."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_err", "LinearBlock")
        err = ValueError("bad input")
        obs.on_block_error("wf", "block_err", "LinearBlock", 0.5, err)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_err")
            assert node.error is not None
            assert "bad input" in node.error

    def test_stores_error_traceback(self, observer):
        """on_block_error stores traceback.format_exception() in RunNode.error_traceback."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_err", "LinearBlock")
        try:
            raise RuntimeError("traceback test")
        except RuntimeError as e:
            obs.on_block_error("wf", "block_err", "LinearBlock", 0.5, e)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_err")
            assert node.error_traceback is not None
            assert "traceback test" in node.error_traceback
            assert "RuntimeError" in node.error_traceback

    def test_inserts_log_entry(self, observer):
        """on_block_error INSERTs a LogEntry with level='error'."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_err", "LinearBlock")
        err = RuntimeError("boom")
        obs.on_block_error("wf", "block_err", "LinearBlock", 1.0, err)

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            error_logs = [entry for entry in logs if entry.level == "error"]
            assert len(error_logs) >= 1


# ---------------------------------------------------------------------------
# 6. on_workflow_complete
# ---------------------------------------------------------------------------


class TestOnWorkflowComplete:
    def test_updates_run_status_to_completed(self, observer):
        """on_workflow_complete UPDATEs Run.status to 'completed'."""
        obs, engine, run_id = observer
        state = WorkflowState(total_cost_usd=0.10, total_tokens=3000)
        obs.on_workflow_complete("wf", state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.completed

    def test_sets_completed_at(self, observer):
        """on_workflow_complete sets Run.completed_at."""
        obs, engine, run_id = observer
        obs.on_workflow_complete("wf", WorkflowState(), 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.completed_at is not None

    def test_sets_duration_s(self, observer):
        """on_workflow_complete sets Run.duration_s."""
        obs, engine, run_id = observer
        obs.on_workflow_complete("wf", WorkflowState(), 12.34)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.duration_s == pytest.approx(12.34, abs=0.1)

    def test_sets_total_cost_and_tokens(self, observer):
        """on_workflow_complete sets Run.total_cost_usd and Run.total_tokens from state."""
        obs, engine, run_id = observer
        state = WorkflowState(total_cost_usd=1.23, total_tokens=45000)
        obs.on_workflow_complete("wf", state, 10.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.total_cost_usd == pytest.approx(1.23, abs=0.01)
            assert run.total_tokens == 45000

    def test_stores_results_json(self, observer):
        """on_workflow_complete stores state.results as Run.results_json."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={
                "block_a": BlockResult(output="output_a"),
                "block_b": BlockResult(output="output_b"),
            }
        )
        obs.on_workflow_complete("wf", state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.results_json is not None
            parsed = json.loads(run.results_json)
            assert parsed["block_a"]["output"] == "output_a"

    def test_inserts_log_entry(self, observer):
        """on_workflow_complete INSERTs a LogEntry."""
        obs, engine, run_id = observer
        obs.on_workflow_complete("wf", WorkflowState(), 5.0)

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            assert len(logs) >= 1
            msg = json.loads(logs[0].message)
            assert msg["event"] == "workflow_complete"


# ---------------------------------------------------------------------------
# 7. on_workflow_error
# ---------------------------------------------------------------------------


class TestOnWorkflowError:
    def test_updates_run_status_to_failed(self, observer):
        """on_workflow_error UPDATEs Run.status to 'failed'."""
        obs, engine, run_id = observer
        err = RuntimeError("workflow exploded")
        obs.on_workflow_error("wf", err, 3.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.failed

    def test_stores_error_message(self, observer):
        """on_workflow_error stores error string in Run.error."""
        obs, engine, run_id = observer
        err = ValueError("bad config")
        obs.on_workflow_error("wf", err, 1.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.error is not None
            assert "bad config" in run.error

    def test_stores_error_traceback_on_run(self, observer):
        """on_workflow_error stores traceback in Run.error_traceback."""
        obs, engine, run_id = observer
        try:
            raise RuntimeError("workflow traceback test")
        except RuntimeError as e:
            obs.on_workflow_error("wf", e, 2.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.error_traceback is not None
            assert "workflow traceback test" in run.error_traceback

    def test_sets_completed_at_and_duration(self, observer):
        """on_workflow_error sets Run.completed_at and Run.duration_s."""
        obs, engine, run_id = observer
        obs.on_workflow_error("wf", RuntimeError("x"), 7.77)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.completed_at is not None
            assert run.duration_s == pytest.approx(7.77, abs=0.1)

    def test_cancelled_error_sets_cancelled_status(self, observer):
        """CancelledError in on_workflow_error sets Run.status to 'cancelled'."""
        obs, engine, run_id = observer
        err = asyncio.CancelledError()
        obs.on_workflow_error("wf", err, 1.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.cancelled

    def test_inserts_log_entry_for_error(self, observer):
        """on_workflow_error INSERTs a LogEntry with level='error'."""
        obs, engine, run_id = observer
        obs.on_workflow_error("wf", RuntimeError("oops"), 1.0)

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            error_logs = [entry for entry in logs if entry.level == "error"]
            assert len(error_logs) >= 1

    def test_inserts_log_entry_for_cancelled(self, observer):
        """CancelledError still inserts a log entry (level='warning' or 'info')."""
        obs, engine, run_id = observer
        obs.on_workflow_error("wf", asyncio.CancelledError(), 1.0)

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            assert len(logs) >= 1


# ---------------------------------------------------------------------------
# 8. Cost delta calculation
# ---------------------------------------------------------------------------


class TestCostDeltaCalculation:
    def test_first_block_delta_equals_cumulative(self, observer):
        """First block's cost_delta equals the cumulative cost (no prior blocks)."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "b1", "LinearBlock")
        obs.on_block_complete(
            "wf", "b1", "LinearBlock", 1.0, WorkflowState(total_cost_usd=0.10, total_tokens=500)
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:b1")
            assert node.cost_usd == pytest.approx(0.10, abs=0.001)

    def test_sequential_blocks_compute_incremental_delta(self, observer):
        """Three sequential blocks each get correct incremental cost delta."""
        obs, engine, run_id = observer
        costs = [0.10, 0.25, 0.25]  # cumulative: 0.10, 0.25, 0.25
        # Expected deltas: 0.10, 0.15, 0.00

        for i, cum_cost in enumerate(costs):
            bid = f"b{i}"
            obs.on_block_start("wf", bid, "LinearBlock")
            obs.on_block_complete(
                "wf",
                bid,
                "LinearBlock",
                1.0,
                WorkflowState(total_cost_usd=cum_cost, total_tokens=100 * (i + 1)),
            )

        with Session(engine) as session:
            n0 = session.get(RunNode, f"{run_id}:b0")
            n1 = session.get(RunNode, f"{run_id}:b1")
            n2 = session.get(RunNode, f"{run_id}:b2")
            assert n0.cost_usd == pytest.approx(0.10, abs=0.001)
            assert n1.cost_usd == pytest.approx(0.15, abs=0.001)
            assert n2.cost_usd == pytest.approx(0.00, abs=0.001)


# ---------------------------------------------------------------------------
# 9. Defensive observer wrapping — DB write failures
# ---------------------------------------------------------------------------


class TestDefensiveObserverWrapping:
    def test_on_workflow_start_db_error_does_not_raise(self, seed_run):
        """If DB write fails in on_workflow_start, error is swallowed (logged, not raised)."""
        engine, run_id = seed_run
        ExecutionObserver = _import_execution_observer()

        # Sabotage the engine to cause DB errors
        bad_engine = create_engine("sqlite:///nonexistent/path/db.sqlite")
        obs_bad = ExecutionObserver(engine=bad_engine, run_id="run_bad")

        # Should NOT raise — observer errors must be swallowed
        obs_bad.on_workflow_start("wf", WorkflowState())

    def test_on_block_start_db_error_does_not_raise(self, seed_run):
        """If DB write fails in on_block_start, error is swallowed."""
        engine, run_id = seed_run
        ExecutionObserver = _import_execution_observer()
        bad_engine = create_engine("sqlite:///nonexistent/path/db.sqlite")
        obs = ExecutionObserver(engine=bad_engine, run_id="run_bad")
        obs.on_block_start("wf", "b1", "LinearBlock")

    def test_on_block_complete_db_error_does_not_raise(self, seed_run):
        """If DB write fails in on_block_complete, error is swallowed."""
        engine, run_id = seed_run
        ExecutionObserver = _import_execution_observer()
        bad_engine = create_engine("sqlite:///nonexistent/path/db.sqlite")
        obs = ExecutionObserver(engine=bad_engine, run_id="run_bad")
        obs.on_block_complete("wf", "b1", "LinearBlock", 1.0, WorkflowState())

    def test_on_block_error_db_error_does_not_raise(self, seed_run):
        """If DB write fails in on_block_error, error is swallowed."""
        engine, run_id = seed_run
        ExecutionObserver = _import_execution_observer()
        bad_engine = create_engine("sqlite:///nonexistent/path/db.sqlite")
        obs = ExecutionObserver(engine=bad_engine, run_id="run_bad")
        obs.on_block_error("wf", "b1", "LinearBlock", 1.0, RuntimeError("x"))

    def test_on_workflow_complete_db_error_does_not_raise(self, seed_run):
        """If DB write fails in on_workflow_complete, error is swallowed."""
        engine, run_id = seed_run
        ExecutionObserver = _import_execution_observer()
        bad_engine = create_engine("sqlite:///nonexistent/path/db.sqlite")
        obs = ExecutionObserver(engine=bad_engine, run_id="run_bad")
        obs.on_workflow_complete("wf", WorkflowState(), 5.0)

    def test_on_workflow_error_db_error_does_not_raise(self, seed_run):
        """If DB write fails in on_workflow_error, error is swallowed."""
        engine, run_id = seed_run
        ExecutionObserver = _import_execution_observer()
        bad_engine = create_engine("sqlite:///nonexistent/path/db.sqlite")
        obs = ExecutionObserver(engine=bad_engine, run_id="run_bad")
        obs.on_workflow_error("wf", RuntimeError("x"), 1.0)


# ---------------------------------------------------------------------------
# 10. Session factory pattern — each write gets its own session
# ---------------------------------------------------------------------------


class TestSessionFactory:
    def test_multiple_block_events_use_separate_sessions(self, observer):
        """Each observer method call creates a new Session (session-per-write pattern)."""
        obs, engine, run_id = observer

        # Patch Session to count instantiations
        original_session = Session
        session_count = {"n": 0}

        class CountingSession(original_session):
            def __init__(self, *args, **kwargs):
                session_count["n"] += 1
                super().__init__(*args, **kwargs)

        with patch("runsight_api.logic.observers.execution_observer.Session", CountingSession):
            ExecutionObserver = _import_execution_observer()
            obs2 = ExecutionObserver(engine=engine, run_id=run_id)
            obs2.on_workflow_start("wf", WorkflowState())
            obs2.on_block_start("wf", "b1", "LinearBlock")
            obs2.on_block_complete(
                "wf", "b1", "LinearBlock", 1.0, WorkflowState(total_cost_usd=0.05)
            )

        # At least 3 separate sessions (one per method call)
        assert session_count["n"] >= 3


# ---------------------------------------------------------------------------
# 11. LogEntry structured JSON format
# ---------------------------------------------------------------------------


class TestLogEntryFormat:
    def test_block_start_log_is_valid_json(self, observer):
        """LogEntry.message from on_block_start is valid JSON with required fields."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_a", "LinearBlock")

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            assert len(logs) >= 1
            msg = json.loads(logs[0].message)
            assert "event" in msg
            assert "block_id" in msg
            assert "block_type" in msg

    def test_block_complete_log_includes_duration_and_cost(self, observer):
        """LogEntry.message from on_block_complete includes duration_s and cost_delta."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_a", "LinearBlock")
        obs.on_block_complete(
            "wf", "block_a", "LinearBlock", 2.5, WorkflowState(total_cost_usd=0.05)
        )

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            complete_logs = [entry for entry in logs if "block_complete" in entry.message]
            assert len(complete_logs) >= 1
            msg = json.loads(complete_logs[0].message)
            assert "duration_s" in msg

    def test_workflow_error_log_includes_error_type(self, observer):
        """LogEntry.message from on_workflow_error includes error type and message."""
        obs, engine, run_id = observer
        obs.on_workflow_error("wf", ValueError("test error"), 1.0)

        with Session(engine) as session:
            from sqlmodel import select

            logs = list(session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all())
            assert len(logs) >= 1
            msg = json.loads(logs[0].message)
            assert "error" in msg or "error_type" in msg
