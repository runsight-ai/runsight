"""Red tests for RUN-5: Concurrent run limits via asyncio.Semaphore.

These tests verify that ExecutionService caps concurrent workflow executions
using an asyncio.Semaphore. All tests should FAIL until the implementation exists.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest


def _make_service(max_concurrent_runs=None):
    """Create an ExecutionService with mock dependencies.

    If max_concurrent_runs is provided, passes it to the constructor.
    This tests that the constructor accepts the new kwarg.
    """
    from runsight_api.logic.services.execution_service import ExecutionService

    run_repo = Mock()
    workflow_repo = Mock()
    provider_repo = Mock()

    mock_entity = Mock()
    mock_entity.yaml = (
        "workflow:\n  name: t\n  entry: b1\n  transitions: []\n"
        "blocks:\n  b1:\n    type: linear\n    soul_ref: test\n"
        "souls: {}\nconfig: {}"
    )
    workflow_repo.get_by_id.return_value = mock_entity
    provider_repo.get_by_type.return_value = None

    kwargs = dict(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
    )
    if max_concurrent_runs is not None:
        kwargs["max_concurrent_runs"] = max_concurrent_runs

    svc = ExecutionService(**kwargs)
    return svc, run_repo, workflow_repo, provider_repo


def _patch_parse_workflow(slow_run_coro):
    """Return a context manager that patches parse_workflow_yaml.

    The parsed workflow's .run will be set to slow_run_coro.
    """
    mock_wf = Mock()
    mock_wf.run = slow_run_coro

    return patch(
        "runsight_api.logic.services.execution_service.parse_workflow_yaml",
        return_value=mock_wf,
    )


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
        svc, *_ = _make_service(max_concurrent_runs=max_concurrent)

        currently_running = 0
        max_observed = 0
        lock = asyncio.Lock()
        gate = asyncio.Event()
        all_entered = asyncio.Event()

        async def tracked_run(*args, **kwargs):
            nonlocal currently_running, max_observed
            async with lock:
                currently_running += 1
                if currently_running > max_observed:
                    max_observed = currently_running
                if currently_running >= max_concurrent:
                    all_entered.set()
            # Wait at the gate so runs pile up
            await gate.wait()
            async with lock:
                currently_running -= 1
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = _patch_parse_workflow(tracked_run)
        with p1:
            for i in range(total_runs):
                await svc.launch_execution(f"run_{i}", "wf_1", {"instruction": "go"})

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
        svc, *_ = _make_service()  # No max_concurrent_runs — should default to 5
        total_runs = 7

        currently_running = 0
        max_observed = 0
        lock = asyncio.Lock()
        gate = asyncio.Event()
        five_entered = asyncio.Event()

        async def tracked_run(*args, **kwargs):
            nonlocal currently_running, max_observed
            async with lock:
                currently_running += 1
                if currently_running > max_observed:
                    max_observed = currently_running
                if currently_running >= 5:
                    five_entered.set()
            await gate.wait()
            async with lock:
                currently_running -= 1
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = _patch_parse_workflow(tracked_run)
        with p1:
            for i in range(total_runs):
                await svc.launch_execution(f"run_d{i}", "wf_1", {"instruction": "go"})

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
        svc, *_ = _make_service(max_concurrent_runs=max_concurrent)

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

        p1 = _patch_parse_workflow(gated_run)
        with p1:
            for i in range(total_runs):
                await svc.launch_execution(f"run_q{i}", "wf_1", {"instruction": "go"})

            # Release gate — all queued runs should eventually complete
            gate.set()

            try:
                await asyncio.wait_for(all_done.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                pytest.fail(
                    f"Only {completed_count}/{total_runs} runs completed — "
                    f"queued runs did not execute"
                )

            # All tasks should have completed (removed from _running_tasks)
            assert len(svc._running_tasks) == 0, (
                f"Expected all runs to complete, but {len(svc._running_tasks)} are still tracked"
            )

    @pytest.mark.asyncio
    async def test_excess_runs_do_not_fail(self):
        """Runs beyond the limit should queue, NOT raise or return 429-style error."""
        max_concurrent = 1
        svc, run_repo, *_ = _make_service(max_concurrent_runs=max_concurrent)

        gate = asyncio.Event()

        async def blocking_run(*args, **kwargs):
            await gate.wait()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = _patch_parse_workflow(blocking_run)
        with p1:
            # First run occupies the semaphore
            await svc.launch_execution("run_a", "wf_1", {"instruction": "go"})
            # Second run should NOT raise — it queues
            await svc.launch_execution("run_b", "wf_1", {"instruction": "go"})

            # Both should be in _running_tasks (one active, one waiting)
            assert "run_a" in svc._running_tasks
            assert "run_b" in svc._running_tasks

            gate.set()
            await asyncio.sleep(0.3)


# ---------------------------------------------------------------------------
# 3. Semaphore released on error (no deadlock)
# ---------------------------------------------------------------------------


class TestSemaphoreRelease:
    @pytest.mark.asyncio
    async def test_semaphore_released_on_workflow_error(self):
        """If workflow.run() raises, the semaphore slot is released (no deadlock).

        With semaphore(1): run_1 fails, then run_2 should still acquire the semaphore.
        """
        svc, *_ = _make_service(max_concurrent_runs=1)

        call_count = 0

        async def failing_then_ok(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = _patch_parse_workflow(failing_then_ok)
        with p1:
            await svc.launch_execution("run_fail", "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.1)  # Let the failure happen

            # Now launch a second run — it should NOT deadlock
            await svc.launch_execution("run_ok", "wf_1", {"instruction": "go"})

            # Give it time to complete
            await asyncio.sleep(0.2)

            # Second run should have completed
            assert call_count == 2, "Second run never executed — semaphore likely leaked"

    @pytest.mark.asyncio
    async def test_semaphore_released_on_cancellation(self):
        """If an asyncio task is cancelled, the semaphore slot is released.

        With semaphore(1): cancel run_1, then run_2 should acquire the semaphore.
        """
        svc, *_ = _make_service(max_concurrent_runs=1)

        run_started = asyncio.Event()
        run2_completed = asyncio.Event()

        async def long_run(*args, **kwargs):
            run_started.set()
            await asyncio.sleep(10)  # Simulate long-running workflow
            from runsight_core.state import WorkflowState

            return WorkflowState()

        async def quick_run(*args, **kwargs):
            run2_completed.set()
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

        p1 = _patch_parse_workflow(dispatch_run)
        with p1:
            await svc.launch_execution("run_cancel", "wf_1", {"instruction": "go"})
            await run_started.wait()

            # Cancel the first task
            task = svc._running_tasks.get("run_cancel")
            assert task is not None, "run_cancel should be in _running_tasks"
            task.cancel()
            await asyncio.sleep(0.1)

            # Launch second run — should acquire released semaphore
            await svc.launch_execution("run_after_cancel", "wf_1", {"instruction": "go"})

            # Should complete within a reasonable time (not deadlocked)
            try:
                await asyncio.wait_for(run2_completed.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("run_after_cancel timed out — semaphore not released on cancellation")

    @pytest.mark.asyncio
    async def test_semaphore_released_in_finally_block(self):
        """Semaphore must be released in a finally block so ALL exit paths release it.

        We verify by draining the semaphore completely, causing failures in each slot,
        then launching one more run that should still succeed.
        """
        limit = 2
        svc, *_ = _make_service(max_concurrent_runs=limit)

        async def always_fail(*args, **kwargs):
            raise RuntimeError("always fails")

        p1 = _patch_parse_workflow(always_fail)
        with p1:
            # Fill all semaphore slots with failing runs
            for i in range(limit):
                await svc.launch_execution(f"run_fail_{i}", "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.2)  # Let all fail

        # Now launch one more — should succeed if semaphore was properly released
        success_event = asyncio.Event()

        async def success_run(*args, **kwargs):
            success_event.set()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1c = _patch_parse_workflow(success_run)
        with p1c:
            await svc.launch_execution("run_after_fails", "wf_1", {"instruction": "go"})
            try:
                await asyncio.wait_for(success_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("run_after_fails never ran — semaphore slots leaked from failures")


# ---------------------------------------------------------------------------
# 4. Run status stays pending until semaphore acquired
# ---------------------------------------------------------------------------


class TestPendingUntilAcquired:
    @pytest.mark.asyncio
    async def test_status_pending_while_queued(self):
        """A run blocked on the semaphore should remain in 'pending' status.

        With semaphore(1): run_1 occupies the slot. run_2 should stay pending.
        """
        from runsight_api.domain.entities.run import Run, RunStatus
        from sqlmodel import Session, SQLModel, create_engine

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        from runsight_api.logic.services.execution_service import ExecutionService

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = (
            "workflow:\n  name: t\n  entry: b1\n  transitions: []\n"
            "blocks:\n  b1:\n    type: linear\n    soul_ref: test\n"
            "souls: {}\nconfig: {}"
        )
        workflow_repo.get_by_id.return_value = mock_entity
        provider_repo.get_by_type.return_value = None

        # Create two Run records in the DB
        with Session(db_engine) as session:
            for rid in ("run_active", "run_queued"):
                run = Run(
                    id=rid,
                    workflow_id="wf_1",
                    workflow_name="wf_1",
                    status=RunStatus.pending,
                    task_json="{}",
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

        p1 = _patch_parse_workflow(blocking_run)
        with p1:
            # First run occupies the semaphore
            await svc.launch_execution("run_active", "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.1)

            # Second run should be queued
            await svc.launch_execution("run_queued", "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.1)

            # run_queued should still be pending (blocked on semaphore)
            with Session(db_engine) as session:
                queued = session.get(Run, "run_queued")
                assert queued.status == RunStatus.pending, (
                    f"Expected queued run to remain 'pending', got '{queued.status}'"
                )

            gate.set()
            await asyncio.sleep(0.3)

    @pytest.mark.asyncio
    async def test_status_transitions_to_running_after_semaphore_acquired(self):
        """Once a queued run acquires the semaphore, it should transition to 'running'."""
        from runsight_api.domain.entities.run import Run, RunStatus
        from sqlmodel import Session, SQLModel, create_engine

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        from runsight_api.logic.services.execution_service import ExecutionService

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = (
            "workflow:\n  name: t\n  entry: b1\n  transitions: []\n"
            "blocks:\n  b1:\n    type: linear\n    soul_ref: test\n"
            "souls: {}\nconfig: {}"
        )
        workflow_repo.get_by_id.return_value = mock_entity
        provider_repo.get_by_type.return_value = None

        with Session(db_engine) as session:
            for rid in ("run_first", "run_second"):
                session.add(
                    Run(
                        id=rid,
                        workflow_id="wf_1",
                        workflow_name="wf_1",
                        status=RunStatus.pending,
                        task_json="{}",
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

        p1 = _patch_parse_workflow(dispatch_run)
        with p1:
            await svc.launch_execution("run_first", "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.1)

            await svc.launch_execution("run_second", "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.1)

            # Release first — second should then acquire and transition to running
            first_gate.set()

            try:
                await asyncio.wait_for(second_running.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("Second run never started after first completed")

            await asyncio.sleep(0.1)

            with Session(db_engine) as session:
                run2 = session.get(Run, "run_second")
                assert run2.status in (RunStatus.running, RunStatus.completed), (
                    f"Expected 'running' or 'completed', got '{run2.status}'"
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
        svc, *_ = _make_service(max_concurrent_runs=1)

        gate = asyncio.Event()

        async def blocking_run(*args, **kwargs):
            await gate.wait()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        p1 = _patch_parse_workflow(blocking_run)
        with p1:
            # Fill the semaphore
            await svc.launch_execution("run_fill", "wf_1", {"instruction": "go"})

            # This should return within a short time, NOT block
            try:
                await asyncio.wait_for(
                    svc.launch_execution("run_queued", "wf_1", {"instruction": "go"}),
                    timeout=0.5,
                )
            except asyncio.TimeoutError:
                pytest.fail(
                    "launch_execution blocked on full semaphore — "
                    "must return immediately so caller gets HTTP 200"
                )

            gate.set()
            await asyncio.sleep(0.3)
