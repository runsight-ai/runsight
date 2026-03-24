"""
Failing tests for RUN-286: Rewrite FanOutBlock for per-exit tasks and per-exit result keying.

Each branch (exit) gets its own soul + task instruction. Results are keyed per-exit
at state.results["{block_id}.{exit_id}"] and combined at state.results["{block_id}"].

Tests cover ALL acceptance criteria:
- Per-exit task differentiation (each branch gets unique instruction)
- Per-exit result keying (state.results["{block_id}.{exit_id}"])
- Combined result at state.results["{block_id}"]
- exit_handle set to exit_id on per-exit results
- Context inherited from state.current_task.context
- current_task=None doesn't crash (context defaults)
- Stateful mode: per-exit conversation histories keyed by exit_id
- Cost/token aggregation
- FanOutBlockDef with old soul_refs rejects
- FanOutBlockDef with exits (FanOutExitDef list) validates
- build() resolves soul_refs and creates FanOutBranch list
- Empty branches raises ValueError at build time
- Same soul on multiple exits: independent histories in stateful mode
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import FanOutExitDef


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def soul_analyst():
    return Soul(id="analyst", role="Analyst", system_prompt="You are an analyst.")


@pytest.fixture
def soul_reviewer():
    return Soul(id="reviewer", role="Reviewer", system_prompt="You are a reviewer.")


@pytest.fixture
def soul_editor():
    return Soul(
        id="editor",
        role="Editor",
        system_prompt="You are an editor.",
        model_name="claude-3-opus-20240229",
    )


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute_task = AsyncMock()
    runner.model_name = "gpt-4o"
    runner._build_prompt = MagicMock(
        side_effect=lambda task: (
            task.instruction
            if not task.context
            else f"{task.instruction}\n\nContext:\n{task.context}"
        )
    )
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
# 1. FanOutBranch dataclass exists and is importable
# ===========================================================================


class TestFanOutBranchDataclass:
    """FanOutBranch is a dataclass with exit_id, label, soul, task_instruction."""

    def test_importable_from_fanout_module(self):
        """FanOutBranch is importable from runsight_core.blocks.fanout."""
        from runsight_core.blocks.fanout import FanOutBranch

        assert FanOutBranch is not None

    def test_is_dataclass(self):
        """FanOutBranch is a dataclass."""
        from runsight_core.blocks.fanout import FanOutBranch
        import dataclasses

        assert dataclasses.is_dataclass(FanOutBranch)

    def test_has_required_fields(self, soul_analyst):
        """FanOutBranch has exit_id, label, soul, task_instruction."""
        from runsight_core.blocks.fanout import FanOutBranch

        branch = FanOutBranch(
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
# 2. FanOutBlock constructor accepts branches (not souls)
# ===========================================================================


class TestFanOutBlockNewConstructor:
    """FanOutBlock constructor takes (block_id, branches, runner)."""

    def test_accepts_branches_parameter(self, soul_analyst, mock_runner):
        """FanOutBlock can be constructed with branches list."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze this",
            ),
        ]
        block = FanOutBlock("fanout_1", branches, mock_runner)
        assert block.block_id == "fanout_1"

    def test_empty_branches_raises_valueerror(self, mock_runner):
        """FanOutBlock with empty branches list raises ValueError mentioning 'branches'."""
        from runsight_core.blocks.fanout import FanOutBlock

        with pytest.raises(ValueError, match="branches"):
            FanOutBlock("fanout_1", [], mock_runner)

    def test_branches_attribute_accessible(self, soul_analyst, soul_reviewer, mock_runner):
        """FanOutBlock.branches is accessible and contains the provided branches."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze this",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review this",
            ),
        ]
        block = FanOutBlock("fanout_1", branches, mock_runner)
        assert len(block.branches) == 2
        assert block.branches[0].exit_id == "exit_a"
        assert block.branches[1].exit_id == "exit_b"


# ===========================================================================
# 3. Per-exit task differentiation: each branch gets its own Task
# ===========================================================================


class TestPerExitTaskDifferentiation:
    """Each branch receives its own task with its unique instruction."""

    async def test_each_branch_receives_unique_instruction(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """runner.execute_task is called with a different Task.instruction per branch."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze the proposal",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review the proposal",
            ),
        ]

        captured_tasks = {}

        async def _capture(task, soul, **kwargs):
            captured_tasks[soul.id] = task
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_capture)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Parent instruction"))
        await block.execute(state)

        # Analyst branch must have received "Analyze the proposal"
        assert captured_tasks["analyst"].instruction == "Analyze the proposal"
        # Reviewer branch must have received "Review the proposal"
        assert captured_tasks["reviewer"].instruction == "Review the proposal"

    async def test_each_branch_task_has_correct_id_format(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Per-branch Task.id follows format '{block_id}_{exit_id}'."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        captured_tasks = {}

        async def _capture(task, soul, **kwargs):
            captured_tasks[soul.id] = task
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_capture)

        block = FanOutBlock("my_fanout", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Parent instruction"))
        await block.execute(state)

        assert captured_tasks["analyst"].id == "my_fanout_exit_a"
        assert captured_tasks["reviewer"].id == "my_fanout_exit_b"


# ===========================================================================
# 4. Per-exit result keying
# ===========================================================================


class TestPerExitResultKeying:
    """Results stored at state.results["{block_id}.{exit_id}"] per branch."""

    async def test_per_exit_results_stored(self, soul_analyst, soul_reviewer, mock_runner):
        """Each branch's result appears at state.results['{block_id}.{exit_id}']."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

        assert "fan.exit_a" in new_state.results
        assert "fan.exit_b" in new_state.results

    async def test_per_exit_result_contains_correct_output(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Per-exit BlockResult.output matches what the branch produced."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

        assert new_state.results["fan.exit_a"].output == "Output from analyst"
        assert new_state.results["fan.exit_b"].output == "Output from reviewer"

    async def test_per_exit_result_exit_handle_set(self, soul_analyst, soul_reviewer, mock_runner):
        """Per-exit BlockResult has exit_handle set to the exit_id."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

        assert new_state.results["fan.exit_a"].exit_handle == "exit_a"
        assert new_state.results["fan.exit_b"].exit_handle == "exit_b"


# ===========================================================================
# 5. Combined result at state.results["{block_id}"]
# ===========================================================================


class TestCombinedResult:
    """Combined summary result stored at state.results["{block_id}"]."""

    async def test_combined_result_exists(self, soul_analyst, soul_reviewer, mock_runner):
        """state.results[block_id] contains a combined BlockResult."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

        assert "fan" in new_state.results
        assert isinstance(new_state.results["fan"], BlockResult)

    async def test_combined_result_is_json_list(self, soul_analyst, soul_reviewer, mock_runner):
        """Combined result output is a JSON list."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

        parsed = json.loads(new_state.results["fan"].output)
        assert isinstance(parsed, list)
        assert len(parsed) == 2


# ===========================================================================
# 6. Context inherited from state.current_task.context
# ===========================================================================


class TestContextInheritance:
    """Branch tasks inherit context from state.current_task.context."""

    async def test_context_passed_to_branch_task(self, soul_analyst, mock_runner):
        """When current_task has context, each branch's Task.context is set to it."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
        ]

        captured_tasks = {}

        async def _capture(task, soul, **kwargs):
            captured_tasks[soul.id] = task
            return _make_exec_result(task.id, soul.id, "Output")

        mock_runner.execute_task = AsyncMock(side_effect=_capture)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(
            current_task=Task(
                id="parent",
                instruction="Parent instruction",
                context="Budget is $10k",
            )
        )
        await block.execute(state)

        assert captured_tasks["analyst"].context == "Budget is $10k"

    async def test_current_task_none_does_not_crash(self, soul_analyst, mock_runner):
        """When state.current_task is None, context defaults to None and no crash."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
        ]

        captured_tasks = {}

        async def _capture(task, soul, **kwargs):
            captured_tasks[soul.id] = task
            return _make_exec_result(task.id, soul.id, "Output")

        mock_runner.execute_task = AsyncMock(side_effect=_capture)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=None)

        # Must not raise
        await block.execute(state)

        # Context defaults to None
        assert captured_tasks["analyst"].context is None

    async def test_current_task_without_context_passes_none(self, soul_analyst, mock_runner):
        """When current_task exists but has no context, branch task context is None."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
        ]

        captured_tasks = {}

        async def _capture(task, soul, **kwargs):
            captured_tasks[soul.id] = task
            return _make_exec_result(task.id, soul.id, "Output")

        mock_runner.execute_task = AsyncMock(side_effect=_capture)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Parent instruction"))
        await block.execute(state)

        assert captured_tasks["analyst"].context is None


# ===========================================================================
# 7. Cost/token aggregation across branches
# ===========================================================================


class TestCostTokenAggregation:
    """Costs and tokens from all branches are summed into the state."""

    async def test_cost_aggregation(self, soul_analyst, soul_reviewer, mock_runner):
        """total_cost_usd sums costs from all branches."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            if soul.id == "analyst":
                return _make_exec_result(task.id, soul.id, "Out A", cost=0.05, tokens=200)
            return _make_exec_result(task.id, soul.id, "Out B", cost=0.03, tokens=150)

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(
            current_task=Task(id="parent", instruction="Go"),
            total_cost_usd=0.10,
            total_tokens=50,
        )
        new_state = await block.execute(state)

        assert new_state.total_cost_usd == pytest.approx(0.18)  # 0.10 + 0.05 + 0.03
        assert new_state.total_tokens == 400  # 50 + 200 + 150


