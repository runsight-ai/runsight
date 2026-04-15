"""
Failing tests for RUN-286: Rewrite DispatchBlock for per-exit tasks and per-exit result keying.

Each branch (exit) gets its own soul + task instruction. Results are keyed per-exit
at state.results["{block_id}.{exit_id}"] and combined at state.results["{block_id}"].

Tests cover ALL acceptance criteria:
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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import execute_block_for_test
from pydantic import ValidationError
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import DispatchExitDef

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


class TestDispatchBranchDataclass:
    """DispatchBranch is a dataclass with exit_id, label, soul, task_instruction."""

    def test_importable_from_dispatch_module(self):
        """DispatchBranch is importable from runsight_core.blocks.dispatch."""
        from runsight_core.blocks.dispatch import DispatchBranch

        assert DispatchBranch is not None

    def test_is_dataclass(self):
        """DispatchBranch is a dataclass."""
        import dataclasses

        from runsight_core.blocks.dispatch import DispatchBranch

        assert dataclasses.is_dataclass(DispatchBranch)

    def test_has_required_fields(self, soul_analyst):
        """DispatchBranch has exit_id, label, soul, task_instruction."""
        from runsight_core.blocks.dispatch import DispatchBranch

        branch = DispatchBranch(
            exit_id="exit_a",
            label="Exit A",
            soul=soul_analyst,
            task_instruction="Analyze the data",
        )
        assert branch.exit_id == "exit_a"
        assert branch.label == "Exit A"
        assert branch.soul is soul_analyst
        assert branch.task_instruction == "Analyze the data"


# ===========================================================================
# 2. DispatchBlock constructor accepts branches (not souls)
# ===========================================================================


class TestDispatchBlockNewConstructor:
    """DispatchBlock constructor takes (block_id, branches, runner)."""

    def test_accepts_branches_parameter(self, soul_analyst, mock_runner):
        """DispatchBlock can be constructed with branches list."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze this",
            ),
        ]
        block = DispatchBlock("dispatch_1", branches, mock_runner)
        assert block.block_id == "dispatch_1"

    def test_empty_branches_raises_valueerror(self, mock_runner):
        """DispatchBlock with empty branches list raises ValueError mentioning 'branches'."""
        from runsight_core.blocks.dispatch import DispatchBlock

        with pytest.raises(ValueError, match="branches"):
            DispatchBlock("dispatch_1", [], mock_runner)

    def test_branches_attribute_accessible(self, soul_analyst, soul_reviewer, mock_runner):
        """DispatchBlock.branches is accessible and contains the provided branches."""
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze this",
            ),
            DispatchBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review this",
            ),
        ]
        block = DispatchBlock("dispatch_1", branches, mock_runner)
        assert len(block.branches) == 2
        assert block.branches[0].exit_id == "exit_a"
        assert block.branches[1].exit_id == "exit_b"


# ===========================================================================
# 3. Per-exit task differentiation: each branch gets its own Task
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
# 6. Context inherited from state.current_context
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
        state = WorkflowState(
            shared_memory={"_resolved_inputs": {"context": "Budget is $10k"}},
        )
        await execute_block_for_test(block, state)

        assert captured_tasks["analyst"]["context"] == "Budget is $10k"

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
# 8. DispatchBlockDef schema validation
# ===========================================================================


