"""
Failing tests for RUN-715: DispatchBlock branch session isolation via copy_context.

DispatchBlock runs branches in parallel via asyncio.gather(). Without isolation,
concurrent branches sharing a parent BudgetSession create race conditions. Solution:
each branch gets an isolated child session via copy_context().run(), costs reconciled
to parent after gather.

Tests cover all acceptance criteria:
- Each asyncio.gather branch runs with its own isolated BudgetSession
- Branch costs do NOT accrue to parent during parallel execution
- After gather returns, all branch costs reconciled to parent via reconcile_child()
- Flow-level check_or_raise() runs after reconciliation
- Branch exceeding its own block cap -> BudgetKilledException from that branch
- Combined branch costs exceeding flow cap -> BudgetKilledException after reconciliation
- No budget set -> branches run identically to current behavior (zero overhead)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.budget_enforcement import (
    BudgetKilledException,
    BudgetSession,
    _active_budget,
)
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_soul(soul_id: str) -> Soul:
    return Soul(id=soul_id, role=soul_id.title(), system_prompt=f"You are {soul_id}.")


def _make_branches(count: int) -> list[DispatchBranch]:
    """Create N branches with distinct souls and instructions."""
    souls = [_make_soul(f"soul_{i}") for i in range(count)]
    return [
        DispatchBranch(
            exit_id=f"exit_{i}",
            label=f"Exit {i}",
            soul=souls[i],
            task_instruction=f"Task for branch {i}",
        )
        for i in range(count)
    ]


def _make_exec_result(task_id: str, soul_id: str, output: str, cost: float = 0.0, tokens: int = 0):
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


def _make_runner_with_costs(
    branches: list[DispatchBranch], costs: list[float], tokens: list[int] | None = None
):
    """Create a mock runner whose execute_task returns controlled costs per branch.

    The side_effect captures the _active_budget contextvar at call time so tests
    can inspect which session was active for each branch.
    """
    if tokens is None:
        tokens = [0] * len(branches)

    runner = MagicMock()
    runner.model_name = "gpt-4o"
    runner._build_prompt = MagicMock(
        side_effect=lambda task: task.instruction,
    )

    call_idx = 0
    captured_sessions: list[BudgetSession | None] = []

    async def _side_effect(task: Task, soul: Soul, **kwargs):
        nonlocal call_idx
        idx = call_idx
        call_idx += 1

        # Capture whatever BudgetSession is active for this branch
        session = _active_budget.get(None)
        captured_sessions.append(session)

        # Simulate accruing cost to the active session (as achat would)
        if session is not None:
            session.accrue(cost_usd=costs[idx], tokens=tokens[idx])

        return _make_exec_result(
            task_id=task.id,
            soul_id=soul.id,
            output=f"result_{idx}",
            cost=costs[idx],
            tokens=tokens[idx],
        )

    runner.execute_task = AsyncMock(side_effect=_side_effect)
    runner.captured_sessions = captured_sessions
    return runner


# ===========================================================================
# 1. Each gather branch sees its own isolated BudgetSession
# ===========================================================================


class TestBranchSessionIsolation:
    """Each asyncio.gather branch must run with its own isolated BudgetSession."""

    @pytest.mark.asyncio
    async def test_each_branch_sees_distinct_session(self):
        """Given 3 branches with an active parent session,
        each branch should see a different BudgetSession in _active_budget."""
        branches = _make_branches(3)
        costs = [0.10, 0.20, 0.30]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=5.0)
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_1", branches, runner)
            state = WorkflowState()
            await block.execute(state)

            sessions = runner.captured_sessions
            assert len(sessions) == 3

            # Each branch should have its own session, not the parent
            for s in sessions:
                assert s is not None, "Branch should see a BudgetSession, not None"
                assert s is not parent, "Branch should NOT see the parent session directly"

            # All three sessions should be distinct objects
            assert sessions[0] is not sessions[1]
            assert sessions[1] is not sessions[2]
            assert sessions[0] is not sessions[2]
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_branch_sessions_are_isolated_children(self):
        """Isolated child sessions should have parent=None and be distinct
        from the parent — proving they were created via create_isolated_child()."""
        branches = _make_branches(2)
        costs = [0.50, 0.50]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=5.0)
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_2", branches, runner)
            state = WorkflowState()
            await block.execute(state)

            for s in runner.captured_sessions:
                assert s is not None
                # Must NOT be the parent session
                assert s is not parent, "Branch should see an isolated child, not the parent"
                # Isolated child has parent=None
                assert s.parent is None, "Isolated child must have parent=None"
        finally:
            _active_budget.set(None)


# ===========================================================================
# 2. Branch costs do NOT accrue to parent during parallel execution
# ===========================================================================


class TestNoConcurrentParentAccrual:
    """Branch costs must NOT reach the parent session during gather."""

    @pytest.mark.asyncio
    async def test_parent_cost_zero_during_branch_execution(self):
        """While branches are executing, the parent session should have cost=0.
        Costs are only reconciled AFTER gather completes."""
        branches = _make_branches(2)
        costs = [0.50, 0.60]

        parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=5.0)

        parent_cost_during_execution: list[float] = []

        runner = MagicMock()
        runner.model_name = "gpt-4o"
        runner._build_prompt = MagicMock(side_effect=lambda task: task.instruction)

        call_idx = 0

        async def _side_effect(task, soul, **kwargs):
            nonlocal call_idx
            idx = call_idx
            call_idx += 1

            session = _active_budget.get(None)
            if session is not None:
                session.accrue(cost_usd=costs[idx], tokens=0)

            # Record parent cost at this point in time
            parent_cost_during_execution.append(parent.cost_usd)

            return _make_exec_result(
                task_id=task.id,
                soul_id=soul.id,
                output=f"r{idx}",
                cost=costs[idx],
            )

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        _active_budget.set(parent)
        try:
            block = DispatchBlock("dispatch_3", branches, runner)
            state = WorkflowState()
            await block.execute(state)

            # During execution, parent should not have accrued any branch costs
            for cost_snapshot in parent_cost_during_execution:
                assert cost_snapshot == 0.0, (
                    f"Parent cost should be 0.0 during branch execution, got {cost_snapshot}"
                )
        finally:
            _active_budget.set(None)


# ===========================================================================
# 3. After gather, all branch costs reconciled to parent
# ===========================================================================


class TestPostGatherReconciliation:
    """After asyncio.gather returns, parent session must reflect combined branch costs."""

    @pytest.mark.asyncio
    async def test_parent_has_combined_cost_after_execute(self):
        """Acceptance scenario: 3 branches costing $0.50, $0.60, $0.40.
        After execute(), parent.cost_usd == 1.50."""
        branches = _make_branches(3)
        costs = [0.50, 0.60, 0.40]
        tokens = [100, 200, 300]
        runner = _make_runner_with_costs(branches, costs, tokens)

        parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=2.00)
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_4", branches, runner)
            state = WorkflowState()
            await block.execute(state)

            assert parent.cost_usd == pytest.approx(1.50)
            assert parent.tokens == 600
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_parent_with_prior_cost_adds_branch_costs(self):
        """If parent already has $0.50 from earlier blocks, and branches add $0.80,
        parent.cost_usd should be $1.30 after reconciliation."""
        branches = _make_branches(2)
        costs = [0.40, 0.40]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=5.0)
        parent.accrue(cost_usd=0.50, tokens=200)  # prior cost from earlier blocks
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_5", branches, runner)
            state = WorkflowState()
            await block.execute(state)

            assert parent.cost_usd == pytest.approx(1.30)
        finally:
            _active_budget.set(None)


# ===========================================================================
# 4. Flow-level check_or_raise() runs after reconciliation
# ===========================================================================


class TestFlowCheckAfterReconciliation:
    """After reconciliation, DispatchBlock must call parent.check_or_raise()."""

    @pytest.mark.asyncio
    async def test_combined_cost_exceeding_flow_cap_raises(self):
        """Acceptance scenario: flow cap=$2.00, branches cost $0.80+$0.90+$0.70=$2.40.
        After reconciliation, parent.check_or_raise() raises BudgetKilledException."""
        branches = _make_branches(3)
        costs = [0.80, 0.90, 0.70]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=2.00,
            on_exceed="fail",
        )
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_6", branches, runner)
            state = WorkflowState()

            with pytest.raises(BudgetKilledException) as exc_info:
                await block.execute(state)

            exc = exc_info.value
            assert exc.scope == "workflow"
            assert exc.limit_kind == "cost_usd"
            assert exc.limit_value == 2.00
            assert exc.actual_value == pytest.approx(2.40)
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_under_flow_cap_does_not_raise(self):
        """Acceptance scenario: flow cap=$2.00, branches cost $0.50+$0.60+$0.40=$1.50.
        No exception after reconciliation."""
        branches = _make_branches(3)
        costs = [0.50, 0.60, 0.40]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=2.00,
            on_exceed="fail",
        )
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_7", branches, runner)
            state = WorkflowState()

            # Should not raise
            await block.execute(state)
            assert parent.cost_usd == pytest.approx(1.50)
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_prior_cost_plus_branches_exceeding_cap_raises(self):
        """Parent already at $1.50, branches add $0.60 total, cap is $2.00 -> raises."""
        branches = _make_branches(2)
        costs = [0.30, 0.30]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=2.00,
            on_exceed="fail",
        )
        parent.accrue(cost_usd=1.50, tokens=0)
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_8", branches, runner)
            state = WorkflowState()

            with pytest.raises(BudgetKilledException) as exc_info:
                await block.execute(state)

            assert exc_info.value.actual_value == pytest.approx(2.10)
        finally:
            _active_budget.set(None)


# ===========================================================================
# 5. Branch exceeding its own block cap raises during gather
# ===========================================================================


class TestBranchBlockCapEnforcement:
    """A branch exceeding its own isolated session's cap raises BudgetKilledException."""

    @pytest.mark.asyncio
    async def test_branch_over_block_cap_raises(self):
        """If a branch's isolated session has cost_cap_usd (inherited from parent)
        and that branch exceeds it, BudgetKilledException propagates from gather.

        The achat layer calls session.check_or_raise() after each LLM call.
        We simulate that by having the mock accrue and then check.
        The key assertion: the session checked is an isolated child, not the parent."""
        branches = _make_branches(2)

        # Parent cap is $0.50 — isolated children inherit this cap
        parent = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=0.50,
            on_exceed="fail",
        )

        runner = MagicMock()
        runner.model_name = "gpt-4o"
        runner._build_prompt = MagicMock(side_effect=lambda task: task.instruction)

        call_idx = 0
        branch_costs = [0.60, 0.20]  # first branch exceeds $0.50 cap
        checked_sessions: list[BudgetSession | None] = []

        async def _side_effect(task, soul, **kwargs):
            nonlocal call_idx
            idx = call_idx
            call_idx += 1

            session = _active_budget.get(None)
            checked_sessions.append(session)
            if session is not None:
                session.accrue(cost_usd=branch_costs[idx], tokens=0)
                # Simulate what achat does: check after accrual
                session.check_or_raise()

            return _make_exec_result(
                task_id=task.id,
                soul_id=soul.id,
                output=f"r{idx}",
                cost=branch_costs[idx],
            )

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        _active_budget.set(parent)
        try:
            block = DispatchBlock("dispatch_9", branches, runner)
            state = WorkflowState()

            with pytest.raises(BudgetKilledException) as exc_info:
                await block.execute(state)

            assert exc_info.value.limit_kind == "cost_usd"

            # The session that raised should have been an isolated child, not the parent
            # If isolation is not implemented, the check runs against the parent which
            # would also raise — but the parent should remain untouched during execution.
            # Verify parent was not accrued to directly during branch execution:
            # After the exception, parent cost should be 0.0 (no reconciliation happened
            # because gather failed)
            assert parent.cost_usd == 0.0, (
                "Parent should not have been accrued to during branch execution; "
                f"got {parent.cost_usd}"
            )
        finally:
            _active_budget.set(None)


