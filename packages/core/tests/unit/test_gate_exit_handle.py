"""
Failing tests for RUN-268: GateBlock returns exit_handle pass/fail, delete GateError.

GateBlock.execute() returns BlockResult(exit_handle="pass") or BlockResult(exit_handle="fail")
instead of raising GateError. GateError class deleted entirely. Auto-inject default exits.

Tests cover:
- AC1: GateBlock.execute() never raises on FAIL — returns state normally
- AC2: PASS returns BlockResult with exit_handle="pass"
- AC3: FAIL returns BlockResult with exit_handle="fail"
- AC4: GateError class deleted (no longer importable from gate.py)
- AC5: No metadata writes in GateBlock (no {id}_decision in metadata)
- AC6: Gate with conditional_transitions works standalone (not inside loop)
- AC7: Auto-injected exits: pass and fail when block_def.exits is None
- Extra: GateError import removed from loop.py
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import execute_block_for_test
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "gate_soul") -> Soul:
    return Soul(id=soul_id, kind="soul", name="Gate", role="Gate", system_prompt="Evaluate quality")


def _make_gate(block_id: str = "gate1", eval_key: str = "content", **kwargs):
    """Create a GateBlock with sensible defaults."""
    from runsight_core.blocks.gate import GateBlock

    soul = kwargs.pop("soul", _make_soul())
    runner = kwargs.pop("runner", _mock_runner("PASS"))
    return GateBlock(
        block_id=block_id,
        gate_soul=soul,
        eval_key=eval_key,
        runner=runner,
        **kwargs,
    )


# ==============================================================================
# AC1: GateBlock.execute() never raises on FAIL — returns state normally
# ==============================================================================


class TestGateNeverRaisesOnFail:
    """GateBlock.execute() must return state (not raise) when the gate fails."""

    @pytest.mark.asyncio
    async def test_fail_returns_state_not_exception(self):
        """When runner returns FAIL, execute() must return a WorkflowState, not raise."""
        runner = _mock_runner("FAIL: bad quality")
        block = _make_gate(block_id="gate_f1", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft text")})

        # Current code raises GateError — after RUN-268 this must return normally.
        result_state = await execute_block_for_test(block, state)

        assert isinstance(result_state, WorkflowState)

    @pytest.mark.asyncio
    async def test_fail_does_not_raise_gate_error(self):
        """Ensure no GateError is raised — it should be deleted entirely."""
        runner = _mock_runner("FAIL: needs improvement")
        block = _make_gate(block_id="gate_f2", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Some draft")})

        # Must not raise any exception
        result_state = await execute_block_for_test(block, state)
        assert result_state is not None

    @pytest.mark.asyncio
    async def test_fail_preserves_cost_propagation(self):
        """On FAIL, cost and tokens must still be propagated in the returned state."""
        runner = _mock_runner("FAIL: poor structure", cost=0.03, tokens=150)
        block = _make_gate(block_id="gate_f3", runner=runner)
        state = WorkflowState(
            results={"content": BlockResult(output="Draft")},
            total_cost_usd=1.0,
            total_tokens=500,
        )

        result_state = await execute_block_for_test(block, state)

        assert result_state.total_cost_usd == pytest.approx(1.03)
        assert result_state.total_tokens == 650


# ==============================================================================
# AC2: PASS returns BlockResult with exit_handle="pass"
# ==============================================================================


class TestGatePassExitHandle:
    """PASS path must set exit_handle='pass' on the BlockResult."""

    @pytest.mark.asyncio
    async def test_pass_exit_handle_is_pass(self):
        """BlockResult for PASS must have exit_handle='pass'."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_p1", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Good content")})

        result_state = await execute_block_for_test(block, state)

        assert result_state.results["gate_p1"].exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_pass_output_preserved(self):
        """On PASS, the output field of BlockResult is still populated."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_p2", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Evaluated content")})

        result_state = await execute_block_for_test(block, state)

        result = result_state.results["gate_p2"]
        assert result.output is not None
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_pass_with_extract_field_has_exit_handle(self):
        """PASS with extract_field still sets exit_handle='pass'."""
        import json

        runner = _mock_runner("PASS")
        json_content = [{"author": "extracted_value"}]
        block = _make_gate(
            block_id="gate_p3",
            runner=runner,
            extract_field="author",
        )
        state = WorkflowState(results={"content": BlockResult(output=json.dumps(json_content))})

        result_state = await execute_block_for_test(block, state)

        assert result_state.results["gate_p3"].exit_handle == "pass"


# ==============================================================================
# AC3: FAIL returns BlockResult with exit_handle="fail"
# ==============================================================================


class TestGateFailExitHandle:
    """FAIL path must return BlockResult with exit_handle='fail' and feedback as output."""

    @pytest.mark.asyncio
    async def test_fail_exit_handle_is_fail(self):
        """BlockResult for FAIL must have exit_handle='fail'."""
        runner = _mock_runner("FAIL: bad quality")
        block = _make_gate(block_id="gate_fl1", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft")})

        result_state = await execute_block_for_test(block, state)

        assert result_state.results["gate_fl1"].exit_handle == "fail"

    @pytest.mark.asyncio
    async def test_fail_output_contains_feedback(self):
        """On FAIL, the BlockResult output should contain the feedback reason."""
        runner = _mock_runner("FAIL: missing citations")
        block = _make_gate(block_id="gate_fl2", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft text")})

        result_state = await execute_block_for_test(block, state)

        result = result_state.results["gate_fl2"]
        assert "missing citations" in result.output

    @pytest.mark.asyncio
    async def test_fail_block_result_stored_in_results(self):
        """On FAIL, results[block_id] must be a BlockResult (not absent or None)."""
        runner = _mock_runner("FAIL: incomplete")
        block = _make_gate(block_id="gate_fl3", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Partial draft")})

        result_state = await execute_block_for_test(block, state)

        assert "gate_fl3" in result_state.results
        assert isinstance(result_state.results["gate_fl3"], BlockResult)


# ==============================================================================
# AC4: GateError class deleted — no longer importable
# ==============================================================================


class TestGateErrorDeleted:
    """GateError must be completely removed from gate.py."""

    def test_gate_error_not_importable(self):
        """Importing GateError from gate.py must raise ImportError."""
        with pytest.raises(ImportError):
            from runsight_core.blocks.gate import GateError  # noqa: F401

    def test_gate_module_has_no_gate_error_attr(self):
        """The gate module must not have a 'GateError' attribute at all."""
        import runsight_core.blocks.gate as gate_mod

        assert not hasattr(gate_mod, "GateError")


# ==============================================================================
# AC5: No metadata writes — no {id}_decision in metadata
# ==============================================================================


class TestNoMetadataWrites:
    """GateBlock must not write {block_id}_decision to state.metadata."""

    @pytest.mark.asyncio
    async def test_pass_no_decision_metadata(self):
        """On PASS, metadata must NOT contain '{block_id}_decision'."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_m1", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Good")})

        result_state = await execute_block_for_test(block, state)

        assert "gate_m1_decision" not in result_state.metadata

    @pytest.mark.asyncio
    async def test_fail_no_decision_metadata(self):
        """On FAIL, metadata must NOT contain '{block_id}_decision'."""
        runner = _mock_runner("FAIL: needs work")
        block = _make_gate(block_id="gate_m2", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft")})

        result_state = await execute_block_for_test(block, state)

        assert "gate_m2_decision" not in result_state.metadata

    @pytest.mark.asyncio
    async def test_metadata_unchanged_on_pass(self):
        """On PASS, pre-existing metadata must not gain any _decision key."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_m3", runner=runner)
        state = WorkflowState(
            results={"content": BlockResult(output="Content")},
            metadata={"existing_key": "value"},
        )

        result_state = await execute_block_for_test(block, state)

        # No new *_decision keys should appear
        decision_keys = [k for k in result_state.metadata if k.endswith("_decision")]
        assert decision_keys == []


# ==============================================================================
# AC6: Gate with conditional_transitions works standalone (not inside loop)
# ==============================================================================


class TestGateStandaloneWithConditionalTransitions:
    """Gate can be used standalone; its exit_handle drives conditional_transitions."""

    @pytest.mark.asyncio
    async def test_pass_exit_handle_matches_transition_key(self):
        """On PASS, exit_handle='pass' can be used as a conditional_transition key."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="standalone_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        result_state = await execute_block_for_test(block, state)

        exit_handle = result_state.results["standalone_gate"].exit_handle
        # Simulates conditional_transition lookup: {"pass": "next_block", "fail": "error_block"}
        transitions = {"pass": "next_block", "fail": "error_block"}
        assert exit_handle in transitions
        assert transitions[exit_handle] == "next_block"

    @pytest.mark.asyncio
    async def test_fail_exit_handle_matches_transition_key(self):
        """On FAIL, exit_handle='fail' can be used as a conditional_transition key."""
        runner = _mock_runner("FAIL: not good enough")
        block = _make_gate(block_id="standalone_gate2", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft")})

        result_state = await execute_block_for_test(block, state)

        exit_handle = result_state.results["standalone_gate2"].exit_handle
        transitions = {"pass": "next_block", "fail": "error_block"}
        assert exit_handle in transitions
        assert transitions[exit_handle] == "error_block"

    @pytest.mark.asyncio
    async def test_gate_returns_without_loop_wrapping(self):
        """Gate does not require a LoopBlock wrapper to function — it returns state directly."""
        runner = _mock_runner("FAIL: needs revision")
        block = _make_gate(block_id="solo_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Some text")})

        # Must not raise — standalone gate returns state on both pass and fail
        result_state = await execute_block_for_test(block, state)
        assert isinstance(result_state, WorkflowState)
        assert result_state.results["solo_gate"].exit_handle in ("pass", "fail")


