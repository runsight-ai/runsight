"""Concurrent run limits via asyncio.Semaphore.

These tests verify that ExecutionService caps concurrent workflow executions
using an asyncio.Semaphore.
"""

import asyncio
from unittest.mock import Mock

import pytest

from runsight_api.data.repositories.run_repo import RunRepository
from tests.logic.execution_service_helpers import CONCURRENCY_WORKFLOW_ID
from tests.logic.execution_service_helpers import CONCURRENCY_WORKFLOW_NAME
from tests.logic.execution_service_helpers import CONCURRENCY_WORKFLOW_YAML
from tests.logic.execution_service_helpers import concurrency_inputs
from tests.logic.execution_service_helpers import make_service
from tests.logic.execution_service_helpers import patch_parse_workflow


# ---------------------------------------------------------------------------
# 1. Constructor accepts max_concurrent_runs kwarg
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_constructor_accepts_max_concurrent_runs_kwarg(self):
        """ExecutionService.__init__ accepts max_concurrent_runs keyword arg."""
        from runsight_api.logic.services.execution_service import ExecutionService

        # Should not raise TypeError about unexpected keyword argument
        ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            max_concurrent_runs=10,
        )


# ---------------------------------------------------------------------------
# 2. Semaphore limits concurrent executions
# ---------------------------------------------------------------------------