# ===========================================================================
# 8. FanOutBlockDef schema validation
# ===========================================================================


class TestFanOutBlockDefSchema:
    """FanOutBlockDef validates with exits (FanOutExitDef list), rejects old soul_refs."""

    def test_old_soul_refs_rejected(self):
        """FanOutBlockDef with soul_refs raises ValidationError (extra='forbid')."""
        from runsight_core.blocks.fanout import FanOutBlockDef

        with pytest.raises(ValidationError):
            FanOutBlockDef(
                type="fanout",
                soul_refs=["analyst", "reviewer"],
            )

    def test_exits_with_fanout_exit_defs_validates(self):
        """FanOutBlockDef with exits list of FanOutExitDef objects validates."""
        from runsight_core.blocks.fanout import FanOutBlockDef

        exit_a = FanOutExitDef(id="exit_a", label="Exit A", soul_ref="analyst", task="Analyze")
        exit_b = FanOutExitDef(id="exit_b", label="Exit B", soul_ref="reviewer", task="Review")
        block_def = FanOutBlockDef(type="fanout", exits=[exit_a, exit_b])

        assert len(block_def.exits) == 2
        assert block_def.exits[0].soul_ref == "analyst"
        assert block_def.exits[1].task == "Review"

    def test_exits_field_is_required(self):
        """FanOutBlockDef without exits raises ValidationError mentioning 'exits'."""
        from runsight_core.blocks.fanout import FanOutBlockDef

        with pytest.raises(ValidationError, match="exits"):
            FanOutBlockDef(type="fanout")

    def test_exits_field_typed_as_fanout_exit_def(self):
        """FanOutBlockDef.exits is typed as List[FanOutExitDef] (not List[ExitDef])."""
        from runsight_core.blocks.fanout import FanOutBlockDef

        # The field annotation for exits should reference FanOutExitDef
        exits_field = FanOutBlockDef.model_fields["exits"]
        annotation_str = str(exits_field.annotation)
        assert "FanOutExitDef" in annotation_str, (
            f"Expected exits field to be typed as List[FanOutExitDef], "
            f"got annotation: {annotation_str}"
        )

    def test_no_soul_refs_field_on_model(self):
        """FanOutBlockDef should not have a soul_refs field at all."""
        from runsight_core.blocks.fanout import FanOutBlockDef

        assert "soul_refs" not in FanOutBlockDef.model_fields


