"""Isolated wrapper tool output propagation behavior."""

from __future__ import annotations

import asyncio

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ResultEnvelope

pytestmark = pytest.mark.real_subprocess_isolation


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
