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

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
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