# ==============================================================================
# AC7: Auto-injected exits: pass and fail when block_def.exits is None
# ==============================================================================


class TestAutoInjectExits:
    """build() must auto-inject pass/fail ExitDefs when block_def.exits is None."""

    def test_build_injects_pass_fail_exits_when_none(self):
        """When GateBlockDef.exits is None, build() injects pass and fail ExitDefs."""
        from runsight_core.blocks.gate import GateBlockDef, build

        block_def = GateBlockDef(
            type="gate",
            soul_ref="gate_soul",
            eval_key="content",
            exits=None,
        )
        souls_map = {"gate_soul": _make_soul()}
        runner = _mock_runner("PASS")

        # After build, the block_def should have exits auto-injected
        # (build() mutates or the returned block carries them)
        _block = build("test_gate", block_def, souls_map, runner, {})

        # The block_def.exits should now have pass and fail
        assert block_def.exits is not None
        assert len(block_def.exits) == 2
        exit_ids = [e.id for e in block_def.exits]
        assert "pass" in exit_ids
        assert "fail" in exit_ids

    def test_build_injected_exits_have_correct_labels(self):
        """Auto-injected exits must have labels 'Pass' and 'Fail'."""
        from runsight_core.blocks.gate import GateBlockDef, build

        block_def = GateBlockDef(
            type="gate",
            soul_ref="gate_soul",
            eval_key="content",
            exits=None,
        )
        souls_map = {"gate_soul": _make_soul()}
        runner = _mock_runner("PASS")

        build("test_gate", block_def, souls_map, runner, {})

        exits_by_id = {e.id: e for e in block_def.exits}
        assert exits_by_id["pass"].label == "Pass"
        assert exits_by_id["fail"].label == "Fail"

    def test_build_preserves_explicit_exits(self):
        """When GateBlockDef.exits is explicitly set, build() must NOT overwrite it."""
        from runsight_core.blocks.gate import GateBlockDef, build
        from runsight_core.yaml.schema import ExitDef

        custom_exits = [
            ExitDef(id="approved", label="Approved"),
            ExitDef(id="rejected", label="Rejected"),
        ]
        block_def = GateBlockDef(
            type="gate",
            soul_ref="gate_soul",
            eval_key="content",
            exits=custom_exits,
        )
        souls_map = {"gate_soul": _make_soul()}
        runner = _mock_runner("PASS")

        build("test_gate", block_def, souls_map, runner, {})

        assert len(block_def.exits) == 2
        exit_ids = [e.id for e in block_def.exits]
        assert "approved" in exit_ids
        assert "rejected" in exit_ids

    def test_build_injects_exit_def_types(self):
        """Auto-injected exits must be ExitDef instances."""
        from runsight_core.blocks.gate import GateBlockDef, build
        from runsight_core.yaml.schema import ExitDef

        block_def = GateBlockDef(
            type="gate",
            soul_ref="gate_soul",
            eval_key="content",
            exits=None,
        )
        souls_map = {"gate_soul": _make_soul()}
        runner = _mock_runner("PASS")

        build("test_gate", block_def, souls_map, runner, {})

        for exit_def in block_def.exits:
            assert isinstance(exit_def, ExitDef)


# ==============================================================================
# Extra: GateError import removed from loop.py
# ==============================================================================


class TestGateErrorRemovedFromLoop:
    """GateError import must be removed from loop.py."""

    def test_loop_module_does_not_import_gate_error(self):
        """loop.py must not contain an import of GateError."""
        import inspect

        import runsight_core.blocks.loop as loop_mod

        source = inspect.getsource(loop_mod)
        assert "GateError" not in source, (
            "loop.py still references GateError — the import line must be removed"
        )
