"""Red tests for RUN-326 + RUN-333: single status writer + fresh session per operation.

RUN-326: _run_workflow must NOT call _set_run_status for completed/failed.
         ExecutionObserver is the sole writer of terminal Run status.

RUN-333: launch_execution must use a fresh session for its error-path DB writes,
         not a long-lived run_repo that holds a stale session.
"""

import ast
import asyncio
import inspect
import textwrap
from unittest.mock import Mock

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.services.execution_service import ExecutionService


# ======================================================================
# C1 — Single status writer (RUN-326)
# ======================================================================


class TestSingleWriterSourceInspection:
    """Use AST / source inspection to verify _run_workflow doesn't write
    terminal statuses (completed / failed)."""

    def _get_run_workflow_ast(self) -> ast.FunctionDef:
        """Parse the source of _run_workflow and return its AST node."""
        source = inspect.getsource(ExecutionService._run_workflow)
        # dedent because inspect.getsource may return indented code
        source = textwrap.dedent(source)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_run_workflow":
                    return node
        pytest.fail("Could not find _run_workflow in AST")

    def test_run_workflow_does_not_call_set_run_status_completed(self):
        """_run_workflow source must NOT contain _set_run_status(..., RunStatus.completed)."""
        source = inspect.getsource(ExecutionService._run_workflow)
        # Check for any reference to RunStatus.completed in _set_run_status calls
        assert (
            "RunStatus.completed" not in source
            or "_set_run_status" not in source.split("RunStatus.completed")[0].split("\n")[-1]
        ), (
            "_run_workflow still calls _set_run_status with RunStatus.completed — "
            "ExecutionObserver should be the sole writer"
        )

    def test_run_workflow_does_not_call_set_run_status_failed(self):
        """_run_workflow source must NOT contain _set_run_status(..., RunStatus.failed)."""
        source = inspect.getsource(ExecutionService._run_workflow)
        assert (
            "RunStatus.failed" not in source
            or "_set_run_status" not in source.split("RunStatus.failed")[0].split("\n")[-1]
        ), (
            "_run_workflow still calls _set_run_status with RunStatus.failed — "
            "ExecutionObserver should be the sole writer"
        )

    def test_run_workflow_no_terminal_set_run_status_via_ast(self):
        """AST-level check: no _set_run_status call in _run_workflow passes
        RunStatus.completed or RunStatus.failed as an argument."""
        func_node = self._get_run_workflow_ast()
        source = inspect.getsource(ExecutionService._run_workflow)

        # Find all calls to self._set_run_status
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue
            # Check if call is self._set_run_status
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "_set_run_status":
                # Inspect arguments for RunStatus.completed or RunStatus.failed
                call_source = ast.get_source_segment(textwrap.dedent(source), node)
                if call_source is None:
                    # Fallback: check arg AST nodes
                    for arg in node.args + [kw.value for kw in node.keywords]:
                        if isinstance(arg, ast.Attribute):
                            if arg.attr in ("completed", "failed"):
                                pytest.fail(
                                    f"_run_workflow calls _set_run_status with "
                                    f"RunStatus.{arg.attr} — observer should be sole writer"
                                )
                else:
                    for terminal in ("completed", "failed"):
                        if f"RunStatus.{terminal}" in call_source:
                            pytest.fail(
                                f"_run_workflow calls _set_run_status with "
                                f"RunStatus.{terminal} — observer should be sole writer"
                            )


class TestObserverWritesTerminalStatus:
    """Verify ExecutionObserver correctly sets terminal Run status."""

    @pytest.fixture
    def db_engine(self):
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def run_in_db(self, db_engine):
        """Insert a pending Run record and return its id."""
        run_id = "run_obs_test"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                status=RunStatus.running,
                task_json="{}",
            )
            session.add(run)
            session.commit()
        return run_id

    def test_observer_on_workflow_complete_sets_completed(self, db_engine, run_in_db):
        """ExecutionObserver.on_workflow_complete sets Run.status = completed."""
        from runsight_core.state import WorkflowState

        obs = ExecutionObserver(engine=db_engine, run_id=run_in_db)
        state = WorkflowState()
        obs.on_workflow_complete("test_wf", state, duration_s=1.0)

        with Session(db_engine) as session:
            run = session.get(Run, run_in_db)
            assert run.status == RunStatus.completed, f"Expected completed, got {run.status}"

    def test_observer_on_workflow_error_sets_failed(self, db_engine, run_in_db):
        """ExecutionObserver.on_workflow_error sets Run.status = failed."""
        obs = ExecutionObserver(engine=db_engine, run_id=run_in_db)
        error = RuntimeError("something broke")
        obs.on_workflow_error("test_wf", error, duration_s=0.5)

        with Session(db_engine) as session:
            run = session.get(Run, run_in_db)
            assert run.status == RunStatus.failed, f"Expected failed, got {run.status}"


# ======================================================================
# C8 — Fresh session per operation (RUN-333)
# ======================================================================


class TestFreshSessionPerOperation:
    """ExecutionService.launch_execution must not rely on a long-lived
    run_repo for its error-path DB writes. It should create its own
    session when writing the failure status."""

    def test_launch_execution_error_path_uses_engine_not_run_repo(self):
        """When launch_execution hits an error before task creation, it
        should use a fresh Session(self.engine) to write the failure —
        not self.run_repo.get_run / self.run_repo.update_run.

        Source inspection: the except block in launch_execution should
        NOT reference self.run_repo."""
        source = inspect.getsource(ExecutionService.launch_execution)

        # Parse the AST to find the except handler(s)
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Get all attribute accesses inside the except block
                for child in ast.walk(node):
                    if isinstance(child, ast.Attribute):
                        if isinstance(child.value, ast.Attribute):
                            if (
                                child.value.attr == "run_repo"
                                and isinstance(child.value.value, ast.Name)
                                and child.value.value.id == "self"
                            ):
                                pytest.fail(
                                    "launch_execution except block still uses "
                                    "self.run_repo — must use a fresh Session(self.engine)"
                                )

    @pytest.mark.asyncio
    async def test_launch_execution_error_path_writes_via_engine_session(self):
        """Integration test: when workflow_repo.get_by_id returns None,
        launch_execution should write the failure using a fresh session
        from self.engine, NOT via run_repo."""
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_session_test"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_missing",
                workflow_name="wf_missing",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        # run_repo is a mock — we verify it is NOT called
        run_repo = Mock()
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = None  # triggers error path
        provider_repo = Mock()

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        await svc.launch_execution(run_id, "wf_missing", {"instruction": "test"})
        await asyncio.sleep(0.05)

        # run_repo.get_run should NOT have been called (fresh session used instead)
        run_repo.get_run.assert_not_called()
        run_repo.update_run.assert_not_called()

        # But the run should still be marked as failed in the DB
        with Session(db_engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.failed, (
                f"Expected run to be marked failed via engine session, got {run.status}"
            )
            assert run.error is not None
