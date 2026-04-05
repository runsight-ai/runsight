"""
Failing tests for RUN-395: ISO-005 — Migrate LinearBlock + GateBlock + SynthesizeBlock
to subprocess via IsolatedBlockWrapper.

Tests cover all 13 acceptance criteria:
 AC1:  IsolatedBlockWrapper wraps LinearBlock, GateBlock, SynthesizeBlock, DispatchBlock
 AC2:  Wrapper exposes self.soul for observer (prompt_hash, soul_version)
 AC3:  Existing block code runs unchanged inside subprocess
 AC4:  All existing block tests pass without modification (structural — no new test)
 AC5:  Agentic loop works through subprocess (LLM → tool → LLM)
 AC6:  Cost/tokens in ResultEnvelope applied to WorkflowState correctly
 AC7:  Stateful blocks: conversation history round-trips (ContextEnvelope → ResultEnvelope)
 AC8:  LoopBlock with subprocess inner blocks: 3 rounds, history carries across rounds
 AC9:  retry_config works: retryable errors retry, non-retryable don't
 AC10: retry_config matches original error type, not SubprocessError
 AC11: timeout_seconds and stall_thresholds added to BaseBlockDef (YAML-configurable)
 AC12: fit_to_budget() runs inside subprocess (no engine-side budgeting)
 AC13: No if/else dispatch in workflow.py — wrapper applied at build time
"""

import asyncio

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.synthesize import SynthesizeBlock
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope
from runsight_core.observer import compute_prompt_hash, compute_soul_version
from runsight_core.primitives import Soul, Task
from runsight_core.state import WorkflowState
from runsight_core.yaml.schema import BaseBlockDef, RetryConfig

# ── Shared fixtures ─────────────────────────────────────────────────────────


def _make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(
        id=soul_id,
        role="Tester",
        system_prompt="You are a test soul.",
        model_name="gpt-4o-mini",
    )


def _make_state(task_instruction: str = "Do something") -> WorkflowState:
    return WorkflowState(
        current_task=Task(id="t1", instruction=task_instruction),
    )


# ==============================================================================
# AC1: IsolatedBlockWrapper wraps LinearBlock, GateBlock, SynthesizeBlock,
#      DispatchBlock — and is itself a BaseBlock
# ==============================================================================


class TestIsolatedBlockWrapperWrapsBlocks:
    """IsolatedBlockWrapper can wrap each LLM block type."""

    def test_import_isolated_block_wrapper(self):
        """IsolatedBlockWrapper is importable from runsight_core.isolation."""
        from runsight_core.isolation import IsolatedBlockWrapper

        assert IsolatedBlockWrapper is not None

    def test_wrapper_is_base_block_subclass(self):
        """IsolatedBlockWrapper must be a BaseBlock subclass."""
        from runsight_core.isolation import IsolatedBlockWrapper

        assert issubclass(IsolatedBlockWrapper, BaseBlock)

    def test_wraps_linear_block(self):
        """IsolatedBlockWrapper can wrap a LinearBlock."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)
        assert wrapper.block_id == "blk1"

    def test_wraps_gate_block(self):
        """IsolatedBlockWrapper can wrap a GateBlock."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = GateBlock("gate1", soul, "eval_blk", runner)
        wrapper = IsolatedBlockWrapper(block_id="gate1", inner_block=inner)
        assert wrapper.block_id == "gate1"

    def test_wraps_synthesize_block(self):
        """IsolatedBlockWrapper can wrap a SynthesizeBlock."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = SynthesizeBlock("synth1", ["a", "b"], soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="synth1", inner_block=inner)
        assert wrapper.block_id == "synth1"

    def test_wraps_dispatch_block(self):
        """IsolatedBlockWrapper can wrap a DispatchBlock."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        branches = [
            DispatchBranch(exit_id="a", label="A", soul=soul, task_instruction="do A"),
        ]
        inner = DispatchBlock("fan1", branches, runner)
        wrapper = IsolatedBlockWrapper(block_id="fan1", inner_block=inner)
        assert wrapper.block_id == "fan1"