# ===========================================================================
# 6. Combined branch costs exceeding flow cap after reconciliation
# ===========================================================================


class TestCombinedBranchCostFlowCap:
    """Combined costs from all branches should trigger flow-level cap after reconciliation."""

    @pytest.mark.asyncio
    async def test_token_cap_exceeded_after_reconciliation(self):
        """Flow has token_cap=1000. Branches produce 400+400+300=1100 tokens.
        After reconciliation, check_or_raise raises for token_cap."""
        branches = _make_branches(3)
        costs = [0.10, 0.10, 0.10]
        tokens = [400, 400, 300]
        runner = _make_runner_with_costs(branches, costs, tokens)

        parent = BudgetSession(
            scope_name="workflow:test",
            token_cap=1000,
            on_exceed="fail",
        )
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_10", branches, runner)
            state = WorkflowState()

            with pytest.raises(BudgetKilledException) as exc_info:
                await block.execute(state)

            assert exc_info.value.limit_kind == "token_cap"
            assert exc_info.value.actual_value == 1100
        finally:
            _active_budget.set(None)


# ===========================================================================
# 7. No budget set -> branches run identically to current behavior
# ===========================================================================


class TestNoBudgetSetFallback:
    """When no budget is active, DispatchBlock should run without any overhead."""

    @pytest.mark.asyncio
    async def test_no_active_budget_runs_normally(self):
        """When _active_budget is None, execute works as before with no isolation."""
        branches = _make_branches(2)
        costs = [0.30, 0.40]
        runner = _make_runner_with_costs(branches, costs)

        # Ensure no budget is active
        _active_budget.set(None)

        try:
            block = DispatchBlock("dispatch_11", branches, runner)
            state = WorkflowState()
            result = await block.execute(state)

            # Execution should succeed normally
            assert "dispatch_11" in result.results
            assert result.total_cost_usd == pytest.approx(0.70)

            # All captured sessions should be None (no isolation attempted)
            for s in runner.captured_sessions:
                assert s is None, "Without budget, branches should see no session"
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_no_budget_produces_correct_results(self):
        """Without budget, the dispatch block still produces correct per-exit results."""
        branches = _make_branches(3)
        costs = [0.0, 0.0, 0.0]
        runner = _make_runner_with_costs(branches, costs)

        _active_budget.set(None)

        try:
            block = DispatchBlock("dispatch_12", branches, runner)
            state = WorkflowState()
            result = await block.execute(state)

            # Per-exit results should exist
            assert "dispatch_12.exit_0" in result.results
            assert "dispatch_12.exit_1" in result.results
            assert "dispatch_12.exit_2" in result.results
            # Combined result should exist
            assert "dispatch_12" in result.results
        finally:
            _active_budget.set(None)


