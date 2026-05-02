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
from runsight_core.primitives import Soul
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


class TestPerExitTaskDifferentiation:
    """Each branch receives its own task with its unique instruction."""

    @pytest.mark.asyncio
    async def test_each_branch_receives_unique_instruction(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """runner.execute_task is called with a different Task.instruction per branch."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze the proposal",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review the proposal",
            ),
        ]

        captured_tasks = {}

        async def _capture(instruction, context, soul, **kwargs):
            captured_tasks[soul.id] = {"instruction": instruction, "context": context}
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState()
        await execute_block_for_test(block, state)

        # Analyst branch must have received "Analyze the proposal"
        assert captured_tasks["analyst"]["instruction"] == "Analyze the proposal"
        # Reviewer branch must have received "Review the proposal"
        assert captured_tasks["reviewer"]["instruction"] == "Review the proposal"

    @pytest.mark.asyncio
    async def test_each_branch_task_has_correct_id_format(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Each branch's instruction must reach the runner correctly."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        captured_tasks = {}

        async def _capture(instruction, context, soul, **kwargs):
            captured_tasks[soul.id] = {"instruction": instruction, "context": context}
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = DispatchBlock("my_dispatch", branches, mock_runner)
        state = WorkflowState()
        await execute_block_for_test(block, state)

        assert captured_tasks["analyst"]["instruction"] == "Analyze"
        assert captured_tasks["reviewer"]["instruction"] == "Review"


# ===========================================================================
# 4. Per-exit result keying
# ===========================================================================


class TestPerExitResultKeying:
    """Results stored at state.results["{block_id}.{exit_id}"] per branch."""

    @pytest.mark.asyncio
    async def test_per_exit_results_stored(self, soul_analyst, soul_reviewer, mock_runner):
        """Each branch's result appears at state.results['{block_id}.{exit_id}']."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState()
        new_state = await execute_block_for_test(block, state)

        assert "fan.exit_a" in new_state.results
        assert "fan.exit_b" in new_state.results

    @pytest.mark.asyncio
    async def test_per_exit_result_contains_correct_output(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Per-exit BlockResult.output matches what the branch produced."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState()
        new_state = await execute_block_for_test(block, state)

        assert new_state.results["fan.exit_a"].output == "Output from analyst"
        assert new_state.results["fan.exit_b"].output == "Output from reviewer"

    @pytest.mark.asyncio
    async def test_per_exit_result_exit_handle_set(self, soul_analyst, soul_reviewer, mock_runner):
        """Per-exit BlockResult has exit_handle set to the exit_id."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState()
        new_state = await execute_block_for_test(block, state)

        assert new_state.results["fan.exit_a"].exit_handle == "exit_a"
        assert new_state.results["fan.exit_b"].exit_handle == "exit_b"


# ===========================================================================
# 5. Combined result at state.results["{block_id}"]
# ===========================================================================


class TestCombinedResult:
    """Combined summary result stored at state.results["{block_id}"]."""

    @pytest.mark.asyncio
    async def test_combined_result_exists(self, soul_analyst, soul_reviewer, mock_runner):
        """state.results[block_id] contains a combined BlockResult."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState()
        new_state = await execute_block_for_test(block, state)

        assert "fan" in new_state.results
        assert isinstance(new_state.results["fan"], BlockResult)

    @pytest.mark.asyncio
    async def test_combined_result_is_json_list(self, soul_analyst, soul_reviewer, mock_runner):
        """Combined result output is a JSON list."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState()
        new_state = await execute_block_for_test(block, state)

        parsed = json.loads(new_state.results["fan"].output)
        assert isinstance(parsed, list)
        assert len(parsed) == 2


# ===========================================================================
# 5b. Direct BlockOutput contract
# ===========================================================================


class TestDirectBlockOutputContract:
    """DispatchBlock.execute returns combined output plus per-exit BlockResult data."""

    @pytest.mark.asyncio
    async def test_block_output_contains_combined_output_cost_and_extra_results(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Direct execution exposes the same public result contract before state apply."""
        from runsight_core.blocks.dispatch import DispatchBlock

        setup_runner_side_effect(
            mock_runner,
            {
                "analyst": make_result("analyst", "Alpha final.", cost=0.04, tokens=400),
                "reviewer": make_result("reviewer", "Beta final.", cost=0.06, tokens=600),
            },
        )
        block = DispatchBlock("fan", make_branches(soul_analyst, soul_reviewer), mock_runner)

        output = await block.execute(make_dispatch_context("fan"))

        assert isinstance(output, BlockOutput)
        assert output.cost_usd == pytest.approx(0.10)
        assert output.total_tokens == 1000

        combined = json.loads(output.output)
        assert {item["exit_id"] for item in combined} == {"exit_a", "exit_b"}

        assert output.extra_results is not None
        assert set(output.extra_results) == {"fan.exit_a", "fan.exit_b"}
        assert output.extra_results["fan.exit_a"].output == "Alpha final."
        assert output.extra_results["fan.exit_a"].exit_handle == "exit_a"
        assert output.extra_results["fan.exit_b"].output == "Beta final."
        assert output.extra_results["fan.exit_b"].exit_handle == "exit_b"


# ===========================================================================
# 6. Context inherited from state.current_context
# ===========================================================================


class TestCostTokenAggregation:
    """Costs and tokens from all branches are summed into the state."""

    @pytest.mark.asyncio
    async def test_cost_aggregation(self, soul_analyst, soul_reviewer, mock_runner):
        """total_cost_usd sums costs from all branches."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            if soul.id == "analyst":
                return _make_exec_result("execute", soul.id, "Out A", cost=0.05, tokens=200)
            return _make_exec_result("execute", soul.id, "Out B", cost=0.03, tokens=150)

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        state = WorkflowState(
            total_cost_usd=0.10,
            total_tokens=50,
        )
        new_state = await execute_block_for_test(block, state)

        assert new_state.total_cost_usd == pytest.approx(0.18)  # 0.10 + 0.05 + 0.03
        assert new_state.total_tokens == 400  # 50 + 200 + 150


# ===========================================================================
# 7b. Budget isolation
# ===========================================================================