# ===========================================================================
# 9. build() function creates FanOutBranch list from exits
# ===========================================================================


class TestBuildFunction:
    """build() resolves soul_refs from exits and creates FanOutBranch list."""

    def test_build_creates_block_with_branches(self, soul_analyst, soul_reviewer, mock_runner):
        """build() reads block_def.exits and returns FanOutBlock with branches."""
        from runsight_core.blocks.fanout import build, FanOutBlockDef

        exit_a = FanOutExitDef(
            id="exit_a", label="Exit A", soul_ref="analyst", task="Analyze the data"
        )
        exit_b = FanOutExitDef(
            id="exit_b", label="Exit B", soul_ref="reviewer", task="Review the data"
        )
        block_def = FanOutBlockDef(type="fanout", exits=[exit_a, exit_b])

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
        from runsight_core.blocks.fanout import build, FanOutBlockDef

        exit_a = FanOutExitDef(id="exit_a", label="Exit A", soul_ref="nonexistent", task="Do stuff")
        block_def = FanOutBlockDef(type="fanout", exits=[exit_a])

        with pytest.raises(ValueError, match="nonexistent"):
            build("fan_1", block_def, {"analyst": soul_analyst}, mock_runner, {})

    def test_build_empty_exits_raises_valueerror(self, mock_runner):
        """build() with an empty exits list raises ValueError mentioning 'branches' or 'exits'."""
        from runsight_core.blocks.fanout import build

        block_def = MagicMock()
        block_def.exits = []

        with pytest.raises(ValueError, match="(?i)branches|exits"):
            build("fan_1", block_def, {}, mock_runner, {})


# ===========================================================================
# 10. Stateful mode: per-exit conversation histories
# ===========================================================================


