"""Isolated block wrapper budget fitting behavior."""

from __future__ import annotations

import asyncio

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ResultEnvelope

pytestmark = pytest.mark.real_subprocess_isolation


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
        inner = LinearBlock("isolated_linear_block", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
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
                asyncio.get_event_loop().run_until_complete(
                    wrapper.execute(_make_ctx(wrapper, state))
                )
                # fit_to_budget must NOT be called on the engine side
                spy.assert_not_called()


# ==============================================================================
# Behavior coverage
# ==============================================================================
