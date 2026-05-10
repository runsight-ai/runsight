"""Isolated wrapper loop subprocess block behavior."""

from __future__ import annotations

import asyncio

import pytest
from isolation_wrapper_helpers import apply_output as _apply_output
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ResultEnvelope
from runsight_core.isolation.workspace import WorkspaceRunRequest

pytestmark = pytest.mark.real_subprocess_isolation


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

        async def mock_run(request: WorkspaceRunRequest) -> ResultEnvelope:
            nonlocal call_count
            call_count += 1
            envelope = request.envelope
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
