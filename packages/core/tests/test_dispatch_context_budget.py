"""
Tests for Rewrite DispatchBlock for per-exit tasks and per-exit result keying.

Each branch (exit) gets its own soul + task instruction. Results are keyed per-exit
at state.results["{block_id}.{exit_id}"] and combined at state.results["{block_id}"].

Tests cover dispatch behavior:
- Per-exit task differentiation (each branch gets unique instruction)
- Per-exit result keying (state.results["{block_id}.{exit_id}"])
- Combined result at state.results["{block_id}"]
- exit_handle set to exit_id on per-exit results
- Context inherited from state.current_context
- current_task=None doesn't crash (context defaults)
- Stateful mode: per-exit conversation histories keyed by exit_id
- Cost/token aggregation
- DispatchBlockDef with old soul_refs rejects
- DispatchBlockDef with exits (DispatchExitDef list) validates
- build() resolves soul_refs and creates DispatchBranch list
- Empty branches raises ValueError at build time
- Same soul on multiple exits: independent histories in stateful mode
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import execute_block_for_test
from dispatch_block_helpers import (
    make_branches,
    make_dispatch_context,
    make_result,
    setup_runner_side_effect,
)
from runsight_core.block_io import BlockOutput
from runsight_core.budget_enforcement import BudgetSession, _active_budget
from runsight_core.primitives import Soul, Step
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def soul_analyst():
    return Soul(
        id="analyst",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="You are an analyst.",
    )


@pytest.fixture
def soul_reviewer():
    return Soul(
        id="reviewer",
        kind="soul",
        name="Reviewer",
        role="Reviewer",
        system_prompt="You are a reviewer.",
    )


@pytest.fixture
def soul_editor():
    return Soul(
        id="editor",
        kind="soul",
        name="Editor",
        role="Editor",
        system_prompt="You are an editor.",
        model_name="claude-3-opus-20240229",
    )


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o"
    return runner


def _make_exec_result(task_id, soul_id, output, cost=0.0, tokens=0):
    """Helper to create an ExecutionResult."""
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


# ===========================================================================
# 1. DispatchBranch dataclass exists and is importable
# ===========================================================================


class TestContextInheritance:
    """Branch tasks inherit context from state.current_context."""

    @pytest.mark.asyncio
    async def test_context_passed_to_branch_task(self, soul_analyst, mock_runner):
        """When context is passed via resolved_inputs, each branch receives it."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
        ]

        captured_tasks = {}

        async def _capture(instruction, context, soul, **kwargs):
            captured_tasks[soul.id] = {"instruction": instruction, "context": context}
            return _make_exec_result("execute", soul.id, "Output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = DispatchBlock("fan", branches, mock_runner)
        block.declared_inputs = {"context": "shared_memory._resolved_inputs.context"}
        state = WorkflowState(
            shared_memory={"_resolved_inputs": {"context": "Budget is $10k"}},
        )
        await execute_block_for_test(block, state)

        assert captured_tasks["analyst"]["context"] == "Budget is $10k"

    @pytest.mark.asyncio
    async def test_step_declared_context_reaches_each_branch(self, soul_analyst, mock_runner):
        """Step declared inputs flow through BlockContext into every branch call."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
        ]
        captured_contexts = []

        async def _capture(instruction, context, soul, **kwargs):
            captured_contexts.append(context)
            return _make_exec_result("execute", soul.id, "Output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = DispatchBlock("fan", branches, mock_runner)
        step = Step(block=block, declared_inputs={"context": "source"})
        state = WorkflowState(results={"source": BlockResult(output="declared context")})

        await execute_block_for_test(block, state, step=step)

        assert captured_contexts == ["declared context"]

    @pytest.mark.asyncio
    async def test_current_task_none_does_not_crash(self, soul_analyst, mock_runner):
        """When state.current_task is None, context defaults to None and no crash."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
        ]

        captured_tasks = {}

        async def _capture(instruction, context, soul, **kwargs):
            captured_tasks[soul.id] = {"instruction": instruction, "context": context}
            return _make_exec_result("execute", soul.id, "Output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState()

        # Must not raise
        await execute_block_for_test(block, state)

        # Context defaults to None
        assert captured_tasks["analyst"]["context"] is None

    @pytest.mark.asyncio
    async def test_current_task_without_context_passes_none(self, soul_analyst, mock_runner):
        """When current_task exists but has no context, branch task context is None."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
        ]

        captured_tasks = {}

        async def _capture(instruction, context, soul, **kwargs):
            captured_tasks[soul.id] = {"instruction": instruction, "context": context}
            return _make_exec_result("execute", soul.id, "Output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState()
        await execute_block_for_test(block, state)

        assert captured_tasks["analyst"]["context"] is None


# ===========================================================================
# 7. Cost/token aggregation across branches
# ===========================================================================


class TestBudgetIsolation:
    """Branch budget sessions are isolated and reconciled for dispatch gather."""

    @pytest.mark.asyncio
    async def test_active_parent_budget_creates_isolated_branch_sessions(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Each branch executes under a child budget session, never the parent."""
        from runsight_core.blocks.dispatch import DispatchBlock

        captured_sessions: dict[str, object] = {}

        async def _capture_session(instruction, context, soul, **kwargs):
            captured_sessions[soul.id] = _active_budget.get(None)
            return make_result(soul.id, f"{soul.id} output", cost=0.001, tokens=10)

        mock_runner.execute = AsyncMock(side_effect=_capture_session)
        parent = BudgetSession(scope_name="workflow:dispatch_v2", cost_cap_usd=1.0)
        token = _active_budget.set(parent)
        try:
            block = DispatchBlock("fan", make_branches(soul_analyst, soul_reviewer), mock_runner)
            await block.execute(make_dispatch_context("fan"))
        finally:
            _active_budget.reset(token)

        assert set(captured_sessions) == {"analyst", "reviewer"}
        assert captured_sessions["analyst"] is not parent
        assert captured_sessions["reviewer"] is not parent
        assert captured_sessions["analyst"] is not captured_sessions["reviewer"]

    @pytest.mark.asyncio
    async def test_dispatch_without_parent_budget_runs_plain_block_output(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Dispatch still returns BlockOutput when no parent budget session exists."""
        from runsight_core.blocks.dispatch import DispatchBlock

        setup_runner_side_effect(
            mock_runner,
            {
                "analyst": make_result("analyst", "Alpha."),
                "reviewer": make_result("reviewer", "Beta."),
            },
        )
        assert _active_budget.get(None) is None

        block = DispatchBlock("fan", make_branches(soul_analyst, soul_reviewer), mock_runner)
        output = await block.execute(make_dispatch_context("fan"))

        assert isinstance(output, BlockOutput)
        assert len(json.loads(output.output)) == 2

    @pytest.mark.asyncio
    async def test_parent_budget_reconciles_branch_costs_after_gather(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Parent budget totals include all child branch spend after dispatch."""
        from runsight_core.blocks.dispatch import DispatchBlock

        results_by_soul = {
            "analyst": make_result("analyst", "Alpha.", cost=0.05, tokens=500),
            "reviewer": make_result("reviewer", "Beta.", cost=0.03, tokens=300),
        }

        async def _accruing_side_effect(instruction, context, soul, **kwargs):
            result = results_by_soul[soul.id]
            session = _active_budget.get(None)
            if session is not None:
                session.accrue(cost_usd=result.cost_usd, tokens=result.total_tokens)
            return result

        mock_runner.execute = AsyncMock(side_effect=_accruing_side_effect)
        parent = BudgetSession(scope_name="workflow:dispatch_v2", cost_cap_usd=10.0)
        token = _active_budget.set(parent)
        try:
            block = DispatchBlock("fan", make_branches(soul_analyst, soul_reviewer), mock_runner)
            await block.execute(make_dispatch_context("fan"))
        finally:
            _active_budget.reset(token)

        assert parent.cost_usd == pytest.approx(0.08)
        assert parent.tokens == 800


# ===========================================================================
# 8. DispatchBlockDef schema validation
# ===========================================================================
