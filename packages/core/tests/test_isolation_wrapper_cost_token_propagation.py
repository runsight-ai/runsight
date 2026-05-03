"""Isolated wrapper cost and token propagation behavior."""

from __future__ import annotations

import asyncio

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ResultEnvelope

pytestmark = pytest.mark.real_subprocess_isolation


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