class TestConcurrencyLimit:
    @pytest.mark.asyncio
    async def test_only_n_run_simultaneously(self):
        """With semaphore(N), only N workflows execute at the same time.

        Launch N+2 runs with semaphore(2). At any point, at most 2 should
        be inside the workflow.run() call simultaneously.
        """
        max_concurrent = 2
        total_runs = max_concurrent + 2
        svc, *_ = make_service(max_concurrent_runs=max_concurrent)

        active_runs = 0
        max_observed = 0
        lock = asyncio.Lock()
        gate = asyncio.Event()
        all_entered = asyncio.Event()

        async def tracked_run(*args, **kwargs):
            nonlocal active_runs, max_observed
            async with lock:
                active_runs += 1
                if active_runs > max_observed:
                    max_observed = active_runs
                if active_runs >= max_concurrent:
                    all_entered.set()
            # Wait at the gate so runs pile up
            await gate.wait()
            async with lock:
                active_runs -= 1
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = patch_parse_workflow(tracked_run)
        with p1:
            for i in range(total_runs):
                await svc.launch_execution(
                    f"concurrency-run-{i}",
                    CONCURRENCY_WORKFLOW_ID,
                    concurrency_inputs(),
                    branch=None,
                )

            # Wait for the semaphore-permitted tasks to enter tracked_run
            try:
                await asyncio.wait_for(all_entered.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for concurrent runs to enter tracked_run")

            # Allow a moment for any extra tasks to sneak in (they shouldn't)
            await asyncio.sleep(0.05)

            # Only max_concurrent should be running at once
            assert max_observed <= max_concurrent, (
                f"Expected at most {max_concurrent} concurrent runs, but observed {max_observed}"
            )
            assert max_observed == max_concurrent, (
                f"Expected exactly {max_concurrent} concurrent runs "
                f"(semaphore should allow that many), but observed {max_observed}"
            )

            # Release the gate so all tasks complete
            gate.set()
            await asyncio.sleep(0.3)

    @pytest.mark.asyncio
    async def test_default_limit_is_5(self):
        """With no max_concurrent_runs arg, exactly 5 (not 6) can run concurrently.

        Behavioral proof of the default limit without inspecting internals.
        """
        svc, *_ = make_service()  # No max_concurrent_runs — should default to 5
        total_runs = 7

        active_runs = 0
        max_observed = 0
        lock = asyncio.Lock()
        gate = asyncio.Event()
        five_entered = asyncio.Event()

        async def tracked_run(*args, **kwargs):
            nonlocal active_runs, max_observed
            async with lock:
                active_runs += 1
                if active_runs > max_observed:
                    max_observed = active_runs
                if active_runs >= 5:
                    five_entered.set()
            await gate.wait()
            async with lock:
                active_runs -= 1
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = patch_parse_workflow(tracked_run)
        with p1:
            for i in range(total_runs):
                await svc.launch_execution(
                    f"default-limit-run-{i}",
                    CONCURRENCY_WORKFLOW_ID,
                    concurrency_inputs(),
                    branch=None,
                )

            # Wait for 5 to enter
            try:
                await asyncio.wait_for(five_entered.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for 5 concurrent runs")

            # Brief pause to let a 6th sneak in if limit is wrong
            await asyncio.sleep(0.05)

            assert max_observed == 5, (
                f"Default limit should allow exactly 5 concurrent runs, but observed {max_observed}"
            )

            gate.set()
            await asyncio.sleep(0.3)

    @pytest.mark.asyncio
    async def test_queued_runs_eventually_execute(self):
        """Runs beyond the semaphore limit queue and eventually execute (no failure)."""
        max_concurrent = 1
        total_runs = 3
        svc, *_ = make_service(max_concurrent_runs=max_concurrent)

        completed_count = 0
        lock = asyncio.Lock()
        all_done = asyncio.Event()
        gate = asyncio.Event()

        async def gated_run(*args, **kwargs):
            nonlocal completed_count
            await gate.wait()
            from runsight_core.state import WorkflowState

            result = WorkflowState()
            async with lock:
                completed_count += 1
                if completed_count >= total_runs:
                    all_done.set()
            return result

        p1 = patch_parse_workflow(gated_run)
        with p1:
            for i in range(total_runs):
                await svc.launch_execution(
                    f"queued-run-{i}",
                    CONCURRENCY_WORKFLOW_ID,
                    concurrency_inputs(),
                    branch=None,
                )

            # Release gate — all queued runs should eventually complete
            gate.set()

            try:
                await asyncio.wait_for(all_done.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                pytest.fail(
                    f"Only {completed_count}/{total_runs} runs completed — "
                    f"queued runs did not execute"
                )

            # All tasks should have completed (removed from runtime.running_tasks)
            assert len(svc._runtime.running_tasks) == 0, (
                "Expected all runs to complete, but "
                f"{len(svc._runtime.running_tasks)} are still tracked"
            )

    @pytest.mark.asyncio
    async def test_excess_runs_do_not_fail(self):
        """Runs beyond the limit should queue, NOT raise or return 429-style error."""
        max_concurrent = 1
        svc, *_ = make_service(max_concurrent_runs=max_concurrent)

        gate = asyncio.Event()

        async def blocking_run(*args, **kwargs):
            await gate.wait()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = patch_parse_workflow(blocking_run)
        with p1:
            # First run occupies the semaphore
            await svc.launch_execution(
                "active-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )
            # Second run should NOT raise — it queues
            await svc.launch_execution(
                "waiting-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )

            # Both should be in runtime.running_tasks (one active, one waiting)
            assert "active-run" in svc._runtime.running_tasks
            assert "waiting-run" in svc._runtime.running_tasks

            gate.set()
            await asyncio.sleep(0.3)


# ---------------------------------------------------------------------------
# 3. Semaphore released on error (no deadlock)
# ---------------------------------------------------------------------------


class TestSemaphoreRelease:
    @pytest.mark.asyncio
    async def test_semaphore_released_on_workflow_error(self):
        """If workflow.run() raises, the semaphore slot is released (no deadlock).

        With semaphore(1), a failed run should release the slot for the next run.
        """
        svc, *_ = make_service(max_concurrent_runs=1)

        call_count = 0

        async def failing_then_ok(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = patch_parse_workflow(failing_then_ok)
        with p1:
            await svc.launch_execution(
                "failing-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )
            await asyncio.sleep(0.1)  # Let the failure happen

            # Now launch a second run — it should NOT deadlock
            await svc.launch_execution(
                "recovery-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )

            # Give it time to complete
            await asyncio.sleep(0.2)

            # Second run should have completed
            assert call_count == 2, "Second run never executed — semaphore likely leaked"

    @pytest.mark.asyncio
    async def test_semaphore_released_on_cancellation(self):
        """If an asyncio task is cancelled, the semaphore slot is released.

        With semaphore(1), cancelling the first run should let the next run acquire it.
        """
        svc, *_ = make_service(max_concurrent_runs=1)

        cancellable_run_started = asyncio.Event()
        after_cancel_completed = asyncio.Event()

        async def long_run(*args, **kwargs):
            cancellable_run_started.set()
            await asyncio.sleep(10)  # Simulate long-running workflow
            from runsight_core.state import WorkflowState

            return WorkflowState()

        async def quick_run(*args, **kwargs):
            after_cancel_completed.set()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        # Both launches share one patch scope; the coro switches between calls
        call_count = 0

        async def dispatch_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return await long_run(*args, **kwargs)
            return await quick_run(*args, **kwargs)

        p1 = patch_parse_workflow(dispatch_run)
        with p1:
            await svc.launch_execution(
                "cancellable-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )
            await cancellable_run_started.wait()

            # Cancel the first task
            task = svc._runtime.running_tasks.get("cancellable-run")
            assert task is not None, "cancellable-run should be in runtime.running_tasks"
            task.cancel()
            await asyncio.sleep(0.1)

            # Launch second run — should acquire released semaphore
            await svc.launch_execution(
                "after-cancel-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )

            # Should complete within a reasonable time (not deadlocked)
            try:
                await asyncio.wait_for(after_cancel_completed.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("after-cancel-run timed out — semaphore not released on cancellation")

    @pytest.mark.asyncio
    async def test_semaphore_released_in_finally_block(self):
        """Semaphore must be released in a finally block so ALL exit paths release it.

        We verify by draining the semaphore completely, causing failures in each slot,
        then launching one more run that should still succeed.
        """
        limit = 2
        svc, *_ = make_service(max_concurrent_runs=limit)

        async def always_fail(*args, **kwargs):
            raise RuntimeError("always fails")

        p1 = patch_parse_workflow(always_fail)
        with p1:
            # Fill all semaphore slots with failing runs
            for i in range(limit):
                await svc.launch_execution(
                    f"failing-slot-run-{i}",
                    CONCURRENCY_WORKFLOW_ID,
                    concurrency_inputs(),
                    branch=None,
                )
            await asyncio.sleep(0.2)  # Let all fail

        # Now launch one more — should succeed if semaphore was properly released
        success_event = asyncio.Event()

        async def success_run(*args, **kwargs):
            success_event.set()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1c = patch_parse_workflow(success_run)
        with p1c:
            await svc.launch_execution(
                "post-failure-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )
            try:
                await asyncio.wait_for(success_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("post-failure-run never ran — semaphore slots leaked from failures")


# ---------------------------------------------------------------------------
# 4. Run status stays pending until semaphore acquired
# ---------------------------------------------------------------------------


class TestPendingUntilAcquired:
    @pytest.mark.asyncio
    async def test_status_pending_while_queued(self):
        """A run blocked on the semaphore should remain in 'pending' status.

        With semaphore(1), the first run occupies the slot and the next stays pending.
        """
        from sqlmodel import Session, SQLModel, create_engine

        from runsight_api.domain.entities.run import Run, RunStatus

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        from runsight_api.logic.services.execution_service import ExecutionService

        run_repo = RunRepository(Session(db_engine))
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = CONCURRENCY_WORKFLOW_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider_repo.get_by_type.return_value = None

        # Create two Run records in the DB
        with Session(db_engine) as session:
            for run_id in ("active-run", "queued-run"):
                run = Run(
                    id=run_id,
                    workflow_id=CONCURRENCY_WORKFLOW_ID,
                    workflow_name=CONCURRENCY_WORKFLOW_NAME,
                    status=RunStatus.pending,
                    task_json="{}",
                    branch="main",
                )
                session.add(run)
            session.commit()

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
            max_concurrent_runs=1,
        )

        gate = asyncio.Event()

        async def blocking_run(*args, **kwargs):
            await gate.wait()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = patch_parse_workflow(blocking_run)
        with p1:
            # First run occupies the semaphore
            await svc.launch_execution(
                "active-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )
            await asyncio.sleep(0.1)

            # Second run should be queued
            await svc.launch_execution(
                "queued-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )
            await asyncio.sleep(0.1)

            # The queued run should still be pending while blocked on the semaphore.
            with Session(db_engine) as session:
                queued = session.get(Run, "queued-run")
                assert queued.status == RunStatus.pending, (
                    f"Expected queued run to remain 'pending', got '{queued.status}'"
                )

            gate.set()
            await asyncio.sleep(0.3)

    @pytest.mark.asyncio
    async def test_status_transitions_to_running_after_semaphore_acquired(self):
        """Once a queued run acquires the semaphore, it should transition to 'running'."""
        from sqlmodel import Session, SQLModel, create_engine

        from runsight_api.domain.entities.run import Run, RunStatus

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        from runsight_api.logic.services.execution_service import ExecutionService

        run_repo = RunRepository(Session(db_engine))
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = CONCURRENCY_WORKFLOW_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider_repo.get_by_type.return_value = None

        with Session(db_engine) as session:
            for run_id in ("blocking-run", "released-run"):
                session.add(
                    Run(
                        id=run_id,
                        workflow_id=CONCURRENCY_WORKFLOW_ID,
                        workflow_name=CONCURRENCY_WORKFLOW_NAME,
                        status=RunStatus.pending,
                        task_json="{}",
                        branch="main",
                    )
                )
            session.commit()

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
            max_concurrent_runs=1,
        )

        first_gate = asyncio.Event()
        second_running = asyncio.Event()

        call_count = 0

        async def dispatch_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First run: block until released
                await first_gate.wait()
                from runsight_core.state import WorkflowState

                return WorkflowState()
            else:
                # Second run: signal that it started
                second_running.set()
                from runsight_core.state import WorkflowState

                return WorkflowState()

        p1 = patch_parse_workflow(dispatch_run)
        with p1:
            await svc.launch_execution(
                "blocking-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )
            await asyncio.sleep(0.1)

            await svc.launch_execution(
                "released-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )
            await asyncio.sleep(0.1)

            # Release first — second should then acquire and transition to running
            first_gate.set()

            try:
                await asyncio.wait_for(second_running.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("Second run never started after first completed")

            await asyncio.sleep(0.1)

            with Session(db_engine) as session:
                released_run = session.get(Run, "released-run")
                assert released_run.status in (RunStatus.running, RunStatus.completed), (
                    f"Expected 'running' or 'completed', got '{released_run.status}'"
                )


# ---------------------------------------------------------------------------
# 5. Immediate 200 — launch_execution returns before semaphore acquired
# ---------------------------------------------------------------------------


class TestImmediateReturn:
    @pytest.mark.asyncio
    async def test_launch_returns_immediately_even_when_semaphore_full(self):
        """launch_execution should return immediately (user gets 200) even if
        the semaphore is fully occupied. The semaphore wait happens in the
        background task, not in launch_execution itself.
        """
        svc, *_ = make_service(max_concurrent_runs=1)

        gate = asyncio.Event()

        async def blocking_run(*args, **kwargs):
            await gate.wait()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = patch_parse_workflow(blocking_run)
        with p1:
            # Fill the semaphore
            await svc.launch_execution(
                "slot-filling-run",
                CONCURRENCY_WORKFLOW_ID,
                concurrency_inputs(),
                branch=None,
            )

            # This should return within a short time, NOT block
            try:
                await asyncio.wait_for(
                    svc.launch_execution(
                        "queued-launch-run",
                        CONCURRENCY_WORKFLOW_ID,
                        concurrency_inputs(),
                        branch=None,
                    ),
                    timeout=0.5,
                )
            except asyncio.TimeoutError:
                pytest.fail(
                    "launch_execution blocked on full semaphore — "
                    "must return immediately so caller gets HTTP 200"
                )

            gate.set()
            await asyncio.sleep(0.3)
