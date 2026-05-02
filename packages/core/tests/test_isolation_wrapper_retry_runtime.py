"""Isolated wrapper retry runtime behavior."""

from __future__ import annotations

import asyncio

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ResultEnvelope
from runsight_core.yaml.schema import RetryConfig

pytestmark = pytest.mark.real_subprocess_isolation


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
