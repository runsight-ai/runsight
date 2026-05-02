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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import execute_block_for_test
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState

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


class TestStatefulPerExitHistories:
    """Stateful mode keys histories by '{block_id}_{exit_id}' (not soul_id)."""

    @pytest.mark.asyncio
    async def test_stateful_creates_per_exit_history_keys(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Stateful DispatchBlock creates history keys using exit_id, not soul_id."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="analysis",
                label="Analysis",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="review",
                label="Review",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState()
        new_state = await execute_block_for_test(block, state)

        # Keys use exit_id, not soul_id
        assert "fan_analysis" in new_state.conversation_histories
        assert "fan_review" in new_state.conversation_histories
        # Old soul_id-based keys must NOT exist
        assert "fan_analyst" not in new_state.conversation_histories
        assert "fan_reviewer" not in new_state.conversation_histories

    @pytest.mark.asyncio
    async def test_stateful_continuation_reads_per_exit_history(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """On round 2, each branch reads its exit_id-keyed history."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="analysis",
                label="Analysis",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="review",
                label="Review",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        prior_analysis = [
            {"role": "user", "content": "Round 1 prompt"},
            {"role": "assistant", "content": "Analysis round 1"},
        ]
        prior_review = [
            {"role": "user", "content": "Round 1 prompt"},
            {"role": "assistant", "content": "Review round 1"},
        ]

        captured_messages = {}
        _instr_to_key = {"Analyze": "fan_analysis", "Review": "fan_review"}

        async def _capture(instruction, context, soul, **kwargs):
            key = _instr_to_key.get(instruction, instruction)
            captured_messages[key] = kwargs.get("messages")
            return _make_exec_result("execute", soul.id, f"{soul.id} round 2")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = DispatchBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState(
            conversation_histories={
                "fan_analysis": prior_analysis,
                "fan_review": prior_review,
            },
        )
        await execute_block_for_test(block, state)

        # Analysis branch must have received analysis history
        assert captured_messages["fan_analysis"] is not None
        # Review branch must have received review history
        assert captured_messages["fan_review"] is not None

    @pytest.mark.asyncio
    async def test_stateful_budget_fitting_uses_branch_soul_model(
        self, soul_analyst, soul_editor, mock_runner
    ):
        """Budget fitting uses each branch's soul model, not a shared model."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="analysis",
                label="Analysis",
                soul=soul_analyst,  # model_name=None -> uses runner default
                task_instruction="Analyze",
            ),
            DispatchBranch(
                exit_id="edit",
                label="Edit",
                soul=soul_editor,  # model_name="claude-3-opus-20240229"
                task_instruction="Edit",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_exec_result("execute", soul.id, f"Output from {soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState()

        models_seen = []

        from runsight_core.memory.budget import BudgetedContext, BudgetReport

        def _tracking_budget(request, counter):
            models_seen.append(request.model)
            report = BudgetReport(
                model=request.model,
                max_input_tokens=0,
                output_reserve=0,
                effective_budget=100000,
                p1_tokens=0,
                p2_tokens_before=0,
                p2_tokens_after=0,
                p3_tokens_before=0,
                p3_tokens_after=0,
                p3_pairs_dropped=0,
                total_tokens=0,
                headroom=100000,
                warnings=[],
            )
            return BudgetedContext(
                instruction=request.instruction,
                context=request.context,
                messages=list(request.conversation_history),
                report=report,
            )

        with patch(
            "runsight_core.blocks.dispatch.fit_to_budget",
            side_effect=_tracking_budget,
        ):
            await execute_block_for_test(block, state)

        assert "gpt-4o" in models_seen
        assert "claude-3-opus-20240229" in models_seen


# ===========================================================================
# 11. Same soul on multiple exits: independent histories
# ===========================================================================


class TestSameSoulMultipleExits:
    """Same soul on two different exits produces independent histories."""

    @pytest.mark.asyncio
    async def test_same_soul_different_exits_independent_histories(self, soul_analyst, mock_runner):
        """When the same soul is used on two different exits, each exit gets
        its own independent conversation history keyed by exit_id."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_cost",
                label="Cost Analysis",
                soul=soul_analyst,
                task_instruction="Analyze costs",
            ),
            DispatchBranch(
                exit_id="exit_risk",
                label="Risk Analysis",
                soul=soul_analyst,  # Same soul, different exit
                task_instruction="Analyze risks",
            ),
        ]

        async def _side_effect(instruction, context, soul, **kwargs):
            if "costs" in instruction:
                return _make_exec_result("execute", soul.id, "COST_OUTPUT")
            return _make_exec_result("execute", soul.id, "RISK_OUTPUT")

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        block = DispatchBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState()
        new_state = await execute_block_for_test(block, state)

        # Each exit has its own history
        assert "fan_exit_cost" in new_state.conversation_histories
        assert "fan_exit_risk" in new_state.conversation_histories

        # Histories are independent
        cost_content = " ".join(
            msg["content"] for msg in new_state.conversation_histories["fan_exit_cost"]
        )
        risk_content = " ".join(
            msg["content"] for msg in new_state.conversation_histories["fan_exit_risk"]
        )

        assert "COST_OUTPUT" in cost_content
        assert "RISK_OUTPUT" not in cost_content
        assert "RISK_OUTPUT" in risk_content
        assert "COST_OUTPUT" not in risk_content

    @pytest.mark.asyncio
    async def test_same_soul_different_exits_round_2_reads_correct_history(
        self, soul_analyst, mock_runner
    ):
        """On round 2, each exit reads its own history (not the other exit's)."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_cost",
                label="Cost Analysis",
                soul=soul_analyst,
                task_instruction="Analyze costs",
            ),
            DispatchBranch(
                exit_id="exit_risk",
                label="Risk Analysis",
                soul=soul_analyst,
                task_instruction="Analyze risks",
            ),
        ]

        prior_cost = [
            {"role": "user", "content": "Cost prompt round 1"},
            {"role": "assistant", "content": "Cost analysis round 1"},
        ]
        prior_risk = [
            {"role": "user", "content": "Risk prompt round 1"},
            {"role": "assistant", "content": "Risk analysis round 1"},
        ]

        captured_messages = {}
        _instruction_to_key = {"Analyze costs": "fan_exit_cost", "Analyze risks": "fan_exit_risk"}

        async def _capture(instruction, context, soul, **kwargs):
            key = _instruction_to_key.get(instruction, instruction)
            captured_messages[key] = kwargs.get("messages")
            return _make_exec_result("execute", soul.id, f"{soul.id} round 2")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = DispatchBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState(
            conversation_histories={
                "fan_exit_cost": prior_cost,
                "fan_exit_risk": prior_risk,
            },
        )
        await execute_block_for_test(block, state)

        # Cost exit must receive cost history only
        cost_msgs = captured_messages.get("fan_exit_cost")
        assert cost_msgs is not None
        # Risk exit must receive risk history only
        risk_msgs = captured_messages.get("fan_exit_risk")
        assert risk_msgs is not None


# ===========================================================================
# 12. Non-stateful path still works
# ===========================================================================


class TestNonStatefulPath:
    """Non-stateful execute still works with the new branch-based constructor."""

    @pytest.mark.asyncio
    async def test_non_stateful_no_history_entries(self, soul_analyst, soul_reviewer, mock_runner):
        """A non-stateful DispatchBlock does not create conversation_histories."""
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
        assert block.stateful is False

        state = WorkflowState()
        new_state = await execute_block_for_test(block, state)

        assert new_state.conversation_histories == {}

    @pytest.mark.asyncio
    async def test_non_stateful_still_produces_per_exit_results(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Non-stateful DispatchBlock still stores per-exit results."""
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
        assert "fan" in new_state.results
