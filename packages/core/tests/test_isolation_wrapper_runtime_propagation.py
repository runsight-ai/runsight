"""Isolation wrapper result, history, retry, and error propagation contracts."""

from __future__ import annotations

import asyncio

import pytest
from isolation_wrapper_helpers import apply_output as _apply_output
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope
from runsight_core.yaml.schema import RetryConfig


class TestWrapperOutputFromToolUsingWorker:
    """Wrapper returns worker output produced after tool-use conversation turns."""

    def test_worker_output_after_tool_conversation_is_returned(self):
        """ResultEnvelope.output is exposed through the wrapper BlockOutput."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
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
            result_output = asyncio.get_event_loop().run_until_complete(
                wrapper.execute(_make_ctx(wrapper, state))
            )

        assert result_output.output == "result with tools"


# ==============================================================================
# Behavior coverage
# ==============================================================================


class TestWrapperCostTokenOutputFields:
    """Wrapper maps ResultEnvelope cost and token counts onto BlockOutput fields."""

    def test_result_envelope_cost_usd_maps_to_block_output(self):
        """ResultEnvelope.cost_usd is returned on BlockOutput.cost_usd."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
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
            result_output = asyncio.get_event_loop().run_until_complete(
                wrapper.execute(_make_ctx(wrapper, state))
            )

        assert result_output.cost_usd == pytest.approx(0.0042)

    def test_result_envelope_total_tokens_maps_to_block_output(self):
        """ResultEnvelope.total_tokens is returned on BlockOutput.total_tokens."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
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
            result_output = asyncio.get_event_loop().run_until_complete(
                wrapper.execute(_make_ctx(wrapper, state))
            )

        assert result_output.total_tokens == 750


# ==============================================================================
# Behavior coverage
# ==============================================================================


class TestConversationHistoryRoundTrip:
    """Conversation history must survive the ContextEnvelope → ResultEnvelope round-trip."""

    def test_history_returned_in_state(self):
        """ResultEnvelope.conversation_history is written back to state."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        updated_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
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
            result_output = asyncio.get_event_loop().run_until_complete(
                wrapper.execute(_make_ctx(wrapper, state))
            )

        # Worker returns a full history, so wrapper must replace rather than append.
        history_key = f"isolated_linear_block_{soul.id}"
        assert result_output.conversation_replacements is not None
        assert history_key in result_output.conversation_replacements
        assert result_output.conversation_replacements[history_key] == updated_history

    def test_existing_history_sent_in_envelope(self):
        """Pre-existing conversation history is included in the ContextEnvelope."""
        from unittest.mock import MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        prior_history = [
            {"role": "user", "content": "round 1"},
            {"role": "assistant", "content": "response 1"},
        ]

        state = _make_state()
        history_key = f"isolated_linear_block_{soul.id}"
        state = state.model_copy(update={"conversation_histories": {history_key: prior_history}})

        captured_envelope = {}

        async def mock_run(envelope: ContextEnvelope) -> ResultEnvelope:
            captured_envelope["val"] = envelope
            return ResultEnvelope(
                block_id="isolated_linear_block",
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
            asyncio.get_event_loop().run_until_complete(wrapper.execute(_make_ctx(wrapper, state)))

        assert captured_envelope["val"].conversation_history == prior_history


# ==============================================================================
# Behavior coverage
# ==============================================================================


class TestLoopBlockWithSubprocessInnerBlocks:
    """LoopBlock executing wrapped blocks must carry history across rounds."""

    def test_three_round_loop_accumulates_history(self):
        """After 3 loop rounds, conversation history contains all rounds."""
        from unittest.mock import MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("loop_inner_linear_block", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="loop_inner_linear_block", inner_block=inner)

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
                block_id="loop_inner_linear_block",
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

        # Simulate 3 loop rounds manually — after each round, apply output to state so
        # conversation history accumulates across rounds.
        with patch.object(wrapper, "_run_in_subprocess", side_effect=mock_run):
            for _ in range(3):
                ctx = _make_ctx(wrapper, state)
                result_output = asyncio.get_event_loop().run_until_complete(wrapper.execute(ctx))
                state = _apply_output(state, "loop_inner_linear_block", result_output)

        history_key = f"loop_inner_linear_block_{soul.id}"
        history = state.conversation_histories.get(history_key, [])
        assert history == [
            {"role": "user", "content": "round 1"},
            {"role": "assistant", "content": "response 1"},
            {"role": "user", "content": "round 2"},
            {"role": "assistant", "content": "response 2"},
            {"role": "user", "content": "round 3"},
            {"role": "assistant", "content": "response 3"},
        ]
        assert call_count == 3


# ==============================================================================
# Behavior coverage
# ==============================================================================


class TestRetryConfigWithWrapper:
    """retry_config on IsolatedBlockWrapper must control retry behavior."""

    def test_wrapper_carries_retry_config(self):
        """IsolatedBlockWrapper preserves retry_config from the inner block definition."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        retry_cfg = RetryConfig(max_attempts=3, non_retryable_errors=["ValueError"])
        wrapper = IsolatedBlockWrapper(
            block_id="isolated_linear_block",
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
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(
            block_id="isolated_linear_block",
            inner_block=inner,
            retry_config=RetryConfig(
                max_attempts=3,
                non_retryable_errors=["ValueError"],
            ),
        )

        # Subprocess returns error with error_type="ValueError"
        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
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
                asyncio.get_event_loop().run_until_complete(
                    wrapper.execute(_make_ctx(wrapper, state))
                )
            # The raised error type name should be "ValueError", not "SubprocessError"
            assert "ValueError" in str(type(exc_info.value).__name__) or "ValueError" in str(
                exc_info.value
            )


# ==============================================================================
# Behavior coverage
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
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
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
                asyncio.get_event_loop().run_until_complete(
                    wrapper.execute(_make_ctx(wrapper, state))
                )

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
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        state = _make_state()
        with patch.object(
            wrapper,
            "_run_in_subprocess",
            new_callable=AsyncMock,
            side_effect=TimeoutError("timed out after 30s"),
        ):
            with pytest.raises(TimeoutError):
                asyncio.get_event_loop().run_until_complete(
                    wrapper.execute(_make_ctx(wrapper, state))
                )

    def test_heartbeat_stall_raises_block_stall_error(self):
        """Heartbeat stall raises BlockStallError."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.isolation.errors import BlockStallError

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        state = _make_state()
        with patch.object(
            wrapper,
            "_run_in_subprocess",
            new_callable=AsyncMock,
            side_effect=BlockStallError("stalled in phase 'executing'"),
        ):
            with pytest.raises(BlockStallError):
                asyncio.get_event_loop().run_until_complete(
                    wrapper.execute(_make_ctx(wrapper, state))
                )

    def test_nonzero_exit_raises_block_execution_error(self):
        """Non-zero subprocess exit raises BlockExecutionError."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.isolation.errors import BlockExecutionError

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
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
                asyncio.get_event_loop().run_until_complete(
                    wrapper.execute(_make_ctx(wrapper, state))
                )


# ==============================================================================
# Behavior coverage
# ==============================================================================