class TestDispatchBlockDefSchema:
    """DispatchBlockDef validates with exits (DispatchExitDef list), rejects old soul_refs."""

    def test_old_soul_refs_rejected(self):
        """DispatchBlockDef with soul_refs raises ValidationError (extra='forbid')."""
        from runsight_core.blocks.dispatch import DispatchBlockDef

        with pytest.raises(ValidationError):
            DispatchBlockDef(
                type="dispatch",
                soul_refs=["analyst", "reviewer"],
            )

    def test_exits_with_dispatch_exit_defs_validates(self):
        """DispatchBlockDef with exits list of DispatchExitDef objects validates."""
        from runsight_core.blocks.dispatch import DispatchBlockDef

        exit_a = DispatchExitDef(id="exit_a", label="Exit A", soul_ref="analyst", task="Analyze")
        exit_b = DispatchExitDef(id="exit_b", label="Exit B", soul_ref="reviewer", task="Review")
        block_def = DispatchBlockDef(type="dispatch", exits=[exit_a, exit_b])

        assert len(block_def.exits) == 2
        assert block_def.exits[0].soul_ref == "analyst"
        assert block_def.exits[1].task == "Review"

    def test_exits_field_is_required(self):
        """DispatchBlockDef without exits raises ValidationError mentioning 'exits'."""
        from runsight_core.blocks.dispatch import DispatchBlockDef

        with pytest.raises(ValidationError, match="exits"):
            DispatchBlockDef(type="dispatch")

    def test_exits_field_typed_as_dispatch_exit_def(self):
        """DispatchBlockDef.exits is typed as List[DispatchExitDef] (not List[ExitDef])."""
        from runsight_core.blocks.dispatch import DispatchBlockDef

        # The field annotation for exits should reference DispatchExitDef
        exits_field = DispatchBlockDef.model_fields["exits"]
        annotation_str = str(exits_field.annotation)
        assert "DispatchExitDef" in annotation_str, (
            f"Expected exits field to be typed as List[DispatchExitDef], "
            f"got annotation: {annotation_str}"
        )

    def test_no_soul_refs_field_on_model(self):
        """DispatchBlockDef should not have a soul_refs field at all."""
        from runsight_core.blocks.dispatch import DispatchBlockDef

        assert "soul_refs" not in DispatchBlockDef.model_fields


# ===========================================================================
# 9. build() function creates DispatchBranch list from exits
# ===========================================================================


class TestBuildFunction:
    """build() resolves soul_refs from exits and creates DispatchBranch list."""

    def test_build_creates_block_with_branches(self, soul_analyst, soul_reviewer, mock_runner):
        """build() reads block_def.exits and returns DispatchBlock with branches."""
        from runsight_core.blocks.dispatch import DispatchBlockDef, build

        exit_a = DispatchExitDef(
            id="exit_a", label="Exit A", soul_ref="analyst", task="Analyze the data"
        )
        exit_b = DispatchExitDef(
            id="exit_b", label="Exit B", soul_ref="reviewer", task="Review the data"
        )
        block_def = DispatchBlockDef(type="dispatch", exits=[exit_a, exit_b])

        souls_map = {"analyst": soul_analyst, "reviewer": soul_reviewer}
        block = build("fan_1", block_def, souls_map, mock_runner, {})

        assert len(block.branches) == 2
        assert block.branches[0].exit_id == "exit_a"
        assert block.branches[0].soul is soul_analyst
        assert block.branches[0].task_instruction == "Analyze the data"
        assert block.branches[1].exit_id == "exit_b"
        assert block.branches[1].soul is soul_reviewer
        assert block.branches[1].task_instruction == "Review the data"

    def test_build_raises_on_missing_soul_ref(self, soul_analyst, mock_runner):
        """build() raises ValueError when a soul_ref is not in souls_map."""
        from runsight_core.blocks.dispatch import DispatchBlockDef, build

        exit_a = DispatchExitDef(
            id="exit_a",
            label="Exit A",
            soul_ref="nonexistent",
            task="Do stuff",
        )
        block_def = DispatchBlockDef(type="dispatch", exits=[exit_a])

        with pytest.raises(ValueError, match="nonexistent"):
            build("fan_1", block_def, {"analyst": soul_analyst}, mock_runner, {})

    def test_build_empty_exits_raises_valueerror(self, mock_runner):
        """build() with an empty exits list raises ValueError mentioning 'branches' or 'exits'."""
        from runsight_core.blocks.dispatch import build

        block_def = MagicMock()
        block_def.exits = []

        with pytest.raises(ValueError, match="(?i)branches|exits"):
            build("fan_1", block_def, {}, mock_runner, {})


# ===========================================================================
# 10. Stateful mode: per-exit conversation histories
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
