"""
LinearBlock builds user messages from _resolved_inputs.

Expected behavior:
- LinearBlock no longer reads state.current_task
- LinearBlock builds its instruction from state.shared_memory["_resolved_inputs"]
- LinearBlock works when _resolved_inputs is empty (produces empty user message)
- LinearBlock works when _resolved_inputs has content from upstream blocks

Implementation contract:
- Read `_resolved_inputs = state.shared_memory.get("_resolved_inputs", {})`
- If _resolved_inputs has content, serialize as instruction string
- If empty, instruction is empty string ""
- Context is None (no current_task to read context from)
- Use runner.execute() in both paths
- No Task import needed
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState


async def _exec(block, state):
    """Helper: build BlockContext, execute block, apply output to state."""
    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exec_result(task_id, soul_id, output, cost=0.0, tokens=0):
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_soul():
    from runsight_core.primitives import Soul

    return Soul(
        id="test_soul",
        kind="soul",
        name="Tester",
        role="Tester",
        system_prompt="You test things.",
        model_name="gpt-4o",
        provider="openai",
    )


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with runner.execute (not execute_task)."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o"
    return runner


def _make_linear_block(block_id, soul, runner):
    from runsight_core.blocks.linear import LinearBlock

    return LinearBlock(block_id, soul, runner)


# ===========================================================================
# 1. Source-level: no Task import in linear.py
# ===========================================================================


class TestStatefulHistoryBuiltFromStrings:
    """Stateful path must build conversation history using string instruction, not Task objects."""

    @pytest.mark.asyncio
    async def test_stateful_path_builds_history_with_user_message(self, sample_soul, mock_runner):
        """After stateful execution, conversation_histories has a user message with string content."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "response from linear"
            )
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        block.stateful = True
        state = WorkflowState()
        new_state = await _exec(block, state)

        history_key = "linear1_test_soul"
        assert history_key in new_state.conversation_histories, (
            f"Expected history key '{history_key}' in conversation_histories. "
            f"Found keys: {list(new_state.conversation_histories.keys())}"
        )
        history = new_state.conversation_histories[history_key]
        assert len(history) > 0

        user_msgs = [m for m in history if m.get("role") == "user"]
        assert len(user_msgs) >= 1, "Expected at least one user message in history"
        user_content = user_msgs[-1]["content"]
        assert isinstance(user_content, str), (
            f"User message content must be a string, got {type(user_content)}"
        )

    @pytest.mark.asyncio
    async def test_stateful_path_history_contains_assistant_response(
        self, sample_soul, mock_runner
    ):
        """After stateful execution, history has an assistant message with the LLM response."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "LLM response text"
            )
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        block.stateful = True
        state = WorkflowState()
        new_state = await _exec(block, state)

        history = new_state.conversation_histories.get("linear1_test_soul", [])
        assistant_msgs = [m for m in history if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1, "Expected at least one assistant message in history"
        assert assistant_msgs[-1]["content"] == "LLM response text"

    @pytest.mark.asyncio
    async def test_stateful_path_does_not_call_build_prompt_with_task(
        self, sample_soul, mock_runner
    ):
        """Stateful path must not call runner._build_prompt(task) — Task object must not be passed."""
        build_prompt_calls = []
        mock_runner._build_prompt = MagicMock(
            side_effect=lambda arg: build_prompt_calls.append(arg)
        )
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "output"
            )
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        block.stateful = True
        state = WorkflowState()
        await _exec(block, state)

        # _build_prompt must not have been called at all (Task is deleted, strings are used directly)
        assert len(build_prompt_calls) == 0, (
            f"_build_prompt was called {len(build_prompt_calls)} time(s) — "
            "stateful path must build prompt from strings without _build_prompt"
        )


# ===========================================================================
# 8. Result stored correctly in state.results
# ===========================================================================
