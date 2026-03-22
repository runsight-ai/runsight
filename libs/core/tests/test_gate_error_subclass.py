"""
Failing tests for RUN-254: Create GateError subclass instead of monkey-patching ValueError.

Tests cover:
- GateError class exists and is importable from gate.py
- GateError inherits from Exception (not ValueError)
- GateError.__init__ accepts message, gate_id, state and stores them as attributes
- gate.py source does NOT monkey-patch .state onto exceptions (no `error.state =` pattern)
- GateBlock.execute() raises GateError (not ValueError) on gate failure
- LoopBlock catches GateError for gate retry logic (continues loop on gate failure)
"""

import inspect
import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState


# ── Helpers ──────────────────────────────────────────────────────────────


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.execute_task = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "gate_soul") -> Soul:
    return Soul(id=soul_id, role="Gate", system_prompt="Evaluate quality")


# ===========================================================================
# 1. GateError class — existence and inheritance
# ===========================================================================


class TestGateErrorClassExists:
    """GateError is importable from the gate module."""

    def test_gate_error_importable(self):
        """GateError should be importable from runsight_core.blocks.gate."""
        from runsight_core.blocks.gate import GateError

        assert GateError is not None

    def test_gate_error_is_exception_subclass(self):
        """GateError must inherit from Exception, not ValueError."""
        from runsight_core.blocks.gate import GateError

        assert issubclass(GateError, Exception)

    def test_gate_error_is_not_value_error_subclass(self):
        """GateError must NOT inherit from ValueError — avoids silent swallowing."""
        from runsight_core.blocks.gate import GateError

        assert not issubclass(GateError, ValueError)


# ===========================================================================
# 2. GateError structured fields — gate_id and state in __init__
# ===========================================================================


class TestGateErrorStructuredFields:
    """GateError stores gate_id and state as constructor params, not monkey-patched."""

    def test_gate_error_has_gate_id_attribute(self):
        """GateError(message, gate_id=..., state=...) stores gate_id."""
        from runsight_core.blocks.gate import GateError

        state = WorkflowState()
        err = GateError("test failure", gate_id="gate_1", state=state)
        assert err.gate_id == "gate_1"

    def test_gate_error_has_state_attribute(self):
        """GateError(message, gate_id=..., state=...) stores state."""
        from runsight_core.blocks.gate import GateError

        state = WorkflowState(metadata={"key": "value"})
        err = GateError("test failure", gate_id="gate_2", state=state)
        assert err.state is state
        assert err.state.metadata["key"] == "value"

    def test_gate_error_message_in_str(self):
        """str(GateError) should contain the message."""
        from runsight_core.blocks.gate import GateError

        state = WorkflowState()
        err = GateError("gate check failed", gate_id="gate_3", state=state)
        assert "gate check failed" in str(err)

    def test_gate_error_is_instantiable(self):
        """GateError can be raised and caught with structured fields intact."""
        from runsight_core.blocks.gate import GateError

        state = WorkflowState()
        with pytest.raises(GateError) as exc_info:
            raise GateError("fail reason", gate_id="g1", state=state)

        assert exc_info.value.gate_id == "g1"
        assert exc_info.value.state is state


# ===========================================================================
# 3. No monkey-patching — source code inspection
# ===========================================================================


class TestNoMonkeyPatching:
    """gate.py must not monkey-patch .state onto exception objects."""

    def test_gate_source_has_no_error_dot_state_assignment(self):
        """The source of gate.py must not contain `error.state =` pattern."""
        source = inspect.getsource(GateBlock)
        # Match patterns like `error.state = ...` or `e.state = ...`
        monkey_patch_pattern = re.compile(r"\w+\.state\s*=\s*(?!self)")
        matches = monkey_patch_pattern.findall(source)
        assert len(matches) == 0, f"Found monkey-patch pattern(s) in GateBlock source: {matches}"


# ===========================================================================
# 4. GateBlock raises GateError on failure
# ===========================================================================