class TestStatefulPerExitHistories:
    """Stateful mode keys histories by '{block_id}_{exit_id}' (not soul_id)."""

    async def test_stateful_creates_per_exit_history_keys(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Stateful FanOutBlock creates history keys using exit_id, not soul_id."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="analysis",
                label="Analysis",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="review",
                label="Review",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

        # Keys use exit_id, not soul_id
        assert "fan_analysis" in new_state.conversation_histories
        assert "fan_review" in new_state.conversation_histories
        # Old soul_id-based keys must NOT exist
        assert "fan_analyst" not in new_state.conversation_histories
        assert "fan_reviewer" not in new_state.conversation_histories

    async def test_stateful_continuation_reads_per_exit_history(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """On round 2, each branch reads its exit_id-keyed history."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="analysis",
                label="Analysis",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
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

        async def _capture(task, soul, **kwargs):
            captured_messages[task.id] = kwargs.get("messages")
            return _make_exec_result(task.id, soul.id, f"{soul.id} round 2")

        mock_runner.execute_task = AsyncMock(side_effect=_capture)

        block = FanOutBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState(
            current_task=Task(id="parent", instruction="Round 2"),
            conversation_histories={
                "fan_analysis": prior_analysis,
                "fan_review": prior_review,
            },
        )
        await block.execute(state)

        # Analysis branch must have received analysis history
        assert captured_messages["fan_analysis"] is not None
        # Review branch must have received review history
        assert captured_messages["fan_review"] is not None

    async def test_stateful_budget_fitting_uses_branch_soul_model(
        self, soul_analyst, soul_editor, mock_runner
    ):
        """Budget fitting uses each branch's soul model, not a shared model."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="analysis",
                label="Analysis",
                soul=soul_analyst,  # model_name=None -> uses runner default
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="edit",
                label="Edit",
                soul=soul_editor,  # model_name="claude-3-opus-20240229"
                task_instruction="Edit",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))

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
                task=Task(
                    id="budget_task", instruction=request.instruction, context=request.context
                ),
                messages=list(request.conversation_history),
                report=report,
            )

        with patch(
            "runsight_core.blocks.fanout.fit_to_budget",
            side_effect=_tracking_budget,
        ):
            await block.execute(state)

        assert "gpt-4o" in models_seen
        assert "claude-3-opus-20240229" in models_seen


# ===========================================================================
# 11. Same soul on multiple exits: independent histories
# ===========================================================================


class TestSameSoulMultipleExits:
    """Same soul on two different exits produces independent histories."""

    async def test_same_soul_different_exits_independent_histories(self, soul_analyst, mock_runner):
        """When the same soul is used on two different exits, each exit gets
        its own independent conversation history keyed by exit_id."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_cost",
                label="Cost Analysis",
                soul=soul_analyst,
                task_instruction="Analyze costs",
            ),
            FanOutBranch(
                exit_id="exit_risk",
                label="Risk Analysis",
                soul=soul_analyst,  # Same soul, different exit
                task_instruction="Analyze risks",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            if "costs" in task.instruction:
                return _make_exec_result(task.id, soul.id, "COST_OUTPUT")
            return _make_exec_result(task.id, soul.id, "RISK_OUTPUT")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

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

    async def test_same_soul_different_exits_round_2_reads_correct_history(
        self, soul_analyst, mock_runner
    ):
        """On round 2, each exit reads its own history (not the other exit's)."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_cost",
                label="Cost Analysis",
                soul=soul_analyst,
                task_instruction="Analyze costs",
            ),
            FanOutBranch(
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

        async def _capture(task, soul, **kwargs):
            captured_messages[task.id] = kwargs.get("messages")
            return _make_exec_result(task.id, soul.id, f"{soul.id} round 2")

        mock_runner.execute_task = AsyncMock(side_effect=_capture)

        block = FanOutBlock("fan", branches, mock_runner)
        block.stateful = True

        state = WorkflowState(
            current_task=Task(id="parent", instruction="Round 2"),
            conversation_histories={
                "fan_exit_cost": prior_cost,
                "fan_exit_risk": prior_risk,
            },
        )
        await block.execute(state)

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

    async def test_non_stateful_no_history_entries(self, soul_analyst, soul_reviewer, mock_runner):
        """A non-stateful FanOutBlock does not create conversation_histories."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        assert block.stateful is False

        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

        assert new_state.conversation_histories == {}

    async def test_non_stateful_still_produces_per_exit_results(
        self, soul_analyst, soul_reviewer, mock_runner
    ):
        """Non-stateful FanOutBlock still stores per-exit results."""
        from runsight_core.blocks.fanout import FanOutBlock, FanOutBranch

        branches = [
            FanOutBranch(
                exit_id="exit_a",
                label="Exit A",
                soul=soul_analyst,
                task_instruction="Analyze",
            ),
            FanOutBranch(
                exit_id="exit_b",
                label="Exit B",
                soul=soul_reviewer,
                task_instruction="Review",
            ),
        ]

        async def _side_effect(task, soul, **kwargs):
            return _make_exec_result(task.id, soul.id, f"Output from {soul.id}")

        mock_runner.execute_task = AsyncMock(side_effect=_side_effect)

        block = FanOutBlock("fan", branches, mock_runner)
        state = WorkflowState(current_task=Task(id="parent", instruction="Go"))
        new_state = await block.execute(state)

        assert "fan.exit_a" in new_state.results
        assert "fan.exit_b" in new_state.results
        assert "fan" in new_state.results
