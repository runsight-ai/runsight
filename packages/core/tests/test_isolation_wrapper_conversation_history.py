"""Isolated wrapper conversation history behavior."""

from __future__ import annotations

import asyncio

from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope


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