# ==============================================================================
# AC2: Wrapper exposes self.soul for observer (prompt_hash, soul_version)
# ==============================================================================


class TestWrapperExposesSoul:
    """The wrapper must expose self.soul from the inner block for telemetry."""

    def test_soul_attribute_from_linear_block(self):
        """Wrapper.soul returns the inner LinearBlock's soul."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)
        assert wrapper.soul is soul

    def test_soul_attribute_from_gate_block(self):
        """Wrapper.soul returns the inner GateBlock's gate_soul."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = GateBlock("gate1", soul, "eval_blk", runner)
        wrapper = IsolatedBlockWrapper(block_id="gate1", inner_block=inner)
        # The wrapper must expose a soul (however it maps the inner block's attribute)
        assert wrapper.soul is not None
        assert compute_prompt_hash(wrapper.soul) == compute_prompt_hash(soul)

    def test_prompt_hash_computable_from_wrapper_soul(self):
        """Observer can compute prompt_hash from wrapper.soul."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)
        assert compute_prompt_hash(wrapper.soul) is not None

    def test_soul_version_computable_from_wrapper_soul(self):
        """Observer can compute soul_version from wrapper.soul."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)
        assert compute_soul_version(wrapper.soul) is not None

    @pytest.mark.asyncio
    async def test_wrapper_envelope_preserves_extended_soul_runtime_fields(self):
        """Subprocess envelope keeps provider/runtime tool-contract fields intact."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = Soul(
            id="tool_soul",
            role="Tester",
            system_prompt="Use tools carefully.",
            model_name="gpt-4o-mini",
            provider="openai",
            temperature=0.0,
            max_tokens=256,
            required_tool_calls=["http_request", "slack_webhook"],
        )
        inner = LinearBlock("blk1", soul, MagicMock())
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)
        captured = {}

        async def _capture(envelope: ContextEnvelope) -> ResultEnvelope:
            captured["envelope"] = envelope
            return ResultEnvelope(
                block_id="blk1",
                output="ok",
                exit_handle="done",
                cost_usd=0.0,
                total_tokens=0,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=[],
                error=None,
                error_type=None,
            )

        wrapper._run_in_subprocess = _capture
        await wrapper.execute(_make_state())

        envelope = captured["envelope"]
        assert envelope.soul.provider == "openai"
        assert envelope.soul.temperature == 0.0
        assert envelope.soul.max_tokens == 256
        assert envelope.soul.required_tool_calls == ["http_request", "slack_webhook"]


# ==============================================================================
# AC3: Existing block code runs unchanged inside subprocess
# ==============================================================================


class TestExistingBlockCodeUnchanged:
    """Wrapper delegates to SubprocessHarness.run(), not direct block.execute()."""

    def test_wrapper_execute_returns_workflow_state(self):
        """Wrapper.execute() returns a WorkflowState (via subprocess)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        # The wrapper should invoke SubprocessHarness, not inner.execute() directly
        mock_result = ResultEnvelope(
            block_id="blk1",
            output="test output",
            exit_handle="done",
            cost_usd=0.001,
            total_tokens=42,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            result_state = asyncio.get_event_loop().run_until_complete(wrapper.execute(state))
        assert isinstance(result_state, WorkflowState)
        assert "blk1" in result_state.results

    def test_inner_block_execute_not_called_directly(self):
        """The wrapper must NOT call inner_block.execute() in the engine process."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        inner.execute = AsyncMock()

        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="blk1",
            output="done",
            exit_handle="done",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

        inner.execute.assert_not_called()


# ==============================================================================
# AC5: Agentic loop works through subprocess (LLM → tool → LLM)
# ==============================================================================


class TestAgenticLoopThroughSubprocess:
    """The agentic tool-call loop must function through the subprocess boundary."""

    def test_tool_calls_count_propagated(self):
        """ResultEnvelope.tool_calls_made is reflected in final state."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="blk1",
            output="result with tools",
            exit_handle="done",
            cost_usd=0.05,
            total_tokens=1500,
            tool_calls_made=3,
            delegate_artifacts={},
            conversation_history=[
                {"role": "user", "content": "prompt"},
                {"role": "assistant", "content": "calling tool"},
                {"role": "tool", "content": "tool result"},
                {"role": "assistant", "content": "result with tools"},
            ],
            error=None,
            error_type=None,
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            result_state = asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

        assert result_state.results["blk1"].output == "result with tools"


# ==============================================================================
# AC6: Cost/tokens in ResultEnvelope applied to WorkflowState correctly
# ==============================================================================


class TestCostTokenPropagation:
    """Cost and token counts from ResultEnvelope must be applied to WorkflowState."""

    def test_cost_usd_applied(self):
        """ResultEnvelope.cost_usd is added to state.total_cost_usd."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="blk1",
            output="ok",
            exit_handle="done",
            cost_usd=0.0042,
            total_tokens=500,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

        state = _make_state()
        state = state.model_copy(update={"total_cost_usd": 0.01})

        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            result_state = asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

        assert result_state.total_cost_usd == pytest.approx(0.01 + 0.0042)

    def test_total_tokens_applied(self):
        """ResultEnvelope.total_tokens is added to state.total_tokens."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="blk1",
            output="ok",
            exit_handle="done",
            cost_usd=0.0,
            total_tokens=750,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

        state = _make_state()
        state = state.model_copy(update={"total_tokens": 100})

        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            result_state = asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

        assert result_state.total_tokens == 100 + 750


# ==============================================================================
# AC7: Stateful blocks — conversation history round-trips
# ==============================================================================


class TestConversationHistoryRoundTrip:
    """Conversation history must survive the ContextEnvelope → ResultEnvelope round-trip."""

    def test_history_returned_in_state(self):
        """ResultEnvelope.conversation_history is written back to state."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        updated_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        mock_result = ResultEnvelope(
            block_id="blk1",
            output="hi there",
            exit_handle="done",
            cost_usd=0.001,
            total_tokens=50,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=updated_history,
            error=None,
            error_type=None,
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            result_state = asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

        # History should be stored under the block_id + soul_id key
        history_key = f"blk1_{soul.id}"
        assert history_key in result_state.conversation_histories
        assert result_state.conversation_histories[history_key] == updated_history

    def test_existing_history_sent_in_envelope(self):
        """Pre-existing conversation history is included in the ContextEnvelope."""
        from unittest.mock import MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        prior_history = [
            {"role": "user", "content": "round 1"},
            {"role": "assistant", "content": "response 1"},
        ]

        state = _make_state()
        history_key = f"blk1_{soul.id}"
        state = state.model_copy(update={"conversation_histories": {history_key: prior_history}})

        captured_envelope = {}

        async def mock_run(envelope: ContextEnvelope) -> ResultEnvelope:
            captured_envelope["val"] = envelope
            return ResultEnvelope(
                block_id="blk1",
                output="ok",
                exit_handle="done",
                cost_usd=0.0,
                total_tokens=0,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=prior_history
                + [
                    {"role": "user", "content": "round 2"},
                    {"role": "assistant", "content": "response 2"},
                ],
                error=None,
                error_type=None,
            )

        with patch.object(wrapper, "_run_in_subprocess", side_effect=mock_run):
            asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

        assert captured_envelope["val"].conversation_history == prior_history


# ==============================================================================
# AC8: LoopBlock with subprocess inner blocks — 3 rounds, history carries
# ==============================================================================


class TestLoopBlockWithSubprocessInnerBlocks:
    """LoopBlock executing wrapped blocks must carry history across rounds."""

    def test_three_round_loop_accumulates_history(self):
        """After 3 loop rounds, conversation history contains all rounds."""
        from unittest.mock import MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("inner_blk", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="inner_blk", inner_block=inner)

        call_count = 0

        async def mock_run(envelope: ContextEnvelope) -> ResultEnvelope:
            nonlocal call_count
            call_count += 1
            # Each round adds to conversation history
            incoming = list(envelope.conversation_history)
            new_history = incoming + [
                {"role": "user", "content": f"round {call_count}"},
                {"role": "assistant", "content": f"response {call_count}"},
            ]
            return ResultEnvelope(
                block_id="inner_blk",
                output=f"output round {call_count}",
                exit_handle="done",
                cost_usd=0.001,
                total_tokens=100,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=new_history,
                error=None,
                error_type=None,
            )

        state = _make_state()

        # Simulate 3 loop rounds manually
        with patch.object(wrapper, "_run_in_subprocess", side_effect=mock_run):
            for _ in range(3):
                state = asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

        history_key = f"inner_blk_{soul.id}"
        history = state.conversation_histories.get(history_key, [])
        # 3 rounds x 2 messages each = 6 messages minimum
        assert len(history) >= 6
        assert call_count == 3


# ==============================================================================
# AC9: retry_config works — retryable errors retry, non-retryable don't
# ==============================================================================


class TestRetryConfigWithWrapper:
    """retry_config on IsolatedBlockWrapper must control retry behavior."""

    def test_wrapper_carries_retry_config(self):
        """IsolatedBlockWrapper preserves retry_config from the inner block definition."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        retry_cfg = RetryConfig(max_attempts=3, non_retryable_errors=["ValueError"])
        wrapper = IsolatedBlockWrapper(
            block_id="blk1",
            inner_block=inner,
            retry_config=retry_cfg,
        )
        assert wrapper.retry_config is not None
        assert wrapper.retry_config.max_attempts == 3

    def test_non_retryable_error_not_retried(self):
        """Errors in non_retryable_errors list are raised immediately, not retried."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(
            block_id="blk1",
            inner_block=inner,
            retry_config=RetryConfig(
                max_attempts=3,
                non_retryable_errors=["ValueError"],
            ),
        )

        # Subprocess returns error with error_type="ValueError"
        mock_result = ResultEnvelope(
            block_id="blk1",
            output=None,
            exit_handle="error",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error="bad value",
            error_type="ValueError",
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            # Should raise a non-retryable error (not SubprocessError)
            with pytest.raises(Exception) as exc_info:
                asyncio.get_event_loop().run_until_complete(wrapper.execute(state))
            # The raised error type name should be "ValueError", not "SubprocessError"
            assert "ValueError" in str(type(exc_info.value).__name__) or "ValueError" in str(
                exc_info.value
            )


# ==============================================================================
# AC10: retry_config matches original error type, not SubprocessError
# ==============================================================================


class TestRetryMatchesOriginalErrorType:
    """Error propagation must use the original error type from ResultEnvelope,
    not a generic SubprocessError wrapper."""

    def test_error_type_from_envelope_used_for_retry_matching(self):
        """The error raised by the wrapper uses ResultEnvelope.error_type, not SubprocessError."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="blk1",
            output=None,
            exit_handle="error",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error="something broke",
            error_type="RuntimeError",
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            with pytest.raises(Exception) as exc_info:
                asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

        # The exception must carry the original error type for retry matching
        # It should NOT be "SubprocessError"
        error = exc_info.value
        # BlockExecutionError should preserve original_error_type
        assert hasattr(error, "original_error_type") or type(error).__name__ != "SubprocessError"
        if hasattr(error, "original_error_type"):
            assert error.original_error_type == "RuntimeError"

    def test_timeout_raises_timeout_error(self):
        """Subprocess timeout raises TimeoutError, not SubprocessError."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        state = _make_state()
        with patch.object(
            wrapper,
            "_run_in_subprocess",
            new_callable=AsyncMock,
            side_effect=TimeoutError("timed out after 30s"),
        ):
            with pytest.raises(TimeoutError):
                asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

    def test_heartbeat_stall_raises_block_stall_error(self):
        """Heartbeat stall raises BlockStallError."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.isolation.errors import BlockStallError

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        state = _make_state()
        with patch.object(
            wrapper,
            "_run_in_subprocess",
            new_callable=AsyncMock,
            side_effect=BlockStallError("stalled in phase 'executing'"),
        ):
            with pytest.raises(BlockStallError):
                asyncio.get_event_loop().run_until_complete(wrapper.execute(state))

    def test_nonzero_exit_raises_block_execution_error(self):
        """Non-zero subprocess exit raises BlockExecutionError."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.isolation.errors import BlockExecutionError

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="blk1",
            output=None,
            exit_handle="error",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error="Process exit error (code 1)",
            error_type="SubprocessError",
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            with pytest.raises(BlockExecutionError):
                asyncio.get_event_loop().run_until_complete(wrapper.execute(state))


# ==============================================================================
# AC11: timeout_seconds and stall_thresholds added to BaseBlockDef
# ==============================================================================


class TestBaseBlockDefSchemaAdditions:
    """BaseBlockDef must include timeout_seconds and stall_thresholds fields."""

    def test_timeout_seconds_field_exists(self):
        """BaseBlockDef has timeout_seconds with default 300."""
        assert "timeout_seconds" in BaseBlockDef.model_fields
        field = BaseBlockDef.model_fields["timeout_seconds"]
        assert field.default == 300

    def test_timeout_seconds_min_value(self):
        """timeout_seconds rejects values < 1."""
        from pydantic import ValidationError
        from runsight_core.blocks.linear import LinearBlockDef

        # First verify the field exists and valid values work
        valid = LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=1)
        assert valid.timeout_seconds == 1
        # Then verify out-of-range is rejected
        with pytest.raises(ValidationError):
            LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=0)

    def test_timeout_seconds_max_value(self):
        """timeout_seconds rejects values > 3600."""
        from pydantic import ValidationError
        from runsight_core.blocks.linear import LinearBlockDef

        # First verify the field exists and valid values work
        valid = LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=3600)
        assert valid.timeout_seconds == 3600
        # Then verify out-of-range is rejected
        with pytest.raises(ValidationError):
            LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=3601)

    def test_timeout_seconds_valid_value(self):
        """timeout_seconds accepts valid values within range."""
        from runsight_core.blocks.linear import LinearBlockDef

        block_def = LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=60)
        assert block_def.timeout_seconds == 60

    def test_stall_thresholds_field_exists(self):
        """BaseBlockDef has stall_thresholds field (optional dict)."""
        assert "stall_thresholds" in BaseBlockDef.model_fields
        field = BaseBlockDef.model_fields["stall_thresholds"]
        assert field.default is None

    def test_stall_thresholds_accepts_dict(self):
        """stall_thresholds can be set to a phase → seconds mapping."""
        from runsight_core.blocks.linear import LinearBlockDef

        block_def = LinearBlockDef(
            type="linear",
            soul_ref="test",
            stall_thresholds={"parsing": 10, "executing": 60},
        )
        assert block_def.stall_thresholds == {"parsing": 10, "executing": 60}

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_timeout_seconds_roundtrip_yaml(self):
        """timeout_seconds survives YAML parse round-trip."""
        import yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  blk1:
    type: linear
    soul_ref: test
    timeout_seconds: 120
workflow:
  name: test_wf
  entry: blk1
  transitions:
    - from: blk1
      to: null
"""
        from unittest.mock import MagicMock

        from runsight_core.yaml.parser import parse_workflow_yaml

        runner = MagicMock()
        parse_workflow_yaml(yaml_str, runner=runner)
        # The parsed workflow accepts the YAML — verify the raw value survived
        raw = yaml.safe_load(yaml_str)
        assert raw["blocks"]["blk1"]["timeout_seconds"] == 120


# ==============================================================================
# AC12: fit_to_budget() runs inside subprocess (no engine-side budgeting)
# ==============================================================================


class TestBudgetFittingInsideSubprocess:
    """The wrapper must NOT call fit_to_budget on the engine side.
    Budget fitting happens inside the subprocess worker."""

    def test_wrapper_does_not_import_fit_to_budget(self):
        """IsolatedBlockWrapper.execute() does not call fit_to_budget."""
        from unittest.mock import AsyncMock, MagicMock, patch

        import runsight_core.memory.budget as budget_module
        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("blk1", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="blk1", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="blk1",
            output="ok",
            exit_handle="done",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            with patch.object(
                budget_module, "fit_to_budget", wraps=budget_module.fit_to_budget
            ) as spy:
                asyncio.get_event_loop().run_until_complete(wrapper.execute(state))
                # fit_to_budget must NOT be called on the engine side
                spy.assert_not_called()


# ==============================================================================
# AC13: No if/else dispatch in workflow.py — wrapper applied at build time
# ==============================================================================


class TestNoDispatchInWorkflow:
    """LLM blocks are wrapped at build time by the parser/builder, not by
    runtime dispatch in workflow.py."""

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parser_returns_wrapped_blocks_for_linear(self):
        """parse_workflow_yaml wraps linear blocks with IsolatedBlockWrapper."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  blk1:
    type: linear
    soul_ref: test
workflow:
  name: test_wf
  entry: blk1
  transitions:
    - from: blk1
      to: null
"""
        runner = MagicMock()
        wf = parse_workflow_yaml(yaml_str, runner=runner)
        block = wf._blocks["blk1"]
        assert isinstance(block, IsolatedBlockWrapper)

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parser_returns_wrapped_blocks_for_gate(self):
        """parse_workflow_yaml wraps gate blocks with IsolatedBlockWrapper."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  producer:
    type: linear
    soul_ref: test
  gate1:
    type: gate
    soul_ref: test
    eval_key: producer
workflow:
  name: test_wf
  entry: producer
  transitions:
    - from: producer
      to: gate1
    - from: gate1
      to: null
"""
        runner = MagicMock()
        wf = parse_workflow_yaml(yaml_str, runner=runner)
        block = wf._blocks["gate1"]
        assert isinstance(block, IsolatedBlockWrapper)

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parser_returns_wrapped_blocks_for_synthesize(self):
        """parse_workflow_yaml wraps synthesize blocks with IsolatedBlockWrapper."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  a:
    type: linear
    soul_ref: test
  b:
    type: linear
    soul_ref: test
  synth:
    type: synthesize
    soul_ref: test
    input_block_ids:
      - a
      - b
workflow:
  name: test_wf
  entry: a
  transitions:
    - from: a
      to: b
    - from: b
      to: synth
    - from: synth
      to: null
"""
        runner = MagicMock()
        wf = parse_workflow_yaml(yaml_str, runner=runner)
        block = wf._blocks["synth"]
        assert isinstance(block, IsolatedBlockWrapper)

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parser_returns_wrapped_blocks_for_dispatch(self):
        """parse_workflow_yaml wraps dispatch blocks with IsolatedBlockWrapper."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  fan:
    type: dispatch
    exits:
      - id: a
        label: A
        soul_ref: test
        task: Do A
      - id: b
        label: B
        soul_ref: test
        task: Do B
workflow:
  name: test_wf
  entry: fan
  transitions:
    - from: fan
      to: null
"""
        runner = MagicMock()
        wf = parse_workflow_yaml(yaml_str, runner=runner)
        block = wf._blocks["fan"]
        assert isinstance(block, IsolatedBlockWrapper)