# ===========================================================================
# 8. Parent session restored after execute
# ===========================================================================


class TestParentSessionRestored:
    """After DispatchBlock.execute(), _active_budget should be the parent session again."""

    @pytest.mark.asyncio
    async def test_active_budget_is_parent_after_execute(self):
        """_active_budget should be restored to the parent session after execute."""
        branches = _make_branches(2)
        costs = [0.10, 0.10]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=5.0)
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_13", branches, runner)
            state = WorkflowState()
            await block.execute(state)

            # After execute, the parent should be the active budget again
            assert _active_budget.get(None) is parent
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_active_budget_restored_even_on_budget_exception(self):
        """Even when a BudgetKilledException is raised, parent session should be restored."""
        branches = _make_branches(2)
        costs = [1.50, 1.50]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=1.00,
            on_exceed="fail",
        )
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_14", branches, runner)
            state = WorkflowState()

            with pytest.raises(BudgetKilledException):
                await block.execute(state)

            # Parent should still be the active budget
            assert _active_budget.get(None) is parent
        finally:
            _active_budget.set(None)


# ===========================================================================
# 9. Isolated child scope naming
# ===========================================================================


class TestIsolatedChildScopeNaming:
    """Isolated children should have meaningful scope names for debugging."""

    @pytest.mark.asyncio
    async def test_branch_sessions_contain_exit_id_in_scope(self):
        """Each branch session's scope_name should contain the branch exit_id."""
        branches = _make_branches(2)
        costs = [0.10, 0.10]
        runner = _make_runner_with_costs(branches, costs)

        parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=5.0)
        _active_budget.set(parent)

        try:
            block = DispatchBlock("dispatch_15", branches, runner)
            state = WorkflowState()
            await block.execute(state)

            sessions = runner.captured_sessions
            assert len(sessions) == 2
            for i, s in enumerate(sessions):
                assert s is not None
                assert f"exit_{i}" in s.scope_name, (
                    f"Branch session scope should contain exit_id 'exit_{i}', got '{s.scope_name}'"
                )
        finally:
            _active_budget.set(None)