class TestGateBlockRaisesGateError:
    """GateBlock.execute() raises GateError (not ValueError) when gate fails."""

    @pytest.mark.asyncio
    async def test_gate_fail_raises_gate_error(self):
        """When runner returns FAIL, GateBlock should raise GateError."""
        from runsight_core.blocks.gate import GateError

        runner = _mock_runner("FAIL: poor quality")
        block = GateBlock(
            block_id="gate_test",
            gate_soul=_make_soul(),
            eval_key="content",
            runner=runner,
        )
        state = WorkflowState(results={"content": BlockResult(output="Draft text")})

        with pytest.raises(GateError):
            await block.execute(state)

    @pytest.mark.asyncio
    async def test_gate_error_contains_gate_id(self):
        """The raised GateError should contain the gate's block_id."""
        from runsight_core.blocks.gate import GateError

        runner = _mock_runner("FAIL: needs work")
        block = GateBlock(
            block_id="quality_gate",
            gate_soul=_make_soul(),
            eval_key="draft",
            runner=runner,
        )
        state = WorkflowState(results={"draft": BlockResult(output="Some draft")})

        with pytest.raises(GateError) as exc_info:
            await block.execute(state)

        assert exc_info.value.gate_id == "quality_gate"

    @pytest.mark.asyncio
    async def test_gate_error_contains_updated_state(self):
        """The raised GateError should carry the updated state (with cost/tokens)."""
        from runsight_core.blocks.gate import GateError

        runner = _mock_runner("FAIL: bad", cost=0.05, tokens=200)
        block = GateBlock(
            block_id="cost_gate",
            gate_soul=_make_soul(),
            eval_key="data",
            runner=runner,
        )
        state = WorkflowState(
            results={"data": BlockResult(output="Content")},
            total_cost_usd=1.0,
            total_tokens=500,
        )

        with pytest.raises(GateError) as exc_info:
            await block.execute(state)

        err_state = exc_info.value.state
        assert err_state.total_cost_usd == 1.0 + 0.05
        assert err_state.total_tokens == 500 + 200
        assert err_state.metadata["cost_gate_decision"] == "fail"


# ===========================================================================
# 5. LoopBlock catches GateError for retry logic
# ===========================================================================


class _GateFailBlock(BaseBlock):
    """Simulates a gate that fails on the first N calls, then passes."""

    def __init__(self, block_id: str, fail_count: int = 1):
        super().__init__(block_id)
        self.fail_count = fail_count
        self._call_count = 0

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        from runsight_core.blocks.gate import GateError

        self._call_count += 1
        if self._call_count <= self.fail_count:
            updated_state = state.model_copy(
                update={
                    "metadata": {
                        **state.metadata,
                        f"{self.block_id}_decision": "fail",
                    }
                }
            )
            raise GateError(
                f"Gate {self.block_id} failed on call {self._call_count}",
                gate_id=self.block_id,
                state=updated_state,
            )
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output="PASS"),
                },
                "metadata": {
                    **state.metadata,
                    f"{self.block_id}_decision": "pass",
                },
            }
        )


class TestLoopBlockCatchesGateError:
    """LoopBlock should catch GateError from inner blocks and continue to next round."""

    @pytest.mark.asyncio
    async def test_loop_continues_on_gate_error(self):
        """When an inner gate block raises GateError, LoopBlock should catch it and retry."""
        gate = _GateFailBlock("gate_block", fail_count=2)
        blocks = {"gate_block": gate}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["gate_block"],
            max_rounds=5,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Gate failed on rounds 1 and 2, passed on round 3 — loop should complete
        assert gate._call_count == 3
        assert result_state.results["gate_block"].output == "PASS"

    @pytest.mark.asyncio
    async def test_loop_exhausts_rounds_on_persistent_gate_failure(self):
        """If gate always fails, LoopBlock should exhaust max_rounds and still raise GateError."""
        from runsight_core.blocks.gate import GateError

        gate = _GateFailBlock("gate_block", fail_count=100)  # always fails
        blocks = {"gate_block": gate}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["gate_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        with pytest.raises(GateError):
            await loop.execute(state, blocks=blocks)

        # All 3 rounds should have been attempted
        assert gate._call_count == 3

    @pytest.mark.asyncio
    async def test_loop_preserves_state_from_gate_error(self):
        """When GateError is caught, the state from the error should be used for the next round."""

        gate = _GateFailBlock("gate_block", fail_count=1)
        blocks = {"gate_block": gate}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["gate_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Gate failed once, passed on second round
        assert gate._call_count == 2
        assert result_state.metadata.get("gate_block_decision") == "pass"

    @pytest.mark.asyncio
    async def test_loop_does_not_catch_value_error(self):
        """LoopBlock should NOT catch generic ValueError — only GateError."""

        class ValueErrorBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                raise ValueError("not a gate error")

        bad_block = ValueErrorBlock("bad_block")
        blocks = {"bad_block": bad_block}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["bad_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        with pytest.raises(ValueError, match="not a gate error"):
            await loop.execute(state, blocks=blocks)
